#!/usr/bin/env python3
"""
K-run 회의녹음요약 v3.0 — 설치 및 사용 매뉴얼 PDF 생성기
실행: python generate_manual_pdf.py
출력: 회의녹음요약_매뉴얼_v3.0.pdf
"""
import os, sys, math, urllib.request

try:
    from fpdf import FPDF
except ImportError:
    os.system(f"{sys.executable} -m pip install fpdf2")
    from fpdf import FPDF

# ── 폰트 경로 ────────────────────────────────────────────────────
FONT_R = [r"C:\Windows\Fonts\malgun.ttf",
          "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
          os.path.join(os.path.dirname(__file__), "NanumGothic.ttf")]
FONT_B = [r"C:\Windows\Fonts\malgunbd.ttf",
          "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
          os.path.join(os.path.dirname(__file__), "NanumGothicBold.ttf")]

def find_font(candidates):
    for p in candidates:
        if p and os.path.exists(p):
            return p
    dl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NanumGothic.ttf")
    url = "https://github.com/naver/nanumfont/raw/master/NanumGothic.ttf"
    try: urllib.request.urlretrieve(url, dl); return dl
    except: return None

# ── 색상 ─────────────────────────────────────────────────────────
NAVY    = (27,  58,  92)
DARK_BG = (13,  27,  46)
BLUE    = (45, 108, 180)
LBLUE   = (232, 242, 252)
WHITE   = (255, 255, 255)
BLACK   = (30,  30,  30)
GRAY    = (110, 110, 110)
LGRAY   = (245, 245, 245)
DGRAY   = (45,  45,  45)

INFO_BG  = (232, 244, 255); INFO_BR  = (180, 215, 250)
WARN_BG  = (255, 249, 225); WARN_BR  = (255, 200,   0)
SUCC_BG  = (240, 251, 240); SUCC_BR  = ( 90, 185,  90)
ERR_BG   = (255, 241, 241); ERR_BR   = (220,  80,  80)

W, H = 210, 297   # A4 mm
L, R, B_MARGIN = 20, 20, 22


