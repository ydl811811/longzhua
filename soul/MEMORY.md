## 🔧 环境配置

模型：DeepSeek V4 Flash 直连，provider=deepseek（base_url=https://api.deepseek.com/v1，sk-前缀key）。minimax-cn 已到期停用。
识图：SenseNova（sensenova-6.7-flash-lite），超10240token用ffmpeg缩至1024。
adata：v2.9.5@pip。腾讯 qt.gtimg.cn 五档主力源，新浪备用。
§
NAS：192.168.31.10（FNOS），openclaw-gateway 在上运行。
Router：ImmortalWRT 192.168.31.1（Nikki/mihomo）。fake-ip+proxy-server-nameserver，需备份再改。backup_lingzhua_to_github.py DNS patch已删（GitHub走代理可达）。
Nikki：/etc/nikki/profiles/，yq 删 dns.proxy-server-nameserver，respect-rules 需 false。
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
sing-box旁路网关 192.168.31.141：sing-box 1.13.14，TUN+FakeIP，Clash API:9090/密码054826，面板http://192.168.31.141:9090/ui。DNS已优化（删除运营商DNS，只保留ali-dns/google-dns DoH+fakeip）。nftables dns_block链已生效：放行127.0.0.0/8和sing-box-tun的DNS，封锁其他明文DNS。旁路设备.102/.156/.10/.81。→ skill:sing-box-gateway
§
Hermes自定义provider默认自动调用/v1/models覆盖models:列表。如需手动列表加discover_models: false。
§
清仓后清理：①position状态用status: sold（不是cleared，脚本只认sold）②删除state文件~/.hermes/scripts/.market_alert_state中对应代码行
§
观察票(signal_type:watch)不移除，每日15:10 cron扫触底信号。513120港股创新药ETF波段：entry 1.10-1.13/1.05-1.07,SL1.05,TP1.19/1.23。
§
主路由192.168.31.1(ImmortalWrt)：Nikki代理已关闭。曾针对.102手机DNAT重定向(→141:7891)已清理。
§
用户计划购买雷鸟鹤6 26款75寸电视（型号75R69A）替换故障的荣耀X1 65寸。目标价格：京东自营叠满券+国补后约3276-3438元，拼多多百亿补贴约3241元。推荐京东自营（售后+送装一体）。配置：312分区Mini LED、1300nits、150Hz、华星HVA屏、无开机广告、灵控系统3.0（安卓底层，可装APK）