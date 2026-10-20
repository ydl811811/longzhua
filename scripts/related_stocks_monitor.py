#!/usr/bin/env python3.12
"""
related_stocks_monitor.py - 关联股票观察池监控器

每日盘后自动检查 5 只 ETF 持仓的关联股票异动：
1. 涨跌幅 > ±5% → 触发
2. 在北向 TOP10/15 → 触发
3. 龙虎榜上榜且净买入 > 0 → 触发

输出 trigger 报告 → 给老大做 ETF 持仓决策参考

用法：
    /home/yu/.hermes/skills/a-stock-data-venv/bin/python \\
        /home/yu/.hermes/scripts/related_stocks_monitor.py \\
        --date 20260810
"""
from __future__ import annotations
import sys
import os
import json
import argparse
import time
from datetime import datetime
from pathlib import Path
import yaml

sys.path.insert(0, os.path.expanduser("~/.hermes/skills/a-stock-data/astock-fund/scripts"))
sys.path.insert(0, os.path.expanduser("~/.hermes/scripts"))
from tushare_xianyu import call_with_failover

POOL_FILE = Path.home() / ".hermes/stock-portfolio/related_stocks_pool.yaml"


def load_pool():
    if not POOL_FILE.exists():
        raise FileNotFoundError(f"观察池不存在: {POOL_FILE}")
    with open(POOL_FILE) as f:
        return yaml.safe_load(f)


def get_stock_quote(code: str) -> dict:
    """拉单只股票实时行情（沪深）"""
    if code.startswith(('6', '9')):
        full_code = f"sh{code}"
    else:
        full_code = f"sz{code}"
    try:
        r = call_with_failover('daily', {'ts_code': f'{code}.{"SH" if code.startswith("6") else "SZ"}', 'start_date': '20260807', 'end_date': '20260810'})
        # 直接用 tencent qt.gtimg.cn（更快）
        import requests
        url = f"http://qt.gtimg.cn/q={full_code}"
        r = requests.get(url, timeout=5)
        text = r.content.decode('gbk', errors='ignore')
        # 解析：v_sh601138="100...."
        if '="' in text:
            data = text.split('="')[1].strip('";\n').split('~')
            return {
                'code': code,
                'name': data[1] if len(data) > 1 else '',
                'price': float(data[3]) if len(data) > 3 and data[3] else 0,
                'pct_change': float(data[32]) if len(data) > 32 and data[32] else 0,
                'volume': data[6] if len(data) > 6 else '',
            }
    except Exception as e:
        pass
    return {'code': code, 'price': 0, 'pct_change': 0}


def get_top_list(trade_date: str) -> list:
    """龙虎榜每日"""
    r = call_with_failover('top_list', {'trade_date': trade_date})
    if r.get('code') == 0:
        items = r.get('data', {}).get('items', [])
        fields = r.get('data', {}).get('fields', [])
        return [dict(zip(fields, i)) for i in items]
    return []


def get_hsgt_top(trade_date: str) -> list:
    """北向 TOP10"""
    r = call_with_failover('hsgt_top10', {'trade_date': trade_date})
    if r.get('code') == 0:
        items = r.get('data', {}).get('items', [])
        fields = r.get('data', {}).get('fields', [])
        return [dict(zip(fields, i)) for i in items]
    return []


HK_ALIAS = {
    'BABA': 'hk09988', 'JD': 'hk09618', 'PDD': 'hk09888', 'NTES': 'hk09999',
    'BIDU': 'hk09888', 'NIO': 'hk09866', 'XPEV': 'hk09868',
}


def to_market_code(code) -> str:
    """观察池 code -> 腾讯行情 market code"""
    s = str(code).strip().upper()
    if s in HK_ALIAS:
        return HK_ALIAS[s]
    if s.isdigit():
        if len(s) == 5:
            return 'hk' + s
        if len(s) == 6:
            return ('sh' if s[0] in '56' else 'sz') + s
    return ''


def get_quotes(market_codes: list) -> dict:
    """qt.gtimg.cn 批量行情（直连，不依赖 tushare 代理），单批最多 50 code"""
    result = {}
    codes = [x for x in market_codes if x]
    for i in range(0, len(codes), 50):
        batch = codes[i:i + 50]
        try:
            import requests
            r = requests.get('http://qt.gtimg.cn/q=' + ','.join(batch), timeout=15)
            text = r.content.decode('gbk', errors='ignore')
        except Exception as e:
            print(f'  [WARN] 行情源 qt.gtimg.cn 拉取失败: {type(e).__name__}: {e}')
            continue
        for line in text.strip().split('\n'):
            if '="' not in line:
                continue
            key = line.split('="')[0].replace('v_', '')
            parts = line.split('="')[1].strip('";').split('~')
            if len(parts) > 32:
                try:
                    result[key] = {
                        'name': parts[1],
                        'price': float(parts[3]),
                        'pct_change': float(parts[32]),
                    }
                except ValueError:
                    pass
        time.sleep(0.3)
    return result


