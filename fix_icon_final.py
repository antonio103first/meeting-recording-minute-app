"""
favicon.ico(IconKitchen 원본)를 직접 사용하도록 make_icon.py + GitHub 업데이트
실행: python fix_icon_final.py
"""
import os, json, base64, urllib.request, urllib.error

REPO      = "antonio103first/meeting-recording-minute-app"
TOKEN     = "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"
ICON_DIR  = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web"
FAVICON   = os.path.join(ICON_DIR, "favicon.ico")
ICON_512  = os.path.join(ICON_DIR, "icon-512.png")

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "fix_icon_final.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def upload(local_path, gh_path, message):
    with open(local_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    existing, status = gh_api(f"/contents/{gh_path}")
    sha = existing.get("sha") if status == 200 else None
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha
    _, status = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    ok = status in (200, 201)
    print(f"  {'OK' if ok else 'FAIL'} - {gh_path}")
    return ok

# 파일 존재 확인
print("[검증] IconKitchen 파일 확인...")
for f in [FAVICON, ICON_512]:
    exists = os.path.exists(f)
    size = os.path.getsize(f) if exists else 0
    print(f"  {'OK' if exists else '없음'} - {os.path.basename(f)} ({size:,} bytes)")

if not os.path.exists(FAVICON):
    print("\n!! favicon.ico 없음. 경로 확인 필요.")
    input("아무 키나 누르면 종료됩니다...")
    exit()

# make_icon.py 교체: PNG 변환 없이 favicon.ico 복사만 수행
NEW_MAKE_ICON = '''import os, shutil

base     = os.path.dirname(os.path.abspath(__file__))
ico_path = os.path.join(base, "app_icon.ico")

# favicon.ico가 이미 존재하면 그대로 사용 (변환 불필요)
if os.path.exists(ico_path):
    print("app_icon.ico already exists, skipping generation.")
else:
    print("app_icon.ico not found.")
    raise FileNotFoundError("app_icon.ico not found in repo.")

print("Icon ready: " + ico_path)
print("Icon generation complete.")
'''

print("\n[1/3] favicon.ico → app_icon.ico 업로드...")
upload(FAVICON, "app_icon.ico", "fix: IconKitchen favicon.ico 원본 직접 사용 (색상 보존)")

print("\n[2/3] app_icon.png 업로드...")
upload(ICON_512, "app_icon.png", "fix: app_icon.png 원본 유지")

print("\n[3/3] make_icon.py 업데이트 (변환 제거)...")
# make_icon.py SHA 가져오기
data, status = gh_api("/contents/make_icon.py")
sha = data.get("sha") if status == 200 else None
encoded = base64.b64encode(NEW_MAKE_ICON.encode("utf-8")).decode("ascii")
payload = {"message": "fix: make_icon.py - PNG 변환 제거, favicon.ico 원본 직접 사용", "content": encoded}
if sha:
    payload["sha"] = sha
_, status = gh_api("/contents/make_icon.py", method="PUT", data=payload)
print(f"  {'OK' if status in (200,201) else 'FAIL'} - make_icon.py")

print(f"\n빌드 자동 시작: https://github.com/{REPO}/actions")
print(f"완료 후 다운로드: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
