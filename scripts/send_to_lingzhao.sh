#!/usr/bin/env bash
# send_to_lingzhao.sh
# 统一给小妹(灵爪)发文件的管道：本地 → NAS inbox + 校验

set -euo pipefail

REMOTE_USER="YDL"
REMOTE_HOST="192.168.31.10"
REMOTE_DIR="~/.openclaw/workspace/claw-communication/inbox"

usage() {
  echo "用法: $0 <本地文件路径> [远端文件名]" >&2
  echo "示例: $0 claw-communication/outbox/来自龙爪_xxx.md" >&2
  exit 1
}

if [[ ${1-} == "" ]]; then
  usage
fi

LOCAL_PATH="$1"
REMOTE_NAME="${2-}"

if [[ ! -f "$LOCAL_PATH" ]]; then
  echo "❌ 本地文件不存在: $LOCAL_PATH" >&2
  exit 1
fi

if [[ -z "$REMOTE_NAME" ]]; then
  REMOTE_NAME="$(basename "$LOCAL_PATH")"
fi

REMOTE_TARGET="$REMOTE_DIR/$REMOTE_NAME"

echo "📨 准备发送给小妹: $LOCAL_PATH → $REMOTE_USER@$REMOTE_HOST:$REMOTE_TARGET"

# 1) 发送文件
scp "$LOCAL_PATH" "${REMOTE_USER}@${REMOTE_HOST}:$REMOTE_TARGET"

# 2) 远端校验
ssh "${REMOTE_USER}@${REMOTE_HOST}" "test -f '$REMOTE_TARGET' && ls -l '$REMOTE_TARGET'" >/tmp/send_to_lingzhao_last.log 2>&1 || {
  echo "❌ 远端未找到文件，发送失败 (请查看 /tmp/send_to_lingzhao_last.log)" >&2
  exit 1
}

echo "✅ 已成功送达小妹收件箱: $REMOTE_TARGET"