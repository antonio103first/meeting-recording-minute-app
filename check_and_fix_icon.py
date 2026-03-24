"""
1. GitHub의 app_icon.png 상태 확인
2. 로컬 MEET 아이콘으로 재업로드
3. build.yml에 --add-data "app_icon.ico;." 추가 (런타임 아이콘 적용)
실행: python check_and_fix_icon.py
"""
import os, json, base64, urllib.request, urllib.error

REPO       = "antonio103first/meeting-recording-minute-app"
TOKEN      = "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"
LOCAL_ICON = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web\icon-512.png"
BASE       = os.path.dirname(os.path.abspath(__file__))

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "check_and_fix_icon.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

# ── 1. GitHub app_icon.png 현재 크기 확인 ─────────────────────────────
print("[1/3] GitHub app_icon.png 확인 중...")
data, status = gh_api("/contents/app_icon.png")
if status == 200:
    gh_size = data.get("size", 0)
    print(f"  GitHub app_icon.png 크기: {gh_size:,} bytes")
    if gh_size < 10000:
        print("  !! 크기가 너무 작음 → MEET 아이콘이 아닐 가능성 높음")
    else:
        print("  OK 크기 정상")
    icon_sha = data["sha"]
else:
    print(f"  app_icon.png 없음 (HTTP {status})")
    icon_sha = None

# ── 2. 로컬 MEET 아이콘 → GitHub 재업로드 ────────────────────────────
print("\n[2/3] 로컬 MEET 아이콘 재업로드 중...")
if not os.path.exists(LOCAL_ICON):
    print(f"  !! 로컬 파일 없음: {LOCAL_ICON}")
    print("  → 다른 경로에 있으면 LOCAL_ICON 변수 수정 필요")
else:
    local_size = os.path.getsize(LOCAL_ICON)
    print(f"  로컬 아이콘 크기: {local_size:,} bytes")
    with open(LOCAL_ICON, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    payload = {"message": "fix: MEET 아이콘(app_icon.png) 재업로드", "content": encoded}
    if icon_sha:
        payload["sha"] = icon_sha
    _, status = gh_api("/contents/app_icon.png", method="PUT", data=payload)
    if status in (200, 201):
        print("  OK - app_icon.png 업로드 성공")
    else:
        print(f"  FAIL HTTP {status}")

# ── 3. build.yml 수정 (--add-data app_icon.ico 추가) ──────────────────
print("\n[3/3] build.yml 수정 중 (런타임 아이콘 번들 추가)...")
data, status = gh_api("/contents/.github/workflows/build.yml")
yml_sha = data["sha"]

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
        pip install -r requirements.txt
        pip install pyinstaller

    - name: 아이콘 생성
      run: python make_icon.py

    - name: EXE 빌드 (PyInstaller)
      run: |
        pyinstaller --onefile --windowed `
          --name "회의녹음요약" `
          --icon app_icon.ico `
          --add-data "app_icon.ico;." `
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
          --collect-all "google.genai" `
          app_dist/main.py

    - name: EXE 확인
      run: dir dist\\

    - name: 릴리즈 생성 및 EXE 업로드
      uses: softprops/action-gh-release@v2
      with:
        tag_name: build-${{ github.run_number }}
        name: "회의녹음요약 Build #${{ github.run_number }}"
        body: |
          MEET 아이콘 적용 빌드
          커밋: ${{ github.sha }}
        files: dist/회의녹음요약.exe
"""

encoded = base64.b64encode(NEW_BUILD_YML.encode("utf-8")).decode("ascii")
payload = {
    "message": "fix: app_icon.ico 런타임 번들 추가 + MEET 아이콘 재적용",
    "content": encoded,
    "sha": yml_sha
}
_, status = gh_api("/contents/.github/workflows/build.yml", method="PUT", data=payload)
if status in (200, 201):
    print("  OK - build.yml 업로드 성공")
    print(f"\n빌드 자동 시작: https://github.com/{REPO}/actions")
    print(f"완료 후 다운로드: https://github.com/{REPO}/releases")
else:
    print(f"  FAIL HTTP {status}")

input("\n아무 키나 누르면 종료됩니다...")
