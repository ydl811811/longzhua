#!/usr/bin/env python3
"""skill_refs_sync.py — 跨技能 references 副本漂移巡检

背景：Hermes skill_view 有路径沙箱，跨技能绝对路径被拒（"Path escapes allowed directory"），
所以「公共目录 + 绝对路径引用」走不通；跨技能复用只能靠**副本**。副本的唯一风险是漂移
（两边改了不一致）。本脚本用 md5 检测漂移，输出漂移组供修复。

用法：
  python3 ~/.hermes/scripts/skill_refs_sync.py            # 报告模式（默认，退出码 0/1）
  python3 ~/.hermes/scripts/skill_refs_sync.py --fix      # 用 canonical 副本覆盖其余副本
  python3 ~/.hermes/scripts/skill_refs_sync.py --json      # 机器可读

副本头部约定（可选但推荐）：
  > canonical: <skill-dir>/references/<file>.md
canonical 显式标注时优先它；否则取 mtime 最旧的当正本。
"""
import argparse
import collections
import hashlib
import json
import os
import sys
import time

SKILLS_ROOT = os.environ.get("HERMES_SKILLS", os.path.expanduser("~/.hermes/skills"))
SKIP_PARTS = {".archive", "venv", "node_modules", "__pycache__"}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hint(path):
    """读文件头 5 行找 `canonical: <skill>/references/<file>`。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 6:
                    break
                if "canonical:" in line:
                    return line.split("canonical:", 1)[1].strip().strip("`")
    except OSError:
        pass
    return None


def collect():
    """返回 {relpath: {"path","skill","mtime","md5"}}"""
    out = {}
    for root, dirs, files in os.walk(SKILLS_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_PARTS]
        if "/.archive" in root:
            continue
        for name in files:
            if not name.endswith(".md"):
                continue
            p = os.path.join(root, name)
            if "/references/" not in p.replace(os.sep, "/"):
                continue
            skill = p.split(os.sep)[3] if os.path.abspath(SKILLS_ROOT).count(os.sep) == 2 else None
            # 取相对 SKILLS_ROOT 的第一段作为 skill 名
            rel = os.path.relpath(p, SKILLS_ROOT)
            skill = rel.split(os.sep)[0]
            try:
                out[rel] = {
                    "path": p,
                    "skill": skill,
                    "mtime": os.path.getmtime(p),
                    "md5": md5(p),
                }
            except OSError:
                pass
    return out


def group_cross_skill(bybase):
    """按 basename 分组，只保留跨技能（skill 集合 >1）的组。"""
    groups = []
    for bn, entries in bybase.items():
        skills = {e["skill"] for e in entries}
        if len(skills) >= 2:
            groups.append((bn, sorted(entries, key=lambda e: e["mtime"])))
    return groups


def pick_canonical(entries):
    """优先显式 canonical 标注；否则 mtime 最旧。返回 entry。"""
    for e in entries:
        hint = canonical_hint(e["path"])
        if hint:
            hint = hint.replace("\\", "/")
            for c in entries:
                rel = os.path.relpath(c["path"], SKILLS_ROOT).replace(os.sep, "/")
                if rel == hint or rel.endswith("/" + hint.split("/")[-1]) and c["skill"] in hint:
                    return c
    return entries[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    files = collect()
    bybase = collections.defaultdict(list)
    for rel, info in files.items():
        bybase[os.path.basename(rel)].append(info)
    groups = group_cross_skill(bybase)

    drift = []
    clean = 0
    total_copies = 0
    for bn, entries in groups:
        total_copies += len(entries)
        md5s = {e["md5"] for e in entries}
        if len(md5s) == 1:
            clean += 1
            continue
        canon = pick_canonical(entries)
        drift.append({
            "basename": bn,
            "canonical": os.path.relpath(canon["path"], SKILLS_ROOT),
            "copies": [
                {
                    "path": os.path.relpath(e["path"], SKILLS_ROOT),
                    "skill": e["skill"],
                    "md5": e["md5"],
                    "mtime": time.strftime("%Y-%m-%d %H:%M", time.localtime(e["mtime"])),
                    "differs": e["md5"] != canon["md5"],
                }
                for e in entries
            ],
        })

    if args.fix:
        n = 0
        for g in drift:
            src = os.path.join(SKILLS_ROOT, g["canonical"])
            for c in g["copies"]:
                if not c["differs"]:
                    continue
                dst = os.path.join(SKILLS_ROOT, c["path"])
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(src, "rb") as f, open(dst, "wb") as o:
                    o.write(f.read())
                n += 1
        if not args.json:
            print(f"已用 canonical 覆盖 {n} 个漂移副本")

    result = {
        "skills_root": SKILLS_ROOT,
        "cross_skill_duplicate_groups": len(groups),
        "in_sync_groups": clean,
        "drifted_groups": len(drift),
        "total_copies_in_cross_skill_groups": total_copies,
        "drift": drift,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"skills_root: {SKILLS_ROOT}")
        print(f"跨技能重复组: {len(groups)}  内容一致: {clean}  漂移: {len(drift)}")
        print(f"重复组内副本总数: {total_copies}")
        if drift:
            print("\n漂移组：")
            for g in drift:
                print(f"\n[{g['basename']}] 正本 = {g['canonical']}")
                for c in g["copies"]:
                    mark = "OK " if not c["differs"] else "≠ "
                    print(f"  {mark}{c['mtime']}  {c['skill']}/{c['path'].split('/')[-1]}  md5={c['md5'][:8]}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())