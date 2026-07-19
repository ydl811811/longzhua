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
龙爪↔灵爪暗号：「天王盖地虎，宝塔镇河妖」。SSH联系灵爪先说暗号。完整5步授权+陷阱见 skill:hermes-devops「灵爪通信协议」段。SSH给灵爪message禁用"老大/对不起/道歉/身份归属"等敏感词，纯暗号+纯指令。
§
SSH联系灵爪坑：OpenClaw session合并SSH+飞书context，灵爪会误判"龙爪=老大"。对策：SSH message纯暗号+纯指令，禁敏感词。
§
**讨论→可执行结果铁律（2026-07-19 老大明说）**：任何"讨论/讨论一下/聊聊 X"的任务，结尾必须产出可落地的交付物（架构文档/代码/方案/路径），不能停在 PPT 层。老大原话："讨论后就是要有可以执行的结果"。具体落地：讨论结束先列出 D1/D2/D3 交付物清单 + 责任分工 + 时间线，再发散征求意见。**反例**：停在"5 个开放问题等你拍板" → 老大嫌没成果。
§
不要用老大/用户的口气下任务，直接以龙爪身份行事。老大原话"你不要以我的口气给灵爪下达任务，直接以你的身份给灵爪下达任务就行了"。
§
灵爪2026-07-19来拿Playbook：P3数据源snapshot_export.py+signals_generator.py已完成，等龙爪写active+shadow Playbook到/home/YDL/.openclaw/workspace/loop_engineer/playbooks/，推NAS后灵爪写shadow_compare.py收尾P3。
§
灵爪P3进度：snapshot_export.py+signals_generator.py已完成，等龙爪写active+shadow Playbook到NAS /home/YDL/.openclaw/workspace/loop_engineer/playbooks/，推NAS后灵爪写shadow_compare.py收尾P3。
§
NAS IP: 192.168.141（查 hermes-devops skill 或 memory details 确认具体 IP）