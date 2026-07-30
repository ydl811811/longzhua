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
老大强调"不要凭直觉下结论"（2026-07-21 PPT 教训）：当老大说"我把15页发给你，你说没内容"时，是因为我之前看错了页码，把第20页误判为第15页空章节页。规则：分析截图/PPT/文档时，必须以"页面右下角页码数字"为准，不要凭图片内容相似度推断页码；遇到"Subtitle 占位符未填"等结论前，先核对页码是否正确。引用：~/.hermes/details/discipline.md "老大决策模式"段已记录"老大 2026-07-21 现场表达两个 first-class 偏好"，本条扩展第三项——重视准确性。
§
老大偏好 — Bekaert 项目 PPT 润色方向（2026-07-21 确认）：语言书面化、版面整齐表格化、感悟要"升华"不要列表。详见 `bekaert-process-development` skill 的 P3/P4 pitfalls。
§
Hermes 飞书自动投递会话中，调用 `hermes send --to feishu` 会被 skip。正确做法：在最终回复里用 `MEDIA:<path>` 标记附件路径。详见 `bekaert-process-development` skill P5。
§
灵爪协作（2026-07-23 老大确认）：龙爪可 SSH 调灵爪，无需老大飞书私信授权。patch 工具不可靠（2026-07-23 教训：每改一处必 grep 时间戳验证，sed 比 patch 稳）。AmazingData 试用 2026-07-10 至 2026-08-09（账号 334500028836 / 120.86.124.106:8600），查询可用但实时推送 WebSocket 连不上。详情见 details/lingzhua.md + ~/.hermes/config/amazingdata_credentials.yaml。
§
龙爪在 2026-07-23 下午 AmazingData 调研中踩坑：报告"数据源能用 N 类数据"前必须实测每个 API 拿返回值列成表格，不能基于"理论上有 SDK"就推断能拿 N 类数据。同样的纪律要应用到未来所有数据源调研（通达信 MCP / akshare / tushare）。详见 loop-engineer-trading SKILL.md §22。
§
老大偏好: 数据源测试必须标接口名（2026-07-24）。用户提"新买的接口" → 先标名再报数据。配套: xianyu-tushare skill。
§
旁路由（192.168.31.50）已弃用 DAED，改用 Nikki（mihomo）。面板 http://192.168.31.50:9090/ui/zashboard/。141 本机（192.168.31.141）sing-box 已停用，流量走硬路由（192.168.31.1）→ 旁路由 Nikki。
§
141 是给龙爪的宿主机，老大主笔记本是 156（Windows，Realtek 网卡）。股票分析：数据+趋势我给，**交易参数老大定**（a-share-research skill 已写）。