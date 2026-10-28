#!/usr/bin/python3.12
"""
集合竞价监控脚本 — 优先关注持仓股
每个交易日的 9:25 执行
数据源：monitor_positions.yaml (真实持仓) + portfolio.yaml (候选股)
"""

import urllib.request
import urllib.parse
import re
import os
import sys
import socket
import ssl
import http.client
from datetime import datetime

# ===================== 配置 =====================
MONITOR_FILE = '/home/yu/.hermes/stock-portfolio/monitor_positions.yaml'
PORTFOLIO_FILE = '/home/yu/.hermes/stock-portfolio/portfolio.yaml'
WATCHED_FILE = '/home/yu/.hermes/stock-portfolio/monitor_watched.yaml'
OUTPUT_FILE = '/home/yu/.hermes/cron/output/auction_monitor.txt'
# 竞价快照缓存（按交易日）：09:25 跑完固化，之后重跑仍显示 09:25 竞价数据，
# 避免开盘后「竞价量」变成累计成交量导致口径漂移。
SNAP_FILE = '/home/yu/.hermes/stock-portfolio/.auction_snapshot.json'
# 昨晚策略文档目录（承接待办的来源）
STRATEGY_DIR = '/home/yu/.hermes/cron/output'
STRATEGY_PREFIX = 'eod_strategy_'
# ===================== 配置 =====================

import yaml


def load_targets():
    """
    从 monitor_positions.yaml 读真实持仓（status=holding）
    从 portfolio.yaml 读候选股（watched_stocks + watched_funds）
    返回 (holdings, candidates)
    """
    HOLDINGS = []  # (market_code, name, stop_loss, tp1, tp2)
    CANDIDATES = []  # (market_code, name)

    # ─── 1. 真实持仓（monitor_positions.yaml） ───
    try:
        with open(MONITOR_FILE, 'r') as f:
            doc = yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] 无法读取 {MONITOR_FILE}: {e}", file=sys.stderr)
        doc = {}

    for p in doc.get('positions', []):
        if p.get('status') != 'holding':
            continue
        code = str(p.get('code', ''))
        name = p.get('name', '')
        market = p.get('market', 'sh')
        sl = p.get('stop_loss')
        tp1 = p.get('take_profit_1')
        tp2 = p.get('take_profit_2')
        note = p.get('note', '')
        # 台账 TP 是嵌套 take_profit 列表（level/target/status），旧扁平字段 take_profit_1/2 早已停用
        # → 只取 status=pending 的档位，否则止盈预警永远不触发
        tp_list = p.get('take_profit')
        if isinstance(tp_list, list):
            pend = [t.get('target') for t in tp_list
                    if isinstance(t, dict) and t.get('status') == 'pending' and t.get('target')]
            if pend:
                if tp1 is None:
                    tp1 = pend[0]
                if tp2 is None and len(pend) > 1:
                    tp2 = pend[1]
        # 观察期离场线（observation_mode_20261023.enabled）优先于台账 stop_loss
        # 原因：2026-10-23 老大定「剩余 3 只再观察一下」→ 台账 SL 早已破但语义是
        # 「不主动减仓」，真正的红线是 exit_line。玲珑 decision_engine 已用同样口径，
        # 竞价脚本不同步就会天天误报「已破止损！需处置」（与玲珑重复噪音同源）。
        obs = p.get('observation_mode_20261023')
        obs_on = False
        exit_line = None
        relief_lines = []
        if isinstance(obs, dict) and obs.get('enabled'):
            obs_on = True
            el = obs.get('exit_line')
            if el:
                try:
                    exit_line = float(el)
                except (TypeError, ValueError):
                    exit_line = None
            rl = obs.get('relief_lines') or ''
            relief_lines = [float(x) for x in re.findall(r'\d+\.\d+', str(rl))]

        if code and name:
            prefix = 'sh' if market == 'sh' else 'sz'
            HOLDINGS.append((f'{prefix}{code}', name, sl, tp1, tp2, note,
                             obs_on, exit_line, relief_lines))

    # ─── 2. 候选股（portfolio.yaml watched_stocks + watched_funds） ───
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            pf = yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] 无法读取 {PORTFOLIO_FILE}: {e}", file=sys.stderr)
        pf = {}

    # 候选ETF
    for w in pf.get('watched_funds', []):
        code = str(w.get('code', ''))
        name = w.get('name', '')
        market = w.get('market', 'sh')
        if code and name:
            prefix = 'sh' if market == 'sh' else 'sz'
            CANDIDATES.append((f'{prefix}{code}', name, None, None))

    # 候选股
    for w in pf.get('watched_stocks', []):
        code = str(w.get('code', ''))
        name = w.get('name', '')
        market = w.get('market', 'sh')
        if code and name:
            prefix = 'sh' if market == 'sh' else 'sz'
            CANDIDATES.append((f'{prefix}{code}', name, None, None))

    # 真实候选池（monitor_watched.yaml watched[]：带 entry_max/entry_min 触发区间）
    # —— portfolio.yaml 只列了 7 只，监控脚本 stock_monitor.py 用的是这 15 只，
    #    竞价报告必须与之一致，否则「距触发位」无从谈起。
    try:
        with open(WATCHED_FILE, 'r') as f:
            wdoc = yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] 无法读取 {WATCHED_FILE}: {e}", file=sys.stderr)
        wdoc = {}

    for w in (wdoc or {}).get('watched', []):
        code = str(w.get('code', ''))
        name = w.get('name', '')
        market = w.get('market', 'sh')
        if not (code and name):
            continue
        prefix = 'sh' if market == 'sh' else 'sz'
        kind = w.get('signal_type', 'pullback')
        emax = w.get('entry_max')
        emin = w.get('entry_min')
        rmn = w.get('ratio_min', 1.0) or 1.0
        sl = w.get('stop_loss')
        status = str(w.get('status') or '')
        suspended = status.startswith('cleared') or 'suspend' in status.lower()
        trig = None
        trig_str = None
        if emax:
            trig = (kind, float(emax), float(emin) if emin else None,
                    float(rmn), float(sl) if sl else None, suspended)
            trig_str = f"{float(emin):.3f}~{float(emax):.3f}" if emin else f"≤{float(emax):.3f}"
        CANDIDATES.append((f'{prefix}{code}', name, trig, trig_str))

    # 去重：候选不重复，且不包含已在持仓中的
    # ⚠️ 2026-10-27 修复：同一代码可能同时出现在 portfolio.yaml（无触发区间）
    # 和 monitor_watched.yaml（有 entry/止损/五档比门槛）。
    # 旧逻辑「先到先得」→ portfolio.yaml 的裸条目排在前面，把带触发区间的条目挤掉
    # （实测 512480 / 300444 触发区间显示 "--"，还漏掉了「已破止损不建仓」判定）。
    # 修复：同一代码保留「带触发信息」的那条（trig 非 None 优先）。
    holding_codes = {h[0] for h in HOLDINGS}
    by_code = {}
    for c in CANDIDATES:
        if c[0] in holding_codes:
            continue
        prev = by_code.get(c[0])
        if prev is None:
            by_code[c[0]] = c
        elif (prev[2] is None) and (c[2] is not None):
            # 新的有触发信息 → 替换旧的裸条目
            by_code[c[0]] = c
    CANDIDATES = list(by_code.values())

    return HOLDINGS, CANDIDATES


