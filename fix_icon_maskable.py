"""
icon-maskable-512.png (투명 없는 버전) → ICO 변환 → GitHub 업로드
실행: python fix_icon_maskable.py
"""
import os, json, base64, urllib.request, urllib.error, io
from PIL import Image

REPO     = "antonio103first/meeting-recording-minute-app"
TOKEN    = "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"
ICON_DIR = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    h = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json",
         "Content-Type": "application/json", "User-Agent": "fix_icon_maskable.py"}
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
    print(f"  {'OK' if s in (200,201) else f'FAIL {s}'} - {gh_path}")

# 사용할 PNG 선택 (투명 없는 maskable 버전 우선)
print("[1/3] PNG 파일 선택...")
candidates = ["icon-maskable-512.png", "icon-maskable-192.png", "icon-512.png", "icon-192.png"]
src = None
for fn in candidates:
    p = os.path.join(ICON_DIR, fn)
    if os.path.exists(p):
        src = p
        print(f"  선택: {fn} ({os.path.getsize(p):,} bytes)")
        break

if not src:
    print("  오류: 파일 없음")
    input("종료"); exit()

# ICO 생성 - 투명 배경을 아이콘 배경색으로 채움
print("\n[2/3] ICO 생성...")
img = Image.open(src).convert("RGBA")
print(f"  원본: {img.size}, 모드: {img.mode}")

# 투명 영역을 아이콘 배경색(마젠타/퍼플)으로 채우기
bg_color = (100, 30, 160, 255)  # 퍼플 계열
background = Image.new("RGBA", img.size, bg_color)
background.paste(img, mask=img.split()[3])
img_solid = background.convert("RGB")

# 다중 크기 ICO 생성
sizes = [256, 128, 64, 48, 32, 16]
ico_frames = [img_solid.resize((s, s), Image.LANCZOS) for s in sizes]

buf = io.BytesIO()
ico_frames[0].save(
    buf, format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=ico_frames[1:]
)
ico_bytes = buf.getvalue()
print(f"  ICO 생성: {len(ico_bytes):,} bytes ({len(sizes)}개 크기)")

# PNG도 저장 (app_icon.png용)
png_buf = io.BytesIO()
img_solid.save(png_buf, format="PNG")
png_bytes = png_buf.getvalue()

# GitHub 업로드
print("\n[3/3] GitHub 업로드...")
upload(ico_bytes, "app_icon.ico", "fix: maskable PNG 기반 고품질 ICO (투명 배경 제거)")
upload(png_bytes, "app_icon.png", "fix: maskable PNG 배경 고정 버전")

print(f"\n빌드: https://github.com/{REPO}/actions")
print(f"릴리즈: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
