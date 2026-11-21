#!/usr/bin/env python3
"""test_repeat_notify.py —— 取消「当日重复触发静默」回归测试

2026-11-18 老大指令：只要条件成立就推送预警，不再当日静默。
本测试 **不发任何真实消息**：monkeypatch send_feishu / fetch_stock。
跑法：python3 ~/.hermes/scripts/test_repeat_notify.py
"""
import sys, os, json, tempfile
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock_monitor as sm

TODAY = datetime.now().strftime('%Y-%m-%d')
TS    = datetime.now().strftime('%Y%m%d%H%M%S')
SENT  = []

def _fake_send(msg, emoji='🐉'):
    SENT.append((emoji, msg))

def _mk(price, prev, high, low, ratio):
    return {'price': price, 'prev': prev, 'open': price, 'high': high, 'low': low,
            'chg_pct': (price/prev-1)*100 if prev else 0.0, 'volume': 1000,
            'ratio': ratio, 'buy_vols': [1]*5, 'sell_vols': [1]*5, 'quote_ts': TS}

def run_watched(cfg, data, state):
    """跑一次候选监控：返回 (是否发消息, 新state)"""
    sm.send_feishu = _fake_send
    sm.fetch_stock = lambda code, market='sz': dict(data)
    before = len(SENT)
    r = sm.check_watched(cfg['code'], cfg['name'], 'sz', cfg, state)
    msg = r[0] if isinstance(r, tuple) else r
    new_state = r[1] if isinstance(r, tuple) else state
    return len(SENT) > before, msg, new_state

def run_position(cfg, data, state):
    sm.send_feishu = _fake_send
    sm.fetch_stock = lambda code, market='sz': dict(data)
    before = len(SENT)
    r = sm.check_position(cfg['code'], cfg['name'], 'sz', cfg, state)
    msg = r[0] if isinstance(r, tuple) else r
    new_state = r[1] if isinstance(r, tuple) else state
    return len(SENT) > before, msg, new_state

FAILS = []
def check(name, cond, detail=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('  | ' + str(detail)) if detail and not cond else ''))
    if not cond: FAILS.append(name)

WATCH = {'code': '999001', 'name': '测试候选', 'entry_max': 1.0, 'ratio_min': 1.2,
         'stop_loss': 0.90, 'signal_type': 'pullback', 'status': 'waiting_reversal'}
QUAL  = _mk(0.99, 1.05, 1.05, 0.98, 1.5)    # 下穿成立 + 五档比达标
NOQ   = _mk(1.02, 1.05, 1.05, 1.01, 1.5)    # 未下穿（当日最低在触发位上方）
RATIO = _mk(0.99, 1.05, 1.05, 0.98, 0.9)    # 下穿成立但五档比不足
BROKE = _mk(0.89, 1.05, 1.05, 0.88, 1.5)    # 已破止损
BACKUP = _mk(1.02, 1.05, 1.05, 0.98, 1.5)   # 当日最低曾下穿 1.00，但现价已回到触发位上方（追高）

print('=== A. 候选股 pullback ===')
st = {'date': TODAY, 'triggered': {}}
f1, m1, st = run_watched(WATCH, QUAL, st);  check('A1 首次合格扫描 → 发', f1, m1)
f2, m2, st = run_watched(WATCH, QUAL, st);  check('A2 同日第二次合格扫描 → 再发', f2, m2)
f3, m3, st = run_watched(WATCH, NOQ,  st);  check('A3 不合格扫描 → 不发', not f3, m3)
f4, m4, st = run_watched(WATCH, QUAL, st);  check('A4 不合格后再合格 → 再发', f4, m4)
f5, m5, st = run_watched(WATCH, QUAL, {'date': '2020-01-01', 'triggered': {'999001': ['pullback']}})
check('A5 跨日合格扫描 → 发', f5, m5)
f6, _, _ = run_watched(WATCH, RATIO, st);   check('A6 五档比不足 → 阻断', not f6)
f7, _, _ = run_watched(WATCH, BROKE, st);   check('A7 已破止损 → 阻断', not f7)
# reversal 上穿要求: prev < trigger 且 up_price >= trigger；此处 prev=1.05 >= trigger → 非今日上穿
f8, m8, _ = run_watched(dict(WATCH, signal_type='reversal'), _mk(1.02,1.05,1.05,1.01,1.5), st)
check('A8 reversal 未上穿 → 阻断', not f8, m8)
# 反向: prev<trigger 且现价上穿 → 必须发
f9, m9, _ = run_watched(dict(WATCH, signal_type='reversal'), _mk(1.05,0.95,1.05,0.99,1.5), st)
check('A9 reversal 今日上穿 → 发', f9, m9)
# 2026-11-19 接货价闸门：当日最低曾下穿 ≠ 可建仓；现价必须仍在触发位之下
f10, m10, _ = run_watched(WATCH, BACKUP, st)
check('A10 当日最低曾下穿但现价在触发位上方 → 阻断(不追高)', (not f10) and '非有效接货位' in str(m10), m10)

print('=== B. 持仓（tier 各自独立） ===')
POS = {'code': '999002', 'name': '测试持仓', 'status': 'holding', 'shares': 1000, 'cost': 1.0,
       'stop_loss': 1.0, 'take_profit': [{'level': 1, 'target': 1.10, 'shares': 500, 'status': 'pending'}]}
stp = {'date': TODAY, 'triggered': {}}
p1, pm1, stp = run_position(POS, _mk(0.99, 1.05, 1.05, 0.98, 1.5), stp)
check('B1 止损首次 → 发', p1, pm1)
p2, pm2, stp = run_position(POS, _mk(0.99, 1.05, 1.05, 0.98, 1.5), stp)
check('B2 止损同日第二次 → 再发', p2, pm2)
stp2 = {'date': TODAY, 'triggered': {}}
tp1, tpm1, stp2 = run_position(POS, _mk(1.12, 1.05, 1.12, 1.11, 1.5), stp2)
tp2, tpm2, stp2 = run_position(POS, _mk(1.12, 1.05, 1.12, 1.11, 1.5), stp2)
check('B3 TP tier 同日两次 → 都发', tp1 and tp2, (tpm1, tpm2))

print('=== C. state 文件形状兼容（auto_stock_alert.py 共用） ===')
check('C1 state 顶层键仍是 date/triggered', set(stp.keys()) <= {'date', 'triggered'}, list(stp.keys()))
check('C2 triggered 结构仍是 {code: [tier]}', isinstance(stp.get('triggered'), dict), stp.get('triggered'))
check('C3 tier 仍按日留痕', 'stop_loss' in (stp.get('triggered', {}).get('999002') or []), stp.get('triggered'))
with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as tf:
    json.dump(stp, tf); tmp = tf.name
check('C4 state 可 JSON 序列化', os.path.getsize(tmp) > 0)
os.unlink(tmp)

print('=== D. 正式候选池未被改动 ===')
import yaml
W = yaml.safe_load(open(os.path.expanduser('~/.hermes/stock-portfolio/monitor_watched.yaml'), encoding='utf-8'))
wl = W.get('watched') or []
codes = [str(x.get('code')) for x in wl]
check('D1 候选池 18 只', len(wl) == 18, len(wl))
check('D2 159996 在池', codes.count('159996') == 1)
check('D3 510880 在池', codes.count('510880') == 1)
check('D4 001358 在池且唯一', codes.count('001358') == 1)
check('D5 候选身份无重复', len(codes) == len(set(codes)))

print()
print(f'总计 {len(FAILS)} 失败' if FAILS else 'ALL PASS')
sys.exit(1 if FAILS else 0)
