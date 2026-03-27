#!/usr/bin/env python3
"""
K-run 회의녹음요약 v3.0 — 설치 및 사용 매뉴얼 PDF 생성기
실행: python generate_manual_pdf.py
출력: 회의녹음요약_매뉴얼_v3.0.pdf

필요 패키지: pip install fpdf2
"""

import os
import sys
import urllib.request

# ── 패키지 설치 확인 ────────────────────────────────────────────
try:
    from fpdf import FPDF
except ImportError:
    print("fpdf2 설치 중...")
    os.system(f"{sys.executable} -m pip install fpdf2")
    from fpdf import FPDF

# ── 폰트 설정 ────────────────────────────────────────────────────
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    r"/usr/share/fonts/nanum/NanumGothic.ttf",
    os.path.join(os.path.dirname(__file__), "NanumGothic.ttf"),
    os.path.join(os.path.dirname(__file__), "malgun.ttf"),
]
FONT_BOLD_CANDIDATES = [
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    r"/usr/share/fonts/nanum/NanumGothicBold.ttf",
    os.path.join(os.path.dirname(__file__), "NanumGothicBold.ttf"),
]

def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    # NanumGothic 다운로드
    dl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NanumGothic.ttf")
    print(f"한국어 폰트를 찾을 수 없어 NanumGothic을 다운로드합니다: {dl_path}")
    url = "https://github.com/naver/nanumfont/raw/master/NanumGothic.ttf"
    try:
        urllib.request.urlretrieve(url, dl_path)
        return dl_path
    except Exception as e:
        print(f"폰트 다운로드 실패: {e}")
        return None

def find_font_bold():
    for p in FONT_BOLD_CANDIDATES:
        if os.path.exists(p):
            return p
    dl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NanumGothicBold.ttf")
    url = "https://github.com/naver/nanumfont/raw/master/NanumGothicBold.ttf"
    try:
        urllib.request.urlretrieve(url, dl_path)
        return dl_path
    except:
        return None

# ── 색상 정의 ────────────────────────────────────────────────────
NAVY    = (27, 58, 92)      # #1B3A5C
DARK_BG = (13, 27, 46)      # #0D1B2E cover background
BLUE    = (45, 108, 180)    # #2D6CB4
LBLUE   = (230, 240, 249)   # #E6F0F9
WHITE   = (255, 255, 255)
BLACK   = (30, 30, 30)
GRAY    = (100, 100, 100)
LGRAY   = (240, 240, 240)
DGRAY   = (45, 45, 45)      # code bg

INFO_BG     = (231, 244, 255)
INFO_BR     = (183, 216, 250)
WARN_BG     = (255, 248, 225)
WARN_BR     = (255, 214, 0)
SUCC_BG     = (240, 250, 240)
SUCC_BR     = (100, 187, 100)
ERR_BG      = (255, 240, 240)
ERR_BR      = (255, 107, 107)

# ── 페이지 크기 ──────────────────────────────────────────────────
W, H = 210, 297  # A4 mm


