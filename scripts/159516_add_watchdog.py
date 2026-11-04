#!/usr/bin/python3.12
# -*- coding: utf-8 -*-
"""
159516 半导体设备ETF国泰 — 条件加仓盯盘（2026-11-04 建立）

背景：
  11/04 10:05:06 老大买入 10000 份 @ 0.452（4520 元）建仓，止损 0.425。
  老大指示「可以按条件加仓」→ 建三档条件加仓 ladder，由本脚本盯价触发。

三档（配置在台账 monitor_positions.yaml 的 add_position_plan.tiers，脚本读取）：
  tier 1 右侧第一确认  收盘 ≥ MA5        + 量 ≥ 0.8x5日均 + 收盘不贴当日低   → 3000 份
  tier 2 右侧第二确认  收盘 ≥ 0.470      + 连续 2 日收盘站上 MA5            → 2000 份
  tier 3 回踩确认      0.431 ≤ 收盘 ≤ 0.443 + 不破 60 日低 + 有承接 + 缩量   → 2000 份

为什么不用 stock_monitor.py 的 add_position_N_target：
  stock_monitor.py 只支持「现价 ≤ target」触底方向（P0-14 延伸 1）。
  tier 1/2 是「现价 ≥ target」突破方向，方向相反塞进去会误触发。
  → tier 1/2 必须独立脚本；tier 3 虽然是触底方向，但条件含缩量/承接/收盘，
    单一价格判定不够，故三档统一放本脚本，不污染主监控。

两个 cron（同一脚本，按时间自动切模式）：
  盘中 */15 9-15  → mode=intraday，只评 tier 3（回踩企稳需要盘中确认）
  收盘 35 15      → mode=close，评 tier 1/2/3（右侧确认必须用收盘价）

watchdog 模式：无触发 = stdout 为空 = 静默不推送（这是预期行为，不是故障）。
每档 one-shot（state file 永久记录，触发过就不再触发），防同一天连发。

数据源：腾讯 qt.gtimg.cn 实时（价格/量/五档）+ 新浪日K（MA/量能/连续日）
"""

import os
import sys
import json
import time
import hmac
import hashlib
import base64
import urllib.request
import socket
import re
from datetime import datetime, time as dtime

# ─── 强制 IPv4（避免 qt.gtimg.cn 的 IPv6 抖动）────────────────────
_socket_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: _socket_orig(h, p, socket.AF_INET, t, pr, fl)

HOME = os.path.expanduser('~')
POS_FILE = os.path.expanduser('~/.hermes/stock-portfolio/monitor_positions.yaml')
STATE_FILE = os.path.expanduser('~/.hermes/stock-portfolio/.159516_add_state.json')
LOG_FILE = os.path.expanduser('~/.hermes/cron/output/159516_add_watchdog.txt')

CODE = '159516'
MARKET = 'sz'
NAME = '半导体设备ETF国泰'

FEISHU_BOT_URL = os.getenv('FEISHU_BOT_URL', 'https://open.feishu.cn/open-apis/bot/v2/hook/fbfd7f01-878c-4ece-80e6-5e7324ab3692')
FEISHU_BOT_SECRET = os.getenv('FEISHU_BOT_SECRET', '9vXyEvLigZ70Ynw1YeUtI')

VOL_FACTOR = 0.8        # 量能门槛：≥ 5 日均量 0.8 倍
INTRADAY_LOW = 0.431    # 60 日低（破位线）


# ─── 飞书 ─────────────────────────────────────────────────────────────
def _feishu_sign():
    ts = str(int(time.time()))
    s = f'{ts}\n{FEISHU_BOT_SECRET}'
    h = hmac.new(s.encode('utf-8'), digestmod=hashlib.sha256).digest()
    return ts, base64.b64encode(h).decode('utf-8')


