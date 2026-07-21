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
**股票账户信息（2026-07-20）**：本金 ~6万。持仓 6 只 ETF：159869 游戏ETF华夏（-1.74%）、516010 游戏ETF国泰（+1.23%）、588080 科创50ETF（-17.99% 深套）、513050 中概互联网ETF（+2.90%）、513120 港股创新药ETF（平本）、159928 消费ETF（+3.52%）。已清仓：000783 长江证券（7/17 于 8.67 清仓）。⚠️ 科创50ETF 成本 2.146（高点买入），现价 1.760，浮亏 -18%，止损位 1.640。指数本身是 2026 年最强指数（年初至今 +70%），但用户买在高点。补仓决策待明天开盘后拉数据再定。
§
灵爪 09:12 三问拍板请求：(1) signals_generator.py 路径谁改 (2) config_paths.py 范围 (3) 8:30 cron 是否暂缓。灵爪已回滚 signals_generator.py 到原 3 行硬编码，scp 同步到本地。decision_engine.py 仍在用 /home/YDL/ 直写而非 config_paths。
§
灵爪 09:12 问的 signals_generator.py 在龙爪本地不存在（/home/yu/.hermes/stock-portfolio/loop_engineer/scripts/ 下只有 gen_signals.py, export_snapshot.py, p3_shadow_compare.py）。灵爪说"已回滚并 scp 同步到你本地 scripts/"，但实际未同步到或文件名不同。
§
老大问早盘市场风向扫描是否失效 — 需检查 cron 任务状态
§
晨报脚本 `morning_scan.py` 已从 NAS 迁移回本地，简化版（无 NAS 路径依赖），cron job 固定 minimax-m3 provider。
§
老大强调"不要凭直觉下结论"（2026-07-21 PPT 教训）：当老大说"我把15页发给你，你说没内容"时，是因为我之前看错了页码，把第20页误判为第15页空章节页。规则：分析截图/PPT/文档时，必须以"页面右下角页码数字"为准，不要凭图片内容相似度推断页码；遇到"Subtitle 占位符未填"等结论前，先核对页码是否正确。引用：~/.hermes/details/discipline.md "老大决策模式"段已记录"老大 2026-07-21 现场表达两个 first-class 偏好"，本条扩展第三项——重视准确性。
§
老大偏好 — Bekaert 项目 PPT 润色方向（2026-07-21 确认）：语言书面化、版面整齐表格化、感悟要"升华"不要列表。详见 `bekaert-process-development` skill 的 P3/P4 pitfalls。
§
Hermes 飞书自动投递会话中，调用 `hermes send --to feishu` 会被 skip。正确做法：在最终回复里用 `MEDIA:<path>` 标记附件路径。详见 `bekaert-process-development` skill P5。