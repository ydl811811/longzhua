#!/usr/bin/python3.12
# -*- coding: utf-8 -*-
"""
Loop Engineer 盘中决策 → 本会话投递 relay

背景（2026-10-23 龙爪改造）：
  玲珑盘中决策原本走飞书群机器人 webhook，推到另一个频道（群），
  老大在本会话（飞书 DM）收不到。
  改造：daily_pipeline.py 加 PUSH_CHANNEL=file 通道 → 写 JSON 到
  ALERT_JSON_FILE，本脚本读 JSON → stdout 交给 cron 投递到本会话。

去重：每条 alert 带 fingerprint（code+action+价格四舍五入到 3 位+触发轮次），
      同一 fingerprint 只投递一次。state 文件记录已投递集合。
      玲珑每 30 分钟重复触发同一 close_long（HR-001 一直成立），
      不去重会一天刷 8 次同样的内容。

watchdog 模式：无新内容 → stdout 为空 = 静默。
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

ALERT_JSON = Path.home() / '.hermes' / 'cron' / 'output' / 'loop_engineer_alert_latest.json'
STATE_FILE = Path.home() / '.hermes' / 'stock-portfolio' / '.loop_engineer_relay_state.json'


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {'date': '', 'sent': []}


def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)


def fingerprint(a):
    """code + action + 价格（3 位）+ 置信度 → 稳定指纹"""
    return f"{a.get('code')}|{a.get('action')}|{float(a.get('price') or 0):.3f}|{a.get('confidence')}"


def main():
    if not ALERT_JSON.exists():
        print('')
        return 0

    try:
        with open(ALERT_JSON) as f:
            payload = json.load(f)
    except Exception as e:
        print(f'[read_err] {e}', file=sys.stderr)
        print('')
        return 0

    today = datetime.now().strftime('%Y-%m-%d')
    json_date = payload.get('date', '')

    # 🔴 GHOST-FIX 2026-10-30: 校验 JSON date 是否为今天。
    # 旧 JSON 残留（如 10/29 写的 alert，date=2026-10-29）会被 relay 当新决策重推，
    # 因为 state.date 每天重置 sent，而 JSON 里的 date 字段从未被校验。
    # 修复：非当日的 JSON 一律静默（清空 state，不推送），防止幽灵推送。
    if json_date != today:
        # 清空 state（旧数据已过期，不应再被任何一天重推）
        state = {'date': today, 'sent': []}
        save_state(state)
        print('')
        return 0

    alerts = payload.get('alerts') or []
    if not alerts:
        print('')
        return 0

    state = load_state()
    if state.get('date') != today:
        state = {'date': today, 'sent': []}
    sent = set(state.get('sent', []))

    new_alerts = []
    for a in alerts:
        fp = fingerprint(a)
        if fp in sent:
            continue
        sent.add(fp)
        new_alerts.append(a)

    state['sent'] = sorted(sent)
    save_state(state)

    if not new_alerts:
        print('')
        return 0

    ts = payload.get('ts', '')
    date_str = payload.get('date', today)
    lines = [f"🔔 玲珑盘中决策 · {date_str.replace('-', '')}", ""]

    for a in new_alerts:
        code = a.get('code', '')
        name = a.get('name', '')
        price = a.get('price', 0)
        action = a.get('action', '')
        conf = a.get('confidence', 0)
        rationale = a.get('rationale', '')
        kf = a.get('key_factors') or []
        icon = '🔴' if action == 'close_long' else '🟢' if 'long' in action else '⚪'
        lines.append(f"{icon} **{code} {name}** @ {float(price):.3f}")
        lines.append(f"   动作: {action} | 置信度: {conf}")
        lines.append(f"   理由: {rationale}")
        if kf:
            lines.append(f"   关键因子: {' | '.join(kf)}")
        lines.append("")

    lines.append("---")
    lines.append("**老大决策反馈**（回复我这条消息即可）：")
    lines.append("- 全部采纳 / 部分采纳 / 全部驳回")
    lines.append("- 或单条: `159869 采纳` / `159869 驳回`")
    lines.append("")
    lines.append("_本条由 Loop Engineer 本地化流水线自动推送（龙爪 relay 转本会话）_")

    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
