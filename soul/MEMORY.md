模型：DeepSeek V4 Flash直连，provider=deepseek（base_url=https://api.deepseek.com/v1，sk-前缀key）。minimax-cn已到期停用
§
老婆QQ:243966637@qq.com，SMTP已配.env。曾收iLink配对码G32MYWVZ
§
NAS:192.168.31.10(FNOS)，openclaw-gateway在上运行。skill:tvbox-config
§
识图：SenseNova(sensenova-6.7-flash-lite)，超10240token用ffmpeg缩至1024
§
盯盘：主动推送不等问。尾盘14:40已成惯例，嫌晚提前。
§
TV-box: http://NAS:19999/merged_32in1.json，/home/YDL/tvbox-repo/。skill:tvbox-config
§
nikki:/etc/nikki/profiles/，yq删dns.proxy-server-nameserver，respect-rules需false
§
adata:v2.9.5@pip，腾讯qt.gtimg.cn五档主力源，新浪备用
§
持仓台账权威文件=~/.hermes/stock-portfolio/monitor_positions.yaml，含全部成本/买卖记录。查持仓先读此文件。App截图=ground truth，核实后为准。
§
ETF减仓：等位置>85%再减，不低位恐慌出。详见skill:trading-lessons
§
投资最重要的事：skill:the-most-important-thing
§
持仓(7/3)：长江电力200/海正药业600/科创50ETF2500@2.146/游戏ETF5000@1.099/TCL科技800@6.16/鼎胜新材200@25.70。清仓：通信ETF/消费电子ETF/金融科技ETF(均7/2止损止盈)。159516接回计划：Batch1 1.65~1.72(1500份)+Batch2 1.53~1.58(1500份)。588080(科创50)≈75%半导体，与159516(设备材料)互补，不与512480重叠。
§
候选股预警要求(2026-06-25确认)：即使候选股触发过建仓信号(price≤entry_max+五档比达标)，也不停止监控，持续显示是否仍在建仓区。飞书推送只发首次，但每日监控简报必须持续可见。不允许出现"监控已停止"。
§
用户期望：当我SSH/连接失败时，先自查skill/memory中的正确账号和凭据再重试，不要直接报告连不上。老大会说"账号对吗"来纠正。
§
大盘历史数据来源：NAS /home/YDL/.openclaw/workspace/a_stock_plan/fund_flow/市场数据汇总.md，含北向资金/涨跌家数/天时评分。收盘采集任务(15:35交易日)自动追加到此文件
§
预警推送只走群聊webhook机器人，不走飞书DM。
§
多氟多接回区间50~52（卖出价附近），等企稳
§
588080科创50≈75%半导体(寒武纪/海光/中芯/澜起/中微)+医疗软件。159516(设备材料)与588080互补，512480(全产业链)与588080高度重叠，老大确认侧重159516。159516接回：Batch1 1.65~1.72+Batch2 1.53~1.58(MA20)。
§
灵爪通信方式：通过NAS sharebox文件交换。用SSH写文件到 lingzhua-box/ 目录即可向灵爪发消息，灵爪回复在 longzhua-box/ 目录。具体凭据见 hermes-devops skill。
§
YAML坑：带前导0的股票代码必须加引号('002407','000100')否则被解析为八进制。用户要求不改止损价，盘中预警触发但未实际卖出时不自动改状态，需用户确认。多氟多新接回44~48。159206卫星ETF新建仓监控(回调1.764~1.766/突破>1.772)。
§
DAED v1.27.0 已手动从 GitHub release 安装（2026-07-04）。opkg源只有v1.24.0。J4125/内核6.6.110实测可用。Nikki已停用
§
Nikki管理：api_secret=054826(uci show nikki.mixin.api_secret)，状态= /etc/init.d/nikki status，端口验证=netstat -tlnp | grep -E '7891|7892|1053|9090'。切换DAED→Nikki：先/etc/init.d/daed disable+stop，再nikki enable+start
§
DAED 面板 admin 密码: admin123（OpenWRT 192.168.31.1:2023）。GraphQL 端点是 /graphql（非 /api/graphql），可从远程主机直接访问 http://192.168.31.1:2023/graphql。