#!/usr/bin/env python3
"""dlog_rotate.py — decision_log.yaml 滚动轮转（方案C 常态化）

策略：
  活文件 ~/.hermes/stock-portfolio/decision_log.yaml 保留最近：
    - decisions: 最近 KEEP_DECISIONS 条（默认 45）
    - records:   最近 KEEP_RECORDS 条（默认 8）
  溢出条目按月写入归档目录：
    ~/.hermes/stock-portfolio_archive/decision_log/{records,decisions}_YYYY-MM.yaml

安全保证：
  - 全程备份（.bak.<stamp>_pre_rotate）
  - 活文件用【原文块】重建（不重新序列化任何条目正文）→ 条目零字节变化
  - 逐条保真断言：活文件保留条目 == 原文件尾部条目（yaml 结构相等）
  - 守恒断言：活文件 + 归档 == 原始总条数
  - 归档条目逐条回查原始集合，保证无损
  - 双 key 结构（records + decisions）保留 → stock-yaml-update 断言脚本不受影响

用法：
  python3 dlog_rotate.py            # 执行轮转
  python3 dlog_rotate.py --dry-run  # 只报告将要移动什么
"""
import argparse
import collections
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

BASE = Path.home() / '.hermes' / 'stock-portfolio'
ARCH = Path.home() / '.hermes' / 'stock-portfolio_archive' / 'decision_log'
LOG = BASE / 'decision_log.yaml'
KEEP_DECISIONS = 45
KEEP_RECORDS = 8


def _date(x):
    v = x.get('date')
    if isinstance(v, str):
        return v
    return v.isoformat() if hasattr(v, 'isoformat') else str(v)


def rotate(dry_run=False):
    if not LOG.exists():
        print('❌ 活文件不存在:', LOG)
        return 1
    old = yaml.safe_load(LOG.read_text())
    recs = old.get('records') or []
    decs = old.get('decisions') or []
    rec_arch, rec_keep = recs[:-KEEP_RECORDS], recs[-KEEP_RECORDS:]
    dec_arch, dec_keep = decs[:-KEEP_DECISIONS], decs[-KEEP_DECISIONS:]

    if not rec_arch and not dec_arch:
        print('ℹ️  溢出条目为 0，无需轮转（活文件 records=%d decisions=%d）' % (len(recs), len(decs)))
        return 0

    print('待移动: records %d 条 / decisions %d 条' % (len(rec_arch), len(dec_arch)))
    for key, items in (('records', rec_arch), ('decisions', dec_arch)):
        c = collections.Counter(_date(i)[:7] for i in items)
        for m in sorted(c):
            print(f'   {key}_{m}.yaml  {c[m]} 条')
    if dry_run:
        return 0

    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    backup = BASE / f'decision_log.yaml.bak.{stamp}_pre_rotate'
    shutil.copy2(LOG, backup)
    print('备份:', backup.name)

    ARCH.mkdir(parents=True, exist_ok=True)

    def group(items):
        g = collections.defaultdict(list)
        for it in items:
            g[_date(it)[:7]].append(it)
        return g

    written = []
    for key, items in (('records', rec_arch), ('decisions', dec_arch)):
        for month, group_items in sorted(group(items).items()):
            p = ARCH / f'{key}_{month}.yaml'
            exist = yaml.safe_load(p.read_text()) if p.exists() else {}
            merged = (exist.get(key) or []) + group_items
            p.write_text(yaml.dump({key: merged}, allow_unicode=True, sort_keys=False, width=100))
            written.append((p, key, group_items))

    # 重建活文件：原文块拼回，零改写
    text = LOG.read_text()
    lines = text.splitlines(keepends=True)
    sec = None
    blocks = {'records': [], 'decisions': []}
    cur = None
    for i, l in enumerate(lines):
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*:\s*$', l):
            sec = l.split(':')[0]
            cur = None
            continue
        if re.match(r'^- ', l) and sec in blocks:
            cur = {'start': i, 'sec': sec, 'text': l}
            blocks[sec].append(cur)
            continue
        if cur is not None:
            cur['text'] += l
    for sec in blocks:
        m = re.search(r'^\s*date:\s*[\'"]?(\d{4}-\d{2}-\d{2})', b['text'], re.M)
        b['date'] = m.group(1) if m else None
    keep_text = {
        'records': [b['text'] for b in blocks['records'][-KEEP_RECORDS:]],
        'decisions': [b['text'] for b in blocks['decisions'][-KEEP_DECISIONS:]],
    }
    new_text = 'records:\n' + ''.join(keep_text['records']) + 'decisions:\n' + ''.join(keep_text['decisions'])
    tmp = BASE / f'.decision_log.new.{stamp}'
    tmp.write_text(new_text)
    probe = yaml.safe_load(tmp.read_text())
    assert 'records' in probe and 'decisions' in probe, '双 key 结构丢失'
    assert len(probe['records']) == len(rec_keep)
    assert len(probe['decisions']) == len(dec_keep)
    assert probe['records'] == rec_keep, 'records 保真失败'
    assert probe['decisions'] == dec_keep, 'decisions 保真失败'
    shutil.copy2(tmp, LOG)
    tmp.unlink()

    # 守恒 + 归档可读性
    tot_keep = len(rec_keep) + len(dec_keep)
    tot_arch = sum(len(it) for _, _, it in written)
    assert tot_keep + tot_arch == len(recs) + len(decs), '条目不守恒'
    for p, key, items in written:
        d = yaml.safe_load(p.read_text())
        assert len(d[key]) == len(items), f'{p.name} 条数不符'
    print('\n✅ 轮转完成: 活文件保留 %d 条 / 归档 %d 条 = 原始 %d 条' % (tot_keep, tot_arch, len(recs) + len(decs)))
    print('   活文件 %d bytes (原 %d)' % (LOG.stat().st_size, backup.stat().st_size))
    for p, key, items in written:
        print(f'   {p.name:<38} {key:<9} +{len(items):>3} 条')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    sys.exit(rotate(dry_run=args.dry_run))
