"""
icon-192.png를 소스로 고품질 ICO 생성 후 GitHub 업로드
실행: python update_icon_192.py
"""
import os, json, base64, urllib.request, urllib.error
from PIL import Image

REPO       = "antonio103first/meeting-recording-minute-app"
TOKEN      = "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"
ICON_DIR   = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web"
BASE       = os.path.dirname(os.path.abspath(__file__))

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "update_icon_192.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def upload_gh(local_path, gh_path, message):
    with open(local_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    existing, status = gh_api(f"/contents/{gh_path}")
    sha = existing.get("sha") if status == 200 else None
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha
    _, status = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    return status in (200, 201)

# 사용 가능한 아이콘 파일 확인
print("[1/3] 아이콘 파일 확인 중...")
candidates = ["icon-192.png", "icon-512.png", "icon-256.png", "icon-128.png"]
src_png = None
for fname in candidates:
    fpath = os.path.join(ICON_DIR, fname)
    if os.path.exists(fpath):
        size = os.path.getsize(fpath)
        print(f"  발견: {fname} ({size:,} bytes)")
        if src_png is None:
            src_png = fpath

if not src_png:
    print("  !! 아이콘 파일을 찾을 수 없습니다. ICON_DIR 경로를 확인하세요.")
    input("아무 키나 누르면 종료됩니다...")
    exit()

print(f"\n  사용할 소스: {os.path.basename(src_png)}")

# 고품질 ICO 생성
print("\n[2/3] 고품질 ICO 생성 중...")
img = Image.open(src_png).convert("RGBA")
print(f"  원본 크기: {img.size}")

# ICO에 포함할 크기들 (Windows 권장)
sizes = [256, 128, 64, 48, 32, 16]
icons = []
for s in sizes:
    resized = img.resize((s, s), Image.LANCZOS)
    icons.append(resized)
    print(f"  {s}x{s} 생성 완료")

ico_path = os.path.join(BASE, "app_icon.ico")
png_path = os.path.join(BASE, "app_icon.png")

icons[0].save(
    ico_path,
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=icons[1:]
)
print(f"  ICO 저장: {ico_path} ({os.path.getsize(ico_path):,} bytes)")

# PNG도 저장 (make_icon.py 참조용)
img.save(png_path, format="PNG")
print(f"  PNG 저장: {png_path}")

# GitHub 업로드
print("\n[3/3] GitHub 업로드 중...")
if upload_gh(png_path, "app_icon.png", "fix: 고품질 아이콘 소스 교체 (icon-192.png)"):
    print("  OK - app_icon.png")
else:
    print("  FAIL - app_icon.png")

if upload_gh(ico_path, "app_icon.ico", "fix: 고품질 ICO 재생성 (256/128/64/48/32/16px)"):
    print("  OK - app_icon.ico")
else:
    print("  FAIL - app_icon.ico")

print(f"\n빌드 자동 시작: https://github.com/{REPO}/actions")
print(f"완료 후 다운로드: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
