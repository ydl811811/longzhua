cycle-investment-masters skill（2026-08-09）：路径 ~/.hermes/skills/cycle-investment-masters/。三人交叉验证=周金涛(康波)+洪灏(中波+估值)+马克斯(心理)。每月 1 号拉 PMI/M1-M2/ERP/新开户 4 指标→更新 references/current-cycle-position-YYYYMM.md。重大事件（PMI 单月>1pct、ERP>5%）立即追加。2026-08：战略看多+战术谨慎+AI 仓位封顶 30-40%+黄金持有不追。马克斯细节在 the-most-important-thing skill。
§
老大 2026-07-31 立的硬偏好「不联想」（已固化到 stock-portfolio-management skill 顶部对话偏好第 4 条）：**用户没说的话不要替他延伸**。典型反例：老大说"以后问到再查"→ 龙爪延伸为"可以下班了"+"今天累计完成 X 项"→ 老大回怼"你怎么老是要下班？"。具体规则：①不复述"今天成绩单" ②不主动提议"接下来 X" ③不主动收尾"可以下班了" ④澄清场景才问且只问一次。
§
141 本机（yu-K46CM / 192.168.31.141）：① a-stock-data 部署在 141 → 本地直接调 venv，**不许 SSH 连自己**；② 老大问"在 X 上吗"先 `hostname && ip addr show` 确认；③ 灵爪 SSH 调龙爪链路 ≠ 龙爪 a-stock-data 可用（灵爪在飞书侧）。**SSH alias 标准化（2026-08-23）**：老大授我权后手写了一个 ssh 别名配置文件进 home 目录（受保护路径 Hermes AI 写不动，必须老大手写）。后续 SSH 走 alias，不复用密码登录。**141 sudo 权限（2026-08-23 老大亲口给密码）**：yu 用户 sudo 密码老大授权可用——记忆见 session 上下文（密码敏感不进 memory），需要改路由 / NM / 系统网络时直接 sudo 试，已授权一次。
§
仓位动态化硬偏好（2026-08-10 老大纠正）：随市场情绪调整，不定死 3 成。详见 emotional-position-regime skill：5 档矩阵 + 4 指标。当前偏热档单赛道 15-20%。
§
券商 App 条件单 valid_until 过期必须主动监控（2026-08-13）：513120 TP3=1.30（8/12 已过期 1 天）+ 159326 TP1=1.75。无 cron 主动 grep = 老大忘延期龙爪不知道。详见 cron-schedule-and-conditional-order-expiry-20260813.md。
§
8/14 老大立的"自主决策"硬偏好（已固化到 stock-portfolio-management skill P0 第 5 条）：**"你不要问我了，你自己决定就好"**——小决策（批量套模板/cron 命名/监控阈值等）直接做，结果落 decision_log。例外三件仍要问：①超 6 万本金建仓 ②硬偏好冲突方案 ③跨 Agent 协调。**8/17 加 ④ "暂不 X" ≠ "撤 X"**（159326 反面教训）。**8/17 加 ⑤ 看当前趋势，不是死守之前定的规则**（继 7/31 不联想、8/14 自主决策 → 第 3 硬偏好，已固化对话偏好第 6 条）：add_position 触发位/止损位是初始设定不是铁律；老大问"X 可以加仓吗"先看实时趋势+量能+均线；趋势变了主动提"重算触发位"。典型反例：513120 add_position_3 1.20 → 老大纠正 → 重算 add_position_4 1.275。monitoring_snapshot 全套 + patch SDK 丢 path → Python 3 兜底。8/17 swing→swing_hold 模板 P0-20：strategy_note 重写 + 3 档 TP 全部 suspended 不删 + 加仓点下移 MA10 + 加仓量 1500-2000。
§
PVE 拓扑（2026-08-16）：J4125-4L PVE 9.2.2 宿主=**31.20**（root=12345678），nic0/1/2/3。VM 101 ImmortalWrt=**31.50**（root/**123456**）。**2026-08-23 切换**：50 上 daed 替代 nikki。详见 `网管/SKILL.md` §5.5/§5.6。**操作自主权硬纪律（2026-08-23 立）**："我在 XX 跑"→只给脚本不远程 SSH 替他跑；"我自己装/配"→立刻停手只回风险；"你帮我跑"→可远程但全局副作用操作必须排查风险链+老大确认。8/23 教训：龙爪 SSH `qm shutdown 101`→ 50 代理挂→ 141 网关断→老大手动救场。