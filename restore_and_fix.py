"""
main.py 복구 + 문법 검증 후 업로드
실행: python restore_and_fix.py
"""
import os, json, base64, urllib.request, urllib.error

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

def gh_api(path, method="GET", data=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "restore_and_fix.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

# 1. main.py 다운로드
print("[1/4] main.py 다운로드...")
d, _ = gh_api("/contents/app_dist/main.py")
main_sha = d["sha"]
content = base64.b64decode(d["content"]).decode("utf-8")

# 2. 현재 문법 확인
print("[2/4] 현재 문법 검증...")
try:
    compile(content, "main.py", "exec")
    print("  현재 main.py 문법 OK")
    current_ok = True
except SyntaxError as e:
    print(f"  !! 문법 오류 발생: {e}")
    current_ok = False

# 3. 아이콘 관련 줄 확인 (참고용 출력)
print("\n[3/4] 아이콘 관련 코드 확인...")
for i, line in enumerate(content.split("\n"), 1):
    if any(k in line for k in ["wm_iconbitmap", "iconphoto", "_icon", "app_icon", "_MEIPASS"]):
        print(f"  L{i:4d}: {line}")

# 4. 아이콘 블록 교체 (문자열 단위, 단순)
print("\n[4/4] 아이콘 코드 정리 및 수정...")

lines = content.split("\n")
new_lines = []
skip_until_pass = False

for line in lines:
    stripped = line.strip()

    # 이전에 내가 삽입한 아이콘 블록 시작 감지
    if skip_until_pass:
        if stripped == "pass":
            skip_until_pass = False
        continue

    # 아이콘 관련 try 블록 감지 (내가 추가한 것)
    if stripped == "try:" and new_lines:
        # 다음 줄들을 미리 보지 않고, 이 try가 아이콘용인지 판단하기 어려우므로
        # 일단 그냥 포함
        new_lines.append(line)
        continue

    if any(k in line for k in ["wm_iconbitmap", "_icon_ref", "_icon_img",
                                 "app_icon.ico", "app_icon.png",
                                 "ImageTk", "iconphoto",
                                 "# --- 앱 아이콘", "# --- 아이콘"]):
        # 이 줄이 속한 try/except 블록 전체를 제거
        # 뒤로 돌아가서 try: 줄 제거
        while new_lines and new_lines[-1].strip() in ("try:", ""):
            new_lines.pop()
        skip_until_pass = True
        continue

    new_lines.append(line)

# self.resizable 다음에 깔끔한 아이콘 코드 삽입
ICON_BLOCK = """\
        try:
            from PIL import Image as _PILImg, ImageTk as _PILTk
            _icon_base = getattr(__import__('sys'), '_MEIPASS', __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
            _icon_path = __import__('os').path.join(_icon_base, 'app_icon.png')
            if __import__('os').path.exists(_icon_path):
                _icon_img = _PILTk.PhotoImage(_PILImg.open(_icon_path))
                self.iconphoto(True, _icon_img)
                self._keep_icon = _icon_img
        except Exception:
            pass"""

result_lines = []
icon_inserted = False
for line in new_lines:
    result_lines.append(line)
    if "self.resizable" in line and not icon_inserted:
        result_lines.append(ICON_BLOCK)
        icon_inserted = True

if not icon_inserted:
    print("  !! self.resizable 못 찾음 - 아이콘 코드 미삽입")
else:
    print("  OK - 아이콘 코드 삽입 완료")

new_content = "\n".join(result_lines)

# 문법 최종 검증
print("\n  최종 문법 검증...")
try:
    compile(new_content, "main.py", "exec")
    print("  문법 OK - 업로드 진행")
except SyntaxError as e:
    print(f"  !! 문법 오류: {e}")
    print("  업로드 중단 - 수동 확인 필요")
    input("아무 키나 누르면 종료됩니다...")
    exit()

# 업로드
encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
payload = {"message": "fix: main.py 복구 + iconphoto(PNG) 아이콘 적용", "content": encoded, "sha": main_sha}
_, status = gh_api("/contents/app_dist/main.py", method="PUT", data=payload)
print(f"  {'OK - 업로드 성공' if status in (200,201) else f'FAIL HTTP {status}'}")

print(f"\n빌드: https://github.com/{REPO}/actions")
print(f"릴리즈: https://github.com/{REPO}/releases")
input("\n아무 키나 누르면 종료됩니다...")
