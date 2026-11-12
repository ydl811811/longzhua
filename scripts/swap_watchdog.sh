#!/usr/bin/env bash
# 141 swap/memory watchdog — 防止 swap 被吃满再次触发整机 OOM。
# 规则：swap 使用率 > 80% 或 available 内存 < 500MB 时告警，否则静默（空输出 = 不打扰）。
set -uo pipefail

TOTAL_SWAP_KB=$(awk '/SwapTotal/{print $2}' /proc/meminfo)
USED_SWAP_KB=$(awk '/^SwapTotal/{t=$2} /^SwapFree/{f=$2} END{print t-f}' /proc/meminfo)
AVAIL_MB=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)

if [ "${TOTAL_SWAP_KB:-0}" -eq 0 ]; then
  exit 0
fi

PCT=$(( USED_SWAP_KB * 100 / TOTAL_SWAP_KB ))
if [ "$PCT" -ge 80 ] || [ "${AVAIL_MB:-0}" -lt 500 ]; then
  echo "[141 内存告警] swap 已用 ${PCT}% (${USED_SWAP_KB}/${TOTAL_SWAP_KB} KiB)，MemAvailable=${AVAIL_MB}MB。"
  echo "动作建议：检查是否有长跑 execute_code / 大文件 git add / checkpoint 扫描；必要时重启 hermes-gateway 释放内存。"
fi
exit 0
