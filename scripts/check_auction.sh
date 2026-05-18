#!/bin/bash
# 检查集合竞价输出是否有内容，有内容则飞书通知
OUTPUT="/home/yu/.hermes/cron/output/auction_monitor.txt"
TOKEN_FILE="$HOME/.hermes/feishu_alert_token"

if [ ! -f "$OUTPUT" ]; then
    exit 0
fi

CONTENT=$(cat "$OUTPUT")
if [ -z "$CONTENT" ]; then
    exit 0
fi

# 检查是否包含 ✅ 或 异常信号（持仓出现🔴）
if echo "$CONTENT" | grep -q '🔴\|✅'; then
    TOKEN=$(cat "$TOKEN_FILE" 2>/dev/null)
    if [ -n "$TOKEN" ]; then
        curl -s -X POST "https://open.feishu.cn/open-apis/bot/v2/hook/${TOKEN}" \
            -H "Content-Type: application/json" \
            -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"📊 集合竞价异动提醒\\n—\\/\\/—\\n$CONTENT\"}}"
    fi
fi
