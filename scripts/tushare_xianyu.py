#!/usr/bin/env python3.12
"""
tushare_xianyu.py - 闲鱼 tushare 15000 积分档客户端 (2026-07-24)

⚠️ 非官方渠道：基于老大闲鱼订单 5125538235575004708，35 元 / 3 个月
服务协议 https://ai-tool.indevs.in/quant/tushare-pro-catalog/

⚠️ 风险（基于 7/23 老大红旗警示）：
- 违反 tushare 服务协议 §2（明文禁止"通过任何非官方或授权途径获得的服务"）
- 可能被官方清理授权 IP，token 失效时无退款
- 7 天观察期（每周检查是否仍可用）

✅ 安全策略：
- 凭证存放在 ~/.hermes/config/xianyu_tushare_credentials.yaml（600 权限）
- 调用使用 requests.Session + X-API-Key header（按文档 Python 模板）
- 本机 fallback：腾讯 qt.gtimg.cn / 新浪 hq.sinajs.cn / 东财 push2.eastmoney.com 仍为首选
- 闲鱼接口仅在用户明确请求时调用

设计：
- call(path, params) → 主调用函数（GET /tushare/pro/<path>?params）
- direct_post(payload) → fastapic 端点（POST json，含 token）
- get_etf_daily(ts_code, start, end) → 5 只持仓快速拉 K 线
- cache_locally(data, key) → 离线落盘到 cache/stock_data/xianyu_tushare/

用法：
    from tushare_xianyu import call, get_etf_daily
    df = call('fund_daily', {'ts_code': '588080.SH', 'start_date': '20260720', 'end_date': '20260724'})
    raw = get_etf_daily('588080.SH', '20260101', '20260724')
"""

import json
import time
import yaml
from pathlib import Path
from typing import Optional
import requests

# ───── 凭证加载 ─────
CRED_FILE = Path.home() / '.hermes/config/xianyu_tushare_credentials.yaml'

def _load_creds():
    if not CRED_FILE.exists():
        raise RuntimeError(f"凭证文件不存在: {CRED_FILE}")
    with open(CRED_FILE) as f:
        return yaml.safe_load(f)


# ───── DNS 修复（2026-08-10）─────
# 教程要求 DNS 解析 104.21.80.1 ai-tool.indevs.in tushare.indevs.in
# 但家里机房 DNS 解析到了错误 IP（198.18.x.x）
# 解决方案：强制 URLConnection 走 104.21.80.1（绕开错误 DNS）
DNS_RESOLVE_IP = '104.21.80.1'

# Monkey-patch urllib3 的 DNS 解析（避免修改 /etc/hosts 需要 sudo 密码）
import socket
_original_getaddrinfo = socket.getaddrinfo
def _patched_getaddrinfo(host, *args, **kwargs):
    if host in ('ai-tool.indevs.in', 'tushare.indevs.in'):
        return _original_getaddrinfo(DNS_RESOLVE_IP, *args, **kwargs)
    return _original_getaddrinfo(host, *args, **kwargs)
socket.getaddrinfo = _patched_getaddrinfo

def _session(key_name=None):
    """按文档示例构建 session（2026-08-10 新增代理 + 多 key 支持）

    Args:
        key_name: 指定 key（None = primary_key）。可选值 'key_1_old' / 'key_2_new'
    """
    creds = _load_creds()
    # 优先用 api_keys（多 key 模式），否则回退到老 api_key
    if 'api_keys' in creds:
        if key_name is None:
            key_name = creds.get('primary_key', list(creds['api_keys'].keys())[0])
        api_key = creds['api_keys'].get(key_name)
        if not api_key:
            raise RuntimeError(f"key '{key_name}' 不存在，可用：{list(creds['api_keys'].keys())}")
    else:
        # 兼容老格式（api_key 单 key）
        api_key = creds['api_key']
    s = requests.Session()
    s.headers.update({"X-API-Key": api_key})
    s.trust_env = False  # 避免环境变量代理污染
    if 'proxy' in creds:
        s.proxies = creds['proxy']
    else:
        s.proxies = {"http": "", "https": ""}
    return s, creds


