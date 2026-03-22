import os, shutil

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
