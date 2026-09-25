#!/usr/bin/python3.12
"""Push mainline weekly report to Feishu home channel."""
import urllib.request, json, time, hmac, hashlib, base64, sys

FEISHU_BOT_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fbfd7f01-878c-4ece-80e6-5e7324ab3692"
FEISHU_SECRET  = "9vXyEvLigZ70Ynw1YeUtI"
REPORT_PATH = "/home/yu/.hermes/reports/mainline_weekly_20260717.md"

with open(REPORT_PATH) as f:
    report = f.read()

summary = (
    "【主线识别周报 2026-07-17】\n\n"
    "指数端：沪指5日累跌5% / 创业板-10% / 科创50单日-7.12% / 200股跌停，极端市。\n\n"
    "逆势3强：\n"
    "1. 电力/公用事业：7/17唯一主力净流入+6.42亿，8股涨停，长江电力单股7亿\n"
    "2. 银行：+0.90%排第二，42股飘红，中报预喜最高+700%\n"
    "3. 石油石化：+0.40%，油气ETF逆势\n\n"
    "最弱：半导体-PCB-通信（7/17电子-4.25%/通信-3.61%）/ AI算力/影视分化\n\n"
    "主线判定：无三条件全满足板块\n"
    "- 准主线：电力/公用事业（条件1+2满足，条件3触达不足）\n"
    "- 准主线：医药生物（龙头哈药7/17剧震-15%收-4.05%见顶，下周考验）\n"
    "- 候选：银行/游戏/旅游\n\n"
    "持仓5只位置：\n"
    "- 159869 游戏ETF：候选（7/17跟调，网格执行）\n"
    "- 588080 科创50：防御（连日重挫，加仓位1.85未触发）\n"
    "- 513050 中概互联：候选\n"
    "- 513120 港股创新药：准主线（龙头考验中）\n"
    "- 159928 消费：防御（按规则周-2%内可加仓2664元）\n\n"
    "候选6只位置：\n"
    "- 159299 金融科技：候选弱\n"
    "- 159865 养殖ETF：准主线（数据接口异常待验证）\n"
    "- 159516 半导体设备：候选反向\n"
    "- 512480 半导体：候选反向\n"
    "- 562510 旅游：候选（距触发-1.3%重点关注）\n"
    "- 513580 恒生科技：候选（破触发线+1.2%）\n\n"
    "弹药建议（现金21,924=21%）：\n"
    "主线未明维持21%现金，仅消费防御仓可小加2664元（跌-2%内）；\n"
    "下周一验证港股创新药龙头是否止跌；\n"
    "不加任何进攻仓（用户纪律：总盈亏-10.1% > -5%）。\n\n"
    "一句话：当前主线未明；准主线电力+医药；维持21%现金，仅消费ETF按规则小加。\n\n"
    "详见：~/.hermes/reports/mainline_weekly_20260717.md"
)

timestamp = str(int(time.time()))
string_to_sign = timestamp + '\n' + FEISHU_SECRET
sign = base64.b64encode(
    hmac.new(string_to_sign.encode(), digestmod=hashlib.sha256).digest()
).decode()

payload = {
    "msg_type": "text",
    "content": {"text": summary},
    "timestamp": timestamp,
    "sign": sign,
}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    FEISHU_BOT_URL, data=data, headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        result = json.loads(r.read())
        print(f"Code: {result.get('StatusCode')}, Msg: {result.get('msg')}")
        print(f"Full: {result}")
except Exception as e:
    print(f"feishu push failed: {e}")
    sys.exit(1)
