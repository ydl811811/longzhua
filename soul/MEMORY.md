灵爪（OpenClaw，飞书 bot）+ 部署铁律（2026-08-01）：**数据接口类 skill 必须龙爪 141 本机部署，灵爪 SSH 调用，不许灵爪自己装**。违反：灵爪自装 mootdx → httpx 冲突 → adata 接口不稳老路。v1 错判教训：建议"灵爪自装"前必走 4 步（sharebox 历史 / lingzhua.md / MEMORY / 都没）。详见 details/lingzhua.md + china-stock-data-providers + evaluate-before-commit-data-sources。
§
默认模型改为 minimax-m3（minimax-cn provider），2026-07-28 老大要求切换。当前 session 生效在下一次新建会话。
§
Bekaert PPT 偏好（书面化语言、整齐表格化、感悟"升华"非列表）+ 飞书自动投递 `hermes send --to feishu` 被 skip（用 `MEDIA:<path>`）。详见 bekaert-process-development skill P3/P5。
§
旁路由（192.168.31.50）已弃用 DAED，改用 Nikki（mihomo）。面板 http://192.168.31.50:9090/ui/zashboard/。141 本机（192.168.31.141）sing-box 已停用，流量走硬路由（192.168.31.1）→ 旁路由 Nikki。
§
2026-07-31 stock-yaml-update skill 升级到 5 陷阱 + postmortem + verify_yaml.sh：① 3 次 patch 失误（old_string 不够独特 / 删整 entry / 同条目改三次）② 1 次数据写错（MA60=1.121 实际 1.1020，凭印象编）③ 1 次 patch loop（删空行连失败 5 次系统警告 4 次）。**铁律**：YAML 用 write_file 整文件重写；patch 失败≥2 次立刻切 write_file；任何写到 YAML 的数字必先 python3 实测。详见 ~/.hermes/skills/stock-yaml-update/SKILL.md + 适用拓宽到 YAML/TOML/嵌套 JSON。
§
老大 2026-07-31 立的硬偏好「不联想」（已固化到 stock-portfolio-management skill 顶部对话偏好第 4 条）：**用户没说的话不要替他延伸**。典型反例：老大说"以后问到再查"→ 龙爪延伸为"可以下班了"+"今天累计完成 X 项"→ 老大回怼"你怎么老是要下班？"。具体规则：①不复述"今天成绩单" ②不主动提议"接下来 X" ③不主动收尾"可以下班了" ④澄清场景才问且只问一次。
§
源码分析 vs 实测冲突时，永远相信实测（2026-07-31 旁路由扩容教训）。详见 details/home-network.md。
§
YouTube字幕抓取：脚本 /home/yu/.hermes/skills/media/youtube-content/scripts/fetch_transcript_with_proxy.py 自动切Nikki YouTube组到台湾住宅节点（台湾-故转）→ 抓字幕 → 抓完切回原节点。任何YouTube视频均可，换VIDEO_ID即可。
§
龙爪 = 141 本机（hostname yu-K46CM / IP 192.168.31.141，2026-08-03 老大纠正）。a-stock-data 部署在 141 上 → 本地直接调 venv，**不许 SSH 连自己**。实战教训：今天 SSH 141 失败 3 次才反应过来。铁律：①"SSH 连 141"= 乌龙；② 老大问"在 X 上吗"时先 `hostname && ip addr show` 确认；③ 灵爪 SSH 调龙爪链路是否通 ≠ 龙爪能否用 a-stock-data（灵爪在飞书侧/龙爪在 141 本地）。
§
老大口语化表达映射（2026-08-05 沉淀，新会话必读）：
- ❌ **"X 买不到了" ≠ 触发了成交**（8/5 513120 教训）：实际 = 触发价已被向上突破/触发条件不可达/条件单 expired。判定：① 现价 vs 触发价方向 ② 触发条件 ≤ 还是 ≥ ③ 条件单是否在监控列表。宁可多问"触发还是作废？"也别凭印象改台账
- "高看一线"= TP 上调要我给数字
- "进攻"/"加仓进攻"= 现有策略上下重注（不改策略）
- "今天不动了"= 只锁该标的不延伸到其他
- 修正不留空白：原错误决策保留（教训），追加新条带 `rollback=true`
- 详见 a-share-position-decision §十一