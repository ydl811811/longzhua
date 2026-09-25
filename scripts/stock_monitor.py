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
FEISHU_BOT_URL   = os.getenv('FEISHU_BOT_URL', 'https://open.feishu.cn/open-apis/bot/v2/hook/fbfd7f01-878c-4ece-80e6-5e7324ab3692')
FEISHU_BOT_SECRET = os.getenv('FEISHU_BOT_SECRET', '9vXyEvLigZ70Ynw1YeUtI')

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
        }
    except (ValueError, IndexError) as e:
        return {'err': f'parse: {e}'}


# ─── 持仓监控 ─────────────────────────────────────────────────────────────
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

    # 1. 止损
    sl = cfg.get('stop_loss')
    if sl and price <= float(sl):
        tier = 'stop_loss'
        if state_should_trigger(state, code, tier):
            msg = f'🔴 {name} 触发止损！现价{price:.3f} ≤ 止损{sl}，请确认卖出'
            send_feishu(msg, '🔴')
            state = state_mark(state, code, tier)
            return msg, state

    # 2. 观察线
    wl = cfg.get('watch_line')
    if wl and price <= float(wl):
        tier = 'watch_line'
        if state_should_trigger(state, code, tier):
            msg = f'🚨 {name} 跌破观察线！现价{price:.3f} ≤ {wl}，必须出局！'
            send_feishu(msg, '🚨')
            state = state_mark(state, code, tier)
            return msg, state

    # 3. TP 触达（v3 schema 优先，老 schema fallback）
    tp_list = get_take_profit_list(cfg)
    for tp_item in tp_list:
        target = tp_item.get('target')
        status = tp_item.get('status', 'pending')
        # 跳过已 cleared / done 的 TP（实物化后不再触发）
        if status in ('cleared', 'done'):
            continue
        if target and price >= float(target):
            tier = f"tp{tp_item['level']}"
            if state_should_trigger(state, code, tier):
                reduce_shares = tp_item.get('shares', 0)
                if not reduce_shares:
                    reduce_shares = round(cfg.get('shares', 0) / 3)
                # v3 schema 走 reduction_shares（clear shared state）
                emoji = '🟢' if tp_item.get('level', 1) <= 2 else '⭐'
                if reduce_shares and reduce_shares > 0:
                    msg = f'{emoji} {name} 触及TP{tp_item["level"]}！现价{price:.3f} ≥ {target}，请确认卖出 {reduce_shares} 份'
                else:
                    msg = f'{emoji} {name} 触及TP{tp_item["level"]}！现价{price:.3f} ≥ {target}，请确认卖出'
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
        if target and price <= float(target):
            tier = f"add_pos_{add_item['level']}"
            if state_should_trigger(state, code, tier):
                add_shares = add_item.get('shares', 0)
                if add_shares:
                    msg = f'📥 {name} 加仓{add_item["level"]}信号！现价{price:.3f} ≤ 目标{target}，请确认加仓 {add_shares} 份'
                else:
                    msg = f'📥 {name} 加仓{add_item["level"]}信号！现价{price:.3f} ≤ 目标{target}，请确认加仓'
                msg += f' | 五档比{ratio:.2f}'
                send_feishu(msg, '📥')
                state = state_mark(state, code, tier)
                return msg, state

    # 不触发 → 仅返回状态文本
    sl_str = f'止损{sl}' if sl else ''
    # v3 schema tp list 转 str
    tp_str = ' '.join([f"TP{i['level']}={i['target']}({i.get('status','?')[:3]})" for i in tp_list])
    # LONGZHUA FIXED 2026-08-04: 之前用 TP 循环的 target 变量显示，导致 add_str 始终 None；
    # 现改为直接读 cfg.get('add_position_1_target') / add_position_2_target
    add_str_parts = []
    for a in add_list:
        add_str_parts.append(f"加仓{a['level']}={a['target']}")
    add_str = ' '.join(add_str_parts)
    info = f'{name} {price:.3f}({data["chg_pct"]:+.2f}%) 五档比{ratio:.2f} | {sl_str} | {tp_str} {add_str}'.strip()
    return info, state


# ─── 候选股监控 ───────────────────────────────────────────────────────────
def check_watched(code, name, market, cfg, state):
    """候选股：建仓触发 (entry_max) / reversal / pullback"""
    trigger_price = cfg.get('entry_max')
    ideal_price  = cfg.get('entry_min')
    rmn          = cfg.get('ratio_min', 0)
    sl           = cfg.get('stop_loss')
    sig_type     = cfg.get('signal_type', 'pullback')

    if trigger_price is None:
        return f'{name} 无 entry_max 跳过', state

    data = fetch_stock(code, market)
    if 'err' in data:
        return f'{name} 数据获取失败: {data["err"]}', state

    price = data['price']
    ratio = data['ratio']

    # watch 型：只观察不触发
    if sig_type == 'watch':
        return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 观察中', state

    # reversal 型：反弹站回 entry_max
    if sig_type == 'reversal':
        if price >= float(trigger_price) and ratio >= rmn:
            tier = 'reversal'
            if state_should_trigger(state, code, tier):
                msg = f'✅ {name} 反弹确认！{price:.2f}({data["chg_pct"]:+.2f}%)站回{trigger_price}，五档比{ratio:.2f}'
                if sl: msg += f'，止损{sl}'
                msg += '，请确认建仓'
                send_feishu(msg, '✅')
                state = state_mark(state, code, tier)
                return msg, state
        return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 等反弹≥{trigger_price}', state

    # pullback 型（默认）：回调到 entry_max 以下
    if price <= float(trigger_price) and ratio >= rmn:
        tier = 'pullback'
        if state_should_trigger(state, code, tier):
            msg = f'✅ {name} 建仓信号！{price:.2f}({data["chg_pct"]:+.2f}%)，五档比{ratio:.2f}'
            if sl: msg += f'，止损{sl}'
            msg += '，请确认建仓'
            send_feishu(msg, '✅')
            state = state_mark(state, code, tier)
            return msg, state

    return f'{name} {price:.2f}({data["chg_pct"]:+.2f}%) 等待回调≤{trigger_price}', state


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