class ManualPDF(FPDF):
    def __init__(self, font_path, font_bold_path):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.font_path = font_path
        self.font_bold_path = font_bold_path or font_path
        self.set_auto_page_break(auto=True, margin=20)
        self.add_font('KR', '', font_path)
        self.add_font('KR', 'B', self.font_bold_path)
        self._page_type = 'content'  # 'cover', 'divider', 'content'

    def header(self):
        pass  # 수동으로 그림

    def footer(self):
        if self._page_type == 'content' and self.page_no() > 2:
            self.set_y(-12)
            self.set_font('KR', '', 8)
            self.set_text_color(*GRAY)
            self.cell(0, 5, 'K-run 회의녹음요약 — 설치 및 사용 매뉴얼', align='C')
            self.set_xy(W - 20, -12)
            self.cell(15, 5, str(self.page_no() - 2), align='R')
            self.set_text_color(*BLACK)

    # ── 색상 헬퍼 ──────────────────────────────────────────────
    def _rgb(self, rgb):
        return rgb[0], rgb[1], rgb[2]

    def fill_rect(self, x, y, w, h, color):
        self.set_fill_color(*color)
        self.rect(x, y, w, h, 'F')

    # ── 커버 페이지 ────────────────────────────────────────────
    def cover_page(self):
        self._page_type = 'cover'
        self.add_page()
        # 배경
        self.fill_rect(0, 0, W, H, DARK_BG)
        # 배경 그라데이션 효과 (하단 약간 밝게)
        for i in range(20):
            alpha = i / 20 * 15
            self.set_fill_color(27 + int(alpha), 58 + int(alpha*0.5), 92 + int(alpha))
            self.rect(0, H - 80 + i * 4, W, 4, 'F')

        # INSTALLATION & USER GUIDE 뱃지
        bw, bh = 100, 10
        bx, by = (W - bw) / 2, H * 0.28
        self.set_draw_color(*WHITE)
        self.set_line_width(0.3)
        self.rect(bx, by, bw, bh)
        self.set_font('KR', '', 7)
        self.set_text_color(*WHITE)
        self.set_xy(bx, by + 1.5)
        self.cell(bw, 7, 'INSTALLATION & USER GUIDE', align='C')

        # 메인 타이틀
        self.set_font('KR', 'B', 32)
        self.set_text_color(*WHITE)
        self.set_xy(0, by + 18)
        self.cell(W, 20, 'K-run', align='C')

        self.set_font('KR', 'B', 36)
        self.set_xy(0, by + 35)
        self.cell(W, 22, '회의녹음요약', align='C')

        # 서브타이틀
        self.set_font('KR', '', 14)
        self.set_xy(0, by + 60)
        self.cell(W, 10, '설치 및 사용 매뉴얼', align='C')

        # 구분선
        self.set_draw_color(70, 120, 180)
        self.set_line_width(1.0)
        lx = W * 0.35
        self.line(lx, by + 74, W - lx, by + 74)

        # 태그라인
        self.set_font('KR', '', 10)
        self.set_text_color(180, 210, 240)
        self.set_xy(0, by + 80)
        self.cell(W, 7, '코딩을 몰라도 괜찮습니다.', align='C')
        self.set_xy(0, by + 87)
        self.cell(W, 7, '이 매뉴얼을 순서대로 따라하면', align='C')
        self.set_xy(0, by + 94)
        self.cell(W, 7, '회의를 자동으로 텍스트와 요약으로 만들 수 있습니다.', align='C')

        # PART 버튼
        btn_y = H * 0.78
        btn_h = 20
        # PART 1
        bx1 = W * 0.2
        self.set_draw_color(*WHITE)
        self.set_fill_color(30, 60, 100)
        self.set_line_width(0.5)
        self.rect(bx1, btn_y, 55, btn_h, 'FD')
        self.set_font('KR', 'B', 8)
        self.set_text_color(*WHITE)
        self.set_xy(bx1, btn_y + 3)
        self.cell(55, 5, 'PART 1', align='C')
        self.set_font('KR', '', 9)
        self.set_xy(bx1, btn_y + 9)
        self.cell(55, 6, '설치 가이드', align='C')
        # PART 2
        bx2 = W * 0.57
        self.rect(bx2, btn_y, 55, btn_h, 'FD')
        self.set_font('KR', 'B', 8)
        self.set_xy(bx2, btn_y + 3)
        self.cell(55, 5, 'PART 2', align='C')
        self.set_font('KR', '', 9)
        self.set_xy(bx2, btn_y + 9)
        self.cell(55, 6, '사용 가이드', align='C')

        # 푸터
        self.set_font('KR', '', 8)
        self.set_text_color(120, 150, 180)
        self.set_xy(0, H - 15)
        self.cell(W, 6, '케이런벤처스 전용 앱  ·  2026', align='C')

    # ── 목차 페이지 ────────────────────────────────────────────
    def toc_page(self):
        self._page_type = 'content'
        self.add_page()
        # 타이틀
        self.set_font('KR', 'B', 28)
        self.set_text_color(*NAVY)
        self.set_xy(20, 20)
        self.cell(0, 14, '목  차', align='L')
        # 파란 구분선
        self.set_draw_color(*BLUE)
        self.set_line_width(1.0)
        self.line(20, 37, W - 20, 37)

        def toc_part(title, y):
            self.fill_rect(20, y, W - 40, 10, LBLUE)
            self.set_font('KR', 'B', 10)
            self.set_text_color(*NAVY)
            self.set_xy(22, y + 1.5)
            self.cell(0, 7, title)

        def toc_entry(num, title, page, y):
            self.set_font('KR', '', 9.5)
            self.set_text_color(*BLACK)
            self.set_xy(30, y)
            self.cell(120, 7, f'  {num}  {title}')
            self.set_xy(W - 35, y)
            self.set_font('KR', 'B', 9.5)
            self.set_text_color(*BLUE)
            self.cell(15, 7, str(page), align='R')
            # 점선
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.2)
            self.set_dash_pattern(dash=1, gap=1)
            self.line(90, y + 5, W - 36, y + 5)
            self.set_dash_pattern()
            self.set_text_color(*BLACK)

        y = 42
        toc_part('PART 1  ·  설치 가이드', y); y += 13
        toc_entry('1-1.', '시작 전 준비물 체크리스트', 3, y); y += 8
        toc_entry('1-2.', 'STEP 1 — 앱 다운로드 및 설치', 4, y); y += 8
        toc_entry('1-3.', 'STEP 2 — CLOVA Speech API 설정', 5, y); y += 8
        toc_entry('1-4.', 'STEP 3 — Gemini API 설정', 6, y); y += 8
        toc_entry('1-5.', 'STEP 4 — Google Drive 연동 (선택)', 7, y); y += 8
        toc_entry('1-6.', '설치 완료 확인', 8, y); y += 8
        toc_entry('1-7.', '자주 묻는 질문 (설치편)', 9, y); y += 15

        toc_part('PART 2  ·  사용 가이드', y); y += 13
        toc_entry('2-1.', '녹음 및 변환 방법', 11, y); y += 8
        toc_entry('2-2.', 'STT 파일로 즉시 요약 (영역 B)', 12, y); y += 8
        toc_entry('2-3.', '요약 방식 선택하기', 13, y); y += 8
        toc_entry('2-4.', '회의목록 조회 및 관리', 14, y); y += 8
        toc_entry('2-5.', 'STT 엔진 비교 및 권장 조합', 15, y); y += 8
        toc_entry('2-6.', '자주 묻는 질문 (사용편)', 16, y); y += 15

        # 알림 박스
        self.info_box(20, y, W - 40, 14,
            '※ 이 앱은 Windows 64-bit PC에서 실행됩니다. 설치 과정에서 CLOVA Speech API 키(유료)와 '
            'Gemini API 키(무료)가 필요합니다.', INFO_BG, INFO_BR)

    # ── PART 구분 페이지 ───────────────────────────────────────
    def part_divider(self, part_num, title, subtitle):
        self._page_type = 'divider'
        self.add_page()
        self.fill_rect(0, 0, W, H, DARK_BG)
        # 세로 중앙 약간 위
        cy = H * 0.45
        self.set_font('KR', '', 10)
        self.set_text_color(140, 180, 220)
        self.set_xy(20, cy - 20)
        self.cell(0, 8, f'PART {part_num}')
        self.set_font('KR', 'B', 30)
        self.set_text_color(*WHITE)
        self.set_xy(20, cy - 10)
        self.cell(0, 18, title)
        self.set_font('KR', '', 11)
        self.set_text_color(170, 200, 230)
        self.set_xy(20, cy + 12)
        self.cell(0, 8, subtitle)

    # ── 섹션 헤더 (파란 왼쪽 보더) ────────────────────────────
    def section_header(self, title):
        self.set_fill_color(*LBLUE)
        self.rect(20, self.get_y(), W - 40, 11, 'F')
        self.set_fill_color(*BLUE)
        self.rect(20, self.get_y(), 3, 11, 'F')
        self.set_font('KR', 'B', 12)
        self.set_text_color(*NAVY)
        self.set_xy(26, self.get_y() + 1.5)
        self.cell(0, 8, title)
        self.ln(14)

    # ── 스텝 헤더 (네이비 배너 + 숫자박스) ────────────────────
    def step_header(self, num, title, subtitle=''):
        self.fill_rect(20, self.get_y(), W - 40, 18, NAVY)
        # 숫자 박스
        self.set_fill_color(*BLUE)
        self.rect(20, self.get_y(), 18, 18, 'F')
        self.set_font('KR', 'B', 14)
        self.set_text_color(*WHITE)
        self.set_xy(20, self.get_y() + 2)
        self.cell(18, 14, str(num), align='C')
        # 타이틀
        self.set_font('KR', 'B', 11)
        self.set_xy(42, self.get_y() - 14)
        self.cell(0, 8, title)
        if subtitle:
            self.set_font('KR', '', 9)
            self.set_text_color(170, 200, 230)
            self.set_xy(42, self.get_y() + 8)
            self.cell(0, 6, subtitle)
        self.set_text_color(*BLACK)
        self.ln(22)

    # ── 서브섹션 헤더 (원문자) ─────────────────────────────────
    def sub_header(self, num, title):
        self.set_font('KR', 'B', 10)
        self.set_text_color(*BLUE)
        self.set_x(20)
        self.cell(0, 8, f'{"①②③④⑤"[num-1]}  {title}')
        self.set_text_color(*BLACK)
        self.ln(9)

    # ── 본문 텍스트 ────────────────────────────────────────────
    def body_text(self, text, indent=20):
        self.set_font('KR', '', 9.5)
        self.set_text_color(*BLACK)
        self.set_x(indent)
        self.multi_cell(W - indent - 20, 6, text)
        self.ln(2)

    # ── 번호 목록 ──────────────────────────────────────────────
    def numbered_list(self, items, indent=25):
        self.set_font('KR', '', 9.5)
        self.set_text_color(*BLACK)
        for i, item in enumerate(items, 1):
            self.set_x(indent)
            # 번호
            self.set_font('KR', 'B', 9.5)
            self.cell(7, 6.5, f'{i}.')
            self.set_font('KR', '', 9.5)
            self.multi_cell(W - indent - 27, 6.5, item)
        self.ln(2)

    # ── 정보 박스 ──────────────────────────────────────────────
    def info_box(self, x, y, w, h_min, text, bg, border, bold_prefix=''):
        # 높이 계산
        self.set_font('KR', '', 9)
        lines = self.get_string_width(text) / (w - 12)
        box_h = max(h_min, (lines + 1) * 6.5 + 8)
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        self.set_line_width(0.5)
        self.rect(x, y, w, box_h, 'FD')
        # 왼쪽 강조 선
        self.set_fill_color(*border)
        self.rect(x, y, 3, box_h, 'F')
        self.set_font('KR', '', 9)
        self.set_text_color(*BLACK)
        self.set_xy(x + 6, y + 4)
        self.multi_cell(w - 10, 6, text)
        self.set_y(y + box_h + 3)

    def info_box_auto(self, text, bg=INFO_BG, border=INFO_BR):
        self.info_box(20, self.get_y(), W - 40, 12, text, bg, border)

    # ── 코드 블록 ──────────────────────────────────────────────
    def code_block(self, text):
        self.set_fill_color(*DGRAY)
        lines = text.strip().split('\n')
        h = len(lines) * 6.5 + 9
        cy = self.get_y()
        self.rect(20, cy, W - 40, h, 'F')
        self.set_font('KR', '', 8.5)
        self.set_text_color(*WHITE)
        self.set_xy(26, cy + 4)
        for line in lines:
            self.set_x(26)
            self.cell(W - 46, 6.5, line)
            self.ln(6.5)
        self.set_text_color(*BLACK)
        self.set_font('KR', '', 9.5)
        self.ln(4)

    # ── 테이블 ─────────────────────────────────────────────────
    def draw_table(self, headers, rows, col_widths=None, indent=20):
        tw = W - indent * 2
        if col_widths is None:
            n = len(headers)
            col_widths = [tw / n] * n
        row_h = 7.5
        # 헤더
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font('KR', 'B', 8.5)
        x = indent
        y = self.get_y()
        for i, h_txt in enumerate(headers):
            self.set_xy(x, y)
            self.set_fill_color(*NAVY)
            self.rect(x, y, col_widths[i], row_h + 1, 'F')
            self.set_xy(x + 1, y + 1)
            self.cell(col_widths[i] - 2, row_h - 1, h_txt, align='C')
            x += col_widths[i]
        self.ln(row_h + 1)
        # 행
        self.set_font('KR', '', 8.5)
        self.set_text_color(*BLACK)
        for ri, row in enumerate(rows):
            bg = LGRAY if ri % 2 == 1 else WHITE
            self.set_fill_color(*bg)
            x = indent
            y = self.get_y()
            row_actual_h = row_h
            # 높이 계산
            for ci, cell_txt in enumerate(row):
                lines_n = max(1, int(self.get_string_width(str(cell_txt)) / (col_widths[ci] - 4)) + 1)
                row_actual_h = max(row_actual_h, lines_n * 5.5 + 2)
            for ci, cell_txt in enumerate(row):
                self.set_xy(x, y)
                self.rect(x, y, col_widths[ci], row_actual_h + 1, 'F')
                # 테두리
                self.set_draw_color(200, 200, 200)
                self.set_line_width(0.2)
                self.rect(x, y, col_widths[ci], row_actual_h + 1)
                self.set_xy(x + 2, y + 1.5)
                self.multi_cell(col_widths[ci] - 4, 5.5, str(cell_txt))
                x += col_widths[ci]
            self.set_y(y + row_actual_h + 1)
        self.ln(4)

    # ── 체크리스트 박스 ────────────────────────────────────────
    def checklist_box(self, title, items, bg=INFO_BG, border=INFO_BR):
        box_h = 10 + len(items) * 8 + 4
        cy = self.get_y()
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        self.set_line_width(0.5)
        self.rect(20, cy, W - 40, box_h, 'FD')
        self.set_fill_color(*border)
        self.rect(20, cy, 3, box_h, 'F')
        self.set_font('KR', 'B', 9.5)
        self.set_text_color(*NAVY)
        self.set_xy(26, cy + 3)
        self.cell(0, 6, title)
        self.set_font('KR', '', 9.5)
        self.set_text_color(*BLACK)
        for item in items:
            self.set_xy(30, self.get_y() + 2)
            self.cell(0, 6, f'□  {item}')
            self.ln(7)
        self.set_y(cy + box_h + 4)

    # ── FAQ 항목 ────────────────────────────────────────────────
    def faq_item(self, question, answer):
        self.set_font('KR', 'B', 9.5)
        self.set_text_color(*BLUE)
        self.set_x(20)
        self.cell(0, 7, f'Q.  {question}')
        self.ln(8)
        self.set_font('KR', '', 9.5)
        self.set_text_color(*BLACK)
        self.set_x(20)
        self.multi_cell(W - 40, 6.5, f'A.  {answer}')
        self.ln(2)
        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.3)
        self.line(20, self.get_y(), W - 20, self.get_y())
        self.ln(5)


