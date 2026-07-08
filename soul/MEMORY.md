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
- 日志: journalctl -u sing-box。skill: networking/sing-box-gateway
- 优化已固化: MTU=1500(非9000,防分片超时)、route.final=漏网之鱼、QUIC reject
- 订阅仅5源: 机场/US-VPS/中转美国/日本JTTI/AWS-LIGHT(sub-store@NAS:3001)，178→41优质节点(清光Cloudflare免费垃圾)。生成脚本/tmp/gen_singbox_5subs.py
- 走旁路设备(ip rule from IP lookup 2022 pri 100): .102/.156/.10(NAS,静态IP需手动改网关)/.81。路由器ImmortalWRT密码123456，DHCP给NAS/.81加sidegw tag下发网关+DNS=141
- 机场"顺畅"官网scwljsq.scl168.club被墙但订阅djcrqwadn.shunsll.net(走CF CDN)可用;NAS未走旁路时拉境外订阅会500
§
Hermes自定义provider默认自动调用/v1/models覆盖models:列表。如需手动列表加discover_models: false。
§
sing-box 旁路网关: /etc/sing-box/config.json (root属主), /etc/systemd/system/sing-box.service.d/override.conf (环境变量)。生成脚本: /tmp/gen_singbox_5subs.py（5订阅源精简版）。Clash API: :9090, secret=054826。面板访问: http://192.168.31.141:9090/ui （不要用HTTPS的metacubexd.pages.dev，有混合内容拦截）。