def fetch_tencent(codes):
    """腾讯接口批量获取行情
    ⚠️ 必须用 IPv4-only 解析 —— qt.gtimg.cn 的 IPv6 端点无响应（不回包），
    urllib 默认 IPv6 优先 → SSL 握手永久挂起 → 全表「数据获取失败」。
    monkey-patch socket.getaddrinfo 拦不住 http.client，必须显式取 AF_INET 地址。
    """
    url = f"https://qt.gtimg.cn/q={','.join(codes)}"
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path + ('?' + parsed.query if parsed.query else '')

    raw = None
    try:
        addrs = [a[4] for a in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)]
        sock = socket.create_connection(addrs[0], timeout=10)
        try:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
            conn = http.client.HTTPConnection(host, port, timeout=10)
            conn.sock = sock
            conn.request('GET', path, headers={'User-Agent': 'Mozilla/5.0'})
            raw = conn.getresponse().read().decode('gbk', errors='replace')
        finally:
            sock.close()
    except Exception as e:
        print(f"[WARN] IPv4 fetch 失败: {e}", file=sys.stderr)
        return {}

    data = {}
    for line in raw.strip().split('\n'):
        m = re.search(r'v_(\w+)="([^"]+)"', line)
        if not m:
            continue
        code = m.group(1)
        fields = m.group(2).split('~')
        if len(fields) < 40:
            continue

        try:
            name = fields[1]
            pre_close = float(fields[4]) if fields[4] else 0.0
            open_p = float(fields[5]) if fields[5] else 0.0
            vol = int(float(fields[6])) if fields[6] else 0
            chg_pct = float(fields[32]) if fields[32] else 0.0

            # 五档结构：买1..买5 = f[10](量) f[11](价) f[12](量) f[13](价) ...
            # → 只取偶数下标（成交量），否则把价格也加进比值，比值被严重扭曲
            def to_int(v):
                try:
                    return int(float(v))
                except:
                    return 0

            buy_total = sum(to_int(fields[i]) for i in (10, 12, 14, 16, 18))
            sell_total = sum(to_int(fields[i]) for i in (20, 22, 24, 26, 28))
            waipan_ratio = round(buy_total / sell_total, 2) if sell_total > 0 else 0.0

            # 五档比可靠性：任一侧挂单过少 → 比值是噪声
            # 2026-10-26 实测 159326 卖盘仅 449 手（约 4.5 万元深度）→ 比值 16.99，
            # 看着"买盘极强"实则是卖方无人挂单；159299 卖盘 106 手 → 6.28，同理。
            # 门槛取 500 手（与"薄量"口径一致）：薄侧 < 500 手时比值只当情绪温度计。
            ratio_reliable = min(buy_total, sell_total) >= 500

            # 竞价价 = parts[9]
            auction_px = float(fields[9]) if len(fields) > 9 and fields[9] else None

            data[code] = {
                'name': name,
                'pre_close': pre_close,
                'open': open_p,
                'price': float(fields[3]) if len(fields) > 3 and fields[3] else open_p,
                'auction_px': auction_px,
                'chg_pct': chg_pct,
                'vol': vol,
                'vol_wan': round(vol / 10000, 1),
                'amount_wan': float(fields[37]) if len(fields) > 37 and fields[37] else 0.0,
                'buy_total': buy_total,
                'sell_total': sell_total,
                'waipan_ratio': waipan_ratio,
                'ratio_reliable': ratio_reliable,
            }
        except Exception:
            continue
    return data


