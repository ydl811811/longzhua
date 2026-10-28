#!/usr/bin/env python3
"""
A股触底反转信号扫描脚本

用法:
    python3 scripts/reversal_scan.py

观察票列表定义在脚本顶部，可直接修改。

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

# ============================================
# 观察票列表（根据需要修改）
# ============================================
TICKERS = [
    # ("代码", "名称", "备注"),
    ("300444", "双杰电气", "13.10→10.57(-19%) 6/25加入"),
    ("002387", "维信诺", "8.97→7.97(-11%) 6/25加入"),
    ("002452", "长高电气", "~11.70→11.18 7/9暴跌-7.76%"),
    ("300629", "新劲刚", "20.50→18.02(-12%) 6/26加入"),
    ("002876", "三利谱", "34.75→29.38(-15%) 6/25加入"),
    ("300623", "捷捷微电", "41.30→38.45 6/25加入"),
    ("512480", "半导体ETF", "观察型"),
    ("603876", "鼎胜新材", "7/2买入25.70→7/9止损21.41(-16.7%) 等趋势逆转"),
]

def scan_reversal():
    """扫描反转信号"""
    codes = [code for code, _, _ in TICKERS]
    quotes = tencent_quote(codes)
    
    results = []
    
    for (code, name, note), q in zip(TICKERS, quotes):
        if "error" in q:
            print(f"跳过 {code}: {q.get('error')}")
            continue
        
        # 获取K线（拉60日: 需要 MA20 + 60日低点做破位量化, 见 SKILL.md §4.10/§4.11）
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
        
        # 3. 量能（注意单位：腾讯 volume_shou 单位是"手"，新浪K线 volume 单位是"股"，须 ×100 换算）
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

        # 5. 60日新低破位 + 均线位置 (SKILL.md §4.10/§4.11)
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
        
        # 综合判断
        # ⚠️ 关键修正 (2026-10-26): 原规则 (收阳+未创新低) 或 (低点抬高+未创新低) 会把
        #    「深跌中继阴线」误判成初步止跌 —— 因为暴跌日的昨低被打到极低, 今日只要不再破
        #    那个坑就算"低点抬高"。必须追加: 非大阴线 + 收在MA5/MA10之上, 否则一律 DOWN。
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


def print_report(results):
    """打印报告"""
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n# 观察票触底反转扫描报告")
    print(f"**时间: {today_str} 收盘**\n")
    
    # 分类输出
    # ⚠️ 2026-10-28 token 优化：no-agent 模式只推送信号票（REVERSAL+STABILIZING），
    # 下行票（DOWN）只存档不打印。原 prompt 要求"只推送有信号的票，没有的只存档"。
    reversal = [r for r in results if r["verdict"] == "REVERSAL"]
    stabilizing = [r for r in results if r["verdict"] == "STABILIZING"]
    down = [r for r in results if r["verdict"] == "DOWN"]
    
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
    
    # DOWN 票只存档（save_archive 已保存全部），不打印——避免推送噪音
    # 2026-10-28 优化：下行票不推送给老大，只落 archive
    
    print("---\n")
    print("数据来源：腾讯行情 + 新浪K线")
    print("仅供技术分析参考，不构成投资建议")


if __name__ == "__main__":
    results = scan_reversal()
    archive_path = save_archive(results)
    # 2026-10-28 token 优化：无信号票只存档不推送（no-agent 空 stdout = 静默）
    # 有 REVERSAL 或 STABILIZING 信号才打印报告（stdout 非空 → 推送给老大）
    has_signal = any(r["verdict"] in ("REVERSAL", "STABILIZING") for r in results)
    if has_signal:
        print(f"(已存档: {archive_path})")
        print_report(results)
    else:
        # 无信号：不打印（stdout 空 → no-agent 模式静默，不推送）
        pass