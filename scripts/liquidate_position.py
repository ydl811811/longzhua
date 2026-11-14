#!/usr/bin/env python3
"""liquidate_position.py —— 清仓专用执行器（schema v1）

2026-11-13 新增。背景：记录两笔 ETF 清仓时，manual_sell_exec.py 只支持减仓
（TP 档保持 pending），清仓需手写一次性 YAML 拼接脚本 → 2026-11-13 返工 5 版、
耗时 67 分钟。本脚本把「清仓」变成一个原子命令，一次完成 schema v1 §2.7 规定的 5 件事：

  1. shares → 0（base_shares 保留原始建仓份数）
  2. status → sold + strategy → cleared
  3. take_profit[].status 全部 → cleared（不是 done —— 清仓时没有任何一档成交）
  4. trailing_stop → null（否则 get_effective_stop_loss 会造出高于成交价的假止损）
  5. 写 exit_record（正典结构）+ 追加 actions sell 条目

用法：
  python3 liquidate_position.py <code> \\
      --shares 5000 --price 1.100 --time '10:17:49' \\
      --reason '09:36 预警线破位后老大手动清仓' \\
      [--date 2026-11-13] [--evidence 'broker_app_screenshot=2026-11-13 成交页'] \\
      [--dry-run]

安全设计：
  - 改前自动备份（时间戳 .bak）
  - 改后内置断言：YAML 可解析 / status=sold / shares=0 / TP 全 cleared /
    trailing_stop=null / exit_record 必填齐全 / 生效止损 == 基础止损
  - 断言失败自动回滚
  - 只改目标 position 块，不动其它块
"""
import sys
import re
import json
import shutil
import datetime
import argparse
from pathlib import Path

import yaml

POS = Path.home() / '.hermes/stock-portfolio/monitor_positions.yaml'
STATE = Path.home() / '.hermes/stock-portfolio/portfolio_state.yaml'

EXIT_REQUIRED = ('exit_date', 'exit_shares', 'exit_price', 'exit_amount',
                 'realized_pnl', 'realized_pnl_pct', 'cleared_at', 'cleared_reason')

# 受控词表（与 references/ledger-vocabulary.md 一致）
ACTION_TYPE = {'buy', 'sell', 'add', 'tp_adjust', 'order_placed', 'add_position_plan',
               'strategy_change', 'grid_init', 'grid_auto', 'grid_param_sync'}
ACTION_TRIGGER = {'manual', 'tp1', 'tp2', 'tp3', 'stop_loss', 'warn_line',
                  'condition_order', 'grid_auto', 'strategy_change', 'rebalance', 'user_manual'}


# ─────────────────────── YAML 文本块定位 ───────────────────────
def pos_code_block(lines, code):
    """返回该 position 块的 (start, end) 行号区间。

    ★ live 台账的列表项缩进不统一：第一个 position 是 '- code: xxx'（0 列缩进，
      YAML 里等同顶层 positions: 的直接子项），其余是 '  - code: xxx'（2 列）。
      本函数按**实际匹配到的缩进**计算块边界，不假设固定缩进。
    """
    pat = re.compile(r"^(\s*)-\s+code:\s*['\"]?" + re.escape(code) + r"['\"]?\s*$")
    start = None
    item_indent = None
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if m:
            start = i
            item_indent = len(m.group(1))
            break
    if start is None:
        raise SystemExit(f'❌ 找不到 position 块: {code}')
    end = len(lines)
    for j in range(start + 1, len(lines)):
        ln = lines[j]
        if not ln.strip():
            continue
        ind = len(ln) - len(ln.lstrip())
        # 下一个同缩进或更浅的列表项 / 任何更浅的非列表内容 → 块结束
        if ind <= item_indent and not re.match(r'^\s*-\s', ln):
            end = j
            break
        if ind == item_indent and re.match(r'^\s*-\s', ln):
            end = j
            break
    return start, end