def call_with_failover(api, params=None, timeout=30):
    """多 key 自动 failover 调用

    主 key 失败时自动尝试备用 key
    """
    creds = _load_creds()
    api_keys = creds.get('api_keys', {creds.get('primary_key', 'single'): creds.get('api_key')})
    primary = creds.get('primary_key', list(api_keys.keys())[0])

    # 主 key 优先
    keys_to_try = [primary] + [k for k in api_keys.keys() if k != primary]

    last_err = None
    for key_name in keys_to_try:
        s, _ = _session(key_name)
        base = creds['super_api_base']
        url = f"{base}{creds['super_api_path_prefix']}/{api}"
        try:
            r = s.get(url, params=params or {}, timeout=timeout)
            if r.status_code == 200:
                d = r.json()
                # 检测 key 失效（403 invalid_api_key）
                if isinstance(d, dict) and d.get('code') == 403 and 'invalid_api_key' in str(d.get('raw', '')):
                    last_err = d
                    continue  # 试下一个 key
                return d
            last_err = {"code": r.status_code, "msg": f"HTTP {r.status_code}"}
        except Exception as e:
            last_err = {"code": -1, "msg": f"{type(e).__name__}: {e}"}
            continue

    return last_err or {"code": -1, "msg": "all keys failed"}


