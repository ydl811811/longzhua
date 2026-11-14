#!/usr/bin/env python3
"""ledger_lint.py —— 台账规范机器校验器（schema v1 / vocabulary v1）

用法：
  python3 ledger_lint.py            # 全量检查，EXIT 0=通过 1=有 ERROR
  python3 ledger_lint.py --strict   # WARN 也算失败
  python3 ledger_lint.py --json     # 机器可读输出

为什么存在（2026-11-13）：
  记录两笔 ETF 清仓耗时 67 分钟 / 162 次工具调用，其中 41 分钟在「翻历史 sold 样本
  反推清仓该写哪几个字段」。翻完发现根本没有惯例 —— 清仓记录有 3 套并存写法、
  TP status 5 种、strategy 7 种、action type 11 种、trigger 43 个自由文本。
  本脚本把规范变成可执行检查，从此不再需要翻样本。

规范源：
  ~/skills/productivity/stock-portfolio-management/references/ledger-schema-v1.md
  ~/skills/productivity/stock-portfolio-management/references/ledger-vocabulary.md
"""
import sys
import json
import argparse
from pathlib import Path

import yaml

BASE = Path.home() / '.hermes/stock-portfolio'
POS = BASE / 'monitor_positions.yaml'
STATE = BASE / 'portfolio_state.yaml'
DLOG = BASE / 'decision_log.yaml'
FUNDS = BASE / 'funds_log.txt'

# ─────────────────────────── 受控词表（来自 ledger-vocabulary.md） ───────────────────────────
STATUS = {'holding', 'sold', 'candidate'}

STRATEGY_BY_STATUS = {
    'holding': {'swing', 'swing_hold', 'tactical', 'right_side_breakout', 'trend'},
    'sold': {'cleared'},
    'candidate': {'pending_buy'},
}

TP_STATUS = {'pending', 'done', 'cleared', 'cancelled', 'suspended'}
TP_ACTION = {'reduce_partial', 'clear_all'}

ACTION_TYPE = {
    'buy', 'sell', 'add', 'tp_adjust', 'order_placed',
    'add_position_plan', 'strategy_change',
    'grid_init', 'grid_auto', 'grid_param_sync',
}

ACTION_TRIGGER = {
    'manual', 'tp1', 'tp2', 'tp3', 'stop_loss', 'warn_line',
    'condition_order', 'grid_auto', 'strategy_change', 'rebalance', 'user_manual',
}

# 废弃写法（顶层出现即 WARN —— 存量保留，新写入禁止）
DEPRECATED_TOP_LEVEL = ('cleared_at', 'cleared_reason', 'historical_exit_record',
                         'realized_pnl', 'realized_pnl_pct')

EXIT_REQUIRED = ('exit_date', 'exit_shares', 'exit_price', 'exit_amount',
                 'realized_pnl', 'realized_pnl_pct', 'cleared_at', 'cleared_reason')


class Report:
    def __init__(self):
        self.errors = []
        self.warns = []
        self.oks = []

    def err(self, code, msg):
        self.errors.append(f'[{code}] {msg}')

    def warn(self, code, msg):
        self.warns.append(f'[{code}] {msg}')

    def ok(self, msg):
        self.oks.append(msg)

    def emit(self, strict=False, as_json=False):
        if as_json:
            print(json.dumps({
                'ok': not self.errors and not (strict and self.warns),
                'errors': self.errors, 'warnings': self.warns, 'passed': self.oks,
            }, ensure_ascii=False, indent=2))
            return 1 if (self.errors or (strict and self.warns)) else 0
        for e in self.errors:
            print(f'  ERROR  {e}')
        for w in self.warns:
            print(f'  WARN   {w}')
        for o in self.oks:
            print(f'  OK     {o}')
        print()
        n_e, n_w = len(self.errors), len(self.warns)
        if n_e:
            print(f'❌ {n_e} 个 ERROR / {n_w} 个 WARN')
        elif strict and n_w:
            print(f'❌ {n_w} 个 WARN（--strict 模式视为失败）')
        else:
            print(f'✅ 台账规范检查通过（{n_w} 个 WARN）')
        return 1 if (n_e or (strict and n_w)) else 0


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(path):
    try:
        return yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except Exception as e:
        return {'__error__': f'{e}'}


