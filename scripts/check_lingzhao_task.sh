#!/bin/bash
# 检查灵爪交代的任务

NAS_IP="192.168.31.10"
SSH_KEY="/home/yu/.ssh/id_ed25519_new"
COMM_DIR="/home/YDL/.openclaw/workspace/claw-communication"

echo "🔍 检查灵爪交代的任务..."
echo "========================"

# 1. 检查inbox目录（主通道）
echo "📂 检查inbox目录（主通道）:"
ssh -i "$SSH_KEY" YDL@$NAS_IP "ls -lt $COMM_DIR/inbox/ 2>/dev/null | head -10" 2>/dev/null

# 2. 检查longzhua-box目录（我的收件箱）
echo ""
echo "📂 检查longzhua-box目录（我的收件箱）:"
ssh -i "$SSH_KEY" YDL@$NAS_IP "ls -lt $COMM_DIR/sharebox/longzhua-box/ 2>/dev/null | head -10" 2>/dev/null

# 3. 检查灵爪工作区是否有新文件
echo ""
echo "📂 检查灵爪工作区新文件:"
ssh -i "$SSH_KEY" YDL@$NAS_IP "find $COMM_DIR -type f -name '*灵爪*' -o -name '*任务*' -o -name '*交代*' -o -name '*指示*' 2>/dev/null | xargs ls -lt 2>/dev/null | head -10" 2>/dev/null

# 4. 检查今天创建的文件
echo ""
echo "📂 检查今天创建的文件:"
TODAY=$(date +%Y%m%d)
ssh -i "$SSH_KEY" YDL@$NAS_IP "find $COMM_DIR -type f -newermt '2026-04-15 00:00:00' ! -newermt '2026-04-16 00:00:00' 2>/dev/null | xargs ls -lt 2>/dev/null | head -10" 2>/dev/null

# 5. 检查灵爪状态
echo ""
echo "📡 检查灵爪进程状态:"
ssh -i "$SSH_KEY" YDL@$NAS_IP "pm2 status openclaw 2>/dev/null | grep -A2 lingzhao" 2>/dev/null

# 6. 检查是否有飞书@消息（通过文件系统）
echo ""
echo "💬 检查飞书相关文件:"
ssh -i "$SSH_KEY" YDL@$NAS_IP "find $COMM_DIR -type f -name '*飞书*' -o -name '*feishu*' -o -name '*@*' 2>/dev/null | xargs ls -lt 2>/dev/null | head -10" 2>/dev/null

echo ""
echo "========================"
echo "📋 检查完成"

# 如果有新文件，显示内容
echo ""
echo "📄 最新文件内容预览:"
LATEST_FILE=$(ssh -i "$SSH_KEY" YDL@$NAS_IP "find $COMM_DIR -type f -newermt '2026-04-15 10:30:00' 2>/dev/null | head -1" 2>/dev/null)
if [ -n "$LATEST_FILE" ]; then
    echo "最新文件: $LATEST_FILE"
    ssh -i "$SSH_KEY" YDL@$NAS_IP "head -20 '$LATEST_FILE' 2>/dev/null"
else
    echo "未找到10:30之后的新文件"
fi