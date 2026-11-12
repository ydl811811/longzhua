#!/usr/bin/python3.12
# -*- coding: utf-8 -*-
"""
统一的股票监控脚本 — 替代 market_alert.py / monitor_513120_add.py / duofluo_monitor.py 等

数据源：
- ~/.hermes/stock-portfolio/monitor_positions.yaml （持仓，status=holding 才监控）
- ~/.hermes/stock-portfolio/monitor_watched.yaml  （候选股，entry_max 触发建仓）
- ~/.hermes/stock-portfolio/monitor_buy_signals.yaml （加仓信号，灵活配置 — 可选）

监控逻辑：
1. 持仓：止损 (stop_loss) / 观察线 (watch_line) / TP1/TP2/TP3 / 补仓位 (add_position_1/2_target)
2. 候选股：建仓触发 (entry_max) / 反弹型 (reversal) / 回调型 (pullback) / 观察型 (watch)
3. 单只股单维度每日只触发一次（写入 state file）

交易时段过滤：
- A 股: 9:30-11:30 + 13:00-15:00
- 其他时间静默，不推送不写文件

飞书：触发即推 webhook（带签名）
"""

import os
import re
import sys
import json
import time
import hmac
import hashlib
import base64
import urllib.request
import socket
from datetime import datetime, time as dtime

from feishu_bot import load_feishu_creds

# ─── 强制 IPv4（避免 qt.gtimg.cn 的 IPv6 抖动）────────────────────────────────
_socket_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: _socket_orig(h, p, socket.AF_INET, t, pr, fl)

# ─── 路径常量 ─────────────────────────────────────────────────────────────
HOME = os.path.expanduser('~')
POS_FILE      = os.path.expanduser('~/.hermes/stock-portfolio/monitor_positions.yaml')
WATCH_FILE    = os.path.expanduser('~/.hermes/stock-portfolio/monitor_watched.yaml')
OBSERVED_FILE = os.path.expanduser('~/.hermes/stock-portfolio/monitor_observed.yaml')  # 仅记录不主动预警
BUY_FILE      = os.path.expanduser('~/.hermes/stock-portfolio/monitor_buy_signals.yaml')  # 可选
STATE_FILE  = os.path.expanduser('~/.hermes/stock-portfolio/.stock_monitor_state.json')
LOG_FILE    = os.path.expanduser('~/.hermes/cron/output/stock_monitor.txt')

# ─── 飞书机器人 ───────────────────────────────────────────────────────────
FEISHU_BOT_URL, FEISHU_BOT_SECRET = load_feishu_creds()


def get_take_profit_list(cfg):
    """v3 schema 优先：读 cfg['take_profit'] list
    老 schema fallback：read take_profit_1/2/3 → 转 list
    返回 [{level, target, shares, status, condition}, ...]"""
    tp = cfg.get('take_profit')
    if isinstance(tp, list):
        return tp
    # 老 schema fallback
    result = []
    for level, key in enumerate(['take_profit_1', 'take_profit_2', 'take_profit_3'], start=1):
        target = cfg.get(key)
        if target:
            result.append({
                'level': level,
                'target': float(target),
                'shares': cfg.get(f'{key}_reduce_shares', 0),
                'status': cfg.get(f'{key}_status', 'pending'),
                'condition': cfg.get(f'{key}_note', ''),
                'old_key': key  # 标记老 key，方便 trace
            })
    return result

def get_effective_stop_loss(cfg, tp_list):
    """生效止损 = max(基础 stop_loss, 已成交 TP 对应的移动止损)

    2026-11-10 新增（515790 SL/TP 重算）：TP 成交后止损上移，不再手改 stop_loss 字段。
    台账写法：
        stop_loss: 0.708            # 基础硬止损（未成交任何 TP 时生效）
        trailing_stop:
          after_tp1: 0.730          # take_profit level 1 的 status 变为 done/cleared 后生效
          after_tp2: 0.750
    生效口径：取所有「已成交档位」对应移动止损与基础止损的最大值（止损只能上移，永不下移）。
    未成交的 TP 不参与计算。
    """
    base = cfg.get('stop_loss')
    vals = []
    if base:
        try:
            vals.append(float(base))
        except (TypeError, ValueError):
            pass
    trail = cfg.get('trailing_stop') or {}
    if isinstance(trail, dict):
        for tp_item in (tp_list or []):
            lvl = tp_item.get('level')
            st = str(tp_item.get('status', 'pending'))
            if st not in ('done', 'cleared'):
                continue
            v = trail.get(f'after_tp{lvl}')
            if v is not None:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
    return max(vals) if vals else None


