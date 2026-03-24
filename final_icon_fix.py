"""
1. 사용자가 지정한 PNG를 app_icon.png로 GitHub 업로드
2. main.py를 iconphoto(PNG) 방식으로 수정 → 색상 손실 없음
실행: python final_icon_fix.py
"""
import os, json, base64, urllib.request, urllib.error

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

# ── PNG 경로: icon-512.png 또는 icon-192.png 중 존재하는 것 사용 ──
ICON_DIR = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web"
for fname in ["icon-512.png", "icon-192.png", "apple-touch-icon.png"]:
    PNG_PATH = os.path.join(ICON_DIR, fname)
    if os.path.exists(PNG_PATH):
        print(f"사용할 PNG: {fname} ({os.path.getsize(PNG_PATH):,} bytes)")
        break
else:
    print("!! IconKitchen PNG 파일을 찾을 수 없습니다.")
    input("종료하려면 아무 키나 누르세요...")
    exit()

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "final_icon_fix.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def get_sha(path):
    d, s = gh_api(f"/contents/{path}")
    return d.get("sha") if s == 200 else None

def upload(content_bytes, gh_path, message):
    encoded = base64.b64encode(content_bytes).decode("ascii")
    sha = get_sha(gh_path)
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha
    _, status = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    ok = status in (200, 201)
    print(f"  {'OK' if ok else f'FAIL HTTP {status}'} - {gh_path}")
    return ok

# ── 1. app_icon.png 업로드 ──────────────────────────────────────────
print("\n[1/3] app_icon.png 업로드...")
with open(PNG_PATH, "rb") as f:
    png_bytes = f.read()
upload(png_bytes, "app_icon.png", "fix: MEET 아이콘 PNG 재업로드 (원본 선명도 유지)")

# ── 2. main.py 수정: iconphoto(PNG) 방식으로 교체 ──────────────────
print("\n[2/3] main.py 아이콘 코드 수정...")
data, _ = gh_api("/contents/app_dist/main.py")
main_sha = data["sha"]
main_content = base64.b64decode(data["content"]).decode("utf-8")

# wm_iconbitmap 관련 블록을 iconphoto 방식으로 교체
import re
new_icon_block = '''        try:
            from PIL import Image, ImageTk
            _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            _png = os.path.join(_base, 'app_icon.png')
            if os.path.exists(_png):
                _img = ImageTk.PhotoImage(Image.open(_png))
                self.iconphoto(True, _img)
                self._icon_img = _img
        except Exception:
            pass'''

# wm_iconbitmap 포함 try 블록 전체 교체
pattern = r'        try:.*?wm_iconbitmap.*?except Exception:\s*pass'
new_content, count = re.subn(pattern, new_icon_block, main_content, flags=re.DOTALL)

if count > 0:
    print(f"  OK - wm_iconbitmap → iconphoto 교체 완료 ({count}곳)")
    upload(new_content.encode("utf-8"), "app_dist/main.py",
           "fix: 앱 아이콘 iconphoto(PNG) 방식으로 변경 - ICO 색상 손실 해결")
else:
    print("  !! wm_iconbitmap 코드를 찾지 못했습니다 - main.py를 직접 확인하세요")

# ── 3. make_icon.py 유지 (빌드 시 ICO는 EXE 파일 아이콘용으로만) ──
print("\n[3/3] 완료")
print(f"\n빌드 자동 시작: https://github.com/{REPO}/actions")
print(f"완료 후 다운로드: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
