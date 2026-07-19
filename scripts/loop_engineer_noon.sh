#!/bin/bash
# Loop Engineer 盘中流水线（感知+决策）
# 每30分钟工作日 9:00-14:30 触发
/usr/bin/python3.12 /home/yu/.hermes/stock-portfolio/loop_engineer/daily_pipeline.py --noon 2>&1
