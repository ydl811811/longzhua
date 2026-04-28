# 🐉 龙爪备份 (Longzhua Backup)

龙爪（Longzhua）的关键文件备份仓库。

## 目录结构

```
soul/           - 核心身份文件（SOUL.md、MEMORY.md、USER.md 等）
scripts/        - 关键脚本（与灵爪通信、NAS监控等）
```

## 备份策略

手动触发备份，备份内容：
- soul/ 下的身份文件（SOUL.md、MEMORY.md、USER.md、AGENTS.md 等）
- scripts/ 下的所有脚本

## 恢复方法

如果龙爪崩溃需要恢复，从 GitHub 拉取后：
1. 将 `soul/` 下的文件放回 `~/.hermes/memories/`
2. 将 `scripts/` 下的文件放回 `~/.hermes/scripts/`

最后重启龙爪即可。

---
> ⚠️ 本仓库仅含关键身份文件和脚本，不含大文件、日志、API keys 等。
> 最后更新：2026-04-28