def holding_signal(d, sl, tp1, tp2, obs_on=False, exit_line=None, relief_lines=None):
    """
    持仓信号 — 更强调风险和机会

    观察期（observation_mode_20261023.enabled）口径：
    台账 stop_loss 已破但语义是「不主动减仓」，真正的红线是 exit_line。
    exit_line 破 → 🔴（必推清仓提醒）
    反弹到 relief_lines → 减亏离场提醒点（🟡，不是加仓信号）
    """
    chg = d['chg_pct']
    ratio = d['waipan_ratio']
    cur_open = d['open']
    pre_close = d['pre_close']
    relief_lines = relief_lines or []

    # 挂单过薄 → 五档比失真 → 视为中性 1.0，不参与信号判定
    if not d.get('ratio_reliable', True):
        ratio = 1.0

    # 竞价量过小（如 15 手）→ 五档比是空挂单噪声，不参与信号判定
    thin = d.get('vol', 0) < 500

    if not cur_open:
        return '⚠️竞价无成交'

    # ── 观察期口径：先判离场线 / 减亏线 ──
    if obs_on and exit_line:
        exit_dist = (cur_open - exit_line) / exit_line * 100
        if exit_dist < 0:
            return f'🔴破离场线{exit_dist:.1f}%！需处置'
        for rl in relief_lines:
            if cur_open >= rl:
                return f'🟡到减亏线{rl:.3f}（减亏离场提醒）'
        # 未触任何线 → 按离场线距离给风险提示（阈值 3% 与摘要块保持一致）
        if exit_dist <= 3.0:
            return f'🟠距离场线{exit_line:.3f}仅{exit_dist:.1f}%'
        return '⚪观察期(未触线)'

    # 检测是否接近止损
    near_stop = False
    near_tp = False
    if stop_loss and pre_close:
        stop_dist = (cur_open - stop_loss) / stop_loss * 100
        if stop_dist <= 2.0:  # 距止损2%以内（含已跌破）
            near_stop = True
    if tp1 and pre_close:
        tp_dist = (tp1 - cur_open) / cur_open * 100
        if tp_dist <= 2.0:  # 距TP1 2%以内
            near_tp = True

    # 信号判断（持仓→偏风险监控）
    if stop_loss and pre_close and cur_open and stop_loss:
        # 已跌破止损线：按跌破深度分级，比"接近止损"更严重
        stop_dist = (cur_open - stop_loss) / stop_loss * 100
        if stop_dist < 0:
            if stop_dist <= -5.0:
                return f'🔴已破止损{stop_dist:.1f}%！需处置'
            return f'🔴已破止损{stop_dist:.1f}%'
    if near_stop and ratio < 0.8:
        return '🔴临近止损！卖压重'
    elif near_stop:
        return '🟠接近止损线'
    elif chg <= -2.0 and ratio <= 0.5:
        return '🔴低开卖压重'
    elif chg <= -2.0:
        return '🟠低开'
    elif near_tp and ratio >= 1.2:
        return '🟢接近TP1买盘强'
    elif near_tp:
        return '🟡接近止盈线'
    elif chg >= 2.0 and ratio >= 1.2:
        return '🟢强势高开'
    elif chg >= 1.0 and ratio >= 1.0:
        return '🟡偏强'
    elif ratio <= 0.5 and chg <= -1.0:
        return '🟠卖压偏重'
    elif thin:
        return '⚪正常(竞价量薄)'
    else:
        return '⚪正常'


def cand_signal(d, trig=None):
    """候选股信号 — 偏机会监控
    trig: (kind, emax, emin, rmn, sl) —— 与 stock_monitor.py check_watched() 完全同口径：
      reversal / new_theme : 现价 ≥ entry_max 且 五档比 ≥ ratio_min  → 建仓评估
      pullback              : 现价 ≤ entry_max 且 五档比 ≥ ratio_min  → 建仓评估
      已跌破自身 stop_loss 的候选 一律不推建仓信号（自相矛盾）
      status=cleared_* 的候选建仓信号已暂停
    """
    chg = d['chg_pct']
    ratio = d['waipan_ratio']
    # 现价优先（开盘后 f[3]），竞价阶段 f[3] == f[5] == 匹配价，回退 f[5]
    price = d.get('price') or d.get('open') or 0

    # 挂单过薄 → 比值失真 → 视为中性 1.0
    ratio_unreliable = not d.get('ratio_reliable', True)
    if ratio_unreliable:
        ratio = 1.0

    if not trig or not price:
        # 无触发区间信息 → 只做情绪判定
        return _emotion_signal(chg, ratio, ratio_unreliable)

    kind, emax, emin, rmn, sl, suspended = trig

    if suspended:
        return '⏸️建仓信号已暂停'

    # 坑 1（与 stock_monitor.py 2026-10-23 修复一致）：已破自身止损位不推建仓
    if sl and price <= float(sl):
        return f'⛔已破止损{float(sl):g}不建仓'

    hit = False
    if kind in ('reversal', 'new_theme'):
        hit = price >= emax and ratio >= rmn
    else:  # pullback
        hit = price <= emax and ratio >= rmn

    if hit:
        # ⚠️ 比值不可靠时不能触发 —— 中性 1.0 会假满足 ratio_min 条件
        if ratio_unreliable:
            base = f'价已到位≥{emax:g}' if kind in ('reversal', 'new_theme') else f'价已回调≤{emax:g}'
            return f'🟡{base}·五档比待确认(挂单薄)'
        if kind == 'new_theme':
            return f'🟢达建仓评估位≥{emax:g}(五档比{ratio:.2f})'
        if kind == 'reversal':
            return f'🟢反弹确认站回{emax:g}(五档比{ratio:.2f})'
        return f'🟢回调到位≤{emax:g}(五档比{ratio:.2f})'

    # 未触发 → 显示距触发位多远
    if kind in ('reversal', 'new_theme'):
        if price >= emax:
            # 价格已到位，仅差五档比条件
            return f'🟡价已到位≥{emax:g}·等五档比≥{rmn:g}(现{ratio:.2f})'
        gap = (emax - price) / price * 100
        if gap <= 3.0:
            return f'🟡距触发位{emax:g}仅{gap:.1f}%'
        return f'⚪距触发位{emax:g}差{gap:.1f}%'
    if price <= emax:
        return f'🟡价已回调≤{emax:g}·等五档比≥{rmn:g}(现{ratio:.2f})'
    gap = (price - emax) / emax * 100
    if gap <= 3.0:
        return f'🟡距回调位{emax:g}仅{gap:.1f}%'
    return f'⚪距回调位{emax:g}差{gap:.1f}%'


