#!/usr/bin/env python3
"""tp_exec.py —— 持仓止盈档成交登记器

背景（2026-11-10）
-----------------
515790 的移动止损（TP1 成交后 0.730 / TP2 成交后 0.750）依赖 take_profit 档的
status 变为 done。台账里 status 还是 pending 时：
  - 脚本的生效止损停在基础 0.708（保护线没上移）
  - 台账持仓份额仍是 8000（而 App 里已只剩 4000）
两个口径同时错，且要手编 YAML 才能修 —— 易漏、易错。

为什么必须人工确认、不能自动
------------------------------
移动止损位是相对「该档实际成交价」定义的。若让脚本按「价格曾触达 TP target」
自动上移：TP1 成交价 0.756 → 移动止损 0.730，而现价才 0.734，差 0.55% < 0.25 ATR，
等于把止损贴到脸上，次日必被噪声扫掉；且 TP 未成交就上移 = 没减仓先丢保护。
所以「该档已成交」这个事实只能来自券商成交回单，由老大确认后登记。

用法
----
  python3 ~/.hermes/scripts/tp_exec.py --list 515790
  python3 ~/.hermes/scripts/tp_exec.py 515790 1 --price 0.756
  python3 ~/.hermes/scripts/tp_exec.py 515790 1 --price 0.756 --dry-run

行为（全部行级定点编辑，不整体重序列化 YAML —— 保住注释与分析正文）
  monitor_positions.yaml
    · 该 code 段 take_profit 中 level=N 的项：status -> done
      并追加 filled_price / filled_shares / filled_at
    · 该段持仓 shares 扣减（base_shares 保留原始建仓量）
    · capital_check.current_position_amount = 新 shares × cost
  portfolio_state.yaml
    · 影子清单 shares / cost_amount 同步
    · take_profit 对应档 status -> done + filled_*
    · available_shares 同步
  decision_log.yaml
    · 追加一条成交登记决策（自动备份 + 双 list 守恒校验）

安全
  · 幂等：已 done / cleared 则拒绝重复登记
  · 改动前对三个文件各生成 .bak
  · 每次写入后 yaml.safe_load 校验 + 条数守恒校验，失败即回滚
  · 现金不自动改：现金只认券商 App 截图，脚本只提示回款额待校准
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

BASE = Path(os.environ.get('TPEXEC_BASE') or (Path.home() / '.hermes' / 'stock-portfolio'))
POS = BASE / 'monitor_positions.yaml'
STATE = BASE / 'portfolio_state.yaml'
DLOG = BASE / 'decision_log.yaml'
SCRIPTS = Path.home() / '.hermes' / 'scripts'
SYNC = SCRIPTS / 'sync_positions_yml.py'
POSPY = SCRIPTS / 'pos.py'
NO_SYNC = bool(os.environ.get('TPEXEC_NO_SYNC'))


def ts():
    return time.strftime('%Y%m%d_%H%M%S')


def now_str():
    return time.strftime('%Y-%m-%d %H:%M:%S')


# ───────────────────────── monitor_positions.yaml ─────────────────────────

def pos_code_block(lines, code):
    """返回该 code 段的行号区间 [start, end)"""
    start = None
    for i, l in enumerate(lines):
        m = re.match(r"^-\s+code:\s*['\"]?" + re.escape(code) + r"['\"]?\s*$", l)
        if m:
            start = i
            break
    if start is None:
        raise SystemExit(f'❌ monitor_positions.yaml 里找不到 code={code}')
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^-\s+code:", lines[j]):
            end = j
            break
    return start, end


def tp_item_range(lines, s, e, level):
    """在 [s,e) 内定位 take_profit 的 level=N 项，返回 (item_start, item_end)

    注意：不能「遇到第一个 - level: 就 break」—— 那样 level=2 永远找不到。
    做法：先定位 take_profit 键，再确定其列表结束行（缩进 <= take_profit 缩进的 key 行），
    在列表范围内收集所有 - level: N 标记，选出目标项。
    """
    tp_idx = None
    tp_indent = 0
    for i in range(s, e):
        m = re.match(r"^(\s*)take_profit:\s*$", lines[i])
        if m:
            tp_idx = i
            tp_indent = len(m.group(1))
            break
    if tp_idx is None:
        raise SystemExit(f'❌ 该持仓没有 take_profit 段')

    # 列表结束：take_profit 之后第一个缩进 <= tp_indent 的非空 key 行
    list_end = e
    for i in range(tp_idx + 1, e):
        l = lines[i]
        if not l.strip() or l.strip().startswith('#'):
            continue
        ind = len(l) - len(l.lstrip())
        if ind <= tp_indent and re.match(r"^\s*[\w-]+:", l):
            list_end = i
            break

    # 收集所有档位标记
    marks = []
    for i in range(tp_idx + 1, list_end):
        m = re.match(r"^(\s*)-\s+level:\s*(\d+)\s*$", lines[i])
        if m:
            marks.append((i, int(m.group(2))))
    if not marks:
        raise SystemExit(f'❌ take_profit 段内没有档位')
    hit = [i for i, lv in marks if lv == level]
    if not hit:
        raise SystemExit(f'❌ 该持仓没有 take_profit level={level} 档'
                         f'（现有档位：{[lv for _, lv in marks]}）')
    item_s = hit[0]
    item_e = next((i for i, _ in marks if i > item_s), list_end)
    return item_s, item_e


def edit_positions(text, code, level, price, sell):
    lines = text.split('\n')
    s, e = pos_code_block(lines, code)

    # 持仓 shares：紧跟 status: holding 之后、缩进 2 的 shares
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
        raise SystemExit('❌ 找不到持仓 shares（status: holding 之后）')
    if sell > pos_sh:
        raise SystemExit(f'❌ 成交 {sell} 份 > 持仓 {pos_sh} 份')

    # cost
    cost = None
    for i in range(s, e):
        m = re.match(r"^  cost:\s*([\d.]+)\s*$", lines[i])
        if m:
            cost = float(m.group(1))
            break

    # take_profit item
    is_s, is_e = tp_item_range(lines, s, e, level)
    item = lines[is_s:is_e]
    st_i = None
    for k, l in enumerate(item):
        if re.match(r"^\s+status:\s*\S+\s*$", l):
            st_i = k
            break
    if st_i is None:
        raise SystemExit('❌ 该档没有 status 字段')
    cur = re.match(r"^\s+status:\s*(\S+)\s*$", item[st_i]).group(1)
    if cur in ('done', 'cleared'):
        raise SystemExit(f'❌ TP{level} 已是 {cur}，不重复登记')
    item[st_i] = re.sub(r"status:\s*\S+", "status: done", item[st_i])
    indent = re.match(r"^(\s*)", item[st_i]).group(1)
    item[st_i + 1:st_i + 1] = [
        f"{indent}filled_price: {price}",
        f"{indent}filled_shares: {sell}",
        f"{indent}filled_at: '{now_str()}'",
    ]
    lines[is_s:is_e] = item

    # capital_check.current_position_amount
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
                lines[i] = f"{m.group(1)}current_position_amount: {round((pos_sh - sell) * cost, 2)}"
                break
    return '\n'.join(lines), pos_sh - sell, cost


# ───────────────────────── portfolio_state.yaml ─────────────────────────

def edit_state(text, code, level, price, sell, new_shares):
    lines = text.split('\n')
    s, e = None, None
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

    cost = None
    for i in range(s, e):
        m = re.match(r"^  cost:\s*([\d.]+)\s*$", lines[i])
        if m:
            cost = float(m.group(1))
            break
    for i in range(s, e):
        m = re.match(r"^  shares:\s*(\d+)\s*$", lines[i])
        if m:
            lines[i] = f"  shares: {new_shares}"
            break
    for i in range(s, e):
        m = re.match(r"^  cost_amount:\s*[\d.]+\s*$", lines[i])
        if m:
            lines[i] = f"  cost_amount: {round(new_shares * cost, 2)}"
            break
    for i in range(s, e):
        m = re.match(r"^  available_shares:\s*\d+\s*$", lines[i])
        if m:
            lines[i] = f"  available_shares: {new_shares}"
            break

    is_s, is_e = tp_item_range(lines, s, e, level)
    item = lines[is_s:is_e]
    st_i = None
    for k, l in enumerate(item):
        if re.match(r"^\s+status:\s*\S+\s*$", l):
            st_i = k
            break
    if st_i is None:
        raise SystemExit('❌ 影子清单该档没有 status 字段')
    cur = re.match(r"^\s+status:\s*(\S+)\s*$", item[st_i]).group(1)
    if cur in ('done', 'cleared'):
        raise SystemExit(f'❌ 影子清单 TP{level} 已是 {cur}')
    item[st_i] = re.sub(r"status:\s*\S+", "status: done", item[st_i])
    indent = re.match(r"^(\s*)", item[st_i]).group(1)
    item[st_i + 1:st_i + 1] = [
        f"{indent}filled_price: {price}",
        f"{indent}filled_shares: {sell}",
        f"{indent}filled_at: '{now_str()}'",
    ]
    lines[is_s:is_e] = item
    return '\n'.join(lines)


# ───────────────────────── decision_log.yaml ─────────────────────────

def append_decision(text, code, level, price, sell, new_shares):
    d = yaml.safe_load(text)
    recs = d.get('records') or []
    decs = d.get('decisions') or []
    entry = {
        'date': time.strftime('%Y-%m-%d'),
        'time': time.strftime('%H:%M'),
        'code': code,
        'topic': f'{code} TP{level} 成交登记 —— 卖出 {sell} 份 @ {price}，'
                 f'持仓 {sell + new_shares} -> {new_shares}，移动止损自动生效',
        'decision': (f'老大在券商 App 实际卖出 {code} {sell} 份 @ {price}，回执确认后由龙爪执行 '
                     f'`tp_exec.py` 登记：monitor_positions.yaml 该档 status -> done（附 filled_price/'
                     f'filled_shares/filled_at），持仓 shares 扣减为 {new_shares}，'
                     f'capital_check.current_position_amount 同步；portfolio_state.yaml 影子清单同步。'
                     f'脚本生效止损随即按 max(基础SL, 已成交档对应移动止损) 上移。'
                     f'App 侧卖出动作由老大执行，龙爪不挂单。'),
        'analysis': (f'移动止损位相对该档实际成交价定义，故「是否成交」只能取自券商成交回单，'
                     f'不可由价格触达推断（若按触达自动上移，TP1 成交价 0.756 对应移动止损 0.730 '
                     f'与现价仅差 0.55% < 0.25 ATR，次日必被噪声扫掉，且未减仓却先丢保护）。'
                     f'成交回款约 {round(sell * price, 2)} 元需以券商 App 截图校准 cash/market_value/'
                     f'total_assets（现金唯一权威源 = App 可用资金，禁止脚本二次倒推）。'),
        'outcome': f'已落库并读回验证；持仓 {new_shares} 份，TP{level} 状态 done。',
        'related_files': ('stock-portfolio/monitor_positions.yaml + stock-portfolio/portfolio_state.yaml + '
                          'stock-portfolio/decision_log.yaml'),
        'data_sources': ['券商 App 成交回执（老大确认）'],
        'executed_by': f'龙爪（{now_str()}，scripts/tp_exec.py）',
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


# ───────────────────────── 其他 ─────────────────────────

def do_list(code):
    d = yaml.safe_load(POS.read_text(encoding='utf-8'))
    for s in d.get('positions') or []:
        if str(s.get('code')) != code:
            continue
        print(f"{code} {s.get('name')}  shares={s.get('shares')} cost={s.get('cost')} "
              f"SL={s.get('stop_loss')} warn={s.get('warn_line')}")
        for tp in s.get('take_profit') or []:
            print(f"  TP{tp.get('level')} target={tp.get('target')} shares={tp.get('shares')} "
                  f"status={tp.get('status')} "
                  f"filled={tp.get('filled_price', '-')}/{tp.get('filled_shares', '-')}")
        trail = s.get('trailing_stop') or {}
        print(f"  trailing_stop: { {k: v for k, v in trail.items() if k != 'note'} }")
        return 0
    raise SystemExit(f'❌ 找不到 code={code}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('code', nargs='?')
    ap.add_argument('level', nargs='?', type=int)
    ap.add_argument('--price', type=float)
    ap.add_argument('--shares', type=int)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()

    if args.list:
        return do_list(args.code)
    if not args.code or args.level is None:
        ap.print_help()
        return 1
    if args.price is None:
        raise SystemExit('❌ 必须给 --price（券商成交价）')

    code, level = args.code, args.level
    ptext = POS.read_text(encoding='utf-8')
    stext = STATE.read_text(encoding='utf-8')

    # 先查该档是否已成交（幂等前置检查，给出准确提示）
    d0 = yaml.safe_load(ptext)
    cfg0 = next((x for x in d0['positions'] if str(x.get('code')) == code), None)
    if cfg0 is None:
        raise SystemExit(f'❌ 找不到 code={code}')
    tp0 = next((t for t in (cfg0.get('take_profit') or [])
                if int(t.get('level', 0)) == level), None)
    if tp0 is None:
        raise SystemExit(f'❌ 没有 take_profit level={level} 档')
    st0 = str(tp0.get('status') or 'pending')
    if st0 in ('done', 'cleared'):
        raise SystemExit(f'❌ TP{level} 已是 {st0}，不重复登记'
                         f'（如需修正请直接改台账或先回滚 .bak）')
    sell = args.shares if args.shares is not None else int(tp0.get('shares') or 0)
    if sell <= 0:
        raise SystemExit('❌ 成交份额无效')

    new_text, new_shares, cost = edit_positions(ptext, code, level, args.price, sell)
    new_state = edit_state(stext, code, level, args.price, sell, new_shares)
    new_dlog = append_decision(DLOG.read_text(encoding='utf-8'), code, level,
                               args.price, sell, new_shares)

    print(f'▶ 登记 {code} TP{level}：成交 {sell} 份 @ {args.price} → 持仓 {new_shares} 份')
    if args.dry_run:
        print('（dry-run，未写入）')
        return 0

    # 备份
    baks = []
    for p in (POS, STATE, DLOG):
        b = p.with_name(p.name + f'.bak.{ts()}_pre_tp_exec')
        shutil.copy2(p, b)
        baks.append(b)

    try:
        POS.write_text(new_text, encoding='utf-8')
        STATE.write_text(new_state, encoding='utf-8')
        DLOG.write_text(new_dlog, encoding='utf-8')
    except Exception as ex:
        for p, b in zip((POS, STATE, DLOG), baks):
            shutil.copy2(b, p)
        raise SystemExit(f'❌ 写入失败已回滚：{ex}')

    # 读回验证
    rd = yaml.safe_load(POS.read_text(encoding='utf-8'))
    rs = next(x for x in rd['positions'] if str(x.get('code')) == code)
    hit = next(t for t in rs['take_profit'] if int(t.get('level', 0)) == level)
    assert rs['shares'] == new_shares, f"shares 读回 {rs['shares']} != {new_shares}"
    assert hit['status'] == 'done', f"status 读回 {hit['status']}"
    print(f'  🔍 读回 monitor_positions：shares={rs["shares"]} '
          f'TP{level}.status={hit["status"]} '
          f'filled={hit.get("filled_price")}/{hit.get("filled_shares")}')

    rdd = yaml.safe_load(DLOG.read_text(encoding='utf-8'))
    print(f'  🔍 读回 decision_log：records={len(rdd.get("records") or [])} '
          f'decisions={len(rdd.get("decisions") or [])} '
          f'last={rdd["decisions"][-1]["topic"][:44]}')

    # 漂移检查
    rc = subprocess.run([sys.executable, str(POSPY), 'check'], capture_output=True, text=True)
    print('  pos.py check:', rc.stdout.strip().replace('\n', ' | '))
    if rc.returncode != 0:
        for p, b in zip((POS, STATE, DLOG), baks):
            shutil.copy2(b, p)
        raise SystemExit('❌ 漂移检查失败，已回滚')

    # NAS 同步
    if SYNC.exists() and not NO_SYNC:
        r = subprocess.run([sys.executable, str(SYNC)], capture_output=True, text=True)
        ok = [l for l in r.stdout.split('\n') if '同步完成' in l]
        print(f'  NAS 同步 rc={r.returncode} {ok}')
    elif NO_SYNC:
        print('  （沙箱模式，跳过 NAS 同步）')

    proceeds = round(sell * args.price, 2)
    print(f'✅ 登记完成。回款约 {proceeds} 元 —— 现金/市值/总资产请以券商 App 截图校准'
          f'（现金唯一权威源 = App 可用资金）。')
    print(f'   生效止损已按 status=auto 上移（基础 SL 与移动止损取 max，只上移不下移）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
