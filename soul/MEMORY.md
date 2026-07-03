沟通：先理逻辑→汇报分析+Grok建议→老大决策。不试超3方案。
§
交易：短线为主。skill:lingzhua-short-term-trading/stock-market-pro/quantitative-research/adata-stock-data
§
模型：DeepSeek V4 Flash直连，provider=deepseek（base_url=https://api.deepseek.com/v1，sk-前缀key）。minimax-cn已到期停用
§
老婆QQ:243966637@qq.com，SMTP已配.env。曾收iLink配对码G32MYWVZ
§
NAS:192.168.31.10(FNOS)，openclaw-gateway在上运行。skill:tvbox-config
§
局域网：路由192.168.31.1 root/123456 | 本机141 sudo:Ydl32021976
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
投资最重要的事知识库：skill:the-most-important-thing。含核心框架(四大秘密+20法则)、实战应用(6大A股场景)、原文出处
§
长江电力持仓补仓策略(2026-06-25)：200股@26.76，止损25.50，TP1=28.00/TP2=29.00。Batch1补仓@26.0~26.2(200股，60日低点支撑)，Batch2@25.5~26.0(200股，1月前低支撑)。监控脚本market_alert.py已加入add_position_1_target/add_position_2_target触发逻辑，价格≤目标时飞书推送📥信号。
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