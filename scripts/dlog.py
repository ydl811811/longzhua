#!/usr/bin/env python3
"""dlog.py — 决策日志跨归档查询工具（配合 2026-11-09 方案C 轮转）

decision_log.yaml 已改为「滚动保留 + 按月归档」：
  活文件 ~/.hermes/stock-portfolio/decision_log.yaml      → 最近 8 records / 45 decisions
  归档   ~/.hermes/stock-portfolio_archive/decision_log/    → records_YYYY-MM.yaml / decisions_YYYY-MM.yaml

用法：
  python3 dlog.py recent 5              # 最近 5 条 decisions（含归档，按时间排序）
  python3 dlog.py recent 5 --key records
  python3 dlog.py find 159583            # 按 code 全文检索（活文件+归档）
  python3 dlog.py month 2026-09          # 某月全部条目
  python3 dlog.py stats                  # 各月条数/体积 + 活文件状态
  python3 dlog.py full --code 159583     # 打印命中条目的完整正文（长文慎用）

设计约束：
  - 只读，不修改任何台账文件
  - 输出默认截断（analysis 正文 preview），避免 token 爆炸
  - 与 pos.py 一样作为「查台账不整读大文件」的入口
"""
import sys
import re
from pathlib import Path

import yaml

BASE = Path.home() / '.hermes' / 'stock-portfolio'
LIVE = BASE / 'decision_log.yaml'
ARCH_DIR = Path.home() / '.hermes' / 'stock-portfolio_archive' / 'decision_log'
PREVIEW = 400


def _date(x):
    v = x.get('date')
    if isinstance(v, str):
        return v
    return v.isoformat() if hasattr(v, 'isoformat') else str(v)


def _load(path):
    d = yaml.safe_load(path.read_text())
    if not isinstance(d, dict):
        return {}, []
    return d


def load_all(key):
    """返回 (key, 全部条目, 来源标签)。归档 + 活文件，按日期/原顺序排序。"""
    items = []
    for p in sorted(ARCH_DIR.glob(f'{key}_*.yaml')):
        if 'full' in p.name:
            continue
        d = yaml.safe_load(p.read_text()) or {}
        for it in d.get(key, []) or []:
            items.append((it, f'{p.name}'))
    d = _load(LIVE)
    for it in d.get(key, []) or []:
        items.append((it, 'LIVE'))
    return items


def cmd_recent(argv):
    n = int(argv[0]) if argv else 5
    key = 'decisions'
    if '--key' in argv:
        key = argv[argv.index('--key') + 1]
    items = load_all(key)
    items.sort(key=lambda t: (_date(t[0]), str(t[0].get('ts', ''))))
    out = []
    for it, src in items[-n:]:
        out.append(
            f"[{_date(it)} {it.get('ts', '?')}] code={it.get('code', '?')} "
            f"src={src}\n  topic: {str(it.get('topic', ''))[:200]}\n"
            f"  decision: {str(it.get('decision', ''))[:300]}"
        )
    print('\n'.join(out) if out else '(无记录)')


def cmd_find(argv):
    if not argv:
        print('用法: dlog.py find <keyword>')
        return
    kw = argv[0].lower()
    hits = []
    for key in ('decisions', 'records'):
        for it, src in load_all(key):
            blob = yaml.dump(it, allow_unicode=True).lower()
            if kw in blob:
                hits.append((_date(it), key, src, it))
    hits.sort(key=lambda t: (t[0], t[1], t[2]))
    print(f'命中 {len(hits)} 条:')
    for d, key, src, it in hits:
        an = str(it.get('analysis', ''))[:PREVIEW].replace('\n', ' ')
        print(f"  {d} [{key}/{src}] code={it.get('code', '?')} {str(it.get('topic', ''))[:120]}")
        if an:
            print(f"      ...{an}...")


def cmd_month(argv):
    m = argv[0] if argv else ''
    found = False
    for key in ('records', 'decisions'):
        p = ARCH_DIR / f'{key}_{m}.yaml'
        if p.exists():
            d = yaml.safe_load(p.read_text()) or {}
            found = True
            print(f'=== {p.name} ({len(d.get(key, []))} 条) ===')
            for it in d.get(key, []):
                print(f"  {_date(it)} {it.get('ts', '?')} code={it.get('code', '?')} "
                      f"{str(it.get('topic', ''))[:120]}")
    if not found:
        # 落在活文件窗口内的月份
        for key in ('records', 'decisions'):
            for it, src in load_all(key):
                if _date(it)[:7] == m:
                    found = True
                    print(f"  [LIVE] {_date(it)} {it.get('ts', '?')} code={it.get('code', '?')} "
                          f"{str(it.get('topic', ''))[:120]}")
    if not found:
        print(f'(归档无 {m} 的条目)')


def cmd_stats(argv):
    print('=== 活文件 ===')
    print(f'  {LIVE}  {LIVE.stat().st_size} bytes')
    d = _load(LIVE)
    print(f"  records={len(d.get('records', []) or [])}  decisions={len(d.get('decisions', []) or [])}")
    print('\n=== 归档 ===')
    tot_r = tot_d = 0
    for p in sorted(ARCH_DIR.glob('*.yaml')):
        if 'full' in p.name:
            continue
        dd = yaml.safe_load(p.read_text()) or {}
        k = list(dd.keys())[0]
        n = len(dd.get(k, []) or [])
        tot_r += n if k == 'records' else 0
        tot_d += n if k == 'decisions' else 0
        print(f'  {p.name:<38} {k:<9} {n:>3} 条 {p.stat().st_size:>7} bytes')
    print(f'\n  归档合计 records={tot_r} decisions={tot_d}')
    print(f'  总计 {tot_r + tot_d + len(d.get("records", []) or []) + len(d.get("decisions", []) or [])} 条')


def cmd_full(argv):
    if not argv:
        print('用法: dlog.py full --code <code> [--date YYYY-MM-DD] [--limit N]')
        return
    code = argv[argv.index('--code') + 1] if '--code' in argv else None
    date = argv[argv.index('--date') + 1] if '--date' in argv else None
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else 3
    hits = []
    for key in ('decisions', 'records'):
        for it, src in load_all(key):
            if code and str(it.get('code')) != code:
                continue
            if date and _date(it) != date:
                continue
            hits.append((_date(it), key, src, it))
    hits.sort()
    for d, key, src, it in hits[-limit:]:
        print(f'=== {d} [{key}/{src}] code={it.get("code")} ===')
        print(yaml.dump(it, allow_unicode=True, sort_keys=False, width=100))


CMDS = {
    'recent': cmd_recent,
    'find': cmd_find,
    'month': cmd_month,
    'stats': cmd_stats,
    'full': cmd_full,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        print('可用命令: ' + ', '.join(CMDS))
        sys.exit(1)
    CMDS[sys.argv[1]](sys.argv[2:])
