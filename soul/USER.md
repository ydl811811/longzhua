# USER.md - 用户档案索引

- 工作（贝卡尔特/钢丝绳/PPT）→ details/work.md
- 联系方式/邮箱/微信飞书 → details/channels.md
- 散户身份 + 本金 + 持仓候选 → details/stock.md
- 决策型用户 + 中文精简 + 操作纪律 → details/discipline.md
- Hermes home channels → details/channels.md
§
老大在贝卡尔特（Bekaert）中国区工厂做工艺工程师，负责钢帘线成品工序捻股工艺。厂内双捻机分BFM9（9工字轮）和BFM4（4工字轮）。钢帘线分两步：Step1做芯股（如0.25+6×0.225），Step2在双捻机上加外层合股。内部APQP使用DP1-DP7七阶段框架。工作邮箱 yu.dingli@bekaert.com。企业色为深朱红 #B63539（不是默认 #C4101C，从老大标题字截图取色确认）。
§
老大 2026-07-20 现场表达两个 first-class 偏好：

1. **"我不懂，我只知道 X"**（场景：系统文件统一 NAS）→ 老大**不关心技术细节**，只关心**业务目标**。给方案时**先给零依赖方案**（rsync + cron / SSH / cron 改 SSH），再给装包方案（NFS / SSHFS / nfs-common）。**避免装新包是默认倾向**。同时 SKILL.md 已知坑 6.5 也记录了这条。

2. **"暗号只有一人一句才合适，不是你全部都说完"**（场景：SSH 联系灵爪暗号协议）→ 暗号必须 ping-pong 分两条发，**禁止**塞进一条消息+塞业务。SKILL.md "灵爪通信协议" 段已加 ping-pong 必读 + references/lingzhua-pingpong-handshake-20260720.md + references/lingzhua-ssh-message-template.md 都已更新。

3. **"你来决定把，我授权给你"** → 进入自主决策模式（之前已有）。SKILL.md 已知坑 9 已加 2026-07-20 扩展（"你来决定" vs "你给个方案" vs "你来定" 三种指令区分）。

记忆索引：风格偏好合集，详见 ~/.hermes/memories/details/discipline.md "老大决策模式"段。
§
灵爪交付不完整/有 bug 时，老大倾向让龙爪直接改（"你自己直接去改"），不回灵爪 ping-pong。判断：小修（2-3 文件数据源切换）→ 龙爪直接改 + 验证；大改（架构/多文件）→ 仍走灵爪。
§
贝卡尔特工艺工程师，讲中文。技术报告偏好书面化语言，版面对齐整齐、宽屏 16:9 风格（13.33×7.5 英寸）。项目结构强调 "项目边界清晰" — 同一份 PPT 涉及多个项目时，需要用分隔页 / 大标号明确区隔。PPT 报告模板：参考 `/home/yu/.hermes/output/bekaert_report/` 下的 .pptx 文件。