# 股票（决策台账 + 操作铁律）

## 文件路径（事实源）

- 持仓：`~/.hermes/stock-portfolio/positions_active.yaml`
- 候选：`~/.hermes/stock-portfolio/candidates_watch.yaml`
- 观察：`~/.hermes/stock-portfolio/watch_only.yaml`
- 决策流水：`~/.hermes/stock-portfolio/decision_log.yaml`（按 code+date 索引，含 trigger/analysis/decision/outcome_pending）
- 监控脚本：`~/.hermes/scripts/stock_monitor.py`
- 监控 cron：`1c6cd4c32caf`（no_agent=True，*/5 9-14 工作日）
- 监控 state：`~/.hermes/scripts/.market_alert_state`

## 用户本金

- **60,000 元**（2026-07-17 用户明确告知）⚠️ **历史数据**（7-17 后的本金/持仓变化以 YAML `positions_active.yaml` 为准，不在此处更新）
- ⚠️ 助理 7/17 15:00 曾误算"现金 21,900 当盈利"，被用户纠正
- **任何资产计算都必须**：总资产 = 持仓市值 + 现金，盈亏 = 总资产 - 本金
- 已写入 `monitor_positions.yaml` 末尾"全账户总览"段

## 铁律 P0（用户 7/16-17 反复确认，2026-07-22 补减仓规则 v2.0）

1. **用户问股 → 先 curl qt.gtimg.cn 拉实时数据 → 绝不靠记忆给股价**
2. ~~**24h 内决策不掉头**，除非新事实（业绩雷/政策反转/系统性风险）~~ — **2026-07-22 删除**（导致 588080 减仓窗口错过，详见 decision_log.yaml）
3. **用户频繁反悔时**（24h 内 2+ 次）→ 维持上一次决策，不顺着新情绪
4. **重大决策**（清仓/换主线/加仓 ≥ 2000 元）→ 等用户点头
5. **小决策**（网格/止损）→ 按 YAML 自动执行
6. **memory 只放索引**不放具体股票代码/价格/数量；具体事项归档到 yaml + reports/
7. **同样的索引归档原则适用于所有非股票事务**

### 减仓触发规则（2026-07-22 升级）

**旧规则（过度保守）**：「五档比 < 0.7 + 量能 1.5-2.5x」才触发减仓，要求双维度同时满足。
**问题**：今天 588080 五档比 0.119（极端值）但量能正常，按旧规则不触发，结果错失减仓窗口。

**新规则（三选二触发减仓 1/3，2026-07-22 起）**：
- 形态危险（连续阴线 + 单日反弹 + 远离 MA20）
- 五档比 < 0.5（极端卖盘挂单）
- 大盘弱势（沪深300 当日转弱）
- 三选二即触发减仓 1/3

**588080 明早 9:30 判定规则（2026-07-22 起）**：
- 高开 +1% 以上 + 五档比 > 1.0 → 维持持仓
- 低开 -1% 以上 + 五档比 < 0.5 → 减仓 1/3（新规矩）
- 现价 ≤ MA60 1.849 → 减仓 1/2
- 现价 ≤ 止损 1.640 → 全清

**详细判定框架**：见 `a-share-position-decision` skill 的"信号灯 + 分批走"段 + `playbook_active.yaml` 的 `discipline` 段。
**实战验证**：
- 2026-07-17 13:07-15:00 三次反悔全部被规则挡掉，结果避免抄在半山腰（见 decision_log.yaml）。
- 2026-07-22 588080 减仓请求被驳回（错过减仓窗口），导致当日 -3% 浮亏，**纪律系统颗粒度需要迭代**（教训已落库 decision_log.yaml）。

## 工作流

**建仓**：候选股触发信号 → 分析确认 → 建仓 → 从 `candidates_watch.yaml` 移除 → 加入 `positions_active.yaml` → 由持仓监控脚本盯盘

**清仓后清理**：
1. position 状态用 `status: sold`（不是 `cleared`，脚本只认 sold）
2. 删除 state 文件 `~/.hermes/scripts/.market_alert_state` 中对应代码行
3. 同步清监控 cron（`cronjob remove <id>`）

## 数据源（2026-07-19 弃用 adata）

⚠️ **adata v2.9.5 已退役**（2026-07-19 老大定）。
- 项目 7 个月没新 commit，参数名/cache/API 多处坏
- K 线返回 0 条；实时行情不可用；全 A 股列表卡死
- skill 已归档到 `~/.hermes/skills/.archive/adata-stock-data`

