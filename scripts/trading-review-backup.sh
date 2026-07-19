#!/bin/bash
# ==============================================
# trading-review 自动备份脚本
# 用法：
#   ./backup.sh                # 全量备份（git add -A）
#   ./backup.sh --journal      # 仅 journal/ 增量备份
# ==============================================
set -euo pipefail

REPO_DIR="/home/yu/trading-review"
cd "$REPO_DIR"

# 检测是否有变更
if [ "${1:-}" = "--journal" ]; then
    git add -A journal/ 2>/dev/null || true
else
    git add -A
fi

# 检查是否有变更需要提交
if git diff --cached --quiet; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') | 无变更，跳过"
    exit 0
fi

# 有变更 → 提交 + 推送
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
MSG="${1:+[journal] }复盘备份 ${TIMESTAMP}"

git commit -m "$MSG"
git push origin main 2>&1 || echo "⚠️ push 失败，稍后重试"

echo "✅ ${MSG} — 完成"