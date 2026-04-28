#!/bin/bash
# 龙爪 → GitHub 备份脚本
# 备份 ~/.hermes/memories/ 和 ~/.hermes/scripts/ 到 ydl811811/longzhua

WORK_DIR="/tmp/longzhua_backup_$$"
GIT_DIR="$HOME/.git-credentials"

# 读取token
TOKEN=$(grep "github.com" "$GIT_DIR" 2>/dev/null | sed 's|https://[^:]*:\([^@]*\)@.*|\1|' | head -1)

if [ -z "$TOKEN" ]; then
    echo "[ERROR] No GitHub token found"
    exit 1
fi

# Clone仓库
git clone "https://${TOKEN}@github.com/ydl811811/longzhua.git" "$WORK_DIR" 2>/dev/null

# 同步soul文件
cp -f ~/.hermes/memories/SOUL.md "$WORK_DIR/soul/" 2>/dev/null
cp -f ~/.hermes/memories/MEMORY.md "$WORK_DIR/soul/" 2>/dev/null
cp -f ~/.hermes/memories/USER.md "$WORK_DIR/soul/" 2>/dev/null

# 同步scripts
cp -f ~/.hermes/scripts/*.sh "$WORK_DIR/scripts/" 2>/dev/null

cd "$WORK_DIR"
git add -A
git commit -m "Auto backup - $(date '+%Y-%m-%d %H:%M')" 2>/dev/null
git push 2>/dev/null

# 清理
rm -rf "$WORK_DIR"
echo "[OK] Backup completed at $(date)"
