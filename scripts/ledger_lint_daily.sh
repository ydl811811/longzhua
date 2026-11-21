#!/bin/bash
# 每日台账规范 lint（schema v1 + 受控词表）—— 08:40 触发
# 退出码语义：ERROR 才失败；历史存量 WARN 属已知数据缺口，只提示不阻断（不套 --strict）
cd /home/yu/.hermes/scripts || exit 1
echo "=== 台账规范 lint $(date '+%F %T') ==="
python3 ledger_lint.py
rc=$?
echo "lint exit=$rc（0 = 无 ERROR；存量 WARN 为历史数据缺口，需人工补数据，不自动阻断）"
exit $rc