class PDF(FPDF):
    def __init__(self, fr, fb):
        super().__init__('P', 'mm', 'A4')
        self.set_auto_page_break(True, margin=B_MARGIN)
        self.add_font('KR', '',  fr)
        self.add_font('KR', 'B', fb)
        self._ptype = 'content'

    def footer(self):
        if self._ptype != 'content': return
        pg = self.page_no() - 2
        if pg < 1: return
        self.set_y(-12)
        self.set_font('KR', '', 7.5); self.set_text_color(*GRAY)
        self.cell(0, 5, 'K-run 회의녹음요약 — 설치 및 사용 매뉴얼', align='C')
        self.set_xy(W - R - 10, -12)
        self.cell(10, 5, str(pg), align='R')
        self.set_text_color(*BLACK)

    def _rect(self, x, y, w, h, color):
        self.set_fill_color(*color); self.rect(x, y, w, h, 'F')

    def _need(self, mm=30):
        if self.get_y() + mm > H - B_MARGIN - 5:
            self.add_page()

    # ── 커버 ───────────────────────────────────────────────────
    def cover(self):
        self._ptype = 'cover'; self.add_page()
        self._rect(0, 0, W, H, DARK_BG)
        bw, by = 106, H * 0.30
        bx = (W - bw) / 2
        self.set_draw_color(100, 150, 200); self.set_line_width(0.4)
        self.rect(bx, by, bw, 9)
        self.set_font('KR', '', 7); self.set_text_color(200, 220, 240)
        self.set_xy(bx, by+1); self.cell(bw, 7, 'INSTALLATION & USER GUIDE', align='C')
        self.set_font('KR', 'B', 30); self.set_text_color(*WHITE)
        self.set_xy(0, by+16); self.cell(W, 16, 'K-run', align='C')
        self.set_font('KR', 'B', 34)
        self.set_xy(0, by+30); self.cell(W, 20, '회의녹음요약', align='C')
        self.set_font('KR', '', 14)
        self.set_xy(0, by+52); self.cell(W, 10, '설치 및 사용 매뉴얼', align='C')
        self.set_draw_color(60, 120, 180); self.set_line_width(0.8)
        self.line(W*0.35, by+65, W*0.65, by+65)
        self.set_font('KR', '', 9.5); self.set_text_color(170, 205, 235)
        for i, t in enumerate(['코딩을 몰라도 괜찮습니다.',
                                '이 매뉴얼을 순서대로 따라하면',
                                '회의를 자동으로 텍스트와 요약으로 만들 수 있습니다.']):
            self.set_xy(0, by+70+i*7); self.cell(W, 7, t, align='C')
        btn_y = H * 0.80
        for i, (lbl, sub) in enumerate([('PART 1','설치 가이드'),('PART 2','사용 가이드')]):
            bx2 = W*0.20 + i*(W*0.38)
            self.set_fill_color(30, 60, 105)
            self.set_draw_color(*WHITE); self.set_line_width(0.4)
            self.rect(bx2, btn_y, 55, 18, 'FD')
            self.set_font('KR', 'B', 8); self.set_text_color(*WHITE)
            self.set_xy(bx2, btn_y+3); self.cell(55, 5, lbl, align='C')
            self.set_font('KR', '', 9)
            self.set_xy(bx2, btn_y+9); self.cell(55, 6, sub, align='C')
        self.set_font('KR', '', 8); self.set_text_color(110, 145, 180)
        self.set_xy(0, H-14); self.cell(W, 6, '케이런벤처스 전용 앱  ·  2026', align='C')

    # ── 목차 ───────────────────────────────────────────────────
    def toc(self):
        self._ptype = 'content'; self.add_page()
        self.set_font('KR', 'B', 26); self.set_text_color(*NAVY)
        self.set_xy(L, 18); self.cell(0, 14, '목  차')
        self.set_draw_color(*BLUE); self.set_line_width(0.8)
        self.line(L, 35, W-R, 35)

        def pt(txt, y):
            self._rect(L, y, W-L-R, 10, LBLUE)
            self.set_font('KR', 'B', 10); self.set_text_color(*NAVY)
            self.set_xy(L+4, y+1.5); self.cell(0, 7, txt)

        def en(sec, title, pg, y):
            self.set_font('KR', '', 9.5); self.set_text_color(*BLACK)
            self.set_xy(L+10, y); self.cell(120, 7, f'{sec}  {title}')
            self.set_font('KR', 'B', 9.5); self.set_text_color(*BLUE)
            self.set_xy(W-R-14, y); self.cell(14, 7, str(pg), align='R')
            self.set_draw_color(210,210,210); self.set_line_width(0.15)
            self.set_dash_pattern(dash=1, gap=1)
            self.line(L+80, y+5.5, W-R-15, y+5.5)
            self.set_dash_pattern(); self.set_text_color(*BLACK)

        y = 40
        pt('PART 1  ·  설치 가이드', y); y += 13
        for s,t,p in [('1-1.','시작 전 준비물 체크리스트',3),
                       ('1-2.','STEP 1 — 앱 다운로드 및 설치',4),
                       ('1-3.','STEP 2 — CLOVA Speech API 설정',5),
                       ('1-4.','STEP 3 — Gemini API 설정',6),
                       ('1-5.','STEP 4 — Google Drive 연동 (선택)',7),
                       ('1-6.','설치 완료 확인',8),
                       ('1-7.','자주 묻는 질문 (설치편)',9)]:
            en(s,t,p,y); y += 8
        y += 6
        pt('PART 2  ·  사용 가이드', y); y += 13
        for s,t,p in [('2-1.','녹음 및 변환 방법',11),
                       ('2-2.','STT 파일로 즉시 요약 (영역 B)',12),
                       ('2-3.','요약 방식 선택하기',13),
                       ('2-4.','회의목록 조회 및 관리',14),
                       ('2-5.','STT 엔진 비교 및 권장 조합',15),
                       ('2-6.','자주 묻는 질문 (사용편)',16)]:
            en(s,t,p,y); y += 8
        y += 6
        self._box('[안내]  이 앱은 Windows 64-bit PC에서 실행됩니다. '
                  'CLOVA Speech API(유료)와 Gemini API(무료)가 필요합니다.',
                  INFO_BG, INFO_BR, y=y)

    # ── PART 구분 ──────────────────────────────────────────────
    def part_page(self, num, title, sub):
        self._ptype = 'divider'; self.add_page()
        self._rect(0, 0, W, H, DARK_BG)
        cy = H * 0.44
        self.set_font('KR', '', 9.5); self.set_text_color(130, 175, 215)
        self.set_xy(L, cy-18); self.cell(0, 8, f'PART  {num}')
        self.set_font('KR', 'B', 28); self.set_text_color(*WHITE)
        self.set_xy(L, cy-8); self.cell(0, 18, title)
        self.set_font('KR', '', 10.5); self.set_text_color(165, 200, 230)
        self.set_xy(L, cy+14); self.cell(0, 8, sub)

    # ── 섹션 헤더 ──────────────────────────────────────────────
    def sec(self, title):
        self._need(18)
        y = self.get_y()
        self._rect(L, y, W-L-R, 11, LBLUE)
        self._rect(L, y, 3, 11, BLUE)
        self.set_font('KR', 'B', 11.5); self.set_text_color(*NAVY)
        self.set_xy(L+6, y+1.5); self.cell(0, 8, title)
        self.ln(14)

    # ── STEP 헤더 ──────────────────────────────────────────────
    def step(self, num, title, sub=''):
        self._need(28)
        y = self.get_y()
        h = 19 if not sub else 23
        self._rect(L, y, W-L-R, h, NAVY)
        self._rect(L, y, 17, h, BLUE)
        self.set_font('KR', 'B', 13); self.set_text_color(*WHITE)
        self.set_xy(L, y+1); self.cell(17, h-2, str(num), align='C')
        self.set_font('KR', 'B', 10.5)
        self.set_xy(L+20, y+3); self.cell(0, 7, title)
        if sub:
            self.set_font('KR', '', 8.5); self.set_text_color(170, 205, 235)
            self.set_xy(L+20, y+12); self.cell(0, 6, sub)
        self.set_text_color(*BLACK); self.ln(h+5)

    # ── 서브 헤더 ──────────────────────────────────────────────
    def sub(self, num, title):
        self._need(12)
        mk = ['(1)', '(2)', '(3)', '(4)', '(5)']
        self.set_font('KR', 'B', 9.5); self.set_text_color(*BLUE)
        self.set_x(L); self.cell(0, 8, f'{mk[num-1]}  {title}')
        self.set_text_color(*BLACK); self.ln(9)

    # ── 본문 ───────────────────────────────────────────────────
    def body(self, text, ind=L):
        self.set_font('KR', '', 9.5); self.set_text_color(*BLACK)
        self.set_x(ind); self.multi_cell(W-ind-R, 6, text); self.ln(2)

    # ── 번호 목록 ──────────────────────────────────────────────
    def nlist(self, items, ind=L+4):
        for i, item in enumerate(items, 1):
            self._need(10)
            self.set_font('KR', 'B', 9); self.set_text_color(*NAVY)
            self.set_x(ind); self.cell(6, 6.5, f'{i}.')
            self.set_font('KR', '', 9); self.set_text_color(*BLACK)
            self.multi_cell(W-ind-R-6, 6.5, item)
        self.ln(2)

    # ── 정보 박스 ──────────────────────────────────────────────
    def _box(self, text, bg, br, y=None):
        inner_w = W - L - R - 8
        self.set_font('KR', '', 8.8)
        # 높이: 글자 수 기반 추정 (한글 1자 ≈ 3.5mm at 8.8pt)
        sw = self.get_string_width(text)
        n_lines = max(1, math.ceil(sw / inner_w))
        box_h = n_lines * 6.2 + 10
        if y is None:
            self._need(box_h + 4); y = self.get_y()
        self.set_fill_color(*bg); self.set_draw_color(*br)
        self.set_line_width(0.4); self.rect(L, y, W-L-R, box_h, 'FD')
        self.set_fill_color(*br); self.rect(L, y, 3, box_h, 'F')
        self.set_xy(L+6, y+4)
        self.multi_cell(inner_w, 6.2, text)
        self.set_y(y + box_h + 4)

    def ibox(self, t, y=None): self._box(t, INFO_BG, INFO_BR, y)
    def wbox(self, t, y=None): self._box(t, WARN_BG, WARN_BR, y)
    def sbox(self, t, y=None): self._box(t, SUCC_BG, SUCC_BR, y)
    def ebox(self, t, y=None): self._box(t, ERR_BG,  ERR_BR,  y)

    # ── 체크리스트 박스 ────────────────────────────────────────
    def cbox(self, title, items, bg=SUCC_BG, br=SUCC_BR):
        box_h = 11 + len(items) * 8 + 3
        self._need(box_h + 4); y = self.get_y()
        self.set_fill_color(*bg); self.set_draw_color(*br)
        self.set_line_width(0.4); self.rect(L, y, W-L-R, box_h, 'FD')
        self.set_fill_color(*br); self.rect(L, y, 3, box_h, 'F')
        self.set_font('KR', 'B', 9.5); self.set_text_color(*NAVY)
        self.set_xy(L+6, y+3); self.cell(0, 6, title)
        self.set_font('KR', '', 9.5); self.set_text_color(*BLACK)
        cy = y + 11
        for item in items:
            self.set_xy(L+9, cy); self.cell(0, 7, f'□   {item}'); cy += 8
        self.set_y(y + box_h + 4)

    # ── 코드 블록 ──────────────────────────────────────────────
    def code(self, text):
        lines = text.strip().split('\n')
        h = len(lines) * 6.5 + 8
        self._need(h + 4); y = self.get_y()
        self._rect(L, y, W-L-R, h, DGRAY)
        self.set_font('KR', '', 8.5); self.set_text_color(*WHITE)
        for i, line in enumerate(lines):
            self.set_xy(L+5, y+4+i*6.5); self.cell(W-L-R-10, 6.5, line)
        self.set_text_color(*BLACK); self.set_y(y+h+4)

    # ── 테이블 (핵심 수정: 행 y 고정) ──────────────────────────
    def tbl(self, headers, rows, col_w=None, ind=L):
        tw = W - ind - R
        if col_w is None:
            col_w = [tw / len(headers)] * len(headers)
        LH = 5.5

        # 헤더
        self._need(12)
        x, y = ind, self.get_y()
        for i, ht in enumerate(headers):
            self._rect(x, y, col_w[i], 9, NAVY)
            self.set_draw_color(*NAVY); self.set_line_width(0.15)
            self.rect(x, y, col_w[i], 9)
            self.set_font('KR', 'B', 8.5); self.set_text_color(*WHITE)
            self.set_xy(x+2, y+1.5); self.cell(col_w[i]-4, 6, str(ht), align='C')
            x += col_w[i]
        self.set_y(y+9)

        # 데이터 행
        for ri, row in enumerate(rows):
            # 행 높이 사전 계산
            row_h = 8
            self.set_font('KR', '', 8.5)
            for ci, ct in enumerate(row):
                sw = self.get_string_width(str(ct))
                cw = col_w[ci] - 4
                if cw > 0:
                    nl = max(1, math.ceil(sw / cw))
                    row_h = max(row_h, nl * LH + 4)

            # 페이지 넘침 처리
            if self.get_y() + row_h > H - B_MARGIN - 6:
                self.add_page()
                x, y2 = ind, self.get_y()
                for i, ht in enumerate(headers):
                    self._rect(x, y2, col_w[i], 9, NAVY)
                    self.set_draw_color(*NAVY); self.set_line_width(0.15)
                    self.rect(x, y2, col_w[i], 9)
                    self.set_font('KR', 'B', 8.5); self.set_text_color(*WHITE)
                    self.set_xy(x+2, y2+1.5); self.cell(col_w[i]-4, 6, str(ht), align='C')
                    x += col_w[i]
                self.set_y(y2+9)

            bg = LGRAY if ri % 2 == 1 else WHITE
            x, y = ind, self.get_y()

            for ci, ct in enumerate(row):
                # 배경 + 테두리
                self.set_fill_color(*bg)
                self.set_draw_color(210, 210, 210); self.set_line_width(0.2)
                self.rect(x, y, col_w[ci], row_h, 'FD')
                # 텍스트 (y 좌표 고정)
                self.set_font('KR', '', 8.5); self.set_text_color(*BLACK)
                self.set_xy(x+2, y+2)
                self.multi_cell(col_w[ci]-4, LH, str(ct))
                x += col_w[ci]

            self.set_y(y + row_h)  # 행 완료 후 y 전진

        self.ln(4)

    # ── FAQ ────────────────────────────────────────────────────
    def faq(self, q, a):
        self._need(22)
        self.set_font('KR', 'B', 9.5); self.set_text_color(*BLUE)
        self.set_x(L); self.cell(0, 7, f'Q.  {q}'); self.ln(8)
        self.set_font('KR', '', 9.5); self.set_text_color(*BLACK)
        self.set_x(L); self.multi_cell(W-L-R, 6.5, f'A.  {a}')
        self.ln(2)
        self.set_draw_color(220,220,220); self.set_line_width(0.25)
        self.line(L, self.get_y(), W-R, self.get_y()); self.ln(5)


