#!/usr/bin/env python3
# Lingzhua -> GitHub backup

import os, sys, subprocess, tempfile, shutil, base64, datetime, re
import requests

# Config
NH = "192.168.31.10"
NU = "YDL"
NK = os.path.expanduser("~/.ssh/id_ed25519_new")

# Token from git-credentials
with open(os.path.expanduser("~/.git-credentials")) as f:
    c = f.read().strip()
# Extract token between : and @
m = re.search(r":(ghp_[^@]+)@", c)
TK = m.group(1) if m else c
OW = "ydl811811"
RP = "openclaw-lingzhua"
API = "https://api.github.com/repos/" + OW + "/" + RP
HDR = {"Authorization": "token " + TK, "Accept": "application/vnd.github.v3+json", "User-Agent": "lingzhua-backup/1.0"}
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
SESSION = requests.Session()
SESSION.verify = False


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


# Step 2: Push to GitHub
ents = []
for r, d, fs in os.walk(WD):
    for fn in fs:
        fp = os.path.join(r, fn)
        rl = os.path.relpath(fp, WD)
        with open(fp, "rb") as f:
            b = base64.b64encode(f.read()).decode()
        rq = SESSION.post(API + "/git/blobs", headers=HDR,
                           json={"content": b, "encoding": "base64"}, timeout=30)
        if rq.status_code == 201:
            sh = rq.json()["sha"]
            mo = "100755" if os.access(fp, os.X_OK) else "100644"
            ents.append({"path": rl, "mode": mo, "type": "blob", "sha": sh})
        else:
            print("  ERROR blob " + rl + ": " + str(rq.status_code))

if not ents:
    print("[WARN] No files")
    shutil.rmtree(WD)
    sys.exit(0)

# Get current state
latest = None
cb = "main"
for br in ["main", "master"]:
    rq = SESSION.get(API + "/git/refs/heads/" + br, headers=HDR, timeout=30)
    if rq.status_code == 200:
        latest = rq.json()["object"]["sha"]
        cb = br; break

bt = None
if latest:
    rq = SESSION.get(API + "/git/commits/" + latest, headers=HDR, timeout=30)
    if rq.status_code == 200:
        bt = rq.json()["tree"]["sha"]

rq = SESSION.post(API + "/git/trees", headers=HDR,
                  json={"base_tree": bt or "", "tree": ents}, timeout=30)
if rq.status_code != 201:
    print("[ERROR] Tree: " + str(rq.status_code))
    shutil.rmtree(WD); sys.exit(1)
nt = rq.json()["sha"]

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
cd = {"message": "Auto backup lingzhua - " + now, "tree": nt}
if latest: cd["parents"] = [latest]
rq = SESSION.post(API + "/git/commits", headers=HDR, json=cd, timeout=30)
if rq.status_code != 201:
    print("[ERROR] Commit: " + str(rq.status_code))
    shutil.rmtree(WD); sys.exit(1)
nc = rq.json()["sha"]

if latest:
    rq = SESSION.patch(API + "/git/refs/heads/" + cb, headers=HDR,
                       json={"sha": nc, "force": False}, timeout=30)
else:
    rq = SESSION.post(API + "/git/refs", headers=HDR,
                      json={"ref": "refs/heads/" + cb, "sha": nc}, timeout=30)

if rq.status_code in (200, 201):
    print("[OK] Pushed to GitHub (" + cb + ")")
else:
    print("[ERROR] Push: " + str(rq.status_code))

shutil.rmtree(WD)
print("[OK] Backup at " + now)
