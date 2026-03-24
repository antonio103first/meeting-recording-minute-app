"""UPGRADE_PLAN_v3.md GitHub 배포"""
import base64, json, urllib.request, urllib.error

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    h = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json",
         "Content-Type": "application/json", "User-Agent": "deploy_plan.py"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

import os
BASE = os.path.dirname(os.path.abspath(__file__))

files = {
    "UPGRADE_PLAN_v3.md": "docs: v3.0 업그레이드 개발 기획서 추가",
    "MANUAL.md": "docs: MANUAL.md 최종본 배포",
    "PLAN.md": "docs: PLAN.md Phase 6 완료 업데이트",
    "HISTORY.md": "docs: HISTORY.md 최종본 배포",
}

for fname, msg in files.items():
    fpath = os.path.join(BASE, fname)
    if not os.path.exists(fpath):
        print(f"  SKIP(없음) - {fname}")
        continue
    with open(fpath, "rb") as f:
        enc = base64.b64encode(f.read()).decode("ascii")
    d, s = gh_api(f"/contents/{fname}")
    sha = d.get("sha") if s == 200 else None
    payload = {"message": msg, "content": enc}
    if sha: payload["sha"] = sha
    _, s = gh_api(f"/contents/{fname}", method="PUT", data=payload)
    print(f"  {'OK' if s in (200,201) else f'FAIL {s}'} - {fname}")

print(f"\nGitHub: https://github.com/{REPO}")
input("아무 키나 누르면 종료됩니다...")
