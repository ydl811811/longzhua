"""飞书自定义机器人凭据加载器（单一事实源）。

设计要点
--------
1. **源码零明文**：URL 与签名 secret 只存在于 ``~/.hermes/.env``（权限 0600），
   任何脚本都不再硬编码。审计口径：对 ``~/.hermes/scripts`` 做 webhook 路径
   字符串扫描，应无真实凭据命中。
2. **不依赖 os.environ**：cron 通过 ``build_subprocess_env()`` 启动子进程时会
   剥离 provider/secret 类环境变量（``.env`` 的键不会进入 ``os.environ``），
   所以只写 ``os.getenv()`` 会在 cron 下拿到空值 → 推送静默失效。
   本模块直接解析 ``~/.hermes/.env`` 文件，cron 与手动运行行为一致。
3. **优先级**：显式环境变量 > ``~/.hermes/.env`` 文件 > 抛错。
   手动 ``FEISHU_BOT_URL=xxx python3 xxx.py`` 可临时覆盖，便于测试。
4. 缺失凭据时抛 ``RuntimeError``（不静默降级），避免"以为在推送其实没推"。

用法
----
    from feishu_bot import FEISHU_BOT_URL, FEISHU_BOT_SECRET
    # 或
    from feishu_bot import load_feishu_creds
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(os.path.expanduser("~")) / ".hermes" / ".env"

KEY_URL = "FEISHU_BOT_URL"
KEY_SECRET = "FEISHU_BOT_SECRET"


def _parse_env_file(path: Path) -> dict[str, str]:
    """解析 ``.env``（支持 ``export K=V`` / 引号 / 注释），不依赖外部包。"""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            result[key] = val
    return result


def load_feishu_creds(env_file: Path | None = None) -> tuple[str, str]:
    """返回 ``(bot_url, bot_secret)``。

    优先级：``os.environ`` > ``~/.hermes/.env`` 文件。
    缺失任一项即抛 ``RuntimeError``——绝不返回空串，避免推送静默失败。
    """
    file_vals = _parse_env_file(env_file or ENV_FILE)
    url = (os.environ.get(KEY_URL) or file_vals.get(KEY_URL) or "").strip()
    secret = (os.environ.get(KEY_SECRET) or file_vals.get(KEY_SECRET) or "").strip()
    missing = [
        name
        for name, val in ((KEY_URL, url), (KEY_SECRET, secret))
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"飞书机器人凭据缺失: {', '.join(missing)}。"
            f"请在 {env_file or ENV_FILE} 中配置（该文件权限应为 0600），"
            f"或以同名环境变量提供。"
        )
    return url, secret


FEISHU_BOT_URL, FEISHU_BOT_SECRET = load_feishu_creds()


__all__ = [
    "FEISHU_BOT_URL",
    "FEISHU_BOT_SECRET",
    "KEY_URL",
    "KEY_SECRET",
    "ENV_FILE",
    "load_feishu_creds",
]
