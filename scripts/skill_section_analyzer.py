#!/usr/bin/env python3
"""列出 SKILL.md 的 H2/H3 章节体积，用于决定拆分方案。
用法: python3 skill_section_analyzer.py <SKILL.md 路径>
"""
import pathlib, sys
p = pathlib.Path(sys.argv[1])
t = p.read_text(encoding='utf-8')
lines = t.split('\n')
marks = [(i, l) for i, l in enumerate(lines) if l.startswith('## ') or l.startswith('### ')]
print(f"FILE {p} total={len(t.encode())} bytes chars={len(t)}")
for k, (i, l) in enumerate(marks):
    end = marks[k+1][0] if k+1 < len(marks) else len(lines)
    sz = sum(len(x.encode())+1 for x in lines[i:end])
    lvl = len(l) - len(l.lstrip('#'))
    print(f"{'  '*(lvl-2)}{sz:>7}B  {l[:100]}")
