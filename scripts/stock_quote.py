#!/usr/bin/python3.12
"""
股票数据 CLI — direct API 封装（替代 adata v2.9.5）

数据源：
  - 腾讯 qt.gtimg.cn：实时行情 + 5 档（盘中首选）
  - 新浪 hq.sinajs.cn：实时行情（集合竞价 prev_close 准）
  - 东方财富 push2.eastmoney.com：批量报价（最快）
  - 新浪 K 线 API：历史 K 线

CLI 用法：
  python3.12 stock_quote.py realtime sh600519 sz000001
  python3.12 stock_quote.py kline sz000536 60
  python3.12 stock_quote.py batch 1.600519,0.000001

Python 用法：
  from stock_quote import tencent_realtime, sina_realtime, eastmoney_batch
  data = tencent_realtime(['sh600519', 'sz000001'])

依赖：仅 Python 3.12+ stdlib（urllib, re, json, argparse）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from typing import Any


# ============== 工具函数 ==============

def safe_int(x) -> int:
    """防 '0.00' / 空字符串导致 int() 崩溃"""
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return 0


def safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except (ValueError, TypeError):
        return default


def http_get(url: str, headers: dict = None, timeout: int = 10) -> bytes:
    """带 UA 的 GET"""
    h = {'User-Agent': 'Mozilla/5.0'}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ============== 腾讯实时行情 + 5 档 ==============

def tencent_realtime(codes: list[str]) -> dict[str, dict]:
    """
    腾讯 qt.gtimg.cn 实时行情。
    codes: ['sh600519', 'sz000001'] 前缀必填
    返回: {code: {name, price, prev_close, open, chg_pct, high, low, vol, 5档bid/ask/ratio}}
    """
    if not codes:
        return {}
    url = 'https://qt.gtimg.cn/q=' + ','.join(codes)
    raw = http_get(url, timeout=8).decode('gbk', errors='replace')

    results = {}
    for line in raw.strip().split('\n'):
        m = re.search(r'v_(\w+)="([^"]+)"', line)
        if not m:
            continue
        code_raw = m.group(1)
        parts = m.group(2).split('~')
        if len(parts) < 40:
            continue

        # 通用字段
        name = parts[1]
        price = safe_float(parts[3])
        prev_close = safe_float(parts[4])
        open_p = safe_float(parts[5])
        vol = safe_int(parts[6])
        chg_pct = safe_float(parts[32])
        high = safe_float(parts[33])
        low = safe_float(parts[34])

        # 5 档：个股/指数 vs ETF 字段不同
        # 个股: parts[9..28] price/vol 交替 (9,11,13,15,17 = 买价; 10,12,14,16,18 = 买量)
        # ETF: parts[36+i*2]=买量, parts[37+i*2]=卖量
        # 自动判断：先看 part[36] 是否能转 float（量是整数）
        # 简单启发：股票代码以 5/15/16/18 开头多为 ETF
        is_etf = code_raw.startswith(('sh5', 'sh15', 'sh16', 'sh18', 'sz15', 'sz16', 'sz18'))

        if is_etf:
            try:
                buy_v = [safe_int(parts[36 + i * 2]) for i in range(5)]
                sell_v = [safe_int(parts[37 + i * 2]) for i in range(5)]
            except (IndexError, ValueError):
                buy_v = sell_v = [0] * 5
        else:
            buy_v = [safe_int(parts[10 + i * 2]) for i in range(5)]
            sell_v = [safe_int(parts[20 + i * 2]) for i in range(5)]

        total_buy = sum(buy_v)
        total_sell = sum(sell_v)
        ratio = round(total_buy / total_sell, 2) if total_sell > 0 else 0

        results[code_raw] = {
            'name': name,
            'price': price,
            'prev_close': prev_close,
            'open': open_p,
            'chg_pct': chg_pct,
            'high': high,
            'low': low,
            'vol': vol,
            'buy_v': buy_v,
            'sell_v': sell_v,
            'total_buy': total_buy,
            'total_sell': total_sell,
            'ratio': ratio,
        }
    return results


# ============== 新浪实时行情（集合竞价阶段更准） ==============

def sina_realtime(codes: list[str]) -> list[dict]:
    """
    新浪 hq.sinajs.cn 实时行情。
    codes: ['sh600519', 'sz000001'] 前缀必填
    返回: list[dict]，每个 dict 含 name/prev_close/now/chg_pct/5档
    ⚠️ 集合竞价阶段 prev_close 最准（parts[2]）
    """
    if not codes:
        return []
    url = f"https://hq.sinajs.cn/list={','.join(codes)}"
    raw = http_get(url, headers={'Referer': 'https://finance.sina.com.cn'}, timeout=8)\
        .decode('gbk', errors='replace')

    results = []
    for line in raw.strip().split('\n'):
        if '=' not in line:
            continue
        content = line.split('=')[1].strip().strip('"').strip(';')
        parts = content.split(',')
        if len(parts) < 30:
            continue
        try:
            name = parts[0]
            open_p = safe_float(parts[1])
            prev_close = safe_float(parts[2])
            now = safe_float(parts[3])
            high = safe_float(parts[4])
            low = safe_float(parts[5])
            vol = safe_int(parts[6])
            chg_pct = round((now - prev_close) / prev_close * 100, 2) if prev_close else 0

            # 新浪 A 股 5 档：parts[10..28] 交替 vol/price
            # parts[10]=买一量, [11]=买一价, ...
            # parts[20]=卖一量, [21]=卖一价, ...
            # ETF 在 parts[9..18]（量在偶数索引 9/10/11/12/13 买，14..18 卖）
            # 这里按 A 股解析（更通用）
            buy_v = [safe_int(parts[10 + i * 2]) for i in range(5)]
            buy_p = [safe_float(parts[11 + i * 2]) for i in range(5)]
            sell_v = [safe_int(parts[20 + i * 2]) for i in range(5)]
            sell_p = [safe_float(parts[21 + i * 2]) for i in range(5)]
            total_buy = sum(buy_v)
            total_sell = sum(sell_v)
            ratio = round(total_buy / total_sell, 2) if total_sell > 0 else 0

            results.append({
                'name': name, 'open': open_p, 'prev_close': prev_close,
                'now': now, 'high': high, 'low': low, 'vol': vol,
                'chg_pct': chg_pct,
                'buy_prices': buy_p, 'buy_vols': buy_v,
                'sell_prices': sell_p, 'sell_vols': sell_v,
                'total_buy': total_buy, 'total_sell': total_sell, 'ratio': ratio,
            })
        except (ValueError, IndexError):
            continue
    return results


# ============== 东方财富批量报价 ==============

def eastmoney_batch(secids: str) -> list[dict]:
    """
    东方财富批量报价（最简最快）。
    secids: '1.600519,0.000001' 市场代码.股票代码
      - 上交所 1. 深交所 0.
    返回: list[dict] {code, name, price, chg_pct}
    """
    url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={secids}&fields=f12,f14,f2,f3,f5,f6,f9"
    raw = http_get(url, timeout=8).decode('utf-8', errors='replace')
    data = json.loads(raw)
    results = []
    for item in data.get('data', {}).get('diff', []):
        results.append({
            'code': item.get('f12'),
            'name': item.get('f14'),
            'price': safe_float(item.get('f2')),
            'chg_pct': safe_float(item.get('f3')),
            'volume': safe_int(item.get('f5')),
            'amount': safe_int(item.get('f6')),
            'turnover_rate': safe_float(item.get('f9')),
        })
    return results


# ============== 新浪历史 K 线 ==============

def sina_kline(prefixed_code: str, days: int = 60) -> list[dict]:
    """
    新浪历史日 K 线。
    prefixed_code: 'sz000536' / 'sh600519'
    返回: list of {day, open, high, low, close, volume}
    volume 单位是股，需 /100/10000 转万手
    """
    url = (
        f'https://quotes.sina.cn/cn/api/jsonp_v2.php/'
        f'var%20_{prefixed_code}_daily='
        f'/CN_MarketDataService.getKLineData'
        f'?symbol={prefixed_code}&scale=240&ma=no&datalen={days}'
    )
    raw = http_get(url, timeout=10).decode('utf-8', errors='replace')
    # 去 JSONP 包装: var xxx = ([...]);
    text = re.sub(r'^/\*.*?\*/\s*var\s+\w+\s*=\s*\(', '', raw, flags=re.DOTALL)
    text = re.sub(r'\);\s*$', '', text)
    return json.loads(text)


# ============== CLI ==============

def _print_realtime(rows: dict | list):
    """
    打印实时报价表格。
    rows: 腾讯返回 dict{code: data}，新浪/东方财富返回 list[data]
    """
    # 统一转 list[(code, data)]
    if isinstance(rows, dict):
        items = list(rows.items())
    else:
        # list 模式下：新浪/东方财富 list，尝试用 codes 顺序 + list 元素
        items = []
        for r in rows:
            code = r.get('code') or r.get('code_raw') or '?'
            items.append((code, r))

    if not items:
        print("（无数据）")
        return
    print(f"{'名称':<12}{'代码':<10}{'现价':>10}{'涨跌幅':>8}{'5档比':>8}  状态")
    print('-' * 60)
    for code, r in items:
        chg = r.get('chg_pct', 0)
        ratio = r.get('ratio', 0)
        icon = '🟢' if chg > 0 else '🔴' if chg < 0 else '⚪'
        ratio_icon = '💪' if ratio > 1.3 else '⚠️' if 0 < ratio < 0.7 else '➖'
        # 中文截断：取 6 字（= 12 显示列）
        name = r.get('name', '?')[:6]
        price = r.get('price', r.get('now', 0))
        # 腾讯 key 是 sh600519，去掉前缀更短
        display_code = code[2:] if code.startswith(('sh', 'sz')) else code
        print(f"{name:<12}{display_code:<10}{price:>10.3f}{chg:>+7.2f}%{ratio:>7.2f}  {icon}{ratio_icon}")


def main():
    parser = argparse.ArgumentParser(description='股票数据 CLI（direct API，替代 adata）')
    sub = parser.add_subparsers(dest='cmd', required=True)

    # realtime: 腾讯 + 5 档
    p_rt = sub.add_parser('realtime', help='腾讯实时行情 + 5 档')
    p_rt.add_argument('codes', nargs='+', help='如 sh600519 sz000001')

    # sina: 新浪（集合竞价准）
    p_sn = sub.add_parser('sina', help='新浪实时（集合竞价 prev_close 准）')
    p_sn.add_argument('codes', nargs='+', help='如 sh600519 sz000001')

    # batch: 东方财富批量
    p_ba = sub.add_parser('batch', help='东方财富批量报价（最快）')
    p_ba.add_argument('secids', help='如 1.600519,0.000001')

    # kline: 新浪历史 K 线
    p_kl = sub.add_parser('kline', help='新浪历史 K 线')
    p_kl.add_argument('code', help='如 sz000536')
    p_kl.add_argument('days', type=int, nargs='?', default=60)

    args = parser.parse_args()

    try:
        if args.cmd == 'realtime':
            data = tencent_realtime(args.codes)
            _print_realtime(data)  # 传 dict，_print_realtime 会用 key 作为 code
        elif args.cmd == 'sina':
            data = sina_realtime(args.codes)
            # 新浪 list 没带 code，从 args.codes 取
            for r, code in zip(data, args.codes):
                r['code'] = code
            _print_realtime(data)
        elif args.cmd == 'batch':
            data = eastmoney_batch(args.secids)
            _print_realtime(data)
        elif args.cmd == 'kline':
            klines = sina_kline(args.code, args.days)
            print(f"{'日期':<12}{'开盘':>8}{'最高':>8}{'最低':>8}{'收盘':>8}{'量(万手)':>10}")
            print('-' * 56)
            for k in klines:
                vol_wan = safe_int(k['volume']) / 100 / 10000
                print(f"{k['day']:<12}{float(k['open']):>8.2f}{float(k['high']):>8.2f}"
                      f"{float(k['low']):>8.2f}{float(k['close']):>8.2f}{vol_wan:>10.0f}")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