def find_key(lines, s, e, key, indent=None):
    """在块内找顶层 key 行号。返回行号或 None。

    indent=None 时自适应：取块内第一个缩进 >= 2 的 key 行作为基准缩进
    （live 台账 position 块的 key 缩进为 2，列表项 '- ' 本身在 0 列）。
    """
    if indent is None:
        indent = 2
        for i in range(s, min(e, len(lines))):
            ln = lines[i]
            if re.match(r'^\s*-\s', ln):
                continue
            if ln.strip() and not ln.lstrip().startswith('#'):
                indent = len(ln) - len(ln.lstrip())
                break
    pat = re.compile(r'^' + ' ' * indent + re.escape(key) + r'\s*:')
    for i in range(s, min(e, len(lines))):
        if pat.match(lines[i]):
            return i
    return None


def set_key(lines, s, e, key, new_text, indent=None):
    i = find_key(lines, s, e, key, indent)
    if i is None:
        return None
    ind = len(lines[i]) - len(lines[i].lstrip())
    lines[i] = ' ' * ind + new_text
    return i


def del_key(lines, s, e, key, indent=None):
    """删除顶层 key 及其嵌套子行。"""
    i = find_key(lines, s, e, key, indent)
    if i is None:
        return False
    indent = len(lines[i]) - len(lines[i].lstrip())
    j = i + 1
    while j < len(lines):
        ln = lines[j]
        if not ln.strip():
            j += 1
            continue
        ind = len(ln) - len(ln.lstrip())
        if ind <= indent:
            break
        j += 1
    del lines[i:j]
    return True


def insert_after(lines, s, e, anchor, new_lines, indent=None):
    i = find_key(lines, s, e, anchor, indent)
    if i is None:
        return False
    ind = len(lines[i]) - len(lines[i].lstrip())
    for off, nl in enumerate(new_lines):
        lines.insert(i + 1 + off, ' ' * ind + nl)
    return True


def tp_item_range(lines, s, e, level):
    """定位 take_profit 里某个 level 档的行区间。"""
    pat = re.compile(r'^\s*-\s+level:\s*' + str(level) + r'\s*$')
    for i in range(s, e):
        if pat.match(lines[i]):
            base = len(lines[i]) - len(lines[i].lstrip())
            j = i + 1
            while j < e:
                ln = lines[j]
                if not ln.strip():
                    j += 1
                    continue
                ind = len(ln) - len(ln.lstrip())
                if ind <= base:
                    break
                j += 1
            return i, j
    return None, None


def yq(v):
    """YAML 标量格式化。"""
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?', s):
        return "'" + s + "'"
    return "'" + s.replace("'", "''") + "'"


