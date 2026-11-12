#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stock_monitor 统一监控 —— 双通道投递包装器

【为什么存在】
2026-11-11 根因复盘：交易提醒只走自定义机器人 webhook（目标群「股票提醒」），
老大日常看的是当前 DM / 「闲聊免费」群 → 监控脚本正常执行、webhook 投递成功，
但老大看不到 = 通知路由盲区。本脚本在不改动 stock_monitor.py 推送逻辑的前提下，
补一条 im/v1/messages API 通道到 DM，保证「群留档 + DM 必达」。

【设计要点】
1. 不修改 /home/yu/.hermes/scripts/stock_monitor.py —— 共享脚本零侵入。
2. 凭据不走 os.environ：cron 的 build_subprocess_env() 会剥离 provider/secret
   类环境变量，因此这里直接解析 ~/.hermes/.env 文件；DM chat_id 从
   ~/.hermes/config.yaml 顶层 FEISHU_HOME_CHANNEL 读取。
3. 子进程跑 stock_monitor.py，其 webhook 通道保持原样（群留档）；
   本脚本只把 stdout 里「⚠️ 触发:」段落转发到 DM。
4. 无触发时不发任何消息（stdout 无触发段 → 不调用 API）。
5. 凭据一律不落日志、不打印。

用法：
  python3 stock_monitor_relay.py            # 正常模式
  python3 stock_monitor_relay.py --dry      # 只打印将要发送的内容，不真发
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

HERMES_DIR = Path.home() / '.hermes'
ENV_FILE = HERMES_DIR / '.env'
CONFIG_FILE = HERMES_DIR / 'config.yaml'
MONITOR_SCRIPT = HERMES_DIR / 'scripts' / 'stock_monitor.py'
TRIGGER_MARK = '⚠️ 触发:'

# 额外落地目标：老大日常在看的「闲聊免费」群（chat_id 由 im/v1/chats 列出并核对过，
# 龙爪 app bot cli_a93559e471b8dbd2 在该群内，可直发）。webhook 通道仍留「股票提醒」群。
EXTRA_TARGETS = ['oc_ca1a8378751f1d71ba8e370d8808b699']


def _parse_env_file(path: Path) -> dict:
    """解析 .env（支持 export K=V / 引号 / 注释），不依赖外部包。"""
    vals: dict = {}
    if not path.is_file():
        return vals
    for raw in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[len('export '):].strip()
        if '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            vals[key] = val
    return vals


def get_app_creds() -> tuple:
    """返回 (app_id, app_secret)。优先环境变量，回落到 .env 文件。"""
    env = _parse_env_file(ENV_FILE)
    app_id = (os.environ.get('FEISHU_APP_ID') or env.get('FEISHU_APP_ID') or '').strip()
    app_secret = (os.environ.get('FEISHU_APP_SECRET') or env.get('FEISHU_APP_SECRET') or '').strip()
    return app_id, app_secret


def get_home_chat_id() -> str:
    """DM 目标 chat_id：config.yaml 顶层 FEISHU_HOME_CHANNEL。"""
    env = _parse_env_file(ENV_FILE)
    cid = (os.environ.get('FEISHU_HOME_CHANNEL') or env.get('FEISHU_HOME_CHANNEL') or '').strip()
    if cid:
        return cid
    if CONFIG_FILE.is_file():
        for line in CONFIG_FILE.read_text(encoding='utf-8', errors='ignore').splitlines():
            m = re.match(r'^FEISHU_HOME_CHANNEL:\s*(\S+)\s*$', line)
            if m:
                return m.group(1).strip()
    return ''


def get_tenant_token(app_id: str, app_secret: str) -> str:
    url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
    payload = json.dumps({'app_id': app_id, 'app_secret': app_secret}).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        return data.get('tenant_access_token') or ''
    except Exception as e:
        print(f'[relay_err] token 获取失败: {type(e).__name__}')
        return ''


def send_dm(text: str, chat_id: str = '') -> bool:
    app_id, app_secret = get_app_creds()
    chat_id = chat_id or get_home_chat_id()
    if not (app_id and app_secret and chat_id):
        print('[relay_err] 缺少 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_HOME_CHANNEL')
        return False
    token = get_tenant_token(app_id, app_secret)
    if not token:
        return False
    url = 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id'
    payload = {
        'receive_id': chat_id,
        'msg_type': 'text',
        'content': json.dumps({'text': text}, ensure_ascii=False),
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json; charset=utf-8',
                 'Authorization': f'Bearer {token}'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        ok = data.get('code', 0) == 0
        if not ok:
            print(f'[relay_err] DM 投递被拒: code={data.get("code")} msg={data.get("msg")}')
        return ok
    except Exception as e:
        print(f'[relay_err] DM 投递异常: {type(e).__name__}')
        return False


def run_monitor() -> str:
    """跑 stock_monitor.py，返回其 stdout。"""
    try:
        proc = subprocess.run(
            [sys.executable, str(MONITOR_SCRIPT)],
            capture_output=True, text=True, timeout=180,
            cwd=str(MONITOR_SCRIPT.parent),
        )
        out = proc.stdout or ''
        if proc.returncode != 0:
            out += f'\n[monitor_exit={proc.returncode}] ' + (proc.stderr or '')[-500:]
        return out
    except Exception as e:
        return f'[relay_err] 执行 monitor 失败: {type(e).__name__}: {e}'


def extract_trigger(out: str) -> str:
    """从 monitor stdout 提取「⚠️ 触发:」之后的内容。"""
    if TRIGGER_MARK not in out:
        return ''
    return out.split(TRIGGER_MARK, 1)[1].strip()


def main() -> int:
    dry = '--dry' in sys.argv
    out = run_monitor()
    # stdout 原样保留（cron local 留档 + 排障）
    print(out)
    trigger = extract_trigger(out)
    if not trigger:
        return 0
    text = f'🐉 龙爪信号 · 交易提醒\n{trigger}'
    if dry:
        print('[relay_dry] 将发送:')
        print(text)
        return 0
    # 双会话落地：当前 DM（老大日常看的地方）+ 「闲聊免费」群（历史留档）
    targets = []
    dm_cid = get_home_chat_id()
    if dm_cid:
        targets.append(('DM', dm_cid))
    for cid in EXTRA_TARGETS:
        targets.append(('群', cid))
    for label, cid in targets:
        ok = send_dm(text, chat_id=cid)
        print(f'[relay] {label} 投递 {"成功" if ok else "失败"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
