"""현재 GitHub main.py 상태 진단"""
import base64, urllib.request, urllib.error, json

REPO  = "antonio103first/meeting-recording-minute-app"
TOKEN = "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"

req = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/contents/app_dist/main.py",
    headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())

content = base64.b64decode(d["content"]).decode("utf-8")

# 문법 검사
try:
    compile(content, "main.py", "exec")
    print("문법: OK")
except SyntaxError as e:
    print(f"문법 오류: {e}")

# 아이콘 관련 줄 출력
print("\n=== 아이콘 관련 코드 ===")
for i, line in enumerate(content.split("\n"), 1):
    if any(k in line for k in ["icon", "wm_icon", "iconphoto", "_MEIPASS", "PIL", "ImageTk"]):
        print(f"L{i:4d}: {line}")

# 전체 저장
with open("main_current.py", "w", encoding="utf-8") as f:
    f.write(content)
print("\nmain_current.py 저장 완료 - 내용 확인 가능")
input("아무 키나 누르면 종료됩니다...")
