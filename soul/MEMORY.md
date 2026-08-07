灵爪（OpenClaw，飞书 bot）+ 部署铁律（2026-08-01）：**数据接口类 skill 必须龙爪 141 本机部署，灵爪 SSH 调用，不许灵爪自己装**。违反：灵爪自装 mootdx → httpx 冲突 → adata 接口不稳老路。v1 错判教训：建议"灵爪自装"前必走 4 步（sharebox 历史 / lingzhua.md / MEMORY / 都没）。详见 details/lingzhua.md + china-stock-data-providers + evaluate-before-commit-data-sources。
§
默认模型改为 minimax-m3（minimax-cn provider），2026-07-28 老大要求切换。当前 session 生效在下一次新建会话。
§
Bekaert PPT 偏好（书面化语言、整齐表格化、感悟"升华"非列表）+ 飞书自动投递 `hermes send --to feishu` 被 skip（用 `MEDIA:<path>`）。详见 bekaert-process-development skill P3/P5。
§
旁路由（192.168.31.50）已弃用 DAED，改用 Nikki（mihomo）。面板 http://192.168.31.50:9090/ui/zashboard/。141 本机（192.168.31.141）sing-box 已停用，流量走硬路由（192.168.31.1）→ 旁路由 Nikki。
§
stock-yaml-update 7 陷阱 + verify_yaml.sh：YAML write_file 整文件重写；patch 失败≥2 次切 write_file；写到 YAML 的数字必先 python3 实测；sibling 改动警告必 read_file 重读再 patch；加仓信号先核 TP 实物化（grep take_profit_X_status）不直接套 add_position_1 计划；sold 字段清理按老大原话范围别擅自动；**"直接改"协议（8/7 13:34）**：老大说"已成交"+ 截图含方向/价/份数/时间 + 我能算新 shares/cost/realized_pnl → 直接改台账+decision_log 不重复确认，底线截图必须有（防 8/5"买不到了"陷阱）。详见 stock-yaml-update SKILL.md §五 + stock-portfolio-management/references/sold-fields-and-tp-physicalization-20260807.md。
§
老大 2026-07-31 立的硬偏好「不联想」（已固化到 stock-portfolio-management skill 顶部对话偏好第 4 条）：**用户没说的话不要替他延伸**。典型反例：老大说"以后问到再查"→ 龙爪延伸为"可以下班了"+"今天累计完成 X 项"→ 老大回怼"你怎么老是要下班？"。具体规则：①不复述"今天成绩单" ②不主动提议"接下来 X" ③不主动收尾"可以下班了" ④澄清场景才问且只问一次。
§
源码分析 vs 实测冲突时，永远相信实测（2026-07-31 旁路由扩容教训）。详见 details/home-network.md。
§
YouTube字幕抓取：脚本 /home/yu/.hermes/skills/media/youtube-content/scripts/fetch_transcript_with_proxy.py 自动切Nikki YouTube组到台湾住宅节点（台湾-故转）→ 抓字幕 → 抓完切回原节点。任何YouTube视频均可，换VIDEO_ID即可。
§
龙爪 = 141 本机（hostname yu-K46CM / IP 192.168.31.141，2026-08-03 老大纠正）。a-stock-data 部署在 141 上 → 本地直接调 venv，**不许 SSH 连自己**。实战教训：今天 SSH 141 失败 3 次才反应过来。铁律：①"SSH 连 141"= 乌龙；② 老大问"在 X 上吗"时先 `hostname && ip addr show` 确认；③ 灵爪 SSH 调龙爪链路是否通 ≠ 龙爪能否用 a-stock-data（灵爪在飞书侧/龙爪在 141 本地）。
§
持仓股接回纪律（2026-08-07 老大确立）：趋势没走坏（MA5/10/20 站上+量能正常+不破关键支撑）→ 减仓后必须接回，不是可选项。任何 holding 减仓后必须 mark reentry_plan（接回触发价/份数/止损/规则）。持仓纪律不是临时决策。