**改用 direct API**（skill: stock-data-tencent-api 内有完整函数）：
- 实时行情：腾讯 `qt.gtimg.cn` + 5 档（脚本 `~/.hermes/scripts/stock_quote.py` 待写）
- 历史 K 线：新浪 `quotes.sina.cn/.../getKLineData`
- 批量报价：东方财富 `push2.eastmoney.com/api/qt/ulist.np/get`
- 集合竞价阶段（09:15~09:25）：优先用新浪（prev_close 准确）

资金流/北向/概念/财务的 fallback：东方财富直 curl 接口（待补充 skill）

## 监控架构（2026-07-17）

- 统一脚本 `~/.hermes/scripts/stock_monitor.py`
- cron `1c6cd4c32caf`：no_agent=True，*/5 9-14 工作日
- 含 A 股时段过滤 + 单标单维每日一次防重
- **监控 cron 必须 no_agent=True**（避免 cron 注入扫描器误报）

## 散户身份

- 主账户 ~58,125 元，6 持仓 + 6 候选
- YAML（`monitor_positions.yaml` / `watched.yaml`）是 cron 单一事实源
- **新增/清仓后用户需主动告知**，我手动同步 YAML

## 股票台账持续化原则

每次分析/判定/触发必须沉淀到 `~/.hermes/stock-portfolio/decision_log.yaml`：
- 按 `code+date` 索引
- 字段：`trigger` / `analysis` / `decision` / `outcome_pending`
- memory 只保留台账路径索引，**不堆具体股票细节**
- 老大话："你应该有一个台账来记录这些事情，记忆中只要放个股票索引就行"

## 玲珑数据源补完（概念/资金/北向/涨停/评级/筹码）🟡 等老大明天决策

**触发**：7/23 14:xx 老大问"玲珑决策只能看技术指标，要怎么补 6 类数据"——研究 tdx_quant → 通达信 MCP 价格 → akshare / tushare 实测

**调研结论（7/23 实测）**：
- 1. **tdx_quant** (henrylin99/tdx_quant, 139 stars, 1 个月没 push) — 架构可借鉴，但 tdx_mcp 的 API key 不公开标价（服务 tdx.com.cn:3001，企业级，个人难拿）
- 2. **通达信 MCP** — 无公开定价，需 service@tdx.com.cn 商务洽谈，个人大概率被拒
- 3. **AmazingData 试用账号** (银河证券星耀数智) — 实测**只能**拿 get_code_list（1603 ETF 代码），K线/快照/财务/股东 全锁（err_code -97），PermissionCode 3|4|32|33 缺高级权限，2026-08-09 到期
- 4. **akshare** (1.18.53) — 走东财反爬严，3/6 接口 ConnectionError
- 5. **tushare 试用号** (token /home/yu/tk.csv) — K线+daily_basic+stock_basic 能用，moneyflow/hsgt/limit/cyq/concept/top_list 全部"没接口访问权限"，要 **5000+ 积分**

**真选项（老大待定）**：
- A. 充 tushare 官方 5000 积分（**~200-500 元/季**，永久解锁 14+ 类数据，资金/北向/涨停/财务/周月K/龙虎榜/融资融券/股东/分红/基金/指数/可转债/期货/宏观）
- B. 充 tushare 官方 15000 积分（**~1500 元/季**）— ⚠️ **比 5000 只多 30% 频次，不多数据种类**（老大已确认）
- C. 闲鱼 35 元 / 3 个月 / 15000 积分（**红旗：违反 tushare 协议 §2 黑产风险、IP 绑定、多人共享易封**）— **🟡 老大今天 18:xx 已收链接，明天问清楚再买**
- D. 不充，腾讯免费 + 手动维护

**🚨 闲鱼 4 大红旗（老大已看到，明早问 3 件事）**：
1. token 哪来的？（官方 1500 你卖 35 = 100% 黑产/批量号）
2. 卖多少份？（> 10 份 = 必封）
3. 被封退款吗？（基本跑路）
**官方证据**：
- tushare 服务协议 doc_id=405：明文禁止"通过任何非官方或授权途径获得的服务"
- GitHub issue #1865：token 绑 IP，IP 不在白名单直接拒
- 闲鱼近期对虚拟商品严打（南都/凤凰报道）

**接驳点（一旦 A 决定后要做）**：
- 写 `amazingdata_connector.py` / `tushare_connector.py`
- `perception.py` 集成新数据源
- `decision_engine.check_hard_rules()` 加新字段（资金净流入/北向持股变化/涨停连板/财务指标）
- 端到端验证 + 落库 `decision_log.yaml`

