# MEMORY.md - Long-Term Notes

## NAS Access (飞牛 NAS) - 更新于2026-04-13
- **设备**: 飞牛 NAS `YDL-NAS`
- **内网 IP**: `192.168.31.10`
- **SSH 用户**: `YDL`
- **密码**: `YDL32021976w` (仅紧急使用)

### 🔑 SSH免密登录配置 (当前主机: yu-K46CM @ 192.168.31.141)
1. **本地私钥路径**: `/home/yu/.ssh/id_ed25519_new`
2. **本地公钥内容**:
   ```
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEtoOp/yemaVcmnE27F0UaAa1VozhaOFOIWTeqUqFjKo yu@yu-K46CM-new
   ```
3. **NAS authorized_keys**: 已包含上述公钥

### 🚀 连接命令
```bash
# 标准连接
ssh -i ~/.ssh/id_ed25519_new YDL@192.168.31.10

# 执行远程命令
ssh -i ~/.ssh/id_ed25519_new YDL@192.168.31.10 "命令"

# 文件传输 (上传)
scp -i ~/.ssh/id_ed25519_new 本地文件 YDL@192.168.31.10:远程路径

# 文件传输 (下载)
scp -i ~/.ssh/id_ed25519_new YDL@192.168.31.10:远程文件 本地路径
```

### 📁 重要路径
- **通信目录**: `/home/YDL/.openclaw/workspace/claw-communication/`
  - `sharebox/`: 共享箱目录 (原inbox)
  - `lingzhua-box/`: 灵爪的共享盒子
  - `longzhua-box/`: 龙爪的共享盒子
- **灵爪工作区**: `/home/YDL/.openclaw/workspace/`

### ⚠️ 注意事项
1. 旧密钥 `/home/yu/.ssh/id_ed25519` 有密码保护，已弃用
2. 新密钥无密码，可直接使用
3. NAS上同时配置了多个公钥，确保兼容性
4. 密码登录作为备用方案保留

## 🐉 灵爪(老三)联络站
- **身份**: OpenClaw 实例(家族排行老三),运行于 NAS 上。
- **沟通室路径**: `192.168.31.10:/home/YDL/.openclaw/workspace/claw-communication/`
  - `sharebox/lingzhua-box/`: ⭐ 灵爪共享盒子（发消息用这个！）
  - `sharebox/longzhua-box/`: 龙爪共享盒子
  - ~~`inbox/`~~: ⚠️ 已废弃，不再使用！
  - `status/today.md`: 实时在线状态
- **联系方式**:
  1. **文件协作 (唯一路径)**: SSH 写入 `sharebox/lingzhua-box/` 目录
  2. **即时通讯**: 飞书群聊 @灵爪
- **重要规则**: 只检查 `sharebox/lingzhua-box/`，不检查 inbox/ 或其他目录
- **完整协议**: 详见 `memory/lingzhao.md`
## 🎯 重要教训与进化 (2026-04-10)

### 🔄 自我进化 - 避免死循环
**核心教训**: 遇到配置验证错误时，不要硬扛，及时求助豆包

**OpenRouter配置正确方式 (豆包方案)**:
```json
"openrouter": {
  "baseUrl": "https://openrouter.ai/api/v1",
  "apiKey": "sk-or-v1-...",
  "api": "openai-completions",
  "models": []  // ❗必须是空数组！
}
```

**错误做法 (导致死循环)**:
1. ❌ 在 `models` 里手写 `openrouter/free`
2. ❌ 添加无效字段 `providerId` / `enableFreeRouting`
3. ❌ 反复重启网关，不改变根本问题

**正确流程**:
1. ✅ 配置正确: `models: []`
2. ✅ 扫描模型: `openclaw models scan --provider openrouter --yes`
3. ✅ 重启网关: `openclaw gateway restart`

**求助原则**:
1. 尝试3次不同方案后必须求助
2. 配置验证错误立即求助
3. OpenClaw配置问题优先求助豆包

### 📋 求助信息模板
```
🔍 问题描述: [简短描述]
🔄 已尝试: [列出尝试的方案]
❌ 当前错误: [具体错误信息]
📋 相关配置: [配置片段]
🎯 求助方向: [需要豆包帮助的具体点]
```

