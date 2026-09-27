#!/usr/bin/env python3
"""Fixed backup_to_github via GitHub Contents API."""
import base64
import datetime
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
OWNER_REPO = "ydl811811/longzhua"
BRANCH = "master"
CREDS_FILE = pathlib.Path.home() / ".git-credentials"
HOME = pathlib.Path.home()
MEM_DIR = HOME / ".hermes" / "memories"
SCR_DIR = HOME / ".hermes" / "scripts"

SOUL_FILES = [
    "SOUL.md", "MEMORY.md", "USER.md",
    "00-essence.md", "01-laoda-identity.md",
    "02-network.md", "03-finance.md", "04-dragon-host.md",
]


def get_token():
    if not CREDS_FILE.exists():
        sys.exit("[ERROR] no ~/.git-credentials")
    for line in CREDS_FILE.read_text().splitlines():
        if "github.com" not in line:
            continue
        m = re.match(r"https://[^:]*:([^@]*)@", line)
        if m:
            return m.group(1)
    sys.exit("[ERROR] token not parseable")


def _build_ssl_context():
    import ssl
    # Workaround: uv-bundled Python 3.11.15 uses OpenSSL 3.5 which produces a
    # ClientHello that GitHub rejects with EOF during TLS 1.3 handshake.
    # Force max protocol to TLS 1.2 — verified working.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    # Load system + env-specified CA bundles explicitly. Setting SSL_CERT_FILE
    # alone is not enough when a custom context is built.
    ctx.load_default_certs()
    return ctx

_SSL_CTX = _build_ssl_context()

import time

def http(method, url, token, body=None, max_retries=4):
    """HTTP call with retry on transient errors (400/5xx) and short socket timeout."""
    data = None
    headers = {
        "Authorization": "token " + token,
        "User-Agent": "hermes-backup",
        "Accept": "application/vnd.github+json",
    }
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    last_code = None
    last_body = b""
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            last_code, last_body = e.code, e.read()
            # 401/404/422/422 are caller errors — don't retry, surface immediately
            if last_code in (401, 403, 404, 422):
                return last_code, last_body
            # 400/5xx/transient: retry with backoff
            time.sleep(0.8 * (2 ** attempt))
        except Exception:
            # network/SSL errors — retry
            time.sleep(0.8 * (2 ** attempt))
    return last_code if last_code is not None else 0, last_body


def get_existing_sha(token, path):
    quoted = urllib.parse.quote(path, safe="")
    url = API + "/repos/" + OWNER_REPO + "/contents/" + quoted + "?ref=" + BRANCH
    code, body = http("GET", url, token)
    if code == 200:
        return json.loads(body).get("sha")
    return None


def put_file(token, path, content_bytes, message):
    existing = get_existing_sha(token, path)
    payload = {
        "message": message,
        "branch": BRANCH,
        "content": base64.b64encode(content_bytes).decode(),
    }
    if existing:
        payload["sha"] = existing
    url = API + "/repos/" + OWNER_REPO + "/contents/" + urllib.parse.quote(path, safe="")
    code, body = http("PUT", url, token, payload)
    if code not in (200, 201):
        raise RuntimeError(str(code) + ": " + repr(body[:300]))
    return json.loads(body).get("commit", {}).get("sha")


def collect_soul():
    out = []
    for name in SOUL_FILES:
        p = MEM_DIR / name
        if p.is_file():
            out.append(("soul/" + name, p))
    det = MEM_DIR / "details"
    if det.is_dir():
        for f in sorted(det.rglob("*")):
            if f.is_file():
                rel = f.relative_to(MEM_DIR)
                out.append(("soul/" + rel.as_posix(), f))
    return out


def collect_scripts():
    out = []
    skip_pat = re.compile(r"(\.bak($|\.)|\.lock$|\.duofluo_alert_state$|__pycache__)")
    for f in sorted(list(SCR_DIR.glob("*.sh")) + list(SCR_DIR.glob("*.py"))):
        if not f.is_file():
            continue
        if skip_pat.search(f.name):
            continue
        out.append(("scripts/" + f.name, f))
    return out


def main():
    token = get_token()
    print("token length:", len(token))

    soul = collect_soul()
    scripts = collect_scripts()
    print("local:", len(soul), "soul file(s),", len(scripts), "script(s)")

    msg = "Auto backup - " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    pushed = 0
    skipped = 0
    failures = []

    for remote_path, local in soul + scripts:
        content = local.read_bytes()
        try:
            commit_sha = put_file(token, remote_path, content, msg)
            pushed += 1
            print("  +", remote_path, "->", commit_sha[:8])
        except RuntimeError as e:
            err = str(e)
            if "is identical" in err or "no_op" in err:
                skipped += 1
                print("  =", remote_path, "unchanged")
            else:
                failures.append((remote_path, err))
                print("  !", remote_path, "FAIL:", err)
        # small throttle to avoid GitHub anti-abuse throttling
        time.sleep(0.4)

    print("\nDone. pushed=", pushed, "skipped=", skipped, "failed=", len(failures))
    if failures:
        for path, err in failures:
            print("  FAIL", path + ":", err[:120])
        sys.exit(1)
    print("[OK] Backup completed at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()
