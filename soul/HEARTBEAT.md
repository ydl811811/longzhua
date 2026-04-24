# HEARTBEAT.md - 轻量级状态检查

## 检查原则
1. ✅ 只检查本地关键状态（不进行网络操作）
2. ✅ NAS通信由专用监控脚本处理
3. ✅ 避免重复检查，节省token

## 检查项目
- 本地OpenClaw网关状态
- 本地代理服务状态
- 基本系统健康度

## 执行命令
# 检查本地代理是否运行
curl -s http://localhost:5002/health 2>/dev/null | grep -q '"status":"ok"' && echo "✅ 代理服务正常" || echo "⚠️ 代理服务异常"

# 检查OpenClaw网关进程
ps aux | grep -q "openclaw-gateway" && echo "✅ OpenClaw网关运行中" || echo "⚠️ OpenClaw网关未运行"

# 基本系统状态
echo "🕐 系统时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "💾 内存使用: $(free -h | awk '/^Mem:/ {print $3"/"$2}')"