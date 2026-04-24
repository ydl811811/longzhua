#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AData 股票数据获取模块 - 实时数据修复版（价格/涨跌幅校正）

- 实时行情：优先使用腾讯财经 + 东方财富作为数据源
  - 腾讯字段映射按 qt.gtimg.cn 官方/社区文档：
    v_sh600519="1~贵州茅台~600519~当前价~昨收~今开~成交量~外盘~内盘~买一~...~时间~涨跌~涨跌%~最高~最低~价/量/额~..."
    索引：
      3  当前价
      4  昨收价
      5  今开价
      31 涨跌
      32 涨跌%
      33 最高
      34 最低

- 历史数据：仍使用 akshare 的日 K 线接口

供 adata_api_server.py 调用：
- fetch_stock_data_cached (目前仅用于缓存状态，暂不返回全市场全量数据)
- fetch_single_stock
- fetch_historical_data
- get_cache_status
- test_all_sources
"""

import time
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
import requests
import re

try:
    import akshare as ak
except Exception:  # akshare 不可用时，仅禁用历史数据功能
    ak = None

try:
    import tushare as ts
except Exception:
    ts = None

# 配置文件路径（在 yu 的 workspace 下）
ADATA_CONFIG_PATH = Path.home() / ".openclaw" / "workspace" / "adata_config.json"


def _load_tushare_token() -> Optional[str]:
    """优先从环境变量读取，其次从 adata_config.json 读取 tushare_token。"""
    token = os.getenv("TUSHARE_TOKEN")
    if token:
        return token
    try:
        if ADATA_CONFIG_PATH.exists():
            with ADATA_CONFIG_PATH.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            token = cfg.get("tushare_token") or cfg.get("TUSHARE_TOKEN")
            return token
    except Exception:
        pass
    return None

# =====================
# 缓存状态（仅统计用途）
# =====================
_cached_realtime_data = None
_cached_timestamp = 0.0
CACHE_DURATION = 120  # 秒


def _get_market_prefix(code: str) -> str:
    """根据股票代码返回带交易所前缀的代码，如 sh600519 / sz300750"""
    code = code.strip().replace('.', '').lower()
    code = code.replace('sh', '').replace('sz', '').replace('bj', '')

    if code.startswith('6') or code.startswith('688'):
        return f"sh{code}"
    elif code.startswith('0') or code.startswith('3'):
        return f"sz{code}"
    else:
        return f"bj{code}"


def _fetch_from_tencent(code: str) -> Optional[Dict[str, Any]]:
    """从腾讯财经获取实时数据。

    字段映射参考公开文档：
      0  未知/市场标识
      1  名称
      2  代码
      3  当前价格
      4  昨收
      5  今开
      6  成交量（手）
      ...
      31 涨跌
      32 涨跌%
      33  最高
      34  最低
      35  价格/成交量（手）/成交额（元）
      36  成交量（手）
      37  成交额（万）
    """
    symbol = _get_market_prefix(code)
    url = f"https://qt.gtimg.cn/q={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://gu.qq.com/",
    }
    resp = requests.get(url, headers=headers, timeout=5)
    if resp.status_code != 200:
        return None

    m = re.search(r'="([^"\n]+)"', resp.text)
    if not m:
        return None
    parts = m.group(1).split("~")
    if len(parts) < 40:
        return None

    try:
        name = parts[1]
        price = float(parts[3])  # 当前价
        pre_close = float(parts[4])  # 昨收
        open_price = float(parts[5])  # 今开

        # 成交量/成交额
        # 6 和 36 理论上都是成交量（手），用 36 优先，回退 6
        volume = 0
        for idx in (36, 6):
            try:
                volume = int(float(parts[idx]))
                break
            except Exception:
                continue

        # 成交额：37 为“万”，需要乘以 10000
        try:
            amount = float(parts[37]) * 10000.0
        except Exception:
            amount = 0.0

        # 涨跌与涨跌幅、最高、最低
        change = float(parts[31])  # 涨跌
        change_pct = float(parts[32])  # 涨跌%，单位：百分比
        high = float(parts[33])
        low = float(parts[34])

        # 换手率、市值、涨跌停
        try:
            turnover = float(parts[38])  # 换手率（%）
        except Exception:
            turnover = 0.0
        try:
            float_mc = float(parts[44])  # 流通市值（亿元）
        except Exception:
            float_mc = 0.0
        try:
            total_mc = float(parts[45])  # 总市值（亿元）
        except Exception:
            total_mc = 0.0
        try:
            limit_up = float(parts[47])  # 涨停价
        except Exception:
            limit_up = 0.0
        try:
            limit_down = float(parts[48])  # 跌停价
        except Exception:
            limit_down = 0.0
    except Exception:
        return None

    return {
        "code": code,
        "symbol": symbol,
        "name": name,
        "price": price,
        "change": change,
        "change_percent": change_pct,
        "open": open_price,
        "pre_close": pre_close,
        "high": high,
        "low": low,
        "volume": volume,
        "amount": amount,
        "turnover_rate": turnover,
        "float_market_cap": float_mc,
        "market_cap": total_mc,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "tencent",
    }


def _get_market_id(code: str) -> str:
    """东方财富 secid 所需的 market id：沪 1 / 深 0 / 北交所暂按 0 处理"""
    code = code.strip().replace('.', '')
    if code.startswith('6') or code.startswith('688'):
        return "1"  # 沪市
    else:
        return "0"  # 深市 / 其余


def _fetch_from_eastmoney(code: str) -> Optional[Dict[str, Any]]:
    """从东方财富获取实时数据（备用）"""
    market_id = _get_market_id(code)
    secid = f"{market_id}.{code.strip().replace('.', '')}"
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}"
    resp = requests.get(url, timeout=5)
    if resp.status_code != 200:
        return None
    data = resp.json().get("data") or {}
    if not data:
        return None

    try:
        name = data.get("f14", "未知")
        price = (data.get("f43") or 0) / 100
        change = (data.get("f170") or 0) / 100
        change_pct = (data.get("f171") or 0) / 100  # 已经是百分比
        high = (data.get("f44") or 0) / 100
        low = (data.get("f45") or 0) / 100
        open_price = (data.get("f46") or 0) / 100
        volume = data.get("f47") or 0
        amount = data.get("f48") or 0
    except Exception:
        return None

    return {
        "code": code,
        "symbol": secid,
        "name": name,
        "price": price,
        "change": change,
        "change_percent": change_pct,
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,
        "amount": amount,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "eastmoney",
    }


def fetch_stock_data_cached(verbose: bool = True) -> Optional[pd.DataFrame]:
    """获取全部 A 股实时数据（目前用于缓存状态统计，不强行依赖远程接口）。

    现在不再直接依赖 akshare 的全市场接口，避免因为对方网络问题导致整个服务不可用。
    返回 None 时，上层会按缓存为空处理。
    """
    global _cached_realtime_data, _cached_timestamp

    current_time = time.time()
    if _cached_realtime_data is not None and current_time - _cached_timestamp < CACHE_DURATION:
        if verbose:
            print(f"📦 使用缓存数据（年龄: {int(current_time - _cached_timestamp)}秒)")
        return _cached_realtime_data

    if verbose:
        print("⚠️ 暂不从远程拉取全市场实时数据，仅维护缓存状态")

    _cached_realtime_data = None
    _cached_timestamp = 0.0
    return None


def fetch_single_stock(code: str, verbose: bool = False) -> Optional[Dict[str, Any]]:
    """获取单只股票实时数据。

    优先腾讯财经，其次东方财富，最后返回 None。
    """
    if verbose:
        print(f"🔍 获取单股实时数据: {code}")

    # 1) 腾讯财经
    try:
        data = _fetch_from_tencent(code)
        if data is not None:
            if verbose:
                print("✅ 腾讯财经数据获取成功")
            return data
    except Exception as e:
        if verbose:
            print(f"❌ 腾讯财经数据获取失败: {e}")

    # 2) 东方财富备用
    try:
        data = _fetch_from_eastmoney(code)
        if data is not None:
            if verbose:
                print("✅ 东方财富数据获取成功")
            return data
    except Exception as e:
        if verbose:
            print(f"❌ 东方财富数据获取失败: {e}")

    if verbose:
        print("⚠️ 所有实时数据源均失败")
    return None


def _normalize_ts_code(stock_code: str) -> str:
    """将 600519 / sh600519 / 600519.SH 统一成 Tushare ts_code 格式。"""
    code = stock_code.strip().upper().replace(".", "")
    code = code.replace("SH", "").replace("SZ", "").replace("BJ", "")
    if code.startswith("6") or code.startswith("688"):
        return f"{code}.SH"
    elif code.startswith("0") or code.startswith("3"):
        return f"{code}.SZ"
    else:
        return f"{code}.BJ"


def fetch_historical_data(
    stock_code: str,
    start_date: str = "20240101",
    end_date: str = None,
    k_type: int = 1,
) -> Optional[pd.DataFrame]:
    """获取历史 K 线数据。

    - 优先使用 Tushare Pro（日线/周线/月线，前复权）
    - 失败或未配置时回退到 akshare（日/周/月，前复权）

    k_type 含义约定：
      1 = 日线
      2 = 周线
      3 = 月线
    """
    if end_date is None:
        end_date = pd.Timestamp.now().strftime("%Y%m%d")

    # ---------- 优先使用 Tushare Pro（前复权） ----------
    token = _load_tushare_token()
    if token and ts is not None:
        try:
            ts.set_token(token)
            pro = ts.pro_api()
            ts_code = _normalize_ts_code(stock_code)

            # 选择周期接口
            adj = "qfq"  # 前复权
            if k_type == 2:
                fetch_fn = pro.weekly
            elif k_type == 3:
                fetch_fn = pro.monthly
            else:
                fetch_fn = pro.daily

            df = fetch_fn(ts_code=ts_code, start_date=start_date, end_date=end_date, adj=adj)
            if df is not None and not df.empty:
                # 排序 + 字段规范
                date_col = "trade_date" if "trade_date" in df.columns else "trade_date"
                df = df.sort_values(date_col)
                df["date"] = pd.to_datetime(df[date_col])
                df = df.rename(
                    columns={
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "vol": "volume",
                        "amount": "amount",
                        "pct_chg": "pct_chg",
                        "change": "change",
                        "turnover_rate": "turnover",
                    }
                )
                cols = [
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "amount",
                    "pct_chg",
                    "change",
                    "turnover",
                ]
                existing = [c for c in cols if c in df.columns]
                print(f"✅ Tushare 获取历史数据成功: {ts_code}, {len(df)} 条, k_type={k_type}")
                return df[existing]
        except Exception as e:
            print(f"⚠️ Tushare 获取历史数据失败，将回退到 akshare: {e}")

    # ---------- 回退到 akshare ----------
    if ak is None:
        print("❌ akshare 未安装，无法获取历史数据")
        return None

    # akshare 需要带市场前缀
    clean_code = stock_code.replace("sh", "").replace("sz", "").replace("bj", "").replace(".", "")
    if clean_code.startswith("6") or clean_code.startswith("688"):
        ak_code = f"sh{clean_code}"
    elif clean_code.startswith("0") or clean_code.startswith("3"):
        ak_code = f"sz{clean_code}"
    else:
        ak_code = f"bj{clean_code}"

    def fmt(date_str: str) -> str:
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    ak_start = fmt(start_date)
    ak_end = fmt(end_date)

    print(f"📅 使用 akshare 获取 {ak_code} 历史数据 ({ak_start} 到 {ak_end})")
    try:
        df = ak.stock_zh_a_hist(symbol=ak_code, period="daily", start_date=ak_start, end_date=ak_end, adjust="")
        if df is None or df.empty:
            print("⚠️ 历史数据返回为空")
            return None

        print(f"✅ akshare 获取成功，{len(df)} 条历史数据")
        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "pct_chg",
                "涨跌额": "change",
                "换手率": "turnover",
            }
        )
        return df
    except Exception as e:
        print(f"❌ 获取历史数据异常: {e}")
        return None


def get_cache_status() -> dict:
    """获取缓存状态"""
    global _cached_realtime_data, _cached_timestamp
    current_time = time.time()

    if _cached_realtime_data is None:
        return {"status": "empty", "age": None, "count": 0, "ttl": CACHE_DURATION}

    age = current_time - _cached_timestamp
    return {
        "status": "valid" if age < CACHE_DURATION else "expired",
        "age": age,
        "count": len(_cached_realtime_data),
        "ttl": CACHE_DURATION,
    }


def test_all_sources() -> dict:
    """测试实时数据源可用性。

    逻辑：用几只代表性股票测试 fetch_single_stock，只要有一只成功就认为整体可用。
    """
    test_codes = ["600519", "300750", "000001"]
    success = 0
    for code in test_codes:
        data = fetch_single_stock(code, verbose=True)
        if data is not None:
            success += 1

    status = "success" if success > 0 else "error"
    return {
        "status": status,
        "tested_codes": test_codes,
        "success_count": success,
        "cache_status": get_cache_status(),
        "timestamp": time.time(),
    }


def fetch_a50_cfd() -> Optional[Dict[str, Any]]:
    """从新浪财经期货接口获取新华富时A50 CFD实时数据。

    代码：hf_CHA50CFD
    新华富时A50是中国境外上市、以人民币计价、追踪A股市场的重要衍生指标。

    字段映射（逗号分隔）：
      0  当前价格
      1  （空）
      2  卖价
      3  买价
      4  最高
      5  最低
      6  时间 HH:MM:SS
      7  结算价？
      8  昨收？
      9  成交量（手）
      ...
      12 日期 YYYY-MM-DD
      13 名称
      14 未使用
    """
    url = "https://hq.sinajs.cn/list=hf_CHA50CFD"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200:
            return None
        m = re.search(r'="([^"]+)"', resp.text)
        if not m:
            return None
        parts = m.group(1).split(",")
        if len(parts) < 14:
            return None

        try:
            price = float(parts[0]) if parts[0] else 0.0
            sell = float(parts[2]) if parts[2] else 0.0
            buy = float(parts[3]) if parts[3] else 0.0
            high = float(parts[4]) if parts[4] else 0.0
            low = float(parts[5]) if parts[5] else 0.0
            ts_str = parts[6].strip() if len(parts) > 6 else ""
            settlement = float(parts[7]) if parts[7] else 0.0
            pre_close = float(parts[8]) if parts[8] else 0.0
            volume = int(parts[9]) if parts[9].isdigit() else 0
            date_str = parts[12].strip() if len(parts) > 12 else ""
            name = parts[13].strip() if len(parts) > 13 else "新华富时A50"

            change = price - pre_close if pre_close else 0.0
            change_pct = (change / pre_close * 100) if pre_close else 0.0
        except Exception:
            return None

        return {
            "code": "CHA50CFD",
            "symbol": "hf_CHA50CFD",
            "name": name,
            "price": price,
            "sell": sell,
            "buy": buy,
            "change": change,
            "change_percent": change_pct,
            "high": high,
            "low": low,
            "volume": volume,
            "pre_close": pre_close,
            "settlement": settlement,
            "time": ts_str,
            "date": date_str,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "sina_futures",
        }
    except Exception:
        return None
