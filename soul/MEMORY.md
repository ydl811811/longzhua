cycle-investment-masters skill（2026-08-09）：路径 ~/.hermes/skills/cycle-investment-masters/。三人交叉验证=周金涛(康波)+洪灏(中波+估值)+马克斯(心理)。每月 1 号拉 PMI/M1-M2/ERP/新开户 4 指标→更新 references/current-cycle-position-YYYYMM.md。重大事件（PMI 单月>1pct、ERP>5%）立即追加。2026-08：战略看多+战术谨慎+AI 仓位封顶 30-40%+黄金持有不追。马克斯细节在 the-most-important-thing skill。
§
Bekaert PPT 偏好（书面化语言、整齐表格化、感悟"升华"非列表）+ 飞书自动投递 `hermes send --to feishu` 被 skip（用 `MEDIA:<path>`）。详见 bekaert-process-development skill P3/P5。
§
旁路由（192.168.31.50）已弃用 DAED，改用 Nikki（mihomo）。面板 http://192.168.31.50:9090/ui/zashboard/。141 本机（192.168.31.141）sing-box 已停用，流量走硬路由（192.168.31.1）→ 旁路由 Nikki。
§
老大 2026-07-31 立的硬偏好「不联想」（已固化到 stock-portfolio-management skill 顶部对话偏好第 4 条）：**用户没说的话不要替他延伸**。典型反例：老大说"以后问到再查"→ 龙爪延伸为"可以下班了"+"今天累计完成 X 项"→ 老大回怼"你怎么老是要下班？"。具体规则：①不复述"今天成绩单" ②不主动提议"接下来 X" ③不主动收尾"可以下班了" ④澄清场景才问且只问一次。
§
龙爪 = 141 本机（hostname yu-K46CM / IP 192.168.31.141，2026-08-03 老大纠正）。a-stock-data 部署在 141 上 → 本地直接调 venv，**不许 SSH 连自己**。实战教训：今天 SSH 141 失败 3 次才反应过来。铁律：①"SSH 连 141"= 乌龙；② 老大问"在 X 上吗"时先 `hostname && ip addr show` 确认；③ 灵爪 SSH 调龙爪链路是否通 ≠ 龙爪能否用 a-stock-data（灵爪在飞书侧/龙爪在 141 本地）。
§
仓位动态化硬偏好（2026-08-10 老大纠正）：随市场情绪调整，不定死 3 成。详见 emotional-position-regime skill：5 档矩阵 + 4 指标。当前偏热档单赛道 15-20%。
§
stock_monitor cron schedule 必须 9-15 不是 9-14（2026-08-13 老大纠正"应该监控到 15 点才对"）：9-14 漏跑尾盘 5 分钟。修 `cronjob update --schedule '*/5 9-15 * * 1-5'`。
§
券商 App 条件单 valid_until 过期必须主动监控（2026-08-13）：513120 TP3=1.30（8/12 已过期 1 天）+ 159326 TP1=1.75。无 cron 主动 grep = 老大忘延期龙爪不知道。详见 cron-schedule-and-conditional-order-expiry-20260813.md。
§
老大仓位管理偏好（2026-08-10 纠正）：仓位不是定死的 3 成，必须随市场情绪动态调整。5 档情绪仓位表（极冷70-80%/偏冷50%/正常60%/偏热40%/过热30%），单赛道上限相应调整。当前 8/10 市场情绪 = 偏热档（沪深300 PE 14.45 + 上证 PE 18.11 + 半天成交 1.7 万亿）。任何时候建仓方案必须按当前情绪档 + 真实资金量（6 万本金）+ 1 手 100 股资金门槛算，不能凭空假设预算。
§
老大"长期看好想增厚底仓"语义（2026-08-13）：长期看好 ≠ 现在买。跌到 MA20 / swing_add_zone 才接回。513120 1.289 老大拒绝追高（+8.3% 超买区），改 reentry_plan（1.18-1.20 接 1000 份增厚底仓）。所有持仓 ETF 适用：长期看好写进 reentry_plan，不要写进"今天加仓"。详见 stock-portfolio-management SKILL.md §P0-12-C。
§
stock-portfolio 8/13 三铁律（合并）：①银河唯一账户（33450*****36），broker 字段统一。②候选 vs 持仓去重（159299 教训，老大加仓后必须立刻 grep 候选池标 done）。③黄灯 ≠ 红灯（MA5 破 + 缩量是黄灯不动；触止损/成本/放量才红灯）。详见 P0-12/13。