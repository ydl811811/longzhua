# ⚠️ 老索引归档（2026-07-20 起被 MEMORY.md 取代）

> **2026-07-20 整理后，主索引迁到 `~/.hermes/memories/MEMORY.md`**（每次 session 由 system prompt 自动注入）。
>
> 本文保留作为检索总表 + 维护原则备忘，方便人工 audit 时对照。

## 当前索引（9 个类别，跟 MEMORY.md 一致）

| 类别 | 详情文件 |
|---|---|
| 家庭网络 / 设备 IP / 旁路网关历史 | `details/home-network.md` |
| NAS（飞牛 FNOS / Docker / TV-box） | `details/nas.md` |
| 灵爪（OpenClaw / NAS 上的 AI 助手 / 协作分工铁律） | `details/lingzhua.md` |
| 股票（决策台账 + 操作铁律 + 本金） | `details/stock.md` |
| 工作（贝卡尔特 / 钢丝绳 / BFM 机型 / DP1-DP7） | `details/work.md` |
| 联系方式 / Hermes 平台 channels | `details/channels.md` |
| Hermes 工具栈（版本 / 限制 / 已知坑 / 升级区别） | `details/hermes-stack.md` |
| 操作纪律 / 沟通规则 / 身份铁律 / 自主决策 | `details/discipline.md` |
| 检索总表（本文件） | `details/index.md` |

## 检索模式

- 用户问 X 相关的事 → **先看 MEMORY.md 索引**（system prompt 自动注入）→ 读对应 `details/<x>.md`
- 多类别话题 → 读多个详情文件
- 找不到 → 可能是新领域，写一个新详情文件并加到 **MEMORY.md** 索引

## 维护原则

- **MEMORY.md / USER.md 都是索引层**，永远保持精简（当前 ≤ 1500 chars）
- 详细数据放 `details/`，可以无限膨胀
- 任何会话结束后新增的事实 → 写到对应 `details/<类别>.md`，**不写** MEMORY.md 索引行（除非新增类别）
- 索引的每一行**必须**指明详情文件路径，缺一不可
- **禁止同一事实写多处**（容易不同步）→ 单一事实源原则
- 详见 `details/discipline.md`「📂 Memory 归档铁律」段

## 历史

- 2026-07-20 整理：MEMORY.md 重写为极简索引（1126 chars），本文件标为"老索引归档"
- 2026-07-18 创建本索引文件
- 2026-07-19 加入 discipline.md 引用