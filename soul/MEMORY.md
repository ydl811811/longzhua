老大沟通风格：先理清逻辑再行动，不要闷头搞太久。遇到问题→先汇报分析+Grok建议→老大决策。不要自己试超过3个方案还无果才报。
§
老大交易体系：短线为主，已有skill：lingzhua-short-term-trading、stock-market-pro、quantitative-research、adata-stock-data
§
Hermès身份：男性，希腊信使之神，狡黠高效，数字世界信使。但名字是"龙爪"，老大起的。
§
老婆QQ邮箱：243966637@qq.com，发送旅游方案附件时用。QQ邮箱SMTP正常（授权码已存.env）。你老婆邮箱收到江西行程邮件后自动回复了一个iLink Bot配对码（G32MYWVZ），说明她邮箱也被绑定过配对系统。
§
老三(NAS)：192.168.31.10 = FNOS，openclaw-gateway在其上运行。SSH用户名**YDL（大写）**，私钥~/.ssh/id_ed25519_new。教训：一直用小写ydl被PAM拒绝，密码和公钥双拒，排查3小时才发现。
§
主路由：192.168.31.1，用户root，密码123456（OpenWRT软路由）。SSH需要交互密码，用sshpass：sshpass -p '123456' ssh root@192.168.31.1 "命令"。J4125 CPU，正常48-49°C。
§
识图：auxiliary.vision已配SenseNova(sensenova-6.7-flash-lite)，vision_analyze走这个。若报token超限(>10240)，先用ffmpeg压缩：ffmpeg -i input.jpg -vf "scale=1024:1024:force_original_aspect_ratio=decrease" -update 1 input_small.jpg
§
老大交易风格：盘中实时盯盘，需要我主动推送分析（不等他问）。今日14:40推送尾盘分析已成惯例。对时间敏感，说"太晚了"就把分析提前跑。
§
Lucky已装（v2.27.2），运行192.168.31.1:16601，账号666/666，Luci界面已启用。下一步：配DDNS+SSL证书+HTTPS反代理，实现公网IPv6访问NAS和软路由。
§
TV-box融合配置（NAS）：http://192.168.31.10:19999/merged_32in1.json，systemd用户服务持久。文件/home/YDL/tvbox-repo/，pg.jar同目录。管理：systemctl --user restart tvbox-http。Skill已建：tvbox-config。
§
nikki：profiles目录`/etc/nikki/profiles/`。yq启动时删`.dns.proxy-server-nameserver`等字段，`fake-ip-filter-mode: rule`可保留。踩坑：`respect-rules: true`+yq删空`proxy-server-nameserver`→mihomo报错无法启动，必须`false`。`Seven1_fallback_Rule-Set_Enhanced.yaml`在跑（原版备用）。
§
adata库实际路径：/home/yu/.local/lib/python3.12/site-packages/adata（v2.9.5），skill目录不存在。直接python3.12调用，腾讯接口qt.gtimg.cn是五档实时主力源，新浪备用。
§
台账(portfolio.yaml)可能与App实际持仓不一致。教训：用户App截图是最新的持仓 ground truth，不能迷信台账文件。今日发现588080实际5300股vs台账5000股，即使用户没特别说明，也要先对比台账和App数据再分析。核实后再行动。
§
老大有T+0操作习惯：买入后当日反弹则卖当天买的那部分（卖持有的部分不等同），不是全出，是降成本操作。如今日捷捷微电(300623)买入200股@34.98后反弹卖出这200股。波段持仓用底仓+波段仓双层管理。
§
老大证券App：东吴证券（账号6072结尾）。今日持仓（2026-05-27）：588080(3000股@1.860)、512480(3500股@2.271)、鼎胜新材(200@28.066)、捷捷微电(200@36.345)、劲拓股份(300@29.401)。博实股份已清仓亏-396.68。账户总资产58,771.66元，可用23,045元，仓位60.8%。波段策略：ETF底仓+波段仓，TP触发出售，buy_target跌加仓。
§
清仓股不再触发止损预警：已清仓的股票必须从 monitor_positions.yaml 移除，旧状态（.market_alert_state）也需清理；新策略以候选股逻辑（接回区间+五档比）监控，不走止损逻辑。老大原话："已经清仓的股票，不应该再触发止损预警，我们已经制定新的策略，应该根据最新的策略触发。"