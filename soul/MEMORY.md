模型：DeepSeek V4 Flash 直连，provider=deepseek（base_url=https://api.deepseek.com/v1，sk-前缀key）。minimax-cn 已到期停用。memory provider已从hindsight改为local（免费）。
§
Router：ImmortalWRT 192.168.31.1（Nikki/mihomo），SSH root密码123456，LuCI web密码123456
§
TV-box：http://NAS:19999/merged_32in1.json，/home/YDL/tvbox-repo/。→ skill:tvbox-config
灵爪：通过 NAS sharebox 文件交换。SSH 写 lingzhua-box/ 目录发消息，回复在 longzhua-box/。→ skill:hermes-devops
§
Firecrawl：web/web_extract 后端。API Key 有效，systemd drop-in 加载。web_search 正常，web_extract 被部分网站策略拦截需另调。
§
ETF减仓：等位置>85%再减，不低位恐慌出。→ skill:trading-lessons
§
监控文件结构：positions_active.yaml（持仓）、candidates_watch.yaml（候选）、watch_only.yaml（观察），脚本从这三个文件读取数据。
§
旁路网关192.168.31.141：Ubuntu 24.04，sing-box已停用，现走主路由Nikki。sudo密码：Ydl32021976。
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
灵爪(NAS上的OpenClaw) ≠ astron-code-latest(讯飞MaaS) — 前者是NAS上的AI Agent(192.168.31.10, OpenClaw, 端口18789)，走飞书聊天；后者是旁路网关配置的MaaS API模型。用户说"灵爪不回复"时要SSH到NAS查OpenClaw进程，不是测讯飞MaaS。
§
Cronjob模型漂移：全局provider变更后，旧cronjob会被跳过。修复：`cronjob update <job_id> --model '{"model": "astron-code-latest", "provider": "custom"}'`
§
用户网络配置：联通千兆宽带（无锡）+ 光猫2.5G网口 + 主路由ImmortalWRT 2.5G网口 + 2个小米千兆网口中继路由器（192.168.31.69/155）。实测下载1260 Mbps超千兆，上传70 Mbps。千兆中继是瓶颈，日常够用。