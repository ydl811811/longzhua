# 🐉 AData API 使用指南 v2.2

**最后更新**: 2026-04-13
**服务地址**: `http://192.168.31.141:5000` 或 `http://localhost:5000`

---

## 🚀 快速开始

### 1. 服务状态检查
```bash
# 健康检查
curl http://localhost:5000/health

# 查看所有端点
curl http://localhost:5000/
```

### 2. 启动服务
```bash
# 在工作目录启动
cd ~/.openclaw/workspace
python3 adata_api_server.py

# 或使用nohup后台运行
nohup python3 adata_api_server.py > /tmp/adata.log 2>&1 &
```

---

## 📊 API 端点详解

### 1. **首页信息** `GET /`
返回所有可用端点和系统信息。
```bash
curl http://localhost:5000/
```

### 2. **健康检查** `GET /health`
检查服务状态和缓存信息。
```bash
curl http://localhost:5000/health
```

### 3. **单只股票实时数据** `GET /stock?code=股票代码`
获取单只股票的实时行情数据。
```bash
# 基本用法
curl "http://localhost:5000/stock?code=002415"

# 使用雪球优先策略（响应更快）
curl "http://localhost:5000/stock?code=002415&xueqiu=true"
```

**参数**:
- `code`: 股票代码（支持格式：`002415`、`sz002415`、`600519`、`sh600519`）
- `xueqiu`: 可选，`true` 使用雪球优先策略（默认 `false`）

**返回字段**:
```json
{
  "代码": "sz002415",
  "名称": "海康威视",
  "今开": 31.51,
  "昨收": 31.71,
  "最新价": 32.65,
  "最高": 32.66,
  "最低": 31.41,
  "涨跌额": 0.94,
  "涨跌幅": 2.964,
  "成交量": 64249030.0,
  "成交额": 2068425798.0,
  "时间戳": "15:00:00"
}
```

### 4. **批量获取多只股票** `GET /stocks?codes=代码1,代码2,...`
批量获取多只股票的实时数据，支持并发获取。
```bash
# 批量查询3只股票
curl "http://localhost:5000/stocks?codes=002415,600519,300750"

# 禁用缓存（获取最新数据）
curl "http://localhost:5000/stocks?codes=002415,600519&cache=false"
```

**参数**:
- `codes`: 逗号分隔的股票代码列表
- `cache`: 可选，是否使用缓存（默认 `true`）

**返回示例**:
```json
{
  "status": "success",
  "requested": 3,
  "success": 3,
  "failed": 0,
  "use_cache": true,
  "data": {
    "002415": { ... },
    "600519": { ... },
    "300750": { ... }
  }
}
```

### 5. **历史K线数据** `GET /history?code=股票代码&start=开始日期`
获取股票的历史K线数据。
```bash
# 获取2024年以来的日K线
curl "http://localhost:5000/history?code=002415&start=20240101"

# 获取5分钟K线，指定结束日期
curl "http://localhost:5000/history?code=002415&start=20240101&end=20240408&k_type=5"
```

**参数**:
- `code`: 股票代码
- `start`: 开始日期，格式 `YYYYMMDD`
- `end`: 结束日期，格式 `YYYYMMDD`（可选，默认今天）
- `k_type`: K线类型（可选，默认 `1`）
  - `1`: 日K
  - `5`: 5分钟K
  - `15`: 15分钟K
  - `30`: 30分钟K
  - `60`: 60分钟K

### 6. **数据源测试** `GET /test`
测试所有数据源的连通性和响应时间。
```bash
curl http://localhost:5000/test
```

### 7. **缓存状态** `GET /cache`
查看缓存状态和命中率。
```bash
curl http://localhost:5000/cache
```

---

## 🔧 数据源架构

### 实时数据源（4层冗余）
1. **东方财富** - 优先源，速度快
2. **新浪财经** - 稳定备选
3. **百度财经** - 第三备选
4. **网易财经** - 第四备选
5. **雪球** - 快速备选（`xueqiu=true`时优先）

### 历史数据源（2层冗余）
1. **baostock** - 优先源，稳定
2. **官方AData库** - 备选源（需 `pip install adata`）

### 缓存机制
- **缓存时间**: 120秒
- **请求锁**: 防止并发重复请求
- **支持并发**: 50+ 并发请求
- **智能更新**: 缓存过期时自动更新

---

## ⚡ 使用技巧与最佳实践

