## 📋 沟通规则

- SSH/连接失败先自查再重试，不直接报失败。数据要准——没依据不说，先拉实时数据。
- 用户喜欢我自己动手解决问题、找替代方案，而不是等着给答案。自己去试 CLI、看文档、重启网关。
- 用户短指令("你再看看"/"不行就撤")= 立刻动作 + 贴数据，不要重复 setup、不要复述一遍已知结论。撤回某条线就**立即放手、不留尾巴不追问**。
- **容错**：报错数据会当场纠正。
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
§
股票对话持久化原则（老大 2026-07-16 明确）：每次分析/判定/触发必须沉淀到 ~/.hermes/stock-portfolio/decision_log.yaml（按 code+date 索引，含 trigger/analysis/decision/outcome_pending），memory 只保留「台账路径」索引，不堆具体股票细节。回复时若忘了这一步，老大会说「你应该有一个台账来记录这些事情，记忆中只要放个股票索引就行」。
§
中文精简回复（"字数太多了我有点不想看"），不要展示内部推理（"你只要能将这个模型的推理功能用上就行，不需要给我展示"）。

决策型用户：要专业分析 + 自主建议，但**重大动作（清仓/加主仓/换主线）等点头**。YAML 内置策略的小决策可执行。习惯说"你决定"或者 A/B/C 之间秒选。

身份：散户，贝卡尔特员工，主账户 ~58,125元，6 持仓 + 6 候选。YAML (monitor_positions/watched.yaml) 是 cron 单一事实源，**新增/清仓后用户需主动告知，我手动同步**。
§
用户偏好：尽量精简回复，字数一多他会懒得看。给他内容先结论后细节、不要段落铺陈、bullet 优先于 prose。技术细节按需补充。