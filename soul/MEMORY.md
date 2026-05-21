老大持仓实际是588080（科创50ETF易方达），不是588000（华夏）。以后老大提ETF时先确认代码。
老大邮箱：mailuser@ydl.de5.net（自托管VPS），密码YDLEMAIL2026，SMTP 587/IMAP 143 STARTTLS。VPS IP 207.56.226.188。老大偏好：问题复杂时主动说"来问grok"，不要装额外软件，说"搞好了通知我"。
§
老大沟通风格：先理清逻辑再行动，不要闷头搞太久。遇到问题→先汇报分析+Grok建议→老大决策。不要自己试超过3个方案还无果才报。
§
老大交易体系：短线为主，已有skill：lingzhua-short-term-trading、stock-market-pro、quantitative-research、adata-stock-data
§
adata-stock-data：skill路径~/.hermes/skills/adata-stock-data/，python3.12（skill内详）
老大QQ邮箱：452512209@qq.com，SMTP smtp.qq.com:587（skill: nas-sharebox-access）
模型：minimax-cn，MiniMax-M2.7
§
Hermès身份：男性，希腊信使之神，狡黠高效，数字世界信使。但名字是"龙爪"，老大起的。
§
老婆QQ邮箱：243966637@qq.com，发送旅游方案附件时用。QQ邮箱SMTP正常（授权码已存.env）。你老婆邮箱收到江西行程邮件后自动回复了一个iLink Bot配对码（G32MYWVZ），说明她邮箱也被绑定过配对系统。
§
今日教训（2026-05-21）：晨报脚本hardcoded持仓列表，没有动态读台账。候选股预警规则太宽松（五档比<0.5需同时满足涨跌<-2%才告警），导致博实股份五档比0.18未预警，需修改。
分析输出偏好：五档数据用表格展示（卖盘|买盘对比），数字+含义标注，结尾给明确结论。
§
老三(NAS)：192.168.31.10 = FNOS，openclaw-gateway在其上运行。SSH用户名**YDL（大写）**，私钥~/.ssh/id_ed25519_new。教训：一直用小写ydl被PAM拒绝，密码和公钥双拒，排查3小时才发现。
§
主路由：192.168.31.1，用户root，密码123456（OpenWRT软路由）
§
识图：auxiliary.vision已配SenseNova(sensenova-6.7-flash-lite)，vision_analyze走这个。若报token超限(>10240)，先用ffmpeg压缩：ffmpeg -i input.jpg -vf "scale=1024:1024:force_original_aspect_ratio=decrease" -update 1 input_small.jpg
§
网络调试：必须先抓baseline再让用户操作（controlled experiment），不能先让用户操作再回头查数据。流程：准备好对比框架→抓baseline→用户做动作→再抓→diff对比。路由排查时命令执行后必须验证返回了实际数据（空输出陷阱）。
§
Lucky已装（v2.27.2），运行192.168.31.1:16601，账号666/666，Luci界面已启用。下一步：配DDNS+SSL证书+HTTPS反代理，实现公网IPv6访问NAS和软路由。
§
灵爪飞书答非所问根因：灵爪feishu channel用app(cli_a93559e471b8dbd2)，与龙爪主飞书(ou_7cb0ccf9)不同应用，消息全路由agent:main:main。解法：删掉灵爪feishu channel重新配对（龙爪自身配置不动，只修灵爪）。
§
nikki：profiles目录`/etc/nikki/profiles/`。yq启动时删`.dns.proxy-server-nameserver`等字段，`fake-ip-filter-mode: rule`可保留。踩坑：`respect-rules: true`+yq删空`proxy-server-nameserver`→mihomo报错无法启动，必须`false`。`Seven1_fallback_Rule-Set_Enhanced.yaml`在跑（原版备用）。
§
老大今日确立新决策框架：先判断市场强弱（强势/中性/弱势），再决定对应策略（右侧追涨/等回调/观望）。不再死守单一风格。早盘08:00扫市场风向的morning_scan.py已建立（cron: 1af1d3ae2ace），输出含综合判断+操作建议推送飞书。
§
新候选股（2026-05-19入台账）：沪硅产业(688126)、中天科技(600522)、利元亨(688499)、长江通信(688999)。沪硅产业竞价量15265万手+五档比5.55=重要异动信号。
§
老大今日操作：600900长江电力卖出200股@27.29，剩200股持仓。集合竞价快照整合持仓+候选股统一表格，一屏全览6只。