def check_positions(mp, rep):
    if '__error__' in mp:
        rep.err('YAML', f'monitor_positions.yaml 解析失败: {mp["__error__"]}')
        return
    positions = mp.get('positions')
    if not isinstance(positions, list):
        rep.err('STRUCT', 'monitor_positions.yaml 顶层 positions 不是 list')
        return

    for p in positions:
        if not isinstance(p, dict):
            rep.err('STRUCT', 'positions 中存在非 mapping 条目')
            continue
        code = str(p.get('code', '?'))

        # ── status ──
        st = p.get('status')
        if st not in STATUS:
            rep.err('STATUS', f'{code}: status={st!r} 不在词表 {sorted(STATUS)}')

        # ── strategy ──
        sg = p.get('strategy')
        allowed = STRATEGY_BY_STATUS.get(st, set())
        if st in ('holding', 'sold', 'candidate'):
            if sg not in allowed:
                rep.err('STRATEGY', f'{code}: status={st} 时 strategy={sg!r} 非法'
                                     f'（应为 {sorted(allowed)}）')
        elif sg is not None and sg not in set().union(*STRATEGY_BY_STATUS.values()):
            rep.err('STRATEGY', f'{code}: strategy={sg!r} 不在词表')

        # ── shares / base_shares / cost ──
        shares = p.get('shares')
        if st == 'holding':
            if not isinstance(shares, int) or shares <= 0:
                rep.err('SHARES', f'{code}: holding 必须 shares 为正整数，实际 {shares!r}')
            if _num(p.get('cost')) is None:
                rep.err('COST', f'{code}: holding 缺 cost')
            if p.get('base_shares') is None:
                rep.warn('BASE_SHARES', f'{code}: holding 缺 base_shares')
        elif st == 'candidate':
            if p.get('stop_loss') is not None:
                rep.warn('CANDIDATE_STOP', f'{code}: candidate 不应有 stop_loss（未建仓无止损）')
            if p.get('shares') not in (None, 0):
                rep.err('SHARES', f'{code}: candidate 必须 shares 为 0 或缺省，实际 {shares!r}')
        elif st == 'sold':
            if shares != 0:
                rep.err('SHARES', f'{code}: sold 必须 shares=0，实际 {shares!r}')
            if p.get('base_shares') is None:
                rep.warn('BASE_SHARES', f'{code}: sold 缺 base_shares（原始建仓份数应保留）')
            if p.get('strategy') != 'cleared':
                rep.err('STRATEGY', f'{code}: sold 必须 strategy=cleared')

        # ── stop_loss ≤ cost ──（只对 holding 生效：sold 的 stop_loss 是历史留痕，非活跃止损）
        sl, cost = _num(p.get('stop_loss')), _num(p.get('cost'))
        if st == 'holding' and sl is not None and cost is not None and sl > cost * 1.005:
            rep.err('STOP', f'{code}: stop_loss {sl} > cost {cost} —— 止损档无效')

        # ── trailing_stop：sold 必须 null ──
        ts = p.get('trailing_stop')
        if st == 'sold' and ts not in (None, 'null'):
            rep.err('TRAILING', f'{code}: sold 必须 trailing_stop: null'
                                 f'（非 null 会造出高于成交价的假止损），实际 {ts!r}')

        # ── take_profit ──
        tps = p.get('take_profit')
        if st == 'holding':
            if not tps:
                rep.err('TP', f'{code}: holding 缺 take_profit')
            elif isinstance(tps, list):
                total_tp = 0
                seen_levels = set()
                for t in tps:
                    if not isinstance(t, dict):
                        rep.err('TP', f'{code}: take_profit 条目非 mapping')
                        continue
                    lvl = t.get('level')
                    if lvl in seen_levels:
                        rep.err('TP', f'{code}: take_profit level={lvl} 重复')
                    seen_levels.add(lvl)
                    tst = t.get('status')
                    if tst not in TP_STATUS:
                        rep.err('TP_STATUS', f'{code}: TP{lvl} status={tst!r} 不在词表 {sorted(TP_STATUS)}')
                    if t.get('action') not in TP_ACTION:
                        rep.err('TP_ACTION', f'{code}: TP{lvl} action={t.get("action")!r} 不在词表 {sorted(TP_ACTION)}')
                    tgt = _num(t.get('target'))
                    if tst == 'pending' and tgt is not None and cost is not None and tgt < cost * 0.995:
                        rep.err('TP_TARGET', f'{code}: TP{lvl} target {tgt} < cost {cost} —— 旧档未按实际成交重算')
                    if isinstance(t.get('shares'), int):
                        total_tp += t['shares']
                if isinstance(shares, int) and total_tp > shares:
                    rep.err('TP_SHARES', f'{code}: TP 份数合计 {total_tp} > 持仓 {shares} —— 触发会卖超')
        elif st == 'sold' and isinstance(tps, list):
            for t in tps:
                if isinstance(t, dict) and t.get('status') == 'done':
                    rep.warn('TP_DONE', f'{code}: TP{t.get("level")} status=done —— '
                                        f'清仓成交价若低于该档 target，应为 cleared 而非 done')

        # ── actions ──
        acts = p.get('actions')
        if st == 'holding' and not acts and not p.get('entry_batches'):
            rep.err('ACTIONS', f'{code}: holding 但无 actions/entry_batches —— 成交事实未落盘')
        if isinstance(acts, list):
            for a in acts:
                if not isinstance(a, dict):
                    continue
                at = a.get('type')
                if at not in ACTION_TYPE:
                    rep.err('ACTION_TYPE', f'{code}: actions.type={at!r} 不在词表')
                tr = a.get('trigger')
                if tr is not None and tr not in ACTION_TRIGGER:
                    rep.warn('ACTION_TRIGGER', f'{code}: actions.trigger={tr!r} 是自由文本'
                                               f'（应改受控枚举 + 描述写 reason）')
                for f in ('date', 'type', 'shares', 'price', 'amount', 'reason'):
                    if a.get(f) in (None, ''):
                        rep.warn('ACTION_FIELD', f'{code}: action({at}) 缺 {f}')

        # ── capital_check 必须是 map ──
        cc = p.get('capital_check')
        if cc is not None and not isinstance(cc, dict):
            rep.err('CAPITAL_CHECK', f'{code}: capital_check 必须是 map，实际 {type(cc).__name__}')

        # ── exit_record ──
        er = p.get('exit_record')
        if st == 'sold':
            if er is None:
                rep.warn('EXIT_RECORD', f'{code}: sold 缺 exit_record')
            elif isinstance(er, list):
                rep.warn('EXIT_RECORD', f'{code}: exit_record 是 list 形态（存量写法）—— 新写入须用 map')
            elif isinstance(er, dict):
                ed = er.get('exit_date')
                if ed is not None and not isinstance(ed, str):
                    rep.err('EXIT_DATE_TYPE', f'{code}: exit_date 必须是字符串 YYYY-MM-DD，'
                                              f'实际 {type(ed).__name__}（YAML 原生 date 会破坏序列化）')
                miss = [f for f in EXIT_REQUIRED if f not in er]
                if miss:
                    rep.warn('EXIT_RECORD', f'{code}: exit_record 缺字段 {miss}')
                if _num(er.get('exit_amount')) is not None and _num(er.get('exit_price')) is not None \
                        and isinstance(er.get('exit_shares'), int):
                    calc = round(er['exit_shares'] * er['exit_price'], 2)
                    if abs(calc - float(er['exit_amount'])) > 0.01:
                        rep.err('EXIT_AMOUNT', f'{code}: exit_amount={er["exit_amount"]} '
                                              f'≠ shares×price = {calc}')
        elif er is not None:
            rep.err('EXIT_RECORD', f'{code}: status={st} 不该有 exit_record')

        # ── 废弃顶层写法 ──
        for f in DEPRECATED_TOP_LEVEL:
            if f in p:
                rep.warn('DEPRECATED', f'{code}: 顶层 {f} 属废弃写法 —— 应收进 exit_record')

    rep.ok(f'monitor_positions.yaml：{len(positions)} 个标的已按 schema v1 校验')