**已确认不影响**：当前 4 个 cron (b8ae5b8ca837/f371f5ab8931/a44e0a6d6d46/1af1d3ae2ace) 继续跑，LONGZHUA 标记全部保留

**B 路线（用 tushare 试用号）已放弃**——实测 daily 拿 0 条、daily_basic 1次/小时限速、6 类高级数据全无权限。试用号能力被高估。

**C 路线（闲鱼 35 元 / 3 个月 / huanghanchi）已采纳（2026-07-24）**—— 38/41 接口 92.7% 可用，5/6 类目标数据打通：
- 覆盖：daily / fund_daily / moneyflow / hsgt_top10 / hsgt_fund_flow / stock_hsgt / limit_list_d / cyq_perf / analyst_rank / fina_indicator / fund_basic / fund_nav / income / kpl_list / 港股 / 美股 / 期货 / 可转债 / 指数 / 宏观利率
- 不通：concept（服务端递归 bug 503）
- 凭证：`~/.hermes/config/xianyu_tushare_credentials.yaml`
- 客户端：`~/.hermes/scripts/tushare_xianyu.py`
- 缓存：`~/.hermes/cache/stock_data/xianyu_tushare/initial_cache_20260724.json`
- 风险：违反 tushare 服务协议 §2（非官方渠道），可能随时被封（无退款）；**7 天观察期（7/31 检 token 状态）**
- 完整复盘：decision_log.yaml 第 35 条 / 详细监控见下面"闲鱼 token 健康度检查"步骤

**接入优先级**（按已验证可用 + 用户最常用）：
1. **fund_daily**：5 只 ETF 的 fund_daily（替代新浪 hq.sinajs.cn 的 ETF K 线）
2. **moneyflow**：588080 资金流（替代 hourly detection）
3. **hsgt_top10**：每日 15:30 收盘后拉（替代东财 push2.eastmoney.com 的北向接口）
4. **limit_list_d**：板块涨停情绪（替代连板计算）
5. **cyq_perf**：筹码分布（5 只 ETF 不适用，仅 A 股）
6. **analyst_rank**：机构调研情绪（基础信号）

**闲鱼 token 健康度检查**（每周一 09:00 cron）：
```bash
python3 -c "
import sys; sys.path.insert(0, '/home/yu/.hermes/scripts')
from tushare_xianyu import call
r = call('fund_daily', {'ts_code': '588080.SH', 'start_date': '20260720', 'end_date': '20260724'})
if r.get('code') == 0 and r.get('data', {}).get('items'):
    print('✅ 闲鱼 token alive')
else:
    print(f'❌ 闲鱼 token dead: {r.get(\"msg\")}')
"
```

---

## 闲鱼 tushare 缓存策略（2026-07-31 老大拍板）

**老大决定**：**不缓存**。每次盘后做复盘/回测，按需直接调 HTTP。

**具体含义**：
- ✅ 闲鱼 tushare 接口可用于**复盘回测**（盘后 15:30 后 6 类决策数据：资金流 / 北向 / 涨停 / 分析师 / 筹码 / 概念）
- ❌ 不维护本地缓存（之前 7/24 的 `initial_cache_20260724.json` 已删）
- ❌ 不自动续拉（无 cron）
- ❌ 不改造 `call()` 函数（保持直打 HTTP，不查缓存）

**老大的取舍**：
- 优点：数据永远最新；接口被封时**减少被封面积**（没缓存文件没风险）
- 代价：接口被封或网络断 = 复盘回测暂时无法做

**调用模板**（盘后复盘回测时）：
```bash
python3.12 -c "
import sys; sys.path.insert(0, '/home/yu/.hermes/scripts')
from tushare_xianyu import call, get_etf_daily, get_moneyflow, get_hsgt_top10, get_limit_list
# 按需调用，每次打 HTTP
"
```

**接口实测状态（2026-07-31）**：
- ✅ token alive（7 天观察期通过）
- ✅ `fund_daily` / `daily` 数据已更新到 7/30（含今日盘中 `daily`）
- ✅ `hsgt_top10` / `limit_list_d` / `analyst_rank` / `stock_basic` 正常
- ⚠️ `moneyflow` 接口通但 0 条（日期范围无数据，不是接口坏）
- ❌ `concept` 服务端 503 recursion bug（未修复）
- ❌ `rt_k` timeout（盘中实时拿不到）