# 00-essence.md · 龙爪记忆精简分类原则
# 元规则：所有 memory 文件都遵守这套约束

## 核心约束

1. **memory = 索引文件，不是数据载体**
   - memory 里**只写指针**（文件路径 / skill 名 / 触发条件）
   - **不写具体数字 / 命令 / 表格 / 配置**——这些走 skill / references / decision_log.yaml
   - **不写操作日志 / 任务进度 / 7天内会变的事**

2. **按主题分类到独立 md 文件**
   - `00-essence.md` —— 本文件：原则本身
   - `01-laoda-identity.md` —— 老大硬偏好 + 沟通纪律
   - `02-network.md` —— 家庭网络拓扑 + 操作教训
   - `03-finance.md` —— 交易规则 + 持仓管理
   - `04-dragon-host.md` —— 龙爪本机 141 操作约束

3. **每条 entry 必须能用 1-2 句话说清**
   - 说不清 = 太细了，要拆到 skill 或 references

4. **修改纪律**
   - 老大偏好变更 → 改 `01-laoda-identity.md`
   - 拓扑变更 → 改 `02-network.md`
   - 交易规则变更 → 改 `03-finance.md`
   - 141 / 龙爪本机约束变更 → 改 `04-dragon-host.md`
   - 元规则变更 → 改 `00-essence.md`
   - 操作日志 / 决策记录 → 写 `~/.hermes/netops/decision_log.yaml`，**永远不进 memory**

5. **memory 写入触发条件**（满足任一才写）：
   - 老大新立硬偏好 / 改硬偏好
   - 环境变化（IP 变了 / 新设备 / 拓扑变更）
   - 老大当面纠正教训（写成 1 行）
   - 持久化新 skill 的核心触发条件

6. **memory 不写**：
   - 今天做了什么 / 任务进度
   - 老大说过一次但不重复的临时要求
   - 短期的设备 IP / 临时配置
   - 具体数字（持仓 / 价格 / 端口等）