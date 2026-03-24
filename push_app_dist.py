"""
app_dist/ 전체 파일을 GitHub에 업로드하여 빌드 오류를 해결합니다.
실행: python push_app_dist.py
"""
import os, base64, json, urllib.request, urllib.error

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"
BASE  = os.path.dirname(os.path.abspath(__file__))

# PyInstaller build.yml 에 명시된 파일 + main.py
APP_DIST_FILES = [
    "config.py",
    "database.py",
    "recorder.py",
    "gemini_service.py",
    "clova_service.py",
    "file_manager.py",
    "google_drive.py",
    "main.py",
]

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "push_app_dist.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def upload_file(local_path, gh_path, message):
    if not os.path.exists(local_path):
        print(f"  SKIP (not found): {local_path}")
        return False

    with open(local_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    existing, status = gh_api(f"/contents/{gh_path}")
    sha = existing.get("sha") if status == 200 else None

    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    _, status = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    action = "업데이트" if sha else "신규"
    if status in (200, 201):
        print(f"  OK ({action}): {gh_path}")
        return True
    else:
        print(f"  FAIL (HTTP {status}): {gh_path}")
        return False

print("\n[1/2] app_dist/ 파일 GitHub 업로드 중...")
print(f"      로컬 경로: {os.path.join(BASE, 'app_dist')}\n")

success = 0
fail = 0
skip = 0

for fname in APP_DIST_FILES:
    local = os.path.join(BASE, "app_dist", fname)
    gh    = f"app_dist/{fname}"
    msg   = f"fix: restore app_dist/{fname} for PyInstaller build"
    result = upload_file(local, gh, msg)
    if result is True:
        success += 1
    elif result is False and not os.path.exists(local):
        skip += 1
    else:
        fail += 1

print(f"\n결과: {success}개 업로드 성공, {skip}개 스킵(파일없음), {fail}개 실패")

# 업로드 성공 시 자동으로 Actions 빌드가 트리거됨
if success > 0:
    print("\n[2/2] 빌드 자동 트리거됨 (commit push 방식)")
    print(f"확인: https://github.com/{REPO}/actions")
else:
    print("\n[!] 업로드된 파일이 없습니다. app_dist/ 폴더를 확인하세요.")

input("\n아무 키나 누르면 종료됩니다...")
