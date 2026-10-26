#!/usr/bin/env python3.12
"""
晨报生成脚本 - 简化版
功能：外盘数据 + 持仓行情 + 飞书推送
"""
import socket
import ssl
import http.client
import urllib.request
import urllib.parse
import json
import re
import hmac
import hashlib
import base64
import time
import yaml
from datetime import datetime
from pathlib import Path

# ============ 强制 IPv4 的 fetch（避免 IPv6 hang）============
def fetch(url, headers=None, timeout=10, enc='gbk'):
    """强制 IPv4 连接，避免 IPv6 卡死

    ⚠️ enc 参数：腾讯/新浪行情是 GBK，东财 datacenter-web / push2his 是 UTF-8。
    用 GBK 解 UTF-8 的 JSON 会有把引号吃掉的风险 → 东财接口必须显式 enc='utf-8'。
    """
    headers = headers or {'User-Agent': 'Mozilla/5.0'}
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    path = parsed.path or '/'
    if parsed.query:
        path += '?' + parsed.query

    # DNS 解析 - 仅 IPv4
    addrs = [a[4] for a in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)]
    if not addrs:
        raise OSError(f'No IPv4 address for {host}')
    addr = addrs[0]

    sock = socket.create_connection(addr, timeout=timeout)
    try:
        if parsed.scheme == 'https':
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)

        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.sock = sock
        conn.request('GET', path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        return raw.decode(enc, errors='replace')
    finally:
        sock.close()


# ============ 配置 ============
# ⚠️ 持仓数据源切换：portfolio.yaml 是僵尸文件（6/23 后未更新），
# 改读 monitor_positions.yaml（实时维护，holding 状态为准）
PORTFOLIO_FILE = Path.home() / '.hermes/stock-portfolio/portfolio.yaml'  # 已废弃（2026-06-23 后停更，仅留作历史参考，不再读取）
MONITOR_POSITIONS_FILE = Path.home() / '.hermes/stock-portfolio/monitor_positions.yaml'  # 唯一权威持仓源
POSITIONS_ACTIVE_FILE = Path.home() / '.hermes/stock-portfolio/positions_active.yaml.deprecated-20260724'  # 2026-07-24 废弃：双源已统一到 monitor_positions.yaml
OUTPUT_DIR = Path.home() / '.hermes/cron/output/1af1d3ae2ace'

# 飞书推送
FEISHU_BOT_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fbfd7f01-878c-4ece-80e6-5e7324ab3692"
FEISHU_SECRET = "9vXyEvLigZ70Ynw1YeUtI"


def send_feishu(msg):
    """发送飞书（带签名验证）"""
    timestamp = int(time.time())
    string_to_sign = f"{timestamp}\n{FEISHU_SECRET}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    
    payload = {
        "msg_type": "text",
        "content": {"text": msg},
        "timestamp": timestamp,
        "sign": sign
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(FEISHU_BOT_URL, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"⚠️ 飞书推送失败: {e}")
        return None
def get_global_indices():
    """获取全球指数：美股、日经、港股

    历史教训（2026-07-22）：
    - 旧版本用腾讯 usNDX/usDJI/usINX，但有缓存问题（晨报显示纳指 29155，实际 25837）
    - 修复：优先 Yahoo Finance（实测数据正确），腾讯接口作备用
    """
    result = {}

    # 美股指数 - 优先 Yahoo Finance（实测数据准确）
    us_codes_yf = {
        '^NDX': '纳斯达克100',
        '^DJI': '道琼斯',
        '^SPX': '标普500',  # ⚠️ 腾讯代码是 usINX，不是 usSPX
    }
    yf_success = False
    try:
        for sym, name in us_codes_yf.items():
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?interval=1d&range=5d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode('utf-8'))
            meta = data['chart']['result'][0]['meta']
            price = meta.get('regularMarketPrice', 0)
            prev = meta.get('chartPreviousClose', 0)
            if price and prev:
                chg = (price / prev - 1) * 100
                result[name] = {'price': price, 'prev': prev, 'chg': chg}
        yf_success = bool(result)
        if yf_success:
            print(f"  ✅ 美股数据从 Yahoo Finance 获取 ({len(result)} 个指数)")
    except Exception as e:
        print(f"  Yahoo Finance 美股数据获取失败: {e}")

    # Yahoo 失败时回退到腾讯接口
    if not yf_success:
        us_codes_tx = {'usNDX': '纳斯达克100', 'usDJI': '道琼斯', 'usINX': '标普500'}
        try:
            raw = fetch(f"https://qt.gtimg.cn/q={','.join(us_codes_tx.keys())}")
            for line in raw.strip().split('\n'):
                orig = line
                if '="' in orig:
                    line = orig.split('="', 1)[1]
                if '"' not in line:
                    continue
                # NOTE 正则必须匹配未剥离的原始行。老代码对已剥离行跑 v_(\w+)=
                # 必然匹配不到, 静默返回空 dict, 晨报 4 个指数全部显示暂无数据
                # 2026-10-21 修复
                m = re.search(r'v_(\w+)=', orig)
                if not m:
                    continue
                code = m.group(1)
                if code not in us_codes_tx:
                    continue
                parts = line.split('~')
                if len(parts) > 4 and parts[3] and parts[4]:
                    try:
                        price = float(parts[3])
                        prev = float(parts[4])
                        chg = (price / prev - 1) * 100 if prev else 0
                        result[us_codes_tx[code]] = {'price': price, 'prev': prev, 'chg': chg}
                    except Exception:
                        pass
            if result:
                print(f"  [WARN] 美股数据回退腾讯接口(数据可能不准, {len(result)} 个指数)")
            else:
                print(f"  [WARN] 腾讯美股接口解析为空(regex 未命中)")
        except Exception as e:
            print(f"  腾讯美股数据也获取失败: {e}")

    # 新浪全球指数兜底 (2026-10-21 新增)
    # Yahoo 403 + 东财 push2 IP 被封 + 腾讯 US parser 曾失效 -> 三重失效时救场
    # gb_$ndx / gb_$dji / gb_$inx 与腾讯 usNDX/usDJI/usINX 实测完全一致;
    # 日经用 b_NKY (gb_$n225 系列全部为空)。int_* 系列数据陈旧(纳指 22484 vs 实际 29490), 禁用。
    sina_codes = {
        'gb_$ndx': '纳斯达克100',
        'gb_$dji': '道琼斯',
        'gb_$inx': '标普500',
        'b_NKY': '日经225',
    }
    # 日经 b_NKY 字段错位一位: f[2]=绝对涨跌(621.34), f[3]=涨跌幅%(0.97)
    # gb_$* 系列 f[2] 直接就是涨跌幅%(-0.13)。两者不可混用。
    sina_chg_idx = {'gb_$ndx': 2, 'gb_$dji': 2, 'gb_$inx': 2, 'b_NKY': 3}
    need = {k: v for k, v in sina_codes.items() if v not in result}
    if need:
        ok_names = []
        try:
            raw_s = fetch(
                "https://hq.sinajs.cn/list=" + ','.join(need.keys()),
                headers={'User-Agent': 'Mozilla/5.0',
                         'Referer': 'https://finance.sina.com.cn'})
            for ln in raw_s.strip().split('\n'):
                m_s = re.search(r'hq_str_([^=]+?)\*?="', ln)
                if not m_s:
                    continue
                c = m_s.group(1)
                if c not in need:
                    continue
                body = ln.split('="', 1)[1].rstrip('";')
                f = body.split(',')
                # 新浪全球指数格式: 名称,价格,涨跌幅,...
                # gb_$ndx = 名称,29490.28,-0.13,2026-10-21 05:30:00,...
                # b_NKY   = 名称,64696.69,621.34,0.97,2:12 AM,...  <- 百分比在 f[3]
                ci = sina_chg_idx.get(c, 2)
                if len(f) <= ci or not f[1]:
                    continue
                try:
                    price = float(f[1])
                    chg = float(f[ci])
                    prev = price / (1 + chg / 100) if chg != -100 else price
                    result[need[c]] = {'price': price, 'prev': prev, 'chg': chg}
                    ok_names.append(need[c])
                except (ValueError, ZeroDivisionError):
                    continue
            if ok_names:
                print(f"  [OK] 新浪兜底补齐 {len(ok_names)} 个指数: {', '.join(ok_names)}")
        except Exception as e:
            print(f"  新浪兜底失败: {e}")

    # 日经225 - Yahoo Finance(东财已覆盖时跳过, 减少无谓请求)
    if '日经225' not in result:
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EN225?interval=1d&range=2d"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode('utf-8'))
            meta = data['chart']['result'][0]['meta']
            price = meta.get('regularMarketPrice', 0)
            prev = meta.get('chartPreviousClose', 0)
            if price and prev:
                chg = (price / prev - 1) * 100
                result['日经225'] = {'price': price, 'prev': prev, 'chg': chg}
        except Exception as e:
            print(f"  日经数据获取失败: {e}")

    return result


def _extract_shares(pos):
    """从 monitor_positions.yaml 的混乱字段中提取份额（2026-07-22 加兼容）

    字段优先级：
    1. shares（标准字段）
    2. batch_shares（513050 用的旧字段）
    3. add_position_1_shares（588080 用的字段，意为"已建仓"）
    4. multi_account 块里的"合计"行（159869 跨账户）
    5. 从 note 里正则匹配 "买入 NNNN 份/股"
    """
    # 1. 标准 shares
    shares = pos.get('shares', 0)
    if shares and shares > 0:
        return int(shares)

    # 2. batch_shares
    shares = pos.get('batch_shares', 0)
    if shares and shares > 0:
        return int(shares)

    # 3. add_position_1_shares（588080 等只有"加仓计划"的标的）
    shares = pos.get('add_position_1_shares', 0)
    if shares and shares > 0:
        return int(shares)

    # 4. multi_account 块（159869 跨账户）
    ma = pos.get('multi_account', '')
    if isinstance(ma, str):
        # 匹配"合计: ... 14000份"
        m = re.search(r'合计[：:]\s*([\d,]+)\s*份', ma)
        if m:
            return int(m.group(1).replace(',', ''))

    # 5. 从 note 里提取
    note = str(pos.get('note', ''))
    m = re.search(r'买入\s*([\d,]+)\s*[份股]', note)
    if m:
        return int(m.group(1).replace(',', ''))

    return 0


def check_portfolio_consistency():
    """台账单源自检（2026-07-24 简化）：只检查 monitor_positions.yaml 内部是否一致

    历史教训（2026-07-22）：原版双源对比 monitor_positions.yaml vs positions_active.yaml，
    双源永远对不齐（active 是僵尸文件），导致晨报每天报 3-5 条冗余警告。
    2026-07-24 废弃 positions_active.yaml 后，只检查 monitor 自身 + 持仓清单完整性。
    """
    warnings = []
    if not MONITOR_POSITIONS_FILE.exists():
        warnings.append(f"❌ 持仓台账文件不存在: {MONITOR_POSITIONS_FILE}")
        return warnings

    with open(MONITOR_POSITIONS_FILE) as f:
        mon_doc = yaml.safe_load(f) or {}

    mon_pos = mon_doc.get('positions', [])

    # 1. holding 状态的标的必须有可识别的份额
    for p in mon_pos:
        if p.get('status') == 'holding':
            code = str(p.get('code', '')).strip("'")
            shares = _extract_shares(p)
            if shares <= 0:
                warnings.append(f"⚠️ {code} {p.get('name')} 标记 holding 但份额为 0/无法提取")

    # 2. sold 标的：标准 shares 字段不应有 >0 值
    #    注：sold 标的的 note 通常含"卖出 600 份"等字样，会被 _extract_shares 误读
    #    所以这里只看标准 shares 字段（其他字段视为历史记录，无须警告）
    for p in mon_pos:
        if p.get('status') == 'sold':
            code = str(p.get('code', '')).strip("'")
            # 只查标准 shares 字段，其他不查（避免 note/sold_info 中的"卖出 N 股"误报）
            std_shares = p.get('shares', 0)
            if std_shares and std_shares > 0:
                warnings.append(f"⚠️ {code} {p.get('name')} 状态=sold 但 shares={std_shares}（建议归零或删除该字段）")

    return warnings


def get_portfolio_quotes():
    """从 monitor_positions.yaml 单源读取真实持仓，获取行情

    历史教训：
    - 2026-07-22：原版读 portfolio.yaml（6/23 后停更的僵尸文件），导致晨报持仓区显示
      4 只已清仓僵尸 + 漏掉 3 只真实持仓
    - 2026-07-24：废弃 positions_active.yaml 双源对比，统一单源读 monitor_positions.yaml，
      按 status=holding + shares>0 过滤
    """
    if not MONITOR_POSITIONS_FILE.exists():
        print(f"  ⚠️ 台账文件不存在: {MONITOR_POSITIONS_FILE}")
        return []

    with open(MONITOR_POSITIONS_FILE) as f:
        mon_doc = yaml.safe_load(f) or {}

    pos_map = {}
    for p in mon_doc.get('positions', []):
        code = str(p['code']).strip("'")
        if p.get('status') == 'holding':
            shares = _extract_shares(p)
            if shares > 0:
                pos_map[code] = {
                    'market': p.get('market', 'sh'),
                    'name': p.get('name', ''),
                    'shares': shares,
                }

    if not pos_map:
        print("  ⚠️ 没有找到任何 holding 状态的持仓")
        return []

    codes = []
    names = {}
    shares_map = {}
    for code, info in pos_map.items():
        full_code = f"{info['market']}{code}"
        codes.append(full_code)
        names[full_code] = info['name']
        shares_map[full_code] = info['shares']

    print(f"  ✅ 从 monitor_positions.yaml 单源读到 {len(codes)} 只持仓: {codes}")

    # 获取行情
    quotes = []
    try:
        raw = fetch(f"https://qt.gtimg.cn/q={','.join(codes)}")
        for line in raw.strip().split('\n'):
            m_code = re.search(r'v_(\w+)=', line)
            if not m_code:
                continue
            code_raw = m_code.group(1)
            parts = line.split('=')[1].strip('"').split('~')
            if len(parts) < 32:
                continue
            try:
                price = float(parts[3])
                prev = float(parts[4])
                chg = (price / prev - 1) * 100 if prev else 0
                # 开盘前腾讯会把日涨跌字段清零(price==prev, open==0) -> 显示 +0.00% 是假象,
                # 且会污染 calculate_verdict 的持仓均值。标记 pre_open 并排除出打分。
                pre_open = (float(parts[5] or 0) == 0)
                name = names.get(code_raw, parts[1])
                quotes.append({
                    'code': code_raw,
                    'name': name,
                    'price': price,
                    'prev': prev,
                    'chg': chg,
                    'pre_open': pre_open,
                    'shares': shares_map.get(code_raw, 0),
                })
            except:
                continue
    except Exception as e:
        print(f"  行情获取失败: {e}")

    # 按份额倒序排（大持仓在前）
    quotes.sort(key=lambda q: -q.get('shares', 0))
    return quotes
def get_macro_news():
    """获取宏观快讯"""
    try:
        import urllib.request
        url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_101_ajaxResult_50_1_.html"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://www.eastmoney.com'
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read().decode('utf-8')
        
        titles = re.findall(r'"title":"([^"]+)"', raw)[:8]
        return titles
    except Exception as e:
        print(f"  快讯获取失败: {e}")
        return []


def get_sina_quotes(codes, referer='https://finance.sina.com.cn'):
    """新浪 hq.sinajs.cn 批量取价。字段位置因品种而异，由调用方处理。

    2026-10-26 实测：
      b_NKY    -> f[1]=现价 f[2]=绝对涨跌 f[3]=涨跌幅% f[6]=日期 f[7]=时间
      hf_CHA50CFD -> f[0]=现价 f[6]=时间 f[7]=昨收 f[8]=开盘 f[12]=日期 f[13]=名称
      gb_$sox  -> f[1]=现价 f[2]=涨跌幅%
    """
    out = {}
    try:
        raw = fetch(
            'https://hq.sinajs.cn/list=' + ','.join(codes),
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': referer})
    except Exception as e:
        print(f"  ⚠️ 新浪批量取价失败: {e}")
        return out
    for ln in raw.strip().split('\n'):
        m = re.search(r'hq_str_([^=]+?)\*?="', ln)
        if not m:
            continue
        code = m.group(1)
        body = ln.split('="', 1)[1].rstrip('";')
        if not body:
            continue
        out[code] = body.split(',')
    return out


def get_sector_indices():
    """板块/区域指数（脚本缺口，2026-10-23 费半 -6.72% 被漏的教训）

    返回：费城半导体 SOX / 费半ETF SOXX / 罗素2000 IWM / 恒生 / 恒生科技
    腾讯与新浪双源，方向不一致时标记 conflict（不静默取一个）
    """
    result = {}
    # 腾讯侧
    tx = {'usSOXX': '费半ETF', 'usIWM': '罗素2000', 'hkHSI': '恒生指数', 'hkHSTECH': '恒生科技'}
    try:
        raw = fetch('https://qt.gtimg.cn/q=' + ','.join(tx.keys()))
        for line in raw.strip().split('\n'):
            m = re.search(r'v_(\w+)=', line)
            if not m:
                continue
            code = m.group(1)
            if code not in tx:
                continue
            parts = line.split('=')[1].strip('";').split('~')
            if len(parts) < 33:
                continue
            try:
                price = float(parts[3]); prev = float(parts[4])
            except (ValueError, IndexError):
                continue
            ts = parts[30] if len(parts) > 30 else ''
            result[tx[code]] = {'price': price, 'prev': prev,
                                'chg': (price / prev - 1) * 100 if prev else 0,
                                'ts': ts, 'src': '腾讯'}
    except Exception as e:
        print(f"  ⚠️ 腾讯板块指数失败: {e}")

    # 新浪侧补 SOX 本体（腾讯无对应代码）
    sina = get_sina_quotes(['gb_$sox'])
    f = sina.get('gb_$sox')
    if f and len(f) > 2:
        try:
            price = float(f[1]); chg = float(f[2])
            prev = price / (1 + chg / 100) if chg != -100 else price
            result['费城半导体SOX'] = {'price': price, 'prev': prev, 'chg': chg,
                                      'ts': f[3] if len(f) > 3 else '', 'src': '新浪'}
        except (ValueError, IndexError):
            pass

    # 交叉校验：SOX 与 SOXX 方向应一致
    sox = result.get('费城半导体SOX'); soxx = result.get('费半ETF')
    if sox and soxx and (sox['chg'] > 0) != (soxx['chg'] > 0):
        print(f"  ⚠️ 费半数据冲突: SOX {sox['chg']:+.2f}% vs SOXX {soxx['chg']:+.2f}%")
        result['_conflict'] = '费半 SOX/SOXX 方向不一致'
    return result


def get_a50():
    """富时中国A50期货（腾讯 A50 代码全部 none_match，只能走新浪）

    2026-10-26 实测：hf_CHA50CFD f[0]=现价 f[7]=昨收 f[6]=时间 f[12]=日期
    """
    sina = get_sina_quotes(['hf_CHA50CFD'])
    f = sina.get('hf_CHA50CFD')
    if not f or len(f) < 9:
        return None
    try:
        price = float(f[0]); prev = float(f[7])
    except (ValueError, IndexError):
        return None
    if not prev:
        return None
    return {'price': price, 'prev': prev, 'chg': (price / prev - 1) * 100,
            'ts': f[6] if len(f) > 6 else '', 'date': f[12] if len(f) > 12 else ''}


def get_china_adr():
    """中概 ADR（比港股收盘晚 4 小时，更贴 A 股开盘）

    2026-10-26 实测：阿里 -2.14% / 京东 -1.25% / 百度 -1.00%
    → 513050 的隔夜方向直接由这项决定
    """
    codes = {'usBABA': '阿里巴巴', 'usJD': '京东', 'usBIDU': '百度',
             'usPDD': '拼多多', 'usTCEHY': '腾讯ADR', 'usNTES': '网易'}
    out = {}
    try:
        raw = fetch('https://qt.gtimg.cn/q=' + ','.join(codes.keys()))
    except Exception as e:
        print(f"  ⚠️ 中概ADR失败: {e}")
        return out
    for line in raw.strip().split('\n'):
        m = re.search(r'v_(\w+)=', line)
        if not m or m.group(1) not in codes:
            continue
        parts = line.split('=')[1].strip('";').split('~')
        if len(parts) < 33:
            continue
        try:
            price = float(parts[3]); prev = float(parts[4])
        except (ValueError, IndexError):
            continue
        out[codes[m.group(1)]] = {'price': price, 'prev': prev,
                                  'chg': (price / prev - 1) * 100 if prev else 0,
                                  'ts': parts[30] if len(parts) > 30 else ''}
    return out


def get_turnover():
    """两市成交额（东财 push2his kline，上证+深证相加）

    2026-10-26 实测：上证 8986.7 亿 + 深证 10576.2 亿 = 1.96 万亿
    """
    total = 0.0
    detail = {}
    for secid, name in [('1.000001', '上证'), ('0.399001', '深证')]:
        u = ('https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=' + secid +
             '&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57'
             '&klt=101&fqt=0&end=20500101&lmt=3')
        try:
            raw = fetch(u, headers={'User-Agent': 'Mozilla/5.0',
                                    'Referer': 'https://quote.eastmoney.com/'},
                        enc='utf-8')
            d = json.loads(raw)
            klines = (d.get('data') or {}).get('klines') or []
            if not klines:
                continue
            last = klines[-1].split(',')
            amt = float(last[6]) / 1e8  # 元 -> 亿
            detail[name] = {'date': last[0], 'amount_yi': amt}
            total += amt
        except Exception as e:
            print(f"  ⚠️ {name}成交额失败: {e}")
    return {'total_yi': total, 'detail': detail}


def get_margin_balance():
    """融资余额（东财 RPTA_RZRQ_LSHJ，注意报表名带 A）

    2026-10-26 实测：10/23 余额 24026.6 亿，单日 -242.78 亿，5 日累计 -507 亿
    → 放量反弹当天杠杆资金撤退 = 反弹由存量腾挪驱动（独立于行情的质量判据）
    """
    u = ('https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPTA_RZRQ_LSHJ'
         '&columns=ALL&sortColumns=DIM_DATE&sortTypes=-1&pageSize=6&pageNumber=1'
         '&source=WEB&client=WEB')
    try:
        raw = fetch(u, headers={'User-Agent': 'Mozilla/5.0',
                                'Referer': 'https://data.eastmoney.com/'},
                    enc='utf-8')
        d = json.loads(raw)
        rows = ((d.get('result') or {}).get('data')) or []
        if not rows:
            return None
        series = []
        for r in rows:
            rzye = r.get('RZYE')
            if not rzye:
                continue
            series.append({'date': str(r.get('DIM_DATE', ''))[:10],
                           'balance_yi': rzye / 1e8})
        if not series:
            return None
        latest = series[0]
        prev = series[1] if len(series) > 1 else None
        chg = (latest['balance_yi'] - prev['balance_yi']) if prev else 0.0
        cum5 = (latest['balance_yi'] - series[5]['balance_yi']) if len(series) >= 6 else 0.0
        return {'latest': latest, 'prev': prev, 'chg_yi': chg,
                'cum5_yi': cum5, 'series': series}
    except Exception as e:
        print(f"  ⚠️ 融资余额失败: {e}")
        return None


def get_a_index_snapshot():
    """A股指数快照（含上证50 vs 创业板指的风格分化对比）"""
    idx = [('sh000001', '上证指数'), ('sh000300', '沪深300'), ('sh000016', '上证50'),
           ('sz399001', '深成指'), ('sz399006', '创业板指'), ('sh000688', '科创50'),
           ('sh000905', '中证500')]
    out = {}
    try:
        raw = fetch('https://qt.gtimg.cn/q=' + ','.join(c for c, _ in idx))
    except Exception as e:
        print(f"  ⚠️ A股指数失败: {e}")
        return out
    for line in raw.strip().split('\n'):
        m = re.search(r'v_(\w+)=', line)
        if not m:
            continue
        parts = line.split('=')[1].strip('";').split('~')
        if len(parts) < 33:
            continue
        try:
            price = float(parts[3]); prev = float(parts[4])
        except (ValueError, IndexError):
            continue
        out[m.group(1)] = {'price': price, 'prev': prev,
                           'chg': (price / prev - 1) * 100 if prev else 0,
                           'ts': parts[30] if len(parts) > 30 else ''}
    return out


def get_limit_structure(date_compact):
    """涨停/连板结构（判断主线是否成型）

    2026-10-26 实测：82 涨停但 70 家首板 → 主线未成型
    """
    u = ('https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989'
         '&dpt=wz.ztzt&Pageindex=0&pagesize=400&sort=fbt%3Aasc&date=' + date_compact +
         '&fields=c,n,p,zdp,lbc,hybk,zbc')
    try:
        raw = fetch(u, headers={'User-Agent': 'Mozilla/5.0',
                                'Referer': 'https://quote.eastmoney.com/'},
                    enc='utf-8')
        d = json.loads(raw)
        pool = (d.get('data') or {}).get('pool') or []
    except Exception as e:
        print(f"  ⚠️ 涨停池失败: {e}")
        return None
    if not pool:
        return None
    from collections import Counter
    lbc = Counter(int(it.get('lbc') or 1) for it in pool)
    ind = Counter(it.get('hybk') for it in pool if it.get('hybk'))
    return {'total': len(pool), 'lbc_dist': dict(lbc),
            'first_board': lbc.get(1, 0),
            'industries': ind.most_common(6),
            'high_board': [(it.get('c'), it.get('n'), it.get('lbc'))
                           for it in pool if int(it.get('lbc') or 1) >= 3]}


def calculate_verdict(indices, quotes, sector=None, a50=None, adr=None,
                      turnover=None, margin=None):
    """综合打分判断（2026-10-26 扩展：补入脚本原先漏掉的 6 个变量）"""
    score = 0
    notes = []
    
    # 外盘：纳指/道指
    for name in ['纳斯达克100', '道琼斯']:
        if name in indices:
            chg = indices[name]['chg']
            if chg >= 0.5:
                score += 1
            elif chg <= -0.5:
                score -= 1
    
    # 日经
    if '日经225' in indices:
        chg = indices['日经225']['chg']
        if chg >= 0.5:
            score += 1
        elif chg <= -0.5:
            score -= 1
    
    # 持仓标的（排除开盘前快照：腾讯此时日涨跌恒为 0，会把均值拉向中性）
    traded = [q for q in quotes if not q.get('pre_open')]
    if traded:
        avg_chg = sum(q['chg'] for q in traded) / len(traded)
        if avg_chg >= 1:
            score += 1
        elif avg_chg <= -1:
            score -= 1

    # ===== 以下为 2026-10-26 新增：脚本原先完全没覆盖的变量 =====
    # 教训：2026-10-23 费半 -6.72% 被漏；2026-10-26 A50/融资余额/ADR/成交额全漏

    # 1) 费城半导体（芯片板块系统性重定价的探针，权重 ≥ 三大指数）
    sox_chg = None
    if sector:
        sox = sector.get('费城半导体SOX') or sector.get('费半ETF')
        if sox:
            sox_chg = sox['chg']
            if sox_chg >= 0.5:
                score += 1
                notes.append(f'费半 {sox_chg:+.2f}% (+1)')
            elif sox_chg <= -0.5:
                score -= 1
                notes.append(f'费半 {sox_chg:+.2f}% (-1)')

    # 2) A50 期货（A股开盘最直接的外围压力）
    if a50:
        if a50['chg'] >= 0.3:
            score += 1
            notes.append(f"A50 {a50['chg']:+.2f}% (+1)")
        elif a50['chg'] <= -0.3:
            score -= 1
            notes.append(f"A50 {a50['chg']:+.2f}% (-1)")

    # 3) 中概 ADR（比港股收盘晚 4 小时，更贴 A 股开盘；直接决定 513050）
    if adr:
        vals = [v['chg'] for v in adr.values()]
        if vals:
            avg = sum(vals) / len(vals)
            if avg <= -1.0:
                score -= 1
                notes.append(f"中概ADR均值 {avg:+.2f}% (-1)")
            elif avg >= 1.0:
                score += 1
                notes.append(f"中概ADR均值 {avg:+.2f}% (+1)")

    # 4) 两市成交额（>1.2万亿 +1；<8000亿 -1）
    if turnover and turnover.get('total_yi'):
        total = turnover['total_yi']
        if total >= 12000:
            score += 1
            notes.append(f"成交额 {total/10000:.2f}万亿 (+1)")
        elif total < 8000:
            score -= 1
            notes.append(f"成交额 {total/10000:.2f}万亿 (-1)")

    # 5) 融资余额（杠杆资金撤退 = 领先风险信号；单日 <-200亿 额外 -1）
    if margin:
        chg = margin.get('chg_yi', 0)
        if chg <= -200:
            score -= 1
            notes.append(f"融资余额 {chg:+.0f}亿 (-1)")
        elif chg >= 200:
            score += 1
            notes.append(f"融资余额 {chg:+.0f}亿 (+1)")

    if score >= 2:
        verdict = '🟢 强势'
    elif score <= -2:
        verdict = '🔴 弱势'
    elif score <= -1:
        verdict = '🟡 中性偏弱'
    elif score == 1:
        verdict = '🟡 中性偏强'
    else:
        verdict = '🟡 中性'
    return verdict, score, notes


def generate_report():
    """生成晨报"""
    today = datetime.now().strftime('%Y-%m-%d')

    print("\n" + "=" * 60)
    print(f"🌅 早盘市场扫描 {today}")
    print("=" * 60)

    # 0. 台账一致性检查（2026-07-22 加入）
    print("\n🔍 台账一致性检查...")
    consistency_warnings = check_portfolio_consistency()
    for w in consistency_warnings:
        print(f"  {w}")
    if not consistency_warnings:
        print("  ✅ monitor_positions.yaml 单源内部一致性 OK")

    # 1. 外盘数据
    print("\n📊 获取外盘数据...")
    indices = get_global_indices()

    # 1b. 板块/区域指数 + A50 + 中概ADR（2026-10-26 新增，脚本原缺口）
    print("\n🔬 获取板块指数/A50/中概ADR...")
    sector = get_sector_indices()
    a50 = get_a50()
    adr = get_china_adr()

    # 1c. 两市成交额 + 融资余额（新增）
    print("\n💰 获取成交额/融资余额...")
    turnover = get_turnover()
    margin = get_margin_balance()

    # 1d. A股指数快照 + 涨停结构（新增）
    print("\n📊 获取A股指数/涨停结构...")
    a_index = get_a_index_snapshot()
    ymd = (datetime.now() - __import__('datetime').timedelta(days=1))
    limit_struct = get_limit_structure(ymd.strftime('%Y%m%d'))

    # 2. 持仓行情
    print("\n💼 获取持仓行情...")
    quotes = get_portfolio_quotes()

    # 3. 宏观快讯
    print("\n📰 获取宏观快讯...")
    news = get_macro_news()

    # 4. 综合判断
    verdict, score, score_notes = calculate_verdict(
        indices, quotes, sector=sector, a50=a50, adr=adr,
        turnover=turnover, margin=margin)

    # 5. 组装报告
    lines = []
    lines.append(f"🌅 早盘风向 · {today}")
    lines.append("")
    lines.append(f"## 综合判断：{verdict}")
    lines.append(f"### 置信度：{'高' if abs(score) >= 2 else '中'}")
    if score_notes:
        lines.append(f"> 打分明细：{' | '.join(score_notes)}")
    lines.append("")

    # 一致性警告（如有）
    if consistency_warnings:
        lines.append("---")
        lines.append("")
        lines.append("## ⚠️ 台账一致性警告")
        for w in consistency_warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 一、外盘（隔夜）")

    for name in ['纳斯达克100', '道琼斯', '标普500', '日经225']:
        if name in indices:
            d = indices[name]
            chg_str = f"{d['chg']:+.2f}%"
            lines.append(f"- {name}: {d['price']:.2f} {chg_str}")
        else:
            lines.append(f"- {name}: 暂无数据")

    # 板块指数（脚本 2026-10-23 缺口）
    if sector:
        lines.append("")
        lines.append("**板块/区域指数（脚本原缺口）**")
        for key in ['费城半导体SOX', '费半ETF', '罗素2000', '恒生指数', '恒生科技']:
            if key in sector:
                d = sector[key]
                ts = str(d.get('ts', ''))[-8:]
                lines.append(f"- {key}: {d['price']:.2f} {d['chg']:+.2f}% ({d.get('src','?')} {ts})")

    if a50:
        lines.append(f"- 富时A50期货: {a50['price']:.2f} {a50['chg']:+.2f}% (新浪 {a50.get('ts','')} 实时)")

    if adr:
        lines.append("")
        lines.append("**中概ADR（比港股收盘晚4小时，更贴A股开盘）**")
        for k, v in adr.items():
            lines.append(f"- {k}: {v['price']:.2f} {v['chg']:+.2f}%")

    # 成交额 + 融资余额
    if turnover and turnover.get('total_yi'):
        lines.append("")
        parts = " + ".join(f"{n} {v['amount_yi']:.0f}亿" for n, v in turnover['detail'].items())
        lines.append(f"**两市成交额**：{parts} = **{turnover['total_yi']/10000:.2f}万亿**")
    if margin:
        lines.append(f"**融资余额**：{margin['latest']['balance_yi']:.0f}亿 "
                     f"(单日 {margin['chg_yi']:+.0f}亿, 5日累计 {margin['cum5_yi']:+.0f}亿)")

    lines.append("")
    lines.append("## 二、昨日A股")
    if a_index:
        for code, label in [('sh000001', '上证指数'), ('sh000016', '上证50'),
                            ('sz399006', '创业板指'), ('sh000688', '科创50')]:
            if code in a_index:
                d = a_index[code]
                lines.append(f"- {label}: {d['price']:.2f} {d['chg']:+.2f}%")
        if 'sh000016' in a_index and 'sz399006' in a_index:
            gap = a_index['sz399006']['chg'] - a_index['sh000016']['chg']
            style = "成长/科技领涨" if gap > 0 else "价值/权重领涨"
            lines.append(f"- 风格分化: 创业板 {a_index['sz399006']['chg']:+.2f}% vs 上证50 "
                         f"{a_index['sh000016']['chg']:+.2f}% (差 {gap:+.2f}%) → {style}")
    if limit_struct:
        lines.append(f"- 涨停 {limit_struct['total']} 家 (首板 {limit_struct['first_board']} 家) "
                     f"→ {'主线未成型' if limit_struct['first_board'] > limit_struct['total']*0.7 else '有连板主线'}")
        if limit_struct['industries']:
            ind = "、".join(f"{n}{c}" for n, c in limit_struct['industries'])
            lines.append(f"- 涨停行业分布: {ind}")
        if limit_struct['high_board']:
            hb = "、".join(f"{n}({b}板)" for _, n, b in limit_struct['high_board'])
            lines.append(f"- 连板梯队: {hb}")

    lines.append("")
    lines.append("## 三、宏观快讯")
    if news:
        for i, title in enumerate(news[:5], 1):
            lines.append(f"{i}. {title}")
    else:
        lines.append("暂无快讯")

    lines.append("")
    all_pre = quotes and all(q.get('pre_open') for q in quotes)
    if all_pre:
        lines.append("## 四、持仓标的（开盘前快照，涨跌幅未生成）")
    else:
        lines.append("## 四、持仓标的（昨结算参考）")
    if quotes:
        for q in quotes:
            chg_str = f"{q['chg']:+.2f}%" if not q.get('pre_open') else "（待开盘）"
            shares_str = f" ({q['shares']:,}份)" if q.get('shares', 0) > 0 else ""
            lines.append(f"- {q['name']}: {q['price']:.3f} {chg_str}{shares_str}")
    else:
        lines.append("暂无持仓")
    
    lines.append("")
    lines.append("---")
    lines.append(f"综合打分: {score} → {verdict}")
    
    # 操作建议
    if '弱势' in verdict:
        lines.append("操作建议: 观望为主，不建仓")
    elif '强势' in verdict:
        lines.append("操作建议: 可考虑逢低布局")
    else:
        lines.append("操作建议: 观望，等待方向明确")
    
    report = "\n".join(lines)
    
    # 6. 保存报告
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{today}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n✅ 报告已保存: {output_file}")
    
    # 7. 飞书推送
    print("\n📤 推送飞书...")
    result = send_feishu(report)
    if result and result.get('code') == 0:
        print("✅ 飞书推送成功")
    else:
        print(f"⚠️ 飞书推送失败: {result}")
    
    return report


if __name__ == '__main__':
    generate_report()