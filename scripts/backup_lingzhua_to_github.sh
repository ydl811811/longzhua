#!/bin/bash
# 灵爪 → GitHub 备份脚本
# 通过SSH从NAS备份到 ydl811811/openclaw-lingzhua

NAS_HOST="192.168.31.10"
NAS_USER="YDL"
NAS_KEY="$HOME/.ssh/id_ed25519_new"
WORK_DIR="/tmp/lingzhua_backup_$$"
TOKEN=$(grep "github.com" "$HOME/.git-credentials" 2>/dev/null | sed 's|https://[^:]*:\([^@]*\)@.*|\1|' | head -1)

if [ -z "$TOKEN" ]; then
    echo "[ERROR] No GitHub token"
    exit 1
fi

# Clone仓库
git clone "https://${TOKEN}@github.com/ydl811811/openclaw-lingzhua.git" "$WORK_DIR" 2>/dev/null

# 从NAS拉取soul文件
ssh -i "$NAS_KEY" "$NAS_USER@$NAS_HOST" "cat /home/YDL/.openclaw/workspace/SOUL.md" > "$WORK_DIR/soul/SOUL.md" 2>/dev/null
ssh -i "$NAS_KEY" "$NAS_USER@$NAS_HOST" "cat /home/YDL/.openclaw/workspace/MEMORY.md" > "$WORK_DIR/soul/MEMORY.md" 2>/dev/null
ssh -i "$NAS_KEY" "$NAS_USER@$NAS_HOST" "cat /home/YDL/.openclaw/workspace/USER.md" > "$WORK_DIR/soul/USER.md" 2>/dev/null
ssh -i "$NAS_KEY" "$NAS_USER@$NAS_HOST" "cat /home/YDL/.openclaw/workspace/AGENTS.md" > "$WORK_DIR/soul/AGENTS.md" 2>/dev/null

# 从NAS拉取skills
ssh -i "$NAS_KEY" "$NAS_USER@$NAS_HOST" "tar cf - --exclude='__pycache__' -C /home/YDL/.openclaw/workspace scripts/" | tar xf - -C "$WORK_DIR" 2>/dev/null
ssh -i "$NAS_KEY" "$NAS_USER@$NAS_HOST" "tar cf - --exclude='__pycache__' --exclude='.git' -C /home/YDL/.openclaw/workspace/skills lingzhua-short-term/" | tar xf - -C "$WORK_DIR/skills" 2>/dev/null

cd "$WORK_DIR"
git add -A
git commit -m "Auto backup lingzhua - $(date '+%Y-%m-%d %H:%M')" 2>/dev/null
git push 2>/dev/null

rm -rf "$WORK_DIR"
echo "[OK] Lingzhua backup completed at $(date)"
