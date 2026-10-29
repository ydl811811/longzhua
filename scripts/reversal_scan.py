#!/usr/bin/env python3
"""
A股触底反转信号扫描脚本 — 存量候选池自动刷新版 (2026-10-29 老大拍板方案A)

用法:
    python3 scripts/reversal_scan.py

【2026-10-29 改造】候选池自动刷新 (方案A: 存量池自动刷新):
  1. 不再硬编码 TICKERS —— 改为从 monitor_watched.yaml 读候选池
     (status 为 waiting_reversal / waiting_observe 的条目自动纳入扫描)
  2. 跳过 cleared_* / sold 条目
  3. 扫描结果写回候选池: 每只票的最近信号状态更新到 yaml (last_scan 字段)
  4. 只推送有信号的票 (REVERSAL / STABILIZING), 无信号静默 (no-agent)

数据源:
    - 腾讯 qt.gtimg.cn（实时行情）
    - 新浪 quotes.sina.cn（日K线）
"""

import sys
import os
import json
sys.path.insert(0, "/home/yu/.hermes/skills/a-stock-data/astock-common/scripts")
from common import tencent_quote, fallback_kline

# 存档目录（无信号票也存档，仅推送有信号的）
ARCHIVE_DIR = "/home/yu/公共/观察票扫描"

# 候选池来源
WATCH_FILE = os.path.expanduser("~/.hermes/stock-portfolio/monitor_watched.yaml")

# 只扫描这些 status（cleared_* / sold 跳过）
ACTIVE_STATUSES = ("waiting_reversal", "waiting_observe")


def load_watchlist():
    """从 monitor_watched.yaml 读候选池，返回 [(code, name, note, market)]"""
    try:
        import yaml
        with open(WATCH_FILE) as f:
            d = yaml.safe_load(f)
    except Exception as e:
        print(f"[yaml_err] 读取候选池失败: {e}")
        return []
    out = []
    for p in d.get('watched', []) or []:
        status = str(p.get('status', ''))
        if status not in ACTIVE_STATUSES:
            continue  # cleared_* / sold 跳过
        code = str(p.get('code', ''))
        name = p.get('name', '')
        market = p.get('market', 'sz')
        entry_max = p.get('entry_max', '')
        note = f"候选池 status={status} entry_max={entry_max}"
        out.append((code, name, note, market))
    return out


def scan_reversal(tickers):
    """扫描反转信号。tickers: [(code, name, note, market)]"""
    codes = [t[0] for t in tickers]
    if not codes:
        return []
    quotes = tencent_quote(codes)

    results = []

    for (code, name, note, market), q in zip(tickers, quotes):
        if not isinstance(q, dict) or "error" in q:
            print(f"跳过 {code}: {q.get('error') if isinstance(q, dict) else 'quote_error'}")
            continue

        # 获取K线（拉60日: 需要 MA20 + 60日低点做破位量化）
        klines = fallback_kline(code, days=60)
        if not klines or len(klines) < 5:
            print(f"跳过 {code}: K线数据不足")
            continue

        recent = klines[-10:] if len(klines) >= 10 else klines
        yesterday = recent[-1]
        closes_60 = [k["close"] for k in klines]
        ma20 = sum(closes_60[-20:]) / 20 if len(closes_60) >= 20 else sum(closes_60) / len(closes_60)
        min_low_60d = min(k["low"] for k in klines)
        max_high_60d = max(k["high"] for k in klines)
        pos_60d = ((q["price"] - min_low_60d) / (max_high_60d - min_low_60d) * 100
                   if max_high_60d > min_low_60d else 50)
        vs_ma20 = (q["price"] / ma20 - 1) * 100

        # 今日数据
        today = {
            "open": q["open"],
            "close": q["price"],
            "high": q["high"],
            "low": q["low"],
            "volume": q["volume_shou"],
        }

        # 判定标准
        signals = []

        # 1. 收阳线
        is_yang = today["close"] > today["open"]
        if is_yang:
            signals.append("收阳线")

        # 2. 低点抬高
        low_rising = today["low"] >= yesterday["low"]
        if low_rising:
            signals.append("低点抬高")
        else:
            signals.append("低点降低")

        # 3. 量能（腾讯 volume_shou 单位"手"，新浪K线 volume 单位"股"，须 ×100 换算）
        today_vol_shares = today["volume"] * 100
        avg_vol_5d = sum(k["volume"] for k in recent[-5:]) / 5
        vol_ratio = today_vol_shares / avg_vol_5d if avg_vol_5d > 0 else 1
        if vol_ratio < 0.7:
            signals.append(f"缩量({vol_ratio:.2f}x)")
        elif vol_ratio > 1.3:
            signals.append(f"放量({vol_ratio:.2f}x)")

        # 4. 未创新低
        min_low_10d = min(k["low"] for k in recent)
        no_new_low = today["low"] >= min_low_10d
        if no_new_low:
            signals.append("未创新低")
        else:
            signals.append("创新低")

        # 5. 60日新低破位 + 均线位置
        new_low_60d = today["low"] < min_low_60d
        if new_low_60d:
            signals.append("创60日新低")
        above_ma5 = today["close"] > (sum(closes_60[-5:]) / 5)
        above_ma10 = today["close"] > (sum(closes_60[-10:]) / 10)
        if above_ma5:
            signals.append("站上MA5")
        if above_ma10:
            signals.append("站上MA10")

        # 价格位置
        closes = [k["close"] for k in recent]
        min_close = min(closes)
        max_close = max(closes)
        range_pos = (today["close"] - min_close) / (max_close - min_close) * 100 if max_close > min_close else 50

        # 综合判断 (2026-10-26 关键修正: 防深跌中继阴线误判)
        body_pct = (today["close"] - today["open"]) / yesterday["close"] * 100
        big_yin = body_pct <= -2.0
        ma_ok = above_ma5 or above_ma10

        if is_yang and low_rising and no_new_low and not new_low_60d:
            verdict = "REVERSAL"
        elif no_new_low and not big_yin and ma_ok and not new_low_60d:
            verdict = "STABILIZING"
        else:
            verdict = "DOWN"

        results.append({
            "code": code,
            "name": name,
            "note": note,
            "market": market,
            "price": today["close"],
            "change_pct": q["change_pct"],
            "open": today["open"],
            "high": today["high"],
            "low": today["low"],
            "volume_wan": round(today["volume"] / 10000, 1),
            "vol_ratio": round(vol_ratio, 2),
            "min_low_10d": min_low_10d,
            "yesterday_low": yesterday["low"],
            "yesterday_close": yesterday["close"],
            "yesterday_date": yesterday["date"],
            "range_pos": round(range_pos, 1),
            "min_low_60d": min_low_60d,
            "max_high_60d": max_high_60d,
            "pos_60d": round(pos_60d, 1),
            "vs_ma20": round(vs_ma20, 2),
            "body_pct": round(body_pct, 2),
            "signals": signals,
            "verdict": verdict,
        })
    return results


