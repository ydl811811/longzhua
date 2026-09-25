#!/usr/bin/python3.12
"""
集合竞价监控脚本 — 优先关注持仓股
每个交易日的 9:25 执行
数据源：monitor_positions.yaml (真实持仓) + portfolio.yaml (候选股)
"""

import urllib.request
import re
import os
import sys
from datetime import datetime

# ===================== 配置 =====================
MONITOR_FILE = '/home/yu/.hermes/stock-portfolio/monitor_positions.yaml'
PORTFOLIO_FILE = '/home/yu/.hermes/stock-portfolio/portfolio.yaml'
OUTPUT_FILE = '/home/yu/.hermes/cron/output/auction_monitor.txt'
# ===================== 配置 =====================

import yaml


def load_targets():
    """
    从 monitor_positions.yaml 读真实持仓（status=holding）
    从 portfolio.yaml 读候选股（watched_stocks + watched_funds）
    返回 (holdings, candidates)
    """
    HOLDINGS = []  # (market_code, name, stop_loss, tp1, tp2)
    CANDIDATES = []  # (market_code, name)

    # ─── 1. 真实持仓（monitor_positions.yaml） ───
    try:
        with open(MONITOR_FILE, 'r') as f:
            doc = yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] 无法读取 {MONITOR_FILE}: {e}", file=sys.stderr)
        doc = {}

    for p in doc.get('positions', []):
        if p.get('status') != 'holding':
            continue
        code = str(p.get('code', ''))
        name = p.get('name', '')
        market = p.get('market', 'sh')
        sl = p.get('stop_loss')
        tp1 = p.get('take_profit_1')
        tp2 = p.get('take_profit_2')
        note = p.get('note', '')
        if code and name:
            prefix = 'sh' if market == 'sh' else 'sz'
            HOLDINGS.append((f'{prefix}{code}', name, sl, tp1, tp2, note))

    # ─── 2. 候选股（portfolio.yaml watched_stocks + watched_funds） ───
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            pf = yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] 无法读取 {PORTFOLIO_FILE}: {e}", file=sys.stderr)
        pf = {}

    # 候选ETF
    for w in pf.get('watched_funds', []):
        code = str(w.get('code', ''))
        name = w.get('name', '')
        market = w.get('market', 'sh')
        if code and name:
            prefix = 'sh' if market == 'sh' else 'sz'
            CANDIDATES.append((f'{prefix}{code}', name))

    # 候选股
    for w in pf.get('watched_stocks', []):
        code = str(w.get('code', ''))
        name = w.get('name', '')
        market = w.get('market', 'sh')
        if code and name:
            prefix = 'sh' if market == 'sh' else 'sz'
            CANDIDATES.append((f'{prefix}{code}', name))

    # 去重：候选不重复，且不包含已在持仓中的
    holding_codes = {h[0] for h in HOLDINGS}
    CANDIDATES = [c for c in CANDIDATES if c[0] not in holding_codes]

    return HOLDINGS, CANDIDATES


def fetch_tencent(codes):
    """腾讯接口批量获取行情"""
    url = f"https://qt.gtimg.cn/q={','.join(codes)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode('gbk', errors='replace')
    except Exception as e:
        return {}

    data = {}
    for line in raw.strip().split('\n'):
        m = re.search(r'v_(\w+)="([^"]+)"', line)
        if not m:
            continue
        code = m.group(1)
        fields = m.group(2).split('~')
        if len(fields) < 40:
            continue

        try:
            name = fields[1]
            pre_close = float(fields[4]) if fields[4] else 0.0
            open_p = float(fields[5]) if fields[5] else 0.0
            vol = int(float(fields[6])) if fields[6] else 0
            chg_pct = float(fields[32]) if fields[32] else 0.0

            def to_int(v):
                try:
                    return int(float(v))
                except:
                    return 0

            buy_total = sum(to_int(fields[i]) for i in range(10, 20))
            sell_total = sum(to_int(fields[i]) for i in range(20, 30))
            waipan_ratio = round(buy_total / sell_total, 2) if sell_total > 0 else 0.0

            # 竞价价 = parts[9]
            auction_px = float(fields[9]) if len(fields) > 9 and fields[9] else None

            data[code] = {
                'name': name,
                'pre_close': pre_close,
                'open': open_p,
                'auction_px': auction_px,
                'chg_pct': chg_pct,
                'vol': vol,
                'vol_wan': round(vol / 10000, 1),
                'buy_total': buy_total,
                'sell_total': sell_total,
                'waipan_ratio': waipan_ratio,
            }
        except Exception:
            continue
    return data


