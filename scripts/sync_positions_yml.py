#!/usr/bin/env python3
"""
sync_positions_yml.py — 龙爪侧持仓 YAML → NAS stock_shared/ 镜像
龙爪 cron */5 跑（hermes 本机 K46CM）
灵爪侧所有脚本只读 /home/YDL/.openclaw/workspace/stock_shared/*.yaml

用法:
  python3 sync_positions_yml.py            # 一次同步
  python3 sync_positions_yml.py --dry-run  # 只显示 diff 不真同步

对应整合方案 D1-2（v0.2_draft.md 第 4 行）
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 龙爪侧台账源（cron 单一事实源，铁律 P0）
SRC_DIR = Path.home() / '.hermes' / 'stock-portfolio'

# 同步到 NAS 的 YAML（2026-07-24 取消 positions_active.yaml 双源推送）
SYNC_FILES = [
    'candidates_watch.yaml',
    'decision_log.yaml',
    'monitor_positions.yaml',
    'monitor_watched.yaml',
]  # 2026-07-24 废弃 positions_active.yaml — 详见 ~/.hermes/stock-portfolio/decision_log.yaml

# NAS 镜像目标
NAS_DIR = '/home/YDL/.openclaw/workspace/stock_shared'
NAS_HOST = 'YDL@192.168.31.10'
SSH_KEY = str(Path.home() / '.ssh' / 'id_ed25519_new')

# 同步日志
LOG_DIR = Path.home() / '.hermes' / 'stock-portfolio' / 'loop_engineer' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'sync_positions.log'


def log(msg: str) -> None:
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def sync_one(src: Path, dry_run: bool = False) -> bool:
    """scp 单文件到 NAS,返回 True=成功"""
    if not src.exists():
        log(f'  ⚠️ 源文件不存在: {src}')
        return False
    dst = f'{NAS_HOST}:{NAS_DIR}/{src.name}'
    if dry_run:
        log(f'  [DRY] {src.name}: {src.stat().st_size} bytes')
        return True
    r = subprocess.run(
        ['scp', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no', str(src), dst],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode == 0:
        log(f'  ✅ {src.name}: {src.stat().st_size} bytes → NAS')
        return True
    log(f'  ❌ {src.name}: {r.stderr.strip()[:200]}')
    return False


def main() -> int:
    dry_run = '--dry-run' in sys.argv
    log(f'=== 同步开始 (dry_run={dry_run}) ===')
    ok_count = 0
    for name in SYNC_FILES:
        src = SRC_DIR / name
        if sync_one(src, dry_run=dry_run):
            ok_count += 1
    log(f'=== 同步完成 {ok_count}/{len(SYNC_FILES)} ===')
    return 0 if ok_count == len(SYNC_FILES) else 1


if __name__ == '__main__':
    sys.exit(main())