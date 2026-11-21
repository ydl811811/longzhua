#!/usr/bin/env python3
"""通用 SKILL.md 拆分器：把超长章节搬到 references/，主文件留索引。

模式:
  table  —— 章节主体是一个 Markdown 表格，按行分块成多个 references 文件
  h3     —— 章节主体按 H3 小节切块成多个 references 文件

用法:
  python3 split_skill_generic.py <skill_dir> <H2标题正则> <mode> [max_bytes_per_ref] [--dry-run]

安全:
  自动备份 SKILL.md -> SKILL.md.bak.<ts>_pre_split
  保持 frontmatter 不变
  保留章节标题行 + 生成指针区块
"""
import pathlib
import re
import shutil
import sys
import time

SKILL_DIR = pathlib.Path(sys.argv[1])
SEC_RE = re.compile(sys.argv[2])
MODE = sys.argv[3]                      # table | h3
MAXB = int(sys.argv[4]) if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else 14000
DRY = "--dry-run" in sys.argv
PREFIX = sys.argv[5] if len(sys.argv) > 5 and not sys.argv[5].startswith("--") else None
MAIN = SKILL_DIR / "SKILL.md"
REF = SKILL_DIR / "references"

text = MAIN.read_text(encoding="utf-8")
lines = text.split("\n")

# ---- 定位章节：优先 H2，其次 H3 ----
def find_section():
    h2 = [(i, l) for i, l in enumerate(lines) if l.startswith("## ")]
    for k, (i, l) in enumerate(h2):
        if SEC_RE.search(l):
            end = h2[k + 1][0] if k + 1 < len(h2) else len(lines)
            return (i, end, l)
    # 回退：H3 章节（下一个同级或更高级标题结束）
    h3 = [(i, l) for i, l in enumerate(lines) if l.startswith("### ")]
    for k, (i, l) in enumerate(h3):
        if SEC_RE.search(l):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## ") or lines[j].startswith("### "):
                    end = j; break
            return (i, end, l)
    return None

target = find_section()
if not target:
    print("NO_MATCH"); sys.exit(1)
start, end, title = target
body = lines[start:end]
body_bytes = sum(len(x.encode()) + 1 for x in body)
print(f"章节: {title}")
print(f"范围: 行 {start}..{end}  体积 {body_bytes:,} bytes")

raw = re.sub(r"[^0-9a-zA-Z]+", "-", title.replace("## ", "")).strip("-").lower()
slug = raw[:40] or "section"
if PREFIX:
    slug = PREFIX
if len(slug) < 3:   # 纯中文标题 -> ASCII 兜底
    ascii_map = {"必读坑": "pitfalls", "参考文档": "refs", "环境特定知识": "env-knowledge",
                 "关键陷阱": "pitfalls", "参考资料": "refs", "关键陷阱（29 条": "pitfalls",
                 "反模式": "antipatterns", "铁律": "iron-rules", "分类决策表": "decision-table"}
    slug = "sec-" + re.sub(r"[^0-9a-zA-Z]+", "-",
            " ".join(ascii_map.get(w, w) for w in title.split())).strip("-").lower()[:30]
    slug = slug or "section"

if MODE == "table":
    # 找表头行 + 分隔行 + 数据行
    hdr_i = None
    for i, l in enumerate(body):
        if l.startswith("|") and i + 1 < len(body) and re.match(r"^\|[\s:|-]+\|?\s*$", body[i + 1]):
            hdr_i = i; break
    if hdr_i is None:
        print("NO_TABLE"); sys.exit(1)
    pre = body[:hdr_i]                 # 章节标题 + 引言
    header = body[hdr_i:hdr_i + 2]     # 表头 + 分隔行
    rows = [l for l in body[hdr_i + 2:] if l.strip().startswith("|") and l.strip() != "|"]
    other = [l for l in body[hdr_i + 2:] if not (l.strip().startswith("|") and l.strip() != "|")]
    # 主题分类
    def cat(row):
        if re.search(r"PVE|VM |LVM|qm |虚拟|ISO|镜像|磁盘|resize|网卡槽", row): return "pve-vm"
        if re.search(r"mihomo|yaml|代理|Nikki|honk|daed|dns|fakeip|节点|订阅|TPROXY", row): return "proxy-dns"
        if re.search(r"老大|纪律|汇报|反模式|不要|别再|立刻停", row): return "discipline"
        if re.search(r"iperf|吞吐|小包|软路由|带宽|测速|flow_offload", row): return "perf-router"
        return "misc"
    buckets = {}
    order = []
    for r_ in rows:
        c = cat(r_)
        if c not in buckets:
            buckets[c] = []; order.append(c)
        buckets[c].append(r_)
    groups = []
    for c in order:
        rs = buckets[c]
        cur = []; csz = 0
        for r_ in rs:
            b = len(r_.encode()) + 1
            if cur and csz + b > MAXB:
                groups.append((c, cur)); cur = []; csz = 0
            cur.append(r_); csz += b
        if cur: groups.append((c, cur))
    files = []
    for n, (c, rs) in enumerate(groups, 1):
        name = f"{slug}-{c}-{n}.md"
        out = [f"# {title} — {c} ({n}/{len(groups)})", "",
               f"> 由 `split_skill_generic.py` 从 SKILL.md 拆分（{time.strftime('%Y-%m-%d')}）。",
               f"> 读取方式：`skill_view(\"<skill-name>\", file_path='references/{name}'`)。", "",
               *header, ""]
        out.extend(rs)
        files.append((name, c, len(rs), out))
    new_section = list(pre)
    new_section.append("")
    new_section.append(f"> ⚠️ 本章共 {len(rows)} 条坑，已按主题拆分到 `references/`，**按需读取**（避免一次性灌爆上下文）：")
    new_section.append("")
    for name, c, n, _ in files:
        new_section.append(f"- **{c}**（{n} 条）→ `references/{name}`")
    new_section.append("")
    new_section.append("> 需要全文时按上面路径逐个取；只看某一类时直接取对应文件即可。")
    new_section.append("")
    if other:
        new_section.append("> 章节内非表格内容（已保留在主文件）：")
        new_section.extend([l for l in other if l.strip()])
        new_section.append("")