def get_add_position_list(cfg):
    """v3 schema：不在主台账（pending_orders.yaml 独立文件）
    老 schema fallback：read add_position_1/2_target"""
    result = []
    for n in range(1, 5):
        target = cfg.get(f'add_position_{n}_target')
        if target:
            result.append({
                'level': n,
                'target': float(target),
                'shares': cfg.get(f'add_position_{n}_shares', 0),
                'status': cfg.get(f'add_position_{n}_status', 'pending'),
                'old_key': f'add_position_{n}_target'
            })
    return result


# ─── 交易时段 ─────────────────────────────────────────────────────────────
A_SH_MORNING_OPEN  = dtime(9, 30)
A_SH_MORNING_CLOSE = dtime(11, 30)
A_SH_AFTER_OPEN    = dtime(13, 0)
A_SH_AFTER_CLOSE   = dtime(15, 0)


def is_trading_hours(now=None):
    """A 股交易时段：9:30-11:30 + 13:00-15:00（工作日）"""
    now = now or datetime.now()
    if now.weekday() >= 5:  # 周六周日
        return False
    t = now.time()
    return (A_SH_MORNING_OPEN <= t <= A_SH_MORNING_CLOSE) or (A_SH_AFTER_OPEN <= t <= A_SH_AFTER_CLOSE)


# ─── 飞书推送 ─────────────────────────────────────────────────────────────
def _feishu_sign():
    ts = str(int(time.time()))
    s = f'{ts}\n{FEISHU_BOT_SECRET}'
    h = hmac.new(s.encode('utf-8'), digestmod=hashlib.sha256).digest()
    return ts, base64.b64encode(h).decode('utf-8')


