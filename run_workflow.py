"""
GitHub Actions 워크플로를 수동으로 트리거합니다.
실행: python run_workflow.py
"""
import json, urllib.request, urllib.error

REPO     = "antonio103first/meeting-recording-minute-app"
TOKEN    = "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"
WORKFLOW = "build.yml"
BRANCH   = "master"

url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
data = json.dumps({"ref": BRANCH}).encode()
headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "Content-Type": "application/json",
    "User-Agent": "run_workflow.py"
}

req = urllib.request.Request(url, data=data, headers=headers, method="POST")
try:
    with urllib.request.urlopen(req) as r:
        print(f"OK (HTTP {r.status}): 빌드 트리거 성공!")
        print(f"확인: https://github.com/{REPO}/actions")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"FAIL (HTTP {e.code}): {body}")

input("\n아무 키나 누르면 종료됩니다...")
