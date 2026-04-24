#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AData HTTP API 服务 - 多数据源冗余版本
启动命令：python3 adata_api_server.py
访问地址：http://192.168.31.141:5000
"""

from flask import Flask, jsonify, request
import pandas as pd
import json
import threading
from adata_fetcher_simple import (
    fetch_stock_data_cached,
    fetch_single_stock,
    fetch_historical_data,
    get_cache_status,
    test_all_sources,
    fetch_a50_cfd
)

app = Flask(__name__)

# 缓存最新数据（避免频繁请求）
_cached_data = None
_cached_timestamp = None

# 请求锁（防止并发请求导致多次获取）
_data_lock = threading.Lock()
_fetch_in_progress = False


@app.route('/')
def index():
    """API 首页"""
    cache_status = get_cache_status()
    return jsonify({
        "service": "AData 股票数据 API",
        "version": "2.2 (缓存优化版)",
        "endpoints": {
            "GET /all": "获取全部 A 股实时数据",
            "GET /stock?code=600519": "获取单只股票实时数据",
            "GET /stocks?codes=600519,002584": "批量获取多只股票 ⭐新",
            "GET /history?code=600519&start=20240101": "获取历史 K 线数据",
            "GET /test": "测试所有数据源",
            "GET /health": "健康检查",
            "GET /cache": "查看缓存状态 ⭐新"
        },
        "data_sources": {
            "realtime": ["新浪财经 (主力)", "雪球 (快速备选)"],
            "historical": ["baostock", "官方 AData 库"]
        },
        "features": {
            "fallback": "自动切换数据源，保证获取成功率",
            "cache": "120 秒缓存 + 请求锁，支持 50+ 并发",
            "fast_mode": "单只股票 3 秒响应，批量并发获取",
            "official_integration": HAS_ADATA
        },
        "cache_status": cache_status
    })


@app.route('/health')
def health():
    """健康检查"""
    cache_status = get_cache_status()
    return jsonify({
        "status": "ok",
        "cache": cache_status,
        "version": "2.2"
    })


@app.route('/cache')
def cache_info():
    """查看缓存状态"""
    return jsonify(get_cache_status())


@app.route('/stocks')
def get_multiple_stocks():
    """批量获取多只股票数据"""
    codes_param = request.args.get('codes')
    
    if not codes_param:
        return jsonify({"status": "error", "message": "缺少参数：codes (例：600519,002584,300750)"}), 400
    
    # 解析股票代码
    codes = [c.strip() for c in codes_param.split(',')]
    
    # 逐个获取
    results = {}
    for code in codes:
        stock_data = fetch_single_stock(code, verbose=False)
        results[code] = stock_data
    
    # 统计结果
    success_count = sum(1 for v in results.values() if v is not None)
    
    return jsonify({
        "status": "success",
        "requested": len(codes),
        "success": success_count,
        "failed": len(codes) - success_count,
        "data": results
    })


@app.route('/all')
def get_all_stocks():
    """获取全部 A 股数据（使用优化后的缓存）"""
    # 使用新的缓存函数
    df = fetch_stock_data_cached(verbose=False)
    
    if df is None:
        return jsonify({"status": "error", "message": "数据获取失败"}), 503
    
    # 转换为字典列表
    data = df.to_dict(orient='records')
    return jsonify({
        "status": "success",
        "count": len(data),
        "cache_age": get_cache_status()['age'],
        "data": data
    })
    
@app.route('/stock')
def get_single_stock():
    """获取单只股票数据"""
    code = request.args.get('code')
    
    if not code:
        return jsonify({"status": "error", "message": "缺少参数：code"}), 400
    
    # 获取股票数据
    result = fetch_single_stock(code, verbose=False)
    
    if result is None:
        return jsonify({"status": "error", "message": f"未找到股票：{code}"}), 404
    
    # 清理数据
    cleaned = {}
    for key, value in result.items():
        try:
            if isinstance(value, (int, float)):
                cleaned[key] = round(value, 2) if not isinstance(value, int) else value
            else:
                cleaned[key] = str(value)
        except:
            cleaned[key] = str(value)
    
    return jsonify({
        "status": "success",
        "data": cleaned
    })


@app.route('/test')
def test_sources():
    """测试所有数据源"""
    results = test_all_sources()
    return jsonify(results)


@app.route('/history')
def get_history():
    """获取股票历史 K 线数据（使用 baostock）"""
    code = request.args.get('code')
    start = request.args.get('start', '20240101')
    end = request.args.get('end', None)
    k_type = request.args.get('k_type', '1', type=int)
    
    if not code:
        return jsonify({"status": "error", "message": "缺少参数：code"}), 400
    
    # 调用历史数据获取函数（内部已优先使用 Tushare，无需 baostock 标志）
    try:
        df = fetch_historical_data(code, start, end, k_type)
        
        if df is None:
            return jsonify({
                "status": "error",
                "message": "历史数据获取失败，请稍后重试"
            }), 503
        
        # 转换为 JSON
        result_df = df.copy()
        numeric_cols = ['open', 'close', 'high', 'low', 'volume', 'amount']
        for col in numeric_cols:
            if col in result_df.columns:
                result_df[col] = pd.to_numeric(result_df[col], errors='coerce').round(2)
        
        return jsonify({
            "status": "success",
            "stock_code": code,
            "start_date": start,
            "end_date": end or pd.Timestamp.now().strftime("%Y%m%d"),
            "k_type": k_type,
            "count": len(result_df),
            "data": result_df.to_dict('records')
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"历史数据获取异常: {str(e)}"
        }), 503






@app.route("/a50")
def get_a50_cfd():
    """获取新华富时A50 CFD实时行情"""
    data = fetch_a50_cfd()
    if data is None:
        return jsonify({
            "status": "error",
            "message": "A50数据获取失败，请稍后重试"
        }), 502
    return jsonify({
        "status": "success",
        "data": data
    })

if __name__ == '__main__':
    import socket
    
    # 获取本机 IP
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("=" * 60)
    print("🐉 AData API 服务启动中... (v2.0 极简稳定版)")
    print("=" * 60)
    print(f"  本地访问：http://127.0.0.1:5000")
    print(f"  局域网访问：http://{local_ip}:5000")
    print(f"  实时数据源：新浪财经 (5501只A股)")
    print(f"  历史数据：akshare 日线数据")
    print(f"  缓存：120 秒自动缓存")
    print("=" * 60)
    print("\nAPI 端点:")
    print("  GET /all          - 全部 A 股实时数据 (5501只)")
    print("  GET /stock?code=X - 单只股票实时数据")
    print("  GET /stocks?codes=X,Y,Z - 批量获取多只股票")
    print("  GET /history?code=X&start=20240101 - 历史 K 线数据")
    print("  GET /test         - 测试所有数据源")
    print("  GET /health       - 健康检查")
    print("  GET /cache        - 查看缓存状态")
    print("=" * 60)
    
    print("\n按 Ctrl+C 停止服务\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
