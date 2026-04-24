# 🐉 龙爪备份 (Longzhua Backup)

龙爪（Longzhua）的关键文件备份仓库。

## 目录结构

```
soul/           - 核心身份文件（AGENTS.md, SOUL.md, MEMORY.md 等）
scripts/        - 关键脚本（与灵爪通信、NAS监控等）
core_services/  - 核心服务代码（AData API 等）
memory/         - 近期记忆日志
```

## 恢复方法

如果龙爪崩溃需要恢复，从 GitHub 拉取后：
1. 将 `soul/` 下的文件放回 `~/.openclaw/workspace/`
2. 将 `scripts/` 下的文件放回 `~/.openclaw/workspace/scripts/`
3. 将 `core_services/` 下的文件放回 `~/.openclaw/workspace/`

最后重启 OpenClaw 网关即可。

---

> ⚠️ 本仓库仅含关键文件，不含大文件（如 avatar.png、日志文件等）。
> 最后更新：2026-04-24
