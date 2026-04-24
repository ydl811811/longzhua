# 🐉 AData股票数据API - 灵爪使用指南

## 📡 服务地址
```
主服务: http://192.168.31.141:5000
备用地址: http://localhost:5000 (同一台机器)
```

## 🚀 快速开始

### 1. 健康检查
```bash
curl "http://192.168.31.141:5000/health"
```
```json
{
  "status": "ok",
  "version": "2.2",
  "cache": {
    "status": "valid",
    "age": 45.2,
    "count": 5501,
    "ttl": 120
  }
}
```

### 2. 获取单只股票实时数据
```bash
# 平安银行
curl "http://192.168.31.141:5000/stock?code=000001"

# 科大讯飞
curl "http://192.168.31.141:5000/stock?code=002230"

# 贵州茅台
curl "http://192.168.31.141:5000/stock?code=600519"
```

### 3. 批量获取多只股票
```bash
curl "http://192.168.31.141:5000/stocks?codes=600519,300750,002594"
```

### 4. 获取全部A股数据 (5501只)
```bash
curl "http://192.168.31.141:5000/all"
```

### 5. 获取历史K线数据
```bash
# 最近30天数据
curl "http://192.168.31.141:5000/history?code=000001&start=20240315"

# 指定日期范围
curl "http://192.168.31.141:5000/history?code=000001&start=20240101&end=20240331"
```

## 📊 数据字段说明

### 实时数据字段
```json
{
  "代码": "000001",        // 股票代码
  "名称": "平安银行",      // 股票名称
  "最新价": 10.25,        // 最新价格
  "涨跌幅": 1.23,         // 涨跌幅百分比
  "涨跌额": 0.12,         // 涨跌金额
  "成交量": 1234567,      // 成交量(手)
  "成交额": 123456789,    // 成交额(元)
  "振幅": 2.34,           // 振幅百分比
  "最高": 10.30,          // 当日最高
  "最低": 10.10,          // 当日最低
  "今开": 10.15,          // 今日开盘
  "昨收": 10.13,          // 昨日收盘
  "量比": 1.23,           // 量比
  "换手率": 0.56,         // 换手率百分比
  "市盈率": 8.90,         // 市盈率
  "市净率": 0.78,         // 市净率
  "总市值": 1234567890,   // 总市值(元)
  "流通市值": 987654321   // 流通市值(元)
}
```

### 历史数据字段
```json
{
  "date": "2024-04-01",   // 交易日期
  "open": 10.15,          // 开盘价
  "close": 10.25,         // 收盘价
  "high": 10.30,          // 最高价
  "low": 10.10,           // 最低价
  "volume": 1234567,      // 成交量
  "amount": 123456789,    // 成交额
  "pct_chg": 1.23,        // 涨跌幅百分比
  "change": 0.12,         // 涨跌额
  "amplitude": 2.34,      // 振幅百分比
  "turnover": 0.56        // 换手率百分比
}
```

## 🔧 服务特性

### 缓存机制
- **自动缓存**: 120秒缓存，减少数据源压力
- **智能更新**: 缓存过期后自动刷新
- **状态监控**: 可通过 `/cache` 端点查看缓存状态

### 数据源
- **实时数据**: 新浪财经 (5501只A股)
- **历史数据**: akshare日线数据
- **数据质量**: 经过清洗和标准化

### 性能特点
- **快速响应**: 缓存命中时 < 50ms
- **批量支持**: 支持最多50只股票批量查询
- **并发处理**: 支持多请求并发

## 🐍 Python使用示例

### 基础查询
```python
import requests
import json

# 配置
BASE_URL = "http://192.168.31.141:5000"

def get_stock_data(code):
    """获取单只股票数据"""
    url = f"{BASE_URL}/stock?code={code}"
    response = requests.get(url)
    return response.json()

def get_history(code, start_date, end_date=None):
    """获取历史数据"""
    url = f"{BASE_URL}/history?code={code}&start={start_date}"
    if end_date:
        url += f"&end={end_date}"
    response = requests.get(url)
    return response.json()

# 使用示例
if __name__ == "__main__":
    # 获取平安银行实时数据
    data = get_stock_data("000001")
    print(f"平安银行: {data['data']['最新价']}")
    
    # 获取历史数据
    hist = get_history("000001", "20240401")
    print(f"历史数据条数: {hist['count']}")
```

### 批量处理
```python
def batch_query(codes):
    """批量查询多只股票"""
    codes_str = ",".join(codes)
    url = f"{BASE_URL}/stocks?codes={codes_str}"
    response = requests.get(url)
    return response.json()

# 批量查询热门股票
hot_stocks = ["600519", "300750", "002594", "000858", "002415"]
result = batch_query(hot_stocks)
print(f"成功获取 {result['success']}/{result['requested']} 只股票")
```

## ⚠️ 注意事项

### 使用限制
1. **缓存时间**: 实时数据缓存120秒，历史数据无缓存
2. **批量限制**: 建议单次批量不超过50只股票
3. **网络要求**: 需要能访问 `192.168.31.141` 的内网环境

### 错误处理
```python
try:
    response = requests.get(f"{BASE_URL}/stock?code=000001", timeout=5)
    data = response.json()
    if data['status'] == 'success':
        # 处理成功数据
        pass
    else:
        print(f"查询失败: {data.get('message', '未知错误')}")
except requests.exceptions.Timeout:
    print("请求超时，请检查网络连接")
except requests.exceptions.ConnectionError:
    print("连接失败，请检查服务状态")
except json.JSONDecodeError:
    print("响应格式错误")
```

## 🔍 服务状态监控

### 健康检查
```bash
# 检查服务状态
curl "http://192.168.31.141:5000/health"

# 检查缓存状态
curl "http://192.168.31.141:5000/cache"

# 测试所有数据源
curl "http://192.168.31.141:5000/test"
```

### 系统服务
```bash
# 查看服务状态 (在yu-K46CM上)
systemctl --user status adata-api

# 重启服务
systemctl --user restart adata-api

# 查看日志
journalctl --user -u adata-api -n 20
```

## 🚨 故障排除

### 常见问题
1. **连接失败**: 检查 `192.168.31.141` 网络连通性
2. **数据为空**: 可能是数据源暂时不可用，稍后重试
3. **响应缓慢**: 检查缓存状态，首次加载可能需要时间

### 联系支持
- **服务维护**: 龙爪 (yu-K46CM)
- **问题反馈**: 通过飞书群聊 @龙爪
- **紧急处理**: SSH到 `192.168.31.141` 检查服务

## 📈 使用场景建议

### 适合场景
1. **实时监控**: 监控自选股价格变化
2. **数据分析**: 获取历史数据进行回测
3. **批量处理**: 一次性获取多只股票数据
4. **系统集成**: 作为其他系统的数据源

### 性能建议
1. **缓存利用**: 频繁查询时依赖缓存机制
2. **批量操作**: 多只股票时使用批量接口
3. **错误重试**: 网络波动时实现重试机制
4. **数据本地化**: 重要数据本地存储备份

---

**最后更新**: 2026-04-14  
**维护者**: 龙爪  
**服务状态**: ✅ 运行正常  
**数据覆盖**: 5501只A股实时 + 历史数据