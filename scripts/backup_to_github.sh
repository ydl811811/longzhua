#!/bin/bash
# 龙爪 → GitHub 备份脚本（修复版，2026-09-26）
# 原版本使用 '***' 替换真实 token，导致 git clone 静默失败
# 现改用 GitHub Contents API 推送，无需 git 网络出口（沙箱可访问 api.github.com）
exec /usr/bin/env python3 "$HOME/.hermes/scripts/backup_to_github.py" "$@"