def check_state(ps, mp, rep):
    if '__error__' in ps:
        rep.err('YAML', f'portfolio_state.yaml 解析失败: {ps["__error__"]}')
        return
    acc = ps.get('account') or {}
    positions = mp.get('positions') or [] if isinstance(mp, dict) else []
    hold = {str(p['code']) for p in positions
            if isinstance(p, dict) and p.get('status') == 'holding'}

    # 影子清单
    shadow = {str(x.get('code')) for x in (ps.get('positions') or []) if isinstance(x, dict)}
    for c in sorted(hold - shadow):
        rep.err('SHADOW', f'{c}: monitor_positions 是 holding 但 portfolio_state 影子清单缺该标的')
    for c in sorted(shadow - hold):
        rep.err('SHADOW', f'{c}: portfolio_state 影子清单有但 monitor_positions 非 holding')
    for x in (ps.get('positions') or []):
        if not isinstance(x, dict):
            continue
        c = str(x.get('code'))
        m = next((p for p in positions if isinstance(p, dict) and str(p.get('code')) == c), None)
        if m:
            for f in ('shares', 'cost'):
                a, b = x.get(f), m.get(f)
                if a is not None and b is not None and _num(a) is not None and _num(b) is not None:
                    if abs(float(a) - float(b)) > 1e-9:
                        rep.err('SHADOW_FIELD', f'{c}.{f}: portfolio_state={a} ≠ monitor_positions={b}')

    # 恒等式
    cash, mv, oth, ta = (_num(acc.get(k)) for k in ('cash', 'market_value', 'other_funds', 'total_assets'))
    if None not in (cash, mv, ta):
        implied = round(ta - cash - (oth or 0.0), 2)
        if mv is None:
            rep.err('IDENTITY', f'account 缺 market_value')
        elif abs(implied - mv) > 0.05:
            rep.err('IDENTITY', f'cash {cash} + mv {mv} + other {oth} ≠ total_assets {ta} '
                               f'（推算 mv = {implied}）')

    # capital_check.base_cash == account.cash
    for p in positions:
        if not isinstance(p, dict) or p.get('status') != 'holding':
            continue
        cc = p.get('capital_check') or {}
        if isinstance(cc, dict) and cc.get('base_cash') is not None and cash is not None:
            if abs(float(cc['base_cash']) - cash) > 0.01:
                rep.err('BASE_CASH', f'{p.get("code")}: capital_check.base_cash={cc["base_cash"]} '
                                     f'≠ account.cash={cash}')

    rep.ok('portfolio_state.yaml：影子清单 + 账户恒等式已校验')


