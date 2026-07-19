#!/bin/bash
# Loop Engineer 盘后流水线（持仓快照+复盘+影子对比+git备份）
# 每天 15:15 工作日触发（先于 15:30 的全量备份）
/usr/bin/python3.12 /home/yu/.hermes/stock-portfolio/loop_engineer/daily_pipeline.py --eod 2>&1
