#!/bin/bash
# source_health.sh — 数据源健康度快照（cron 09:00 / 15:35 跑）
# 推到 NAS stock_shared/source_health.json（hermes terminal 不能直接写 NAS，改 SSH 内执行）

NAS_DIR="/home/YDL/.openclaw/workspace/stock_shared"

ssh -i /home/yu/.ssh/id_ed25519_new -o BatchMode=yes -o StrictHostKeyChecking=no YDL@192.168.31.10 \
  "python3 - <<'PY'
import sys, json
from datetime import datetime
sys.path.insert(0, '/home/YDL/loop_engineer')
from quote_provider import health as qp_health
out = {
    'ts': datetime.now().isoformat(timespec='seconds'),
    'sources': qp_health(),
}
with open('$NAS_DIR/source_health.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('source_health.json written')
PY"