def _emotion_signal(chg, ratio, ratio_unreliable=False):
    """无 entry 区间时的纯情绪判定

    ⚠️ 2026-10-27 修复：挂单薄时 ratio 被置为中性 1.0，
    旧逻辑只按 ratio 判定 → 低开 -5.33% 的万集科技(ratio 0.17)被判成「⚪正常」，
    严重低开完全被吞掉。修复：低开/大跌优先按 chg 判定，ratio 只作增强。
    """
    # 严重低开（不论挂单厚薄）优先报出
    if chg <= -5.0:
        return '🔴大幅低开'
    if chg <= -2.0:
        if ratio_unreliable or ratio <= 0.5:
            return '🔴低开异常'
        return '🟠低开'
    # 上涨侧（需 ratio 支持，但薄挂单时不能把 ratio=1.0 当真）
    if ratio_unreliable:
        if chg >= 2.0:
            return '🟡涨幅待确认(挂单薄)'
        if chg >= 1.0:
            return '⚪小幅高开(挂单薄)'
        return '⚪正常'
    if ratio >= 1.5 and chg >= 1.5:
        return '🟢异动拉升'
    if ratio >= 1.2 and chg >= 2.0:
        return '🟢放量突破'
    if ratio >= 1.2 and chg >= 1.0:
        return '🟡偏强'
    if ratio >= 1.0 and chg >= 1.5:
        return '🟡稳量上行'
    if ratio <= 0.5 and chg <= -2.0:
        return '🔴低开异常'
    if ratio <= 0.7:
        return '🟠卖压重'
    return '⚪正常'


def load_pending_actions(today_str, holdings, data):
    """解析最近一份 eod_strategy_*.md → 今日待执行的持仓动作 + 竞价条件核对。

    ⚠️ 2026-10-28 新增：竞价报告此前**完全不承接**昨晚策略的待办动作，
    导致「513050 ≤0.930 清 7,000 份」这类今日执行项只存在于晚报文件里，
    老大在 09:25 看不到 → 本函数把动作拉进竞价报告并标注条件状态。

    纪律（SKILL.md「竞价快照 ≠ 触发证据」）：
    价格条件可由竞价验证；时间条件（5 分钟不反弹）/ 五档比条件**不可**，
    一律写「价格条件已满足 · 时间/挂单条件待 09:30 后确认」，**不得写「触发」**。
    """
    import glob
    import re

    files = sorted(glob.glob(os.path.join(STRATEGY_DIR, STRATEGY_PREFIX + '*.md')))
    # 排除今天的文件（今天 21:00 的晚报是给明天的）
    # ⚠️ 文件名日期是 20261027（无分隔符），today_str 是 2026-10-28 → 必须先归一化再比
    def _fname_date(p):
        raw = os.path.basename(p)[len(STRATEGY_PREFIX):-3]
        if len(raw) == 8 and raw.isdigit():
            return f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
        return raw
    files = [f for f in files if _fname_date(f) < today_str]
    if not files:
        return [], None
    path = files[-1]
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    except Exception:
        return [], None

    # 目标日声明校验（P0-54）：文内声明的目标日必须等于今天，否则不承接
    # 支持两种写法：「策略针对 **10/28（星期三）**」与「策略针对 10/28」
    tm = re.match(r'(\d{4})-(\d{2})-(\d{2})', today_str)
    if tm:
        want = (tm.group(2), tm.group(3))
        declared = None
        for dm in re.finditer(r'策略针对[^\n]*?(\d{1,2})\s*[/月]\s*(\d{1,2})\s*日?', text):
            declared = (f'{int(dm.group(1)):02d}', f'{int(dm.group(2)):02d}')
            break
        if declared and declared != want:
            return [], None

    # 定位「操作策略」段
    sec = ''
    for mm in re.finditer(r'##\s*[^\n]*操作策略[^\n]*\n(.*?)(?=\n##\s|\Z)', text, re.S):
        sec = mm.group(1)
        break
    if not sec:
        return [], None

    # 代码 → 带市场前缀（从持仓表反查；非持仓代码不在持仓表里 → 跳过）
    code_map = {}
    for mc, name, *_ in holdings:
        code_map[mc[2:]] = (mc, name)

    actions = []
    notes = []
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 4:
            continue
        if cells[0].startswith('---') or cells[0].startswith(':'):
            continue
        if cells[0] == '时点':
            continue
        when, tgt, act, cond = cells[0], cells[1], cells[2], cells[3]
        risk = cells[4] if len(cells) > 4 else ''

        cm = re.search(r'(\d{6})', tgt)
        if not cm:
            # 非持仓行（如「候选池 一律不建仓」）→ 记为备注行
            if '候选' in tgt:
                notes.append({'when': when, 'target': tgt, 'action': act, 'cond': cond})
            continue
        raw_code = cm.group(1)
        if raw_code not in code_map:
            continue
        mc, name = code_map[raw_code]

        # 触发条件里的主价位 + 方向（只认全角 ≤ ≥，避免匹配 "0.96 < 1.0" 这类）
        thr = None
        cmp = None
        tm2 = re.search(r'(≤|≥)\s*(\d+\.\d+)', cond)
        if tm2:
            cmp = tm2.group(1)
            thr = float(tm2.group(2))
        has_time = bool(re.search(r'不反弹|不回升|反抽不回|分钟', cond))
        has_ratio = '五档比' in cond

        d = data.get(mc) or {}
        price = d.get('open') or 0
        price_ok = None
        if thr is not None and price:
            price_ok = (price <= thr) if cmp == '≤' else (price >= thr)

        actions.append({
            'mc': mc, 'code': raw_code, 'name': name, 'when': when,
            'action': act, 'cond': cond, 'risk': risk,
            'thr': thr, 'cmp': cmp, 'price': price,
            'price_ok': price_ok, 'has_time': has_time, 'has_ratio': has_ratio,
        })

    src = os.path.basename(path)
    return actions, {'src': src, 'notes': notes}


