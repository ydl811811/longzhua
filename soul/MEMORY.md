cycle-investment-masters skill（2026-08-09）：路径 ~/.hermes/skills/cycle-investment-masters/。三人交叉验证=周金涛(康波)+洪灏(中波+估值)+马克斯(心理)。每月 1 号拉 PMI/M1-M2/ERP/新开户 4 指标→更新 references/current-cycle-position-YYYYMM.md。重大事件（PMI 单月>1pct、ERP>5%）立即追加。2026-08：战略看多+战术谨慎+AI 仓位封顶 30-40%+黄金持有不追。马克斯细节在 the-most-important-thing skill。
§
默认模型改为 minimax-m3（minimax-cn provider），2026-07-28 老大要求切换。当前 session 生效在下一次新建会话。
§
Bekaert PPT 偏好（书面化语言、整齐表格化、感悟"升华"非列表）+ 飞书自动投递 `hermes send --to feishu` 被 skip（用 `MEDIA:<path>`）。详见 bekaert-process-development skill P3/P5。
§
旁路由（192.168.31.50）已弃用 DAED，改用 Nikki（mihomo）。面板 http://192.168.31.50:9090/ui/zashboard/。141 本机（192.168.31.141）sing-box 已停用，流量走硬路由（192.168.31.1）→ 旁路由 Nikki。
§
stock-yaml-update 关键纪律：YAML write_file 整文件重写（patch 失败≥2 切）；数字必实测；sibling 警告必 read 重读；"直接改"协议=截图+4 要素（方向/价/份数/时间）→ 直改台账+decision_log（8/7 老大拍板）。详见 SKILL.md §五。
§
老大 2026-07-31 立的硬偏好「不联想」（已固化到 stock-portfolio-management skill 顶部对话偏好第 4 条）：**用户没说的话不要替他延伸**。典型反例：老大说"以后问到再查"→ 龙爪延伸为"可以下班了"+"今天累计完成 X 项"→ 老大回怼"你怎么老是要下班？"。具体规则：①不复述"今天成绩单" ②不主动提议"接下来 X" ③不主动收尾"可以下班了" ④澄清场景才问且只问一次。
§
源码分析 vs 实测冲突时，永远相信实测（2026-07-31 旁路由扩容教训）。详见 details/home-network.md。
§
YouTube字幕抓取：脚本 /home/yu/.hermes/skills/media/youtube-content/scripts/fetch_transcript_with_proxy.py 自动切Nikki YouTube组到台湾住宅节点（台湾-故转）→ 抓字幕 → 抓完切回原节点。任何YouTube视频均可，换VIDEO_ID即可。
§
龙爪 = 141 本机（hostname yu-K46CM / IP 192.168.31.141，2026-08-03 老大纠正）。a-stock-data 部署在 141 上 → 本地直接调 venv，**不许 SSH 连自己**。实战教训：今天 SSH 141 失败 3 次才反应过来。铁律：①"SSH 连 141"= 乌龙；② 老大问"在 X 上吗"时先 `hostname && ip addr show` 确认；③ 灵爪 SSH 调龙爪链路是否通 ≠ 龙爪能否用 a-stock-data（灵爪在飞书侧/龙爪在 141 本地）。
§
仓位动态化硬偏好（2026-08-10 老大纠正）：随市场情绪调整，不定死 3 成。详见 emotional-position-regime skill：5 档矩阵 + 4 指标。当前偏热档单赛道 15-20%。
§
xianyu-tushare 失效（2026-08-10 实测）：11 接口全 403（block_moneyflow/moneyflow/margin/top_list/top_inst/analyst_rank 等 + fund_daily 之前能用现在也 403）。错误 `invalid_api_key`。存续 17 天（7/24 买 → 8/10 全失效）。非官方 tushare 必然短命。P2 不能走 tushare。已在 stock-portfolio-management skill 顶部加 P0-8 铁律。
§
老大仓位管理偏好（2026-08-10 纠正）：仓位不是定死的 3 成，必须随市场情绪动态调整。5 档情绪仓位表（极冷70-80%/偏冷50%/正常60%/偏热40%/过热30%），单赛道上限相应调整。当前 8/10 市场情绪 = 偏热档（沪深300 PE 14.45 + 上证 PE 18.11 + 半天成交 1.7 万亿）。任何时候建仓方案必须按当前情绪档 + 真实资金量（6 万本金）+ 1 手 100 股资金门槛算，不能凭空假设预算。