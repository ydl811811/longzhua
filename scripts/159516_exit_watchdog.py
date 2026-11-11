#!/usr/bin/python3.12
# -*- coding: utf-8 -*-
"""
159516 半导体设备ETF国泰 — 离场协议盯盘（2026-11-06 建立）

背景：
  11/06 08:57 老大定开盘价口径离场协议（台账 exit_protocol_20261106）：
    开盘 <= 0.481      → 市价清 5000 份（跳空穿硬止损）
    开盘 0.481~0.5184  → 清 5000 份
    开盘 0.5184~0.525  → 清 5000 份（警戒线被破 = 主力托单撤）
    开盘 >= 0.525      → 持有 5000 份不动；盘中跌破 0.5184 → 清 5000 份

为什么不用 stock_monitor.py 的 stop_loss / watch_line：
  1. 止损字段 stop_loss=0.481 是「跳空穿」的兜底线，不是主离场线（主离场线 0.5184/0.525）
  2. 本协议的 b4 分支需要「开盘 >= 0.525 才持有」这一开盘前置条件 —— stock_monitor 是
     纯盘中价判定，没有「开盘价」概念，无法表达「先看开盘，再决定盘中用哪条线」
  3. 参照 159516_add_watchdog.py 的做法（加仓方向 stock_monitor 不支持 → 独立脚本）

两个 cron（同一脚本，按时间自动切模式）：
  开盘模式 31 9 * * 1-5   → 只判开盘价，命中 b1~b3 即清仓提醒（b4 不动）
  盘中模式 */5 9-15 * * 1-5 → 只在「开盘 >= 0.525 已持有」前提下盯跌破 0.5184

watchdog 模式：无触发 = stdout 为空 = 静默不推送（这是预期行为，不是故障）。
每个分支每日只推一次（state file 去重）。

数据源：腾讯 qt.gtimg.cn 实时（现价/开盘价/五档）
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

from feishu_bot import load_feishu_creds

# ─── 强制 IPv4（避免 qt.gtimg.cn 的 IPv6 抖动）────────────────────
_socket_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: _socket_orig(h, p, socket.AF_INET, t, pr, fl)

HOME = os.path.expanduser('~')
POS_FILE = os.path.expanduser('~/.hermes/stock-portfolio/monitor_positions.yaml')
STATE_FILE = os.path.expanduser('~/.hermes/stock-portfolio/.159516_exit_state.json')
LOG_FILE = os.path.expanduser('~/.hermes/cron/output/159516_exit_watchdog.txt')

CODE = '159516'
MARKET = 'sz'
NAME = '半导体设备ETF国泰'

FEISHU_BOT_URL, FEISHU_BOT_SECRET = load_feishu_creds()


# ─── 协议参数（与台账 exit_protocol_20261106 一致）──────────────
LINE_STOP = 0.481     # b1 上沿：开盘 <= 0.481 → 市价清（跳空穿硬止损）
LINE_SELL = 0.5184    # b2/b3 下沿 / b4 盘中触发线
LINE_ALERT = 0.525    # b3/b4 分界：警戒线（开板后 4 次低点托单线）
CLEAR_SHARES = 5000


def _feishu_sign():
    ts = str(int(time.time()))
    s = f'{ts}\n{FEISHU_BOT_SECRET}'
    h = hmac.new(s.encode('utf-8'), digestmod=hashlib.sha256).digest()
    return ts, base64.b64encode(h).decode('utf-8')


def send_feishu(text, emoji='🔴'):
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


def fetch_quote():
    prefix = MARKET
    try:
        url = f'https://qt.gtimg.cn/q={prefix}{CODE}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('gbk')
    except Exception as e:
        return {'err': f'fetch: {e}'}
    m = re.search(r'v_' + prefix + str(CODE) + r'="([^"]+)"', raw)
    if not m:
        return {'err': 'no_match'}
    parts = m.group(1).split('~')
    if len(parts) < 35:
        return {'err': 'short_data'}
    try:
        bv = [int(parts[i] or 0) for i in (10, 12, 14, 16, 18)]
        sv = [int(parts[i] or 0) for i in (20, 22, 24, 26, 28)]
        tb, ts_ = sum(bv), sum(sv)
        return {
            'price': float(parts[3]), 'prev': float(parts[4]), 'open': float(parts[5]),
            'high': float(parts[33]), 'low': float(parts[34]), 'chg_pct': float(parts[32]),
            'ratio': (tb / ts_ if ts_ else 0), 'ts': parts[30],
            'bid1': parts[9], 'bid1_vol': bv[0], 'ask1': parts[19], 'ask1_vol': sv[0],
        }
    except (ValueError, IndexError) as e:
        return {'err': f'parse: {e}'}


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


def state_load():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def state_save(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)


def mode_of(now):
    """返回 'open' / 'intraday' / None（不推）"""
    if now.weekday() >= 5:
        return None
    t = now.time()
    # 开盘判定窗口：09:31~09:59（09:30 集合竞价撮合后 open 价已定）
    if dtime(9, 31) <= t <= dtime(9, 59):
        return 'open'
    # 盘中窗口：09:30~11:30 + 13:00~15:00
    if (dtime(9, 30) <= t <= dtime(11, 30)) or (dtime(13, 0) <= t <= dtime(15, 0)):
        return 'intraday'
    return None


def build_msg(branch, q, pos):
    op = q['open']
    cost = float(pos.get('cost') or 0)
    sh = int(pos.get('shares') or 0)
    pnl = (q['price'] - cost) * sh if cost else 0
    pnl_pct = (q['price'] / cost - 1) * 100 if cost else 0
    if branch == 'b1':
        act = '开盘 <= 0.481 = 跳空穿硬止损 → 市价清仓，不等反弹'
    elif branch == 'b2':
        act = '开盘落在 0.481~0.5184 = 开盘已破次级警戒 → 清仓'
    elif branch == 'b3':
        act = '开盘落在 0.5184~0.525 = 警戒线 0.525 被破（主力托单撤）→ 清仓'
    else:
        act = '盘中跌破 0.5184 → 清仓'
    return (f'🔴 {NAME} {CODE} 触发离场协议 {branch}！\n'
            f'{act}\n'
            f'开盘 {op:.3f}  现价 {q["price"]:.3f}（{q["chg_pct"]:+.2f}%）  昨收 {q["prev"]:.3f}\n'
            f'持仓 {sh} 份 @ 成本 {cost}，现价实现 {pnl:+.0f} 元 / {pnl_pct:+.2f}%\n'
            f'五档比 {q["ratio"]:.2f}（买一 {q["bid1"]}/{q["bid1_vol"]} 手 vs 卖一 {q["ask1"]}/{q["ask1_vol"]} 手）\n'
            f'→ 请确认卖出 {CLEAR_SHARES} 份。你在 App 手动下单，我改台账。')


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
    # 已清仓 → 静默
    if pos.get('status') != 'holding':
        print('')
        return 0
    shares = int(pos.get('shares') or 0)
    if shares <= 0:
        print('')
        return 0

    q = fetch_quote()
    if 'err' in q:
        print('')
        return 0

    state = state_load()
    today = now.strftime('%Y-%m-%d')
    fired = set(state.get(today, []))
    msgs = []
    log_lines = []

    op = q['open']
    price = q['price']

    log_lines.append(
        f'{CODE} {NAME} mode={mode} 现价{price:.3f} 开盘{op:.3f} 昨收{q["prev"]:.3f} '
        f'({q["chg_pct"]:+.2f}%) 五档比{q["ratio"]:.2f} 持仓{shares}份 '
        f'[线: {LINE_STOP}/{LINE_SELL}/{LINE_ALERT}]')

    if mode == 'open':
        # 开盘判定：b1 / b2 / b3 → 清；b4 → 持有（记录状态，不推）
        if op <= LINE_STOP:
            branch = 'b1'
        elif op <= LINE_SELL:
            branch = 'b2'
        elif op < LINE_ALERT:
            branch = 'b3'
        else:
            branch = 'b4'
        if branch == 'b4':
            # 持有档 → 标记当日状态，供盘中模式读取（不推送）
            state[today] = sorted(fired | {'held_b4'})
            state_save(state)
            log_lines.append('  → b4 开盘 >= 0.525，持有 5000 份不动（已记入 state，盘中跌破 0.5184 再清）')
        else:
            key = f'open_{branch}'
            if key not in fired:
                msg = build_msg(branch, q, pos)
                send_feishu(msg, '🔴')
                fired.add(key)
                msgs.append(msg)
                state[today] = sorted(fired)
                state_save(state)
    else:
        # 盘中判定：仅当 b4（开盘 >= 0.525 持有）时才盯跌破 0.5184
        if 'held_b4' not in fired:
            log_lines.append('  → 非 b4 持有档（开盘即清仓分支），盘中不重复推')
        elif price < LINE_SELL:
            key = 'intraday_b4_break'
            if key not in fired:
                msg = build_msg('b4_intraday', q, pos)
                send_feishu(msg, '🔴')
                fired.add(key)
                msgs.append(msg)
                state[today] = sorted(fired)
                state_save(state)
        else:
            log_lines.append(f'  → 持有中，现价 {price:.3f} 未跌破 {LINE_SELL}')

    out = f'=== 159516 离场盯盘 {now:%Y-%m-%d %H:%M:%S} ===\n' + '\n'.join(log_lines)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'w') as f:
        f.write(out)

    # watchdog 模式：只有触发才输出到 stdout（空 = 静默不推送）
    if msgs:
        print(out + '\n\n⚠️ 触发:\n' + '\n'.join(msgs))
    else:
        print('')
    return 0


if __name__ == '__main__':
    sys.exit(main())