# ───── 主调用函数 ─────
def call(path: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
    """
    通用 GET 调用 super API.
    例子: call('daily', {'ts_code': '000001.SZ'})
    """
    s, creds = _session()
    base = creds['super_api_base']
    url = f"{base}{creds['super_api_path_prefix']}/{path}"
    try:
        r = s.get(url, params=params or {}, timeout=timeout)
        if r.status_code != 200:
            return {"code": r.status_code, "msg": f"HTTP {r.status_code}", "raw": r.text[:200]}
        return r.json()
    except Exception as e:
        return {"code": -1, "msg": f"{type(e).__name__}: {e}", "raw": ""}


def direct_post(payload: dict, timeout: int = 15) -> dict:
    """fastapic 端点（POST json）"""
    s, creds = _session()
    url = creds['fastapic_url']
    payload = {**payload, 'token': creds['fastapic_token']}
    try:
        r = requests.post(url, json=payload, headers={"Accept-Encoding": "identity"}, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"code": -1, "msg": f"{type(e).__name__}: {e}"}


# ───── 高级封装（5 只持仓优先） ─────
HOLDINGS = {
    '588080': 'sh',   # 科创50ETF
    '159869': 'sz',   # 游戏动漫ETF
    '513050': 'sh',   # 中概互联网ETF
    '513120': 'sh',   # 港股创新药ETF
    '516010': 'sh',   # 游戏ETF国泰
}

def ts_code(code: str) -> str:
    """159869 → 159869.SZ"""
    if '.' in code:
        return code
    m = {'sh': 'SH', 'sz': 'SZ'}[HOLDINGS.get(code, 'sh' if code.startswith(('5','6','0')) else 'sz')]
    return f"{code}.{m}"


def get_etf_daily(code: str, start_date: str, end_date: str) -> list:
    """拉单只 ETF K 线（用 fund_daily）
    入参: code=588080 / start_date=20260101 / end_date=20260724
    返回: items list (按 tushare 协议: trade_date/open/high/low/close/pre_close/change/pct_chg/vol/amount)
    """
    ts = ts_code(code)
    r = call('fund_daily', {'ts_code': ts, 'start_date': start_date, 'end_date': end_date})
    if r.get('code') == 0 and r.get('data', {}).get('items'):
        return r['data']['items']
    return []


def get_stock_daily(code: str, start_date: str, end_date: str) -> list:
    """拉 A 股 K 线（用 daily）"""
    ts = ts_code(code)
    r = call('daily', {'ts_code': ts, 'start_date': start_date, 'end_date': end_date})
    if r.get('code') == 0 and r.get('data', {}).get('items'):
        return r['data']['items']
    return []


def get_cyq(code: str, trade_date: Optional[str] = None) -> list:
    """拉筹码分布 (cyq_perf)"""
    ts = ts_code(code)
    params = {'ts_code': ts}
    if trade_date:
        params['trade_date'] = trade_date
    r = call('cyq_perf', params)
    if r.get('code') == 0 and r.get('data', {}).get('items'):
        return r['data']['items']
    return []


def get_moneyflow(code: str, start_date: str, end_date: str) -> list:
    """拉资金流 (moneyflow)"""
    ts = ts_code(code)
    r = call('moneyflow', {'ts_code': ts, 'start_date': start_date, 'end_date': end_date})
    if r.get('code') == 0 and r.get('data', {}).get('items'):
        return r['data']['items']
    return []


def get_hsgt_top10(trade_date: str) -> list:
    """拉北向 TOP10 (hsgt_top10)"""
    r = call('hsgt_top10', {'trade_date': trade_date})
    if r.get('code') == 0 and r.get('data', {}).get('items'):
        return r['data']['items']
    return []


def get_limit_list(trade_date: str) -> list:
    """拉涨停板列表 (limit_list_d)"""
    r = call('limit_list_d', {'trade_date': trade_date})
    if r.get('code') == 0 and r.get('data', {}).get('items'):
        return r['data']['items']
    return []


# ───── 离线缓存（避免每个 cron 都去拉） ─────
CACHE_DIR = Path.home() / '.hermes/cache/stock_data/xianyu_tushare'

def cache_locally(data: any, key: str) -> Path:
    """将任意数据落盘到 cache 目录，文件名 = key.json"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / f"{key}.json"
    with open(f, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2, default=str)
    return f


def load_cache(key: str) -> Optional[any]:
    """读缓存"""
    f = CACHE_DIR / f"{key}.json"
    if not f.exists():
        return None
    try:
        with open(f) as fp:
            return json.load(fp)
    except Exception:
        return None


# ───── 一次性缓存 5 只持仓的全量数据 ─────
def cache_holdings_full(days: int = 180) -> dict:
    """拉 5 只持仓最近 N 天 K 线 + 筹码 + 资金流，落盘缓存"""
    from datetime import datetime, timedelta
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

    results = {}
    for code in HOLDINGS:
        results[code] = {
            'fund_daily': get_etf_daily(code, start, end),
        }
        time.sleep(0.3)  # 礼貌限速 (卖家限速 400 次/分)

    cache_locally(results, f"holdings_full_{end}")
    return results


# ───── CLI 入口 ─────
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 tushare_xianyu.py etf <code>          # 单只 ETF K 线")
        print("  python3 tushare_xianyu.py holdings            # 5 只持仓全缓存")
        print("  python3 tushare_xianyu.py cyq <code>          # 单只筹码分布")
        print("  python3 tushare_xianyu.py moneyflow <code>    # 单只资金流")
        print("  python3 tushare_xianyu.py hsgt 20240725       # 北向 TOP10")
        print("  python3 tushare_xianyu.py limit 20240725      # 涨停板")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == 'etf':
        items = get_etf_daily(sys.argv[2], sys.argv[3], sys.argv[4])
        for it in items[:5]:
            print(it)
    elif cmd == 'holdings':
        results = cache_holdings_full()
        print(f"缓存了 {len(results)} 只持仓")
    elif cmd == 'cyq':
        items = get_cyq(sys.argv[2])
        print(f"共 {len(items)} 条筹码记录")
        if items[:3]:
            print("样本:", items[:3])
    elif cmd == 'moneyflow':
        items = get_moneyflow(sys.argv[2], sys.argv[3], sys.argv[4])
        for it in items[:5]:
            print(it)
    elif cmd == 'hsgt':
        items = get_hsgt_top10(sys.argv[2])
        print(f"共 {len(items)} 条北向记录")
        if items[:3]:
            print("样本:", items[:3])
    elif cmd == 'limit':
        items = get_limit_list(sys.argv[2])
        print(f"共 {len(items)} 条涨停记录")
        if items[:3]:
            print("样本:", items[:3])