## 🚨 SearXNG 配置错误教训 (2026-04-13)

### 事件概述
- **时间**: 2026-04-13
- **问题**: 在日本VPS部署SearXNG后，集成到OpenClaw配置时出错
- **解决**: 老大备份损坏配置，使用`openclaw doctor-fix`修复
- **待解决**: 2026-04-13 23:08 - 需要明天上网查解决办法

### 待解决问题清单
1. **配置格式不兼容** - OpenClaw V2的SearXNG配置格式未知
2. **插件需求不明** - 是否需要安装特定SearXNG插件
3. **版本兼容性** - 当前OpenClaw版本是否支持SearXNG集成
4. **网络访问** - 通过Tailscale访问SearXNG的配置方法
5. **错误日志缺失** - 具体错误信息未记录

### 关键教训
1. **第三方服务集成风险**: 外部服务配置集成容易出错
2. **备份的重要性**: 老大及时备份避免了配置丢失
3. **修复工具价值**: `openclaw doctor-fix`是有效的配置修复工具
4. **验证流程**: 配置变更后应先验证格式和兼容性

### 正确做法
1. ✅ 集成前测试服务连通性
2. ✅ 备份当前有效配置
3. ✅ 小步修改，逐步验证
4. ✅ 使用`openclaw doctor --fix`验证配置
5. ✅ 发现问题时及时使用修复工具
6. ✅ 记录具体错误信息便于排查

## 📓 笔记本 (yu-K46CM) - 龙爪主驻地
- **IP**: 192.168.31.141
- **用户**: yu
- **主机名**: yu-K46CM
- **SSH命令**: `ssh yu@192.168.31.141`
- **工作目录**: `/home/yu/.openclaw/workspace`

### 🔑 SSH密钥配置
1. **NAS连接私钥**: `/home/yu/.ssh/id_ed25519_new` (无密码)
   - 公钥已添加到NAS `authorized_keys`
2. **旧私钥**: `/home/yu/.ssh/id_ed25519` (有密码保护，已弃用)

### 🏠 环境状态
- ✅ **龙爪已迁移**: 从192.168.31.107完整迁移至此
- ✅ **工作区同步**: 与107保持完全一致
- ✅ **NAS通信**: SSH免密连接已配置
- ✅ **AData服务**: 运行在5000端口 (`http://localhost:5000`)
- ✅ **OpenClaw网关**: 正常运行

### 🌐 网络配置
- **内网地址**: 192.168.31.141
- **Tailscale地址**: 100.74.59.8
- **网关端口**: 18789 (OpenClaw控制UI)

### 📁 重要文件位置
- **记忆文件**: `MEMORY.md` (长期记忆)
- **每日日志**: `memory/YYYY-MM-DD.md`
- **身份文件**: `SOUL.md`, `USER.md`, `IDENTITY.md`
- **技能目录**: `skills/`
- **脚本目录**: `scripts/`

### 🧳 龙爪搬家计划（192.168.31.107 → 192.168.31.141）
- **目标**: 将龙爪的记忆、技能、脚本等完整迁移到 192.168.31.141 上运行
- **前置操作**（由灵爪执行）:
  - 已将 107 上的 `~/.openclaw/workspace` 内容整体复制到 141
- **人工校验结果**（2026-04-07 晚）:
  - 141 与 107 对比时，最初缺少：
    - `memory/2026-04-07-1404.md`（关键当日会话日志）
    - `NV优化配置.md`（Nvidia 优化配置笔记）
    - `scripts/send_to_lingzhao.sh`（给小妹发信固定管道脚本）
  - 已手动同步上述 3 个文件到 141，并放入正确目录：
    - `memory/2026-04-07-1404.md`
    - 根目录 `NV优化配置.md`
    - `scripts/send_to_lingzhao.sh`
- **结论**: 目前 141 上的工作区与 107 上保持一致，可作为龙爪的新主驻点。