elif MODE == "h3":
    h3_idx = [i for i, l in enumerate(body) if l.startswith("### ")]
    if not h3_idx:
        # 无 H3 子节 -> 按行分块回退
        pre = body[:1]
        content = [l for l in body[1:] if l.strip()]
        groups = []; cur = []; csz = 0
        for l in content:
            b = len(l.encode()) + 1
            if cur and csz + b > MAXB:
                groups.append(cur); cur = []; csz = 0
            cur.append(l); csz += b
        if cur: groups.append(cur)
        files = []
        for n, g in enumerate(groups, 1):
            name = f"{slug}-part{n}.md"
            out = [f"# {title} — 第 {n}/{len(groups)} 部分", "",
                   f"> 由 `split_skill_generic.py` 从 SKILL.md 拆分（{time.strftime('%Y-%m-%d')}）。",
                   f"> 读取方式：`skill_view(\"<skill-name>\", file_path='references/{name}'`)。", ""]
            out.extend(g); out.append("")
            files.append((name, f"part{n}", len(g), out))
        new_section = list(pre)
        new_section.append("")
        new_section.append(f"> ⚠️ 本章内容已拆到 `references/`，**按需读取**：")
        new_section.append("")
        for name, c, n, _ in files:
            new_section.append(f"- **{c}**（{n} 行）→ `references/{name}`")
        new_section.append("")
    else:
        pre = body[:h3_idx[0]]
        blocks = []
        for k, s in enumerate(h3_idx):
            e = h3_idx[k + 1] if k + 1 < len(h3_idx) else len(body)
            blocks.append((body[s], body[s:e]))
        groups = []; cur = []; csz = 0
        for h, b in blocks:
            bs = sum(len(x.encode()) + 1 for x in b)
            if cur and csz + bs > MAXB:
                groups.append(cur); cur = []; csz = 0
            cur.append((h, b)); csz += bs
        if cur: groups.append(cur)
        files = []
        for n, g in enumerate(groups, 1):
            name = f"{slug}-part{n}.md"
            out = [f"# {title} — 第 {n}/{len(groups)} 部分", "",
                   f"> 由 `split_skill_generic.py` 从 SKILL.md 拆分（{time.strftime('%Y-%m-%d')}）。",
                   f"> 读取方式：`skill_view(\"<skill-name>\", file_path='references/{name}'`)。", ""]
            for h, b in g:
                out.append(h); out.append(""); out.extend(b); out.append("")
            files.append((name, f"part{n}", len(g), out))
        new_section = list(pre)
        new_section.append("")
        new_section.append(f"> ⚠️ 本章内容较多，已按块拆分到 `references/`，**按需读取**：")
        new_section.append("")
        for name, c, n, _ in files:
            new_section.append(f"- **{c}**（{n} 个小节）→ `references/{name}`")
        new_section.append("")