# ─────────────────────── 清仓主逻辑 ───────────────────────
def liquidate_block(lines, s, e, args, cost):
    """在 [s,e) 块内执行清仓 5 件事。返回 (new_lines, info)。

    ★ 删/插行会改变后续行号 —— 每次结构性改动后必须用 pos_code_block 重算块边界。
      （2026-11-13 一次性脚本返工的根因就是行号漂移）
    """
    code = args.code
    today = args.date or datetime.date.today().isoformat()

    def reblock():
        """重新定位块边界，返回 (s, e)。"""
        nonlocal s, e
        s, e = pos_code_block(lines, code)
        return s, e

    # 读现状
    sh_line = find_key(lines, s, e, 'shares')
    if sh_line is None:
        raise SystemExit('❌ 找不到 shares')
    sh_ind = len(lines[sh_line]) - len(lines[sh_line].lstrip())
    m = re.match(r"^" + ' ' * sh_ind + r"shares:\s*(\d+)\s*$", lines[sh_line])
    if not m:
        raise SystemExit('❌ shares 不是整数格式')
    pos_shares = int(m.group(1))
    if args.shares != pos_shares:
        raise SystemExit(
            f'❌ --shares {args.shares} ≠ 实际持仓 {pos_shares} 份。'
            f'清仓必须卖光全部（减仓请用 manual_sell_exec.py）')

    base_shares = pos_shares
    bs_line = find_key(lines, s, e, 'base_shares')
    if bs_line is not None:
        mb_i = len(lines[bs_line]) - len(lines[bs_line].lstrip())
        mb = re.match(r"^" + ' ' * mb_i + r"base_shares:\s*(\d+)\s*$", lines[bs_line])
        if mb:
            base_shares = int(mb.group(1))

    # ── 1) shares → 0 ──
    lines[sh_line] = ' ' * sh_ind + 'shares: 0'

    # ── 2) status → sold + strategy → cleared ──
    set_key(lines, s, e, 'status', 'status: sold')
    if find_key(lines, s, e, 'strategy') is None:
        insert_after(lines, s, e, 'status', ['strategy: cleared'])
    else:
        set_key(lines, s, e, 'strategy', 'strategy: cleared')

    # ── 3) take_profit 各档 status → cleared ──
    tp_levels = []
    i = s
    while i < e:
        mtp = re.match(r"^\s*-\s+level:\s*(\d+)\s*$", lines[i])
        if mtp:
            lvl = int(mtp.group(1))
            tp_levels.append(lvl)
            base = len(lines[i]) - len(lines[i].lstrip())
            j = i + 1
            while j < e:
                ln = lines[j]
                if not ln.strip():
                    j += 1
                    continue
                ind = len(ln) - len(lines[j].lstrip())
                if ind <= base:
                    break
                mst = re.match(r"^(\s+)status:\s*(\S+)\s*$", ln)
                if mst:
                    lines[j] = f"{mst.group(1)}status: cleared"
                j += 1
            i = j
            continue
        i += 1

    # ── 4) trailing_stop → null ──
    del_key(lines, s, e, 'trailing_stop')
    reblock()

    # ── 5) 写 exit_record ──
    amount = round(args.shares * args.price, 2)
    realized = round((args.price - cost) * args.shares, 2)
    realized_pct = round((args.price - cost) / cost * 100, 2) if cost else 0.0
    cleared_at = f'{today} {args.time}'

    ev = {}
    if args.evidence:
        for line in args.evidence.split('||'):
            k, _, v = line.partition('=')
            if k.strip():
                ev[k.strip()] = v.strip()

    er_lines = [
        "exit_record:",
        f"  exit_date: '{today}'",
        f"  exit_shares: {args.shares}",
        f"  exit_price: {args.price}",
        f"  exit_amount: {amount}",
        f"  realized_pnl: {realized}",
        f"  realized_pnl_pct: {realized_pct}",
        f"  cleared_at: '{cleared_at}'",
        f"  cleared_reason: {yq(args.reason)}",
    ]
    if ev:
        er_lines.append('  fill:')
        er_lines.append(f'    shares: {args.shares}')
        er_lines.append(f'    price: {args.price}')
        er_lines.append(f'    amount: {amount}')
        er_lines.append(f"    time: '{cleared_at}'")
        er_lines.append('    broker_confirmed: true')
        for k, v in ev.items():
            er_lines.append(f'    {k}: {yq(v)}')

    # 移除旧的 exit_record（若有），再插入
    del_key(lines, s, e, 'exit_record')
    reblock()
    # 插到 strategy 之后
    si = find_key(lines, s, e, 'strategy')
    if si is None:
        raise SystemExit('❌ 找不到 strategy')
    si_ind = len(lines[si]) - len(lines[si].lstrip())
    er_indented = [' ' * si_ind + er_lines[0]] + \
        [' ' * (si_ind + 2) + l.strip() if not l.startswith('  ') else ' ' * (si_ind + 2) + l[2:]
         for l in er_lines[1:]]
    for off, nl in enumerate(er_indented):
        lines.insert(si + 1 + off, nl)
    reblock()

    # 移除顶层废弃字段（若存在）
    #   含 historical_exit_record —— 它是旧快照写法（8/7 已废弃），清仓时一并清除，
    #   但其内容先并入 exit_record.legacy_fields 以免丢失。
    for f in ('cleared_at', 'cleared_reason', 'realized_pnl', 'realized_pnl_pct'):
        del_key(lines, s, e, f)
    her = find_key(lines, s, e, 'historical_exit_record')
    if her is not None:
        her_ind = len(lines[her]) - len(lines[her].lstrip())
        her_end = her + 1
        while her_end < e:
            ln = lines[her_end]
            if not ln.strip():
                her_end += 1
                continue
            if (len(ln) - len(ln.lstrip())) <= her_ind:
                break
            her_end += 1
        old_hist = '\n'.join(lines[her:her_end]).strip()
        del lines[her:her_end]
        reblock()
        # 旧快照内容并入 exit_record.legacy_historical_exit_record（原文保留，不丢信息）
        ei = find_key(lines, s, e, 'exit_record')
        if ei is not None:
            ei_ind = len(lines[ei]) - len(lines[ei].lstrip())
            hist_lines = [' ' * (ei_ind + 2) + 'legacy_historical_exit_record: ' + yq(old_hist)]
            for off, nl in enumerate(hist_lines):
                lines.insert(ei + 1 + off, nl)
            reblock()
    reblock()

    # ── 追加 actions sell 条目 ──
    trig = args.trigger or 'manual'
    if trig not in ACTION_TRIGGER:
        raise SystemExit(f'❌ trigger={trig!r} 不在受控词表 {sorted(ACTION_TRIGGER)}')
    act_lines = [
        "  - date: '%s'" % today,
        "    time: '%s'" % args.time,
        "    type: sell",
        f"    trigger: {trig}",
        f"    shares: {args.shares}",
        f"    price: {args.price}",
        f"    amount: {amount}",
        f"    reason: {yq(args.reason)}",
    ]
    ai = find_key(lines, s, e, 'actions')
    if ai is None:
        # 没有 actions 列表则新建（放在 block 末尾的同级）
        a_ind = 2
        for i in range(s, e):
            if lines[i].strip() and not lines[i].lstrip().startswith('-'):
                a_ind = len(lines[i]) - len(lines[i].lstrip()); break
        act_indented = [' ' * a_ind + 'actions:']
        for k, nl in enumerate(act_lines):
            act_indented.append(' ' * (a_ind + (0 if k == 0 else 2)) + nl.strip())
        lines[s:e] = lines[s:e] + act_indented
    else:
        # 插到 actions: 列表末尾（下一个同级 key 之前）
        base = len(lines[ai]) - len(lines[ai].lstrip())
        j = ai + 1
        while j < len(lines):
            ln = lines[j]
            if not ln.strip():
                j += 1
                continue
            ind = len(ln) - len(ln.lstrip())
            if ind <= base and not re.match(r"^\s*-\s", ln):
                break
            j += 1
        # live 台账的 YAML 列表风格：列表项 '- key: v' 与 key 同缩进，
        # 续行比 key 多 2 空格（实测：'  actions:' / '  - date: ...' / '    time: ...'）
        act_indented = []
        for k, nl in enumerate(act_lines):
            if k == 0:
                act_indented.append(' ' * base + nl.strip())
            else:
                act_indented.append(' ' * (base + 2) + nl.strip())
        for off, nl in enumerate(act_indented):
            lines.insert(j + off, nl)
    reblock()

    # ── stop_loss_note 追加历史留痕说明 ──
    #    注意：该字段是长文本，YAML 会折行成多行 —— 必须追加到该 key 块的**最后一行**，
    #    否则说明会被插到句子中间（2026-11-13 测试踩到）。
    sn = find_key(lines, s, e, 'stop_loss_note')
    if sn is not None:
        note = ' [2026-11-13 归一：sold 条目的 stop_loss 为历史留痕，不再是活跃止损]'
        blk_end = sn + 1
        while blk_end < e:
            ln = lines[blk_end]
            if not ln.strip():
                blk_end += 1
                continue
            ind = len(ln) - len(ln.lstrip())
            if ind <= 2:
                break
            blk_end += 1
        last = blk_end - 1
        if '历史留痕' not in '\n'.join(lines[sn:blk_end]):
            lines[last] = lines[last].rstrip() + note

    info = {
        'code': code, 'pos_shares': pos_shares, 'base_shares': base_shares,
        'cost': cost, 'exit_shares': args.shares, 'exit_price': args.price,
        'exit_amount': amount, 'realized_pnl': realized,
        'realized_pnl_pct': realized_pct, 'cleared_at': cleared_at,
        'tp_levels_cleared': tp_levels, 'trigger': trig,
    }
    return lines, info