def _pending_status(a):
    """把竞价核对结果翻译成一句话状态"""
    if a['price_ok'] is None:
        return '价格条件待确认（无明确价位）'
    if not a['price_ok']:
        if a['cmp'] == '≤':
            gap = (a['price'] - a['thr']) / a['thr'] * 100
            return f"价格条件未满足（竞价 {a['price']:.3f} 需回落 {gap:.1f}% 至 ≤{a['thr']:g}）→ 今日暂不触发"
        gap = (a['thr'] - a['price']) / a['price'] * 100
        return f"价格条件未满足（竞价 {a['price']:.3f} 需反弹 {gap:.1f}% 至 ≥{a['thr']:g}）→ 今日暂不触发"
    extra = []
    if a['has_time']:
        extra.append('时间条件')
    if a['has_ratio']:
        extra.append('五档比条件')
    if extra:
        return f"✅ 价格条件已满足 · {'/'.join(extra)}待 09:30 后确认"
    return '✅ 价格条件已满足'


def fetch_minute(code):
    """腾讯分时接口 → (date, bars)

    ⚠️ 2026-10-28 新增：开盘后复核「N 分钟不反弹」类时间条件用。
    ⚠️ 返回结构是两层：d['data'][code]['data'] = {'data': ['HHMM 价格 累计量 累计额', ...], 'date': 'YYYYMMDD'}
    —— 注意里层还有一层 dict，直接取 node['data'] 会拿到 dict 不是 list（10/28 实测踩过）。
    """
    import json
    url = f'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={code}'
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path + ('?' + parsed.query if parsed.query else '')
    try:
        addrs = [a[4] for a in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)]
        sock = socket.create_connection(addrs[0], timeout=10)
        try:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
            conn = http.client.HTTPConnection(host, port, timeout=10)
            conn.sock = sock
            conn.request('GET', path, headers={'User-Agent': 'Mozilla/5.0'})
            raw = conn.getresponse().read().decode('utf-8', errors='replace')
        finally:
            sock.close()
        node = json.loads(raw)['data'][code]['data']
        bars = [r.split() for r in node['data']]
        return node.get('date'), bars
    except Exception as e:
        print(f"[WARN] 分时获取失败 {code}: {e}", file=sys.stderr)
        return None, []


def verify_pending_post_open(pending, window_minutes=5):
    """开盘后复核：把「价格条件 + 时间条件(5 分钟不反弹)」逐条判定。

    ⚠️ 2026-10-28 新增。纪律（SKILL.md「竞价快照 ≠ 触发证据」）：
    只有**价格条件与时间条件同时成立**才写「完整触发」；
    价格条件成立但时间条件不成立 → 写「时间条件不成立 → 未触发」；
    价格条件不成立 → 写「价格条件未满足 → 未触发」（无论时间条件如何）。
    """
    cache = {}
    results = []
    for a in pending:
        r = dict(a)
        r['verify'] = None
        if a['mc'] not in cache:
            cache[a['mc']] = fetch_minute(a['mc'])
        date, bars = cache[a['mc']]
        if not bars or not a['thr']:
            r['verify'] = '无分时数据 / 无明确价位，未复核'
            results.append(r)
            continue

        prices = [float(b[1]) for b in bars]
        op = prices[0]
        # 5 分钟窗口 = 0930~0934
        w5 = [float(b[1]) for b in bars if '0930' <= b[0] <= '0934']
        hi5 = max(w5) if w5 else op
        hi_all = max(prices)
        lo_all = min(prices)
        last = prices[-1]

        if a['cmp'] == '≤':
            px_ok = op <= a['thr']
        else:
            px_ok = op >= a['thr']

        rebound = None
        if a['has_time']:
            # 从触发条件里提取反弹阈值（「不回升 0.946」/「反抽不回 0.6582」）
            rm = re.search(r'(?:不回升|反抽不回|不反弹)\s*([\d.]+)', a['cond'])
            if rm:
                rebound = float(rm.group(1))
                reb_hit = hi_all >= rebound
            else:
                reb_hit = None
        else:
            reb_hit = None

        r['open_px'] = op
        r['hi5'] = hi5
        r['hi_all'] = hi_all
        r['lo_all'] = lo_all
        r['last_px'] = last
        r['bars_end'] = bars[-1][0]
        r['rebound_thr'] = rebound

        if not px_ok:
            r['verify'] = f"价格条件未满足（开盘 {op:.3f}，需{'≤' if a['cmp'] == '≤' else '≥'}{a['thr']:g}）→ **未触发**"
        elif rebound is not None and reb_hit:
            r['verify'] = f"价格条件满足，但已反弹至 {hi_all:.3f}（≥{rebound:g}）→ **未触发**（反弹条件不成立）"
        elif rebound is not None:
            r['verify'] = (f"价格条件满足（开盘 {op:.3f} ≤ {a['thr']:g}），"
                           f"至 {bars[-1][0]} 未反弹 {rebound:g}（区间高 {hi_all:.3f}）→ **完整触发**")
        else:
            r['verify'] = f"价格条件满足（开盘 {op:.3f}）→ 触发（无条件型）"

        # 五档比条件（需实时比值，薄挂单时不作准）
        if a['has_ratio']:
            r['verify'] += "｜五档比条件须实时盘口复核"
        results.append(r)
    return results


