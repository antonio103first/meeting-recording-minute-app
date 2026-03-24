"""
GitHub API를 사용해 누락된 문서 파일을 직접 업로드하는 스크립트
실행: python push_docs.py
"""
import base64
import json
import os
import urllib.request
import urllib.error

TOKEN = "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"
REPO  = "antonio103first/meeting-recording-minute-app"
BASE  = os.path.dirname(os.path.abspath(__file__))

FILES = ["MANUAL.md", "PLAN.md", "HISTORY.md"]

def api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "push_docs.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

for fname in FILES:
    fpath = os.path.join(BASE, fname)
    if not os.path.exists(fpath):
        print(f"SKIP (not found): {fname}")
        continue

    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    # 현재 파일 SHA 확인 (업데이트 시 필요)
    existing, status = api(f"/contents/{fname}")
    sha = existing.get("sha") if status == 200 else None

    payload = {
        "message": f"docs: {fname} 추가/동기화",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    _, status = api(f"/contents/{fname}", method="PUT", data=payload)
    if status in (200, 201):
        action = "업데이트" if sha else "신규 생성"
        print(f"OK ({action}): {fname}")
    else:
        print(f"FAIL (HTTP {status}): {fname}")

print("완료")