def send_feishu(text, emoji='📥'):
    ts, sign = _feishu_sign()
    payload = {'timestamp': ts, 'sign': sign, 'msg_type': 'text',
               'content': {'text': f'{emoji} 龙爪信号\n{text}'}}
    req = urllib.request.Request(
        FEISHU_BOT_URL, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            if data.get('code', 0) != 0:
                print(f'[feishu_err] {data}', file=sys.stderr)
    except Exception as e:
        print(f'[feishu_err] {e}', file=sys.stderr)


# ─── 台账 ─────────────────────────────────────────────────────────────
def load_ledger():
    try:
        import yaml
        with open(POS_FILE) as f:
            d = yaml.safe_load(f)
    except Exception as e:
        print(f'[yaml_err] {e}', file=sys.stderr)
        return None
    for p in d.get('positions', []) or []:
        if str(p.get('code')) == CODE:
            return p
    return None


def load_tiers(pos):
    plan = pos.get('add_position_plan') or {}
    tiers = plan.get('tiers') or []
    out = []
    for t in tiers:
        out.append({
            'level': int(t['level']),
            'name': t.get('name', ''),
            'trigger': t.get('trigger', ''),
            'target': float(t['target']),
            'target_mode': t.get('target_mode', 'fixed'),
            'target_label': t.get('target_label', ''),
            'shares': int(t['shares']),
            'conditions': t.get('conditions', ''),
            'red_lines': t.get('red_lines', ''),
            'chase_limit_pct': float(t.get('chase_limit_pct', 0.02)),
        })
    return sorted(out, key=lambda x: x['level'])


# ─── state（one-shot 去重）──────────────────────────────────────────
def state_load():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {'fired': [], 'warned': []}


def state_save(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)


# ─── 行情 ─────────────────────────────────────────────────────────────
def fetch_quote():
    prefix = MARKET
    try:
        url = f'https://qt.gtimg.cn/q={prefix}{CODE}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0',
                                                   'Referer': 'https://gu.qq.com/'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('gbk', 'ignore')
    except Exception as e:
        return {'err': f'fetch: {e}'}
    m = re.search(r'v_' + prefix + CODE + r'="([^"]+)"', raw)
    if not m:
        return {'err': 'no_match'}
    p = m.group(1).split('~')
    if len(p) < 40:
        return {'err': 'short_data'}
    try:
        price = float(p[3]); prev = float(p[4])
        high = float(p[33]); low = float(p[34])
        vol_shou = float(p[6])          # 手
        ts = p[30]
        bq = sum(float(p[i] or 0) for i in [10, 12, 14, 16, 18])
        sq = sum(float(p[20 + i * 2] or 0) for i in range(5))
        # 涨停价（ETF 10%）+ 封单量（买一）
        limit_price = round(prev * 1.10, 3)
        seal_shares = float(p[10] or 0) * 100
        return {'price': price, 'prev': prev, 'high': high, 'low': low,
                'vol_shou': vol_shou, 'vol_shares': vol_shou * 100, 'ts': ts,
                'chg_pct': (price / prev - 1) * 100 if prev else 0,
                'ratio': bq / sq if sq else 0,
                'limit_price': limit_price,
                'seal_shares': seal_shares,
                # 封板判定：现价触及涨停价 且 卖一~五无挂单（真封板）
                'is_limit_up': price >= limit_price - 1e-6 and sq == 0,
                'sell_sum': sq, 'buy_sum': bq}
    except (ValueError, IndexError) as e:
        return {'err': f'parse: {e}'}


def fetch_kline(datalen=60):
    url = ('https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           'CN_MarketData.getKLineData')
    data = f'symbol={MARKET}{CODE}&scale=240&ma=no&datalen={datalen}'.encode()
    req = urllib.request.Request(url, data=data,
                                 headers={'User-Agent': 'Mozilla/5.0',
                                          'Referer': 'https://finance.sina.com.cn'})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f'[kline_err] {e}', file=sys.stderr)
        return []


def build_series(kl, price, today):
    """返回 (closes[], vols[], ma5_series[], has_today_bar)

    新浪日K 可能滞后（末条不是今天）→ 用腾讯实时价补今天那条。
    """
    rows = [k for k in kl]
    has_today = bool(rows) and rows[-1].get('day') == today
    closes = [float(k['close']) for k in rows]
    vols = [float(k['volume']) for k in rows]
    if has_today:
        # 用实时价覆盖今日（更准）
        closes[-1] = price
        vols[-1] = 0.0     # 今日量从腾讯取，不从新浪取
    else:
        closes.append(price)
        vols.append(0.0)
    ma5 = []
    for i in range(len(closes)):
        if i >= 4:
            ma5.append(sum(closes[i - 4:i + 1]) / 5)
        else:
            ma5.append(None)
    return closes, vols, ma5, has_today


def vol5_avg(vols, has_today):
    """5 日均量：取今天之前的 5 个交易日（排除今日）

    build_series 已保证 vols[-1] 恒为今日占位（0），故 vols[:-1] 恒为历史日。
    """
    hist = vols[:-1][-5:]
    return sum(hist) / len(hist) if hist else 0


# ─── 时间 ─────────────────────────────────────────────────────────────
def mode_of(now):
    """'close' | 'intraday' | None

    close 模式最早 15:05 起 —— 15:00 是收盘集合竞价，此刻「收盘价」尚未定型，
    右侧确认必须等竞价结束后再判。15:00-15:05 返回 None = 静默。
    """
    t = now.time()
    if now.weekday() >= 5:
        return None
    if t >= dtime(15, 5):
        return 'close'
    if dtime(9, 30) <= t <= dtime(11, 30) or dtime(13, 0) <= t < dtime(15, 0):
        return 'intraday'
    return None


# ─── 判定 ─────────────────────────────────────────────────────────────
def eval_tiers(tiers, q, closes, ma5, v5, mode, fired, pos_take_profit=None):
    """判定加仓档。互斥规则（防止一天推两条加仓指令）：

    - tier 2（右侧第二确认）要求 tier 1 已经触发过 → 右侧阶梯递进，不跳级
    - tier 3（回踩确认）是「跌下来接」的反向路径，要求 tier 1/2 都没触发过
      → 右侧走了就不再回头接，底部接了就不再追高，两条路径互斥
    - 单次运行最多命中一档（取 level 最小的命中项）

    同理 tier 1 要求 tier 2 尚未触发（tier 2 触发说明右侧已走完一轮）。
    """
    price = q['price']
    low = q['low']
    high = q['high']
    vol = q['vol_shares']
    ratio = q['ratio']
    today_close = closes[-1]
    ma5_today = ma5[-1]
    ma5_prev = ma5[-2] if len(ma5) >= 2 else None
    prev_close = closes[-2] if len(closes) >= 2 else None
    vol_ok = v5 > 0 and vol >= v5 * VOL_FACTOR
    vol_low = v5 > 0 and vol <= v5 * VOL_FACTOR
    streak2 = (ma5_prev is not None and prev_close is not None
               and prev_close >= ma5_prev and today_close >= ma5_today)

    results = []
    # ── 2026-11-04 机制修正：涨停封板 / 追高禁令 / 与 TP 互斥 ──
    # 1) 涨停封板禁止加仓：封板价无法成交（封单排队），且 R/R 已崩
    # 2) 追高禁令：加仓触发价低于现价 2% 以上 = 追高（§8.9 铁律）
    # 3) 与 TP 互斥：已有 TP 档位触发 → 同日不再加仓（先减后加 = 自相矛盾）
    tp_hit = any(pos_tp.get('status') == 'pending'
                 and price >= float(pos_tp.get('target') or 0)
                 for pos_tp in (pos_take_profit or []))
    for t in tiers:
        if t['level'] in fired:
            continue
        ok = False
        detail = []
        if t['trigger'] == 'breakout':
            if mode != 'close':
                continue
            # 互斥：tier1 要求 tier2 未触发；tier2 要求 tier1 已触发
            if t['level'] == 1 and 2 in fired:
                continue
            if t['level'] == 2 and 1 not in fired:
                continue
            tgt = ma5_today if t['target_mode'] == 'ma5' else t['target']
            if tgt is None:
                continue
            # ── 新增：涨停封板禁止加仓 ──
            if q.get('is_limit_up'):
                continue
            # ── 新增：与 TP 互斥（已有 TP 触发 → 今日不加仓）──
            if tp_hit:
                continue
            # ── 新增：追高禁令（触发价低于现价 chase_limit 以上 = 追高）──
            # chase_limit 按档位配置：MA5 动态档 2%（紧），固定结构位档可放宽
            chase_limit = float(t.get('chase_limit_pct', 0.02))
            chase_gap = (price - tgt) / tgt
            if chase_gap > chase_limit:
                continue
            if t['target_mode'] == 'ma5':
                detail.append(f'MA5={tgt:.4f}(当日实算)')
            else:
                detail.append(f'目标{tgt:.3f}({t["target_label"]})')
            if today_close < tgt:
                continue
            detail.append(f'收盘{today_close:.3f} ≥ {tgt:.4f}')
            if t['level'] == 1:
                if not vol_ok:
                    continue
                detail.append(f'量{vol/1e8:.2f}亿 ≥ 5日均{v5/1e8:.2f}亿×0.8')
                if high > 0 and (today_close - low) / high < 0.01:
                    continue
                detail.append('收盘不贴当日低')
            else:
                if not streak2:
                    continue
                detail.append('连续 2 日收盘站上 MA5')
            ok = True
        elif t['trigger'] == 'pullback':
            # 互斥：右侧档已触发就不再回头接（避免一边追高一边接跌）
            if 1 in fired or 2 in fired:
                continue
            # ── 新增：涨停封板不回踩（不可能同时封板又回踩）──
            if q.get('is_limit_up'):
                continue
            if mode == 'intraday':
                if not (0.435 <= price <= t['target']):
                    continue
                if low < INTRADAY_LOW:
                    continue
                if price <= low:
                    continue
                if ratio < 1.0:
                    continue
                detail.append(f'现价{price:.3f}∈[0.435,{t["target"]:.3f}]')
                detail.append(f'今日低{low:.3f}未破60日低{INTRADAY_LOW}')
                detail.append(f'五档比{ratio:.2f}≥1.0')
            else:
                if not (INTRADAY_LOW <= today_close <= t['target']):
                    continue
                if low < INTRADAY_LOW:
                    continue
                if today_close <= low:
                    continue
                if not vol_low:
                    continue
                detail.append(f'收盘{today_close:.3f}∈[{INTRADAY_LOW},{t["target"]:.3f}]')
                detail.append(f'今日低{low:.3f}未破60日低')
                detail.append(f'收盘高于当日低=有承接')
                detail.append(f'量{vol/1e8:.2f}亿 ≤ 5日均{v5/1e8:.2f}亿×0.8=缩量')
            ok = True
        if ok:
            results.append((t, detail))
            break          # 单次最多命中一档
    return results


# ─── 主逻辑 ───────────────────────────────────────────────────────────
def main():
    now = datetime.now()
    mode = mode_of(now)
    if mode is None:
        print('')
        return 0

    pos = load_ledger()
    if not pos:
        print('')
        return 0
    if pos.get('status') != 'holding':
        print('')
        return 0
    plan = pos.get('add_position_plan') or {}
    if not plan.get('enabled'):
        print('')
        return 0

    tiers = load_tiers(pos)
    if not tiers:
        print('')
        return 0

    q = fetch_quote()
    if 'err' in q:
        print('')
        return 0
    today = now.strftime('%Y-%m-%d')
    # 数据新鲜度：腾讯快照必须是今天，否则是休市/停牌旧值 → 静默
    if not q['ts'].startswith(now.strftime('%Y%m%d')):
        print('')
        return 0

    kl = fetch_kline(60)
    if not kl:
        print('')
        return 0
    closes, vols, ma5, has_today = build_series(kl, q['price'], today)
    v5 = vol5_avg(vols, has_today)

    st = state_load()
    fired = set(st.get('fired', []))
    warned = set(st.get('warned', []))

    log_lines = [f'{CODE} {NAME} {now.strftime("%Y-%m-%d %H:%M:%S")} mode={mode}',
                 f'  现价 {q["price"]:.3f} ({q["chg_pct"]:+.2f}%) 日内[{q["low"]:.3f}-{q["high"]:.3f}] '
                 f'量 {q["vol_shares"]/1e8:.2f}亿股 5日均 {v5/1e8:.2f}亿股 五档比 {q["ratio"]:.2f} '
                 f'MA5 {ma5[-1]:.4f}']

    msgs = []

    # 0. 破位停加仓预警（0.431 破位，止损 0.425 之前）
    if q['price'] < INTRADAY_LOW and 'break_0431' not in warned:
        sl = pos.get('stop_loss', 0.425)
        msgs.append(
            f'🔴 {NAME} {CODE} 破 60 日低 {INTRADAY_LOW}！结构破位\n'
            f'现价 {q["price"]:.3f} < {INTRADAY_LOW}（今日低 {q["low"]:.3f}，五档比 {q["ratio"]:.2f}）\n'
            f'持仓 {pos.get("shares")} 份 @ 成本 {pos.get("cost")}\n'
            f'→ 全部加仓档暂停（tier 1/2/3 取消触发）。距止损 {sl} 只剩 '
            f'{(q["price"]/sl-1)*100:+.2f}%。破 {sl} 我会推清仓。')
        warned.add('break_0431')

    # 1. 加仓档判定
    hits = eval_tiers(tiers, q, closes, ma5, v5, mode, fired,
                      pos_take_profit=pos.get('take_profit') or [])
    for t, detail in hits:
        amt = t['target'] * t['shares']
        msg = (f'📥 {NAME} {CODE} 加仓档 {t["level"]}「{t["name"]}」触发！\n'
               f'持仓 {pos.get("shares")} 份 @ 成本 {pos.get("cost")}，现价 {q["price"]:.3f}'
               f'（{q["chg_pct"]:+.2f}%，五档比 {q["ratio"]:.2f}）\n'
               f'条件命中：' + ' + '.join(detail) + '\n'
               f'→ 建议加仓 {t["shares"]} 份（参考 {amt:.0f} 元）。加完均价会变，'
               f'记得发成交截图给我，我更新台账 + 重算 TP 份数。\n'
               f'⚠️ 红线：{t["red_lines"]}')
        msgs.append(msg)
        fired.add(t['level'])

    # 1b. 涨停封板预警：加仓全部冻结（2026-11-04 机制修正）
    if q.get('is_limit_up') and 'limit_up' not in warned:
        seal_yi = q.get('seal_shares', 0) / 1e8
        tp_targets = [f"{tp.get('target')}" for tp in (pos.get('take_profit') or [])
                      if tp.get('status') == 'pending'
                      and q['price'] >= float(tp.get('target') or 0)]
        msgs.append(
            f'🔴 {NAME} {CODE} 涨停封板 {q["price"]:.3f}！加仓档全部冻结\n'
            f'封单 {seal_yi:.2f} 亿份（排队买入实际无法成交）\n'
            f'持仓 {pos.get("shares")} 份 @ 成本 {pos.get("cost")}，浮盈 '
            f'{(q["price"]-float(pos.get("cost")))*pos.get("shares",0):+.0f} 元\n'
            + (f'⚠️ 已触发 TP 档位：{", ".join(tp_targets)} → 明日 T+1 后执行减仓\n'
               if tp_targets else '')
            + '→ 涨停日不追高加仓（§8.9 铁律：买点位置 >70% 禁止追）。'
              '等回踩企稳或直接走 TP 减仓。'
        )
        warned.add('limit_up')

    if msgs:
        for m in msgs:
            send_feishu(m, '🔴' if m.startswith('🔴') else '📥')

    st['fired'] = sorted(fired)
    st['warned'] = sorted(warned)
    st['last_run'] = now.strftime('%Y-%m-%d %H:%M:%S')
    st['last_price'] = q['price']
    state_save(st)

    log_lines.append(f'  已触发档位: {sorted(fired) or "无"}')
    out = '=== 159516 加仓盯盘 ===\n' + '\n'.join(log_lines)
    if msgs:
        out += '\n\n触发:\n' + '\n\n'.join(msgs)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'w') as f:
        f.write(out)

    if msgs:
        print(out)
    else:
        print('')
    return 0


if __name__ == '__main__':
    sys.exit(main())
