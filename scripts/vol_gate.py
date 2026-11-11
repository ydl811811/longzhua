#!/usr/bin/env python3
"""候选股建仓信号的量能确认闸门（2026-11-06 晨读新增，单一实现，两脚本共用）

背景（真实缺陷，非假想）：
  台账 monitor_watched.yaml 的 159299 段写着
    「需站稳 0.64（MA20+清仓价）且**放量 2 日**才算右侧确认，届时再评估建仓」
  但 stock_monitor.py / auction_monitor.py 的 reversal 判定只看
    「现价 ≥ entry_max」+「五档比 ≥ ratio_min」—— 没有任何量能条件。
  → 11/05 起持续误推「✅ 请确认建仓」建仓信号，而当晚晚报结论是「候选池 0 建仓」。
  → 根因 = 台账与脚本是同一逻辑的两份拷贝，脚本那份漏了量能条件。

口径（与晚报 2026-11-05 报的数值逐项对齐，已实测）：
  量比 = 当日成交量 ÷ **前 5 个已完成交易日**平均成交量（不含当日）
  实测 159516 11/05 量比 1.98（晚报同值）| 159299 11/05 量比 0.90（晚报同值）
  连续 N 日 = 最近 N 个**已完成**交易日全部达标（当日盘中量不完整，不参与判定）。
  该口径下 159299 11/04=1.26 达标、11/05=0.90 不达标 → 判定「未连续放量」
  = 与晚报「右侧确认需连续 2 日放量，暂停建仓」结论一致。

数据源：腾讯 web.ifzq.gtimg.cn 日K（HTTP，不封 IP，与 astock-common 同源）。
"""

import json
import urllib.request

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{n},qfq"


def _kline(code, n=20):
    """返回 [(date, volume), ...]，取自腾讯日K。失败返回 []。"""
    url = _KLINE_URL.format(code=code, n=n)
    req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                                "Referer": "https://gu.qq.com/"})
    try:
        raw = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", errors="ignore")
        node = json.loads(raw).get("data", {}).get(code, {})
        rows = node.get("qfqday") or node.get("day") or []
    except Exception:
        return []
    out = []
    for r in rows:
        try:
            out.append((str(r[0]), float(r[5])))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def vol_ratios(code, market="sz", today=None):
    """已完成交易日的量比序列 [(date, ratio), ...]（当日不完整量已剔除）。"""
    prefix = "sh" if market == "sh" else "sz"
    rows = _kline(f"{prefix}{code}")
    if not rows:
        return []
    if today is None:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
    # 剔除当日（盘中量不完整）—— 只用已完成交易日
    done = [(d, v) for d, v in rows if d < today]
    if len(done) < 6:
        return []
    out = []
    for i in range(5, len(done)):
        base = sum(v for _, v in done[i - 5:i]) / 5.0
        if base <= 0:
            continue
        out.append((done[i][0], round(done[i][1] / base, 2)))
    return out


def check(code, market, spec):
    """量能闸门判定。

    spec: {'ratio_min': float, 'days': int}（可选）
    返回 (ok: bool, detail: str)
      ok=False → 不满足建仓量能条件，不得推建仓信号
    spec 为空/缺失 → (True, '') = 不设闸门（保持旧行为）
    """
    if not isinstance(spec, dict):
        return True, ""
    try:
        ratio_min = float(spec.get("ratio_min", 1.0))
        days = int(spec.get("days", 1))
    except (TypeError, ValueError):
        return True, ""
    if days <= 0:
        return True, ""

    ratios = vol_ratios(code, market)
    if not ratios:
        # 取数失败 → 保守起见不放行建仓信号（宁可漏推，不可误推）
        return False, "量比数据获取失败"

    recent = ratios[-days:]
    if len(recent) < days:
        return False, f"量比样本不足({len(recent)}/{days})"

    detail = "/".join(f"{r:.2f}" for _, r in recent)
    ok = all(r >= ratio_min for _, r in recent)
    if ok:
        return True, f"连续{days}日放量 {detail} ≥ {ratio_min}"
    return False, f"量能未确认(连续{days}日量比 {detail}，需 ≥{ratio_min})"
