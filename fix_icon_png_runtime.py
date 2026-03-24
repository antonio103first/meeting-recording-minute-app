"""
앱 실행 시 ICO 대신 PNG를 직접 사용하도록 main.py 수정
PNG는 색상 손실 없이 선명하게 표시됨
실행: python fix_icon_png_runtime.py
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
        "User-Agent": "fix_icon_png_runtime.py"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

# 현재 main.py 가져오기
print("[1/2] main.py 다운로드 중...")
data, _ = gh_api("/contents/app_dist/main.py")
main_sha = data["sha"]
main_content = base64.b64decode(data["content"]).decode("utf-8")

# 기존 아이콘 코드 교체: wm_iconbitmap(ICO) → iconphoto(PNG)
OLD_ICON_CODE = """        try:
            _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            _ico = os.path.join(_base, 'app_icon.ico')
            if os.path.exists(_ico):
                self.wm_iconbitmap(_ico)
        except Exception:
            pass"""

NEW_ICON_CODE = """        try:
            from PIL import Image, ImageTk
            _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            _png = os.path.join(_base, 'app_icon.png')
            if os.path.exists(_png):
                _img = ImageTk.PhotoImage(Image.open(_png))
                self.iconphoto(True, _img)
                self._icon_img = _img  # 참조 유지 (GC 방지)
        except Exception:
            pass"""

if OLD_ICON_CODE in main_content:
    new_content = main_content.replace(OLD_ICON_CODE, NEW_ICON_CODE)
    print("  OK - 아이콘 코드 교체 완료")
else:
    # 패턴이 다를 경우 wm_iconbitmap 라인만 찾아서 교체
    lines = main_content.split('\n')
    new_lines = []
    i = 0
    replaced = False
    while i < len(lines):
        if 'wm_iconbitmap' in lines[i] and not replaced:
            # 이 블록을 새 코드로 교체
            indent = '        '
            new_lines.append(f'{indent}try:')
            new_lines.append(f'{indent}    from PIL import Image, ImageTk')
            new_lines.append(f'{indent}    _base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))')
            new_lines.append(f'{indent}    _png = os.path.join(_base, "app_icon.png")')
            new_lines.append(f'{indent}    if os.path.exists(_png):')
            new_lines.append(f'{indent}        _img = ImageTk.PhotoImage(Image.open(_png))')
            new_lines.append(f'{indent}        self.iconphoto(True, _img)')
            new_lines.append(f'{indent}        self._icon_img = _img')
            new_lines.append(f'{indent}except Exception:')
            new_lines.append(f'{indent}    pass')
            replaced = True
            # 기존 try 블록 스킵
            while i < len(lines) and ('wm_iconbitmap' in lines[i] or
                  ('try' in lines[i] and i > 0) or
                  '_ico' in lines[i] or
                  '_MEIPASS' in lines[i]):
                i += 1
        else:
            new_lines.append(lines[i])
            i += 1
    new_content = '\n'.join(new_lines)
    if replaced:
        print("  OK - wm_iconbitmap 라인 교체 완료")
    else:
        print("  !! 아이콘 코드를 찾지 못했습니다. main.py를 확인하세요.")
        input("아무 키나 누르면 종료됩니다...")
        exit()

# main.py 업로드
print("\n[2/2] main.py 업로드 중...")
encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
payload = {
    "message": "fix: 앱 아이콘 PNG 직접 사용 (iconphoto) - ICO 색상 손실 해결",
    "content": encoded,
    "sha": main_sha
}
_, status = gh_api("/contents/app_dist/main.py", method="PUT", data=payload)
if status in (200, 201):
    print("  OK - main.py 업로드 성공!")
    print(f"\n빌드 자동 시작: https://github.com/{REPO}/actions")
    print(f"완료 후 다운로드: https://github.com/{REPO}/releases")
else:
    print(f"  FAIL HTTP {status}")

input("\n아무 키나 누르면 종료됩니다...")
