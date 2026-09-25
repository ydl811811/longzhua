#!/usr/bin/python3.12
import os
os.chdir('/home/yu/.hermes/scripts')

import urllib.request

code = 'sh600850'
url = f'https://qt.gtimg.cn/q={code}'
with urllib.request.urlopen(url, timeout=10) as r:
    raw = r.read().decode('gbk')
parts = raw.strip().split('~')

name = parts[1]
prev_close = float(parts[4])
open_ = float(parts[5])
price = float(parts[3])
high = float(parts[33])
low = float(parts[34])
chg_pct = float(parts[32])

buy1 = float(parts[9])
sell1 = float(parts[19])
buy_v1 = int(parts[10])
sell_v1 = int(parts[20])
buy_v5 = sum(int(parts[i]) for i in [10,12,14,16,18])
sell_v5 = sum(int(parts[i]) for i in [20,22,24,26,28])
ratio_5 = buy_v5/sell_v5 if sell_v5 > 0 else 0

vol = int(parts[36])/100

# 关键判断
jump_pct = (open_ - prev_close) / prev_close * 100

print(f"【{name} {code[2:]} 集合竞价】")
print(f"时间: 9:25竞价结束")
print(f"昨收: {prev_close:.2f}  开盘: {open_}  现价: {price}  涨跌: {chg_pct:+.2f}%")
print(f"跳空: {jump_pct:+.1f}%")
print(f"五档比: {ratio_5:.2f}  (买{buy_v5} vs 卖{sell_v5})")
print(f"卖1@{sell1}压{sell_v1}手  买1@{buy1}撑{buy_v1}手")

# 决策
signal = "观察"
action = ""

if open_ > 0 and jump_pct >= 5:
    signal = "⚠️ 高开5%以上！注意是否一字板"
    action = "高开过多不追，等回踩确认"
elif open_ > 0 and jump_pct >= 2:
    signal = "✅ 高开2~5%，积极信号"
    action = "若开盘后快速封板，可轻仓试300股"
elif open_ > 0 and jump_pct >= 0:
    signal = "普通高开，观察持续性"
    action = "等盘中回踩21.10支撑确认"
elif open_ < prev_close:
    signal = "⚠️ 低开，观望"
    action = "等价格企稳21.00再考虑"

print(f"\n信号: {signal}")
print(f"建议: {action}")
print(f"\n止损参考: 20.46 (昨收)")
print(f"目标: 23.00~24.00")
