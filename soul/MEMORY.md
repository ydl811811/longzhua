openclaw gateway：灵爪ws://192.168.31.10:18789，中央ws://192.168.31.141:18789（skill: openclaw-gateway-access）
老三(NAS)：sharebox（skill: nas-sharebox-access）
Chrome调试：--headless=new --remote-debugging-port=9222（skill: chrome-remote-debugging）
§
老大风格：有话直说，略带风趣。记忆只存索引，详细找skill。不看tracker式分析，要深度。
§
老大交易体系：短线为主，已有skill：lingzhua-short-term-trading、stock-market-pro、quantitative-research、adata-stock-data
§
adata-stock-data：skill路径~/.hermes/skills/adata-stock-data/，python3.12（skill内详）
老大QQ邮箱：452512209@qq.com，SMTP smtp.qq.com:587（skill: nas-sharebox-access）
模型：minimax-cn，MiniMax-M2.7
§
NVIDIA代理：端口5002，systemd服务nvidia-proxy.service
§
立讯精密(002475)盯盘：cronjob ID 0ccebef61437，明天10:00执行。三信号全满足→飞书警报：①早盘30分钟主力净流入>3亿 ②人气榜前10 ③北向资金>0。老大了不想看盘前分析。
§
Hindsight/Vectorize.io API: key存于.env第407行（HINDSIGHT_API_KEY），仅用于记忆勿明文记录
§
Hermès身份：男性，希腊信使之神，狡黠高效，数字世界信使。但名字是"龙爪"，老大起的。
§
Python文档生成（2026-04-29）：uv pip install python-docx安装，脚本/home/yu/travel/jx/make_doc.py参照此模板生成Word旅游文档