def holding_signal(d, stop_loss, tp1, tp2):
    """
    持仓信号 — 更强调风险和机会
    """
    chg = d['chg_pct']
    ratio = d['waipan_ratio']
    cur_open = d['open']
    pre_close = d['pre_close']

    # 检测是否接近止损
    near_stop = False
    near_tp = False
    if stop_loss and pre_close:
        stop_dist = (cur_open - stop_loss) / stop_loss * 100
        if stop_dist <= 2.0:  # 距止损2%以内
            near_stop = True
    if tp1 and pre_close:
        tp_dist = (tp1 - cur_open) / cur_open * 100
        if tp_dist <= 2.0:  # 距TP1 2%以内
            near_tp = True

    # 信号判断（持仓→偏风险监控）
    if near_stop and ratio < 0.8:
        return '🔴临近止损！卖压重'
    elif near_stop:
        return '🟠接近止损线'
    elif chg <= -2.0 and ratio <= 0.5:
        return '🔴低开卖压重'
    elif chg <= -2.0:
        return '🟠低开'
    elif near_tp and ratio >= 1.2:
        return '🟢接近TP1买盘强'
    elif near_tp:
        return '🟡接近止盈线'
    elif chg >= 2.0 and ratio >= 1.2:
        return '🟢强势高开'
    elif chg >= 1.0 and ratio >= 1.0:
        return '🟡偏强'
    elif ratio <= 0.5 and chg <= -1.0:
        return '🟠卖压偏重'
    else:
        return '⚪正常'


def cand_signal(d):
    """候选股信号 — 偏机会监控"""
    chg = d['chg_pct']
    ratio = d['waipan_ratio']

    if ratio >= 1.5 and chg >= 1.5:
        return '🟢异动拉升'
    if ratio >= 1.2 and chg >= 2.0:
        return '🟢放量突破'
    if ratio >= 1.2 and chg >= 1.0:
        return '🟡偏强'
    if ratio >= 1.0 and chg >= 1.5:
        return '🟡稳量上行'
    if ratio <= 0.5 and chg <= -2.0:
        return '🔴低开异常'
    if ratio <= 0.7:
        return '🟠卖压重'
    return '⚪正常'


