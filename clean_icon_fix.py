"""
아이콘 완전 초기화 - PNG 원본 직접 사용
실행: python clean_icon_fix.py
"""
import os, json, base64, urllib.request, urllib.error

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

ICON_DIR = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "clean_icon_fix.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def get_sha(gh_path):
    d, s = gh_api(f"/contents/{gh_path}")
    return d.get("sha") if s == 200 else None

def upload_bytes(content_bytes, gh_path, message):
    encoded = base64.b64encode(content_bytes).decode("ascii")
    payload = {"message": message, "content": encoded}
    sha = get_sha(gh_path)
    if sha:
        payload["sha"] = sha
    _, status = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    print(f"  {'OK' if status in (200,201) else f'FAIL {status}'} {gh_path}")

# ── 1. PNG 선택 및 업로드 ────────────────────────────────────────────
print("[1/4] PNG 파일 확인...")
src = None
for fn in ["icon-512.png", "icon-192.png"]:
    p = os.path.join(ICON_DIR, fn)
    if os.path.exists(p):
        src = p
        print(f"  사용: {fn}  크기: {os.path.getsize(p):,} bytes")
        break

if not src:
    print("  ERROR: PNG 파일 없음")
    input("종료")
    exit()

with open(src, "rb") as f:
    png_bytes = f.read()

upload_bytes(png_bytes, "app_icon.png", "fix: MEET PNG 원본 업로드")

# ── 2. make_icon.py → 완전 단순화 (ICO 생성 X, 존재 확인만) ─────────
print("\n[2/4] make_icon.py 단순화...")
MAKE_ICON = b'import os\nbase=os.path.dirname(os.path.abspath(__file__))\nprint("Icon step skipped - using pre-built files.")\n'
upload_bytes(MAKE_ICON, "make_icon.py", "fix: make_icon.py 단순화 (변환 제거)")

# ── 3. main.py: iconphoto(PNG) 코드 삽입 ────────────────────────────
print("\n[3/4] main.py 수정...")
d, _ = gh_api("/contents/app_dist/main.py")
main_sha = d["sha"]
main_code = base64.b64decode(d["content"]).decode("utf-8")

ICON_CODE = (
    "        # --- 앱 아이콘 설정 ---\n"
    "        try:\n"
    "            import tkinter as _tk\n"
    "            from PIL import Image as _Img, ImageTk as _ITk\n"
    "            _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))\n"
    "            _png = os.path.join(_base, 'app_icon.png')\n"
    "            if os.path.exists(_png):\n"
    "                _im = _Img.open(_png)\n"
    "                _ph = _ITk.PhotoImage(_im)\n"
    "                self.iconphoto(True, _ph)\n"
    "                self._icon_ref = _ph\n"
    "        except Exception:\n"
    "            pass\n"
    "        # --- 아이콘 설정 끝 ---\n"
)

# 기존 아이콘 관련 코드 모두 제거 후 새 코드 삽입
import re
# 이전 스크립트들이 삽입한 모든 아이콘 블록 제거
cleaned = re.sub(
    r'\s*# ?-*.*?아이콘.*?-*\n.*?try:.*?except Exception:\s*pass\n.*?# ?-*.*?끝.*?\n',
    '\n',
    main_code,
    flags=re.DOTALL
)
# wm_iconbitmap 블록도 제거
cleaned = re.sub(
    r'\s*try:\s*\n\s*(?:from PIL.*?\n\s*)?_base\s*=.*?_MEIPASS.*?\n.*?(?:wm_iconbitmap|iconphoto).*?\n(?:.*?\n)*?\s*except Exception:\s*\n\s*pass\n',
    '\n',
    cleaned,
    flags=re.DOTALL
)

# self.resizable 다음 줄에 아이콘 코드 삽입
if "self.resizable" in cleaned:
    cleaned = re.sub(
        r'(self\.resizable\([^)]+\))',
        r'\1\n' + ICON_CODE,
        cleaned,
        count=1
    )
    print("  OK - iconphoto(PNG) 코드 삽입")
else:
    print("  WARN: self.resizable 없음, 코드 삽입 위치 확인 필요")

upload_bytes(cleaned.encode("utf-8"), "app_dist/main.py",
             "fix: 아이콘 코드 초기화 - iconphoto(PNG) 방식 적용")

# ── 4. build.yml: app_icon.png 번들 추가 확인 ───────────────────────
print("\n[4/4] build.yml app_icon.png 번들 확인...")
d, _ = gh_api("/contents/.github/workflows/build.yml")
yml_sha = d["sha"]
yml = base64.b64decode(d["content"]).decode("utf-8")

if '"app_icon.png;."' not in yml:
    yml = yml.replace(
        '--add-data "app_icon.ico;."',
        '--add-data "app_icon.ico;." `\n          --add-data "app_icon.png;."'
    )
    upload_bytes(yml.encode("utf-8"), ".github/workflows/build.yml",
                 "fix: build.yml app_icon.png 번들 추가")
    print("  OK - app_icon.png 번들 추가됨")
else:
    print("  OK - 이미 포함됨")

print(f"\n완료! 빌드: https://github.com/{REPO}/actions")
print(f"릴리즈: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
