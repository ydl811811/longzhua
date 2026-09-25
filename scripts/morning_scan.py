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
def fetch(url, headers=None, timeout=10):
    """强制 IPv4 连接，避免 IPv6 卡死"""
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
        return raw.decode('gbk', errors='replace')
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
                if '="':
                    line = line.split('="', 1)[1]
                if '"' not in line:
                    continue
                m = re.search(r'v_(\w+)=', line)
                if not m:
                    continue
                code = m.group(1)
                if code not in us_codes_tx:
                    continue
                parts = line.split('=')[1].strip('"').split('~')
                if len(parts) > 4 and parts[3] and parts[4]:
                    try:
                        price = float(parts[3])
                        prev = float(parts[4])
                        chg = (price / prev - 1) * 100 if prev else 0
                        result[us_codes_tx[code]] = {'price': price, 'prev': prev, 'chg': chg}
                    except:
                        pass
            print(f"  ⚠️ 美股数据回退腾讯接口（数据可能不准）")
        except Exception as e:
            print(f"  腾讯美股数据也获取失败: {e}")

    # 日经225 - Yahoo Finance
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
                name = names.get(code_raw, parts[1])
                quotes.append({
                    'code': code_raw,
                    'name': name,
                    'price': price,
                    'prev': prev,
                    'chg': chg,
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


def calculate_verdict(indices, quotes):
    """综合打分判断"""
    score = 0
    
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
    
    # 持仓标的
    if quotes:
        avg_chg = sum(q['chg'] for q in quotes) / len(quotes)
        if avg_chg >= 1:
            score += 1
        elif avg_chg <= -1:
            score -= 1
    
    if score >= 2:
        return '🟢 强势', score
    elif score <= -1:
        return '🔴 弱势', score
    else:
        return '🟡 中性', score


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

    # 2. 持仓行情
    print("\n💼 获取持仓行情...")
    quotes = get_portfolio_quotes()

    # 3. 宏观快讯
    print("\n📰 获取宏观快讯...")
    news = get_macro_news()

    # 4. 综合判断
    verdict, score = calculate_verdict(indices, quotes)

    # 5. 组装报告
    lines = []
    lines.append(f"🌅 早盘风向 · {today}")
    lines.append("")
    lines.append(f"## 综合判断：{verdict}")
    lines.append(f"### 置信度：{'高' if abs(score) >= 2 else '中'}")
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

    lines.append("")
    lines.append("## 二、宏观快讯")
    if news:
        for i, title in enumerate(news[:5], 1):
            lines.append(f"{i}. {title}")
    else:
        lines.append("暂无快讯")

    lines.append("")
    lines.append("## 三、持仓标的（昨结算参考）")
    if quotes:
        for q in quotes:
            chg_str = f"{q['chg']:+.2f}%"
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