"""
build.yml에 permissions: contents: write 추가
실행: python fix_permissions.py
"""
import json, base64, urllib.request, urllib.error

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "fix_permissions.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

data, status = gh_api("/contents/.github/workflows/build.yml")
sha = data["sha"]

NEW_BUILD_YML = """name: Windows EXE 빌드 & 릴리즈

on:
  push:
    branches: [ master ]
  workflow_dispatch:

permissions:
  contents: write

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
        python -m pip install --upgrade pip
        pip install pyinstaller pillow sounddevice soundfile numpy requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

    - name: 아이콘 생성
      run: python make_icon.py

    - name: EXE 빌드 (PyInstaller)
      run: |
        pyinstaller --onefile --windowed `
          --name "회의녹음요약" `
          --icon app_icon.ico `
          --add-data "app_dist/config.py;." `
          --add-data "app_dist/database.py;." `
          --add-data "app_dist/recorder.py;." `
          --add-data "app_dist/gemini_service.py;." `
          --add-data "app_dist/clova_service.py;." `
          --add-data "app_dist/file_manager.py;." `
          --add-data "app_dist/google_drive.py;." `
          --hidden-import "requests" `
          --hidden-import "google.auth" `
          --hidden-import "google.auth.transport.requests" `
          --hidden-import "google_auth_oauthlib.flow" `
          --hidden-import "googleapiclient.discovery" `
          --hidden-import "googleapiclient.http" `
          app_dist/main.py

    - name: EXE 확인
      run: dir dist\\

    - name: 릴리즈 생성 및 EXE 업로드
      uses: softprops/action-gh-release@v2
      with:
        tag_name: build-${{ github.run_number }}
        name: "회의녹음요약 Build #${{ github.run_number }}"
        body: |
          자동 빌드 - MEET 아이콘 적용
          커밋: ${{ github.sha }}
        files: dist/회의녹음요약.exe
"""

encoded = base64.b64encode(NEW_BUILD_YML.encode("utf-8")).decode("ascii")
payload = {
    "message": "fix: GITHUB_TOKEN contents write 권한 추가 (릴리즈 생성)",
    "content": encoded,
    "sha": sha
}

_, status = gh_api("/contents/.github/workflows/build.yml", method="PUT", data=payload)
if status in (200, 201):
    print("OK - 업로드 성공! 빌드 자동 시작됩니다.")
    print(f"Actions: https://github.com/{REPO}/actions")
    print(f"Releases: https://github.com/{REPO}/releases")
else:
    print(f"FAIL HTTP {status}")

input("아무 키나 누르면 종료됩니다...")
