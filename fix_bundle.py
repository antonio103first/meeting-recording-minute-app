"""
build.yml에 app_icon.png 번들 추가 + favicon.ico 재업로드
실행: python fix_bundle.py
"""
import os, json, base64, urllib.request, urllib.error

REPO     = "antonio103first/meeting-recording-minute-app"
TOKEN    = "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"
ICO_PATH = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web\favicon.ico"
PNG_PATH = r"C:\Users\anton\Downloads\IconKitchen-Output (8)\web\icon-512.png"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    h = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json",
         "Content-Type": "application/json", "User-Agent": "fix_bundle.py"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def upload(path_or_bytes, gh_path, msg):
    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            data = f.read()
    else:
        data = path_or_bytes
    enc = base64.b64encode(data).decode("ascii")
    d, s = gh_api(f"/contents/{gh_path}")
    sha = d.get("sha") if s == 200 else None
    payload = {"message": msg, "content": enc}
    if sha: payload["sha"] = sha
    _, s = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    print(f"  {'OK' if s in (200,201) else f'FAIL {s}'} - {gh_path}")

# 1. favicon.ico → app_icon.ico
print("[1/3] favicon.ico 업로드...")
if os.path.exists(ICO_PATH):
    print(f"  크기: {os.path.getsize(ICO_PATH):,} bytes")
    upload(ICO_PATH, "app_icon.ico", "fix: favicon.ico 원본 직접 사용")
else:
    print(f"  파일 없음: {ICO_PATH}")

# 2. icon-512.png → app_icon.png
print("[2/3] icon-512.png 업로드...")
if os.path.exists(PNG_PATH):
    print(f"  크기: {os.path.getsize(PNG_PATH):,} bytes")
    upload(PNG_PATH, "app_icon.png", "fix: icon-512.png 원본 직접 사용")
else:
    print(f"  파일 없음: {PNG_PATH}")

# 3. build.yml - app_icon.png 번들 확인 및 추가
print("[3/3] build.yml 확인...")
d, _ = gh_api("/contents/.github/workflows/build.yml")
sha = d["sha"]
yml = base64.b64decode(d["content"]).decode("utf-8")
print(f"  app_icon.ico 번들: {'있음' if 'app_icon.ico' in yml else '없음'}")
print(f"  app_icon.png 번들: {'있음' if 'app_icon.png' in yml else '없음'}")

# app_icon.png 번들 없으면 추가
if '"app_icon.png;."' not in yml:
    yml = yml.replace(
        '--add-data "app_icon.ico;."',
        '--add-data "app_icon.ico;." `\n          --add-data "app_icon.png;."'
    )
    upload(yml.encode("utf-8"), ".github/workflows/build.yml",
           "fix: build.yml app_icon.png 번들 추가")
    print("  app_icon.png 번들 추가 완료")
else:
    print("  이미 포함됨 - 변경 없음")

print(f"\n빌드: https://github.com/{REPO}/actions")
print(f"릴리즈: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
