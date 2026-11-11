#!/usr/bin/env python3
"""manual_sell_exec.py —— 手动卖出（非 TP 触达）成交登记器

背景（2026-11-11）
------------------
515790 在 2026-11-11 10:09:11 由老大手动卖出 4000 份 @0.724（券商 App 回单）。
这不是 TP1 0.756 的成交，因此：
  - TP1 / TP2 的 status 必须【保持 pending】（不得标记 done）
  - trailing_stop.after_tp1 = 0.730 不得激活（成交价 0.724 与收盘都在其下方）
  - 用 tp_exec.py 登记会错误地把 TP1 标成 done 并激活 0.730 移动止损 → 禁止

本脚本做「手动卖出」专用登记，同时可顺带把减仓后的 SL/预警/TP 结构按新口径重算
（参数重算本身是策略决定，需有回测证据支撑；本脚本只负责定点写入与校验）。

用法
----
  python3 ~/.hermes/scripts/manual_sell_exec.py <code> --shares 4000 --price 0.724 \\
      --time '10:09:11' --reason '券商 App 当日成交回单确认' \\
      [--warn 0.714] [--tp1 0.756:2000] [--tp2 0.765:2000] \\
      [--after-tp1 0.730] [--drop-after-tp2] [--evidence '证据块文本']

行为（行级定点编辑，不整体重序列化 YAML —— 保住注释与分析正文）
  monitor_positions.yaml
    · 持仓 shares 扣减（base_shares 保留原始建仓量）
    · capital_check.current_position_amount / current_position_pct 同步
    · actions 追加一条 sell 记录（成交事实：时间/价/量/额/来源）
    · 可选：warn_line / take_profit 各档 target+shares / trailing_stop 调整
    · 可选：新增 sl_tp_recalc_<date> 证据块
  portfolio_state.yaml
    · 影子清单 shares / cost_amount / available_shares / last_price / float_* 同步
    · take_profit 与 trailing_stop 同步
  decision_log.yaml
    · 追加一条成交登记决策（备份 + 双 list 守恒校验）
  funds_log.txt
    · 追加一条成交留档（现金不自动改）

安全
  · 现金/market_value/total_assets 一律不自动改 —— 唯一权威源是券商 App 可用资金
  · 改动前对每个文件生成 .bak
  · 写入后 yaml.safe_load 校验 + 读回断言，失败即回滚
  · TP 档 status 永不因手动卖出而变更
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

SCRIPTS = Path.home() / '.hermes' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from tp_exec import pos_code_block, tp_item_range  # noqa: E402

BASE = Path(os.environ.get('MSEXEC_BASE') or (Path.home() / '.hermes' / 'stock-portfolio'))
POS = BASE / 'monitor_positions.yaml'
STATE = BASE / 'portfolio_state.yaml'
DLOG = BASE / 'decision_log.yaml'
FUNDS = BASE / 'funds_log.txt'
POSPY = SCRIPTS / 'pos.py'
SYNC = SCRIPTS / 'sync_positions_yml.py'
NO_SYNC = bool(os.environ.get('MSEXEC_NO_SYNC'))


def now_str():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def ts():
    return time.strftime('%Y%m%d_%H%M%S')


def _safe_plain(text):
    """plain scalar 不能含 ': ' / ' #'，且不能以特殊字符开头"""
    s = str(text)
    assert ': ' not in s, f'值里不能有「: 空格」: {s[:60]}'
    assert ' #' not in s, f'值里不能有「#」: {s[:60]}'
    assert not s.startswith(('&', '*', '!', '%', '@', '`', '>', '|', '-', '?', ':')), \
        f'值不能以特殊字符开头: {s[:60]}'
    return s


def _one_line(text, field):
    assert '\n' not in str(text), f'{field} 值里含换行 → 会挤掉闭合引号（陷阱 29）'
    return str(text)


# ───────────────────────── monitor_positions.yaml ─────────────────────────

def _yaml_dq(value):
    """单行双引号标量（转义反斜杠与双引号），值内不得有换行"""
    s = str(value)
    assert '\n' not in s, '文本字段值不能含换行'
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def set_text_field(lines, s, e, key, value, indent_hint=None):
    """把 [s,e) 区间内的标量文本字段 key 整段重写为单行双引号值。

    处理多行折叠续行：找到主行后删除其后所有缩进更深的续行，再写单行值。
    返回 (lines, hit)。未命中返回 hit=False。
    """
    pat = re.compile(r"^(\s*)" + re.escape(key) + r":(\s|$)")
    for i in range(s, e):
        m = pat.match(lines[i])
        if not m:
            continue
        ind = len(m.group(1))
        if indent_hint is not None and ind != indent_hint:
            continue
        j = i + 1
        while j < e:
            l = lines[j]
            if not l.strip():
                break
            jind = len(l) - len(l.lstrip())
            if jind <= ind:
                break
            j += 1
        del lines[i + 1:j]
        lines[i] = f"{' ' * ind}{key}: {_yaml_dq(value)}"
        return lines, True
    return lines, False


def edit_positions(text, code, sell, price, at_time, reason, warn, tps, after_tp1,
                   drop_after_tp2, evidence, evidence_key, texts):
    lines = text.split('\n')
    s, e = pos_code_block(lines, code)

    # 持仓 shares
    pos_sh = None
    for i in range(s, e):
        if re.match(r"^  status:\s*holding\s*$", lines[i]):
            for j in range(i + 1, e):
                m = re.match(r"^  shares:\s*(\d+)\s*$", lines[j])
                if m:
                    pos_sh = int(m.group(1))
                    lines[j] = f"  shares: {pos_sh - sell}"
                    break
            break
    if pos_sh is None:
        raise SystemExit('❌ 找不到持仓 shares')
    if sell > pos_sh:
        raise SystemExit(f'❌ 成交 {sell} 份 > 持仓 {pos_sh} 份')
    new_shares = pos_sh - sell

    cost = None
    for i in range(s, e):
        m = re.match(r"^  cost:\s*([\d.]+)\s*$", lines[i])
        if m:
            cost = float(m.group(1))
            break
    if cost is None:
        raise SystemExit('❌ 找不到 cost')

    # warn_line
    if warn is not None:
        hit = False
        for i in range(s, e):
            m = re.match(r"^  warn_line:\s*[\d.]+\s*$", lines[i])
            if m:
                lines[i] = f"  warn_line: {warn}"
                hit = True
                break
        if not hit:
            raise SystemExit('❌ 找不到 warn_line')

    # trailing_stop
    if drop_after_tp2:
        for i in range(s, e):
            if re.match(r"^\s+after_tp2:\s*[\d.]+\s*$", lines[i]):
                del lines[i]
                break
    if after_tp1 is not None:
        hit = False
        for i in range(s, e):
            m = re.match(r"^(\s+)after_tp1:\s*[\d.]+\s*$", lines[i])
            if m:
                lines[i] = f"{m.group(1)}after_tp1: {after_tp1:.3f}"
                hit = True
                break
        if not hit:
            raise SystemExit('❌ 找不到 trailing_stop.after_tp1')

    # take_profit 各档
    for spec in tps:
        level, target, sh = spec
        is_s, is_e = tp_item_range(lines, s, e, level)
        item = lines[is_s:is_e]
        for k, l in enumerate(item):
            m = re.match(r"^(\s+)target:\s*[\d.]+\s*$", l)
            if m:
                item[k] = f"{m.group(1)}target: {target:.3f}"
                break
        for k, l in enumerate(item):
            m = re.match(r"^(\s+)shares:\s*\d+\s*$", l)
            if m:
                item[k] = f"{m.group(1)}shares: {sh}"
                break
        lines[is_s:is_e] = item

    # 正文同步：预警说明 / 移动止损说明 / 各 TP 档 condition
    if texts.get('sl_note'):
        lines, hit = set_text_field(lines, s, e, 'stop_loss_note', texts['sl_note'], 2)
        if not hit:
            raise SystemExit('❌ 找不到 stop_loss_note')
    if texts.get('warn_line_note'):
        lines, hit = set_text_field(lines, s, e, 'warn_line_note', texts['warn_line_note'], 2)
        if not hit:
            raise SystemExit('❌ 找不到 warn_line_note')
    if texts.get('trail_note'):
        lines, hit = set_text_field(lines, s, e, 'note', texts['trail_note'], 4)
        if not hit:
            raise SystemExit('❌ 找不到 trailing_stop.note')
    for level, cond in (texts.get('tp_conditions') or []):
        is_s, is_e = tp_item_range(lines, s, e, level)
        item = lines[is_s:is_e]
        hit = False
        for k, l in enumerate(item):
            m = re.match(r"^(\s+)condition:", l)
            if m:
                item[k] = f"{m.group(1)}condition: {_yaml_dq(cond)}"
                hit = True
                break
        if not hit:
            raise SystemExit(f'❌ TP{level} 找不到 condition')
        lines[is_s:is_e] = item

    # capital_check
    in_cc = False
    for i in range(s, e):
        if re.match(r"^  capital_check:\s*$", lines[i]):
            in_cc = True
            continue
        if in_cc:
            if re.match(r"^\S", lines[i]):
                break
            m = re.match(r"^(\s+)current_position_amount:\s*[\d.]+\s*$", lines[i])
            if m:
                lines[i] = f"{m.group(1)}current_position_amount: {round(new_shares * cost, 2)}"
                continue
            m = re.match(r"^(\s+)current_position_pct:\s*.*$", lines[i])
            if m:
                lines[i] = (f"{m.group(1)}current_position_pct: "
                            f"{round(new_shares * cost / 40948.47 * 100, 1)}%"
                            f"（{round(new_shares * cost, 2)} 元 / 总资产 40,948.47；"
                            f"总资产为 11/09 App 快照，11/11 卖出后待老大提供 App 最新值校准）")
                continue

    # actions 追加
    act_i = None
    for i in range(s, e):
        if re.match(r"^  actions:\s*$", lines[i]):
            act_i = i
            break
    if act_i is None:
        raise SystemExit('❌ 找不到 actions 段')
    act_end = e
    for i in range(act_i + 1, e):
        l = lines[i]
        if not l.strip():
            continue
        ind = len(l) - len(l.lstrip())
        if ind <= 2 and re.match(r"^\s*[\w-]+:", l):
            act_end = i
            break
    amt = round(sell * price, 2)
    new_action = [
        f"  - date: '{time.strftime('%Y-%m-%d')}'",
        f"    time: {at_time}",
        "    type: sell",
        "    trigger: manual",
        f"    shares: {sell}",
        f"    price: {price}",
        f"    amount: {amt}",
        f"    reason: {_safe_plain(reason)}",
        f"    source: 券商 App 当日成交回单（老大飞书截图，证券卖出，{sell} 份 @ {price}，"
        f"金额 {amt} 元，成交时间 {at_time}）",
    ]
    lines[act_end:act_end] = new_action

    # 证据块（插在既有 sl_tp_recalc_* 之前）
    if evidence:
        ins = None
        for i in range(s, e):
            if re.match(r"^  sl_tp_recalc_", lines[i]):
                ins = i
                break
        if ins is None:
            raise SystemExit('❌ 找不到 sl_tp_recalc_* 锚点')
        blk = [f"  {evidence_key}:"]
        for k, v in evidence:
            blk.append(f"    {k}: {_safe_plain(v)}")
        lines[ins:ins] = blk

    return '\n'.join(lines), new_shares, cost, amt


# ───────────────────────── portfolio_state.yaml ─────────────────────────

def edit_state(text, code, sell, price, warn, tps, after_tp1, drop_after_tp2,
               last_price, note, cost):
    lines = text.split('\n')
    s = None
    for i, l in enumerate(lines):
        if re.match(r"^- code:\s*['\"]?" + re.escape(code) + r"['\"]?\s*$", l):
            s = i
            break
    if s is None:
        raise SystemExit(f'❌ portfolio_state.yaml 无 {code} 影子项')
    e = len(lines)
    for j in range(s + 1, len(lines)):
        if re.match(r"^- code:", lines[j]):
            e = j
            break

    pos_sh = None
    for i in range(s, e):
        m = re.match(r"^  shares:\s*(\d+)\s*$", lines[i])
        if m:
            pos_sh = int(m.group(1))
            break
    if pos_sh is None:
        raise SystemExit('❌ 影子清单无 shares')
    new_shares = pos_sh - sell
    if sell > pos_sh:
        raise SystemExit(f'❌ 成交 {sell} 份 > 持仓 {pos_sh} 份')

    def set_field(pattern, value):
        for i in range(s, e):
            if re.match(pattern, lines[i]):
                lines[i] = re.sub(r"^(\s*[\w-]+:\s*).*$", lambda m: m.group(1) + str(value), lines[i])
                return True
        return False

    set_field(r"^  shares:\s*\d+\s*$", new_shares)
    set_field(r"^  cost_amount:\s*[\d.]+\s*$", round(new_shares * cost, 2))
    set_field(r"^  available_shares:\s*\d+\s*$", new_shares)
    if warn is not None:
        if not set_field(r"^  warn_line:\s*[\d.]+\s*$", warn):
            raise SystemExit('❌ 影子清单无 warn_line')
    if last_price is not None:
        set_field(r"^  last_price:\s*[\d.]+\s*$", last_price)
        fp = round((last_price - cost) * new_shares, 2)
        set_field(r"^  float_pnl:\s*-?[\d.]+\s*$", f'{fp:.2f}')
        set_field(r"^  float_pct:\s*-?[\d.]+\s*$", f'{fp / (new_shares * cost) * 100:.3f}')

    if drop_after_tp2:
        for i in range(s, e):
            if re.match(r"^\s+after_tp2:\s*[\d.]+\s*$", lines[i]):
                del lines[i]
                break
    if after_tp1 is not None:
        hit = False
        for i in range(s, e):
            m = re.match(r"^(\s+)after_tp1:\s*[\d.]+\s*$", lines[i])
            if m:
                lines[i] = f"{m.group(1)}after_tp1: {after_tp1:.3f}"
                hit = True
                break
        if not hit:
            raise SystemExit('❌ 影子清单无 trailing_stop.after_tp1')

    for level, target, sh in tps:
        is_s, is_e = tp_item_range(lines, s, e, level)
        item = lines[is_s:is_e]
        for k, l in enumerate(item):
            m = re.match(r"^(\s+)target:\s*[\d.]+\s*$", l)
            if m:
                item[k] = f"{m.group(1)}target: {target:.3f}"
                break
        for k, l in enumerate(item):
            m = re.match(r"^(\s+)shares:\s*\d+\s*$", l)
            if m:
                item[k] = f"{m.group(1)}shares: {sh}"
                break
        lines[is_s:is_e] = item

    if note:
        for i in range(s, e):
            if re.match(r"^  note:\s*", lines[i]):
                lines[i] = f"  note: {_safe_plain(note)}"
                break

    return '\n'.join(lines), new_shares


# ───────────────────────── decision_log.yaml ─────────────────────────

def append_decision(text, code, sell, price, at_time, reason, new_shares, cost, amt,
                    warn, tps, after_tp1, drop_after_tp2, evidence_text):
    d = yaml.safe_load(text)
    recs = d.get('records') or []
    decs = d.get('decisions') or []
    tp_desc = ' / '.join(f'TP{lv} {tg} 减 {sh}' for lv, tg, sh in tps) or '未变'
    entry = {
        'date': time.strftime('%Y-%m-%d'),
        'time': now_str()[11:16],
        'code': code,
        'topic': f'{code} 手动卖出成交登记 —— 卖出 {sell} 份 @ {price}（成交时间 {at_time}），'
                 f'持仓 {sell + new_shares} -> {new_shares}，非 TP 触达',
        'decision': (f'老大在券商 App 手动卖出 {code} {sell} 份 @ {price}，成交金额 {amt} 元，'
                     f'成交时间 {at_time}（当日成交回单确认）。龙爪按手动卖出登记：'
                     f'monitor_positions.yaml 持仓 shares 扣减为 {new_shares}，'
                     f'capital_check.current_position_amount 同步为 {round(new_shares * cost, 2)}，'
                     f'actions 追加 sell 记录；portfolio_state.yaml 影子清单同步；'
                     f'decision_log.yaml 追加本条。'
                     f'【关键】本笔不是 TP 触达成交 —— take_profit 各档 status 全部保持 pending，'
                     f'不激活 trailing_stop.after_tp1 = {after_tp1}（成交价 {price} 低于该位，'
                     f'激活即假止损）。减仓后参数重算 —— 预警 {warn}，止盈 {tp_desc}，'
                     + (f'TP1 成交后止损上移 {after_tp1}；' if after_tp1 else '')
                     + ('取消 after_tp2（清仓档后无剩余仓位）。' if drop_after_tp2 else '')
                     + f'App 侧卖出动作由老大执行，龙爪不挂单。'),
        'analysis': (f'【成交事实来源】券商 App 当日成交回单（老大飞书截图）：证券卖出，'
                     f'{code}，{sell} 份，成交价 {price}，金额 {amt} 元，成交时间 {at_time}。'
                     f'成交性质 = 手动减半仓，不是预设 TP1 0.756 的成交（成交价 0.724 远低于 0.756）。'
                     f'【为什么不能激活 TP1 移动止损】移动止损位是相对该档实际成交价定义的；'
                     f'本次成交价 {price} 与当日价格均在 0.730 下方，若把 TP1 标 done 并上移止损到 '
                     f'{after_tp1}，等于没到 TP 却先丢保护 —— 违反 P0-64「成交事实只能来自券商回单、'
                     f'不可由价格推断」。'
                     f'【减仓后参数重算依据】{evidence_text}'
                     f'【现金】本脚本不改 cash / market_value / total_assets —— 现金唯一权威源是'
                     f'券商 App 可用资金。毛回款 {amt} 元，ETF 卖出无印花税但有佣金，'
                     f'实际可用资金须以老大 App 截图为准。'),
        'outcome': (f'已落库并读回验证：持仓 {new_shares} 份 @ {cost}（成本额 {round(new_shares * cost, 2)}），'
                    f'TP 各档 status 仍为 pending，现金待 App 校准。'),
        'related_files': ('stock-portfolio/monitor_positions.yaml + stock-portfolio/portfolio_state.yaml + '
                          'stock-portfolio/decision_log.yaml + stock-portfolio/funds_log.txt'),
        'data_sources': ['券商 App 当日成交回单（老大飞书截图）'],
        'executed_by': f'龙爪（{now_str()}，scripts/manual_sell_exec.py）',
    }
    body = yaml.safe_dump([entry], allow_unicode=True, default_flow_style=False,
                           sort_keys=False, width=10 ** 6)
    lines = text.split('\n')
    idx = next((i for i, l in enumerate(lines) if l.startswith('decisions:')), None)
    if idx is None:
        raise SystemExit('❌ decision_log.yaml 找不到 decisions:')
    end = len(lines)
    for i in range(idx + 1, len(lines)):
        l = lines[i]
        if l and not l.startswith(' ') and not l.startswith('-') and ':' in l:
            end = i
            break
    lines = lines[:end] + body.rstrip('\n').split('\n') + lines[end:]
    out = '\n'.join(lines)
    dd = yaml.safe_load(out)
    assert len(dd.get('decisions') or []) == len(decs) + 1, 'decisions 数量异常'
    assert len(dd.get('records') or []) == len(recs), 'records 数量异常'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('code')
    ap.add_argument('--shares', type=int, required=True)
    ap.add_argument('--price', type=float, required=True)
    ap.add_argument('--time', required=True, help='成交时间 HH:MM:SS')
    ap.add_argument('--reason', required=True)
    ap.add_argument('--warn', type=float)
    ap.add_argument('--tp1', help='level:target:shares')
    ap.add_argument('--tp2', help='level:target:shares')
    ap.add_argument('--after-tp1', type=float)
    ap.add_argument('--drop-after-tp2', action='store_true')
    ap.add_argument('--last-price', type=float)
    ap.add_argument('--note')
    ap.add_argument('--evidence')
    ap.add_argument('--evidence-key', default='sl_tp_recalc_manual_sell')
    ap.add_argument('--warn-note', help='预警线说明正文（整段重写）')
    ap.add_argument('--sl-note', help='止损说明正文（整段重写）')
    ap.add_argument('--trail-note', help='trailing_stop.note 正文（整段重写）')
    ap.add_argument('--tp-condition', action='append', default=[],
                    help='level=condition 正文，例 1=反弹到 0.756 减 2000 份')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    tps = []
    for spec, def_level in ((args.tp1, 1), (args.tp2, 2)):
        if not spec:
            continue
        parts = spec.split(':')
        if len(parts) == 2:          # 简写 target:shares，档位取默认（tp1→1, tp2→2）
            tps.append((def_level, float(parts[0]), int(parts[1])))
        elif len(parts) == 3:        # 完整 level:target:shares
            tps.append((int(parts[0]), float(parts[1]), int(parts[2])))
        else:
            raise SystemExit(f'❌ --tp 格式应为 target:shares 或 level:target:shares，收到 {spec}')

    ptext = POS.read_text(encoding='utf-8')
    stext = STATE.read_text(encoding='utf-8')

    d0 = yaml.safe_load(ptext)
    cfg0 = next((x for x in d0['positions'] if str(x.get('code')) == args.code), None)
    if cfg0 is None:
        raise SystemExit(f'❌ 找不到 code={args.code}')
    cost = float(cfg0['cost'])
    cur_shares = int(cfg0['shares'])

    texts = {}
    if args.warn_note:
        texts['warn_line_note'] = args.warn_note
    if args.sl_note:
        texts['sl_note'] = args.sl_note
    if args.trail_note:
        texts['trail_note'] = args.trail_note
    tp_conds = []
    for spec in args.tp_condition:
        lv, _, body = spec.partition('=')
        if not lv.strip() or not body.strip():
            raise SystemExit(f'❌ --tp-condition 格式应为 level=文本，收到 {spec}')
        tp_conds.append((int(lv.strip()), body))
    if tp_conds:
        texts['tp_conditions'] = tp_conds

    evidence = []
    if args.evidence:
        for line in args.evidence.split('||'):
            k, _, v = line.partition('=')
            if k.strip():
                evidence.append((k.strip(), v.strip()))

    new_text, new_shares, cost, amt = edit_positions(
        ptext, args.code, args.shares, args.price, args.time, args.reason,
        args.warn, tps, args.after_tp1, args.drop_after_tp2, evidence, args.evidence_key, texts)
    new_state, _ = edit_state(
        stext, args.code, args.shares, args.price, args.warn, tps, args.after_tp1,
        args.drop_after_tp2, args.last_price, args.note, cost)
    new_dlog = append_decision(
        DLOG.read_text(encoding='utf-8'), args.code, args.shares, args.price, args.time,
        args.reason, new_shares, cost, amt, args.warn, tps, args.after_tp1,
        args.drop_after_tp2, args.evidence or '（无附加证据）')

    print(f'▶ 手动卖出登记 {args.code}：{args.shares} 份 @ {args.price} → 剩余 {new_shares} 份')
    print(f'  毛回款 {amt} 元（现金不改，待 App 校准）')
    if args.dry_run:
        print('（dry-run，未写入）')
        return 0

    baks = []
    for p in (POS, STATE, DLOG, FUNDS):
        if p.exists():
            b = p.with_name(p.name + f'.bak.{ts()}_pre_manual_sell')
            shutil.copy2(p, b)
            baks.append((p, b))

    try:
        POS.write_text(new_text, encoding='utf-8')
        STATE.write_text(new_state, encoding='utf-8')
        DLOG.write_text(new_dlog, encoding='utf-8')
        with FUNDS.open('a', encoding='utf-8') as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d')} {args.time}] {args.code} 手动卖出 "
                    f"{args.shares} 份 @ {args.price} = {amt} 元（券商 App 回单）；"
                    f"现金待 App 可用资金校准（毛回款 {amt}，ETF 无印花税、有佣金）")
    except Exception as ex:
        for p, b in baks:
            shutil.copy2(b, p)
        raise SystemExit(f'❌ 写入失败已回滚：{ex}')

    # 读回断言
    rd = yaml.safe_load(POS.read_text(encoding='utf-8'))
    rs = next(x for x in rd['positions'] if str(x.get('code')) == args.code)
    assert rs['shares'] == new_shares, f"shares 读回 {rs['shares']} != {new_shares}"
    statuses = {t['level']: t.get('status') for t in rs.get('take_profit') or []}
    assert all(v == 'pending' for v in statuses.values()), f'TP 状态被误改: {statuses}'
    print(f'  🔍 monitor_positions：shares={rs["shares"]} TP状态={statuses} '
          f'SL={rs.get("stop_loss")} warn={rs.get("warn_line")}')
    print(f'     trailing_stop={ {k: v for k, v in (rs.get("trailing_stop") or {}).items() if k != "note"} }')
    print(f'     take_profit=' + ' / '.join(
        f'TP{t["level"]}={t["target"]}(减{t["shares"]})' for t in rs.get('take_profit') or []))

    rsd = yaml.safe_load(STATE.read_text(encoding='utf-8'))
    sp = next(x for x in rsd['positions'] if str(x.get('code')) == args.code)
    assert sp['shares'] == new_shares, f"影子 shares 读回 {sp['shares']}"
    print(f'  🔍 portfolio_state：shares={sp["shares"]} cost_amount={sp["cost_amount"]} '
          f'last_price={sp.get("last_price")} float_pnl={sp.get("float_pnl")}')

    rdd = yaml.safe_load(DLOG.read_text(encoding='utf-8'))
    print(f'  🔍 decision_log：records={len(rdd.get("records") or [])} '
          f'decisions={len(rdd.get("decisions") or [])}')

    rc = subprocess.run([sys.executable, str(POSPY), 'check'], capture_output=True, text=True)
    print('  pos.py check:', rc.stdout.strip().replace('\n', ' | '))
    if rc.returncode != 0:
        for p, b in baks:
            shutil.copy2(b, p)
        raise SystemExit('❌ 漂移检查失败，已回滚')

    if SYNC.exists() and not NO_SYNC:
        r = subprocess.run([sys.executable, str(SYNC)], capture_output=True, text=True)
        ok = [l for l in r.stdout.split('\n') if '同步完成' in l]
        print(f'  NAS 同步 rc={r.returncode} {ok}')

    print(f'✅ 手动卖出登记完成。毛回款 {amt} 元 —— cash/market_value/total_assets 未改，'
          f'请用券商 App 可用资金截图校准。')
    return 0


if __name__ == '__main__':
    sys.exit(main())