def check_decision_log(dl, rep):
    if '__error__' in dl:
        rep.err('YAML', f'decision_log.yaml 解析失败: {dl["__error__"]}')
        return
    if not isinstance(dl, dict):
        rep.err('STRUCT', 'decision_log.yaml 顶层不是 dict（records + decisions 双 list）')
        return
    r = dl.get('records')
    d = dl.get('decisions')
    if not isinstance(r, list):
        rep.err('STRUCT', 'decision_log.yaml 缺 records list')
    if not isinstance(d, list):
        rep.err('STRUCT', 'decision_log.yaml 缺 decisions list')
    rep.ok(f'decision_log.yaml：records={len(r) if isinstance(r, list) else "?"} '
           f'decisions={len(d) if isinstance(d, list) else "?"}')


def main():
    ap = argparse.ArgumentParser(description='台账规范机器校验器（schema v1 / vocabulary v1）')
    ap.add_argument('--strict', action='store_true', help='WARN 也视为失败')
    ap.add_argument('--json', action='store_true', help='JSON 输出')
    args = ap.parse_args()

    rep = Report()
    mp = load(POS)
    ps = load(STATE)
    dl = load(DLOG)
    if not FUNDS.exists():
        rep.err('FILE', f'funds_log.txt 不存在: {FUNDS}')

    check_positions(mp, rep)
    check_state(ps, mp, rep)
    check_decision_log(dl, rep)

    return rep.emit(strict=args.strict, as_json=args.json)


if __name__ == '__main__':
    sys.exit(main())