def build_report(data, holdings, candidates):
    """生成报告（文本+Markdown混合）"""
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now().strftime('%H:%M:%S')
    lines = []
    lines.append(f"**📊 集合竞价日报 · {today} {now}**")
    lines.append("")

    # ── 1. 持仓优先展示 ──
    lines.append("━━━ **📌 持仓股** ━━━")
    lines.append("")
    lines.append("```")
    lines.append(f"{'股票':<10}{'代码':<12}{'开盘价':>8}{'涨跌%':>8}{'竞价量':>8}{'五档比':>6}  {'信号'}")
    lines.append("-" * 65)

    holding_rows = []
    for mc, name, sl, tp1, tp2, note in holdings:
        d = data.get(mc)
        if not d:
            holding_rows.append(f"{name:<10}{mc:<12}{'--':>8}{'--':>8}{'--':>8}{'--':>6}  ⚠️数据获取失败")
            continue

        sig = holding_signal(d, sl, tp1, tp2)
        chg_str = f"{d['chg_pct']:+.2f}%"
        vol_str = f"{d['vol_wan']:.1f}万"
        ratio_str = f"{d['waipan_ratio']:.2f}"
        open_str = f"{d['open']:.3f}"

        holding_rows.append(
            f"{name:<10}{mc:<12}{open_str:>8}{chg_str:>8}{vol_str:>8}{ratio_str:>6}  {sig}"
        )

    lines.extend(holding_rows)
    lines.append("```")

    # 持仓摘要：止损/止盈距离
    sl_alerts = []
    tp_alerts = []
    for (mc, name, sl, tp1, tp2, note), row in zip(holdings, holding_rows):
        d = data.get(mc)
        if not d or not d.get('open'):
            continue
        cur = d['open']
        if sl and sl > 0:
            sl_dist = (cur - sl) / sl * 100
            if sl_dist <= 3.0:
                sl_alerts.append(f"  {name}: 距止损{sl:.2f}仅{sl_dist:+.1f}% ({cur:.3f})")
        if tp1 and tp1 > 0:
            tp_dist = (tp1 - cur) / cur * 100
            if tp_dist <= 3.0:
                tp_alerts.append(f"  {name}: 距TP1{tp1:.2f}仅{tp_dist:+.1f}% ({cur:.3f})")

    if sl_alerts:
        lines.append("")
        lines.append("⚠️ **止损预警**")
        for a in sl_alerts:
            lines.append(a)
    if tp_alerts:
        lines.append("")
        lines.append("🎯 **接近止盈**")
        for a in tp_alerts:
            lines.append(a)

    # ── 2. 候选股 ──
    if candidates:
        lines.append("")
        lines.append("━━━ **📎 候选股** ━━━")
        lines.append("")
        lines.append("```")
        lines.append(f"{'股票':<10}{'代码':<12}{'开盘价':>8}{'涨跌%':>8}{'竞价量':>8}{'五档比':>6}  {'信号'}")
        lines.append("-" * 65)

        for mc, name in candidates:
            d = data.get(mc)
            if not d:
                lines.append(f"{name:<10}{mc:<12}{'--':>8}{'--':>8}{'--':>8}{'--':>6}  ⚠️数据获取失败")
                continue

            sig = cand_signal(d)
            chg_str = f"{d['chg_pct']:+.2f}%"
            vol_str = f"{d['vol_wan']:.1f}万"
            ratio_str = f"{d['waipan_ratio']:.2f}"
            open_str = f"{d['open']:.3f}"

            lines.append(
                f"{name:<10}{mc:<12}{open_str:>8}{chg_str:>8}{vol_str:>8}{ratio_str:>6}  {sig}"
            )

        lines.append("```")

    # ── 3. 汇总重点 ──
    lines.append("")
    lines.append("━━━ **📈 竞价要点** ━━━")

    # 持仓风险汇总
    hold_danger = []
    hold_good = []
    for mc, name, sl, tp1, tp2, note in holdings:
        d = data.get(mc)
        if not d:
            continue
        sig = holding_signal(d, sl, tp1, tp2)
        if '🔴' in sig:
            hold_danger.append(f"🔴 {name}：{sig}")
        elif '🟢' in sig:
            hold_good.append(f"🟢 {name}：{sig}")
        elif '🟠' in sig:
            hold_danger.append(f"🟠 {name}：{sig}")

    # 候选机会汇总
    cand_ops = []
    for mc, name in candidates:
        d = data.get(mc)
        if not d:
            continue
        sig = cand_signal(d)
        if '🟢' in sig:
            cand_ops.append(f"🟢 {name}：{sig}")
        elif '🟡' in sig:
            cand_ops.append(f"🟡 {name}：{sig}")

    if hold_danger:
        lines.append("⚠️ **需关注的持仓**")
        for a in hold_danger:
            lines.append(f"  {a}")
    else:
        lines.append("✅ **持仓竞价正常，无风险信号**")

    if hold_good:
        lines.append("")
        lines.append("💪 **持仓强势信号**")
        for a in hold_good:
            lines.append(f"  {a}")

    if cand_ops:
        lines.append("")
        lines.append("👀 **候选股机会**")
        for a in cand_ops:
            lines.append(f"  {a}")

    if not hold_danger and not hold_good and not cand_ops:
        lines.append("  （整体竞价平淡，无极端信号）")

    lines.append("")
    lines.append("*竞价量单位：万手 | 五档比=买盘÷卖盘 | >1买方强 <1卖方强*")
    lines.append("*⚠️ 持仓触发 🔴/🟠 信号应优先处理*")

    return '\n'.join(lines)


def main():
    HOLDINGS, CANDIDATES = load_targets()

    # 所有需查询的代码
    all_codes = [h[0] for h in HOLDINGS] + [c[0] for c in CANDIDATES]
    if not all_codes:
        print("⚠️ 无持仓或候选股可监控")
        return

    data = fetch_tencent(all_codes)

    report = build_report(data, HOLDINGS, CANDIDATES)

    # 写文件
    with open(OUTPUT_FILE, 'w') as f:
        f.write(report)

    print(report)


if __name__ == '__main__':
    main()
