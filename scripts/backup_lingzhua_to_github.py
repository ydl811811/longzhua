#!/usr/bin/env python3
# Lingzhua -> GitHub backup
#
# 2026-10-02 fixes:
#   1. Force TLS 1.2 max (workaround: uv-bundled Python 3.11.15 + OpenSSL 3.5
#      produces a TLS 1.3 ClientHello that GitHub rejects with EOF).
#   2. Throttle /git/blobs POSTs to ~1 req/sec — GitHub rate-limits this
#      endpoint strictly; exceeding it triggers a 20-second cool-down.
#   3. Retry transient errors (400/429/5xx) with exponential backoff.

import os, sys, subprocess, tempfile, shutil, base64, datetime, re, ssl, time
import urllib.request, urllib.error, json as jsonlib

# Config
NH = "192.168.31.10"
NU = "YDL"
NK = os.path.expanduser("~/.ssh/id_ed25519_new")

# Token from git-credentials
with open(os.path.expanduser("~/.git-credentials")) as f:
    c = f.read().strip()
m = re.search(r":(ghp_[^@]+)@", c)
TK = m.group(1) if m else c
OW = "ydl811811"
RP = "openclaw-lingzhua"
API = "https://api.github.com/repos/" + OW + "/" + RP

# TLS 1.2-max context (uv-py3.11 + OpenSSL 3.5 + GitHub EOF workaround)
_SSL_CTX = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_SSL_CTX.check_hostname = True
_SSL_CTX.verify_mode = ssl.CERT_REQUIRED
_SSL_CTX.maximum_version = ssl.TLSVersion.TLSv1_2
_SSL_CTX.load_default_certs()


def http(method, url, body=None, max_retries=5):
    headers = {
        "Authorization": "token " + TK,
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "lingzhua-backup/1.0",
    }
    data = None
    if body is not None:
        data = jsonlib.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    last_code, last_body = 0, b""
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            last_code, last_body = e.code, e.read()
            if last_code in (401, 403, 404, 422):
                return last_code, last_body
            time.sleep(0.5 * (2 ** attempt))
        except Exception:
            time.sleep(0.5 * (2 ** attempt))
    return last_code, last_body


def ssh_run(c):
    r = subprocess.run(["ssh", "-i", NK, "-o", "StrictHostKeyChecking=no",
                      "-o", "ConnectTimeout=10", f"{NU}@{NH}", c],
                     capture_output=True, timeout=30)
    return r.stdout, r.returncode


# Step 1: Pull from NAS
WD = tempfile.mkdtemp(prefix="lingzhua_")
os.makedirs(WD + "/soul", exist_ok=True)
os.makedirs(WD + "/skills", exist_ok=True)

for sf in ["SOUL.md", "MEMORY.md", "USER.md", "AGENTS.md"]:
    o, rc = ssh_run("cat /home/YDL/.openclaw/workspace/" + sf)
    if rc == 0 and o:
        open(WD + "/soul/" + sf, "wb").write(o)
        print("  OK: soul/" + sf + " (" + str(len(o)) + " bytes)")
    else:
        print("  WARN: soul/" + sf + " empty")

o, rc = ssh_run("tar cf - --exclude=__pycache__ -C /home/YDL/.openclaw/workspace scripts/")
if rc == 0 and o:
    subprocess.run(["tar", "xf", "-", "-C", WD], input=o, capture_output=True)
    print("  OK: scripts/ extracted")

o, rc = ssh_run("tar cf - --exclude=__pycache__ --exclude=.git -C /home/YDL/.openclaw/workspace/skills lingzhua-short-term/")
if rc == 0 and o:
    subprocess.run(["tar", "xf", "-", "-C", WD + "/skills"], input=o, capture_output=True)
    print("  OK: lingzhua-short-term extracted")


# Step 2: Push to GitHub — throttle /git/blobs to ~1 req/sec
ents = []
files = []
for r, d, fs in os.walk(WD):
    for fn in fs:
        files.append(os.path.join(r, fn))
files.sort()
print("  uploading " + str(len(files)) + " blobs...")

for i, fp in enumerate(files, 1):
    rl = os.path.relpath(fp, WD)
    with open(fp, "rb") as f:
        data = f.read()
    b = base64.b64encode(data).decode()
    t = time.time()
    code, body = http("POST", API + "/git/blobs",
                      {"content": b, "encoding": "base64"})
    dt = time.time() - t
    if code == 201:
        sh = jsonlib.loads(body)["sha"]
        mo = "100755" if os.access(fp, os.X_OK) else "100644"
        ents.append({"path": rl, "mode": mo, "type": "blob", "sha": sh})
        print("    [" + str(i) + "/" + str(len(files)) + "] " + rl + " ok " + "%.2fs" % dt)
    else:
        print("    [" + str(i) + "/" + str(len(files)) + "] " + rl + " ERROR " + str(code) + " " + body[:120].decode("utf-8", "replace"))
    # Adaptive throttle: GitHub /git/blobs tolerates ~1 req/sec normally but
    # triggers a ~20-second secondary rate-limit cool-down after bursts. If a
    # POST takes >5s, treat it as a cool-down signal and wait the full window.
    if dt >= 5.0:
        wait = max(20.0, dt + 2.0)
        print("    rate-limited; sleeping " + str(int(wait)) + "s before next blob", flush=True)
        time.sleep(wait)
    elif dt < 1.0:
        time.sleep(1.0 - dt)


if not ents:
    print("[WARN] No files")
    shutil.rmtree(WD)
    sys.exit(0)

# Get current state
latest = None
cb = "main"
for br in ["main", "master"]:
    code, body = http("GET", API + "/git/refs/heads/" + br)
    if code == 200:
        latest = jsonlib.loads(body)["object"]["sha"]
        cb = br
        break

bt = None
if latest:
    code, body = http("GET", API + "/git/commits/" + latest)
    if code == 200:
        bt = jsonlib.loads(body)["tree"]["sha"]

code, body = http("POST", API + "/git/trees",
                  {"base_tree": bt or "", "tree": ents})
if code != 201:
    print("[ERROR] Tree: " + str(code) + " " + body[:200].decode("utf-8", "replace"))
    shutil.rmtree(WD)
    sys.exit(1)
nt = jsonlib.loads(body)["sha"]

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
cd = {"message": "Auto backup lingzhua - " + now, "tree": nt}
if latest:
    cd["parents"] = [latest]
code, body = http("POST", API + "/git/commits", cd)
if code != 201:
    print("[ERROR] Commit: " + str(code) + " " + body[:200].decode("utf-8", "replace"))
    shutil.rmtree(WD)
    sys.exit(1)
nc = jsonlib.loads(body)["sha"]

if latest:
    code, body = http("PATCH", API + "/git/refs/heads/" + cb,
                      {"sha": nc, "force": False})
else:
    code, body = http("POST", API + "/git/refs",
                      {"ref": "refs/heads/" + cb, "sha": nc})

if code in (200, 201):
    print("[OK] Pushed to GitHub (" + cb + ")")
else:
    print("[ERROR] Push: " + str(code) + " " + body[:200].decode("utf-8", "replace"))

shutil.rmtree(WD)
print("[OK] Backup at " + now)