# ═══════════════════════════════════════════════════════════════════
# 콘텐츠 생성 함수
# ═══════════════════════════════════════════════════════════════════

def build_pdf(font_path, font_bold_path):
    pdf = ManualPDF(font_path, font_bold_path)

    # ── 커버 ───────────────────────────────────────────────────
    pdf.cover_page()

    # ── 목차 ───────────────────────────────────────────────────
    pdf.toc_page()

    # ══════════════════════════════════════════════════════════
    # PART 1: 설치 가이드
    # ══════════════════════════════════════════════════════════
    pdf.part_divider(1, '설치 가이드', '처음 한 번만 따라하면 됩니다. 약 20~30분 소요됩니다.')
    pdf._page_type = 'content'

    # ── 1-1 준비물 체크리스트 ──────────────────────────────────
    pdf.add_page()
    pdf.section_header('1-1.  시작 전 준비물 체크리스트')
    pdf.body_text('아래 두 가지 API가 필요합니다. 미리 준비해두면 설치가 더 빠릅니다.')
    pdf.draw_table(
        ['서비스', '용도', '웹사이트', '비용'],
        [
            ['CLOVA Speech API', 'STT 음성 변환 (권장)', 'console.ncloud.com', '유료 (종량제)'],
            ['Gemini API', '회의록 요약 (필수)', 'aistudio.google.com', '무료'],
            ['ChatGPT API', 'OpenAI STT/요약 (선택)', 'platform.openai.com', '유료 (선택)'],
            ['Google Drive', '파일 자동 업로드 (선택)', 'drive.google.com', '무료'],
        ],
        col_widths=[42, 50, 52, 26]
    )
    pdf.ln(3)
    pdf.checklist_box('준비 체크리스트', [
        'CLOVA Speech API 키 발급 완료 (Invoke URL + Secret Key)',
        'Gemini API 키 발급 완료',
        'Windows 64-bit PC 확인',
        '인터넷 연결 확인',
    ])

    # ── 1-2 앱 다운로드 ────────────────────────────────────────
    pdf.add_page()
    pdf.step_header(1, '1-2.  STEP 1 — 앱 다운로드 및 설치', 'GitHub에서 앱 파일을 받아옵니다')
    pdf.sub_header(1, '다운로드 링크')
    pdf.body_text('아래 링크에서 로그인 없이 누구나 다운로드할 수 있습니다.')
    pdf.code_block('https://github.com/antonio103first/meeting-recording-minute-app/releases/latest')
    pdf.ln(2)
    pdf.draw_table(
        ['파일', '용도'],
        [
            ['회의녹음요약.exe', '앱 실행 파일 (더블클릭으로 바로 실행)'],
            ['KRunVentures_인증서.cer', 'Windows SmartScreen 경고 해제용 (최초 1회 설치)'],
        ],
        col_widths=[60, 110]
    )
    pdf.sub_header(2, 'SmartScreen 경고 해제')
    pdf.body_text('방법 A — 인증서 설치 (권장, 한 번만 설치하면 이후 경고 없음)')
    pdf.numbered_list([
        'KRunVentures_인증서.cer 더블클릭',
        '인증서 설치 → 로컬 컴퓨터 선택 → 다음',
        '모든 인증서를 다음 저장소에 저장 → 찾아보기 → 신뢰할 수 있는 게시자 선택',
        '다음 → 마침',
    ])
    pdf.body_text('방법 B — 즉시 실행 (인증서 설치 없이)')
    pdf.numbered_list([
        '회의녹음요약.exe 우클릭 → 속성 → 하단 "차단 해제" 체크 → 확인',
        '또는: 빨간 경고 화면에서 "추가 정보" 클릭 → "실행" 버튼 클릭',
    ])

    # ── 1-3 CLOVA Speech ───────────────────────────────────────
    pdf.add_page()
    pdf.step_header(2, '1-3.  STEP 2 — CLOVA Speech API 설정', '한국어 STT 변환 엔진 (권장)')
    pdf.sub_header(1, 'API 키 발급')
    pdf.numbered_list([
        'console.ncloud.com 접속 후 로그인',
        'AI Service → CLOVA Speech 클릭',
        '도메인(앱) 선택 → 설정 탭 → 연동 정보 탭',
        'Invoke URL 및 Secret Key 복사',
    ])
    pdf.info_box_auto(
        '[주의]  NAVER 계정 이메일/비밀번호가 아닌 Invoke URL과 Secret Key를 입력해야 합니다.',
        WARN_BG, WARN_BR
    )
    pdf.sub_header(2, '앱에 입력')
    pdf.numbered_list([
        '앱 실행 → 설정 탭 클릭',
        'CLOVA Speech API 설정 영역에 Invoke URL, Secret Key 입력',
        '저장 버튼 클릭',
        '연결 테스트 버튼으로 [OK] 확인',
        '기본 STT 엔진을 CLOVA Speech (권장)으로 선택',
    ])
    pdf.info_box_auto(
        '[완료]  연결 테스트에서 "연결 성공"이 표시되면 설정 완료입니다.',
        SUCC_BG, SUCC_BR
    )

    # ── 1-4 Gemini API ─────────────────────────────────────────
    pdf.add_page()
    pdf.step_header(3, '1-4.  STEP 3 — Gemini API 설정', '회의록 요약 엔진 (필수)')
    pdf.sub_header(1, 'API 키 발급')
    pdf.numbered_list([
        'aistudio.google.com/apikey 접속 (Google 계정 필요)',
        'Create API Key 클릭',
        '생성된 API 키 복사',
    ])
    pdf.info_box_auto(
        '[안내]  Gemini API는 무료 플랜으로도 일반적인 회의 요약에 충분합니다. '
        'STT에 CLOVA를 사용하더라도 Gemini 키는 반드시 설정해야 합니다.',
        INFO_BG, INFO_BR
    )
    pdf.sub_header(2, '앱에 입력')
    pdf.numbered_list([
        '설정 탭 → Gemini API 설정 영역',
        'API 키 입력 → 저장',
        '연결 테스트 버튼으로 [OK] 확인',
    ])

    # ── 1-5 Google Drive ───────────────────────────────────────
    pdf.add_page()
    pdf.step_header(4, '1-5.  STEP 4 — Google Drive 연동', '선택사항 — 요약 파일 자동 업로드')
    pdf.body_text('설정 시 요약 완료 후 자동으로 Google Drive에 업로드됩니다. 건너뛰어도 됩니다.')
    pdf.sub_header(1, 'OAuth 설정')
    pdf.numbered_list([
        'console.cloud.google.com → 새 프로젝트 생성',
        'API 및 서비스 → 라이브러리 → Google Drive API 활성화',
        '사용자 인증 정보 → OAuth 클라이언트 ID 생성 (애플리케이션 유형: 데스크톱 앱)',
        'JSON 파일 다운로드 → 로컬에 보관',
    ])
    pdf.sub_header(2, '앱에 연동')
    pdf.numbered_list([
        '설정 탭 → Google Drive 설정 → JSON 파일 선택 → 등록',
        '[Google 인증] 버튼 클릭 → 브라우저에서 계정 로그인 및 권한 승인',
        '[두 폴더 한번에 생성] 버튼 클릭 → 폴더 자동 생성 및 ID 저장',
    ])
    pdf.info_box_auto(
        '[안내]  Google Drive 연동은 선택사항입니다. 로컬 PC에만 저장해도 모든 기능을 사용할 수 있습니다.',
        INFO_BG, INFO_BR
    )

    # ── 1-6 설치 완료 ──────────────────────────────────────────
    pdf.add_page()
    pdf.section_header('1-6.  설치 완료 확인')
    pdf.checklist_box('설치 완료 체크리스트', [
        '앱이 정상 실행된다',
        'CLOVA Speech 연결 테스트 [OK] 확인',
        'Gemini API 연결 테스트 [OK] 확인',
        '설정 탭에서 STT 엔진이 CLOVA Speech로 선택됨',
    ], SUCC_BG, SUCC_BR)
    pdf.ln(4)
    # 문제 해결 표
    pdf.set_font('KR', 'B', 10)
    pdf.set_text_color(*ERR_BR)
    pdf.set_x(20)
    pdf.cell(0, 7, '[!]  문제가 발생했다면:')
    pdf.ln(8)
    pdf.set_text_color(*BLACK)
    pdf.draw_table(
        ['증상', '원인', '해결'],
        [
            ['"API 키를 입력해주세요"', '설정 미완료', '설정 탭에서 해당 API 키 입력 후 저장'],
            ['CLOVA 연결 테스트 실패 (401)', 'Secret Key 오입력', 'NAVER Console → 연동 정보의 Secret Key 사용'],
            ['CLOVA 연결 테스트 실패 (403)', '서비스 미신청', 'NAVER Cloud Console에서 CLOVA Speech 신청'],
            ['Gemini 타임아웃 반복', '긴 파일 처리 한계', 'STT 엔진을 CLOVA로 전환'],
            ['앱 실행 차단 (SmartScreen)', '서명 미인식', '인증서 설치 또는 차단 해제 (1-2 참고)'],
        ],
        col_widths=[52, 44, 74]
    )

    # ── 1-7 FAQ 설치편 ─────────────────────────────────────────
    pdf.add_page()
    pdf.section_header('1-7.  자주 묻는 질문 (설치편)')
    pdf.faq_item('회사 밖에서도 사용할 수 있나요?',
        '네, 인터넷이 연결된 환경이라면 어디서든 사용 가능합니다. '
        'Google Drive 연동 기능도 외부에서 정상 작동합니다.')
    pdf.faq_item('ChatGPT API도 반드시 설정해야 하나요?',
        'ChatGPT API는 선택사항입니다. CLOVA Speech(STT) + Gemini(요약) 조합으로 '
        '대부분의 사용 사례를 충분히 처리할 수 있습니다.')
    pdf.faq_item('API 키는 어디에 저장되나요?',
        'API 키는 사용자 PC의 C:\\Users\\{사용자}\\회의녹음요약_데이터\\config.json 파일에 로컬 저장됩니다. '
        'PC 재설치 후에는 이 파일을 백업해두면 설정을 그대로 복원할 수 있습니다.')
    pdf.faq_item('앱 업데이트는 어떻게 하나요?',
        'GitHub Release 페이지(github.com/antonio103first/meeting-recording-minute-app/releases)에서 '
        '최신 exe를 다운로드하여 기존 파일을 교체하면 됩니다. 설정 파일은 유지됩니다.')

    # ══════════════════════════════════════════════════════════
    # PART 2: 사용 가이드
    # ══════════════════════════════════════════════════════════
    pdf.part_divider(2, '사용 가이드', '회의를 시작하면 자동으로 기록됩니다')
    pdf._page_type = 'content'

    # ── 2-1 녹음 및 변환 ──────────────────────────────────────
    pdf.add_page()
    pdf.section_header('2-1.  녹음 및 변환 방법')
    pdf.sub_header(1, '음성 입력')
    pdf.body_text('• 실시간 녹음: 마이크 선택 → [녹음 시작] → [중지] (MP3 자동 저장)\n'
                  '• 기존 파일: [파일 선택] → MP3, WAV, M4A, MP4, OGG, FLAC 지원')
    pdf.sub_header(2, '화자 수 설정')
    pdf.body_text('변환 전 실제 참석자 수를 설정합니다 (1~8명 또는 자동 감지).')
    pdf.sub_header(3, '변환 시작')
    pdf.body_text('[변환 시작] 버튼 클릭 → 설정에서 지정한 STT 엔진과 요약 방식이 자동 적용됩니다.')
    pdf.ln(2)
    pdf.code_block(
        'STT 변환 (진행률 표시)\n'
        '     ↓\n'
        '요약 생성 중...\n'
        '     ↓\n'
        '파일명 입력\n'
        '     ↓\n'
        '로컬 저장 + Drive 업로드 (설정 시)'
    )
    pdf.info_box_auto(
        '[안내]  기본 STT 엔진 및 요약 방식은 설정 탭 → 기본 요약 방식에서 미리 지정하세요.',
        INFO_BG, INFO_BR
    )

    # ── 2-2 STT 파일로 즉시 요약 ─────────────────────────────
    pdf.add_page()
    pdf.section_header('2-2.  STT 파일로 즉시 요약 (영역 B)')
    pdf.body_text('STT 변환을 건너뛰고 기존 .txt 파일로 바로 요약할 수 있습니다.')
    pdf.numbered_list([
        '[STT 파일 선택] 버튼 클릭 → .txt 파일 선택',
        '(선택) 커스텀 프롬프트 입력란에 특별 지시사항 입력',
        '[회의록 변환] 버튼 클릭',
    ])
    pdf.info_box_auto(
        '[안내]  이미 STT 변환된 텍스트 파일이 있거나, 직접 작성한 회의 메모를 AI로 요약할 때 유용합니다.',
        INFO_BG, INFO_BR
    )

    # ── 2-3 요약 방식 ─────────────────────────────────────────
    pdf.add_page()
    pdf.section_header('2-3.  요약 방식 선택하기')
    pdf.body_text('설정 탭 → 기본 요약 방식에서 5가지 방식 중 선택합니다.')
    pdf.draw_table(
        ['방식', '특징 및 적합한 상황'],
        [
            ['화자 중심', '발화자별로 발언 내용을 정리 — 누가 무슨 말을 했는지 추적할 때'],
            ['주제 중심', '논의된 주제별로 분류 — 여러 안건을 다룬 회의에 적합'],
            ['흐름 중심', '회의 진행 순서대로 서술 — 회의 전체 맥락을 파악할 때'],
            ['결정사항 중심', '결정된 사항과 액션 아이템 중심 — 실무 팔로업에 최적'],
            ['커스텀', '직접 입력한 프롬프트로 요약 — 특수한 형식이나 언어 요구 시'],
        ],
        col_widths=[40, 130]
    )
    pdf.info_box_auto(
        '[안내]  커스텀 방식은 영역 A의 변환 전 또는 영역 B의 커스텀 프롬프트 입력란에서 '
        '별도 지시사항을 직접 입력할 수 있습니다.',
        INFO_BG, INFO_BR
    )

    # ── 2-4 회의목록 ─────────────────────────────────────────
    pdf.add_page()
    pdf.section_header('2-4.  회의목록 조회 및 관리')
    pdf.body_text('저장된 모든 회의를 조회하고 다양한 작업을 수행합니다.\n목록에서 항목 선택 후 아래 버튼을 사용하세요.')
    pdf.draw_table(
        ['버튼', '기능'],
        [
            ['[보기]  전체보기', '전체 회의록 팝업 표시 + 파일 직접 열기'],
            ['[인쇄]  출력·인쇄', '연결된 로컬 프린터로 회의록 인쇄'],
            ['[수정]  화자이름', 'STT 결과의 [화자1], [화자2]를 실제 이름으로 변경'],
            ['[공유]  공유', '이메일 공유 또는 클립보드 복사'],
            ['[PDF]  PDF 저장', '회의록을 PDF 파일로 저장 (한글 지원)'],
            ['[삭제]  삭제', '목록에서 삭제 (원본 파일은 유지, DB에서만 제거)'],
        ],
        col_widths=[40, 130]
    )
    pdf.body_text('분리뷰 탭:')
    pdf.body_text('  • [요약] 회의록 요약 탭 — AI가 생성한 요약본 표시\n'
                  '  • [원문] STT 원문 탭 — 음성 인식 원본 텍스트 표시', indent=24)

    # ── 2-5 STT 엔진 비교 ────────────────────────────────────
    pdf.add_page()
    pdf.section_header('2-5.  STT 엔진 비교 및 권장 조합')
    pdf.draw_table(
        ['항목', 'CLOVA Speech (권장)', 'Gemini', 'ChatGPT (Whisper)'],
        [
            ['한국어 정확도', '★★★★★', '★★★★', '★★★★'],
            ['화자 구분', '[O] 지원', '[O] 지원', '[X] 미지원'],
            ['파일 크기 제한', '최대 1GB', '20MB (인라인)', '25MB'],
            ['장시간 처리', '제한 없음 [O]', '1시간 이내 권장', '30분 이내 권장'],
            ['비용', '유료 (종량제)', '무료 (한도 내)', '유료'],
        ],
        col_widths=[38, 47, 38, 47]
    )
    pdf.ln(3)
    pdf.set_font('KR', 'B', 10)
    pdf.set_text_color(*NAVY)
    pdf.set_x(20)
    pdf.cell(0, 7, '권장 조합')
    pdf.ln(9)
    pdf.set_text_color(*BLACK)
    pdf.draw_table(
        ['시나리오', 'STT 엔진', '요약 엔진'],
        [
            ['일반 회의 (30분 이하)', 'CLOVA Speech', 'Gemini'],
            ['장시간 회의 (1시간+)', 'CLOVA Speech', 'Claude'],
            ['다국어 혼용 회의', 'ChatGPT (Whisper)', 'GPT-4o'],
            ['비용 최소화', 'Gemini', 'Gemini'],
        ],
        col_widths=[65, 50, 55]
    )

    # ── 2-6 FAQ 사용편 ────────────────────────────────────────
    pdf.add_page()
    pdf.section_header('2-6.  자주 묻는 질문 (사용편)')
    pdf.faq_item('회의록이 저장되는 위치는 어디인가요?',
        '기본 저장 경로: ~/Documents/Meeting recording/회의록(요약)/\n'
        '설정 탭 → PC 저장 폴더 설정에서 MP3 파일, STT 변환본, 요약 파일 각각의 경로를 변경할 수 있습니다.')
    pdf.faq_item('화자 이름을 나중에 변경할 수 있나요?',
        '네, 회의목록 탭에서 해당 회의를 선택한 후 [수정] 화자이름 버튼을 클릭하면 '
        '[화자1], [화자2] 등을 실제 이름으로 언제든 변경할 수 있습니다.')
    pdf.faq_item('Google Drive 업로드가 안 됩니다.',
        '설정 탭 → Google Drive 설정에서 "미연결" 상태를 확인하세요. '
        '[Google 인증] 버튼을 클릭하여 재인증하면 해결됩니다.')
    pdf.faq_item('긴 회의 파일(1시간 이상)이 처리되지 않습니다.',
        'Gemini STT 엔진은 1시간 이상 파일에서 타임아웃이 발생할 수 있습니다. '
        '설정 탭에서 STT 엔진을 CLOVA Speech로 변경하면 시간 제한 없이 처리됩니다.')

    return pdf


# ═══════════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('=== K-run 회의녹음요약 v3.0 매뉴얼 PDF 생성 ===')

    font = find_font()
    if not font:
        print('ERROR: 한국어 폰트를 찾을 수 없습니다.')
        print('NanumGothic.ttf 또는 malgun.ttf를 이 스크립트와 같은 폴더에 넣어 주세요.')
        sys.exit(1)
    print(f'폰트: {font}')

    font_bold = find_font_bold() or font
    print(f'폰트(Bold): {font_bold}')

    pdf = build_pdf(font, font_bold)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '회의녹음요약_매뉴얼_v3.0.pdf')
    pdf.output(out_path)
    print(f'\n✅ PDF 생성 완료: {out_path}')
