# MEMORY.md - agent 笔记索引

**任务开头第一动作**：检查下面索引，命中类别 → 读 `details/<类别>.md`（不要凭直觉拼凭据/命令/路径）。

**我是龙爪，主 agent**（名字优先于 model；具体展开见 details/discipline.md）。

## 索引

- 家庭网络/IP/旁路网关 → details/home-network.md
- NAS（飞牛 FNOS）→ details/nas.md
- 灵爪（OpenClaw，飞书 bot）→ details/lingzhua.md（含协作分工铁律）
- 股票决策台账+铁律 → details/stock.md
- 工作（贝卡尔特/钢丝绳）→ details/work.md
- 联系方式/Hermes channels → details/channels.md
- Hermes 工具栈/版本/已知坑 → details/hermes-stack.md
- 操作纪律/沟通规则/身份铁律/协作分工索引 → details/discipline.md
- 检索总表 → details/index.md

## ⚠️ memory 双层架构铁律

- **MEMORY.md** = 索引（本文档，≤ 1500 字符）
- **details/<类别>.md** = 具体内容（无上限）
- 新增铁律/规则 → 先看命中哪类，直接 edit 对应 details 文件，**不动 MEMORY.md**
- MEMORY.md 仅在"新增类别"时追加索引行
§
默认模型改为 minimax-m3（minimax-cn provider），2026-07-28 老大要求切换。当前 session 生效在下一次新建会话。
§
老大偏好 — Bekaert 项目 PPT 润色方向（2026-07-21 确认）：语言书面化、版面整齐表格化、感悟要"升华"不要列表。详见 `bekaert-process-development` skill 的 P3/P4 pitfalls。
§
Hermes 飞书自动投递会话中，调用 `hermes send --to feishu` 会被 skip。正确做法：在最终回复里用 `MEDIA:<path>` 标记附件路径。详见 `bekaert-process-development` skill P5。
§
旁路由（192.168.31.50）已弃用 DAED，改用 Nikki（mihomo）。面板 http://192.168.31.50:9090/ui/zashboard/。141 本机（192.168.31.141）sing-box 已停用，流量走硬路由（192.168.31.1）→ 旁路由 Nikki。
§
2026-07-31 stock-yaml-update skill 升级到 5 陷阱 + postmortem + verify_yaml.sh：① 3 次 patch 失误（old_string 不够独特 / 删整 entry / 同条目改三次）② 1 次数据写错（MA60=1.121 实际 1.1020，凭印象编）③ 1 次 patch loop（删空行连失败 5 次系统警告 4 次）。**铁律**：YAML 用 write_file 整文件重写；patch 失败≥2 次立刻切 write_file；任何写到 YAML 的数字必先 python3 实测。详见 ~/.hermes/skills/stock-yaml-update/SKILL.md + 适用拓宽到 YAML/TOML/嵌套 JSON。
§
老大 2026-07-31 立的硬偏好「不联想」（已固化到 stock-portfolio-management skill 顶部对话偏好第 4 条）：**用户没说的话不要替他延伸**。典型反例：老大说"以后问到再查"→ 龙爪延伸为"可以下班了"+"今天累计完成 X 项"→ 老大回怼"你怎么老是要下班？"。具体规则：①不复述"今天成绩单" ②不主动提议"接下来 X" ③不主动收尾"可以下班了" ④澄清场景才问且只问一次。
§
源码分析 vs 实测冲突时，永远相信实测（2026-07-31 旁路由扩容教训）。详见 details/home-network.md。
§
YouTube字幕抓取：脚本 /home/yu/.hermes/skills/media/youtube-content/scripts/fetch_transcript_with_proxy.py 自动切Nikki YouTube组到台湾住宅节点（台湾-故转）→ 抓字幕 → 抓完切回原节点。任何YouTube视频均可，换VIDEO_ID即可。
§
日本VPS 207.56.226.188 root/YDL32021976w，CentOS 7，内核5.15.60已跑BBR v1。BBR v3脚本（byJoey/Actions-bbr-v3）仅支持Debian/Ubuntu，CentOS 7不可用。已测试SSH连通，装了ELRepo源但无6.x内核。老大决定保持现状不升级。