def send_feishu(text, emoji='🐉'):
    """推送到飞书 home 群"""
    ts, sign = _feishu_sign()
    payload = {
        'timestamp': ts,
        'sign': sign,
        'msg_type': 'text',
        'content': {'text': f'{emoji} 龙爪信号\n{text}'}
    }
    req = urllib.request.Request(
        FEISHU_BOT_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            if data.get('code', 0) != 0:
                print(f'[feishu_err] {data}')
            return data
    except Exception as e:
        print(f'[feishu_err] {e}')
        return None


# ─── 状态管理 ─────────────────────────────────────────────────────────────
def state_load():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {'date': '', 'triggered': {}}  # triggered: {code: [tier, ...]}


def state_save(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)


def state_should_trigger(state, code, tier):
    """同一交易日同一标的同一维度只触发一次"""
    today = datetime.now().strftime('%Y-%m-%d')
    if state.get('date') != today:
        # 新一天 → 重置
        state = {'date': today, 'triggered': {}}
    triggered = state['triggered'].get(code, [])
    return tier not in triggered


def state_mark(state, code, tier):
    today = datetime.now().strftime('%Y-%m-%d')
    if state.get('date') != today:
        state = {'date': today, 'triggered': {}}
    state['triggered'].setdefault(code, [])
    if tier not in state['triggered'][code]:
        state['triggered'][code].append(tier)
    return state


# ─── 数据抓取（腾讯 qt.gtimg.cn）────────────────────────────────────────
def fetch_stock(code, market='sz'):
    """返回 dict: price, prev_close, open, high, low, change_pct, volume, ratio(五档比)"""
    prefix = 'sh' if market == 'sh' else 'sz'
    try:
        url = f'https://qt.gtimg.cn/q={prefix}{code}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('gbk')
    except Exception as e:
        return {'err': f'fetch: {e}'}

    m = re.search(r'v_' + prefix + str(code) + r'="([^"]+)"', raw)
    if not m:
        return {'err': 'no_match'}
    parts = m.group(1).split('~')
    if len(parts) < 35:
        return {'err': 'short_data'}

    try:
        price     = float(parts[3])
        prev      = float(parts[4])
        op        = float(parts[5])
        high      = float(parts[33])
        low       = float(parts[34])
        chg_pct   = (price / prev - 1) * 100 if prev else 0

        # 五档买盘（10, 12, 14, 16, 18）/ 卖盘（20, 22, 24, 26, 28）
        buy_vols = [int(parts[i]) for i in [10, 12, 14, 16, 18]]
        sell_vols = [int(parts[i]) for i in [20, 22, 24, 26, 28]]
        total_buy = sum(buy_vols)
        total_sell = sum(sell_vols)
        ratio = total_buy / total_sell if total_sell > 0 else (10.0 if total_buy > 0 else 0)
        # 异常过滤（防止昨收数据触发）
        if ratio > 100:
            ratio = 0  # 视为废数据

        return {
            'price': price, 'prev': prev, 'open': op,
            'high': high, 'low': low, 'chg_pct': chg_pct,
            'volume': int(parts[6]) if len(parts) > 6 else 0,
            'ratio': ratio,
            'buy_vols': buy_vols, 'sell_vols': sell_vols,
            # 行情快照时间戳 YYYYMMDDHHMMSS（parts[30]）——用于判定 high/low
            # 属于哪一天，避免盘前拿到上一交易日残留极值。
            'quote_ts': parts[30] if len(parts) > 30 else '',
        }
    except (ValueError, IndexError) as e:
        return {'err': f'parse: {e}'}


# ─── 持仓监控 ─────────────────────────────────────────────────────────────
def resolve_extremes(data):
    """从行情快照解析出上/下行触发源。

    返回 (up_price, down_price, day_high, day_low)：
      up_price   = max(现价, 当日最高)  → 用于 TP / 涨到触发位（reversal）
      down_price = min(现价, 当日最低)  → 用于 止损 / 预警 / 跌到触发位（pullback）

    两个护栏（缺一不可）：
    1. 防御性校验：极值必须落在 0 < low <= 现价 <= high，否则退回纯现价口径。
       否则腾讯偶发返回 0 时 min(price, 0)=0 → 全量持仓止损立即误触发。
    2. 跨日守卫：腾讯在盘前/非交易时段返回的是「上一交易日」的完整快照
       （parts[30] 时间戳形如 20261111161445），直接采信其 high/low 会让
       次日开盘第一轮读到昨日极值 → 推一条完全错误的预警/止损。
       故要求 quote_ts 前 8 位 == 今天的 YYYYMMDD。
    """
    price = float(data['price'])
    try:
        day_high = float(data.get('high') or 0)
        day_low = float(data.get('low') or 0)
    except (TypeError, ValueError):
        day_high = day_low = 0.0
    if not (0 < day_high and day_high >= price):
        day_high = 0.0
    if not (0 < day_low <= price):
        day_low = 0.0
    quote_ts = str(data.get('quote_ts') or '')
    if quote_ts[:8] != datetime.now().strftime('%Y%m%d'):
        day_high = 0.0
        day_low = 0.0
    up_price = max(price, day_high) if day_high else price
    down_price = min(price, day_low) if day_low else price
    return up_price, down_price, day_high, day_low


def check_position(code, name, market, cfg, state):
    """持仓：止损 / 观察线 / TP1-3 / 补仓位"""
    if cfg.get('status') != 'holding':
        return None  # 只监控 holding 状态的持仓

    data = fetch_stock(code, market)
    if 'err' in data:
        return f'{name} 数据获取失败: {data["err"]}'

    price = data['price']
    ratio = data['ratio']
    msgs = []

    # ── 2026-11-11 修复：触发源取「现价 + 当日极值」中更激进的一侧 ────────
    # 背景：cron 每 5 分钟采样「现价」，盘中瞬间冲高/跳水若在两个采样点之间发生，
    # 就会被判成「没触达」。2026-11-11 实测：159583 旧 TP2 = 1.154，腾讯行情
    # parts[33]（当日最高）= 1.154 已触达，但分时逐笔最高仅 1.152、采样现价更低
    # → TP2 从未触发 = 漏提醒。
    # 口径：TP/上行线用 max(现价, 当日最高)；止损/下行线用 min(现价, 当日最低)。
    # 解析与两个护栏统一走 resolve_extremes()（候选股同一套口径）。
    up_price, down_price, day_high, day_low = resolve_extremes(data)

    # 1. 止损
    sl = cfg.get('stop_loss')
    # ── 2026-10-26 修复（观察期口径，与集合竞价日报 10/26 同口径）────────
    # observation_mode_*.enabled 的持仓，红线是 exit_line 不是台账 stop_loss：
    #   513050 SL 1.06 vs 现价 0.946 (-10.8%)、159326 SL 1.50 vs 1.433 (-4.5%)
    #   两条 stop_loss 早已失效，继续按它推送 = 每日假止损噪音。
    # exit_line（离场线）+ 减亏线由 remaining3_watchdog.py 独占推送
    #   （cron 2683e138ccda 15:35 收盘 + 2ecb3813de71 */15 盘中），本脚本不重复推。
    obs = cfg.get('observation_mode_20261023') or {}
    obs_on = bool(obs.get('enabled')) and obs.get('exit_line') is not None
    if obs_on:
        sl = float(obs['exit_line'])   # 显示用红线改成离场线
    tp_list = get_take_profit_list(cfg)
    # ── 2026-11-10 新增：生效止损 = max(基础 stop_loss, 已成交 TP 的移动止损) ──
    # 触发口径 = 盘中触发（live price ≤ 生效止损即推），不采用收盘确认。
    # 依据（515790 300 日样本重算）：同止损位下收盘确认→次日开盘仅 +1.4pp 胜率，
    # 尾部却由 -208 元恶化到 -519 元（跳空风险），故否决收盘确认。
    eff_sl = get_effective_stop_loss(cfg, tp_list)
    if not obs_on and eff_sl is not None and down_price <= eff_sl:
        tier = 'stop_loss'
        if state_should_trigger(state, code, tier):
            base_sl = cfg.get('stop_loss')
            trail = (cfg.get('trailing_stop') or {})
            moved = ''
            if base_sl is not None and eff_sl != float(base_sl):
                moved = f'（已移动止损，基础 {base_sl} → {eff_sl}）'
            extra = f'（当日最低 {day_low:.3f}）' if day_low and day_low < price else ''
            msg = f'🔴 {name} 触发止损！现价{price:.3f}{extra} ≤ 止损{eff_sl}{moved}，请确认卖出'
            send_feishu(msg, '🔴')
            state = state_mark(state, code, tier)
            return msg, state

    # 2. 观察线
    wl = cfg.get('watch_line')
    if wl and down_price <= float(wl):
        tier = 'watch_line'
        if state_should_trigger(state, code, tier):
            extra = f'（当日最低 {day_low:.3f}）' if day_low and day_low < price else ''
            msg = f'🚨 {name} 跌破观察线！现价{price:.3f}{extra} ≤ {wl}，必须出局！'
            send_feishu(msg, '🚨')
            state = state_mark(state, code, tier)
            return msg, state

    # 2b. 预警线（2026-11-10 新增，515790 0.722）
    # 语义 = 只提醒，不减仓不清仓；与 stop_loss 分属不同字段 + 不同去重档位（tier=warn_line）。
    # 排序在止损之后：价格同时跌破 0.708 与 0.722 时，止损优先（硬风控 > 提示）。
    warn_l = cfg.get('warn_line')
    if warn_l and down_price <= float(warn_l):
        tier = 'warn_line'
        if state_should_trigger(state, code, tier):
            extra = f'（当日最低 {day_low:.3f}）' if day_low and day_low < price else ''
            msg = (f'⚠️ {name} 跌破预警线！现价{price:.3f}{extra} ≤ {warn_l}（仅预警，不减仓不清仓）。'
                   f'硬止损 {eff_sl}，跌破才清仓。')
            send_feishu(msg, '⚠️')
            state = state_mark(state, code, tier)
            return msg, state

    # 3. TP 触达（v3 schema 优先，老 schema fallback）
    # ── 2026-11-04 新增：T+1 可卖性校验（老大纠正「今天刚买，应该无法卖出」）──
    # A 股 ETF 买入当日不可卖。若全部筹码都是今日买入 → 今日 TP 不可执行，
    # 只提示「T+1 锁定，明日执行」，不推「请确认卖出」误导动作。
    today_str = datetime.now().strftime('%Y-%m-%d')
    batches = cfg.get('entry_batches') or []
    locked_shares = sum(int(b.get('shares') or 0) for b in batches
                        if str(b.get('date')) == today_str)
    total_shares = int(cfg.get('shares') or 0)
    sellable_shares = max(0, total_shares - locked_shares)
    for tp_item in tp_list:
        target = tp_item.get('target')
        status = tp_item.get('status', 'pending')
        # 跳过已 cleared / done 的 TP（实物化后不再触发）
        # 2026-10-26: suspended 也跳过（159326 8/17 B 方案老大手动挂起 TP1-3，
        #   挂起状态不应由脚本自动恢复推送）
        # 2026-11-05: not_executed_by_owner 也跳过（159516 老大明确「已经封板，我不想卖」
        #   → TP1/TP2/TP3 三档全部作废；若不跳过，明天会再次推「请确认卖出」）
        if status in ('cleared', 'done', 'suspended', 'not_executed_by_owner'):
            continue
        if target and up_price >= float(target):
            tier = f"tp{tp_item['level']}"
            if state_should_trigger(state, code, tier):
                reduce_shares = tp_item.get('shares', 0)
                if not reduce_shares:
                    reduce_shares = round(cfg.get('shares', 0) / 3)
                # v3 schema 走 reduction_shares（clear shared state）
                emoji = '🟢' if tp_item.get('level', 1) <= 2 else '⭐'
                # 触发价标注：现价未达但当日最高已达时，文案用当日最高并注明来源，
                # 避免老大看到「现价 1.147 ≥ 目标 1.154」这种自相矛盾的表述。
                if up_price > price:
                    px_txt = f'当日最高 {up_price:.3f}'
                else:
                    px_txt = f'现价 {price:.3f}'
                # ── T+1 校验：可卖份数不足 → 不推「请确认卖出」，改推明日执行 ──
                if reduce_shares and reduce_shares > sellable_shares:
                    msg = (f'{emoji} {name} 触及TP{tp_item["level"]}！{px_txt} ≥ {target}，'
                           f'但今日买入 {locked_shares} 份 T+1 锁定（可卖 {sellable_shares} 份）'
                           f'→ 明日(T+1)开盘执行卖出 {reduce_shares} 份')
                    msg += f' | 五档比{ratio:.2f}'
                    send_feishu(msg, emoji)
                    state = state_mark(state, code, tier)
                    return msg, state
                if reduce_shares and reduce_shares > 0:
                    msg = f'{emoji} {name} 触及TP{tp_item["level"]}！{px_txt} ≥ {target}，请确认卖出 {reduce_shares} 份'
                else:
                    msg = f'{emoji} {name} 触及TP{tp_item["level"]}！{px_txt} ≥ {target}，请确认卖出'
                # ── 2026-11-10 成交登记指引 ──
                # 卖出在券商 App 由老大执行；执行后必须登记台账 status → done，
                # 否则移动止损不会生效（生效止损仍停在基础 SL），且持仓份额口径错。
                msg += (f' | 成交后请回复龙爪登记（自动改 status=done + 扣减份额 + 上移止损）：'
                        f'「{code} TP{tp_item["level"]} 已卖 {reduce_shares} 份 @ 实际成交价」'
                        f'（或手动跑 tp_exec.py {code} {tp_item["level"]} --price <成交价>）')
                msg += f' | 五档比{ratio:.2f}'
                send_feishu(msg, emoji)
                state = state_mark(state, code, tier)
                return msg, state

    # 4. 补仓位（v3 schema 已在 pending_orders.yaml；fallback 老字段）
    add_list = get_add_position_list(cfg)
    for add_item in add_list:
        target = add_item.get('target')
        status = add_item.get('status', 'pending')
        # 已 cancelled / filled / expired 不再触发
        if status in ('cancelled', 'filled', 'expired'):
            continue
        if target and down_price <= float(target):
            tier = f"add_pos_{add_item['level']}"
            if state_should_trigger(state, code, tier):
                add_shares = add_item.get('shares', 0)
                extra = f'（当日最低 {day_low:.3f}）' if day_low and day_low < price else ''
                if add_shares:
                    msg = f'📥 {name} 加仓{add_item["level"]}信号！现价{price:.3f}{extra} ≤ 目标{target}，请确认加仓 {add_shares} 份'
                else:
                    msg = f'📥 {name} 加仓{add_item["level"]}信号！现价{price:.3f}{extra} ≤ 目标{target}，请确认加仓'
                msg += f' | 五档比{ratio:.2f}'
                send_feishu(msg, '📥')
                state = state_mark(state, code, tier)
                return msg, state

    # 不触发 → 仅返回状态文本
    # 2026-10-26: 返回纯字符串（不是 tuple）→ 调用方不会把它塞进 triggered_msgs
    if obs_on:
        sl_str = f'离场线{sl}'
        mode_tag = '[观察期]'
    else:
        sl_str = f'止损{sl}' if sl else ''
        if eff_sl is not None and sl is not None and eff_sl != float(sl):
            sl_str = f'止损{sl}→生效{eff_sl}'
        mode_tag = ''
    warn_l = cfg.get('warn_line')
    if warn_l:
        sl_str += f' 预警{warn_l}'
    # v3 schema tp list 转 str
    tp_str = ' '.join([f"TP{i['level']}={i['target']}({i.get('status','?')[:3]})" for i in tp_list])
    # LONGZHUA FIXED 2026-08-04: 之前用 TP 循环的 target 变量显示，导致 add_str 始终 None；
    # 现改为直接读 cfg.get('add_position_1_target') / add_position_2_target
    add_str_parts = []
    for a in add_list:
        add_str_parts.append(f"加仓{a['level']}={a['target']}")
    add_str = ' '.join(add_str_parts)
    head = f'{name} {price:.3f}({data["chg_pct"]:+.2f}%) 五档比{ratio:.2f}'
    if mode_tag:
        head += f' {mode_tag}'
    info = f'{head} | {sl_str} | {tp_str} {add_str}'.strip()
    return info


# ─── 候选股监控 ───────────────────────────────────────────────────────────
def check_watched(code, name, market, cfg, state):
    """候选股：建仓触发 (entry_max) / reversal / pullback

    ── 2026-11-11 改造：状态语义 → 穿越语义 ──────────────────────────────
    旧逻辑：reversal 型判「现价 >= entry_max」= 状态判断。后果有两类，都实测到：
      (a) 长期站在触发位之上的票（300629/159869/159928/512480）每天重推一遍
          「反弹确认」—— 状态重置（state 按交易日重置）后就再推一次，纯噪音；
      (b) 已经在接货区上方的票还会推「请确认建仓」—— 300629 台账明写
          「等回踩 17.3-17.5 接货，不追高」，但现价 18.43 仍被判为「站回17.5」，
          等于推了一条追高信号。
    新逻辑：判「穿越」—— 触发价是盘中被穿越的那一侧，且必须是从触发位另一侧
      走过来的。entry_max 上方 = 上穿触发（reversal/new_theme）；
      entry_max 下方 = 下穿触发（pullback）。
      穿越方向由 prev（昨收）与触发位的关系决定：
        prev < 触发位 且 现价/极值 >= 触发位  → 上穿 → 成立
        prev >= 触发位 且 现价/极值 < 触发位  → 下穿 → 成立（pullback 回调）
      「长期站在上方」= prev >= 触发位 且 现价仍 >= 触发位 → 无穿越 → 不推。
    极值口径与持仓统一走 resolve_extremes()（含防御校验 + 跨日守卫）。
    """
    trigger_price = cfg.get('entry_max')
    ideal_price  = cfg.get('entry_min')
    rmn          = cfg.get('ratio_min', 0)
    sl           = cfg.get('stop_loss')
    sig_type     = cfg.get('signal_type', 'pullback')
    # 观察型：只提示触达评估位，不推建仓指令（老大明确「观察不改档」的票）
    observe_only = bool(cfg.get('observe_only')) or str(cfg.get('status', '')).startswith('cleared_')

    if trigger_price is None:
        return f'{name} 无 entry_max 跳过'

    data = fetch_stock(code, market)
    if 'err' in data:
        return f'{name} 数据获取失败: {data["err"]}'

    price = data['price']
    ratio = data['ratio']
    prev  = data.get('prev') or price
    up_price, down_price, day_high, day_low = resolve_extremes(data)
    trigger_price = float(trigger_price)
    prev_f = float(prev)

    # ── 跨日守卫（候选股专属，比持仓更严）────────────────────────────────
    # 穿越判定需要「昨收 prev」和「今日现价/极值」属于同一个交易日链条。
    # 腾讯在盘前/非交易时段返回的是上一交易日的完整快照（quote_ts 形如
    # 20261111161445），此时 price = 上一交易日收盘、prev = 上上一交易日收盘。
    # 若拿它算穿越：明日开盘前会推出「昨天发生的上穿」= 过期信号。
    # 故非今日快照一律不评估穿越。
    quote_ts = str(data.get('quote_ts') or '')
    if quote_ts[:8] != datetime.now().strftime('%Y%m%d'):
        return (f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 行情快照非今日'
                f'（{quote_ts or "无时间戳"}），暂不评估穿越')

    # watch 型：只观察不触发
    if sig_type == 'watch':
        return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 观察中'

    # ── 2026-10-23 修复 2 坑（备份 stock_monitor.py.bak.20261023_0950_pre_new_theme_fix）──
    #
    # 坑 1：已跌破自身止损位的候选，一律不推建仓信号。
    #       P0-15 四件套里 remove_triggers 定义了"收盘价 < stop_loss → 移出候选"，
    #       在止损位下方再喊"请确认建仓"是自相矛盾的信号（2026-10-23 09:30 英维克
    #       42.80 < SL 43.0、09:35 禾望电气 21.89 < SL 25.0 被推建仓信号）。
    # 2026-11-11：改用 down_price（当日最低）判定 —— 盘中破位后收回也要拦住，
    #       否则「当日最低已破 SL」仍会被推建仓信号。
    if sl and down_price <= float(sl):
        return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 已破止损{sl}，不触发建仓'

    # ── 穿越判定（状态语义 → 穿越语义）────────────────────────────────────
    # 上穿：昨收在触发位下方，今日盘中/收盘已上到触发位或之上
    cross_up   = (prev_f < trigger_price) and (up_price >= trigger_price)
    # 下穿：昨收在触发位上方，今日盘中/收盘已下到触发位或之下
    cross_down = (prev_f >= trigger_price) and (down_price < trigger_price)

    def _price_label(direction):
        """触发价展示：来自极值时写「当日最高/最低」，否则写「现价」

        direction: 'up' 用当日最高，'down' 用当日最低 —— 必须与触发方向一致，
        否则会出现「当日最高 1.240 下穿 1.22」这种方向自相矛盾的文案。
        """
        if direction == 'up' and up_price > price and abs(up_price - price) > 1e-9:
            return f'当日最高 {up_price:.3f}'
        if direction == 'down' and down_price < price and abs(down_price - price) > 1e-9:
            return f'当日最低 {down_price:.3f}'
        return f'现价 {price:.3f}'

    _lbl_up = _price_label('up')
    _lbl_down = _price_label('down')

    def _emit(tier, msg):
        send_feishu(msg, '✅')
        st = state_mark(state, code, tier)
        return msg, st

    # 坑 2：new_theme 型（status=waiting_observe）的触发方向是"涨到 entry_max"
    #       （距 60 日高点收窄至 -25% 内），不是"跌到 entry_max 以下"。
    #       旧代码让 new_theme 落到默认 pullback 分支 → 现价远低于 entry_max 时恒成立
    #       → 9/30 英维克 / 9/35 禾望电气 假建仓信号（两者都远在 entry_max 之下，
    #       涨到 82.86 / 50.25 才够到建仓评估位）。
    if sig_type == 'new_theme':
        if cross_up and ratio >= rmn:
            tier = 'new_theme'
            if state_should_trigger(state, code, tier):
                msg = (f'✅ {name} 达到建仓评估位！{_lbl_up} ≥ {trigger_price:g}，'
                       f'五档比{ratio:.2f}')
                if sl: msg += f'，止损{sl}'
                msg += '，请确认建仓' if not observe_only else '，（观察位触达，不构成下单指令）'
                return _emit(tier, msg)
        return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 等待涨至{trigger_price:g}'

    # reversal 型：反弹站回 entry_max（穿越语义：昨收在下方 → 今日上穿）
    if sig_type == 'reversal':
        if cross_up and ratio >= rmn:
            tier = 'reversal'
            if state_should_trigger(state, code, tier):
                msg = (f'✅ {name} 反弹确认！{_lbl_up}上穿{trigger_price:g}，'
                       f'五档比{ratio:.2f}')
                if sl: msg += f'，止损{sl}'
                msg += '，请确认建仓' if not observe_only else '，（观察位触达，不构成下单指令）'
                return _emit(tier, msg)
        if up_price >= trigger_price:
            # 已在上方 —— 若不是今日上穿，就是「长期站上方」，不再重复推
            return (f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 已在{trigger_price:g}上方'
                    f'（非今日上穿，不重复提示）')
        return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 等反弹上穿{trigger_price:g}'

    # pullback 型（默认）：回调到 entry_max 以下（穿越语义：昨收在上方 → 今日下穿）
    if cross_down and ratio >= rmn:
        tier = 'pullback'
        if state_should_trigger(state, code, tier):
            msg = (f'✅ {name} 建仓信号！{_lbl_down}下穿{trigger_price:g}，'
                   f'五档比{ratio:.2f}')
            if sl: msg += f'，止损{sl}'
            msg += '，请确认建仓' if not observe_only else '，（观察位触达，不构成下单指令）'
            return _emit(tier, msg)
    if down_price < trigger_price:
        return (f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 已在{trigger_price:g}下方'
                f'（非今日下穿，不重复提示）')
    return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 等待回调下穿{trigger_price:g}'


# ─── YAML 解析（最简版，避免依赖 PyYAML）──────────────────────────────────
def parse_simple_yaml(text):
    """极简 YAML 解析：只支持 list of dict / list of list + 单字段"""
    lines = []
    for line in text.split('\n'):
        # 去除注释
        if line.strip().startswith('#') or not line.strip():
            continue
        # 提取缩进和内容
        m = re.match(r'^(\s*)(.+?):\s*(.*)$', line)
        if m:
            indent = len(m.group(1))
            key = m.group(2).strip()
            val = m.group(3).strip().strip('"').strip("'")
            lines.append((indent, key, val))
        elif line.strip().startswith('- '):
            # 列表项（暂简化）
            lines.append((0, '_list_item', line.strip()[2:].strip()))

    # 简化方案：用 PyYAML（如果装了）
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        # fallback: 让 caller 用 try/except
        raise RuntimeError("需要 PyYAML")


def load_yaml(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return parse_simple_yaml(f.read())


# ─── 主入口 ───────────────────────────────────────────────────────────────
def main():
    # 1. 交易时段过滤（非交易时段直接返回，不推不写）
    if not is_trading_hours():
        now = datetime.now().strftime('%H:%M:%S')
        print(f'[{now}] 非交易时段，跳过监控')
        return 0

    state = state_load()

    # 2. 持仓监控
    triggered_msgs = []
    log_lines = []
    try:
        pos_cfg = load_yaml(POS_FILE)
        for s in (pos_cfg.get('positions') or []):
            code = str(s.get('code', ''))
            name = s.get('name', '')
            market = s.get('market', 'sz')
            result = check_position(code, name, market, s, state)
            if result:
                if isinstance(result, tuple):
                    msg, state = result
                    triggered_msgs.append(msg)
                else:
                    msg = result
                log_lines.append(f'{code} {name}: {msg}')
    except Exception as e:
        log_lines.append(f'持仓监控异常: {e}')

    # 3. 候选股监控
    holding_codes = set()
    try:
        pos_cfg = load_yaml(POS_FILE)
        for s in (pos_cfg.get('positions') or []):
            if s.get('status') == 'holding':
                holding_codes.add(str(s.get('code', '')))
    except Exception:
        pass

    try:
        watch_cfg = load_yaml(WATCH_FILE)
        for s in (watch_cfg.get('watched') or []):
            code = str(s.get('code', ''))
            # 去重：已经在持仓的票不再触发候选股建仓信号
            if code in holding_codes:
                continue
            # 去重：候选股自己标记 status=done（已建仓）的也跳过
            if s.get('status') == 'done':
                continue
            name = s.get('name', '')
            market = s.get('market', 'sz')
            result = check_watched(code, name, market, s, state)
            if result:
                if isinstance(result, tuple):
                    msg, state = result
                    triggered_msgs.append(msg)
                else:
                    msg = result
                log_lines.append(f'[候选] {code} {name}: {msg}')
    except Exception as e:
        log_lines.append(f'候选监控异常: {e}')

    # 4. 加仓信号监控（可选）
    if os.path.exists(BUY_FILE):
        try:
            buy_cfg = load_yaml(BUY_FILE)
            # buy_signals 字段灵活自定义
            for s in (buy_cfg.get('signals') or []):
                code = str(s.get('code', ''))
                name = s.get('name', '')
                market = s.get('market', 'sz')
                # 自定义条件：price_low / price_high / volume_ratio
                data = fetch_stock(code, market)
                if 'err' in data:
                    continue
                price = data['price']
                ratio = data['ratio']
                cond = s.get('condition', '')
                tier = f"buy_{s.get('label', 'custom')}"
                triggered = False
                if s.get('price_low') and price <= float(s['price_low']):
                    triggered = True
                elif s.get('price_high') and price >= float(s['price_high']):
                    triggered = True
                if s.get('volume_ratio_min') and ratio < float(s['volume_ratio_min']):
                    triggered = False

                if triggered and state_should_trigger(state, code, tier):
                    msg = f'🚀 {name} 加仓信号！{price:.3f}({data["chg_pct"]:+.2f}%) 五档比{ratio:.2f}，条件：{cond}'
                    send_feishu(msg, '🚀')
                    state = state_mark(state, code, tier)
                    triggered_msgs.append(msg)
                    log_lines.append(f'[加仓] {code} {name}: {msg}')
        except Exception as e:
            log_lines.append(f'加仓监控异常: {e}')

    # 5. 写状态 + 日志
    state_save(state)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    out = f'=== 股票监控 {now} ===\n' + '\n'.join(log_lines)
    if triggered_msgs:
        out += '\n\n⚠️ 触发:\n' + '\n'.join(triggered_msgs)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'w') as f:
        f.write(out)
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
