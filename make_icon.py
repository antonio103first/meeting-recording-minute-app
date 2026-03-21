"""
새 앱 아이콘 생성 스크립트 — 마젠타 배경 + 흰색 문서 + 채팅 버블
실행: python make_icon.py
"""
from PIL import Image, ImageDraw
import os, sys

SIZE = 256

def rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + radius*2, y0 + radius*2], fill=fill)
    draw.ellipse([x1 - radius*2, y0, x1, y0 + radius*2], fill=fill)
    draw.ellipse([x0, y1 - radius*2, x0 + radius*2, y1], fill=fill)
    draw.ellipse([x1 - radius*2, y1 - radius*2, x1, y1], fill=fill)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 배경: 마젠타 (사용자 제공 이미지 색상)
BG_COLOR = (204, 0, 187, 255)
WHITE    = (255, 255, 255, 255)

# ── 배경 (둥근 사각형) ──
rounded_rect(draw, [0, 0, SIZE-1, SIZE-1], 40, BG_COLOR)

# ── 문서 본체 (상단 우측 모서리 접힘) ──
doc_x0, doc_y0 = 52, 38
doc_x1, doc_y1 = 178, 196
fold = 24

doc_pts = [
    (doc_x0,          doc_y0),
    (doc_x1 - fold,   doc_y0),
    (doc_x1,          doc_y0 + fold),
    (doc_x1,          doc_y1),
    (doc_x0,          doc_y1),
]
draw.polygon(doc_pts, fill=WHITE)

# 접힌 삼각형
fold_pts = [
    (doc_x1 - fold, doc_y0),
    (doc_x1,        doc_y0 + fold),
    (doc_x1 - fold, doc_y0 + fold),
]
draw.polygon(fold_pts, fill=(220, 200, 220, 255))

# ── 텍스트 줄 3개 ──
LINE_COLOR = (180, 100, 170, 255)
lx0 = doc_x0 + 16
lx1 = doc_x1 - 20
for i, y in enumerate([108, 128, 148]):
    x_end = lx1 if i < 2 else int(lx0 + (lx1 - lx0) * 0.65)
    draw.rounded_rectangle([lx0, y, x_end, y + 9], radius=4, fill=LINE_COLOR)

# ── 채팅 버블 (우하단 원 + 점 3개) ──
bx, by, br = 178, 186, 32
draw.ellipse([bx - br, by - br, bx + br, by + br], fill=WHITE)

dot_r = 4
for dx in [-10, 0, 10]:
    draw.ellipse([bx+dx-dot_r, by-dot_r, bx+dx+dot_r, by+dot_r], fill=BG_COLOR)

# ── 저장 ──
base = os.path.dirname(os.path.abspath(__file__))
png_path = os.path.join(base, "app_icon.png")
ico_path = os.path.join(base, "app_icon.ico")

img.save(png_path, "PNG")
print("PNG saved: " + png_path)

sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
icons = [img.resize(s, Image.LANCZOS) for s in sizes]
icons[0].save(ico_path, format="ICO", sizes=sizes, append_images=icons[1:])
print("ICO saved: " + ico_path)
print("Icon generation complete.")
