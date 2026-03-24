"""
현재 GitHub의 build.yml 내용을 확인합니다.
실행: python check_build_yml.py
"""
import json, base64, urllib.request, urllib.error

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

def gh_get(path):
    url = f"https://api.github.com/repos/{REPO}{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "check_build_yml.py"
    })
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

data, status = gh_get("/contents/.github/workflows/build.yml")
if status == 200:
    content = base64.b64decode(data["content"]).decode("utf-8")
    print("=== 현재 build.yml 내용 ===")
    print(content)
else:
    print(f"오류 HTTP {status}: {data}")

input("\n아무 키나 누르면 종료됩니다...")