# ═══════════════════════════════════════════════════════════════════
# 콘텐츠 빌드
# ═══════════════════════════════════════════════════════════════════
def build(pdf: PDF) -> PDF:

    pdf.cover()
    pdf.toc()

    # ══ PART 1 ══════════════════════════════════════════════════
    pdf.part_page(1, '설치 가이드', '처음 한 번만 따라하면 됩니다. 약 20~30분 소요됩니다.')
    pdf._ptype = 'content'

    # 1-1
    pdf.add_page()
    pdf.sec('1-1.  시작 전 준비물 체크리스트')
    pdf.body('아래 두 가지 API가 필요합니다. 미리 준비해두면 설치가 더 빠릅니다.')
    pdf.tbl(
        ['서비스', '용도', '웹사이트', '비용'],
        [['CLOVA Speech API', 'STT 음성 변환 (권장)',    'console.ncloud.com',  '유료 (종량제)'],
         ['Gemini API',        '회의록 요약 (필수)',      'aistudio.google.com', '무료'],
         ['ChatGPT API',       'OpenAI STT/요약 (선택)', 'platform.openai.com', '유료 (선택)'],
         ['Google Drive',      '파일 자동 업로드 (선택)', 'drive.google.com',    '무료']],
        col_w=[42, 52, 52, 24]
    )
    pdf.cbox('준비 체크리스트', [
        'CLOVA Speech API 키 발급 완료  (Invoke URL + Secret Key)',
        'Gemini API 키 발급 완료',
        'Windows 64-bit PC 확인',
        '인터넷 연결 확인',
    ])

    # 1-2
    pdf.add_page()
    pdf.step(1, '1-2.  STEP 1 — 앱 다운로드 및 설치', 'GitHub에서 앱 파일을 받아옵니다')
    pdf.sub(1, '다운로드 링크')
    pdf.body('아래 주소에서 로그인 없이 누구나 다운로드할 수 있습니다.')
    pdf.code('https://github.com/antonio103first/meeting-recording-minute-app/releases/latest')
    pdf.tbl(
        ['파일명', '용도'],
        [['회의녹음요약.exe',       '앱 실행 파일 — 더블클릭으로 바로 실행'],
         ['KRunVentures_인증서.cer', 'Windows SmartScreen 경고 해제용 (최초 1회 설치)']],
        col_w=[62, 108]
    )
    pdf.sub(2, 'SmartScreen 경고 해제')
    pdf.body('방법 A — 인증서 설치 (권장, 한 번 설치하면 이후 경고 없음)')
    pdf.nlist([
        'KRunVentures_인증서.cer 더블클릭',
        '인증서 설치 → 로컬 컴퓨터 선택 → 다음',
        '모든 인증서를 다음 저장소에 저장 → 찾아보기 → 신뢰할 수 있는 게시자 선택',
        '다음 → 마침',
    ])
    pdf.body('방법 B — 즉시 실행 (설치 없이)')
    pdf.nlist([
        '회의녹음요약.exe 우클릭 → 속성 → 하단 "차단 해제" 체크 → 확인',
        '또는 빨간 경고 화면에서 "추가 정보" 클릭 → "실행" 클릭',
    ])

    # 1-3
    pdf.add_page()
    pdf.step(2, '1-3.  STEP 2 — CLOVA Speech API 설정', '한국어 STT 변환 엔진 (권장)')
    pdf.sub(1, 'API 키 발급')
    pdf.nlist([
        'console.ncloud.com 접속 후 로그인',
        'AI Service → CLOVA Speech 클릭',
        '도메인(앱) 선택 → 설정 탭 → 연동 정보 탭',
        'Invoke URL 및 Secret Key 복사',
    ])
    pdf.wbox('[주의]  NAVER 계정 이메일/비밀번호가 아닌 Invoke URL과 Secret Key를 입력해야 합니다.')
    pdf.sub(2, '앱에 입력')
    pdf.nlist([
        '앱 실행 → 설정 탭 클릭',
        'CLOVA Speech API 설정 영역에 Invoke URL, Secret Key 입력',
        '저장 버튼 클릭',
        '연결 테스트 버튼 클릭 → [연결 성공] 확인',
        '기본 STT 엔진을 CLOVA Speech (권장)으로 선택',
    ])
    pdf.sbox('[완료]  연결 테스트에서 "연결 성공"이 표시되면 설정 완료입니다.')

    # 1-4
    pdf.add_page()
    pdf.step(3, '1-4.  STEP 3 — Gemini API 설정', '회의록 요약 엔진 (필수)')
    pdf.sub(1, 'API 키 발급')
    pdf.nlist([
        'aistudio.google.com/apikey 접속  (Google 계정 필요)',
        'Create API Key 클릭',
        '생성된 API 키 복사',
    ])
    pdf.ibox('[안내]  Gemini API는 무료 플랜으로도 일반적인 회의 요약에 충분합니다. '
             'STT에 CLOVA를 사용하더라도 Gemini 키는 반드시 설정해야 합니다.')
    pdf.sub(2, '앱에 입력')
    pdf.nlist([
        '설정 탭 → Gemini API 설정 영역',
        'API 키 입력 → 저장',
        '연결 테스트 버튼 클릭 → [연결 성공] 확인',
    ])

    # 1-5
    pdf.add_page()
    pdf.step(4, '1-5.  STEP 4 — Google Drive 연동', '선택사항 — 요약 파일 자동 업로드')
    pdf.body('설정 시 요약 완료 후 자동으로 Google Drive에 업로드됩니다. 건너뛰어도 됩니다.')
    pdf.sub(1, 'OAuth 설정')
    pdf.nlist([
        'console.cloud.google.com → 새 프로젝트 생성',
        'API 및 서비스 → 라이브러리 → Google Drive API 활성화',
        '사용자 인증 정보 → OAuth 클라이언트 ID 생성  (애플리케이션 유형: 데스크톱 앱)',
        'JSON 파일 다운로드 → 로컬에 보관',
    ])
    pdf.sub(2, '앱에 연동')
    pdf.nlist([
        '설정 탭 → Google Drive 설정 → JSON 파일 선택 → 등록',
        '[Google 인증] 버튼 클릭 → 브라우저에서 계정 로그인 및 권한 승인',
        '[두 폴더 한번에 생성] 버튼 클릭 → 폴더 자동 생성 및 ID 저장',
    ])
    pdf.ibox('[안내]  Google Drive 연동은 선택사항입니다. 로컬 PC에만 저장해도 모든 기능을 사용할 수 있습니다.')

    # 1-6
    pdf.add_page()
    pdf.sec('1-6.  설치 완료 확인')
    pdf.cbox('설치 완료 체크리스트', [
        '앱이 정상 실행된다',
        'CLOVA Speech 연결 테스트 [연결 성공] 확인',
        'Gemini API 연결 테스트 [연결 성공] 확인',
        '설정 탭에서 STT 엔진이 CLOVA Speech로 선택됨',
    ])
    pdf.ln(2)
    pdf.set_font('KR', 'B', 9.5); pdf.set_text_color(*ERR_BR)
    pdf.set_x(L); pdf.cell(0, 7, '[!]  문제가 발생했다면:'); pdf.ln(9)
    pdf.set_text_color(*BLACK)
    pdf.tbl(
        ['증상', '원인', '해결 방법'],
        [['"API 키를 입력해주세요"',  '설정 미완료',      '설정 탭에서 해당 API 키 입력 후 저장'],
         ['CLOVA 연결 실패 (401)',     'Secret Key 오입력', 'NAVER Console → 연동 정보의 Secret Key 사용'],
         ['CLOVA 연결 실패 (403)',     '서비스 미신청',    'NAVER Cloud Console에서 CLOVA Speech 신청'],
         ['Gemini 타임아웃 반복',      '긴 파일 처리 한계','STT 엔진을 CLOVA Speech로 전환'],
         ['앱 실행 차단 (SmartScreen)','서명 미인식',      '인증서 설치 또는 속성에서 차단 해제 (1-2 참고)']],
        col_w=[52, 44, 74]
    )

    # 1-7
    pdf.add_page()
    pdf.sec('1-7.  자주 묻는 질문 (설치편)')
    pdf.faq('회사 밖에서도 사용할 수 있나요?',
            '네, 인터넷이 연결된 환경이라면 어디서든 사용 가능합니다. '
            'Google Drive 연동 기능도 외부에서 정상 작동합니다.')
    pdf.faq('ChatGPT API도 반드시 설정해야 하나요?',
            'ChatGPT API는 선택사항입니다. CLOVA Speech(STT) + Gemini(요약) 조합으로 '
            '대부분의 사용 사례를 충분히 처리할 수 있습니다.')
    pdf.faq('API 키는 어디에 저장되나요?',
            r'API 키는 사용자 PC의 C:\Users\{사용자}\회의녹음요약_데이터\config.json에 '
            '로컬 저장됩니다. PC 재설치 후 이 파일을 백업해두면 설정을 그대로 복원할 수 있습니다.')
    pdf.faq('앱 업데이트는 어떻게 하나요?',
            'GitHub Release 페이지(releases/latest)에서 최신 exe를 다운로드하여 '
            '기존 파일을 교체하면 됩니다. 설정 파일은 그대로 유지됩니다.')

    # ══ PART 2 ══════════════════════════════════════════════════
    pdf.part_page(2, '사용 가이드', '회의를 시작하면 자동으로 기록됩니다')
    pdf._ptype = 'content'

    # 2-1
    pdf.add_page()
    pdf.sec('2-1.  녹음 및 변환 방법')
    pdf.sub(1, '음성 입력')
    pdf.body('- 실시간 녹음 :  마이크 선택 → [녹음 시작] → [중지]  (MP3 자동 저장)\n'
             '- 기존 파일    :  [파일 선택] → MP3, WAV, M4A, MP4, OGG, FLAC 지원')
    pdf.sub(2, '화자 수 설정')
    pdf.body('변환 전 실제 참석자 수를 설정합니다 (1~8명 또는 자동 감지).')
    pdf.sub(3, '변환 시작')
    pdf.body('[변환 시작] 버튼 클릭 → 설정에서 지정한 STT 엔진과 요약 방식이 자동 적용됩니다.')
    pdf.ln(2)
    pdf.code('STT 변환 (진행률 표시)\n'
             '     ↓\n'
             '요약 생성 중...\n'
             '     ↓\n'
             '파일명 입력\n'
             '     ↓\n'
             '로컬 저장 + Drive 업로드 (설정 시)')
    pdf.ibox('[안내]  기본 STT 엔진 및 요약 방식은 설정 탭 → 기본 요약 방식에서 미리 지정하세요.')

    # 2-2
    pdf.add_page()
    pdf.sec('2-2.  STT 파일로 즉시 요약 (영역 B)')
    pdf.body('STT 변환을 건너뛰고 기존 .txt 파일로 바로 요약할 수 있습니다.')
    pdf.nlist([
        '[STT 파일 선택] 버튼 클릭 → .txt 파일 선택',
        '(선택) 커스텀 프롬프트 입력란에 특별 지시사항 입력',
        '[회의록 변환] 버튼 클릭',
    ])
    pdf.ibox('[안내]  이미 STT 변환된 텍스트 파일이 있거나, 직접 작성한 회의 메모를 AI로 요약할 때 유용합니다.')

    # 2-3
    pdf.add_page()
    pdf.sec('2-3.  요약 방식 선택하기')
    pdf.body('설정 탭 → 기본 요약 방식에서 5가지 방식 중 선택합니다.')
    pdf.tbl(
        ['방식', '특징 및 적합한 상황'],
        [['화자 중심',    '발화자별로 발언 내용을 정리 — 누가 무슨 말을 했는지 추적할 때'],
         ['주제 중심',    '논의된 주제별로 분류 — 여러 안건을 다룬 회의에 적합'],
         ['흐름 중심',    '회의 진행 순서대로 서술 — 회의 전체 맥락을 파악할 때'],
         ['결정사항 중심','결정된 사항과 액션 아이템 중심 — 실무 팔로업에 최적'],
         ['커스텀',       '직접 입력한 프롬프트로 요약 — 특수한 형식이나 언어 요구 시']],
        col_w=[38, 132]
    )
    pdf.ibox('[안내]  커스텀 방식은 영역 A의 변환 전 또는 영역 B의 커스텀 프롬프트 입력란에서 '
             '별도 지시사항을 직접 입력할 수 있습니다.')

    # 2-4
    pdf.add_page()
    pdf.sec('2-4.  회의목록 조회 및 관리')
    pdf.body('저장된 모든 회의를 조회하고 다양한 작업을 수행합니다.\n목록에서 항목 선택 후 아래 버튼을 사용하세요.')
    pdf.tbl(
        ['버튼', '기능'],
        [['[보기]  전체보기',  '전체 회의록 팝업 표시 + 파일 직접 열기'],
         ['[인쇄]  출력·인쇄', '연결된 로컬 프린터로 회의록 인쇄'],
         ['[수정]  화자이름',  'STT 결과의 [화자1], [화자2]를 실제 이름으로 변경'],
         ['[공유]  공유',      '이메일 공유 또는 클립보드 복사'],
         ['[PDF]  PDF 저장',   '회의록을 PDF 파일로 저장 (한글 지원)'],
         ['[삭제]  삭제',      '목록에서 삭제 (원본 파일 유지, DB에서만 제거)']],
        col_w=[42, 128]
    )
    pdf.body('분리뷰 탭:')
    pdf.body('  - [요약] 회의록 요약 탭 — AI가 생성한 요약본 표시\n'
             '  - [원문] STT 원문 탭     — 음성 인식 원본 텍스트 표시', ind=L+4)

    # 2-5
    pdf.add_page()
    pdf.sec('2-5.  STT 엔진 비교 및 권장 조합')
    pdf.tbl(
        ['항목', 'CLOVA Speech (권장)', 'Gemini', 'ChatGPT (Whisper)'],
        [['한국어 정확도',  '★★★★★',      '★★★★',          '★★★★'],
         ['화자 구분',      '[O] 지원',     '[O] 지원',        '[X] 미지원'],
         ['파일 크기 제한', '최대 1GB',     '20MB (인라인)',    '25MB'],
         ['장시간 처리',    '제한 없음',    '1시간 이내 권장', '30분 이내 권장'],
         ['비용',           '유료 (종량제)','무료 (한도 내)',  '유료']],
        col_w=[38, 48, 38, 46]
    )
    pdf.ln(3)
    pdf.set_font('KR', 'B', 10); pdf.set_text_color(*NAVY)
    pdf.set_x(L); pdf.cell(0, 7, '권장 조합'); pdf.ln(9); pdf.set_text_color(*BLACK)
    pdf.tbl(
        ['시나리오', 'STT 엔진', '요약 엔진'],
        [['일반 회의 (30분 이하)',  'CLOVA Speech',     'Gemini'],
         ['장시간 회의 (1시간+)',   'CLOVA Speech',     'Claude'],
         ['다국어 혼용 회의',       'ChatGPT (Whisper)', 'GPT-4o'],
         ['비용 최소화',            'Gemini',            'Gemini']],
        col_w=[68, 52, 50]
    )

    # 2-6
    pdf.add_page()
    pdf.sec('2-6.  자주 묻는 질문 (사용편)')
    pdf.faq('회의록이 저장되는 위치는 어디인가요?',
            '기본 저장 경로: ~/Documents/Meeting recording/회의록(요약)/\n'
            '설정 탭 → PC 저장 폴더 설정에서 MP3 파일, STT 변환본, 요약 파일 각각의 경로를 변경할 수 있습니다.')
    pdf.faq('화자 이름을 나중에 변경할 수 있나요?',
            '네, 회의목록 탭에서 해당 회의를 선택한 후 [수정] 화자이름 버튼을 클릭하면 '
            '[화자1], [화자2] 등을 실제 이름으로 언제든 변경할 수 있습니다.')
    pdf.faq('Google Drive 업로드가 안 됩니다.',
            '설정 탭 → Google Drive 설정에서 "미연결" 상태를 확인하세요. '
            '[Google 인증] 버튼을 클릭하여 재인증하면 해결됩니다.')
    pdf.faq('긴 회의 파일(1시간 이상)이 처리되지 않습니다.',
            'Gemini STT 엔진은 1시간 이상 파일에서 타임아웃이 발생할 수 있습니다. '
            '설정 탭에서 STT 엔진을 CLOVA Speech로 변경하면 시간 제한 없이 처리됩니다.')

    return pdf


# ═══════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('=== K-run 회의녹음요약 v3.0 매뉴얼 PDF 생성 ===')
    fr = find_font(FONT_R)
    if not fr:
        print('ERROR: 한국어 폰트 없음. NanumGothic.ttf를 스크립트 폴더에 넣어 주세요.')
        sys.exit(1)
    fb = find_font(FONT_B) or fr
    print(f'폰트 Regular : {fr}')
    print(f'폰트 Bold    : {fb}')
    pdf = build(PDF(fr, fb))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '회의녹음요약_매뉴얼_v3.0.pdf')
    pdf.output(out)
    print(f'\n완료: {out}')
