#!/usr/bin/python3.12
# -*- coding: utf-8 -*-
"""
159299 金融科技ETF 收盘一次性监控 — A 方案
- 每天 15:35 跑一次（避开 15:00 收盘竞价 + 让收盘价稳定）
- 命中推飞书 webhook；无命中静默（看 watchdog 模式）
- 单只单维度每日只推一次（state file 控制）

监控信号：
  1. 收盘 ≥ 0.72 → E1 突破加仓信号（试探仓 5000→7000 份）
  2. 收盘 < 0.67 → 三重底跌破，评估止损/暂停加仓

为什么不进 stock_monitor.py：
  - stock_monitor.py 的 add_position_N_target 是"现价 ≤ target"触底加仓方向
  - 159299 这个是"现价 ≥ 0.72"突破加仓，方向相反，强行塞进去会误触发
  - 新建独立脚本 + 独立 cron 最干净，不污染主监控

数据源：新浪日K最新一条（scale=240，datalen=5 拿最近 5 日，最后一条 close = 今日收盘）
"""

import os
import sys
import json
import hmac
import hashlib
import base64
import time
import urllib.request
import socket
from datetime import datetime

from feishu_bot import load_feishu_creds

# ─── 强制 IPv4（避免 qt.gtimg.cn 的 IPv6 抖动）────────────────────
_socket_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: _socket_orig(h, p, socket.AF_INET, t, pr, fl)

# ─── 配置常量 ──────────────────────────────────────────────────────
CODE = '159299'
MARKET = 'sz'
NAME = '金融科技ETF易方达'

BREAKOUT_PRICE = 0.72      # 收盘 ≥ 此价 → E1 加仓信号
BREAKOUT_SHARES = 2000     # 加仓份数（试探仓 5000→7000）

BOTTOM_BREAK = 0.67        # 收盘 < 此价 → 三重底跌破

STATE_FILE = os.path.expanduser('~/.hermes/stock-portfolio/.159299_breakout_state.json')
POS_FILE = os.path.expanduser('~/.hermes/stock-portfolio/monitor_positions.yaml')

# 2026-11-06 修正：本脚本原按「持仓期 E1 加仓计划」写死推 0.72 突破 / 0.67 破底，
# 但 159299 已于 2026-10-28 全清仓（status=sold, shares=0），E1 计划已于
# 2026-10-29 canceled_by_market。11/02 老大拍板 A 把它加回【候选池】
# （monitor_watched.yaml, status=waiting_reversal, entry_max=0.65, SL=0.56），
# 观察条件 = 站上 MA20 0.652 且放量 2 日。
# → 继续按 0.67 判「破底止损」会每天误推「暂停 E1 加仓 + 评估止损 0.62」，
#    而 0.62 是已平仓仓位的止损线，对空仓无意义 = 幽灵警报。
# 本脚本现只保留【候选池右侧确认】一条职责（站上 MA20 0.652 且放量 ≥1.0x），
# 破底提醒交由候选池扫描 (243c6a7adea4 / reversal_scan.py) 统一处理。
CANDIDATE_BREAKOUT = 0.652   # 候选池右侧确认位 = MA20
CANDIDATE_MIN_RATIO = 1.0    # 放量确认阈值（五档比/量比）

# 飞书机器人
FEISHU_BOT_URL, FEISHU_BOT_SECRET = load_feishu_creds()



# ─── State 管理（单日单维度去重）──────────────────────────────────
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def should_trigger(state, signal_type):
    """同日同信号只触发一次"""
    today = datetime.now().strftime('%Y-%m-%d')
    return state.get(signal_type) != today


def mark_triggered(state, signal_type):
    state[signal_type] = datetime.now().strftime('%Y-%m-%d')
    save_state(state)


# ─── 数据获取 ──────────────────────────────────────────────────────
def fetch_close():
    """从新浪日K拿最近 5 日，最后一条 close = 今日收盘价"""
    url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
    data = f'symbol={MARKET}{CODE}&scale=240&ma=no&datalen=5'.encode()
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            klines = json.loads(r.read())
    except Exception as e:
        print(f'[ERR] fetch_close failed: {e}', file=sys.stderr)
        return None
    if not klines:
        return None
    return float(klines[-1]['close']), klines[-1].get('day', '?')