def _pad(s, width, align='<'):
    """按**终端显示宽度**补空格（中文算 2 列）

    2026-10-27 修复：f-string 的 :<10 是按字符数补齐，
    中文名（2 字符宽）会把表格挤歪（实测「半导体ETF国联安」与代码列重叠）。
    """
    import unicodedata
    w = sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in str(s))
    fill = max(0, width - w)
    return str(s) + ' ' * fill if align == '<' else ' ' * fill + str(s)


def _rpad(s, width):
    """右对齐（按显示宽度）"""
    import unicodedata
    w = sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in str(s))
    return ' ' * max(0, width - w) + str(s)


def build_report(data, holdings, candidates, source='实时', phase='auction', stamp=None,
                 pending=None, pending_src=None, verify_note=''):
    """生成报告（文本+Markdown混合）
    phase='auction'  : 09:25 竞价窗口内 → 列名用「开盘价/竞价量」
    phase='intraday' : 已开盘 → 持仓仍用 09:25 快照列名，候选用「现价/成交量」
    stamp            : 报告时间戳（replay 时传 09:25，避免显示成重跑时刻）
    """
    today = datetime.now().strftime('%Y-%m-%d')
    now = stamp or datetime.now().strftime('%H:%M:%S')
    lines = []
    lines.append(f"**📊 集合竞价日报 · {today} {now}**")
    lines.append("")

    # ── 1. 持仓优先展示 ──
    lines.append("━━━ **📌 持仓股** ━━━")
    lines.append("")
    lines.append("```")
    lines.append(f"{_pad('股票', 20)}{_pad('代码', 12)}{_rpad('开盘价', 8)}{_rpad('涨跌%', 9)}{_rpad('竞价量', 10)}{_rpad('五档比', 8)}  信号")
    lines.append("-" * 75)

    holding_rows = []
    for mc, name, sl, tp1, tp2, note, obs_on, exit_line, relief_lines in holdings:
        d = data.get(mc)
        if not d:
            holding_rows.append(f"{_pad(name, 20)}{_pad(mc, 12)}{_rpad('--', 8)}{_rpad('--', 9)}{_rpad('--', 10)}{_rpad('--', 8)}  ⚠️数据获取失败")
            continue

        sig = holding_signal(d, sl, tp1, tp2, obs_on, exit_line, relief_lines)
        chg_str = f"{d['chg_pct']:+.2f}%"
        vol_str = f"{d['vol_wan']:.1f}万"
        ratio_str = f"{d['waipan_ratio']:.2f}"
        open_str = f"{d['open']:.3f}"

        # open=0 → 竞价无成交（不是「平稳」），必须显式标注
        if d['open'] == 0:
            open_str = '0.000'
            sig = '⚠️竞价无成交'
        else:
            if not d.get('ratio_reliable', True):
                ratio_str += '?'
                if '薄' not in sig:
                    sig += '(挂单薄·比值失真)'
            elif d.get('vol', 0) < 500 and '薄' not in sig:
                sig += '(薄量)'

        holding_rows.append(
            f"{_pad(name, 20)}{_pad(mc, 12)}{_rpad(open_str, 8)}{_rpad(chg_str, 9)}{_rpad(vol_str, 10)}{_rpad(ratio_str, 8)}  {sig}"
        )

    lines.extend(holding_rows)
    lines.append("```")

    # 持仓摘要：观察期离场线 / 减亏线（观察期优先），否则止损/止盈距离
    sl_alerts = []
    tp_alerts = []
    for (mc, name, sl, tp1, tp2, note, obs_on, exit_line, relief_lines), row in zip(holdings, holding_rows):
        d = data.get(mc)
        if not d or not d.get('open'):
            continue
        cur = d['open']
        if obs_on and exit_line:
            dist = (cur - exit_line) / exit_line * 100
            if dist < 0:
                sl_alerts.append(f"  🔴 {name}: 已破观察期离场线{exit_line:.3f} {dist:.1f}% (竞价{cur:.3f})")
            elif dist <= 3.0:
                sl_alerts.append(f"  🟠 {name}: 距观察期离场线{exit_line:.3f}仅{dist:.1f}% (竞价{cur:.3f})")
            for rl in relief_lines:
                if cur >= rl:
                    tp_alerts.append(f"  {name}: 已到减亏线{rl:.3f} (竞价{cur:.3f}) — 减亏离场提醒点,非加仓信号")
            continue
        if sl and sl > 0:
            sl_dist = (cur - sl) / sl * 100
            if sl_dist < 0:
                sl_alerts.append(f"  🔴 {name}: 已破止损{sl:.2f} {sl_dist:.1f}% (现价{cur:.3f})")
            elif sl_dist <= 3.0:
                sl_alerts.append(f"  🟠 {name}: 距止损{sl:.2f}仅{sl_dist:.1f}% (现价{cur:.3f})")
        if tp1 and tp1 > 0:
            tp_dist = (tp1 - cur) / cur * 100
            if 0 <= tp_dist <= 3.0:
                tp_alerts.append(f"  {name}: 距TP1{tp1:.2f}仅{tp_dist:.1f}% (现价{cur:.3f})")
            elif tp_dist < 0:
                tp_alerts.append(f"  🎯 {name}: 已过TP1{tp1:.2f} {abs(tp_dist):.1f}% (现价{cur:.3f})")

    if sl_alerts:
        lines.append("")
        lines.append("⚠️ **止损预警**")
        for a in sl_alerts:
            lines.append(a)
    if tp_alerts:
        lines.append("")
        lines.append("🎯 **接近止盈**")
        for a in tp_alerts:
            lines.append(a)

    # ── 2. 候选股 ──
    if candidates:
        lines.append("")
        lines.append("━━━ **📎 候选股** ━━━")
        lines.append("")
        lines.append("```")
        cand_price_col = '现价' if phase == 'intraday' else '开盘价'
        cand_vol_col = '成交量' if phase == 'intraday' else '竞价量'
        lines.append(f"{_pad('股票', 20)}{_pad('代码', 12)}{_rpad(cand_price_col, 8)}{_rpad('涨跌%', 9)}{_rpad(cand_vol_col, 10)}{_rpad('五档比', 8)}{_rpad('触发区间', 16)}  信号")
        lines.append("-" * 98)

        for mc, name, trig, trig_str in candidates:
            d = data.get(mc)
            if not d:
                lines.append(f"{_pad(name, 20)}{_pad(mc, 12)}{_rpad('--', 8)}{_rpad('--', 9)}{_rpad('--', 10)}{_rpad('--', 8)}{_rpad(trig_str or '--', 16)}  ⚠️数据获取失败")
                continue

            sig = cand_signal(d, trig)
            chg_str = f"{d['chg_pct']:+.2f}%"
            vol_str = f"{d['vol_wan']:.1f}万"
            ratio_str = f"{d['waipan_ratio']:.2f}"
            open_str = f"{d['open']:.3f}"

            # 已开盘后 f[3] 才是现价（f[5] 仍是当日开盘价）
            if phase == 'intraday' and d.get('price'):
                open_str = f"{d['price']:.3f}"

            if d['open'] == 0:
                open_str = '0.000'
                sig = '⚠️竞价无成交'
            else:
                if not d.get('ratio_reliable', True):
                    ratio_str += '?'
                    if '薄' not in sig:
                        sig += '(挂单薄·比值失真)'
                elif d.get('vol', 0) < 500 and '薄' not in sig:
                    sig += '(薄量)'

            lines.append(
                f"{_pad(name, 20)}{_pad(mc, 12)}{_rpad(open_str, 8)}{_rpad(chg_str, 9)}{_rpad(vol_str, 10)}{_rpad(ratio_str, 8)}{_rpad(trig_str or '--', 16)}  {sig}"
            )

        lines.append("```")

    # ── 3. 承接待办（昨晚策略 → 今日动作 + 竞价条件核对）──
    # ⚠️ 2026-10-28 新增：竞价报告此前不承接昨晚策略的待办动作，
    # 老大在 09:25 看不到今日要执行什么 → 现在放在「竞价要点」之前。
    if pending:
        lines.append("")
        lines.append("━━━ **📌 承接待办（昨晚策略 → 今日）** ━━━")
        lines.append("")
        lines.append(f"*来源：{pending_src.get('src', '')} {verify_note}*")
        lines.append("")
        lines.append("```")
        for a in pending:
            status = _pending_status(a)
            # 🔴 = 价格条件已满足 → 动作待处置（需开盘后复核时间/挂单条件）
            # ⚪ = 价格条件未满足 → 本条动作今日不触发（不是「预警」，是「暂不触发」）
            flag = '🔴' if a['price_ok'] else '⚪'
            if a.get('verify'):
                lines.append(f"{_pad(a['when'], 8)}{_pad(a['name'], 20)}{_pad(a['action'], 16)}{flag} {a['verify']}")
            else:
                lines.append(f"{_pad(a['when'], 8)}{_pad(a['name'], 20)}{_pad(a['action'], 16)}{flag} {status}")
            lines.append(f"        触发条件：{a['cond']}")
            if a['risk']:
                lines.append(f"        风险点：{a['risk']}")
        if pending_src and pending_src.get('notes'):
            for n in pending_src['notes']:
                lines.append(f"{_pad(n['when'], 8)}{_pad(n['target'], 20)}{_pad(n['action'], 16)}⚪ {n['cond']}")
        lines.append("```")
        lines.append("")
        lines.append("*⚠️ 竞价快照 ≠ 触发证据：价格条件可由竞价验证，时间/五档比条件须用 09:30 后真实数据逐条复核*")

    # ── 4. 汇总重点 ──
    lines.append("")
    lines.append("━━━ **📈 竞价要点** ━━━")

    # 持仓风险汇总
    hold_danger = []
    hold_good = []
    for mc, name, sl, tp1, tp2, note, obs_on, exit_line, relief_lines in holdings:
        d = data.get(mc)
        if not d:
            continue
        sig = holding_signal(d, sl, tp1, tp2, obs_on, exit_line, relief_lines)
        if '🔴' in sig:
            hold_danger.append(f"🔴 {name}：{sig}")
        elif '🟢' in sig:
            hold_good.append(f"🟢 {name}：{sig}")
        elif '🟠' in sig:
            hold_danger.append(f"🟠 {name}：{sig}")
        elif '🟡' in sig:
            hold_good.append(f"🟡 {name}：{sig}")

    # 候选机会汇总
    cand_ops = []
    for mc, name, trig, trig_str in candidates:
        d = data.get(mc)
        if not d:
            continue
        sig = cand_signal(d, trig)
        if '🟢' in sig:
            cand_ops.append(f"🟢 {name}：{sig}")
        elif '🟡' in sig:
            cand_ops.append(f"🟡 {name}：{sig}")

    if hold_danger:
        lines.append("⚠️ **需关注的持仓**")
        for a in hold_danger:
            lines.append(f"  {a}")
    else:
        lines.append("✅ **持仓竞价正常，无风险信号**")

    if hold_good:
        lines.append("")
        lines.append("💪 **持仓强势信号**")
        for a in hold_good:
            lines.append(f"  {a}")

    if cand_ops:
        lines.append("")
        lines.append("👀 **候选股机会**")
        for a in cand_ops:
            lines.append(f"  {a}")

    if not hold_danger and not hold_good and not cand_ops:
        lines.append("  （整体竞价平淡，无极端信号）")

    lines.append("")
    lines.append(f"*竞价量单位：万手 | 五档比=买盘÷卖盘 | >1买方强 <1卖方强 | 数据源口径：{source}*")
    lines.append("*⚠️ 持仓触发 🔴/🟠 信号应优先处理*")
    lines.append("*⚠️ 竞价快照 ≠ 触发证据：执行类动作（清仓/减仓）须用 09:30 后真实数据复核*")

    return '\n'.join(lines)


