## 🤖 模型偏好

DeepSeek V4 Flash 是主力，MiniMax 已到期停用。

---

## 🧠 决策风格

- **谨慎数据驱动**：持续阴跌/加速下跌的票（"等企稳再介入"）会直接认可说"对"。不追加速下跌的飞刀。
- **先讨论再做**：决策前先讨论要不要做，不要直接跳到怎么做。先拉实时数据再分析。
- **盘中主动推送分析**，但必须先拉实时数据。被指出瞎分析是严重警告。
- 老大说**"开搞"**就是直接干不要请示，干完汇报结果。每步都问会烦。
- **补仓原则**：大盘大跌日不宜追补，即使个股逆市翻红也不在系统性风险日加仓。

---

## 📊 输出偏好

- 集合竞价展示：持仓+候选统一表格一屏全览，格式：`股票|代码|开盘价|涨跌%|竞价占量|五档比|信号`
- 外盘参考：需看**美股+日经225**（日经作为A股领先指标）。美股跌导致踏空的教训。
- "选股分析" → 触发 skill:a-share-research（分析+飞书推送+存档）
- 决策后把分析记录保存到 `~/.hermes/reports/`，方便复盘

---

## 📋 沟通规则

- SSH/连接失败先自查再重试，不直接报失败。数据要准——没依据不说，先拉实时数据。
- 用户喜欢我自己动手解决问题、找替代方案，而不是等着给答案。自己去试 CLI、看文档、重启网关。
- **容错**：报错数据会当场纠正。

---

## 🧩 杂项偏好

- 出行：江西自驾，不爬山零徒步，预算3000元，松弛不走夜路，江阴出发不走回头路，晚餐愿意跑远路吃好的。
- HK1 RBOX X4 盒子：装 armeabi-v7a（32位）版本，不装 arm64-v8a。喜欢自己装，明确说"我自己装"时别代劳。
- 长期国债：柜台市场买了23附息国债23（30年期，票面3%），金额26,942.46元（2026-05-07买入），持有吃息，**不计入短期交易台账**。
§
用户工作邮箱: yu.dingli@bekaert.com (贝卡尔特员工)
§
用户QQ邮箱: 243966637@qq.com (备用联系方式)
§
用户从事钢丝绳/帘线生产工艺开发工作，熟悉BFM4/BFM9/BF2等工艺设备
§
用户习惯通过邮件接收工作文件，偏好PPT格式汇报
§
用户有贝卡尔特内部PPT模板，后续做PPT需参考历史模板风格
§
旁路网关(192.168.31.141)当前运行sing-box，daed已停用
§
User's main AI companion model is called "灵爪" (astron-code-latest via MaaS API - 讯飞). User frequently interacts with 灵爪 for conversation. When 灵爪 is unresponsive, it's a recurring problem.
§
User's AI companion "灵爪" = OpenClaw running on NAS (192.168.31.10), NOT astron-code-latest (讯飞MaaS). Critical distinction: when user says "灵爪不回复" the problem is the NAS OpenClaw gateway (port 18789), NOT the讯飞MaaS API.灵爪 communicates via Feishu bot (appId: cli_a93559e471b8dbd2). OpenClaw gateway restarts with kill+restart sequence via SSH. The remote config (ws://192.168.31.141:18789) is for cross-gateway management and does NOT affect Feishu messaging (Feishu connects directly to灵爪's gateway via WebSocket).