# ─────────────────────── 校验 ───────────────────────
def verify(text, args):
    """写入后断言。任一失败抛异常（调用方回滚）。"""
    doc = yaml.safe_load(text)
    pos = next((x for x in doc['positions'] if str(x.get('code')) == args.code), None)
    assert pos is not None, 'position 丢失'
    assert pos.get('status') == 'sold', f"status={pos.get('status')} 应为 sold"
    assert pos.get('shares') == 0, f"shares={pos.get('shares')} 应为 0"
    assert pos.get('strategy') == 'cleared', f"strategy={pos.get('strategy')} 应为 cleared"
    assert pos.get('trailing_stop') in (None, 'null'), \
        f"trailing_stop={pos.get('trailing_stop')} 必须为 null"
    for t in (pos.get('take_profit') or []):
        assert t.get('status') in ('cleared', 'done'), \
            f"TP{t.get('level')} status={t.get('status')} 非法"
    er = pos.get('exit_record')
    assert isinstance(er, dict), f'exit_record 必须是 map，实际 {type(er).__name__}'
    miss = [f for f in EXIT_REQUIRED if f not in er]
    assert not miss, f'exit_record 缺字段 {miss}'
    assert abs(er['exit_amount'] - er['exit_shares'] * er['exit_price']) < 0.01, \
        'exit_amount ≠ shares × price'
    for f in ('cleared_at', 'cleared_reason', 'realized_pnl', 'realized_pnl_pct'):
        assert f not in pos, f'顶层废弃字段 {f} 未清除'
    # 生效止损必须等于基础止损（移动止损不得残留）
    sl = pos.get('stop_loss')
    ts = pos.get('trailing_stop')
    if sl is not None and ts:
        raise AssertionError('trailing_stop 未清除')
    # actions 里必须有本次 sell
    sells = [a for a in (pos.get('actions') or [])
             if isinstance(a, dict) and a.get('type') == 'sell'
             and a.get('date') == er['exit_date']]
    assert sells, 'actions 里找不到本次 sell 记录'
    a0 = sells[-1]
    for f in ('date', 'time', 'type', 'trigger', 'shares', 'price', 'amount', 'reason'):
        assert a0.get(f) not in (None, ''), f'action 缺 {f}'
    assert a0['trigger'] in ACTION_TRIGGER, f"trigger={a0['trigger']} 不在词表"
    assert a0['type'] in ACTION_TYPE, f"type={a0['type']} 不在词表"
    assert a0['shares'] == er['exit_shares'], 'action shares 与 exit_shares 不一致'
    assert abs(float(a0['price']) - er['exit_price']) < 1e-9, 'action price 与 exit_price 不一致'
    return pos