# ─── 飞书推送 ──────────────────────────────────────────────────────
def send_feishu(text, emoji='🟢'):
    """POST 飞书自定义机器人 webhook（带签名）"""
    timestamp = str(int(time.time()))
    string_to_sign = f'{timestamp}\n{FEISHU_BOT_SECRET}'
    hmac_code = hmac.new(string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    payload = {
        'timestamp': timestamp,
        'sign': sign,
        'msg_type': 'text',
        'content': {'text': f'{emoji} {text}'},
    }
    try:
        req = urllib.request.Request(
            FEISHU_BOT_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode('utf-8')
            if '"StatusCode":0' not in body and '"code":0' not in body:
                print(f'[WARN] feishu resp: {body}', file=sys.stderr)
    except Exception as e:
        print(f'[ERR] send_feishu failed: {e}', file=sys.stderr)


# ─── 主逻辑 ────────────────────────────────────────────────────────
def load_positions():
    """读台账，确认 159299 是否仍为持仓（status=holding 且 shares>0）。"""
    try:
        import yaml
        with open(POS_FILE, 'r') as f:
            d = yaml.safe_load(f) or {}
        for p in d.get('positions', []) or []:
            if str(p.get('code')) == CODE:
                return p
    except Exception as e:
        print(f'[WARN] 读台账失败: {e}', file=sys.stderr)
    return None


def main():
    result = fetch_close()
    if result is None:
        print('[SKIP] 数据获取失败，静默')
        return
    close_price, day = result
    print(f'[INFO] {NAME} {day} 收盘 {close_price}')

    # 2026-11-06 修正：仓位门控 —— 台账已非 holding 时不推任何持仓类警报。
    # 159299 已于 2026-10-28 全清仓，E1 计划 10-29 取消，11-02 加回候选池。
    pos = load_positions()
    is_holding = bool(pos and pos.get('status') == 'holding' and (pos.get('shares') or 0) > 0)
    if not is_holding:
        status = (pos or {}).get('status', 'absent')
        print(f'[INFO] 台账 status={status}/shares={(pos or {}).get("shares", 0)} → 非持仓，跳过持仓类警报（仅候选池监控）')

    state = load_state()
    triggered = []

    # 1. 右侧确认（候选池口径）：收盘 ≥ MA20 0.652 且放量确认
    #    仅当 159299 在候选池（monitor_watched.yaml waiting_*）时才推
    if close_price >= CANDIDATE_BREAKOUT:
        if should_trigger(state, 'candidate_breakout'):
            msg = (
                f'{NAME}（{CODE}）收盘 {close_price} ≥ {CANDIDATE_BREAKOUT}（MA20 右侧确认位），\n'
                f'候选池观察条件「站上 MA20 0.652 且放量 2 日」的价格条件成立\n'
                f'⚠️ 仍需核对：①量比 ≥ {CANDIDATE_MIN_RATIO}（放量确认）②连续 2 日站上 ③五档比\n'
                f'（台账 monitor_watched.yaml: entry_max 0.65 / stop_loss 0.56）'
            )
            send_feishu(msg, '🟢')
            mark_triggered(state, 'candidate_breakout')
            triggered.append('candidate_breakout')
        else:
            print(f'[SKIP] candidate_breakout 今日已推送过（{close_price} ≥ {CANDIDATE_BREAKOUT}）')
    else:
        # 收盘未站上，重置状态（次日才能再推）
        if state.get('candidate_breakout'):
            state.pop('candidate_breakout', None)

    # 2. 破底提醒：仅在【仍是持仓】时才有意义（持仓破了离场线才要动作）
    #    2026-11-06：159299 已清仓 → 破底提醒永久关闭，避免幽灵警报
    if is_holding and close_price < BOTTOM_BREAK:
        if should_trigger(state, 'bottom_break'):
            msg = (
                f'{NAME}（{CODE}）收盘 {close_price} < {BOTTOM_BREAK}，\n'
                f'三重底形态失效！\n'
                f'8/19-8/24 三重底位置 0.672/0.671/0.676 已破，'
                f'暂停加仓计划 + 评估是否触发止损 0.62 流程'
            )
            send_feishu(msg, '🔴')
            mark_triggered(state, 'bottom_break')
            triggered.append('bottom_break')
        else:
            print(f'[SKIP] bottom_break 今日已推送过（{close_price} < {BOTTOM_BREAK}）')
    else:
        if not is_holding:
            print(f'[SKIP] bottom_break 不适用（159299 非持仓，破底提醒仅对持仓有效）')
        if state.get('bottom_break'):
            state.pop('bottom_break', None)

    save_state(state)

    if triggered:
        print(f'[OK] 触发信号: {triggered}')
    else:
        print(f'[OK] 无信号（收盘 {close_price} < {CANDIDATE_BREAKOUT} 右侧确认位，静默）')


if __name__ == '__main__':
    main()
