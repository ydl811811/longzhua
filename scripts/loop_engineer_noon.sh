#!/bin/bash
# Loop Engineer 盘中流水线（感知+决策）
# 每30分钟工作日 9:00-14:30 触发
#
# 龙爪 2026-10-23 改造：PUSH_CHANNEL=file
#   盘中 alerts 不再推飞书群机器人，改写 JSON 到
#   ~/.hermes/cron/output/loop_engineer_alert_latest.json
#   再由 scripts/loop_engineer_alert_relay.py 投递到老大本会话
#   （原来推群，老大在 DM 收不到）
#
# 盘后汇总 (--eod) 仍走原 webhook 群机器人，不受影响
export LONGZHUA_PUSH_CHANNEL=file
/usr/bin/python3.12 /home/yu/.hermes/stock-portfolio/loop_engineer/daily_pipeline.py --noon 2>&1