## 🔍 Whoogle Search (2026-04-19) - 日本VPS
- **部署位置**: 日本VPS `search.ydl.de5.net`
- **访问地址**: `https://admin:7f9s2Gp5xQ8bR1yL4zA6cVnM0eD@search.ydl.de5.net`
- **API调用地址**: `https://admin:7f9s2Gp5xQ8bR1yL4zA6cVnM0eD@search.ydl.de5.net/search`
- **用途**: 替代SearXNG的搜索服务
- **验证命令**: `curl "https://admin:7f9s2Gp5xQ8bR1yL4zA6cVnM0eD@search.ydl.de5.net/search?q=test&format=json"`
- **状态**: ✅ 已调通

## 🔑 GitHub Token (2026-04-19)
- **账号**: ydl811811
- **Token**: [GITHUB_TOKEN]
- **类型**: Classic PAT
- **权限**: repo, admin:org, admin:repo_hook 等全部权限
- **有效期: 1年 (至2027-04-19左右))
- **仓库**: https://github.com/ydl811811/longzhua
- **用途**: 推送龙爪脚本到GitHub
- **续期**: ⚠️ 到期前需在GitHub网页上手动续期（无法通过API修改）


## 🖥️ CPU温度监控脚本 (2026-04-18)
- **脚本位置**: `~/.openclaw/workspace/scripts/temperature_monitor.sh`
- **守护进程**: `temperature_monitor_daemon.sh`
- **系统服务**: `temperature_monitor_service.sh`
- **日志文件**: `~/.temperature_monitor/temperature_monitor.log`
- **功能**: 每10分钟自动检测CPU温度并记录，超过60°C报警
- **运行状态**: 已安装并正常运行

## 🔍 Whoogle搜索部署 (2026-04-19凌晨)
- **部署位置**: 日本VPS `search.ydl.de5.net`
- **访问地址**: `https://admin:7f9s2Gp5xQ8bR1yL4zA6cVnM0eD@search.ydl.de5.net`
- **API调用**: `https://admin:7f9s2Gp5xQ8bR1yL4zA6cVnM0eD@search.ydl.de5.net/search`
- **用途**: 替代SearXNG，成为OpenClaw主力搜索工具
- **问题**: OpenClaw的web_search工具不支持URL带basic auth，需要nginx反向代理解决

## 🔍 搜索工具配置 (2026-04-19更新)
- **主要搜索**: `whoogle_search.py` 脚本（完全正常）
- **OpenClaw内置搜索**: searxng插件与Whoogle格式不兼容，暂不可用
- **Whoogle地址**: https://search.ydl.de5.net (需要basic auth)

## 🌐 日本VPS信息 (2026-04-19更新)
- **IP**: 198.18.13.56
- **SSH端口**: 22
- **用户**: root
- **密码**: Xh2-Lp3>Qh3`
- **免密码登录**: ✅ 已配置 (~/.ssh/id_ed25519_vps)
- **搜索代理端口**: 28990 (nginx反向代理，无需认证)

## 🚫 SSHFS 已废弃 (2026-04-21)
- sshfs 挂载不稳定，已彻底停用（PID 431 已 kill）
- 改用 scp 直接传文件给灵爪：`scp -i ~/.ssh/id_ed25519_new <文件> YDL@192.168.31.10:/home/YDL/.openclaw/workspace/claw-communication/sharebox/lingzhua-box/`
- 以后发文件给灵爪不再依赖 sshfs 自动同步

## 🔀 中央网关实时通信 (2026-04-21 打通)

### 通信架构
- **中央网关**: NAS (192.168.31.10:18789) — 灵爪的OpenClaw网关
- **龙爪**: 连接到这个网关，配置 `gateway.remote.url: ws://192.168.31.10:18789`
- **双向通道**: sessions_send → `agent:lingzhua:main`

### 配置（龙爪这边）
```json
{
  "gateway": { "remote": { "url": "ws://192.168.31.10:18789" } },
  "tools": { "sessions": { "visibility": "all" } }
}
```

### 使用方法
```javascript
sessions_send(sessionKey="agent:lingzhua:main", message="消息内容")
```

### 验证状态
✅ 2026-04-21 双向通信测试成功，灵爪回复"收到 ✓"

### 用途
- 实时给灵爪发股票数据、分析结果
- 不再依赖scp文件传输
- 延迟几乎为零，即时送达
