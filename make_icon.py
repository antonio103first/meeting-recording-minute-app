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

img   = Image.open(png_path).convert("RGBA")
sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
icons = [img.resize(s, Image.LANCZOS) for s in sizes]

icons[0].save(ico_path, format="ICO", sizes=sizes, append_images=icons[1:])
print("PNG loaded: " + png_path)
print("ICO saved: " + ico_path)
print("Icon generation complete.")