def check_signals(trade_date: str):
    """检查所有关联股票信号（信号1 涨跌幅走 qt.gtimg.cn 直连 + 信号2/3 走 tushare）"""
    pool = load_pool()
    triggers = []

    # 信号 1：当日涨跌幅（直连行情源，主信号，2026-10-20 启用）
    all_mc = []
    for h in pool['holdings']:
        for s in h['related_stocks']:
            mc = to_market_code(s['code'])
            if mc:
                all_mc.append(mc)
    all_mc = sorted(set(all_mc))
    quotes = get_quotes(all_mc)
    missing = sorted(set(all_mc) - set(quotes.keys()))
    print(f"  行情源 qt.gtimg.cn: 拉到 {len(quotes)}/{len(all_mc)} 只")
    if missing:
        print(f"  [WARN] 行情缺失 {len(missing)} 只: {missing}")

    # 信号 2/3：北向 TOP10 + 龙虎榜（依赖 tushare 闲鱼代理，可能整体失效）
    top_list = get_top_list(trade_date)
    time.sleep(2)
    hsgt_top = get_hsgt_top(trade_date)
    time.sleep(2)

    source_status = {
        'qtimg_quote': 'ok' if quotes else 'fail',
        'tushare_top_list': 'ok' if top_list else 'unavailable',
        'tushare_hsgt_top10': 'ok' if hsgt_top else 'unavailable',
    }
    degraded = [k for k, v in source_status.items() if v == 'unavailable']
    if degraded:
        print(f"  [WARN] tushare 代理不可用 -> {degraded} 本次未评估（这是盲区，不是'无信号'）")

    # 索引化
    dragon_dict = {i.get('name', ''): i for i in top_list}
    hsgt_names = set(i.get('name', '') for i in hsgt_top)

    # 每只 ETF
    for holding in pool['holdings']:
        etf_code = holding['etf_code']
        etf_name = holding['etf_name']
        threshold = holding['signal_threshold']

        triggered_stocks = []

        for stock in holding['related_stocks']:
            stock_code = stock['code']
            stock_name = stock['name']
            signals = []

            # 信号 1：当日涨跌幅超阈值（涨/跌双向）
            q = quotes.get(to_market_code(stock_code))
            if q and abs(q['pct_change']) >= threshold['pct_change']:
                signals.append(f"涨跌幅 {q['pct_change']:+.2f}% (收 {q['price']})")

            # 信号 2：在北向 TOP10
            if threshold['north_top'] and stock_name in hsgt_names:
                signals.append('北向 TOP 净买入')

            # 信号 3：龙虎榜上榜且净买入
            if stock_name in dragon_dict:
                dragon_item = dragon_dict[stock_name]
                net_amount = dragon_item.get('net_amount', 0)
                try:
                    net_amount = float(net_amount) if net_amount else 0
                except (ValueError, TypeError):
                    net_amount = 0
                if net_amount > threshold['dragon_net_buy'] * 1e8:
                    signals.append(f'龙虎榜净买入 {net_amount/1e8:.2f} 亿')

            if signals:
                triggered_stocks.append({
                    'code': stock_code,
                    'name': stock_name,
                    'signal_types': signals,
                })

        if triggered_stocks:
            neg = any('跌' in s for st in triggered_stocks for s in st['signal_types'])
            triggers.append({
                'etf_code': etf_code,
                'etf_name': etf_name,
                'triggered_stocks': triggered_stocks,
                'suggested_action': '评估ETF持仓：减仓/加仓/不动',
                'direction_hint': '关联股走弱 -> 优先复核ETF均线与止损' if neg else '关联股走强 -> 偏正面信号',
                'notify': True,
            })

    return triggers, source_status, missing


def main():
    ap = argparse.ArgumentParser(description="关联股票观察池监控")
    ap.add_argument("--date", help="交易日期 YYYYMMDD（默认今天）")
    args = ap.parse_args()

    trade_date = args.date or datetime.now().strftime("%Y%m%d")

    print(f"=== 关联股票观察池监控 ({trade_date}) ===\n")

    triggers, source_status, missing = check_signals(trade_date)
    data_note = ', '.join(f"{k}={v}" for k, v in source_status.items())

    if not triggers:
        if all(v == 'ok' for v in source_status.values()):
            print("✅ 无触发信号（关联股票全部平静）")
            print("\n策略：维持当前 ETF 持仓方案")
        else:
            print("⚠️ 无触发信号，但数据源不完整 -> 本次结论不完整，不可视为'全部平静'")
            print(f"   数据源: {data_note}")
        return

    # 输出触发报告
    print(f"🚨 共 {len(triggers)} 只 ETF 触发信号\n")
    for t in triggers:
        print(f"### {t['etf_code']} {t['etf_name']} ###")
        for s in t['triggered_stocks']:
            print(f"  - {s['name']} ({s['code']}): {' / '.join(s['signal_types'])}")
        print(f"  建议: {t['suggested_action']}")
        print()

    # 保存 trigger log
    log_file = Path.home() / ".hermes/stock-portfolio/related_stocks_trigger_log.yaml"
    history = []
    if log_file.exists():
        with open(log_file) as f:
            history = yaml.safe_load(f) or []
    history.append({
        'date': trade_date,
        'ts': datetime.now().isoformat(),
        'triggers': triggers,
        'data_source_status': source_status,
        'data_source_note': data_note,
    })
    with open(log_file, 'w') as f:
        yaml.dump(history, f, default_flow_style=False, allow_unicode=True)
    print(f"\n📝 触发记录已保存到 {log_file}")


if __name__ == "__main__":
    main()