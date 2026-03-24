"""
build.yml을 확인하고, 릴리즈 생성이 포함된 올바른 버전으로 업데이트합니다.
실행: python fix_build_yml.py
"""
import json, base64, urllib.request, urllib.error, datetime

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "fix_build_yml.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

# 현재 build.yml 확인
print("[1/3] 현재 build.yml 확인 중...")
data, status = gh_api("/contents/.github/workflows/build.yml")
sha = None
if status == 200:
    sha = data["sha"]
    current = base64.b64decode(data["content"]).decode("utf-8")
    print("=== 현재 build.yml ===")
    print(current[:3000])
    print("... (잘림)" if len(current) > 3000 else "")
else:
    print(f"오류: HTTP {status}")

print("\n[2/3] 수정된 build.yml 준비 중...")

# 올바른 build.yml - master push 시 항상 EXE 빌드 + 릴리즈 생성
tag = datetime.datetime.utcnow().strftime("v%Y.%m%d.%H%M")

NEW_BUILD_YML = f"""name: Windows EXE 빌드 & 릴리즈

on:
  push:
    branches: [ master ]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest

    steps:
    - name: 코드 체크아웃
      uses: actions/checkout@v4

    - name: Python 설치
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: 패키지 설치
      run: |
        pip install pyinstaller pillow sounddevice soundfile numpy requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

    - name: 아이콘 생성
      run: python make_icon.py

    - name: EXE 빌드 (PyInstaller)
      run: |
        pyinstaller --onefile --windowed --name="MeetingMinute" ^
          --add-data "app_dist/config.py;." ^
          --add-data "app_dist/database.py;." ^
          --add-data "app_dist/recorder.py;." ^
          --add-data "app_dist/gemini_service.py;." ^
          --add-data "app_dist/clova_service.py;." ^
          --add-data "app_dist/file_manager.py;." ^
          --add-data "app_dist/google_drive.py;." ^
          --add-data "app_icon.ico;." ^
          app_dist/main.py
      shell: cmd

    - name: EXE 확인
      run: dir dist\\

    - name: 태그 생성 및 릴리즈 업로드
      uses: softprops/action-gh-release@v2
      with:
        tag_name: build-${{{{ github.run_number }}}}
        name: "MeetingMinute Build #${{{{ github.run_number }}}}"
        body: |
          자동 빌드 - ${{{{ github.sha }}}}
          - IconKitchen MEET 디자인 아이콘 적용
          - CLOVA + Gemini + Google Drive 연동
        files: dist/MeetingMinute.exe
        token: ${{{{ secrets.GITHUB_TOKEN }}}}
"""

print("새 build.yml 내용 준비 완료.")
print(f"릴리즈 태그 형식: build-{{run_number}}")

# 업로드
print("\n[3/3] GitHub에 업로드 중...")
encoded = base64.b64encode(NEW_BUILD_YML.encode("utf-8")).decode("ascii")
payload = {
    "message": "fix: build.yml 릴리즈 생성 로직 추가 (softprops/action-gh-release)",
    "content": encoded
}
if sha:
    payload["sha"] = sha

_, status = gh_api("/contents/.github/workflows/build.yml", method="PUT", data=payload)
if status in (200, 201):
    print("OK - build.yml 업로드 성공!")
    print(f"\n빌드가 자동 시작됩니다:")
    print(f"https://github.com/{REPO}/actions")
    print(f"\n완료 후 릴리즈 페이지 확인:")
    print(f"https://github.com/{REPO}/releases")
else:
    print(f"FAIL - HTTP {status}")

input("\n아무 키나 누르면 종료됩니다...")