def save_archive(results):
    """存档全部扫描结果到 JSON（无信号票也存档）"""
    from datetime import datetime
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    path = f"{ARCHIVE_DIR}/{today_str}_观察票反转扫描.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": today_str, "results": results}, f, ensure_ascii=False, indent=1)
    return path


def write_back_to_watch(results):
    """把扫描结果写回 monitor_watched.yaml（刷新 last_scan 字段 + 信号状态）"""
    from datetime import datetime
    try:
        import yaml
        with open(WATCH_FILE) as f:
            d = yaml.safe_load(f)
    except Exception as e:
        print(f"[yaml_err] 写回候选池失败(读): {e}")
        return
    today_str = datetime.now().strftime("%Y-%m-%d")
    updated = 0
    for r in results:
        code = str(r["code"])
        for p in d.get('watched', []) or []:
            if str(p.get('code', '')) == code:
                p['last_scan'] = {
                    'date': today_str,
                    'price': r['price'],
                    'change_pct': r['change_pct'],
                    'verdict': r['verdict'],
                    'signals': r['signals'],
                    'vs_ma20': r['vs_ma20'],
                    'range_pos': r['range_pos'],
                    'pos_60d': r['pos_60d'],
                    'vol_ratio': r['vol_ratio'],
                }
                updated += 1
                break
    # 只有真的改过才写盘
    if updated:
        with open(WATCH_FILE, 'w', encoding='utf-8') as f:
            yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"[写回] 候选池刷新 {updated}/{len(results)} 只 → {WATCH_FILE}")
    return updated


def print_report(results):
    """打印报告"""
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")

    print(f"\n# 观察票触底反转扫描报告")
    print(f"**时间: {today_str} 收盘**\n")

    # 分类输出 (只推送信号票, DOWN 只存档)
    reversal = [r for r in results if r["verdict"] == "REVERSAL"]
    stabilizing = [r for r in results if r["verdict"] == "STABILIZING"]

    if reversal:
        print(f"## ✅ 触底反转信号票 ({len(reversal)}只)\n")
        for r in reversal:
            print(f"### {r['code']} {r['name']}")
            print(f"- 收盘: {r['price']} ({r['change_pct']:+.2f}%)")
            print(f"- 今日: 开{r['open']} 高{r['high']} 低{r['low']}（vs 昨低{r['yesterday_low']}）")
            print(f"- 近10日最低: {r['min_low_10d']}, 价格位置: {r['range_pos']}%区间")
            print(f"- 特征: {', '.join(r['signals'])}")
            print()

    if stabilizing:
        print(f"## ⚠️ 初步止跌票 ({len(stabilizing)}只)\n")
        for r in stabilizing:
            print(f"- {r['code']} {r['name']}: {r['price']} ({r['change_pct']:+.2f}%)")
            print(f"  特征: {', '.join(r['signals'])}")
            print()

    print("---\n")
    print("数据来源：腾讯行情 + 新浪K线（候选池自动刷新方案A）")
    print("仅供技术分析参考，不构成投资建议")


if __name__ == "__main__":
    tickers = load_watchlist()
    if not tickers:
        print("[warn] 候选池无 active 条目，跳过扫描")
        sys.exit(0)

    results = scan_reversal(tickers)
    archive_path = save_archive(results)
    write_back_to_watch(results)

    # 无信号票只存档不推送（no-agent 空 stdout = 静默）
    has_signal = any(r["verdict"] in ("REVERSAL", "STABILIZING") for r in results)
    if has_signal:
        print(f"(已存档: {archive_path})")
        print_report(results)
    else:
        pass
