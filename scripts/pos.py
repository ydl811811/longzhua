#!/usr/bin/env python3
"""pos.py —— 持仓台账精简查询助手（替代整读 monitor_positions.yaml / decision_log.yaml）

用法：
  pos.py                 # 默认 = snapshot：当前账户 + 持仓 + 关键位（1 屏内）
  pos.py snapshot        # 同上
  pos.py cash            # 只打印现金 + 来源 + 校验链
  pos.py check           # 漂移检查：portfolio_state vs monitor_positions vs funds_log
  pos.py all             # 打印 portfolio_state.yaml 全文（~1.5k tokens）

设计（2026-11-09 老大批准 A+B+D）：
- portfolio_state.yaml = 账户层权威数字的**唯一**事实源（现金只认券商 App）
- monitor_positions.yaml = 持仓明细权威源（含完整分析正文）
- 本脚本合并两者，输出精简快照，避免整读 108KB 台账
"""
import sys, os, yaml
from pathlib import Path

BASE = Path.home() / '.hermes/stock-portfolio'
STATE = BASE / 'portfolio_state.yaml'
POS = BASE / 'monitor_positions.yaml'
FUNDS = BASE / 'funds_log.txt'


def load(p):
    try:
        return yaml.safe_load(Path(p).read_text()) or {}
    except Exception as e:
        print(f'[err] 读 {p} 失败: {e}')
        return {}


def snapshot():
    st = load(STATE)
    mp = load(POS)
    acc = st.get('account', {}) or {}
    hold = [p for p in (mp.get('positions') or []) if p.get('status') == 'holding']

    print('=' * 62)
    print(f"账户快照（权威源：portfolio_state.yaml / 券商 App {acc.get('as_of','?')}）")
    print('=' * 62)
    print(f"  总资产   {acc.get('total_assets','?')} 元")
    print(f"  可用现金 {acc.get('cash','?')} 元   ← 来源：{acc.get('cash_source','?')}")
    print(f"  总市值   {acc.get('market_value','?')} 元   仓位 {acc.get('position_pct','?')}%")
    print(f"  总盈亏   {acc.get('total_pnl','?')} 元   当日 {acc.get('day_pnl','?')} 元")
    print()
    if not hold:
        print('  （无 holding 持仓）')
    for p in sorted(hold, key=lambda x: str(x.get('code'))):
        code = str(p.get('code')); name = p.get('name')
        shares = p.get('shares'); cost = p.get('cost')
        amt = round((shares or 0) * (cost or 0), 2)
        cc = p.get('capital_check') or {}
        print(f"── {code} {name}")
        print(f"   持仓 {shares} 份 @ {cost} = {amt} 元 | 止损 {p.get('stop_loss','?')}")
        tps = p.get('take_profit') or []
        if tps:
            print('   止盈 ' + ' / '.join(
                f"TP{t.get('level')}={t.get('target')}(减{t.get('shares')})" for t in tps if t.get('status') == 'pending'))
        sn = p.get('monitoring_snapshot') or {}
        kl = sn.get('key_levels') or {}
        if kl:
            print(f"   支撑 {kl.get('支撑','-')}")
            print(f"   压力 {kl.get('压力','-')}")
        if sn.get('current_light'):
            print(f"   状态 {sn['current_light'][:150]}")
        if cc.get('base_cash') is not None and acc.get('cash') is not None:
            if abs(float(cc['base_cash']) - float(acc['cash'])) > 0.01:
                print(f"   ⚠️ capital_check.base_cash={cc['base_cash']} ≠ portfolio_state.cash={acc['cash']}（需回填）")
        print()
    pc = st.get('pending_confirmations') or []
    if pc:
        print('待老大确认：')
        for x in pc:
            print(f"  • {x}")


def cash():
    st = load(STATE)
    acc = st.get('account', {}) or {}
    print(f"可用现金   {acc.get('cash','?')} 元")
    print(f"来源       {acc.get('cash_source','?')}")
    print(f"截图时间   {acc.get('as_of','?')}")
    print(f"总资产     {acc.get('total_assets','?')} 元")
    v = acc.get('cash_verification_chain')
    if v:
        print('校验链     ' + v)


def check():
    st = load(STATE); mp = load(POS)
    acc = st.get('account', {}) or {}
    problems = []
    # 1) portfolio_state 持仓清单 vs monitor_positions
    sp = {str(x['code']): x for x in (st.get('positions') or [])}
    mp_h = {str(p['code']): p for p in (mp.get('positions') or []) if p.get('status') == 'holding'}
    for code in set(sp) | set(mp_h):
        if code not in sp:
            problems.append(f'{code}: monitor_positions 是 holding 但 portfolio_state 缺该持仓')
        elif code not in mp_h:
            problems.append(f'{code}: portfolio_state 有该持仓但 monitor_positions 非 holding')
        else:
            for f in ('shares', 'cost'):
                a, b = sp[code].get(f), mp_h[code].get(f)
                if a is not None and b is not None and abs(float(a) - float(b)) > 1e-9:
                    problems.append(f'{code}.{f}: portfolio_state={a} ≠ monitor_positions={b}')
    # 2) capital_check.base_cash vs 权威 cash
    for code, p in mp_h.items():
        cc = p.get('capital_check') or {}
        if cc.get('base_cash') is not None and acc.get('cash') is not None:
            if abs(float(cc['base_cash']) - float(acc['cash'])) > 0.01:
                problems.append(f"{code}.capital_check.base_cash={cc['base_cash']} ≠ portfolio_state.cash={acc['cash']}")
    # 3) 恒等式：cash + market_value + other_funds == total_assets
    cost_sum = round(sum((p.get('shares') or 0) * (p.get('cost') or 0) for p in mp_h.values()), 2)
    if acc.get('cash') is not None and acc.get('total_assets') is not None:
        other = float(acc.get('other_funds') or 0)
        implied_mv = round(float(acc['total_assets']) - float(acc['cash']) - other, 2)
        if acc.get('market_value') is not None and abs(implied_mv - float(acc['market_value'])) > 0.05:
            problems.append(f"总资产-现金-other_funds={implied_mv} ≠ market_value={acc['market_value']}")
    print(f"持仓 {len(mp_h)} 只 | 成本合计 {cost_sum} 元 | 现金 {acc.get('cash','?')} | 总资产 {acc.get('total_assets','?')}")
    if problems:
        print('\n⚠️ 发现漂移：')
        for x in problems:
            print('  - ' + x)
        sys.exit(1)
    print('✅ 无漂移')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'snapshot'
    if cmd in ('snapshot', ''):
        snapshot()
    elif cmd == 'cash':
        cash()
    elif cmd == 'check':
        check()
    elif cmd == 'all':
        print(STATE.read_text())
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
