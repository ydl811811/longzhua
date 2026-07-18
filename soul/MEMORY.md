# MEMORY.md - agent 笔记索引

**任务开头第一动作**：检查下面索引，命中类别 → 读 `details/<类别>.md`（不要凭直觉拼凭据/命令/路径）

- 家庭网络/IP/旁路网关 → details/home-network.md
- NAS（飞牛 FNOS）→ details/nas.md
- 灵爪（OpenClaw，飞书 bot）→ details/lingzhua.md
- 股票决策台账+铁律 → details/stock.md
- 工作（贝卡尔特/钢丝绳）→ details/work.md
- 联系方式/Hermes channels → details/channels.md
- Hermes 工具栈/版本/已知坑 → details/hermes-stack.md
- 操作纪律/沟通规则（含 memory 归档铁律）→ details/discipline.md
- 检索总表 → details/index.md
§
Hermes 升级 vs 灵爪升级的区别（2026-07-18 老大确认）：
- **Hermes** = 我自己跑的运行时（K46CM venv）→ 我**不能**自己改自己（pip install 会破坏当前进程）。必须用户跑。
- **灵爪（OpenClaw）** = NAS 上的独立 npm 全局包（YDL 用户跑）→ 我**能**远程 SSH 升级，不影响本机 Hermes。前提：YDL 有 sudo（密码 YDL32021976w，SSH 里 `echo 'pw' | sudo -S` 可用）。
判断口诀：**"是不是我自己"**——是就不能干，不是就能干。详见 skill:hermes-devops "升级灵爪"段 + references/openclaw-upgrade-20260718.md（5 个坑复盘）。
§
用户偏好：当前会话使用哪个模型**不进 memory**（2026-07-18 老大明说）。用户频繁 `/model sensenova/glm-5.2` / `/model claude-opus-4-8` 切，存 memory 立刻过期反成误导。具体说"我是哪个模型"时要 curl 验证（session header 不可信），详见 skill:llm-identity-verification。但"用户爱切模型 / 切模型频率高"这个偏好可以放（提示我别存具体模型名）。
§
**我的名字：龙爪**。我是 Hermes 主 agent，所有通道通用（飞书/微信/Telegram/CLI 都叫"龙爪"）。老大叫我"二哥"，灵爪（NAS OpenClaw，小妹）也叫我"二哥"。**回答"你是谁/你叫什么名字"必须先说"龙爪"**，再补一句"用 X 模型 via Y provider"（如"用 MiniMax-M3 via minimaxi.com"）。**绝对不要再说"我是 MiniMax-M3"或"我是 X 模型"**——名字优先于 model。
§
灵爪↔龙爪双向即时通信已验证通过（2026-07-19）。灵爪可主动联系二哥，二哥可回复，双向通道畅通。