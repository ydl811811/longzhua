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
路由:192.168.31.1 root/123456，OpenWRT J4125@48-49°C。sshpass交互。
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
台账≠持仓真相，App截图=ground truth，先核实再分析
§
清仓股不触止损预警，清monitor_positions.yaml+.market_alert_state。改候选股逻辑监控
§
ETF减仓：等位置>85%再减，不低位恐慌出。详见skill:trading-lessons
§
投资最重要的事知识库：skill:the-most-important-thing。含核心框架(四大秘密+20法则)、实战应用(6大A股场景)、原文出处
§
持仓(6/23更新)：ETF大部减仓（科创50剩~100股/半导体剩~100股/人工智能剩~200股）。新仓：长江电力200@26.76/鼎胜新材200@26.20。仓位~10%，现金~5万等回调接回。三大ETF分批接回方案已定：科创50 Batch1=1.85~1.90/Batch2=1.78~1.82/Batch3=1.65~1.72；半导体 Batch1=2.38~2.42/Batch2=2.20~2.25/Batch3=1.98~2.05；人工智能 Batch1=1.18~1.20/Batch2=1.13~1.16/Batch3=1.05~1.08。候选股新增300444双杰电气。
§
长江电力持仓补仓策略(2026-06-25)：200股@26.76，止损25.50，TP1=28.00/TP2=29.00。Batch1补仓@26.0~26.2(200股，60日低点支撑)，Batch2@25.5~26.0(200股，1月前低支撑)。监控脚本market_alert.py已加入add_position_1_target/add_position_2_target触发逻辑，价格≤目标时飞书推送📥信号。
§
鼎胜新材(603876)持仓策略(2026-06-25更新)：200股@26.20，止损上移至27.70，TP1=30.50/TP2=33.50(年内前高)。催化剂：宁德时代钠新电池Q4量产→铝箔用量翻倍。不加仓等回调。已从monitor_watched.yaml候选股中移除，转入monitor_positions.yaml作为持仓监控。
§
候选股预警要求(2026-06-25确认)：即使候选股触发过建仓信号(price≤entry_max+五档比达标)，也不停止监控，持续显示是否仍在建仓区。飞书推送只发首次，但每日监控简报必须持续可见。不允许出现"监控已停止"。
§
用户期望：当我SSH/连接失败时，先自查skill/memory中的正确账号和凭据再重试，不要直接报告连不上。老大会说"账号对吗"来纠正。
§
劲拓股份(300400)策略(2026-06-25)：signal_type改为reversal，等放量站回MA10(41.64)确认回调结束再介入。止损40.00。现价41.06暂不建仓。分析记录已存~/.hermes/reports/a-share-research/劲拓股份_分析记录_20260625.md
§
大盘历史数据来源：NAS /home/YDL/.openclaw/workspace/a_stock_plan/fund_flow/市场数据汇总.md，含北向资金/涨跌家数/天时评分。收盘采集任务(15:35交易日)自动追加到此文件