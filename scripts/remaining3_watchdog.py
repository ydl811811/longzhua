#!/usr/bin/python3.12
# -*- coding: utf-8 -*-
"""
剩余 3 只持仓观察期盯盘 — 2026-10-23 清仓 3 只后建立

背景：
  10/23 上午清仓 515980 / 159327 / 562800 三只（实现 -2,898.7 元）。
  剩余 3 只按老大指示"再观察一下"，但必须有关键位提醒，不能无声持有。

监控标的与触发线（价位均为 10/23 实测 K 线 + 实时价）：
  159299 金融科技  离场线 0.620（台账 SL）      减亏线 0.654 (MA5) / 0.665 (MA20)
  513050 中概互联  离场线 0.927（今日低/60日低） 减亏线 0.985 (MA5) / 1.006 (MA20)
  159326 电网设备  离场线 1.394（今日低）        减亏线 1.462 (MA5) / 1.477 (MA10)

两条线的语义：
  离场线 = 破位/止损，清仓提醒（红）
  减亏线 = 反弹到均线，减亏离场提醒（黄）—— 不是加仓信号

watchdog 模式：无触发时 stdout 为空 = 静默不推送。
每只票每条线每日只推一次（state file 去重）。

数据源：腾讯 qt.gtimg.cn 实时（复用 stock_monitor.py 的 fetch_stock / send_feishu）
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
from datetime import datetime

# ─── 强制 IPv4（避免 qt.gtimg.cn 的 IPv6 抖动）────────────────────
_socket_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: _socket_orig(h, p, socket.AF_INET, t, pr, fl)

HOME = os.path.expanduser('~')
POS_FILE = os.path.expanduser('~/.hermes/stock-portfolio/monitor_positions.yaml')
STATE_FILE = os.path.expanduser('~/.hermes/stock-portfolio/.remaining3_watchdog_state.json')
LOG_FILE = os.path.expanduser('~/.hermes/cron/output/remaining3_watchdog.txt')

FEISHU_BOT_URL = os.getenv('FEISHU_BOT_URL', 'https://open.feishu.cn/open-apis/bot/v2/hook/fbfd7f01-878c-4ece-80e6-5e7324ab3692')
FEISHU_BOT_SECRET = os.getenv('FEISHU_BOT_SECRET', '9vXyEvLigZ70Ynw1YeUtI')

# ─── 监控配置：离场线 + 减亏线 ─────────────────────────────────────
# exit_line: 破位/止损 → 清仓提醒
# relief_lines: [(价位, 标签)] 反弹到均线 → 减亏离场提醒
WATCH = {
    '159299': {
        'name': '金融科技ETF易方达', 'market': 'sz',
        'exit_line': 0.620, 'exit_label': '台账止损 0.620',
        'relief_lines': [(0.654, 'MA5'), (0.665, 'MA20')],
    },
    '513050': {
        'name': '中概互联网ETF易方达', 'market': 'sh',
        'exit_line': 0.927, 'exit_label': '今日低/60日低 0.927',
        'relief_lines': [(0.985, 'MA5'), (1.006, 'MA20')],
    },
    '159326': {
        'name': '电网设备ETF华夏', 'market': 'sz',
        'exit_line': 1.394, 'exit_label': '今日低 1.394',
        'relief_lines': [(1.462, 'MA5'), (1.477, 'MA10')],
    },
}


def _feishu_sign():
    ts = str(int(time.time()))
    s = f'{ts}\n{FEISHU_BOT_SECRET}'
    h = hmac.new(s.encode('utf-8'), digestmod=hashlib.sha256).digest()
    return ts, base64.b64encode(h).decode('utf-8')


def send_feishu(text, emoji='🐉'):
    ts, sign = _feishu_sign()
    payload = {
        'timestamp': ts, 'sign': sign, 'msg_type': 'text',
        'content': {'text': f'{emoji} 龙爪信号\n{text}'}
    }
    req = urllib.request.Request(
        FEISHU_BOT_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            if data.get('code', 0) != 0:
                print(f'[feishu_err] {data}')
    except Exception as e:
        print(f'[feishu_err] {e}')


def fetch_stock(code, market):
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
        price = float(parts[3])
        prev = float(parts[4])
        high = float(parts[33])
        low = float(parts[34])
        chg = (price / prev - 1) * 100 if prev else 0
        bq = sum(float(parts[i] or 0) for i in [10, 12, 14, 16, 18])
        sq = sum(float(parts[i] or 0) for i in [20, 22, 24, 26, 28])
        ratio = bq / sq if sq else 0
        return {'price': price, 'prev': prev, 'high': high, 'low': low,
                'chg_pct': chg, 'ratio': ratio}
    except (ValueError, IndexError) as e:
        return {'err': f'parse: {e}'}


def load_holdings():
    """从台账读 holding 段（market 字段以台账为准，陷阱 22）"""
    try:
        import yaml
        with open(POS_FILE) as f:
            d = yaml.safe_load(f)
    except Exception as e:
        print(f'[yaml_err] {e}')
        return {}
    out = {}
    for p in d.get('positions', []) or []:
        if p.get('status') != 'holding':
            continue
        code = str(p.get('code', ''))
        if code in WATCH:
            out[code] = p
    return out


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


def is_trading_hours(now=None):
    now = now or datetime.now()
    t = now.time()
    from datetime import time as dtime
    return ((dtime(9, 30) <= t <= dtime(11, 30)) or
            (dtime(13, 0) <= t <= dtime(15, 0))) and now.weekday() < 5


def main():
    if not is_trading_hours():
        print('')
        return 0

    holdings = load_holdings()
    if not holdings:
        print('')
        return 0

    state = state_load()
    today = datetime.now().strftime('%Y-%m-%d')
    msgs = []
    log_lines = []

    for code, cfg in WATCH.items():
        if code not in holdings:
            # 已清仓 → 跳过
            continue
        pos = holdings[code]
        data = fetch_stock(code, cfg['market'])
        if 'err' in data:
            log_lines.append(f'{code} {cfg["name"]}: 数据获取失败 {data["err"]}')
            continue

        price = data['price']
        key = f'{code}|{today}'
        fired = set(state.get(key, []))

        sh = pos.get('shares', 0)
        cost = pos.get('cost', 0)
        pnl_pct = (price / cost - 1) * 100 if cost else 0

        log_lines.append(
            f'{code} {cfg["name"]:<16} {price:.3f}({data["chg_pct"]:+.2f}%) '
            f'五档比{data["ratio"]:.2f} 日内[{data["low"]:.3f}-{data["high"]:.3f}] '
            f'成本{cost} 浮亏{pnl_pct:+.1f}% 离场线{cfg["exit_line"]}')

        # 1. 离场线（破位/止损）→ 清仓提醒
        ek = f'exit_{cfg["exit_line"]}'
        if price <= cfg['exit_line'] and ek not in fired:
            msg = (f'🔴 {cfg["name"]} {code} 破离场线 {cfg["exit_label"]}！\n'
                   f'现价 {price:.3f} ≤ {cfg["exit_line"]}（{data["chg_pct"]:+.2f}%，五档比 {data["ratio"]:.2f}）\n'
                   f'持仓 {sh} 份 @ 成本 {cost}，浮亏 {pnl_pct:+.1f}%\n'
                   f'→ 按观察期纪律：清仓离场。要留就明说，我改离场线。')
            send_feishu(msg, '🔴')
            fired.add(ek)
            msgs.append(msg)

        # 2. 减亏线（反弹到均线）→ 减亏离场提醒
        for lv, tag in cfg['relief_lines']:
            rk = f'relief_{lv}'
            if price >= lv and rk not in fired:
                gain = (price / cost - 1) * 100 if cost else 0
                msg = (f'🟡 {cfg["name"]} {code} 反弹到 {tag} {lv:.3f}！\n'
                       f'现价 {price:.3f}（{data["chg_pct"]:+.2f}%，五档比 {data["ratio"]:.2f}）\n'
                       f'持仓 {sh} 份 @ 成本 {cost}，当前 {gain:+.1f}%'
                       f'（回本需 {cost/price*100-100:+.1f}%）\n'
                       f'→ 观察期减亏离场提醒：可在此减仓离场，或改离场线上移。')
                send_feishu(msg, '🟡')
                fired.add(rk)
                msgs.append(msg)

        state[key] = sorted(fired)

    state_save(state)

    out = f'=== 剩余3只观察盯盘 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===\n'
    out += '\n'.join(log_lines)
    if msgs:
        out += '\n\n⚠️ 触发:\n' + '\n'.join(msgs)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'w') as f:
        f.write(out)

    # watchdog 模式：只有触发才输出到 stdout（空 = 静默不推送）
    if msgs:
        print(out)
    else:
        print('')
    return 0


if __name__ == '__main__':
    sys.exit(main())
