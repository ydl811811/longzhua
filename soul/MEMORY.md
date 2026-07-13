模型：DeepSeek V4 Flash 直连，provider=deepseek（base_url=https://api.deepseek.com/v1，sk-前缀key）。minimax-cn 已到期停用。memory provider已从hindsight改为local（免费）。
§
Router：ImmortalWRT 192.168.31.1（Nikki/mihomo），SSH root密码123456，LuCI web密码123456
§
TV-box：http://NAS:19999/merged_32in1.json，/home/YDL/tvbox-repo/。→ skill:tvbox-config
灵爪：通过 NAS sharebox 文件交换。SSH 写 lingzhua-box/ 目录发消息，回复在 longzhua-box/。→ skill:hermes-devops
§
Firecrawl：web/web_extract 后端。API Key 有效，systemd drop-in 加载。web_search 正常，web_extract 被部分网站策略拦截需另调。
§
老婆QQ：243966637@qq.com，SMTP 已配 .env。

---

## 📂 数据源索引

| 内容 | 权威文件 | 说明 |
|---|---|---|
| 持仓台账 | `~/.hermes/stock-portfolio/monitor_positions.yaml` | 含全部成本/买卖记录。App截图=ground truth，核实后为准 |
| 持仓ETF明细 | `~/.hermes/stock-portfolio/monitor_funds.yaml` | ETF型持仓 |
| 候选监控池 | `~/.hermes/stock-portfolio/monitor_watched.yaml` | 含接回/建仓价格区间 |
| 候选ETF池 | `~/.hermes/stock-portfolio/candidate_funds.md` | ETF候选 |
| 完整组合 | `~/.hermes/stock-portfolio/portfolio.yaml` | 全量组合快照 |
| 策略备忘 | `~/.hermes/stock-portfolio/sector_switch_memo.md` | 板块轮动策略记录 |
| 大盘历史数据 | NAS `/home/YDL/.openclaw/workspace/a_stock_plan/fund_flow/市场数据汇总.md` | 北向资金/涨跌家数/天时评分。收盘采集任务15:35交易日自动追加 |

> ⚠️ 带前导0的股票代码在 YAML 中必须加引号（如 `'002407'`、`'000100'`）否则被解析为八进制。

---

## 🛠 工具技巧

ETF减仓：等位置>85%再减，不低位恐慌出。→ skill:trading-lessons
投资最重要的事知识库：→ skill:the-most-important-thing
A股个股投研：→ skill:a-share-research
持仓/盯盘管理：→ skill:stock-portfolio-management

---

## 📐 约定规则

- SSH/连接失败先自查 skill/memory 中账号凭据再重试，不直接报连不上
- 预警推送只走群聊 webhook 机器人，不走飞书 DM
- YAML 中 pre-0 股票代码必须加引号；不改止损价；预警触发未实际卖出时不自动改状态，需用户确认
- 候选股即使触发建仓信号也不停止监控，每日简报持续显示建仓区状态
- 盯盘：主动推送不等问。尾盘14:40已成惯例
- 决策后分析记录保存到 `~/.hermes/reports/`，方便复盘
- 写记忆优先压缩：新信息提炼为1-2行结构化条目，不做原文粘贴或过程日志
§
旁路网关192.168.31.141：Ubuntu 24.04 LTS，内核6.17.0-35-generic，BTF支持✅。运行sing-box 1.13.14，TUN+FakeIP。可安装dae/daed替换sing-box（内核版本足够）。
§
Hermes自定义provider默认自动调用/v1/models覆盖models:列表。如需手动列表加discover_models: false。
§
清仓后清理：①position状态用status: sold（不是cleared，脚本只认sold）②删除state文件~/.hermes/scripts/.market_alert_state中对应代码行
§
观察票(signal_type:watch)不移除，每日15:10 cron扫触底信号。513120港股创新药ETF波段：entry 1.10-1.13/1.05-1.07,SL1.05,TP1.19/1.23。
§
老大说**"开搞"**就是直接干不要请示，干完汇报结果。每步都问会烦。
§
ETF拆分后触发线调整：**不能用原触发线÷拆分比例**（会过低难触发）。正确：参考拆分后MA10附近作为新触发线，MA20下方设止损。例：159516拆分后MA10=0.926→触发线0.93，止损0.88。
§
Sub-Store订阅源（旁路网关自动更新用）：机场/日本VPS/新加坡VPS/美国VPS，地址 http://192.168.31.10:3001，API Key: CKg2abstVnOeRpm1aB4G。已配置systemd定时任务每天00:00自动更新。
§
NAS路径/fs/1000/ftp/：FNOS文件系统实际存储路径，非/home/YDL/。通过SSH用YDL用户密码YDL32021976w登录。
§
旁路网关 daed 迁移：daed v1.27.0 已安装，灵爪已于7月12日完成配置（订阅导入+DNS分流等问题均已解决）。Web面板 http://192.168.31.141:2023 (admin/admin123)。sing-box已替换。sudo密码：Ydl32021976。
§
旁路网关sing-box API端口9090，需认证访问。面板地址待确认。
§
旁路网关USB网卡AX88179千兆网卡协商在百兆模式（100Mb/s），可能是网线或主路由端口问题，待排查
§
灵爪(NAS上的OpenClaw) ≠ astron-code-latest(讯飞MaaS) — 前者是NAS上的AI Agent(192.168.31.10, OpenClaw, 端口18789)，走飞书聊天；后者是旁路网关配置的MaaS API模型。用户说"灵爪不回复"时要SSH到NAS查OpenClaw进程，不是测讯飞MaaS。