def main():
    ap = argparse.ArgumentParser(description='清仓执行器（schema v1）')
    ap.add_argument('code')
    ap.add_argument('--shares', type=int, required=True)
    ap.add_argument('--price', type=float, required=True)
    ap.add_argument('--time', required=True, help='成交时间 HH:MM:SS')
    ap.add_argument('--reason', required=True)
    ap.add_argument('--date', help='成交日 YYYY-MM-DD，默认今天')
    ap.add_argument('--trigger', default='manual', help='受控 trigger，默认 manual')
    ap.add_argument('--evidence', help='key=value||key=value，填入 exit_record.fill')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    text = POS.read_text(encoding='utf-8')
    doc = yaml.safe_load(text)
    cfg = next((x for x in doc['positions'] if str(x.get('code')) == args.code), None)
    if cfg is None:
        raise SystemExit(f'❌ 找不到 code={args.code}')
    if cfg.get('status') != 'holding':
        raise SystemExit(f'❌ {args.code} 当前 status={cfg.get("status")}，非 holding，不能清仓')
    cost = float(cfg.get('cost') or 0)

    lines = text.split('\n')
    s, e = pos_code_block(lines, args.code)
    lines, info = liquidate_block(lines, s, e, args, cost)
    new_text = '\n'.join(lines)

    if args.dry_run:
        print('=== DRY RUN ===')
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print('\n--- 变更块 ---')
        print('\n'.join(lines[s:e + 40]))
        return 0

    # ── 备份 ──
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    bak = POS.with_suffix(POS.suffix + f'.bak.{ts}_liquidate_{args.code}')
    shutil.copy2(POS, bak)

    try:
        pos = verify(new_text, args)
    except AssertionError as e:
        shutil.copy2(bak, POS)
        raise SystemExit(f'❌ 写入前断言失败，已回滚：{e}')

    POS.write_text(new_text, encoding='utf-8')
    print(f'✅ 已清仓 {args.code}')
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print(f'备份: {bak}')
    print('提示: 记得跑 pos.py check + ledger_lint.py + sync_positions_yml.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
