"""
아이콘 설정 스크립트 — IconKitchen PNG를 앱 아이콘으로 변환 후 GitHub 자동 배포
실행: python setup_icon.py
"""
import os, sys, shutil, subprocess, base64, json, urllib.request, urllib.error

# ── 경로 설정 ──────────────────────────────────────────
REPO_DIR   = os.path.dirname(os.path.abspath(__file__))
SRC_PNG    = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web\icon-512.png"
DST_PNG    = os.path.join(REPO_DIR, "app_icon.png")
DST_ICO    = os.path.join(REPO_DIR, "app_icon.ico")
GH_TOKEN   = "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"
GH_REPO    = "antonio103first/meeting-recording-minute-app"

def log(msg): print(f"  {msg}")

# ── Step 1: PNG 복사 ──────────────────────────────────
print("\n[1/3] 아이콘 PNG 복사 중...")
if not os.path.exists(SRC_PNG):
    print(f"ERROR: 소스 파일을 찾을 수 없습니다:\n  {SRC_PNG}")
    sys.exit(1)
shutil.copy2(SRC_PNG, DST_PNG)
log(f"복사 완료: {DST_PNG}")

# ── Step 2: ICO 변환 ──────────────────────────────────
print("\n[2/3] ICO 변환 중...")
try:
    from PIL import Image
    img = Image.open(DST_PNG).convert("RGBA")
    sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
    icons = [img.resize(s, Image.LANCZOS) for s in sizes]
    icons[0].save(DST_ICO, format="ICO", sizes=sizes, append_images=icons[1:])
    log(f"ICO 생성 완료: {DST_ICO}")
except ImportError:
    print("ERROR: Pillow가 설치되어 있지 않습니다.")
    print("       pip install pillow 실행 후 재시도해주세요.")
    sys.exit(1)

# ── Step 3: GitHub API로 파일 업로드 ──────────────────
print("\n[3/3] GitHub 업로드 중...")

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{GH_REPO}{path}"
    headers = {
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "setup_icon.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

for fpath, fname in [(DST_PNG, "app_icon.png"), (DST_ICO, "app_icon.ico")]:
    with open(fpath, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    existing, status = gh_api(f"/contents/{fname}")
    sha = existing.get("sha") if status == 200 else None

    payload = {
        "message": f"feat: 앱 아이콘 변경 ({fname}) - IconKitchen MEET 디자인",
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha

    _, status = gh_api(f"/contents/{fname}", method="PUT", data=payload)
    if status in (200, 201):
        log(f"{'업데이트' if sha else '신규 업로드'}: {fname}")
    else:
        log(f"FAIL (HTTP {status}): {fname}")

print("\n완료! GitHub에 새 아이콘이 반영되었습니다.")
print(f"https://github.com/{GH_REPO}")
input("\n아무 키나 누르면 종료됩니다...")
