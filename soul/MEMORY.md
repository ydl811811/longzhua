老大持仓实际是588080（科创50ETF易方达），不是588000（华夏）。以后老大提ETF时先确认代码。
老大邮箱：mailuser@ydl.de5.net（自托管VPS），密码YDLEMAIL2026，SMTP 587/IMAP 143 STARTTLS。VPS IP 207.56.226.188。老大偏好：问题复杂时主动说"来问grok"，不要装额外软件，说"搞好了通知我"。
§
老大沟通风格：先理清逻辑再行动，不要闷头搞太久。遇到问题→先汇报分析+Grok建议→老大决策。不要自己试超过3个方案还无果才报。
§
老大交易体系：短线为主，已有skill：lingzhua-short-term-trading、stock-market-pro、quantitative-research、adata-stock-data
§
adata-stock-data skill路径失效（~/.hermes/skills/adata-stock-data/ 不存在）。adata库实际在 /home/yu/.local/lib/python3.12/site-packages/adata（v2.9.5）。腾讯接口（qt.gtimg.cn）才是五档实时主力数据源，新浪接口（hq.sinajs.cn）备用。直接用python3.12调用，不依赖skill路径。
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
网络调试：必须先抓baseline再让用户操作（controlled experiment），不能先让用户操作再回头查数据。流程：准备好对比框架→抓baseline→用户做动作→再抓→diff对比。路由排查时命令执行后必须验证返回了实际数据（空输出陷阱）。
§
Lucky已装（v2.27.2），运行192.168.31.1:16601，账号666/666，Luci界面已启用。下一步：配DDNS+SSL证书+HTTPS反代理，实现公网IPv6访问NAS和软路由。
§
TV-box融合配置（NAS）：http://192.168.31.10:19999/merged_32in1.json，systemd用户服务持久。文件/home/YDL/tvbox-repo/，pg.jar同目录。管理：systemctl --user restart tvbox-http。Skill已建：tvbox-config。
§
nikki：profiles目录`/etc/nikki/profiles/`。yq启动时删`.dns.proxy-server-nameserver`等字段，`fake-ip-filter-mode: rule`可保留。踩坑：`respect-rules: true`+yq删空`proxy-server-nameserver`→mihomo报错无法启动，必须`false`。`Seven1_fallback_Rule-Set_Enhanced.yaml`在跑（原版备用）。
§
adata库实际路径：/home/yu/.local/lib/python3.12/site-packages/adata（v2.9.5），skill目录不存在。直接python3.12调用，腾讯接口qt.gtimg.cn是五档实时主力源，新浪备用。
§
当前持仓（2026-05-23）：588080科创50ETF(1800股)、600900长江电力(200股)、300400劲拓股份(200股)、300629新劲刚(400股)。候选：002698博实股份、300552万集科技、603876鼎胜新材、002876三利谱。688科创板已全剔除。