cycle-investment-masters skill（2026-08-09）：路径 ~/.hermes/skills/cycle-investment-masters/。三人交叉验证=周金涛(康波)+洪灏(中波+估值)+马克斯(心理)。每月 1 号拉 PMI/M1-M2/ERP/新开户 4 指标→更新 references/current-cycle-position-YYYYMM.md。重大事件（PMI 单月>1pct、ERP>5%）立即追加。2026-08：战略看多+战术谨慎+AI 仓位封顶 30-40%+黄金持有不追。马克斯细节在 the-most-important-thing skill。
§
Bekaert PPT 偏好（书面化语言、整齐表格化、感悟"升华"非列表）+ 飞书自动投递 `hermes send --to feishu` 被 skip（用 `MEDIA:<path>`）。详见 bekaert-process-development skill P3/P5。
§
老大 2026-07-31 立的硬偏好「不联想」（已固化到 stock-portfolio-management skill 顶部对话偏好第 4 条）：**用户没说的话不要替他延伸**。典型反例：老大说"以后问到再查"→ 龙爪延伸为"可以下班了"+"今天累计完成 X 项"→ 老大回怼"你怎么老是要下班？"。具体规则：①不复述"今天成绩单" ②不主动提议"接下来 X" ③不主动收尾"可以下班了" ④澄清场景才问且只问一次。
§
龙爪 = 141 本机（hostname yu-K46CM / IP 192.168.31.141，2026-08-03 老大纠正）。a-stock-data 部署在 141 上 → 本地直接调 venv，**不许 SSH 连自己**。实战教训：今天 SSH 141 失败 3 次才反应过来。铁律：①"SSH 连 141"= 乌龙；② 老大问"在 X 上吗"时先 `hostname && ip addr show` 确认；③ 灵爪 SSH 调龙爪链路是否通 ≠ 龙爪能否用 a-stock-data（灵爪在飞书侧/龙爪在 141 本地）。
§
仓位动态化硬偏好（2026-08-10 老大纠正）：随市场情绪调整，不定死 3 成。详见 emotional-position-regime skill：5 档矩阵 + 4 指标。当前偏热档单赛道 15-20%。
§
券商 App 条件单 valid_until 过期必须主动监控（2026-08-13）：513120 TP3=1.30（8/12 已过期 1 天）+ 159326 TP1=1.75。无 cron 主动 grep = 老大忘延期龙爪不知道。详见 cron-schedule-and-conditional-order-expiry-20260813.md。
§
8/14 老大立的"自主决策"硬偏好（已固化到 stock-portfolio-management skill 顶部对话偏好第 5 条）：**"你不要问我了，你自己决定就好"**——以后小决策（批量套模板、cron 命名、文件命名、监控阈值、参考文档适用性等）直接做，结果落 decision_log 即可。例外三件仍要问：①超 6 万本金的建仓动作 ②硬偏好冲突方案 ③跨 Agent 协调。同期落地 5 只 active (513050/513120/159326/562800/159299) 全部加 monitoring_snapshot，模板见 holding-monitoring-snapshot-20260814.md。patch 工具 SDK 状态丢失 path 字段时 → Python 3 兜底（`assert content.count(old) == 1` 验唯一）。
§
PVE 拓扑（2026-08-16 实测）：J4125-4L PVE 9.2.2 宿主=**31.20**（root=12345678），nic0/1/2/3（PVE 不叫 eth）。VM 101 ImmortalWrt=**31.50**（root=123456，真系统 boot=scsi0，336M 需扩），LuCI 200/403 假象（uhttpd fallback 缺 /www/luci）。apk update OK=11435 用 vsean.net 镜像待切官方源。详见 `网管/SKILL.md` §5.5/§5.6 + references/pve-installed-actual-state-20260816.md + references/pve-ip-migration-50-to-20-20260816.md。