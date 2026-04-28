#!/bin/bash
# 检查灵爪是否有新消息发到 longzhua-box
# 如果有新文件，发送通知到飞书

LAST_CHECK_FILE="/tmp/longzhua-box-last-check.txt"
SSH_KEY="/home/yu/.ssh/id_ed25519_new"
NAS_HOST="YDL@192.168.31.10"
BOX_DIR="/home/YDL/.openclaw/workspace/claw-communication/sharebox/longzhua-box"
FEISHU_TOKEN_ENV="FEISHU_WEBHOOK_URL"

# 获取当前最新文件时间戳
CURRENT_LATEST=$(ssh -i "$SSH_KEY" "$NAS_HOST" \
  "ls -lt '$BOX_DIR' 2>/dev/null | head -2" 2>/dev/null | \
  awk 'NR==2 {print $6"-"$7"-"$8" "$9}')

if [ -z "$CURRENT_LATEST" ]; then
  echo "[$(date)] 无法连接NAS或读取目录"
  exit 1
fi

# 读取上次记录
if [ -f "$LAST_CHECK_FILE" ]; then
  LAST_LATEST=$(cat "$LAST_CHECK_FILE")
else
  LAST_LATEST=""
fi

# 比较
if [ "$CURRENT_LATEST" != "$LAST_LATEST" ]; then
  echo "[$(date)] 检测到新文件！"

  # 获取最新文件列表（前5个）
  NEW_FILES=$(ssh -i "$SSH_KEY" "$NAS_HOST" \
    "ls -lt '$BOX_DIR' 2>/dev/null | head -6" 2>/dev/null)

  # 发送飞书通知
  FEISHU_WEBHOOK_URL=$(cat ~/.hermes/config.yaml 2>/dev/null | grep -A1 "feishu_webhook" | tail -1 | awk '{print $2}')
  if [ -n "$FEISHU_WEBHOOK_URL" ]; then
    curl -s -X POST "$FEISHU_WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "{
        \"msg_type\": \"text\",
        \"text\": {
          \"content\": \"🦞 灵爪有新消息！\\n最新文件：\\n${NEW_FILES}\"
        }
      }" 2>/dev/null
  fi

  echo "$CURRENT_LATEST" > "$LAST_CHECK_FILE"
else
  echo "[$(date)] 无新文件， latest: $CURRENT_LATEST"
fi
