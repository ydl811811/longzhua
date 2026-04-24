# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:
- Camera names and locations
- SSH hosts and aliases  
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras
- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH
- home-server → 192.168.1.100, user: admin

### TTS
- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## 🔍 搜索工具配置 (更新于2026-04-13)

### 第一搜索工具: Multi Search Engine
- **主要引擎**: DuckDuckGo (默认)
- **备用引擎**: Tavily Search (需要API密钥)
- **国内引擎**: 百度、必应中国、360、搜狗等
- **脚本路径**: `/home/yu/.openclaw/workspace/scripts/multi_search.py`

### 使用优先级
1. **Multi Search Engine** - 首选，多引擎支持
2. **Tavily Search** - API搜索，结果质量高
3. **OpenClaw内置web_search** - 备用
4. **Agent Browser** - 网页自动化时使用

### 快速搜索命令
```bash
# 使用Multi Search Engine
python3 ~/.openclaw/workspace/scripts/multi_search.py --query "搜索内容" --engine duckduckgo

# 使用Tavily搜索
python3 ~/.openclaw/workspace/skills/tavily-search/scripts/tavily_search.py --query "搜索内容"

# 使用特定引擎
python3 ~/.openclaw/workspace/scripts/multi_search.py --query "内容" --engine baidu
```

### API密钥配置
- **Tavily API**: 已配置在 `~/.openclaw/.env`
- **密钥**: `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`

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
