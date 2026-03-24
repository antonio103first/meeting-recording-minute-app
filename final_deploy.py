"""
최종 배포 스크립트
- app_dist/ 전체 파일 확인 및 업로드
- 아이콘 파일 확인
- MANUAL.md 업데이트
실행: python final_deploy.py
"""
import os, json, base64, urllib.request, urllib.error

REPO     = "antonio103first/meeting-recording-minute-app"
TOKEN    = "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"
BASE     = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    h = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json",
         "Content-Type": "application/json", "User-Agent": "final_deploy.py"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def upload(data_bytes, gh_path, msg):
    enc = base64.b64encode(data_bytes).decode("ascii")
    d, s = gh_api(f"/contents/{gh_path}")
    sha = d.get("sha") if s == 200 else None
    payload = {"message": msg, "content": enc}
    if sha: payload["sha"] = sha
    _, s = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    status = "OK" if s in (200, 201) else f"FAIL({s})"
    print(f"  {status} - {gh_path}")
    return s in (200, 201)

def read_local(path):
    with open(path, "rb") as f:
        return f.read()

def fetch_gh(gh_path):
    d, s = gh_api(f"/contents/{gh_path}")
    if s == 200:
        return base64.b64decode(d["content"]).decode("utf-8"), d.get("sha")
    return None, None

# ── 1. app_dist/ 파일 업로드 ─────────────────────────────────────────
print("=" * 50)
print("[1/3] app_dist/ 파일 배포")
print("=" * 50)
APP_FILES = ["config.py","database.py","recorder.py","gemini_service.py",
             "clova_service.py","file_manager.py","google_drive.py","main.py"]
for fn in APP_FILES:
    local = os.path.join(BASE, "app_dist", fn)
    if os.path.exists(local):
        upload(read_local(local), f"app_dist/{fn}", f"deploy: {fn} 최종본")
    else:
        print(f"  SKIP(없음) - app_dist/{fn}")

# ── 2. 아이콘 파일 배포 ──────────────────────────────────────────────
print("\n" + "=" * 50)
print("[2/3] 아이콘 파일 배포")
print("=" * 50)

# PNG (maskable 우선)
for fn in ["icon-maskable-512.png", "icon-512.png", "icon-192.png"]:
    p = os.path.join(ICON_DIR, fn)
    if os.path.exists(p):
        print(f"  PNG 소스: {fn} ({os.path.getsize(p):,} bytes)")
        upload(read_local(p), "app_icon.png", "deploy: MEET 아이콘 PNG 최종본")
        break

# ICO (favicon.ico 우선)
from PIL import Image
import io
for fn in ["icon-maskable-512.png", "icon-512.png"]:
    p = os.path.join(ICON_DIR, fn)
    if os.path.exists(p):
        img = Image.open(p).convert("RGBA")
        bg = Image.new("RGBA", img.size, (100, 30, 160, 255))
        bg.paste(img, mask=img.split()[3])
        solid = bg.convert("RGB")
        sizes = [256, 128, 64, 48, 32, 16]
        frames = [solid.resize((s,s), Image.LANCZOS) for s in sizes]
        buf = io.BytesIO()
        frames[0].save(buf, format="ICO", sizes=[(s,s) for s in sizes], append_images=frames[1:])
        upload(buf.getvalue(), "app_icon.ico", "deploy: MEET 아이콘 ICO 최종본")
        break

# ── 3. MANUAL.md 업데이트 ────────────────────────────────────────────
print("\n" + "=" * 50)
print("[3/3] MANUAL.md 업데이트")
print("=" * 50)

manual, manual_sha = fetch_gh("MANUAL.md")
if manual:
    # 아이콘 관련 섹션 업데이트 또는 추가
    icon_note = """
## 앱 아이콘 안내

앱 아이콘은 **MEET 디자인** (마젠타/퍼플 그라디언트, 원형 링 패턴)이 적용되어 있습니다.

- 탐색기에서 EXE 파일 아이콘으로 표시됩니다
- 앱 실행 시 창 상단(타이틀바)에도 동일한 아이콘이 표시됩니다
"""
    if "## 앱 아이콘 안내" not in manual:
        # 맨 뒤에 추가
        updated = manual.rstrip() + "\n" + icon_note
    else:
        # 기존 섹션 교체
        import re
        updated = re.sub(r'## 앱 아이콘 안내.*?(?=\n##|\Z)', icon_note.strip(), manual, flags=re.DOTALL)

    upload(updated.encode("utf-8"), "MANUAL.md", "docs: MANUAL.md 아이콘 섹션 업데이트")
else:
    print("  MANUAL.md를 GitHub에서 찾을 수 없음")

print("\n" + "=" * 50)
print("배포 완료!")
print(f"Actions : https://github.com/{REPO}/actions")
print(f"Releases: https://github.com/{REPO}/releases")
print(f"Manual  : https://github.com/{REPO}/blob/master/MANUAL.md")
print("=" * 50)
input("\n아무 키나 누르면 종료됩니다...")
