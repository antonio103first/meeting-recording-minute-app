"""
아이콘 수정 - 단순 버전 (정규식 없음)
실행: python simple_icon_fix.py
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
        "User-Agent": "simple_icon_fix.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def upload(content_bytes, gh_path, message):
    encoded = base64.b64encode(content_bytes).decode("ascii")
    d, s = gh_api(f"/contents/{gh_path}")
    sha = d.get("sha") if s == 200 else None
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha
    _, status = gh_api(f"/contents/{gh_path}", method="PUT", data=payload)
    print(f"  {'OK' if status in (200,201) else f'FAIL {status}'} - {gh_path}")

# 1. PNG 업로드
print("[1/3] PNG 업로드...")
for fn in ["icon-512.png", "icon-192.png"]:
    p = os.path.join(ICON_DIR, fn)
    if os.path.exists(p):
        with open(p, "rb") as f:
            upload(f.read(), "app_icon.png", "fix: MEET PNG 원본 업로드")
        print(f"  사용 파일: {fn}")
        break

# 2. make_icon.py 단순화
print("\n[2/3] make_icon.py 단순화...")
upload(b'print("Icon step complete.")\n', "make_icon.py",
       "fix: make_icon.py 단순화")

# 3. main.py - 현재 파일 줄 단위로 처리 (정규식 없음)
print("\n[3/3] main.py 아이콘 코드 교체...")
d, _ = gh_api("/contents/app_dist/main.py")
main_sha = d["sha"]
lines = base64.b64decode(d["content"]).decode("utf-8").split("\n")

NEW_ICON = [
    "        try:",
    "            from PIL import Image as _I, ImageTk as _IT",
    "            import sys as _s, os as _o",
    "            _b = getattr(_s, '_MEIPASS', _o.path.dirname(_o.path.abspath(__file__)))",
    "            _p = _o.path.join(_b, 'app_icon.png')",
    "            if _o.path.exists(_p):",
    "                _ph = _IT.PhotoImage(_I.open(_p))",
    "                self.iconphoto(True, _ph)",
    "                self._icon_ref = _ph",
    "        except Exception:",
    "            pass",
]

out = []
skip = False
for line in lines:
    # 기존 아이콘 try 블록 시작 감지
    if ("wm_iconbitmap" in line or
        ("iconphoto" in line and "_icon_ref" not in line and "NEW_ICON" not in line) or
        ("_MEIPASS" in line and "_ico" in line)):
        skip = True

    if skip:
        if "except Exception:" in line:
            # 다음 줄(pass)도 스킵 후 종료
            skip = "pass_next"
        elif skip == "pass_next" and "pass" in line.strip():
            skip = False
            # 새 코드 삽입
            out.extend(NEW_ICON)
        continue

    # self.resizable 다음에 아이콘 코드 삽입 (기존 코드가 없는 경우)
    out.append(line)

new_content = "\n".join(out)

# 혹시 교체가 안됐으면 self.resizable 뒤에 삽입
if "iconphoto" not in new_content and "self.resizable" in new_content:
    result = []
    for line in new_content.split("\n"):
        result.append(line)
        if "self.resizable" in line:
            result.extend(NEW_ICON)
    new_content = "\n".join(result)
    print("  self.resizable 뒤에 삽입")

upload(new_content.encode("utf-8"), "app_dist/main.py",
       "fix: 아이콘 iconphoto(PNG) 적용 - 줄 단위 처리")

print(f"\n완료! 빌드: https://github.com/{REPO}/actions")
print(f"릴리즈: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