### 1. 性能优化
```bash
# 批量查询比单只查询快10倍
curl "http://localhost:5000/stocks?codes=002415,600519,300750"

# 实时性要求高时禁用缓存
curl "http://localhost:5000/stock?code=002415&cache=false"

# 快速响应使用雪球优先
curl "http://localhost:5000/stock?code=002415&xueqiu=true"
```

### 2. 错误处理
```bash
# 检查返回状态
response=$(curl -s "http://localhost:5000/stock?code=002415")
status=$(echo $response | jq -r '.status')
if [ "$status" = "success" ]; then
    echo "获取成功"
else
    echo "获取失败"
fi
```

### 3. Python客户端示例
```python
import requests
import json

class ADataClient:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
    
    def get_stock(self, code, use_xueqiu=False):
        """获取单只股票数据"""
        url = f"{self.base_url}/stock"
        params = {"code": code}
        if use_xueqiu:
            params["xueqiu"] = "true"
        
        response = requests.get(url, params=params)
        return response.json()
    
    def get_multiple_stocks(self, codes, use_cache=True):
        """批量获取股票数据"""
        url = f"{self.base_url}/stocks"
        params = {
            "codes": ",".join(codes),
            "cache": "true" if use_cache else "false"
        }
        response = requests.get(url, params=params)
        return response.json()

# 使用示例
client = ADataClient()
data = client.get_stock("002415")
print(f"海康威视当前价格: {data['data']['最新价']}")
```

### 4. Shell脚本示例
```bash
#!/bin/bash
# get_stock.sh - 获取股票数据脚本

ADATA_URL="http://localhost:5000"

get_stock_price() {
    local code=$1
    local response=$(curl -s "${ADATA_URL}/stock?code=${code}")
    local price=$(echo $response | jq -r '.data."最新价"')
    local name=$(echo $response | jq -r '.data."名称"')
    local change=$(echo $response | jq -r '.data."涨跌幅"')
    
    echo "📈 $name ($code)"
    echo "💰 价格: $price"
    echo "📊 涨跌幅: ${change}%"
}

# 使用示例
get_stock_price "002415"
```

---

## 🛠️ 系统管理

### 1. 服务管理
```bash
# 启动服务
cd ~/.openclaw/workspace
python3 adata_api_server.py

# 后台运行
nohup python3 adata_api_server.py > /tmp/adata.log 2>&1 &

# 查看日志
tail -f /tmp/adata.log

# 停止服务
pkill -f "adata_api_server.py"
```

### 2. 监控检查
```bash
# 检查服务是否运行
curl -s http://localhost:5000/health | jq '.status'

# 检查缓存状态
curl -s http://localhost:5000/cache | jq '.'

# 测试所有数据源
curl -s http://localhost:5000/test | jq '.'
```

### 3. 性能监控
```bash
# 查看进程资源使用
ps aux | grep adata_api_server

# 查看端口监听
ss -tlnp | grep :5000

# 查看请求日志
tail -f /tmp/adata.log | grep -E "GET|POST"
```

---

## 🔍 故障排除

### 常见问题

1. **服务无法启动**
   ```bash
   # 检查Python依赖
   pip3 install flask pandas akshare baostock
   
   # 检查端口占用
   ss -tlnp | grep :5000
   
   # 查看错误日志
   python3 adata_api_server.py 2>&1
   ```

2. **数据获取失败**
   ```bash
   # 测试数据源
   curl http://localhost:5000/test
   
   # 检查网络连接
   curl -I https://quote.eastmoney.com
   
   # 尝试禁用缓存
   curl "http://localhost:5000/stock?code=002415&cache=false"
   ```

3. **响应缓慢**
   ```bash
   # 使用雪球优先策略
   curl "http://localhost:5000/stock?code=002415&xueqiu=true"
   
   # 使用批量查询
   curl "http://localhost:5000/stocks?codes=002415"
   
   # 检查缓存状态
   curl http://localhost:5000/cache
   ```

---

## 📁 相关文件

- `adata_api_server.py` - API服务器主程序
- `adata_fetcher.py` - 数据获取核心模块
- `adata_config.json` - 配置文件
- `adata_integration_report.md` - 集成报告
- `adata_data_source_analysis.md` - 数据源分析

---

## 📞 支持与反馈

如有问题，请联系：
- **维护者**: 龙爪
- **更新时间**: 2026-04-13
- **版本**: v2.2 (缓存优化版)

> 提示：本服务已集成到OpenClaw生态，可通过OpenClaw直接调用。