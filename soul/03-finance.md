# 03-finance.md · 交易规则 + 持仓管理
# 交易规则变更时改本文件；台账在 monitor_positions.yaml

## 持仓管理核心规则

| 规则 | 简述 | 详细位置 |
|---|---|---|
| 仓位动态化 | 随市场情绪调整，不定死 3 成 | `emotional-position-regime` skill |
| 暂不 X ≠ 撤 X | swing_hold 模板 P0-20 | stock-portfolio-management skill |
| 看趋势不守规则 | add_position 初始设定不是铁律 | stock-portfolio-management skill §6 |
| 条件单过期监控 | App valid_until 必须 cron 主动 grep | `references/cron-schedule-and-conditional-order-expiry-20260813.md` |

## 投资研究框架

- **周期投资**：cycle-investment-masters skill（康波/中波/心理三层）
  - 每月 1 号拉 4 指标（PMI / M1-M2 / ERP / 新开户）
  - 重大事件（PMI 单月>1pct、ERP>5%）立即追加
  - 2026-08 状态：战略看多 + 战术谨慎 + AI 仓位封顶 30-40% + 黄金持有不追
- **反向投资 / 第二层思考**：`the-most-important-thing` skill（马克斯细节）

## 资产盘点铁律（2026-08-10 起）

- **资产盘点只做一次**（8/10 已完成 228.58 万 = 流动 22.18 + 房产净值 206.4）
- 后续**只关心股票账户资金**，房产净值不再重算

## 操作纪律（重点）

- 老大自操作未通知 → **每周日截图 vs 台账对账**（P0-39 SOP）
- 网格自动成交是漏记主源（每周约 5 笔）
- 加仓后止损必须按新均价上移（513050 案例：1.05→1.09 MA30）

## 详细文档位置

| 主题 | 文档 |
|---|---|
| 持仓管理 SOP | `stock-portfolio-management` skill（30+ P0 铁律）|
| 单次加仓决策框架 | `a-share-position-decision` skill |
| 网格交易方案 | `etf-grid-trading` skill |
| 周期位置判断 | `cycle-investment-masters` skill |
| 反向投资方法论 | `the-most-important-thing` skill |
| 持仓台账 | `~/.hermes/stock-portfolio/monitor_positions.yaml` |