def load_snapshot(date_str):
    """载入当日已固化的竞价快照（若存在）"""
    import json
    try:
        with open(SNAP_FILE, 'r') as f:
            doc = json.load(f)
    except Exception:
        return {}
    return doc.get(date_str, {}) or {}


def save_snapshot(date_str, data):
    """固化当日竞价快照（09:25 那一次的数据）"""
    import json
    try:
        doc = {}
        if os.path.exists(SNAP_FILE):
            with open(SNAP_FILE, 'r') as f:
                doc = json.load(f)
    except Exception:
        doc = {}
    doc[date_str] = data
    # 只保留最近 5 个交易日
    keys = sorted(doc.keys())[-5:]
    doc = {k: doc[k] for k in keys}
    with open(SNAP_FILE, 'w') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def main():
    HOLDINGS, CANDIDATES = load_targets()

    # 所有需查询的代码
    all_codes = [h[0] for h in HOLDINGS] + [c[0] for c in CANDIDATES]
    if not all_codes:
        print("⚠️ 无持仓或候选股可监控")
        return

    today = datetime.now().strftime('%Y-%m-%d')
    now_hm = datetime.now().strftime('%H:%M')
    snap = load_snapshot(today)

    # ── replay 模式：用当日已固化的 09:25 快照重建竞价报告 ──
    # 用途：修完信号逻辑后重发一份**口径纯正**的竞价报告（不开盘后实时数据混入）。
    # 不带 --replay 时的正常行为不变。
    replay = '--replay' in sys.argv
    if replay:
        if not snap:
            print(f"⚠️ {today} 无竞价快照，无法 replay")
            return
        data = snap
        source = '09:25竞价快照(replay)'
        phase = 'auction'
    else:
        # 始终取实时全量（候选股需要），再用 09:25 快照覆盖已有快照的标的，
        # 保证「竞价量」对持仓保持 09:25 口径、候选用最新可用数据。
        data = fetch_tencent(all_codes)
        if snap:
            # ⚠️ 2026-10-27 修复：快照里存的是「全量代码」，旧代码把快照回灌到全部标的，
            # 实际覆盖了候选股 → 但脚注却写「候选=实时」，口径不符。
            # 修复：只用快照覆盖**持仓**，候选一律用实时数据。
            hold_codes = {h[0] for h in HOLDINGS}
            for code, row in snap.items():
                if code in hold_codes:
                    data[code] = row
            source = '持仓=09:25竞价快照 / 候选=实时'
        else:
            source = '实时(09:25竞价)'

        phase = 'auction' if now_hm <= '09:29' else 'intraday'

    # 承接待办：昨晚策略里的今日动作（replay 也用，避免重跑丢信息）
    pending, pending_meta = load_pending_actions(today, HOLDINGS, data)

    # 开盘后（09:30+）→ 用分时逐条复核「价格 + 5 分钟不反弹」条件
    # ⚠️ 竞价快照只能验价格条件；时间条件必须用 09:30 后真实成交数据判定。
    verify_note = ''
    if pending and now_hm > '09:29' and not replay:
        pending = verify_pending_post_open(pending)
        verify_note = '（已用 09:30 后分时数据逐条复核）'

    report = build_report(data, HOLDINGS, CANDIDATES, source, phase,
                          stamp='09:25:00' if replay else None,
                          pending=pending, pending_src=pending_meta,
                          verify_note=verify_note)

    # 首次运行（09:25 竞价窗口内）固化快照
    if not snap and phase == 'auction' and not replay:
        save_snapshot(today, data)

    # 写文件
    with open(OUTPUT_FILE, 'w') as f:
        f.write(report)

    print(report)


if __name__ == '__main__':
    main()
