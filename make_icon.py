"""
App icon generator for GitHub Actions build.
Loads app_icon.png (committed to repo) and generates app_icon.ico.
Run setup_icon.py once locally to set the source icon.
"""
import os
from PIL import Image

base     = os.path.dirname(os.path.abspath(__file__))
png_path = os.path.join(base, "app_icon.png")
ico_path = os.path.join(base, "app_icon.ico")

if not os.path.exists(png_path):
    raise FileNotFoundError("app_icon.png not found. Run setup_icon.py first.")

img = Image.open(png_path).convert("RGB")  # 투명도 제거 — Windows ICO 호환성
s256 = img.resize((256,256), Image.LANCZOS)
s128 = img.resize((128,128), Image.LANCZOS)
s64  = img.resize((64,64),   Image.LANCZOS)
s48  = img.resize((48,48),   Image.LANCZOS)
s32  = img.resize((32,32),   Image.LANCZOS)
s16  = img.resize((16,16),   Image.LANCZOS)

s256.save(ico_path, format="ICO", append_images=[s128, s64, s48, s32, s16])
print("PNG loaded: " + png_path)
print("ICO saved: " + ico_path)
print("Icon generation complete.")
