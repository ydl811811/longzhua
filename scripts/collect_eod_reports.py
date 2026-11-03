#!/usr/bin/env python3
"""collect_eod_reports.py — 龙爪晚报 21:00 的 9 个数据源一键汇总。

背景（2026-11-04 修 bug）：
    晚报 prompt 原来让 agent 去 `~/.hermes/cron/output/` 下按中文名找 9 个报告
    （`morning_scan.txt` / `持仓策略每日回顾.txt` / `主线识别-周报.txt` ...），
    但实际落盘结构是：
      · 脚本型 (no_agent) 任务 -> `cron/output/<job_id>/<YYYY-MM-DD_HH-MM-SS>.md`
      · agent 型任务          -> `cron/output/<job_id>/<时间戳>.md`（含 Prompt+Response 全文）
                                 或 `reports/<固定名>_YYYYMMDD.md`（净报告）
      · 部分脚本额外写根目录固定名（如 `stock_monitor.txt`）
    中文名 9 个里有 7 个根本不存在，agent 只能反复 ls/glob/tail 去找 —— 每次
    晚报都撞满 90 次迭代上限（max_iterations），这是 token 烧掉的主因。

本脚本按 job_id 精确定位每个源，取当日最新的那一份，一次性输出汇总。
找不到就明确标记「未生成」，绝不编造内容。

用法:
    python3 /home/yu/.hermes/scripts/collect_eod_reports.py
    python3 /home/yu/.hermes/scripts/collect_eod_reports.py --date 2026-11-03
    python3 /home/yu/.hermes/scripts/collect_eod_reports.py --json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime

HOME = os.path.expanduser("~")
OUTPUT_DIR = os.path.join(HOME, ".hermes", "cron", "output")
REPORTS_DIR = os.path.join(HOME, ".hermes", "reports")

# 每个源的精确定位规则（2026-11-04 实测落盘结构）
SOURCES = [
    {
        "key": "stock_monitor",
        "label": "股票监控统一脚本（盘中监控）",
        "job_id": "1c6cd4c32caf",
        "fixed": ["stock_monitor.txt"],
        "desc": "盘中每 5 分钟轮询的监控日志 + 当日快照",
    },
    {
        "key": "morning_scan",
        "label": "早盘市场风向扫描",
        "job_id": "1af1d3ae2ace",
        "desc": "09:00 外盘/政策/情绪扫描 + 台账一致性检查",
    },
    {
        "key": "auction_monitor",
        "label": "集合竞价日报",
        "job_id": "661553374a19",
        "fixed": ["auction_monitor.txt"],
        "desc": "09:25 集合竞价开盘价/涨跌幅/五档比信号",
    },
    {
        "key": "loop_engineer_eod",
        "label": "Loop Engineer 盘后流水线",
        "job_id": "f371f5ab8931",
        "desc": "15:15 持仓快照导出 + 信号记录 + 一致率评分",
    },
    {
        "key": "position_review",
        "label": "持仓策略每日回顾",
        "job_id": "7103c1d9a366",
        "dedicated": "cron/output/7103c1d9a366/strategy_review_{dash}.md",
        "desc": "15:30 持仓体检（止损/TP/浮盈）",
    },
    {
        "key": "related_stocks",
        "label": "关联股票观察池监控",
        "job_id": "28b6353e73e9",
        "desc": "15:35 ETF 关联成分股异动扫描",
    },
    {
        "key": "watched_reversal",
        "label": "观察型候选股收盘检查",
        "job_id": "243c6a7adea4",
        "desc": "15:10 候选池触底反转扫描（触底/止跌/新高）",
    },
    {
        "key": "xuxiaoming",
        "label": "徐小明每日策略视频分析",
        "job_id": "f19221ff1705",
        "dedicated": "reports/xuxiaoming_video_{compact}.md",
        "desc": "19:00 视频解读 → 持仓+候选专属策略",
    },
    {
        "key": "mainline",
        "label": "主线识别",
        "job_id": "ab35f2b2c37e",
        "dedicated": "reports/mainline_weekly_{compact}.md",
        "desc": "17:00 板块强度扫描 → 主线/准主线/候选判定",
    },
]

PER_SOURCE_LIMIT = 5000   # 单源截断上限（字符）
TOTAL_LIMIT = 30000       # 总量上限（字符）


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def _head_tail(text: str, limit: int) -> tuple[str, bool]:
    """头尾各取一半，中间用省略号标记截断。"""
    if len(text) <= limit:
        return text, False
    head = int(limit * 0.7)
    tail = limit - head
    return text[:head] + f"\n\n... [中间 {len(text) - limit} 字符已截断] ...\n\n" + text[-tail:], True


def _pick_dedicated(spec: dict, dash: str, compact: str) -> str | None:
    """取 agent 型任务的净报告文件（比 transcript 干净）。"""
    pattern = spec.get("dedicated")
    if not pattern:
        return None
    rel = pattern.format(dash=dash, compact=compact)
    path = os.path.join(HOME, ".hermes", rel)
    if os.path.isfile(path):
        return path
    # 退一步：同目录下当日任意匹配文件
    stem = os.path.splitext(os.path.basename(rel))[0].split("_")[0]
    cands = sorted(
        (p for p in glob.glob(os.path.join(os.path.dirname(path), f"{stem}_*.md"))
         if dash in os.path.basename(p) or compact in os.path.basename(p)),
        key=os.path.getmtime,
        reverse=True,
    )
    return cands[0] if cands else None


def _pick_subdir(spec: dict, dash: str) -> str | None:
    """取脚本型 / agent 型的当日产物（cron/output/<job_id>/*.md）。

    只接受当日文件 —— 不回退到前一天。否则晚报 21:00 跑的时候，
    当日某源没生成就会静默读到昨天的旧数据（比"未生成"更危险）。
    """
    d = os.path.join(OUTPUT_DIR, spec["job_id"])
    if not os.path.isdir(d):
        return None
    today = [p for p in glob.glob(os.path.join(d, "*.md"))
             if os.path.isfile(p) and dash in os.path.basename(p)]
    if not today:
        return None
    return max(today, key=os.path.getmtime)


def _strip_transcript(text: str) -> str:
    """agent 型任务的产物 .md = '## Prompt' + prompt 全文 + '## Response' + 响应。

    只保留 Response 段（真正的报告内容），丢掉前面几万字符的 prompt 回显 ——
    那部分是输入不是产出，喂给晚报只会白烧 token。
    """
    idx = text.find("## Response")
    if idx >= 0:
        return text[idx + len("## Response"):].lstrip()
    return text


def collect(date_str: str | None = None) -> dict:
    now = datetime.now()
    dash = date_str or now.strftime("%Y-%m-%d")
    compact = dash.replace("-", "")

    results = []
    for spec in SOURCES:
        entry = {
            "key": spec["key"],
            "label": spec["label"],
            "desc": spec["desc"],
            "job_id": spec["job_id"],
            "found": False,
            "path": None,
            "text": "",
            "truncated": False,
            "note": "",
        }

        # 1) agent 型任务的净报告优先
        dedicated = _pick_dedicated(spec, dash, compact)
        if dedicated:
            entry["path"] = dedicated
            entry["found"] = True

        # 2) 否则取 cron/output/<job_id>/ 当日产物
        if not entry["found"]:
            sub = _pick_subdir(spec, dash)
            if sub:
                entry["path"] = sub
                entry["found"] = True

        # 3) 根目录固定名补充（如 stock_monitor.txt）
        #    只在它确实是当日产物时才附加，避免把昨天的快照混进今天的晚报
        if spec.get("fixed"):
            for fname in spec["fixed"]:
                fp = os.path.join(OUTPUT_DIR, fname)
                if not os.path.isfile(fp):
                    continue
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime.strftime("%Y-%m-%d") != dash:
                    continue
                body = _read(fp)
                if not body.strip():
                    continue
                if entry["found"] and entry["path"]:
                    entry["text"] += f"\n\n--- 附：{fname} ---\n{body}"
                else:
                    entry["path"] = fp
                    entry["found"] = True
                    entry["text"] = body

        if entry["found"] and entry["path"]:
            if not entry["text"]:
                raw = _read(entry["path"])
                # dedicated 净报告本身就是内容，不用剥；transcript 才要剥
                if not entry["path"].startswith(os.path.join(HOME, ".hermes", "reports")):
                    raw = _strip_transcript(raw)
                entry["text"] = raw
            entry["text"], entry["truncated"] = _head_tail(entry["text"], PER_SOURCE_LIMIT)
            entry["mtime"] = datetime.fromtimestamp(
                os.path.getmtime(entry["path"])
            ).strftime("%Y-%m-%d %H:%M")
        else:
            entry["note"] = "该报告未生成"

        results.append(entry)

    return {"date": dash, "sources": results}


def render(data: dict) -> str:
    lines = [
        f"# 龙爪晚报 · 当日 9 源数据汇总（{data['date']}）",
        "",
        f"来源：cron/output/<job_id>/ 当日产物 + reports/ 净报告，共 {len(data['sources'])} 个源。",
        "标记「未生成」的源表示该 cron 当日无产物 —— 直接在报告里注明，不要编造内容。",
        "",
    ]
    for s in data["sources"]:
        lines.append("=" * 88)
        if s["found"]:
            lines.append(f"## {s['label']}  [{s['job_id']}]")
            lines.append(f"文件: {s['path']}  (mtime {s.get('mtime', '-')})")
            if s["truncated"]:
                lines.append("注意: 本源内容已截断")
            lines.append("")
            lines.append(s["text"].strip())
        else:
            lines.append(f"## {s['label']}  [{s['job_id']}]")
            lines.append("**状态: 该报告未生成**")
        lines.append("")

    body = "\n".join(lines)
    if len(body) > TOTAL_LIMIT:
        body = body[:TOTAL_LIMIT] + "\n\n[汇总已按总量上限截断]"
    return body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD，默认今天")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    data = collect(args.date)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print(render(data))

    missing = [s["label"] for s in data["sources"] if not s["found"]]
    if missing:
        print(f"\n[摘要] 未生成的源 ({len(missing)}): " + "、".join(missing), file=sys.stderr)
    else:
        print("\n[摘要] 9 个源全部就绪", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