elif MODE == "lines":
    # 顺序块切分（散文/自由文本列表），保持原顺序
    pre = body[:1]                      # 保留 H2 标题行
    content = [l for l in body[1:] if l.strip()]
    groups = []; cur = []; csz = 0
    for l in content:
        b = len(l.encode()) + 1
        if cur and csz + b > MAXB:
            groups.append(cur); cur = []; csz = 0
        cur.append(l); csz += b
    if cur: groups.append(cur)
    files = []
    for n, g in enumerate(groups, 1):
        name = f"{slug}-part{n}.md"
        out = [f"# {title} — 第 {n}/{len(groups)} 部分", "",
               f"> 由 `split_skill_generic.py` 从 SKILL.md 拆分（{time.strftime('%Y-%m-%d')}）。",
               f"> 读取方式：`skill_view(\"<skill-name>\", file_path='references/{name}'`)。", ""]
        out.extend(g); out.append("")
        files.append((name, f"part{n}", len(g), out))
    new_section = list(pre)
    new_section.append("")
    new_section.append(f"> ⚠️ 本章内容已拆到 `references/`，**按需读取**：")
    new_section.append("")
    for name, c, n, _ in files:
        new_section.append(f"- **{c}**（{n} 行）→ `references/{name}`")
    new_section.append("")

elif MODE == "bullets":
    # Markdown 列表条目按主题分类切块
    def bcat(l):
        if re.search(r"PVE|VM |LVM|qm |Proxmox|虚拟|ISO", l): return "pve-vm"
        if re.search(r"mihomo|yaml|代理|Nikki|honk|daed|dns|fakeip|节点|订阅|shadowsocks", l): return "proxy-dns"
        if re.search(r"iperf|吞吐|小包|带宽|测速|flow_offload|软路由性能", l): return "perf-bench"
        if re.search(r"NAS|飞牛|fnOS|凭据|密码|credential", l): return "nas-cred"
        return "misc"
    pre = body[:1]                      # 保留 H2 标题行
    items = [l for l in body[1:] if l.strip().startswith(("- ", "* "))]
    other = [l for l in body[1:] if l.strip() and not l.strip().startswith(("- ", "* "))]
    buckets = {}; order = []
    for l in items:
        c = bcat(l)
        if c not in buckets:
            buckets[c] = []; order.append(c)
        buckets[c].append(l)
    groups = []
    for c in order:
        rs = buckets[c]; cur = []; csz = 0
        for l in rs:
            b = len(l.encode()) + 1
            if cur and csz + b > MAXB:
                groups.append((c, cur)); cur = []; csz = 0
            cur.append(l); csz += b
        if cur: groups.append((c, cur))
    files = []
    for n, (c, rs) in enumerate(groups, 1):
        name = f"{slug}-{c}.md"
        out = [f"# {title} — {c}", "",
               f"> 由 `split_skill_generic.py` 从 SKILL.md 拆分（{time.strftime('%Y-%m-%d')}）。",
               f"> 读取方式：`skill_view(\"<skill-name>\", file_path='references/{name}'`)。", ""]
        out.extend(rs)
        files.append((name, c, len(rs), out))
    new_section = list(pre)
    new_section.append("")
    new_section.append(f"> ⚠️ 本章共 {len(items)} 条索引，已按主题拆分到 `references/`，**按需读取**：")
    new_section.append("")
    for name, c, n, _ in files:
        new_section.append(f"- **{c}**（{n} 条）→ `references/{name}`")
    new_section.append("")
    if other:
        new_section.append("> 章节内非列表内容（保留在主文件）：")
        new_section.extend(other)
        new_section.append("")

else:
    print("BAD_MODE"); sys.exit(1)

print()
for name, c, n, out in files:
    print(f"  references/{name:<44} {n:>3} 条")
new_bytes = sum(len(x.encode()) + 1 for x in new_section)
print(f"章节 {body_bytes:,} -> {new_bytes:,} bytes  (-{(body_bytes-new_bytes)/body_bytes*100:.1f}%)")
print(f"主文件 {len(text.encode()):,} -> {len(text.encode())-body_bytes+new_bytes:,} bytes")

if DRY:
    print("[dry-run] 未写入")
    sys.exit(0)

REF.mkdir(parents=True, exist_ok=True)
for name, c, n, out in files:
    (REF / name).write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

bak = MAIN.with_suffix(f".md.bak.{time.strftime('%Y%m%d_%H%M%S')}_pre_split")
shutil.copy2(MAIN, bak)
new_lines = lines[:start] + new_section + lines[end:]
MAIN.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
# frontmatter 校验
chk = MAIN.read_text(encoding="utf-8")
assert chk.startswith("---\n"), "frontmatter 头丢失"
fm = chk.split("---")[1]
assert re.search(r"^name:\s*\S", fm, re.M), "name 丢失"
assert re.search(r"^description:\s*\S", fm, re.M), "description 丢失"
print(f"\n备份: {bak}")
print(f"✅ 主文件 {len(chk.encode()):,} bytes  frontmatter 校验通过")
