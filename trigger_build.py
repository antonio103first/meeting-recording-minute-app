"""
make_icon.py + build.yml 을 GitHub에 업로드하여 빌드를 트리거합니다.
실행: python trigger_build.py
"""
import os, base64, json, urllib.request, urllib.error

REPO     = "antonio103first/meeting-recording-minute-app"
TOKEN    = "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"
BASE     = os.path.dirname(os.path.abspath(__file__))

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "trigger_build.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def upload(gh_path, local_path, message, binary=False):
    mode = "rb" if binary else "r"
    enc  = None if binary else "utf-8"
    with open(local_path, mode, encoding=enc) as f:
        content = f.read()
    if binary:
        encoded = base64.b64encode(content).decode("ascii")
    else:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    existing, status = gh_api(f"/contents/{gh_path}")
    sha = existing.get("sha") if status == 200 else None

    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    _, status = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    action = "업데이트" if sha else "신규"
    if status in (200, 201):
        print(f"  OK ({action}): {gh_path}")
    else:
        print(f"  FAIL (HTTP {status}): {gh_path}")

print("\n[1/2] build.yml 업로드 (workflow_dispatch 포함)...")
upload(
    ".github/workflows/build.yml",
    os.path.join(BASE, ".github", "workflows", "build.yml"),
    "ci: build.yml workflow_dispatch 트리거 추가 + 아이콘 로드 방식 변경"
)

print("\n[2/2] make_icon.py 업로드 (PNG 로드 방식)...")
upload(
    "make_icon.py",
    os.path.join(BASE, "make_icon.py"),
    "feat: 아이콘 변경 - IconKitchen MEET 디자인 적용"
)

print(f"\n완료! Actions 페이지를 새로고침하세요:")
print(f"https://github.com/{REPO}/actions")
input("\n아무 키나 누르면 종료됩니다...")
