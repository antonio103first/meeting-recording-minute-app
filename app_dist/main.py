"""
회의녹음요약 v3 - 메인 GUI
탭 구성: 녹음/변환 | 회의목록 | 설정
자동화 파이프라인: STT → (화자이름) → 요약 → 로컬 저장 → Drive 업로드(선택)
Google Drive A방식: 각 사용자가 직접 OAuth 자격증명 설정

v3 신규 기능:
  F-01: 회의목록 탭 — 요약/STT 분리뷰 + 5개 액션 버튼
  F-02: PDF 내보내기 / Markdown→HTML 렌더링 인쇄 고도화
  F-03: 전 방식 MD 파일 저장 통일
  F-04: 흐름 중심 요약 방식 추가
  F-05: 설정 탭 — ChatGPT API 섹션 추가
  F-06: 녹음탭 — 흐름중심 옵션 + ChatGPT 엔진 선택
  F-06-S: 저장 구조 3폴더 분리 (MP3 / STT .md / 회의록 .md)
"""
import sys
import os
import re
import webbrowser
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from datetime import datetime
from pathlib import Path

# 앱 폴더를 모듈 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import database
import recorder as rec_mod
import gemini_service as gemini
import claude_service as claude
import clova_service as clova
import file_manager as fm
import google_drive as gdrive

# ── 색상 / 스타일 상수 ──────────────────────────────────
BG          = "#F5F6FA"
SIDEBAR_BG  = "#2C3E50"
ACCENT      = "#3498DB"
ACCENT_DARK = "#2980B9"
SUCCESS     = "#27AE60"
DANGER      = "#E74C3C"
WARNING     = "#F39C12"
TEXT        = "#2C3E50"
TEXT_LIGHT  = "#7F8C8D"
WHITE       = "#FFFFFF"
CARD_BG     = "#FFFFFF"
BORDER      = "#E0E0E0"

FONT_TITLE  = ("맑은 고딕", 16, "bold")
FONT_H2     = ("맑은 고딕", 12, "bold")
FONT_BODY   = ("맑은 고딕", 10)
FONT_SMALL  = ("맑은 고딕", 9)
FONT_BTN    = ("맑은 고딕", 10, "bold")


# ════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("회의녹음요약")
        self.geometry("960x760")
        self.minsize(800, 600)
        self.configure(bg=BG)
        self.resizable(True, True)

        # 앱 아이콘 설정
        try:
            _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            _ico = os.path.join(_base, 'app_icon.ico')
            if os.path.exists(_ico):
                self.wm_iconbitmap(_ico)
        except Exception:
            pass

        # 앱 데이터 초기화
        config.ensure_dirs()
        database.init_database()
        self._cfg = config.load_config()

        # 절전 방지 초기화 (Windows 전용)
        self._sleep_prevention_active = False
        try:
            import ctypes
            self._kernel32 = ctypes.windll.kernel32
            self._ES_CONTINUOUS      = 0x80000000
            self._ES_SYSTEM_REQUIRED = 0x00000001
        except Exception:
            self._kernel32 = None

        # 상태 변수
        self._recorder      = rec_mod.AudioRecorder()
        self._cancel_event  = threading.Event()
        self._current_mp3   = None
        self._stt_text      = ""
        self._summary_text  = ""
        self._meeting_id    = None
        self._processing    = False

        # 파이프라인 임시 저장
        self._pipeline_sum_mode    = "speaker"
        self._pipeline_ai_engine   = self._cfg.get("summary_engine", "gemini")  # "gemini" | "claude" | "chatgpt"
        self._pipeline_company_name = ""  # IR 미팅 모드 전용: 혁신의숲 API 조회 기업명
        self._pipeline_stt_engine  = self._cfg.get("stt_engine", "gemini")      # "gemini" | "clova"
        self._pipeline_rename_spk  = False
        self._current_sum_path     = None
        self._metrics_text         = ""
        self._selected_meeting_data = {}

        self._build_ui()
        self._apply_style()
        self._refresh_list()
        self._tick()

        # 앱 종료 시 절전 방지 반드시 해제
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # 첫 실행 마법사 (API 키 없을 때)
        if not self._cfg.get("gemini_api_key", "").strip():
            self.after(200, self._show_first_run_wizard)

    def _on_app_close(self):
        """앱 종료 핸들러 — 절전 방지 반드시 해제 후 종료"""
        self._set_sleep_prevention(False)
        self.destroy()

    # ── UI 구성 ──────────────────────────────────────────
    def _build_ui(self):
        # 헤더
        hdr = tk.Frame(self, bg=SIDEBAR_BG, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🎙 회의녹음요약",
                 font=FONT_TITLE, bg=SIDEBAR_BG, fg=WHITE).pack(side="left", padx=20, pady=10)

        # 탭
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

        self._tab_rec  = tk.Frame(self._nb, bg=BG)
        self._tab_list = tk.Frame(self._nb, bg=BG)
        self._tab_cfg  = tk.Frame(self._nb, bg=BG)

        self._nb.add(self._tab_rec,  text="  🎙 녹음/변환  ")
        self._nb.add(self._tab_list, text="  📋 회의목록  ")
        self._nb.add(self._tab_cfg,  text="  ⚙ 설정  ")

        self._build_tab_record()
        self._build_tab_list()
        self._build_tab_settings()

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                        font=("맑은 고딕", 9),
                        padding=[10, 6],
                        background="#DDE3EA",
                        foreground=TEXT)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", WHITE)],
                  font=[("selected", ("맑은 고딕", 12, "bold"))],
                  padding=[("selected", [16, 10])])
        style.configure("TProgressbar", troughcolor=BORDER,
                        background=ACCENT, thickness=12)

        # 회의목록 내 분리뷰 탭 — 선택 시 다른 탭보다 크게 강조
        style.configure("Detail.TNotebook", background=CARD_BG, borderwidth=0)
        style.configure("Detail.TNotebook.Tab",
                        font=("맑은 고딕", 10),
                        padding=[14, 7],
                        background="#DDE3EA",
                        foreground=TEXT)
        style.map("Detail.TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", WHITE)],
                  font=[("selected", ("맑은 고딕", 11, "bold"))],
                  padding=[("selected", [22, 11])])

    # ════════════════════════════════════════════════════
    # 탭 1 : 녹음/변환
    # ════════════════════════════════════════════════════
    def _build_tab_record(self):
        parent = self._tab_rec

        # ── 하단 고정: 저장 상태 (항상 보임) ──
        save_footer = tk.Frame(parent, bg=CARD_BG,
                               highlightthickness=1, highlightbackground=BORDER)
        save_footer.pack(side="bottom", fill="x", padx=20, pady=(4, 8))
        save_inner = tk.Frame(save_footer, bg=CARD_BG)
        save_inner.pack(fill="x", padx=12, pady=6)
        tk.Label(save_inner, text="💾 저장 & 업로드 상태",
                 font=FONT_H2, bg=CARD_BG, fg=TEXT).pack(anchor="w")
        ttk.Separator(save_inner).pack(fill="x", pady=(4, 6))
        self._save_status_var = tk.StringVar(value="파이프라인을 실행하면 자동으로 저장됩니다.")
        tk.Label(save_inner, textvariable=self._save_status_var,
                 font=FONT_BODY, bg=CARD_BG, fg=TEXT_LIGHT,
                 wraplength=860, justify="left").pack(anchor="w")

        # ── Canvas + Scrollbar (녹음/STT/요약 섹션) ──
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG)
        cwin  = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e):
            canvas.itemconfig(cwin, width=e.width)
        canvas.bind("<Configure>", _resize)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # 마우스 휠 스크롤 (탭 1)
        def _on_rec_scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_rec_scroll))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        pad = {"padx": 20, "pady": 5}

        # ─ 섹션 1: 녹음 ─────────────────────────────────
        self._card(inner, "🎙 녹음").pack(fill="x", **pad)
        rec_card = self._last_card

        # 마이크 선택
        mic_row = tk.Frame(rec_card, bg=CARD_BG)
        mic_row.pack(fill="x", pady=(0, 8))
        tk.Label(mic_row, text="마이크:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(side="left")
        self._mic_var = tk.StringVar(value="기본 마이크")
        self._mic_cb  = ttk.Combobox(mic_row, textvariable=self._mic_var,
                                     width=36, state="readonly", font=FONT_BODY)
        self._mic_cb.pack(side="left", padx=8)
        self._refresh_mic_list()
        ttk.Button(mic_row, text="↻", width=3,
                   command=self._refresh_mic_list).pack(side="left")

        # 녹음 시간
        self._elapsed_var = tk.StringVar(value="00:00:00")
        tk.Label(rec_card, textvariable=self._elapsed_var,
                 font=("맑은 고딕", 20, "bold"),
                 bg=CARD_BG, fg=ACCENT).pack(pady=2)

        # 음량 바
        self._level_bar = ttk.Progressbar(rec_card, maximum=100, length=400)
        self._level_bar.pack(pady=2)

        # 녹음 버튼 행
        btn_row = tk.Frame(rec_card, bg=CARD_BG)
        btn_row.pack(pady=4)
        self._btn_rec   = self._btn(btn_row, "● 녹음 시작", ACCENT, self._toggle_record, w=14)
        self._btn_pause = self._btn(btn_row, "⏸ 일시정지", WARNING, self._toggle_pause, w=12)
        self._btn_stop  = self._btn(btn_row, "■ 중지", DANGER, self._stop_record, w=10)
        self._btn_rec.pack(side="left", padx=4)
        self._btn_pause.pack(side="left", padx=4)
        self._btn_stop.pack(side="left", padx=4)
        self._btn_pause.config(state="disabled")
        self._btn_stop.config(state="disabled")

        # 현재 파일 표시
        file_row = tk.Frame(rec_card, bg=CARD_BG)
        file_row.pack(fill="x", pady=(4, 0))
        tk.Label(file_row, text="선택 파일:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(side="left")
        self._cur_file_var = tk.StringVar(value="(없음)")
        tk.Label(file_row, textvariable=self._cur_file_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT,
                 wraplength=500, justify="left").pack(side="left", padx=8)
        self._btn(file_row, "📂 파일 선택", TEXT_LIGHT,
                  self._pick_audio_file, w=12).pack(side="right")

        # ─ 섹션 2: STT 변환 결과 ────────────────────────
        self._card(inner, "📝 STT 변환 결과").pack(fill="x", **pad)
        stt_card = self._last_card

        # 화자 수 선택 (1~8명 + 자동)
        spk_row = tk.Frame(stt_card, bg=CARD_BG)
        spk_row.pack(fill="x", pady=(0, 2))
        tk.Label(spk_row, text="화자 수:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(side="left")
        self._spk_var = tk.IntVar(value=0)
        for v, t in [(1,"1명"), (2,"2명"), (3,"3명"), (4,"4명"),
                     (5,"5명"), (6,"6명"), (7,"7명"), (8,"8명"), (0,"자동")]:
            tk.Radiobutton(spk_row, text=t, variable=self._spk_var, value=v,
                           bg=CARD_BG, fg=TEXT, font=FONT_BODY,
                           activebackground=CARD_BG).pack(side="left", padx=4)

        # STT 진행 바
        self._stt_prog = ttk.Progressbar(stt_card, maximum=100, length=500)
        self._stt_prog.pack(pady=2)
        self._stt_status_var = tk.StringVar(value="")
        tk.Label(stt_card, textvariable=self._stt_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()

        # [▶ 변환 시작] + [📎 TXT 첨부] + [■ 중단]
        stt_btn_row = tk.Frame(stt_card, bg=CARD_BG)
        stt_btn_row.pack(pady=4)
        self._btn_pipeline = self._btn(stt_btn_row, "▶ 변환 시작",
                                       ACCENT, self._start_pipeline, w=18)
        self._btn_pipeline.pack(side="left", padx=4)
        self._btn_txt_import = self._btn(stt_btn_row, "📎 TXT 파일 첨부",
                                         "#8E44AD", self._import_txt_and_summarize, w=18)
        self._btn_txt_import.pack(side="left", padx=4)
        self._btn_cancel = self._btn(stt_btn_row, "■ 중단",
                                     DANGER, self._cancel_process, w=8)
        self._btn_cancel.pack(side="left", padx=4)
        self._btn_cancel.config(state="disabled")

        # STT 결과 표시
        tk.Label(stt_card, text="변환 결과:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, anchor="w").pack(fill="x", pady=(8, 2))
        self._stt_box = scrolledtext.ScrolledText(
            stt_card, height=5, font=FONT_BODY, wrap="word",
            bg="#FAFAFA", relief="solid", bd=1)
        self._stt_box.pack(fill="x")

        # 이전 회의록 참조 링크 (비교 분석용)
        obs_header = tk.Frame(stt_card, bg=CARD_BG)
        obs_header.pack(fill="x", pady=(10, 2))
        tk.Label(obs_header, text="📎 이전 회의록 참조 (Obsidian 링크, 비교 분석용)",
                 font=FONT_BODY, bg=CARD_BG, fg=TEXT).pack(side="left")
        self._btn_obs_add = self._btn(obs_header, "+ 추가", "#2980B9",
                                      self._obs_link_add, w=6)
        self._btn_obs_add.pack(side="right", padx=2)

        # 링크 목록 프레임 (스크롤 가능)
        self._obs_links_frame = tk.Frame(stt_card, bg=CARD_BG)
        self._obs_links_frame.pack(fill="x")
        self._obs_link_vars = []   # list of StringVar
        self._obs_link_rows = []   # list of Frame (for removal)
        # 초기 1개 행 추가
        self._obs_link_add()

        # ─ 섹션 3: 회의록 요약 결과 ─────────────────────
        self._card(inner, "📋 회의록 요약 결과").pack(fill="x", **pad)
        sum_card = self._last_card

        # 요약 진행 바
        self._sum_prog = ttk.Progressbar(sum_card, maximum=100, length=500)
        self._sum_prog.pack(pady=2)
        self._sum_status_var = tk.StringVar(value="")
        tk.Label(sum_card, textvariable=self._sum_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()

        # 요약 결과 표시
        tk.Label(sum_card, text="요약 결과:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, anchor="w").pack(fill="x", pady=(4, 2))
        self._sum_box = scrolledtext.ScrolledText(
            sum_card, height=8, font=FONT_BODY, wrap="word",
            bg="#FAFAFA", relief="solid", bd=1)
        self._sum_box.pack(fill="x")

        # 커스텀 재요약 버튼
        resummarize_row = tk.Frame(sum_card, bg=CARD_BG)
        resummarize_row.pack(fill="x", pady=(6, 0))
        self._btn_resummarize = self._btn(
            resummarize_row, "🔄 커스텀 재요약", SUCCESS, self._resummarize, w=16)
        self._btn_resummarize.pack(side="left", padx=4)
        self._btn_resummarize.config(state="disabled")
        tk.Label(resummarize_row,
                 text="← 설정 탭의 커스텀 프롬프트를 적용해 재요약",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")


        # ════ 영역 B: 회의록 추가 변환 (STT 파일 → 회의록) ════
        ttk.Separator(inner).pack(fill="x", padx=20, pady=10)
        self._card(inner, "📝 회의록 추가 변환 (STT 파일 선택 → 회의록 생성)").pack(fill="x", padx=20, pady=5)
        b_card = self._last_card

        tk.Label(b_card,
                 text="저장된 STT 파일(.md)을 불러와 새로운 요약 방식으로 추가 변환합니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(0, 6))

        # STT 파일 선택 행
        b_file_row = tk.Frame(b_card, bg=CARD_BG)
        b_file_row.pack(fill="x", pady=4)
        tk.Label(b_file_row, text="STT 파일:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=10, anchor="w").pack(side="left")
        self._b_stt_file_var = tk.StringVar(value="(파일 미선택)")
        self._b_stt_path = None
        tk.Label(b_file_row, textvariable=self._b_stt_file_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left", padx=4)
        self._btn(b_file_row, "📂 STT 파일 선택", ACCENT,
                  self._b_pick_stt_file, w=14).pack(side="right")

        # 커스텀 프롬프트 (1회성)
        cp_row = tk.Frame(b_card, bg=CARD_BG)
        cp_row.pack(fill="x", pady=4)
        tk.Label(cp_row, text="추가 지시:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=10, anchor="w").pack(side="left")
        self._b_custom_prompt = tk.Entry(cp_row, font=FONT_BODY, width=50)
        self._b_custom_prompt.pack(side="left", padx=4)
        tk.Label(cp_row,
                 text="(이번 변환에만 적용, 저장 안됨)",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")

        # 진행률
        self._b_status_var = tk.StringVar(value="")
        tk.Label(b_card, textvariable=self._b_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w")

        # 버튼 행
        b_btn_row = tk.Frame(b_card, bg=CARD_BG)
        b_btn_row.pack(pady=6)
        self._btn_b_convert = self._btn(b_btn_row, "📝 회의록 변환", ACCENT,
                                        self._b_convert_meeting, w=14)
        self._btn_b_convert.pack(side="left", padx=4)
        self._btn_b_stop = self._btn(b_btn_row, "■ 중지", DANGER,
                                     self._b_stop_convert, w=8)
        self._btn_b_stop.pack(side="left", padx=4)
        self._btn_b_stop.config(state="disabled")

        # 요약 결과 표시
        self._b_result_box = tk.Text(
            b_card, height=8, font=FONT_BODY, wrap="word",
            bg="#FAFAFA", relief="solid", bd=1, state="disabled")
        self._b_result_box.pack(fill="x", pady=6)

    # ════════════════════════════════════════════════════
    # 탭 2 : 회의 목록 (v3 — 분리뷰 + 4개 액션 버튼)
    # ════════════════════════════════════════════════════
    def _build_tab_list(self):
        parent = self._tab_list

        # 타이틀 행
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", padx=20, pady=(12, 4))
        tk.Label(top, text="저장된 회의 목록", font=FONT_H2,
                 bg=BG, fg=TEXT).pack(side="left")
        self._btn(top, "↻ 새로고침", ACCENT,
                  self._refresh_list, w=12).pack(side="right")

        # ── PanedWindow: 트리뷰 ↔ 내용보기 세로 드래그 ──
        paned = ttk.PanedWindow(parent, orient="vertical")
        paned.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        # ─ 상단 패널: Treeview + 세로 스크롤바 ──────────
        tree_frame = tk.Frame(paned, bg=BG)

        tree_sb = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_sb.pack(side="right", fill="y")

        cols = ("날짜", "파일명", "녹음", "STT", "요약", "Drive")
        self._tree = ttk.Treeview(tree_frame, columns=cols,
                                  show="headings",
                                  yscrollcommand=tree_sb.set)
        tree_sb.config(command=self._tree.yview)

        col_w   = {"날짜": 140, "파일명": 240, "녹음": 60, "STT": 60, "요약": 60, "Drive": 70}
        col_min = {"날짜":  80, "파일명": 120, "녹음": 40, "STT": 40, "요약": 40, "Drive": 50}
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=col_w[c], minwidth=col_min[c],
                              anchor="center", stretch=True)

        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_list_select)
        paned.add(tree_frame, weight=3)

        # ─ 하단 패널: 4개 액션 버튼 + 분리뷰(요약/STT) ──
        bot_frame = tk.Frame(paned, bg=BG)

        # 4개 액션 버튼 행
        btn_row = tk.Frame(bot_frame, bg=BG)
        btn_row.pack(fill="x", pady=(4, 2))
        self._btn(btn_row, "📄 전체 보기", ACCENT,
                  self._view_meeting_full, w=12).pack(side="left", padx=4)
        self._btn(btn_row, "🖨 출력·인쇄", "#8E44AD",
                  self._print_meeting, w=12).pack(side="left", padx=4)
        self._btn(btn_row, "✏ 화자이름", "#7D6608",
                  self._rename_speaker_dialog, w=11).pack(side="left", padx=4)
        self._btn(btn_row, "📤 공유 ▼", "#16A085",
                  self._share_menu, w=11).pack(side="left", padx=4)
        self._btn(btn_row, "🔍 찾기/바꾸기", "#2E86C1",
                  self._find_replace_dialog, w=13).pack(side="left", padx=4)
        self._btn(btn_row, "🗑 삭제", DANGER,
                  self._delete_meeting, w=10).pack(side="left", padx=4)

        # 요약 / STT 분리 탭바
        self._detail_nb = ttk.Notebook(bot_frame, style="Detail.TNotebook")
        self._detail_nb.pack(fill="both", expand=True, pady=(4, 0))

        self._sum_detail_frame  = tk.Frame(self._detail_nb, bg=CARD_BG)
        self._stt_detail_frame  = tk.Frame(self._detail_nb, bg=CARD_BG)
        self._detail_nb.add(self._sum_detail_frame,  text="  📋 회의록 요약  ")
        self._detail_nb.add(self._stt_detail_frame,  text="  📝 STT 원문  ")

        self._sum_detail_box = scrolledtext.ScrolledText(
            self._sum_detail_frame, font=FONT_BODY, wrap="word",
            bg=CARD_BG, relief="flat", bd=0)
        self._sum_detail_box.pack(fill="both", expand=True)

        self._stt_detail_box = scrolledtext.ScrolledText(
            self._stt_detail_frame, font=FONT_BODY, wrap="word",
            bg=CARD_BG, relief="flat", bd=0)
        self._stt_detail_box.pack(fill="both", expand=True)

        # 하위 호환용 alias (구 코드에서 _detail_box 참조)
        self._detail_box = self._sum_detail_box

        paned.add(bot_frame, weight=2)

    # ════════════════════════════════════════════════════
    # 탭 3 : 설정
    # ════════════════════════════════════════════════════
    def _build_tab_settings(self):
        parent = self._tab_cfg

        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG)
        cwin  = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cwin, width=e.width))
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # 마우스 휠 스크롤 (탭 3)
        def _on_cfg_scroll(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_cfg_scroll))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        pad = {"padx": 20, "pady": 8}

        # ─ ① 기본 요약 방식 ─────────────────────────────────
        self._card(inner, "🗂 기본 요약 방식").pack(fill="x", **pad)
        sm_card = self._last_card

        tk.Label(sm_card,
                 text="변환 시 요약 방식을 지정합니다. 영역 A 자동 변환 시 이 설정이 적용됩니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(0, 6))

        self._default_sum_mode_var = tk.StringVar(
            value=self._cfg.get("summary_mode", "speaker"))
        for label, val in [
            ("주간회의 — K-Run Ventures 파트너 주간회의록", "speaker"),
            ("다자간 협의 — 기관협의·다자간 공식회의·다자간 네트워킹", "topic"),
            ("회의록(업무) — 직전 투자심사 외부 미팅·투자업체 사후관리", "formal_md"),
            ("IR 미팅회의록 ★신규★ — 피투자사 IR 미팅 전문 정리", "ir_md"),
            ("강의 요약 — 학습/세미나 특화", "lecture_md"),
            ("네트워킹(티타임) — 티타임·비공식 네트워킹 대화 정리", "flow"),
            ("전화통화 메모 — 통화 내용 주제별 요약 + 질의응답", "phone"),
        ]:
            fg = SUCCESS if val == "ir_md" else TEXT
            tk.Radiobutton(
                sm_card, text=label,
                variable=self._default_sum_mode_var, value=val,
                bg=CARD_BG, font=FONT_BODY, fg=fg, activebackground=CARD_BG,
                command=self._save_default_sum_mode
            ).pack(anchor="w")

        # ─ Gemini API ───────────────────────────────────
        self._card(inner, "🤖 Gemini API 설정").pack(fill="x", **pad)
        gem_card = self._last_card

        tk.Label(gem_card, text="Gemini API 키:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(anchor="w")
        self._gem_key_var = tk.StringVar(value=self._cfg.get("gemini_api_key", ""))
        gem_entry_row = tk.Frame(gem_card, bg=CARD_BG)
        gem_entry_row.pack(fill="x", pady=4)
        self._gem_entry = tk.Entry(
            gem_entry_row, textvariable=self._gem_key_var,
            width=52, font=FONT_BODY, show="*")
        self._gem_entry.pack(side="left")
        self._gem_show = False
        self._btn(gem_entry_row, "👁", TEXT_LIGHT,
                  self._toggle_gem_key_vis, w=3).pack(side="left", padx=4)

        gem_btn_row = tk.Frame(gem_card, bg=CARD_BG)
        gem_btn_row.pack(pady=6)
        self._btn(gem_btn_row, "저장", ACCENT,
                  self._save_gem_key, w=8).pack(side="left", padx=4)
        self._btn(gem_btn_row, "연결 테스트", SUCCESS,
                  self._test_gem, w=12).pack(side="left", padx=4)
        self._btn(gem_btn_row, "📋 발급 방법", TEXT_LIGHT,
                  self._show_api_guide, w=12).pack(side="left", padx=4)
        self._gem_status_var = tk.StringVar(value="")
        tk.Label(gem_card, textvariable=self._gem_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()
        tk.Label(gem_card,
                 text="▶ aistudio.google.com 에서 무료 API 키를 발급받으세요.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(4, 0))

        # ─ CLOVA Speech API ─────────────────────────────
        self._card(inner, "🎤 CLOVA Speech API 설정 (NAVER Cloud)").pack(fill="x", **pad)
        clova_card = self._last_card

        tk.Label(clova_card,
                 text="Gemini STT 타임아웃 문제 해소 — 한국어 특화 STT (CER ~9.5%)",
                 font=FONT_SMALL, bg=CARD_BG, fg=SUCCESS).pack(anchor="w", pady=(0, 6))

        # Invoke URL
        tk.Label(clova_card, text="Invoke URL:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(anchor="w")
        self._clova_id_var = tk.StringVar(value=self._cfg.get("clova_invoke_url", ""))
        clova_id_row = tk.Frame(clova_card, bg=CARD_BG)
        clova_id_row.pack(fill="x", pady=(2, 4))
        self._clova_id_entry = tk.Entry(
            clova_id_row, textvariable=self._clova_id_var,
            width=52, font=FONT_BODY)
        self._clova_id_entry.pack(side="left")
        self._clova_id_show = True   # URL은 항상 표시

        # Secret Key
        tk.Label(clova_card, text="Secret Key:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(anchor="w")
        self._clova_secret_var = tk.StringVar(value=self._cfg.get("clova_secret_key", ""))
        clova_sec_row = tk.Frame(clova_card, bg=CARD_BG)
        clova_sec_row.pack(fill="x", pady=(2, 6))
        self._clova_secret_entry = tk.Entry(
            clova_sec_row, textvariable=self._clova_secret_var,
            width=52, font=FONT_BODY, show="*")
        self._clova_secret_entry.pack(side="left")
        self._clova_secret_show = False
        self._btn(clova_sec_row, "👁", TEXT_LIGHT,
                  self._toggle_clova_secret_vis, w=3).pack(side="left", padx=4)

        # STT 기본 엔진 선택
        stt_eng_row = tk.Frame(clova_card, bg=CARD_BG)
        stt_eng_row.pack(fill="x", pady=(0, 4))
        tk.Label(stt_eng_row, text="기본 STT 엔진:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(side="left")
        self._stt_engine_var = tk.StringVar(value=self._cfg.get("stt_engine", "gemini"))
        tk.Radiobutton(stt_eng_row, text="Gemini",
                       variable=self._stt_engine_var, value="gemini",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       command=self._save_stt_engine).pack(side="left", padx=(10, 4))
        tk.Radiobutton(stt_eng_row, text="CLOVA Speech (권장)",
                       variable=self._stt_engine_var, value="clova",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       command=self._save_stt_engine).pack(side="left", padx=4)
        tk.Radiobutton(stt_eng_row, text="ChatGPT (Whisper)",
                       variable=self._stt_engine_var, value="chatgpt",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       command=self._save_stt_engine).pack(side="left", padx=4)

        clova_btn_row = tk.Frame(clova_card, bg=CARD_BG)
        clova_btn_row.pack(pady=4)
        self._btn(clova_btn_row, "저장", ACCENT,
                  self._save_clova_keys, w=8).pack(side="left", padx=4)
        self._btn(clova_btn_row, "연결 테스트", SUCCESS,
                  self._test_clova, w=12).pack(side="left", padx=4)
        self._btn(clova_btn_row, "🌐 NCP 콘솔", TEXT_LIGHT,
                  lambda: __import__("webbrowser").open(
                      "https://console.ncloud.com/ai-service/clovaSpeech"),
                  w=12).pack(side="left", padx=4)

        self._clova_status_var = tk.StringVar(value="")
        tk.Label(clova_card, textvariable=self._clova_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()
        tk.Label(clova_card,
                 text="▶ console.ncloud.com → AI Service → CLOVA Speech에서 API 키를 발급받으세요.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(4, 0))
        tk.Label(clova_card,
                 text="  장시간 회의 녹음도 청크 분할로 안정적 처리 (타임아웃 없음)",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w")

        # ─ Claude API ───────────────────────────────────
        self._card(inner, "🤖 Claude API 설정 (Anthropic)").pack(fill="x", **pad)
        cl_card = self._last_card

        tk.Label(cl_card, text="Claude API 키:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(anchor="w")
        self._cl_key_var = tk.StringVar(value=self._cfg.get("claude_api_key", ""))
        cl_entry_row = tk.Frame(cl_card, bg=CARD_BG)
        cl_entry_row.pack(fill="x", pady=4)
        self._cl_entry = tk.Entry(
            cl_entry_row, textvariable=self._cl_key_var,
            width=52, font=FONT_BODY, show="*")
        self._cl_entry.pack(side="left")
        self._cl_show = False
        self._btn(cl_entry_row, "👁", TEXT_LIGHT,
                  self._toggle_cl_key_vis, w=3).pack(side="left", padx=4)

        cl_btn_row = tk.Frame(cl_card, bg=CARD_BG)
        cl_btn_row.pack(pady=6)
        self._btn(cl_btn_row, "저장", ACCENT,
                  self._save_cl_key, w=8).pack(side="left", padx=4)
        self._btn(cl_btn_row, "연결 테스트", SUCCESS,
                  self._test_cl, w=12).pack(side="left", padx=4)
        self._cl_status_var = tk.StringVar(value="")
        tk.Label(cl_card, textvariable=self._cl_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()
        tk.Label(cl_card,
                 text="▶ console.anthropic.com 에서 API 키를 발급받으세요.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(4, 0))
        tk.Label(cl_card,
                 text="  입력 시 변환 옵션에서 'Claude' 엔진을 선택할 수 있습니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w")

        # ─ ChatGPT API ──────────────────────────────────
        self._card(inner, "🤖 ChatGPT API 설정 (OpenAI)").pack(fill="x", **pad)
        gpt_card = self._last_card

        tk.Label(gpt_card, text="OpenAI API 키:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(anchor="w")
        self._gpt_key_var = tk.StringVar(value=self._cfg.get("chatgpt_api_key", ""))
        gpt_entry_row = tk.Frame(gpt_card, bg=CARD_BG)
        gpt_entry_row.pack(fill="x", pady=4)
        self._gpt_entry = tk.Entry(
            gpt_entry_row, textvariable=self._gpt_key_var,
            width=52, font=FONT_BODY, show="*")
        self._gpt_entry.pack(side="left")
        self._gpt_show = False
        self._btn(gpt_entry_row, "👁", TEXT_LIGHT,
                  self._toggle_gpt_key_vis, w=3).pack(side="left", padx=4)

        gpt_btn_row = tk.Frame(gpt_card, bg=CARD_BG)
        gpt_btn_row.pack(pady=6)
        self._btn(gpt_btn_row, "저장", ACCENT,
                  self._save_gpt_key, w=8).pack(side="left", padx=4)
        self._btn(gpt_btn_row, "연결 테스트", SUCCESS,
                  self._test_gpt, w=12).pack(side="left", padx=4)
        self._btn(gpt_btn_row, "🌐 platform.openai.com", TEXT_LIGHT,
                  lambda: webbrowser.open("https://platform.openai.com/api-keys"),
                  w=22).pack(side="left", padx=4)

        # 회의록 요약 API 선택
        ttk.Separator(gpt_card).pack(fill="x", pady=(8, 4))
        sum_api_row = tk.Frame(gpt_card, bg=CARD_BG)
        sum_api_row.pack(fill="x", pady=4)
        tk.Label(sum_api_row, text="회의록 요약 API:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(side="left")
        self._summary_engine_var = tk.StringVar(
            value=self._cfg.get("summary_engine", "gemini"))
        for label, val in [("Gemini", "gemini"), ("Claude", "claude"), ("ChatGPT", "chatgpt")]:
            has_key = bool(self._cfg.get({
                "gemini": "gemini_api_key",
                "claude": "claude_api_key",
                "chatgpt": "chatgpt_api_key"
            }[val], "").strip())
            state = "normal"
            tk.Radiobutton(sum_api_row, text=label,
                           variable=self._summary_engine_var, value=val,
                           bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                           command=self._save_summary_engine).pack(side="left", padx=(10, 2))

        self._gpt_status_var = tk.StringVar(value="")
        tk.Label(gpt_card, textvariable=self._gpt_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()
        tk.Label(gpt_card,
                 text="▶ platform.openai.com → API Keys에서 키를 발급받으세요.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(4, 0))
        tk.Label(gpt_card,
                 text="  입력 시 STT 엔진과 AI 요약 엔진에서 'ChatGPT' 선택 가능",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w")

        # ─ 커스텀 프롬프트 ──────────────────────────────
        self._card(inner, "🎯 요약 커스텀 프롬프트").pack(fill="x", **pad)
        cp_card = self._last_card

        self._cp_enabled_var = tk.BooleanVar(value=self._cfg.get("custom_prompt_enabled", False))
        tk.Checkbutton(cp_card, text="✅ 활성화 — 아래 지시사항을 요약 프롬프트에 추가합니다",
                       variable=self._cp_enabled_var, bg=CARD_BG, font=FONT_BODY,
                       activebackground=CARD_BG).pack(anchor="w", pady=(0, 6))

        tk.Label(cp_card, text="현재 지시사항:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT).pack(anchor="w")
        self._cp_text = scrolledtext.ScrolledText(
            cp_card, height=4, font=FONT_BODY, wrap="word",
            bg="#FAFAFA", relief="solid", bd=1)
        self._cp_text.insert("1.0", self._cfg.get("custom_prompt_text", ""))
        self._cp_text.pack(fill="x", pady=4)

        cp_btn_row1 = tk.Frame(cp_card, bg=CARD_BG)
        cp_btn_row1.pack(fill="x", pady=(0, 4))
        self._btn(cp_btn_row1, "저장", ACCENT, self._save_custom_prompt, w=8).pack(side="left", padx=4)
        self._btn(cp_btn_row1, "초기화", TEXT_LIGHT, self._reset_custom_prompt, w=8).pack(side="left", padx=4)

        cp_btn_row2 = tk.Frame(cp_card, bg=CARD_BG)
        cp_btn_row2.pack(fill="x")
        tk.Label(cp_btn_row2, text="템플릿:", font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT).pack(side="left")
        self._cp_tmpl_var = tk.StringVar()
        self._cp_tmpl_cb = ttk.Combobox(cp_btn_row2, textvariable=self._cp_tmpl_var,
                                        width=20, state="readonly", font=FONT_SMALL)
        self._refresh_prompt_templates()
        self._cp_tmpl_cb.pack(side="left", padx=4)
        self._btn(cp_btn_row2, "불러오기", TEXT_LIGHT,
                  self._load_prompt_template, w=8).pack(side="left", padx=2)
        self._btn(cp_btn_row2, "템플릿 저장", SUCCESS,
                  self._save_prompt_template, w=10).pack(side="left", padx=2)
        self._btn(cp_btn_row2, "삭제", DANGER,
                  self._delete_prompt_template, w=6).pack(side="left", padx=2)

        tk.Label(cp_card,
                 text='예: "기술 결정과 배포 일정을 강조해줘" | "결정사항을 목록으로 명확히 정리해줘"',
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(4, 0))

        # ─ Google Drive 설정 (A방식) ─────────────────────
        self._card(inner, "☁ Google Drive 자동 업로드 설정").pack(fill="x", **pad)
        drv_card = self._last_card

        # 설명 텍스트
        tk.Label(drv_card,
                 text="각 사용자가 본인의 Google Cloud 프로젝트에서 OAuth 자격증명을 발급하여 사용합니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT, wraplength=820, justify="left"
                 ).pack(anchor="w", pady=(0, 6))

        # 상태 표시
        self._drive_status_var = tk.StringVar(value="")
        self._drive_status_lbl = tk.Label(drv_card, textvariable=self._drive_status_var,
                                          font=FONT_BODY, bg=CARD_BG, fg=TEXT_LIGHT)
        self._drive_status_lbl.pack(anchor="w", pady=(0, 4))
        self._refresh_drive_status()

        # 자격증명 파일 행
        cred_row = tk.Frame(drv_card, bg=CARD_BG)
        cred_row.pack(fill="x", pady=(0, 4))
        tk.Label(cred_row, text="OAuth 자격증명 파일:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=20, anchor="w").pack(side="left")
        self._cred_file_var = tk.StringVar(
            value=str(config.CREDENTIALS_FILE) if config.CREDENTIALS_FILE.exists()
            else "(파일 없음)")
        tk.Label(cred_row, textvariable=self._cred_file_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left", padx=4)
        self._btn(cred_row, "📂 파일 선택", ACCENT,
                  self._browse_credentials_file, w=12).pack(side="right")

        # 버튼 행
        drv_btn_row = tk.Frame(drv_card, bg=CARD_BG)
        drv_btn_row.pack(pady=4)
        self._btn(drv_btn_row, "🔐 Google 인증", SUCCESS,
                  self._drive_authenticate, w=14).pack(side="left", padx=4)
        self._btn(drv_btn_row, "🔓 연결 해제", DANGER,
                  self._drive_revoke, w=12).pack(side="left", padx=4)
        self._btn(drv_btn_row, "📋 설정 방법", TEXT_LIGHT,
                  self._show_drive_setup_guide, w=12).pack(side="left", padx=4)
        self._btn(drv_btn_row, "🌐 Google Cloud", TEXT_LIGHT,
                  lambda: webbrowser.open(
                      "https://console.cloud.google.com/apis/credentials"),
                  w=14).pack(side="left", padx=4)

        ttk.Separator(drv_card).pack(fill="x", pady=(8, 6))
        tk.Label(drv_card, text="📁 구글동기화 폴더 설정",
                 font=FONT_H2, bg=CARD_BG, fg=TEXT).pack(anchor="w", pady=(0, 4))

        # MP3 폴더 행
        mp3_row = tk.Frame(drv_card, bg=CARD_BG)
        mp3_row.pack(fill="x", pady=(0, 4))
        tk.Label(mp3_row, text="녹음(MP3) 폴더명:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=18, anchor="w").pack(side="left")
        self._drv_mp3_name_var = tk.StringVar(
            value=self._cfg.get("drive_mp3_folder_name", "녹음파일"))
        tk.Entry(mp3_row, textvariable=self._drv_mp3_name_var,
                 width=18, font=FONT_BODY).pack(side="left", padx=(0, 6))
        self._drv_mp3_id_var = tk.StringVar(
            value=self._cfg.get("drive_mp3_folder_id", ""))
        tk.Label(mp3_row, text="ID:", font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")
        tk.Entry(mp3_row, textvariable=self._drv_mp3_id_var,
                 width=20, font=FONT_SMALL, fg=TEXT_LIGHT).pack(side="left", padx=(2, 6))
        self._btn(mp3_row, "📁 생성/찾기", ACCENT,
                  self._ensure_mp3_folder, w=10).pack(side="left")

        # TXT 폴더 행
        txt_row = tk.Frame(drv_card, bg=CARD_BG)
        txt_row.pack(fill="x", pady=(0, 4))
        tk.Label(txt_row, text="요약(TXT) 폴더명:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=18, anchor="w").pack(side="left")
        self._drv_txt_name_var = tk.StringVar(
            value=self._cfg.get("drive_txt_folder_name", "회의록(요약)"))
        tk.Entry(txt_row, textvariable=self._drv_txt_name_var,
                 width=18, font=FONT_BODY).pack(side="left", padx=(0, 6))
        self._drv_txt_id_var = tk.StringVar(
            value=self._cfg.get("drive_txt_folder_id", ""))
        tk.Label(txt_row, text="ID:", font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")
        tk.Entry(txt_row, textvariable=self._drv_txt_id_var,
                 width=20, font=FONT_SMALL, fg=TEXT_LIGHT).pack(side="left", padx=(2, 6))
        self._btn(txt_row, "📁 생성/찾기", ACCENT,
                  self._ensure_txt_folder, w=10).pack(side="left")

        # 폴더 상태 레이블 + 일괄 저장
        self._drv_folder_status_var = tk.StringVar(value="")
        tk.Label(drv_card, textvariable=self._drv_folder_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w")
        folder_btn_row = tk.Frame(drv_card, bg=CARD_BG)
        folder_btn_row.pack(anchor="w", pady=(4, 2))
        self._btn(folder_btn_row, "폴더 설정 저장", ACCENT,
                  self._save_drive_folder_settings, w=14).pack(side="left", padx=4)
        self._btn(folder_btn_row, "🚀 두 폴더 한번에 생성", SUCCESS,
                  self._ensure_both_folders, w=18).pack(side="left", padx=4)

        tk.Label(drv_card,
                 text="  ↑ Google 인증 후 위 버튼으로 내 Drive에 폴더를 자동 생성/연결하세요.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(0, 4))

        ttk.Separator(drv_card).pack(fill="x", pady=(4, 6))

        # 자동 업로드 체크
        auto_row = tk.Frame(drv_card, bg=CARD_BG)
        auto_row.pack(anchor="w", pady=(4, 0))
        self._drive_auto_var = tk.BooleanVar(
            value=self._cfg.get("drive_auto_upload", True))
        tk.Checkbutton(auto_row,
                       text="변환 완료 후 Google Drive에 자동 업로드",
                       variable=self._drive_auto_var, bg=CARD_BG, font=FONT_BODY,
                       activebackground=CARD_BG,
                       command=self._save_drive_auto_setting).pack(side="left")

        # ─ 저장 경로 설정 (v3 — 3폴더 독립 구조) ─────────
        self._card(inner, "📁 PC 저장 폴더 설정").pack(fill="x", **pad)
        path_card = self._last_card

        tk.Label(path_card,
                 text="각 폴더의 저장 경로를 독립적으로 지정할 수 있습니다. (📂 찾아보기로 전체 경로 선택)",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(0, 8))

        for _lbl, _cfg_key, _default_dir in [
            ("① MP3 녹음파일",  "mp3_full_path",  str(config.MP3_SAVE_DIR)),
            ("② STT 변환본",    "stt_full_path",  str(config.STT_SAVE_DIR)),
            ("③ 회의록 요약",   "sum_full_path",  str(config.SUMMARY_SAVE_DIR)),
        ]:
            _row = tk.Frame(path_card, bg=CARD_BG)
            _row.pack(fill="x", pady=4)
            tk.Label(_row, text=_lbl + ":", font=FONT_BODY,
                     bg=CARD_BG, fg=TEXT, width=14, anchor="w").pack(side="left")
            _var = tk.StringVar(value=self._cfg.get(_cfg_key, _default_dir))
            tk.Entry(_row, textvariable=_var, font=FONT_SMALL, width=34,
                     state="readonly").pack(side="left", padx=4)

            def _make_browse(v=_var, k=_cfg_key):
                def _browse():
                    d = filedialog.askdirectory(title="폴더 선택", initialdir=v.get())
                    if d:
                        v.set(d)
                        self._cfg[k] = d
                        config.save_config(self._cfg)
                        config.reload_paths()
                return _browse
            self._btn(_row, "📂 찾아보기", ACCENT, _make_browse(), w=10).pack(side="left", padx=2)

        # 하위 호환 stub 속성 (다른 메서드 참조 대비)
        self._rec_dir_var    = tk.StringVar(value=str(config.RECORDING_BASE))
        self._mp3_sub_var    = tk.StringVar()
        self._stt_sub_var    = tk.StringVar()
        self._sum_sub_var    = tk.StringVar()
        self._audio_sub_var  = self._mp3_sub_var
        self._mp3_path_lbl   = tk.Label(path_card, bg=CARD_BG)
        self._stt_path_lbl   = tk.Label(path_card, bg=CARD_BG)
        self._sum_path_lbl   = tk.Label(path_card, bg=CARD_BG)
        self._audio_path_lbl = self._mp3_path_lbl

        appdata_row = tk.Frame(path_card, bg=CARD_BG)
        appdata_row.pack(fill="x", pady=(6, 2))
        tk.Label(appdata_row, text="앱 데이터:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        tk.Label(appdata_row, text=str(config.APP_DATA_DIR),
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")

        # ─ Obsidian 연동 설정 ────────────────────────────
        self._card(inner, "📓 Obsidian 연동 설정").pack(fill="x", **pad)
        obs_card = self._last_card

        tk.Label(obs_card,
                 text="회의록 완료 후 Obsidian 볼트 폴더에 자동으로 노트를 생성합니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(0, 6))

        # 자동 저장 체크박스
        self._obs_auto_var = tk.BooleanVar(value=self._cfg.get("obsidian_auto_save", True))
        tk.Checkbutton(obs_card,
                       text="✅ 회의록 완료 후 Obsidian에 자동 저장",
                       variable=self._obs_auto_var, bg=CARD_BG, font=FONT_BODY,
                       activebackground=CARD_BG,
                       command=lambda: self._save_obs_setting()).pack(anchor="w", pady=(0, 4))

        # Obsidian 경로 설정
        obs_path_row = tk.Frame(obs_card, bg=CARD_BG)
        obs_path_row.pack(fill="x", pady=2)
        tk.Label(obs_path_row, text="저장 폴더:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=10, anchor="w").pack(side="left")
        self._obs_dir_var = tk.StringVar(
            value=self._cfg.get("obsidian_meeting_dir",
                                r"C:\Users\anton\Documents\Obsidian_KRUN_Antonio\5. 회의록"))
        tk.Entry(obs_path_row, textvariable=self._obs_dir_var,
                 font=FONT_SMALL, width=38, state="readonly").pack(side="left", padx=4)

        def _browse_obs():
            d = filedialog.askdirectory(title="Obsidian 회의록 폴더 선택",
                                        initialdir=self._obs_dir_var.get())
            if d:
                self._obs_dir_var.set(d)
                self._save_obs_setting()
        self._btn(obs_path_row, "📂 찾아보기", ACCENT, _browse_obs, w=10).pack(side="left", padx=2)

        tk.Label(obs_card,
                 text="※ 저장 파일명 형식: YYMMDD 기업명 IR.md  (예: 260408 서메어 IR.md)",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(4, 0))

        # ─ 로컬 프린터 설정 ──────────────────────────────
        self._card(inner, "🖨 로컬 프린터 설정").pack(fill="x", **pad)
        net_card = self._last_card

        tk.Label(net_card,
                 text="PC에 연결된 프린터를 선택하여 기본 인쇄 프린터로 지정합니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w", pady=(0, 4))

        self._default_printer_var = tk.StringVar(value="프린터 목록 로딩 중...")
        tk.Label(net_card, textvariable=self._default_printer_var,
                 font=FONT_BODY, bg=CARD_BG, fg=SUCCESS).pack(anchor="w", pady=(0, 4))

        prt_list_frame = tk.Frame(net_card, bg=CARD_BG)
        prt_list_frame.pack(fill="x", pady=4)
        self._printer_listbox = tk.Listbox(
            prt_list_frame, height=5, font=FONT_BODY,
            selectmode="single", relief="solid", bd=1,
            bg="#FAFAFA", fg=TEXT)
        prt_sb = ttk.Scrollbar(prt_list_frame, orient="vertical",
                                command=self._printer_listbox.yview)
        self._printer_listbox.configure(yscrollcommand=prt_sb.set)
        self._printer_listbox.pack(side="left", fill="x", expand=True)
        prt_sb.pack(side="right", fill="y")

        prt_btn_row = tk.Frame(net_card, bg=CARD_BG)
        prt_btn_row.pack(pady=6)
        self._btn(prt_btn_row, "🔄 목록 새로고침", ACCENT,
                  self._refresh_printer_list, w=14).pack(side="left", padx=4)
        self._btn(prt_btn_row, "✅ 기본 프린터로 설정", SUCCESS,
                  self._set_default_printer, w=18).pack(side="left", padx=4)

        self._net_printer_status_var = tk.StringVar(value="")
        tk.Label(net_card, textvariable=self._net_printer_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="w")

        # 하위 호환 stub 변수
        self._net_printer_ip_var   = tk.StringVar()
        self._net_printer_name_var = tk.StringVar()

        self.after(300, self._refresh_printer_list)

    # ════════════════════════════════════════════════════
    # 첫 실행 마법사
    # ════════════════════════════════════════════════════
    def _show_first_run_wizard(self):
        """API 키 없을 때 첫 실행 설정 마법사"""
        dlg = tk.Toplevel(self)
        dlg.title("🎙 처음 오셨군요!  빠른 초기 설정")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus_set()

        # 창 가운데 배치
        self.update_idletasks()
        w, h = 540, 540
        x = self.winfo_x() + self.winfo_width() // 2 - w // 2
        y = self.winfo_y() + self.winfo_height() // 2 - h // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.configure(bg=CARD_BG)

        # 타이틀
        tk.Label(dlg, text="🎙 회의녹음요약 초기 설정",
                 font=FONT_TITLE, bg=CARD_BG, fg=TEXT).pack(pady=(20, 4))
        tk.Label(dlg, text="아래 정보를 입력하면 바로 사용 가능합니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=12)

        # ─ Step 1: Gemini API 키 ───────────────────────
        frm1 = tk.LabelFrame(dlg, text="  Step 1. Gemini API 키 (필수)  ",
                              font=FONT_BODY, bg=CARD_BG, fg=TEXT, padx=14, pady=10)
        frm1.pack(fill="x", padx=20, pady=(0, 8))

        entry_row = tk.Frame(frm1, bg=CARD_BG)
        entry_row.pack(fill="x")
        wiz_key_var = tk.StringVar(value=self._cfg.get("gemini_api_key", ""))
        wiz_entry = tk.Entry(entry_row, textvariable=wiz_key_var,
                             width=36, font=FONT_BODY, show="*")
        wiz_entry.pack(side="left")

        wiz_show = [False]
        def _toggle_vis():
            wiz_show[0] = not wiz_show[0]
            wiz_entry.config(show="" if wiz_show[0] else "*")
        self._btn(entry_row, "👁", TEXT_LIGHT, _toggle_vis, w=3).pack(side="left", padx=4)

        guide_row = tk.Frame(frm1, bg=CARD_BG)
        guide_row.pack(fill="x", pady=(6, 0))
        self._btn(guide_row, "📋 발급 방법 보기", TEXT_LIGHT,
                  self._show_api_guide, w=16).pack(side="left")
        self._btn(guide_row, "🌐 aistudio.google.com", ACCENT,
                  lambda: webbrowser.open("https://aistudio.google.com/apikey"),
                  w=22).pack(side="left", padx=8)

        # ─ Step 2: 저장 폴더 ───────────────────────────
        frm2 = tk.LabelFrame(dlg, text="  Step 2. 녹음 저장 폴더  ",
                              font=FONT_BODY, bg=CARD_BG, fg=TEXT, padx=14, pady=10)
        frm2.pack(fill="x", padx=20, pady=(0, 8))

        default_dir = self._cfg.get("recording_dir",
                                    str(Path.home() / "Documents" / "Meeting recording"))
        wiz_dir_var = tk.StringVar(value=default_dir)
        dir_row = tk.Frame(frm2, bg=CARD_BG)
        dir_row.pack(fill="x")
        tk.Entry(dir_row, textvariable=wiz_dir_var, width=36,
                 font=FONT_SMALL, state="readonly").pack(side="left")

        def _pick_dir():
            d = filedialog.askdirectory(title="녹음 저장 폴더 선택",
                                        initialdir=wiz_dir_var.get())
            if d:
                wiz_dir_var.set(d)
        self._btn(dir_row, "📂 변경", ACCENT, _pick_dir, w=8).pack(side="left", padx=6)

        # ─ Step 3: Google Drive (선택) ────────────────
        frm3 = tk.LabelFrame(dlg, text="  Step 3. Google Drive 자동 업로드 (선택)  ",
                              font=FONT_BODY, bg=CARD_BG, fg=TEXT, padx=14, pady=10)
        frm3.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(frm3,
                 text="변환 완료 후 자동으로 Google Drive에 업로드할 수 있습니다.\n"
                      "나중에 '설정' 탭에서도 구성할 수 있습니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT, justify="left").pack(anchor="w")

        drv_btn_row = tk.Frame(frm3, bg=CARD_BG)
        drv_btn_row.pack(fill="x", pady=(6, 0))
        self._btn(drv_btn_row, "📋 Drive 설정 방법", TEXT_LIGHT,
                  self._show_drive_setup_guide, w=18).pack(side="left")
        self._btn(drv_btn_row, "🌐 Cloud Console", TEXT_LIGHT,
                  lambda: webbrowser.open(
                      "https://console.cloud.google.com/apis/credentials"),
                  w=16).pack(side="left", padx=6)

        # ─ 버튼 ─────────────────────────────────────
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=8)
        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=4)

        def _save_and_start():
            key = wiz_key_var.get().strip()
            if not key:
                messagebox.showwarning("알림", "Gemini API 키를 입력해주세요.\n"
                                       "(aistudio.google.com에서 무료 발급 가능)",
                                       parent=dlg)
                return
            self._cfg["gemini_api_key"] = key
            self._cfg["recording_dir"] = wiz_dir_var.get()
            config.save_config(self._cfg)
            config.reload_paths()
            # 설정 탭의 Entry도 갱신
            if hasattr(self, "_gem_key_var"):
                self._gem_key_var.set(key)
            if hasattr(self, "_rec_dir_var"):
                self._rec_dir_var.set(wiz_dir_var.get())
            dlg.destroy()
            messagebox.showinfo("설정 완료", "✅ 초기 설정이 완료되었습니다!\n\n"
                                "이제 녹음/변환 탭에서 바로 시작하세요.\n\n"
                                "☁ Google Drive 연동은 '설정' 탭에서 구성하세요.")

        def _skip():
            dlg.destroy()

        self._btn(btn_row, "✅ 설정 저장 & 시작", SUCCESS,
                  _save_and_start, w=20).pack(side="left", padx=6)
        self._btn(btn_row, "나중에 설정", TEXT_LIGHT,
                  _skip, w=12).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", _skip)

    def _show_api_guide(self):
        """Gemini API 키 발급 상세 안내 팝업"""
        dlg = tk.Toplevel(self)
        dlg.title("📋 Gemini API 키 발급 방법")
        dlg.resizable(True, True)
        dlg.grab_set()

        self.update_idletasks()
        w, h = 540, 460
        x = self.winfo_x() + self.winfo_width() // 2 - w // 2
        y = self.winfo_y() + self.winfo_height() // 2 - h // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.configure(bg=CARD_BG)

        tk.Label(dlg, text="📋 Gemini API 키 발급 방법 (무료)",
                 font=FONT_H2, bg=CARD_BG, fg=TEXT).pack(pady=(16, 4), padx=20, anchor="w")
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=6)

        guide_text = (
            "① 아래 버튼 클릭 또는 aistudio.google.com 직접 접속\n\n"
            "② Google 계정으로 로그인\n\n"
            "③ 좌측 메뉴에서 'Get API key' 클릭\n\n"
            "④ 'API 키 만들기' 버튼 클릭\n\n"
            "⑤ 프로젝트 선택 (없으면 '새 프로젝트 만들기' 클릭)\n\n"
            "⑥ 생성된 API 키 복사\n\n"
            "⑦ 이 앱의 설정 탭 → Gemini API 키 입력란에 붙여넣기 → 저장\n\n"
            "────────────────────────────────\n\n"
            "✅ 무료 사용량\n"
            "   • 분당 15회 요청,  하루 1,500회 요청\n"
            "   • 회의 녹음 요약 용도로 충분한 수준\n\n"
            "⚠ 주의사항\n"
            "   • API 키는 비밀번호처럼 취급하세요\n"
            "   • 타인에게 공유하지 마세요\n"
            "   • 유출 시 aistudio.google.com에서 즉시 삭제/재발급"
        )

        txt = scrolledtext.ScrolledText(
            dlg, font=FONT_BODY, wrap="word", bg="#FAFAFA",
            relief="solid", bd=1, height=16)
        txt.pack(fill="both", expand=True, padx=20, pady=4)
        txt.insert("1.0", guide_text)
        txt.config(state="disabled")

        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=10)
        self._btn(btn_row, "🌐 aistudio.google.com 열기", ACCENT,
                  lambda: webbrowser.open("https://aistudio.google.com/apikey"),
                  w=28).pack(side="left", padx=6)
        self._btn(btn_row, "닫기", TEXT_LIGHT,
                  dlg.destroy, w=8).pack(side="left", padx=6)

    # ════════════════════════════════════════════════════
    # 녹음 기능
    # ════════════════════════════════════════════════════
    def _refresh_mic_list(self):
        devices = rec_mod.get_available_devices()
        names   = ["기본 마이크"] + [d["name"] for d in devices]
        self._mic_cb["values"] = names
        self._mic_cb.current(0)
        self._mic_devices = devices

    def _toggle_record(self):
        if self._recorder.state == "idle":
            idx = None
            sel = self._mic_cb.current()
            if sel > 0 and hasattr(self, "_mic_devices"):
                idx = self._mic_devices[sel - 1]["index"]
            ok, msg = self._recorder.start_recording(device_index=idx)
            if ok:
                self._btn_rec.config(text="● 녹음 중...", bg=DANGER)
                self._btn_pause.config(state="normal")
                self._btn_stop.config(state="normal")
                self._set_sleep_prevention(True)   # 🔒 절전 방지 ON
            else:
                messagebox.showerror("오류", msg)

    def _toggle_pause(self):
        if self._recorder.state == "recording":
            self._recorder.pause_recording()
            self._btn_pause.config(text="▶ 재개")
            self._btn_rec.config(text="⏸ 일시정지 중", bg=WARNING)
        elif self._recorder.state == "paused":
            self._recorder.resume_recording()
            self._btn_pause.config(text="⏸ 일시정지")
            self._btn_rec.config(text="● 녹음 중...", bg=DANGER)

    def _stop_record(self):
        ok, result = self._recorder.stop_recording()
        self._btn_rec.config(text="● 녹음 시작", bg=ACCENT)
        self._btn_pause.config(text="⏸ 일시정지", state="disabled")
        self._btn_stop.config(state="disabled")
        self._set_sleep_prevention(False)   # 🔓 절전 방지 OFF (녹음 종료)
        if not ok:
            messagebox.showerror("오류", result)
            return

        # MP3 변환은 백그라운드 스레드에서 실행 (FFmpeg가 UI를 블록하지 않도록)
        default_name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_녹음"
        self._cur_file_var.set("MP3 변환 중...")
        self._btn_rec.config(state="disabled")
        self._btn_pipeline.config(state="disabled")

        def _convert():
            ok2, out = self._recorder.save_as_mp3(
                result, str(config.MP3_SAVE_DIR), default_name)
            self.after(0, lambda: self._on_mp3_ready(ok2, out))

        threading.Thread(target=_convert, daemon=True).start()

    def _on_mp3_ready(self, ok: bool, out: str):
        """MP3 변환 완료 콜백 (메인 스레드에서 실행)"""
        self._btn_rec.config(state="normal")
        self._btn_pipeline.config(state="normal")
        if ok:
            self._current_mp3 = out
            self._cur_file_var.set(out)
            messagebox.showinfo("녹음 완료", f"✅ 파일 저장됨:\n{out}")
        else:
            self._cur_file_var.set("(변환 실패)")
            messagebox.showerror("MP3 변환 오류", out)

    def _pick_audio_file(self):
        path = filedialog.askopenfilename(
            title="음성 파일 선택",
            filetypes=[("오디오 파일",
                        "*.mp3 *.wav *.m4a *.mp4 *.ogg *.flac"),
                       ("모든 파일", "*.*")])
        if path:
            self._current_mp3 = path
            self._cur_file_var.set(path)

    # ════════════════════════════════════════════════════
    # 자동화 파이프라인
    # ════════════════════════════════════════════════════

    # ── Obsidian 이전 회의록 링크 관리 ──────────────────────────────
    def _obs_link_add(self):
        """이전 회의록 Obsidian 링크 행 추가"""
        var = tk.StringVar()
        row = tk.Frame(self._obs_links_frame, bg=CARD_BG)
        row.pack(fill="x", pady=1)

        entry = tk.Entry(row, textvariable=var, font=FONT_SMALL, width=60,
                         bg="#FAFAFA", relief="solid", bd=1)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        def _browse():
            path = filedialog.askopenfilename(
                title="Obsidian 이전 회의록 선택",
                filetypes=[("Markdown 파일", "*.md"), ("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
            )
            if path:
                var.set(path)

        def _remove():
            row.destroy()
            if var in self._obs_link_vars:
                idx = self._obs_link_vars.index(var)
                self._obs_link_vars.pop(idx)
                self._obs_link_rows.pop(idx)

        self._btn(row, "📂", "#7F8C8D", _browse, w=3).pack(side="left", padx=2)
        self._btn(row, "✕", DANGER, _remove, w=3).pack(side="left", padx=2)

        self._obs_link_vars.append(var)
        self._obs_link_rows.append(row)

    def _get_obsidian_notes_content(self) -> str:
        """입력된 Obsidian 링크 경로에서 파일 내용을 읽어 문자열로 반환"""
        parts = []
        for var in self._obs_link_vars:
            path = var.get().strip()
            if not path:
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read().strip()
                fname = os.path.basename(path)
                parts.append(f"### [{fname}]\n{content}")
            except Exception as e:
                parts.append(f"### [{path}]\n⚠ 파일 읽기 실패: {e}")
        return "\n\n".join(parts)

    def _import_txt_and_summarize(self):
        """[📎 TXT 파일 첨부] 버튼 → STT 결과 txt 불러와 요약 파이프라인 시작"""
        if self._processing:
            messagebox.showwarning("알림", "이미 처리 중입니다. 완료 후 시작해주세요.")
            return

        # ① txt 파일 선택
        path = filedialog.askopenfilename(
            title="STT 결과 TXT 파일 선택",
            filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
        )
        if not path:
            return

        # ② 파일 읽기
        try:
            with open(path, "r", encoding="utf-8") as f:
                stt_text = f.read().strip()
        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="cp949") as f:
                    stt_text = f.read().strip()
            except Exception as e:
                messagebox.showerror("파일 오류", f"파일을 읽을 수 없습니다:\n{e}")
                return
        except Exception as e:
            messagebox.showerror("파일 오류", f"파일을 읽을 수 없습니다:\n{e}")
            return

        if not stt_text:
            messagebox.showwarning("알림", "파일이 비어 있습니다.")
            return

        # ③ STT 박스에 내용 표시
        self._stt_box.delete("1.0", "end")
        self._stt_box.insert("1.0", stt_text)
        self._stt_text = stt_text
        self._stt_status_var.set(f"✅ TXT 불러오기 완료: {Path(path).name}  ({len(stt_text):,}자)")
        self._set_prog(self._stt_prog, 100)
        self._current_mp3 = None   # 녹음 파일 없음 (txt 첨부 모드)

        # ④ 요약 옵션 다이얼로그 (▶ 변환 시작과 동일)
        dlg = tk.Toplevel(self)
        dlg.title("요약 옵션 선택")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus_set()

        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() // 2 - 250
        y = self.winfo_y() + self.winfo_height() // 2 - 230
        dlg.geometry(f"520x540+{x}+{y}")
        dlg.configure(bg=CARD_BG)

        tk.Label(dlg, text="요약 옵션 선택", font=FONT_H2,
                 bg=CARD_BG, fg=TEXT).pack(pady=(12, 2))
        tk.Label(dlg, text=f"파일: {Path(path).name}  ({len(stt_text):,}자)",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(pady=(0, 2))
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=4)

        # 요약 방식
        frm1 = tk.LabelFrame(dlg, text="  요약 방식  ", font=FONT_BODY,
                              bg=CARD_BG, fg=TEXT, padx=12, pady=6)
        frm1.pack(fill="x", padx=20, pady=4)
        sum_mode_var = tk.StringVar(value=self._pipeline_sum_mode)
        _FONT_OPT = ("맑은 고딕", 11)
        tk.Radiobutton(frm1, text="화자 중심 — 참석자별 발언 정리",
                       variable=sum_mode_var, value="speaker",
                       bg=CARD_BG, font=_FONT_OPT, activebackground=CARD_BG).pack(anchor="w", pady=1)
        tk.Radiobutton(frm1, text="다자간 협의 — 기관협의·다자간 공식회의·다자간 네트워킹",
                       variable=sum_mode_var, value="topic",
                       bg=CARD_BG, font=_FONT_OPT, activebackground=CARD_BG).pack(anchor="w", pady=1)
        tk.Radiobutton(frm1, text="회의록(업무) — 직전 투자심사 외부 미팅·투자업체 사후관리",
                       variable=sum_mode_var, value="formal_md",
                       bg=CARD_BG, font=_FONT_OPT, activebackground=CARD_BG).pack(anchor="w", pady=1)
        tk.Radiobutton(frm1, text="IR 미팅회의록 ★신규★ — 피투자사 IR 미팅 전문 정리",
                       variable=sum_mode_var, value="ir_md",
                       bg=CARD_BG, font=_FONT_OPT, fg=SUCCESS, activebackground=CARD_BG).pack(anchor="w", pady=1)
        tk.Radiobutton(frm1, text="강의 요약 — 소주제별 논리적 정리, 신앙/업무 강의 자동 적응",
                       variable=sum_mode_var, value="lecture_md",
                       bg=CARD_BG, font=_FONT_OPT, activebackground=CARD_BG).pack(anchor="w", pady=1)
        tk.Radiobutton(frm1, text="네트워킹(티타임) — 티타임·비공식 네트워킹 대화 정리",
                       variable=sum_mode_var, value="flow",
                       bg=CARD_BG, font=_FONT_OPT, fg=TEXT, activebackground=CARD_BG).pack(anchor="w", pady=1)
        tk.Radiobutton(frm1, text="전화통화 메모 — 통화 내용 주제별 요약 + 질의응답",
                       variable=sum_mode_var, value="phone",
                       bg=CARD_BG, font=_FONT_OPT, fg=TEXT, activebackground=CARD_BG).pack(anchor="w", pady=1)

        # AI 엔진
        frm_ai = tk.LabelFrame(dlg, text="  AI 요약 엔진  ", font=FONT_BODY,
                               bg=CARD_BG, fg=TEXT, padx=12, pady=6)
        frm_ai.pack(fill="x", padx=20, pady=4)
        ai_var = tk.StringVar(value=self._pipeline_ai_engine)
        has_claude  = bool(self._cfg.get("claude_api_key", "").strip())
        has_chatgpt = bool(self._cfg.get("chatgpt_api_key", "").strip())
        tk.Radiobutton(frm_ai, text="Gemini (Google)",
                       variable=ai_var, value="gemini",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm_ai,
                       text="Claude (Anthropic)" + ("" if has_claude else "  ← 설정 탭에서 API 키 입력"),
                       variable=ai_var, value="claude",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       state="normal" if has_claude else "disabled").pack(anchor="w")
        tk.Radiobutton(frm_ai,
                       text="ChatGPT (OpenAI)" + ("" if has_chatgpt else "  ← 설정 탭에서 API 키 입력"),
                       variable=ai_var, value="chatgpt",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       state="normal" if has_chatgpt else "disabled").pack(anchor="w")

        confirmed = {"ok": False}

        def _confirm():
            confirmed["ok"] = True
            self._pipeline_sum_mode  = sum_mode_var.get()
            self._pipeline_ai_engine = ai_var.get()
            dlg.destroy()
            # IR 미팅 모드 선택 시 기업명 입력 (혁신의숲 API 조회용)
            if self._pipeline_sum_mode == "ir_md":
                name = simpledialog.askstring(
                    "기업명 입력",
                    "혁신의숲 조회 기업명을 입력하세요:\n(정확한 법인명 입력 권장, 빈칸 시 API 조회 생략)",
                    parent=self,
                )
                self._pipeline_company_name = (name or "").strip()
            else:
                self._pipeline_company_name = ""

        def _cancel():
            dlg.destroy()

        ttk.Separator(dlg).pack(fill="x", padx=20, pady=8)
        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=10)
        b_start = self._btn(btn_row, "📋 요약 시작", "#8E44AD", _confirm, w=20)
        b_start.config(font=("맑은 고딕", 13, "bold"), pady=12)
        b_start.pack(side="left", padx=10)
        b_cancel = self._btn(btn_row, "취소", TEXT_LIGHT, _cancel, w=12)
        b_cancel.config(font=("맑은 고딕", 12), pady=12)
        b_cancel.pack(side="left", padx=8)
        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        self.wait_window(dlg)

        if not confirmed["ok"]:
            return

        # ⑤ 요약 실행 (STT 단계 건너뛰고 바로 요약)
        self._processing = True
        self._cancel_event.clear()
        self._btn_pipeline.config(state="disabled")
        self._btn_txt_import.config(state="disabled")
        self._btn_cancel.config(state="normal")
        self._btn_resummarize.config(state="disabled")
        self._sum_box.delete("1.0", "end")
        self._sum_status_var.set("")
        self._save_status_var.set("처리 중...")
        self._start_pipeline_summary(stt_text)

    def _start_pipeline(self):
        """[▶ 변환 시작] 버튼 → 파이프라인 시작"""
        if not self._current_mp3:
            messagebox.showwarning("알림", "녹음하거나 파일을 선택해주세요.")
            return

        # STT 엔진 선택 여부에 따라 키 유효성 검사
        stt_eng = self._pipeline_stt_engine
        if stt_eng == "clova":
            if not (self._cfg.get("clova_invoke_url", "").strip() and
                    self._cfg.get("clova_secret_key", "").strip()):
                messagebox.showwarning("알림",
                    "설정 탭에서 CLOVA Speech API 키(Invoke URL / Secret Key)를 먼저 입력해주세요.")
                self._nb.select(2)
                return
        else:
            api_key = self._cfg.get("gemini_api_key", "")
            if not api_key:
                messagebox.showwarning("알림", "설정 탭에서 Gemini API 키를 입력해주세요.")
                self._nb.select(2)
                return
        if self._processing:
            messagebox.showwarning("알림", "이미 처리 중입니다. 완료 후 시작해주세요.")
            return

        # ① 설정 탭의 기본값을 자동 적용 (팝업 없음 — F-06 영역 A 정책)
        self._pipeline_sum_mode   = self._cfg.get("summary_mode", "speaker")
        self._pipeline_ai_engine  = self._cfg.get("summary_engine", "gemini")
        self._pipeline_stt_engine = self._cfg.get("stt_engine", "clova")
        self._pipeline_rename_spk = False

        # IR 미팅 모드인 경우 기업명 입력 (혁신의숲 API 조회용)
        if self._pipeline_sum_mode == "ir_md":
            name = simpledialog.askstring(
                "기업명 입력",
                "혁신의숲 조회 기업명을 입력하세요:\n(정확한 법인명 입력 권장, 빈칸 시 API 조회 생략)",
                parent=self,
            )
            self._pipeline_company_name = (name or "").strip()
        else:
            self._pipeline_company_name = ""

        mode_label_map = {
            "speaker": "주간회의", "topic": "다자간 협의",
            "formal_md": "회의록(업무)", "ir_md": "IR미팅회의록",
            "lecture_md": "강의요약", "flow": "네트워킹(티타임)", "phone": "전화통화메모"
        }
        engine_label_map = {
            "gemini": "Gemini", "claude": "Claude", "chatgpt": "ChatGPT"
        }
        stt_label_map = {
            "gemini": "Gemini", "clova": "CLOVA Speech", "chatgpt": "ChatGPT(Whisper)"
        }
        mode_lbl   = mode_label_map.get(self._pipeline_sum_mode, self._pipeline_sum_mode)
        engine_lbl = engine_label_map.get(self._pipeline_ai_engine, self._pipeline_ai_engine)
        stt_lbl    = stt_label_map.get(self._pipeline_stt_engine, self._pipeline_stt_engine)
        self._stt_status_var.set(
            f"⚙ 설정 자동 적용 — STT: {stt_lbl} | 요약방식: {mode_lbl} | AI: {engine_lbl}"
            f"  (⚙ 설정 탭에서 변경)"
        )

        # ② STT 변환 시작
        self._set_sleep_prevention(True)   # 🔒 절전 방지 ON (STT 변환 시작)
        num_spk = self._spk_var.get()
        self._processing = True
        self._cancel_event.clear()
        self._btn_pipeline.config(state="disabled")
        self._btn_resummarize.config(state="disabled")
        self._btn_cancel.config(state="normal")
        self._stt_prog["value"] = 0
        self._stt_status_var.set("STT 변환 시작...")
        self._stt_box.delete("1.0", "end")
        self._sum_box.delete("1.0", "end")
        self._sum_status_var.set("")
        self._save_status_var.set("처리 중...")

        def run_stt():
            if self._pipeline_stt_engine == "clova":
                ok, text = clova.transcribe(
                    self._current_mp3,
                    invoke_url=self._cfg.get("clova_invoke_url", ""),
                    secret_key=self._cfg.get("clova_secret_key", ""),
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._stt_prog, v)),
                    num_speakers=num_spk,
                    cancel_event=self._cancel_event,
                    status_cb=lambda msg: self.after(0, lambda: self._stt_status_var.set(msg)),
                )
            else:
                ok, text = gemini.transcribe(
                    self._current_mp3,
                    self._cfg.get("gemini_api_key", ""),
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._stt_prog, v)),
                    num_speakers=num_spk,
                    speaker_names={},
                    cancel_event=self._cancel_event,
                    status_cb=lambda msg: self.after(0, lambda: self._stt_status_var.set(msg)),
                )
            self.after(0, lambda: self._on_pipeline_stt_done(ok, text))

        threading.Thread(target=run_stt, daemon=True).start()

    def _on_pipeline_stt_done(self, ok: bool, text: str):
        """② STT 완료 콜백"""
        if not ok:
            self._processing = False
            self._btn_pipeline.config(state="normal")
            self._btn_cancel.config(state="disabled")
            self._stt_status_var.set(f"❌ STT 실패: {text[:60]}")
            messagebox.showerror("STT 오류", text)
            return

        self._stt_text = text
        self._stt_box.delete("1.0", "end")
        self._stt_box.insert("1.0", text)
        self._stt_status_var.set("✅ STT 변환 완료!")
        self._set_prog(self._stt_prog, 100)
        self._btn_resummarize.config(state="normal")

        if self._pipeline_rename_spk:
            self._show_speaker_rename_dialog(text)
        else:
            self._start_pipeline_summary(text)

    def _show_speaker_rename_dialog(self, stt_text: str):
        """③ 화자 이름 입력 다이얼로그"""
        found = sorted(set(re.findall(r'\[화자(\d+)\]', stt_text)), key=int)
        if not found:
            n = self._spk_var.get()
            found = [str(i) for i in range(1, max(n, 1) + 1)] if n > 0 else ["1", "2"]

        dlg = tk.Toplevel(self)
        dlg.title("화자 이름 입력")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus_set()

        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() // 2 - 200
        y = self.winfo_y() + self.winfo_height() // 2 - 150
        dlg.geometry(f"400x{min(120 + len(found) * 44, 500)}+{x}+{y}")
        dlg.configure(bg=CARD_BG)

        tk.Label(dlg, text="화자 이름 입력",
                 font=FONT_H2, bg=CARD_BG, fg=TEXT).pack(pady=(14, 4))
        tk.Label(dlg, text="STT 결과에 표시될 이름을 입력하세요.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()
        ttk.Separator(dlg).pack(fill="x", padx=16, pady=6)

        entries = {}
        frm = tk.Frame(dlg, bg=CARD_BG)
        frm.pack(fill="x", padx=20)
        for num in found:
            row = tk.Frame(frm, bg=CARD_BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"화자{num}:", font=FONT_BODY,
                     bg=CARD_BG, fg=TEXT, width=8, anchor="w").pack(side="left")
            e = tk.Entry(row, font=FONT_BODY, width=22)
            e.insert(0, f"화자{num}")
            e.pack(side="left", padx=4)
            entries[num] = e

        def _apply():
            speaker_names = {int(k): v.get().strip() for k, v in entries.items()}
            updated = gemini.apply_speaker_names(stt_text, speaker_names)
            self._stt_text = updated
            self._stt_box.delete("1.0", "end")
            self._stt_box.insert("1.0", updated)
            dlg.destroy()
            self._start_pipeline_summary(updated)

        def _skip():
            dlg.destroy()
            self._start_pipeline_summary(stt_text)

        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=10)
        self._btn(btn_row, "✔ 적용", SUCCESS, _apply, w=10).pack(side="left", padx=6)
        self._btn(btn_row, "건너뛰기", TEXT_LIGHT, _skip, w=10).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", _skip)

    def _start_pipeline_summary(self, stt_text: str):
        """④ 요약 자동 시작"""
        if self._cancel_event.is_set():
            self._processing = False
            self._btn_pipeline.config(state="normal")
            self._btn_txt_import.config(state="normal")
            self._btn_cancel.config(state="disabled")
            self._sum_status_var.set("중단되었습니다.")
            return

        api_key = self._cfg.get("gemini_api_key", "")
        self._sum_prog["value"] = 0
        self._sum_status_var.set("요약 생성 중...")
        self._sum_box.delete("1.0", "end")

        # 커스텀 프롬프트 적용
        custom_inst = ""
        if self._cfg.get("custom_prompt_enabled") and self._cfg.get("custom_prompt_text"):
            custom_inst = self._cfg["custom_prompt_text"]

        prev_notes = self._get_obsidian_notes_content()

        def run_sum():
            if self._pipeline_ai_engine == "claude":
                cl_key = self._cfg.get("claude_api_key", "")
                ok, text = claude.summarize(
                    stt_text, cl_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_inst,
                )
            elif self._pipeline_ai_engine == "chatgpt":
                gpt_key = self._cfg.get("chatgpt_api_key", "")
                ok, text = self._summarize_with_chatgpt(
                    stt_text, gpt_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_inst,
                )
            else:
                ok, text = gemini.summarize(
                    stt_text, api_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_inst,
                    company_name=self._pipeline_company_name,
                    prev_notes=prev_notes,
                )
            self.after(0, lambda: self._on_pipeline_summary_done(ok, text, stt_text))

        threading.Thread(target=run_sum, daemon=True).start()

    def _on_pipeline_summary_done(self, ok: bool, text: str, stt_text: str):
        """④ 요약 완료 → ⑤ 파일명 입력 → ⑥ 로컬 저장"""
        self._processing = False
        self._set_sleep_prevention(False)   # 🔓 절전 방지 OFF (요약 완료)
        self._btn_pipeline.config(state="normal")
        self._btn_txt_import.config(state="normal")
        self._btn_cancel.config(state="disabled")

        if not ok:
            self._sum_status_var.set(f"❌ 요약 실패: {text[:60]}")
            messagebox.showerror("요약 오류", text)
            return

        # 요약 결과 표시
        self._summary_text = text
        self._sum_box.delete("1.0", "end")
        self._sum_box.insert("1.0", text)
        self._sum_status_var.set("✅ 요약 완료!")
        self._set_prog(self._sum_prog, 100)

        # ⑤ 파일명 입력 팝업
        default_name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_녹음"
        save_name = simpledialog.askstring(
            "파일명 입력",
            "저장할 파일명을 입력하세요 (확장자 제외):",
            initialvalue=default_name,
            parent=self,
        )
        if not save_name or not save_name.strip():
            save_name = default_name
        save_name = save_name.strip()

        # ⑥ 로컬 저장
        msgs = []
        mp3_path = self._current_mp3
        stt_path = sum_path = None
        self._current_sum_path = None

        if stt_text:
            ok2, path = fm.save_stt_text(stt_text, str(config.STT_SAVE_DIR),
                                         save_name + "_STT")
            if ok2:
                stt_path = path
                msgs.append(f"✅ STT 저장: {Path(path).name}")
            else:
                msgs.append(f"❌ STT 저장 실패: {path}")

        if text:
            ok3, path = fm.save_summary_text(text, str(config.SUMMARY_SAVE_DIR),
                                             save_name + "_회의록")
            if ok3:
                sum_path = path
                self._current_sum_path = path
                msgs.append(f"✅ 요약 저장: {Path(path).name}")
            else:
                msgs.append(f"❌ 요약 저장 실패: {path}")

        # ⑦ Google Drive 업로드 (인증된 경우 + 자동 업로드 설정 ON)
        drive_mp3_link = drive_stt_link = drive_sum_link = ""
        drv_status = gdrive.get_credentials_status()
        auto_upload = self._cfg.get("drive_auto_upload", True)

        if drv_status["status"] == "authenticated" and auto_upload:
            self._save_status_var.set("☁ Google Drive 업로드 중...")
            self.update()

            mp3_fid = self._cfg.get("drive_mp3_folder_id", "")
            txt_fid = self._cfg.get("drive_txt_folder_id", "")

            if not mp3_fid or not txt_fid:
                # 폴더 ID 미설정 시 자동 생성 후 업로드
                mp3_name = self._cfg.get("drive_mp3_folder_name", "녹음파일")
                txt_name = self._cfg.get("drive_txt_folder_name", "회의록(요약)")
                r = gdrive.init_drive_folders(mp3_name, txt_name)
                if r["mp3_ok"]:
                    mp3_fid = r["mp3_id"]
                    self._cfg["drive_mp3_folder_id"] = mp3_fid
                if r["txt_ok"]:
                    txt_fid = r["txt_id"]
                    self._cfg["drive_txt_folder_id"] = txt_fid
                config.save_config(self._cfg)

            _mp3_fid_snap = mp3_fid
            _txt_fid_snap = txt_fid

            def run_drive_upload():
                results = gdrive.upload_meeting_files(
                    mp3_path or "", stt_path or "", sum_path or "",
                    mp3_folder_id=_mp3_fid_snap,
                    txt_folder_id=_txt_fid_snap)
                self.after(0, lambda: self._on_drive_upload_done(
                    results, mp3_path, stt_path, sum_path,
                    save_name, stt_text, text, msgs))

            threading.Thread(target=run_drive_upload, daemon=True).start()
            return   # Drive 업로드 완료 후 콜백에서 DB 저장 및 팝업 표시

        # Drive 미연결 또는 자동 업로드 OFF → 바로 DB 저장
        if drv_status["status"] != "authenticated":
            msgs.append("☁ Drive 미연결 (로컬 저장만 완료)")
        elif not auto_upload:
            msgs.append("☁ Drive 자동 업로드 OFF")

        self._finalize_save(mp3_path, stt_path, sum_path, save_name,
                            stt_text, text, msgs,
                            drive_mp3_link, drive_stt_link, drive_sum_link)

    def _on_drive_upload_done(self, results: dict, mp3_path, stt_path, sum_path,
                               save_name, stt_text, text, msgs: list):
        """Drive 업로드 완료 콜백"""
        drive_mp3_link = drive_stt_link = drive_sum_link = ""

        label_map = {"mp3": "MP3", "stt": "STT", "summary": "요약"}
        for key, lbl in label_map.items():
            r = results.get(key, {})
            if r.get("ok"):
                if key == "mp3":
                    drive_mp3_link = r["link"]
                elif key == "stt":
                    drive_stt_link = r["link"]
                else:
                    drive_sum_link = r["link"]
                msgs.append(f"☁ {lbl} Drive 업로드 완료")
            elif r.get("msg") and r["msg"] != "파일 없음":
                msgs.append(f"❌ {lbl} Drive 실패: {r['msg']}")

        self._finalize_save(mp3_path, stt_path, sum_path, save_name,
                            stt_text, text, msgs,
                            drive_mp3_link, drive_stt_link, drive_sum_link)

    def _finalize_save(self, mp3_path, stt_path, sum_path, save_name,
                       stt_text, text, msgs,
                       drive_mp3_link, drive_stt_link, drive_sum_link):
        """DB 저장 + Obsidian 저장 + 완료 팝업"""
        # DB 저장
        if mp3_path or stt_path or sum_path:
            mid = database.save_meeting(
                file_name=save_name,
                mp3_local_path=mp3_path or "",
                stt_local_path=stt_path or "",
                summary_local_path=sum_path or "",
                stt_text=stt_text,
                summary_text=text,
                drive_mp3_link=drive_mp3_link,
                drive_stt_link=drive_stt_link,
                drive_summary_link=drive_sum_link,
                file_size_mb=fm.get_file_size_mb(mp3_path) if mp3_path else 0,
            )
            self._meeting_id = mid
            msgs.append(f"✅ DB 저장 완료 (ID: {mid})")
        self._refresh_list()

        # Obsidian 노트 자동 생성
        if text and self._cfg.get("obsidian_auto_save", True):
            obs_result = self._save_obsidian_note(text, save_name)
            msgs.append(obs_result)

        # 저장 상태 표시
        self._save_status_var.set(" | ".join(msgs))

        # 완료 팝업
        result_lines = ["🎉 처리 완료!", ""]
        result_lines += msgs
        result_lines += ["", f"📁 저장 위치: {config.RECORDING_BASE}"]
        if drive_mp3_link or drive_stt_link or drive_sum_link:
            result_lines += ["", "☁ Google Drive 링크:", drive_mp3_link or ""]
        messagebox.showinfo("완료", "\n".join(result_lines))

    def _extract_counterpart_name(self, summary_text: str) -> str:
        """회의록 본문 헤더 테이블에서 상대방/기업명을 자동 추출"""
        import re as _re
        mode = self._pipeline_sum_mode

        # 모드별 추출 대상 필드 (마크다운 테이블 행 패턴)
        # 형식: | 필드명 | 값 |
        field_patterns = {
            "formal_md": [
                r'\|\s*대\s*상\s*기\s*업\s*\|\s*(.+?)\s*\|',          # 대 상 기 업
            ],
            "topic": [
                r'\|\s*참\s*석\s*기\s*관\s*\|\s*(.+?)\s*\|',          # 참 석 기 관
                r'\|\s*회의명\s*/\s*안건\s*\|\s*(.+?)\s*\|',           # 회의명 / 안건 (fallback)
            ],
            "flow": [
                r'\|\s*참\s*석\s*자\s*\|\s*(.+?)\s*\|',               # 참 석 자
            ],
            "phone": [
                r'\|\s*상\s*대\s*방\s*\|\s*(.+?)\s*\|',               # 상 대 방
            ],
        }

        patterns = field_patterns.get(mode, [])
        for pattern in patterns:
            m = _re.search(pattern, summary_text)
            if m:
                raw = m.group(1).strip()
                # 빈값·AI자동식별·괄호 플레이스홀더 필터
                if raw and raw not in ("(참석 기관 및 인원 자동 식별)", "(투자업체명 자동 식별)",
                                       "[참석자]", "AI 자동 생성", "") \
                        and not raw.startswith("("):
                    # 첫 번째 항목만 사용 (여러 기관이면 첫 기관명)
                    first = _re.split(r'[/,·\n]', raw)[0].strip()
                    # 대괄호 제거
                    first = _re.sub(r'[\[\]]', '', first).strip()
                    if first:
                        return first
        return ""

    def _save_obsidian_note(self, summary_text: str, save_name: str,
                            mode: str = None) -> str:
        """Obsidian 회의록 노트 자동 생성 (저장 전 파일명 확인 다이얼로그 포함)

        파일명 형식 (모드별):
          ir_md      → YYMMDD {기업명}           예) 260408 서메어
          formal_md  → YYMMDD {상대방명}          예) 260408 테라릭스
          topic      → YYMMDD {미팅당사자}        예) 260408 A기관협의
          speaker    → YYMMDD 주간회의            예) 260408 주간회의
          phone      → YYMMDD {상대방명} 통화     예) 260408 서동조대표 통화
          flow       → YYMMDD {상대방명} 티타임   예) 260408 서동조대표 티타임
          lecture_md → YYMMDD {강의명} 강의       예) 260408 창업투자 강의
        """
        try:
            obsidian_dir = self._cfg.get(
                "obsidian_meeting_dir",
                r"C:\Users\anton\Documents\Obsidian_KRUN_Antonio\5. 회의록"
            )
            date_str = datetime.now().strftime("%y%m%d")
            mode = mode or self._pipeline_sum_mode

            # ① 회의록 본문에서 상대방/기업명 자동 추출 (formal_md·topic·flow·phone)
            # _extract_counterpart_name 은 self._pipeline_sum_mode 를 참조하므로
            # mode 가 다를 경우 임시로 교체 후 복원
            _prev_mode = self._pipeline_sum_mode
            if mode != _prev_mode:
                self._pipeline_sum_mode = mode
            auto_name = self._extract_counterpart_name(summary_text)
            if mode != _prev_mode:
                self._pipeline_sum_mode = _prev_mode

            # ② save_name 정제 (fallback용): 날짜+시간 자동생성 prefix 및 불필요 suffix 제거
            import re as _re
            clean = _re.sub(r'^\d{8}_\d{6}_?', '', save_name).strip('_').strip()
            clean = _re.sub(r'[_ ]*(STT|회의록|녹음)$', '', clean, flags=_re.IGNORECASE).strip('_').strip()

            # 최종 사용 이름: 본문 자동추출 → save_name 정제값 → fallback 문자열
            def _name(fallback: str) -> str:
                return auto_name or clean or fallback

            if mode == "speaker":
                note_title = f"{date_str} 주간회의"

            elif mode == "ir_md":
                name = (self._pipeline_company_name.strip()
                        or auto_name or clean or "IR미팅")
                note_title = f"{date_str} {name}"

            elif mode == "formal_md":
                note_title = f"{date_str} {_name('업무미팅')}"

            elif mode == "topic":
                note_title = f"{date_str} {_name('다자협의')}"

            elif mode == "phone":
                note_title = f"{date_str} {_name('통화')} 통화"

            elif mode == "flow":
                note_title = f"{date_str} {_name('티타임')} 티타임"

            elif mode == "lecture_md":
                note_title = f"{date_str} {_name('강의')} 강의"

            else:
                note_title = f"{date_str} {_name('회의록')}"

            # ③ 파일명 확인 다이얼로그 — 사용자가 수정 가능
            confirmed_title = simpledialog.askstring(
                "Obsidian 저장 — 파일명 확인",
                "저장할 파일명을 확인하거나 수정하세요.\n(.md 확장자 자동 추가)",
                initialvalue=note_title,
                parent=self,
            )
            if not confirmed_title or not confirmed_title.strip():
                return "📓 Obsidian 저장 취소됨"

            confirmed_title = confirmed_title.strip()
            # 파일명에 사용 불가한 문자 제거
            confirmed_title = _re.sub(r'[\\/:*?"<>|]', '_', confirmed_title)

            note_filename = confirmed_title + ".md"
            note_path = os.path.join(obsidian_dir, note_filename)

            # 디렉토리 생성 (없을 경우)
            os.makedirs(obsidian_dir, exist_ok=True)

            with open(note_path, "w", encoding="utf-8") as f:
                f.write(summary_text)

            return f"📓 Obsidian 저장: {note_filename}"
        except Exception as e:
            return f"⚠ Obsidian 저장 실패: {e}"

    def _resummarize(self):
        """🔄 커스텀 재요약 — 설정 탭의 커스텀 프롬프트를 현재 STT 텍스트에 적용"""
        if not self._stt_text:
            messagebox.showwarning("알림", "STT 변환 결과가 없습니다. 먼저 변환을 실행해주세요.")
            return
        api_key = self._cfg.get("gemini_api_key", "")
        if not api_key:
            messagebox.showwarning("알림", "설정 탭에서 Gemini API 키를 입력해주세요.")
            return
        if self._processing:
            messagebox.showwarning("알림", "이미 처리 중입니다. 완료 후 실행해주세요.")
            return
        custom_text = self._cfg.get("custom_prompt_text", "")
        if not custom_text.strip():
            messagebox.showwarning("알림",
                "설정 탭 → 🎯 요약 커스텀 프롬프트에 지시사항을 입력하고 저장해주세요.")
            self._nb.select(2)
            return

        self._processing = True
        self._cancel_event.clear()
        self._btn_pipeline.config(state="disabled")
        self._btn_resummarize.config(state="disabled")
        self._btn_cancel.config(state="normal")
        self._sum_prog["value"] = 0
        self._sum_status_var.set("커스텀 재요약 중...")
        self._sum_box.delete("1.0", "end")

        prev_notes = self._get_obsidian_notes_content()

        def run():
            if self._pipeline_ai_engine == "claude":
                cl_key = self._cfg.get("claude_api_key", "")
                ok, text = claude.summarize(
                    self._stt_text, cl_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_text,
                )
            elif self._pipeline_ai_engine == "chatgpt":
                gpt_key = self._cfg.get("chatgpt_api_key", "")
                ok, text = self._summarize_with_chatgpt(
                    self._stt_text, gpt_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_text,
                )
            else:
                ok, text = gemini.summarize(
                    self._stt_text, api_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_text,
                    company_name=self._pipeline_company_name,
                    prev_notes=prev_notes,
                )
            self.after(0, lambda: self._on_resummarize_done(ok, text))

        threading.Thread(target=run, daemon=True).start()

    def _on_resummarize_done(self, ok: bool, text: str):
        """커스텀 재요약 완료 콜백 → 로컬/Drive 저장"""
        self._processing = False
        self._btn_pipeline.config(state="normal")
        self._btn_resummarize.config(state="normal")
        self._btn_cancel.config(state="disabled")

        if not ok:
            self._sum_status_var.set(f"❌ 재요약 실패: {text[:60]}")
            messagebox.showerror("재요약 오류", text)
            return

        self._summary_text = text
        self._sum_box.delete("1.0", "end")
        self._sum_box.insert("1.0", text)
        self._sum_status_var.set("✅ 커스텀 재요약 완료!")
        self._set_prog(self._sum_prog, 100)

        # ── 파일명 입력 팝업 ─────────────────────────────
        default_name = datetime.now().strftime("%Y%m%d_%H%M%S") + "_커스텀요약"
        save_name = simpledialog.askstring(
            "파일명 입력",
            "저장할 파일명을 입력하세요 (확장자 제외):",
            initialvalue=default_name,
            parent=self,
        )
        if not save_name or not save_name.strip():
            save_name = default_name
        save_name = save_name.strip()

        # ── 로컬 저장 ────────────────────────────────────
        msgs = []
        sum_path = None
        self._current_sum_path = None

        ok3, path = fm.save_summary_text(text, str(config.SUMMARY_SAVE_DIR),
                                         save_name + "_재요약")
        if ok3:
            sum_path = path
            self._current_sum_path = path
            msgs.append(f"✅ 재요약 저장: {Path(path).name}")
        else:
            msgs.append(f"❌ 재요약 저장 실패: {path}")

        # ── Google Drive 업로드 ──────────────────────────
        drive_sum_link = ""
        drv_status = gdrive.get_credentials_status()
        auto_upload = self._cfg.get("drive_auto_upload", True)

        if drv_status["status"] == "authenticated" and auto_upload:
            self._save_status_var.set("☁ Google Drive 업로드 중...")
            self.update()
            folder_name = self._cfg.get("drive_folder_name", "회의녹음요약")

            def run_drive():
                results = gdrive.upload_meeting_files(
                    "", "", sum_path or "", folder_name)
                self.after(0, lambda: self._on_resummarize_drive_done(
                    results, sum_path, save_name, text, msgs))

            threading.Thread(target=run_drive, daemon=True).start()
            return  # Drive 완료 콜백에서 마무리

        # Drive 미연결
        if drv_status["status"] != "authenticated":
            msgs.append("☁ Drive 미연결 (로컬 저장만 완료)")
        elif not auto_upload:
            msgs.append("☁ Drive 자동 업로드 OFF")

        self._finalize_resummarize(sum_path, save_name, text, msgs, "")

    def _on_resummarize_drive_done(self, results, sum_path, save_name, text, msgs):
        """커스텀 재요약 Drive 업로드 완료 콜백"""
        drive_sum_link = ""
        if results.get("summary", {}).get("ok"):
            drive_sum_link = results["summary"]["link"]
            msgs.append("☁ 요약 Drive 업로드 완료")
        elif "summary" in results:
            msgs.append(f"❌ 요약 Drive 실패: {results['summary']['msg'][:40]}")
        self._finalize_resummarize(sum_path, save_name, text, msgs, drive_sum_link)

    def _finalize_resummarize(self, sum_path, save_name, text, msgs, drive_sum_link):
        """커스텀 재요약 DB 저장 + 완료 팝업"""
        # DB: 기존 레코드가 있으면 요약 업데이트, 없으면 새 레코드
        if self._meeting_id:
            database.update_meeting_summary(
                self._meeting_id,
                summary_text=text,
                summary_local_path=sum_path or "",
            )
            msgs.append(f"✅ DB 업데이트 (ID: {self._meeting_id})")
        elif sum_path:
            mid = database.save_meeting(
                file_name=save_name,
                mp3_local_path="",
                stt_local_path="",
                summary_local_path=sum_path,
                stt_text=self._stt_text,
                summary_text=text,
                drive_mp3_link="",
                drive_stt_link="",
                drive_summary_link=drive_sum_link,
                file_size_mb=0,
            )
            self._meeting_id = mid
            msgs.append(f"✅ DB 저장 (ID: {mid})")

        self._refresh_list()
        self._save_status_var.set(" | ".join(msgs))

        result_lines = ["🎉 커스텀 재요약 저장 완료!", ""] + msgs
        result_lines += ["", f"📁 저장 위치: {config.SUMMARY_SAVE_DIR}"]
        if drive_sum_link:
            result_lines += ["", f"☁ Drive 링크: {drive_sum_link}"]
        messagebox.showinfo("완료", "\n".join(result_lines))

    def _summarize_with_chatgpt(self, stt_text: str, api_key: str,
                                 progress_cb=None, summary_mode: str = "speaker",
                                 cancel_event=None, custom_instruction: str = "") -> tuple:
        """ChatGPT (OpenAI) 요약 — claude_service 패턴 준용"""
        if not api_key:
            return False, "ChatGPT API 키가 없습니다. 설정 탭에서 입력해주세요."
        if not stt_text.strip():
            return False, "변환된 텍스트가 비어 있습니다."
        try:
            import openai
        except ImportError:
            return False, "openai 패키지가 설치되지 않았습니다.\n'pip install openai' 실행 후 재시도해주세요."

        # gemini_service 템플릿 재사용
        from claude_service import _get_template
        template, trim_fn = _get_template(summary_mode)
        try:
            if progress_cb: progress_cb(10)
            if cancel_event and cancel_event.is_set():
                return False, "사용자에 의해 중단되었습니다."

            from datetime import datetime as _dt
            prompt = template.format(
                text=stt_text[:300000],
                dt=_dt.now().strftime("%Y년 %m월 %d일 %H:%M"),
            )
            if custom_instruction and custom_instruction.strip():
                prompt += f"\n\n[추가 지시사항]\n{custom_instruction.strip()}"

            if progress_cb: progress_cb(30)

            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=config.CHATGPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
                temperature=0.3,
            )
            if cancel_event and cancel_event.is_set():
                return False, "사용자에 의해 중단되었습니다."
            if progress_cb: progress_cb(100)
            result = resp.choices[0].message.content or ""
            if not result:
                return False, "ChatGPT 응답이 비어 있습니다."
            return True, trim_fn(result)
        except Exception as e:
            return False, f"ChatGPT 오류: {str(e)[:300]}"

    # ── 절전 방지 ─────────────────────────────────────────
    def _set_sleep_prevention(self, active: bool):
        """Windows 절전 방지 ON/OFF (녹음·STT·요약 처리 중 PC 절전 차단)"""
        if not self._kernel32:
            return
        try:
            if active:
                self._kernel32.SetThreadExecutionState(
                    self._ES_CONTINUOUS | self._ES_SYSTEM_REQUIRED
                )
                self._sleep_prevention_active = True
            else:
                self._kernel32.SetThreadExecutionState(self._ES_CONTINUOUS)
                self._sleep_prevention_active = False
        except Exception:
            pass

    def _cancel_process(self):
        """■ 중단 버튼"""
        self._cancel_event.set()
        self._stt_status_var.set("중단 요청됨...")
        self._sum_status_var.set("중단 요청됨...")
        self._set_sleep_prevention(False)

    # ════════════════════════════════════════════════════
    # 회의 목록
    # ════════════════════════════════════════════════════
    def _refresh_list(self):
        self._tree.delete(*self._tree.get_children())
        for m in database.get_all_meetings():
            has_drive = bool(
                m.get("drive_mp3_link") or
                m.get("drive_stt_link") or
                m.get("drive_summary_link"))
            self._tree.insert("", "end", iid=str(m["id"]), values=(
                m.get("created_at", "")[:16],
                m.get("file_name", ""),
                "✅" if m.get("mp3_local_path") else "❌",
                "✅" if m.get("stt_text") else "❌",
                "✅" if m.get("summary_text") else "❌",
                "☁✅" if has_drive else "—",
            ))

    def _on_list_select(self, event):
        """트리뷰 선택 시 요약/STT 분리 뷰 자동 표시"""
        sel = self._tree.selection()
        if not sel:
            return
        mid  = int(sel[0])
        data = database.get_meeting(mid)
        self._selected_meeting_data = data

        # 요약 탭
        self._sum_detail_box.delete("1.0", "end")
        self._sum_detail_box.insert("1.0", data.get("summary_text", "(요약 없음)"))

        # STT 원문 탭
        self._stt_detail_box.delete("1.0", "end")
        self._stt_detail_box.insert("1.0", data.get("stt_text", "(STT 원문 없음)"))

    def _view_meeting_full(self):
        """📄 전체 보기 — 별도 창에서 요약 + STT 전체 내용 표시"""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("알림", "항목을 선택해주세요.")
            return
        mid  = int(sel[0])
        data = database.get_meeting(mid)

        dlg = tk.Toplevel(self)
        dlg.title(f"📄 전체 보기 — {data.get('file_name','')}")
        dlg.resizable(True, True)

        self.update_idletasks()
        w, h = 900, 700
        x = self.winfo_x() + self.winfo_width() // 2 - w // 2
        y = self.winfo_y() + self.winfo_height() // 2 - h // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.configure(bg=CARD_BG)

        nb = ttk.Notebook(dlg, style="Detail.TNotebook")
        nb.pack(fill="both", expand=True, padx=10, pady=8)

        # 요약 탭
        sum_frm = tk.Frame(nb, bg=CARD_BG)
        nb.add(sum_frm, text="  📋 회의록 요약  ")
        sum_box = scrolledtext.ScrolledText(sum_frm, font=FONT_BODY, wrap="word", bg="#FAFAFA")
        sum_box.pack(fill="both", expand=True)
        sum_box.insert("1.0", data.get("summary_text", "(없음)"))

        # STT 탭
        stt_frm = tk.Frame(nb, bg=CARD_BG)
        nb.add(stt_frm, text="  📝 STT 원문  ")
        stt_box = scrolledtext.ScrolledText(stt_frm, font=FONT_BODY, wrap="word", bg="#FAFAFA")
        stt_box.pack(fill="both", expand=True)
        stt_box.insert("1.0", data.get("stt_text", "(없음)"))

        # 정보 탭
        info_frm = tk.Frame(nb, bg=CARD_BG)
        nb.add(info_frm, text="  ℹ 정보  ")
        info_text = (
            f"파일명: {data.get('file_name','')}\n"
            f"생성일시: {data.get('created_at','')}\n"
            f"MP3 경로: {data.get('mp3_local_path','—')}\n"
            f"STT 파일: {data.get('stt_local_path','—')}\n"
            f"요약 파일: {data.get('summary_local_path','—')}\n"
            f"Drive MP3: {data.get('drive_mp3_link','—')}\n"
            f"Drive STT: {data.get('drive_stt_link','—')}\n"
            f"Drive 요약: {data.get('drive_summary_link','—')}\n"
            f"파일크기: {data.get('file_size_mb',0):.2f} MB\n"
        )
        info_box = scrolledtext.ScrolledText(info_frm, font=FONT_BODY, wrap="word", bg="#FAFAFA", height=12)
        info_box.pack(fill="both", expand=True)
        info_box.insert("1.0", info_text)
        info_box.config(state="disabled")

        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=8)
        sum_path_full  = data.get("summary_local_path", "")
        stt_path_full  = data.get("stt_local_path", "")

        def _open_file(p):
            if p and Path(p).exists():
                if sys.platform == "win32":
                    os.startfile(p)
                else:
                    subprocess.Popen(["xdg-open", p])
            else:
                messagebox.showwarning("알림", f"파일을 찾을 수 없습니다:\n{p}")

        if sum_path_full and Path(sum_path_full).exists():
            self._btn(btn_row, "📂 회의록 파일 열기", ACCENT,
                      lambda p=sum_path_full: _open_file(p), w=16).pack(side="left", padx=4)
        if stt_path_full and Path(stt_path_full).exists():
            self._btn(btn_row, "📂 STT 파일 열기", SUCCESS,
                      lambda p=stt_path_full: _open_file(p), w=14).pack(side="left", padx=4)
        self._btn(btn_row, "닫기", TEXT_LIGHT, dlg.destroy, w=10).pack(side="left", padx=4)

    # ── 이전 버전 하위 호환 ─────────────────────────────
    def _view_meeting(self):
        self._view_meeting_full()

    def _print_meeting(self):
        """🖨 출력·인쇄 — 로컬 / 네트워크 프린터 선택"""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("알림", "인쇄할 항목을 선택해주세요.")
            return
        mid  = int(sel[0])
        data = database.get_meeting(mid)
        sum_path = data.get("summary_local_path", "")

        if not sum_path or not Path(sum_path).exists():
            summary_text = data.get("summary_text", "")
            if not summary_text:
                messagebox.showwarning("알림", "요약 내용이 없습니다.")
                return
            tmp_path = Path(config.APP_DATA_DIR) / f"_tmp_print_{data.get('file_name','temp')}.md"
            tmp_path.write_text(summary_text, encoding="utf-8")
            sum_path = str(tmp_path)

        # 네트워크 프린터 IP 설정 여부 확인
        net_ip   = self._cfg.get("net_printer_ip", "").strip()
        net_name = self._cfg.get("net_printer_name", "printer").strip()

        if net_ip:
            # 인쇄 방법 선택 메뉴
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(
                label="🖥  로컬 프린터 (기본)",
                command=lambda: self._do_print_local(sum_path))
            menu.add_command(
                label=f"🌐  네트워크 프린터 ({net_ip})",
                command=lambda: self._do_print_network(sum_path, net_ip, net_name))
            try:
                menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
            finally:
                menu.grab_release()
        else:
            self._do_print_local(sum_path)

    def _do_print_local(self, sum_path: str):
        """로컬 기본 프린터로 인쇄"""
        ok, msg = fm.print_file(sum_path)
        if not ok:
            messagebox.showerror("인쇄 오류", msg)

    def _do_print_network(self, sum_path: str, ip: str, printer_name: str):
        """네트워크 IP 프린터로 인쇄"""
        ok, msg = fm.print_to_network(sum_path, ip, printer_name)
        if not ok:
            messagebox.showerror("네트워크 인쇄 오류", msg)
        else:
            messagebox.showinfo("완료", msg)

    # ── 화자이름 변경 ────────────────────────────────────
    def _rename_speaker_dialog(self):
        """✏ 화자이름 변경 — STT 원문 자동 감지 + 일괄 치환"""
        import re
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("알림", "항목을 선택해주세요.")
            return
        mid  = int(sel[0])
        data = database.get_meeting(mid)
        stt_text     = data.get("stt_text", "")
        summary_text = data.get("summary_text", "")
        if not stt_text:
            messagebox.showwarning("알림", "STT 원문이 없습니다.")
            return

        # 화자 패턴 자동 감지 (CLOVA/Gemini/Whisper 공통 패턴)
        # 형식 1: [화자1], [화자 1] — CLOVA STT 출력 형식 (브래킷)
        bracket_nums = re.findall(r'\[화자\s*(\d+)\]', stt_text)
        bracket_speakers = [f"[화자{n}]" for n in sorted(set(bracket_nums), key=int)]

        # 형식 2: 화자1:, Speaker 1:, 이름: — 콜론 구분 형식
        colon_raw = re.findall(
            r'^([가-힣A-Za-z_][\w가-힣]*(?:\s*\d+)?)\s*:', stt_text, re.MULTILINE)
        colon_speakers = sorted(set(colon_raw), key=lambda s: (
            not bool(re.match(r'^(화자|Speaker|SPEAKER)', s)), s))

        speakers = bracket_speakers + [s for s in colon_speakers
                                       if s not in bracket_speakers]
        if not speakers:
            messagebox.showinfo("알림",
                "화자 패턴을 감지하지 못했습니다.\n\n"
                "지원 형식:\n"
                "  • [화자1] 내용 ... (CLOVA STT)\n"
                "  • 화자1: 내용 ... (일반 형식)")
            return

        # 팝업 다이얼로그
        dlg = tk.Toplevel(self)
        dlg.title("✏ 화자이름 변경")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(bg=BG)
        self.update_idletasks()
        w, h = 420, min(120 + len(speakers) * 40, 520)
        x = self.winfo_x() + self.winfo_width() // 2 - w // 2
        y = self.winfo_y() + self.winfo_height() // 2 - h // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(dlg, text="감지된 화자명을 원하는 이름으로 변경하세요.",
                 font=FONT_SMALL, bg=BG, fg=TEXT_LIGHT).pack(pady=(10, 4))

        frm = tk.Frame(dlg, bg=CARD_BG, relief="flat", bd=1)
        frm.pack(fill="both", expand=True, padx=16, pady=4)

        entries = {}
        for spk in speakers:
            row = tk.Frame(frm, bg=CARD_BG)
            row.pack(fill="x", pady=3, padx=10)
            tk.Label(row, text=f"{spk}:", font=FONT_BODY,
                     bg=CARD_BG, fg=TEXT, width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value=spk)
            tk.Entry(row, textvariable=var, font=FONT_BODY, width=18).pack(side="left")
            entries[spk] = var

        scope_var = tk.IntVar(value=3)  # 1=STT만, 2=요약만, 3=둘다
        scope_frm = tk.Frame(dlg, bg=BG)
        scope_frm.pack(pady=4)
        tk.Label(scope_frm, text="적용 범위:", font=FONT_SMALL,
                 bg=BG, fg=TEXT).pack(side="left", padx=6)
        for label, val in [("STT+요약", 3), ("STT만", 1), ("요약만", 2)]:
            tk.Radiobutton(scope_frm, text=label, variable=scope_var, value=val,
                           font=FONT_SMALL, bg=BG).pack(side="left", padx=4)

        def _apply():
            mapping = {old: var.get().strip() or old
                       for old, var in entries.items()}
            scope = scope_var.get()

            new_stt = stt_text
            new_sum = summary_text
            for old, new in mapping.items():
                if old == new:
                    continue
                if old.startswith("[") and old.endswith("]"):
                    # [화자N] 브래킷 형식 치환
                    repl_new = f"[{new}]"
                    if scope in (1, 3):
                        new_stt = new_stt.replace(old, repl_new)
                    if scope in (2, 3):
                        new_sum = new_sum.replace(old, repl_new)
                else:
                    # 콜론 형식 치환
                    pattern = re.compile(r'^' + re.escape(old) + r'\s*:', re.MULTILINE)
                    repl = f"{new}:"
                    if scope in (1, 3):
                        new_stt = pattern.sub(repl, new_stt)
                    if scope in (2, 3):
                        new_sum = re.sub(re.escape(old), new, new_sum)

            # DB 업데이트
            database.update_meeting_summary(mid, stt_text=new_stt, summary_text=new_sum)

            # 로컬 파일 업데이트
            for path_key, text in [("stt_local_path", new_stt),
                                    ("summary_local_path", new_sum)]:
                fpath = data.get(path_key, "")
                if fpath and Path(fpath).exists():
                    try:
                        Path(fpath).write_text(text, encoding="utf-8")
                    except Exception:
                        pass

            # 화면 즉시 갱신
            self._sum_detail_box.delete("1.0", "end")
            self._sum_detail_box.insert("1.0", new_sum)
            self._stt_detail_box.delete("1.0", "end")
            self._stt_detail_box.insert("1.0", new_stt)

            dlg.destroy()
            messagebox.showinfo("완료", "화자이름이 변경되었습니다.")

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(pady=8)
        self._btn(btn_row, "✅ 적용", SUCCESS, _apply, w=10).pack(side="left", padx=6)
        self._btn(btn_row, "취소", TEXT_LIGHT, dlg.destroy, w=8).pack(side="left")

    # ── 공유 드롭다운 ────────────────────────────────────
    def _share_menu(self):
        """📤 공유 ▼ — 드롭다운 메뉴"""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("알림", "공유할 항목을 선택해주세요.")
            return
        mid  = int(sel[0])
        data = database.get_meeting(mid)

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="📋  클립보드 복사",
                         command=lambda: self._share_clipboard(data))
        menu.add_command(label="✉   이메일 전송",
                         command=lambda: self._share_email(data))
        menu.add_command(label="💬  카카오톡 공유",
                         command=lambda: self._share_kakao(data))
        menu.add_separator()
        menu.add_command(label="📁  파일 탐색기에서 열기",
                         command=lambda: self._share_explorer(data))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _share_clipboard(self, data: dict):
        """📋 클립보드에 요약 텍스트 복사"""
        text = data.get("summary_text", "")
        if not text:
            messagebox.showwarning("알림", "요약 내용이 없습니다.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("완료", "회의록 요약이 클립보드에 복사되었습니다.")

    def _share_email(self, data: dict):
        """✉ 기본 메일 클라이언트로 이메일 전송"""
        import urllib.parse
        # safe="" 전면 인코딩 시 URL 길이 폭발 → 본문은 앞 2000자만, 줄바꿈 보존
        subject = urllib.parse.quote(
            f"[회의록] {data.get('file_name', '회의록')}", safe="")
        raw_body = data.get("summary_text", "")[:2000]
        body = urllib.parse.quote(raw_body, safe="\r\n")
        webbrowser.open(f"mailto:?subject={subject}&body={body}")

    def _share_kakao(self, data: dict):
        """💬 카카오톡 공유 — MD → PDF 변환 후 파일 탐색기 오픈"""
        summary_text = data.get("summary_text", "")
        if not summary_text:
            messagebox.showwarning("알림", "요약 내용이 없습니다.")
            return

        file_name = data.get("file_name", "회의록")
        pdf_name  = f"{Path(file_name).stem}_회의록.pdf"
        pdf_path  = str(Path(config.SUMMARY_SAVE_DIR) / pdf_name)

        ok, result = fm.export_pdf(summary_text, pdf_path,
                                   title=Path(file_name).stem)
        if ok:
            fm.open_file_in_explorer(result)
            messagebox.showinfo(
                "카카오톡 공유",
                f"PDF 파일이 생성되었습니다.\n\n"
                f"파일명: {Path(result).name}\n\n"
                "파일 탐색기에서 PDF 파일을\n"
                "카카오톡 채팅창으로 드래그하여 전송하세요.")
        else:
            # PDF 변환 실패 시 클립보드 복사 폴백
            self.clipboard_clear()
            self.clipboard_append(summary_text)
            messagebox.showinfo(
                "카카오톡 공유",
                f"PDF 변환 실패: {result}\n\n"
                "회의록 텍스트를 클립보드에 복사했습니다.\n"
                "카카오톡에 붙여넣기(Ctrl+V) 해주세요.")

    def _share_explorer(self, data: dict):
        """📁 파일 탐색기에서 열기"""
        sum_path = data.get("summary_local_path", "")
        if sum_path and Path(sum_path).exists():
            fm.open_file_in_explorer(sum_path)
        else:
            fm.open_file_in_explorer(str(config.SUMMARY_SAVE_DIR))

    # 구버전 하위 호환
    def _share_meeting(self):
        sel = self._tree.selection()
        if sel:
            self._share_menu()

    def _find_replace_dialog(self):
        """🔍 찾기/바꾸기 — 회의록 요약 텍스트에서 검색 및 치환"""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("알림", "항목을 선택해주세요.")
            return

        mid  = int(sel[0])
        data = self._selected_meeting_data

        dlg = tk.Toplevel(self)
        dlg.title("🔍 찾기 / 바꾸기")
        dlg.resizable(False, False)
        dlg.configure(bg=CARD_BG)

        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() // 2 - 230
        y = self.winfo_y() + self.winfo_height() // 2 - 120
        dlg.geometry(f"460x260+{x}+{y}")

        # ── 입력 필드 ─────────────────────────────────────
        pad = dict(padx=20, pady=4)

        tk.Label(dlg, text="찾기 / 바꾸기", font=FONT_H2,
                 bg=CARD_BG, fg=TEXT).pack(pady=(14, 4))
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=2)

        find_frm = tk.Frame(dlg, bg=CARD_BG)
        find_frm.pack(fill="x", **pad)
        tk.Label(find_frm, text="찾기:", font=FONT_BODY, bg=CARD_BG, fg=TEXT,
                 width=7, anchor="w").pack(side="left")
        find_var = tk.StringVar()
        find_entry = tk.Entry(find_frm, textvariable=find_var, font=FONT_BODY, width=36)
        find_entry.pack(side="left", padx=(0, 4))

        repl_frm = tk.Frame(dlg, bg=CARD_BG)
        repl_frm.pack(fill="x", **pad)
        tk.Label(repl_frm, text="바꾸기:", font=FONT_BODY, bg=CARD_BG, fg=TEXT,
                 width=7, anchor="w").pack(side="left")
        repl_var = tk.StringVar()
        repl_entry = tk.Entry(repl_frm, textvariable=repl_var, font=FONT_BODY, width=36)
        repl_entry.pack(side="left", padx=(0, 4))

        # 대소문자 무시 옵션
        opt_frm = tk.Frame(dlg, bg=CARD_BG)
        opt_frm.pack(fill="x", padx=20, pady=(0, 4))
        nocase_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frm, text="대소문자 무시", variable=nocase_var,
                       bg=CARD_BG, font=FONT_SMALL, fg=TEXT,
                       activebackground=CARD_BG).pack(side="left")

        status_var = tk.StringVar(value="")
        tk.Label(dlg, textvariable=status_var, font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack()

        # ── 내부 상태 ──────────────────────────────────────
        state = {"last_pos": "1.0", "count": 0}
        TAG = "fr_highlight"
        self._sum_detail_box.tag_config(TAG, background="#F9E79F", foreground="#000000")

        def _clear_tags():
            self._sum_detail_box.tag_remove(TAG, "1.0", "end")

        def _find_next(from_pos=None):
            keyword = find_var.get()
            if not keyword:
                status_var.set("찾을 내용을 입력하세요.")
                return None
            _clear_tags()
            start = from_pos or state["last_pos"]
            pos = self._sum_detail_box.search(
                keyword, start, stopindex="end",
                nocase=nocase_var.get()
            )
            if not pos:
                # 처음부터 다시
                pos = self._sum_detail_box.search(
                    keyword, "1.0", stopindex="end",
                    nocase=nocase_var.get()
                )
                if not pos:
                    status_var.set("⚠ 찾을 수 없습니다.")
                    state["last_pos"] = "1.0"
                    return None
            end_pos = f"{pos}+{len(keyword)}c"
            self._sum_detail_box.tag_add(TAG, pos, end_pos)
            self._sum_detail_box.see(pos)
            state["last_pos"] = end_pos
            status_var.set(f"발견: {pos}")
            return pos, end_pos

        def _replace_one():
            result = _find_next()
            if not result:
                return
            pos, end_pos = result
            self._sum_detail_box.delete(pos, end_pos)
            self._sum_detail_box.insert(pos, repl_var.get())
            state["last_pos"] = f"{pos}+{len(repl_var.get())}c"
            _find_next(state["last_pos"])

        def _replace_all():
            keyword = find_var.get()
            replacement = repl_var.get()
            if not keyword:
                status_var.set("찾을 내용을 입력하세요.")
                return
            _clear_tags()
            content = self._sum_detail_box.get("1.0", "end-1c")
            import re as _re
            flags = _re.IGNORECASE if nocase_var.get() else 0
            new_content, count = _re.subn(_re.escape(keyword), replacement, content, flags=flags)
            if count == 0:
                status_var.set("⚠ 찾을 수 없습니다.")
                return
            # 텍스트 박스 갱신
            self._sum_detail_box.delete("1.0", "end")
            self._sum_detail_box.insert("1.0", new_content)
            state["last_pos"] = "1.0"
            # DB + 로컬 파일 저장
            stt_text = data.get("stt_text", "")
            database.update_meeting_summary(mid, stt_text=stt_text, summary_text=new_content)
            fpath = data.get("summary_local_path", "")
            if fpath and Path(fpath).exists():
                try:
                    Path(fpath).write_text(new_content, encoding="utf-8")
                except Exception:
                    pass
            self._selected_meeting_data["summary_text"] = new_content
            status_var.set(f"✅ {count}건 바꾸기 완료 — 저장됨")

        # ── 버튼 행 ────────────────────────────────────────
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=6)
        btn_frm = tk.Frame(dlg, bg=CARD_BG)
        btn_frm.pack(pady=4)
        self._btn(btn_frm, "다음 찾기", ACCENT, _find_next, w=11).pack(side="left", padx=4)
        self._btn(btn_frm, "바꾸기", "#8E44AD", _replace_one, w=10).pack(side="left", padx=4)
        self._btn(btn_frm, "모두 바꾸기", SUCCESS, _replace_all, w=11).pack(side="left", padx=4)
        self._btn(btn_frm, "닫기", TEXT_LIGHT, lambda: (dlg.destroy(), _clear_tags()), w=8).pack(side="left", padx=4)

        dlg.protocol("WM_DELETE_WINDOW", lambda: (dlg.destroy(), _clear_tags()))
        find_entry.focus_set()
        find_entry.bind("<Return>", lambda e: _find_next())

    def _delete_meeting(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("알림", "삭제할 항목을 선택해주세요.")
            return
        if messagebox.askyesno("확인", "선택한 항목을 삭제할까요?\n(DB에서만 삭제되며 로컬 파일은 유지됩니다)"):
            database.delete_meeting(int(sel[0]))
            self._refresh_list()
            self._sum_detail_box.delete("1.0", "end")
            self._stt_detail_box.delete("1.0", "end")

    # ════════════════════════════════════════════════════
    # 설정 기능
    # ════════════════════════════════════════════════════
    # ════════════════════════════════════════════════════
    # Google Drive 설정 기능
    # ════════════════════════════════════════════════════
    def _refresh_drive_status(self):
        """Drive 인증 상태 라벨 갱신"""
        if not hasattr(self, "_drive_status_var"):
            return
        st = gdrive.get_credentials_status()
        color_map = {
            "authenticated": SUCCESS,
            "need_auth": WARNING,
            "no_credentials": DANGER,
            "no_package": DANGER,
        }
        icon_map = {
            "authenticated": "✅",
            "need_auth": "⚠",
            "no_credentials": "❌",
            "no_package": "❌",
        }
        status = st["status"]
        icon = icon_map.get(status, "❌")
        self._drive_status_var.set(f"{icon} {st['msg']}")
        self._drive_status_lbl.config(
            fg=color_map.get(status, DANGER))

    def _browse_credentials_file(self):
        """OAuth 클라이언트 JSON 파일 선택 및 복사"""
        path = filedialog.askopenfilename(
            title="Google OAuth 클라이언트 JSON 선택",
            filetypes=[("JSON 파일", "*.json"), ("모든 파일", "*.*")])
        if not path:
            return
        ok, msg = gdrive.save_credentials_file(path)
        if ok:
            self._cred_file_var.set(str(config.CREDENTIALS_FILE))
            self._refresh_drive_status()
            messagebox.showinfo("완료", f"✅ {msg}\n\n이제 'Google 인증' 버튼을 클릭하세요.")
        else:
            messagebox.showerror("오류", msg)

    def _drive_authenticate(self):
        """브라우저 OAuth 인증 실행"""
        st = gdrive.get_credentials_status()
        if st["status"] == "no_credentials":
            messagebox.showwarning("알림",
                                   "OAuth 자격증명 파일이 없습니다.\n"
                                   "'📂 파일 선택'으로 google_credentials.json을 등록해주세요.\n\n"
                                   "'📋 설정 방법' 버튼을 클릭하면 발급 방법을 확인할 수 있습니다.")
            return
        if st["status"] == "no_package":
            messagebox.showerror("오류", "google-auth 패키지가 설치되지 않았습니다.")
            return
        messagebox.showinfo("인증 시작",
                            "브라우저가 열립니다.\nGoogle 계정으로 로그인하여 권한을 허용해주세요.")
        self._drive_status_var.set("⏳ 인증 진행 중...")
        self.update()

        def run_auth():
            ok, msg = gdrive.authenticate()
            self.after(0, lambda: self._on_drive_auth_done(ok, msg))

        threading.Thread(target=run_auth, daemon=True).start()

    def _on_drive_auth_done(self, ok: bool, msg: str):
        self._refresh_drive_status()
        if ok:
            messagebox.showinfo("인증 완료", f"✅ {msg}")
        else:
            messagebox.showerror("인증 실패", msg)

    def _drive_revoke(self):
        """Drive 연결 해제"""
        if not messagebox.askyesno("확인", "Google Drive 연결을 해제할까요?"):
            return
        ok, msg = gdrive.revoke_token()
        self._refresh_drive_status()
        if ok:
            messagebox.showinfo("완료", f"✅ {msg}")
        else:
            messagebox.showerror("오류", msg)

    def _save_drive_auto_setting(self):
        """자동 업로드 체크박스 상태 저장"""
        self._cfg["drive_auto_upload"] = self._drive_auto_var.get()
        config.save_config(self._cfg)

    def _save_obs_setting(self):
        """Obsidian 연동 설정 저장"""
        self._cfg["obsidian_auto_save"] = self._obs_auto_var.get()
        self._cfg["obsidian_meeting_dir"] = self._obs_dir_var.get()
        config.save_config(self._cfg)

    def _show_drive_setup_guide(self):
        """Google Drive OAuth 자격증명 발급 방법 안내 팝업"""
        dlg = tk.Toplevel(self)
        dlg.title("📋 Google Drive 연동 설정 방법")
        dlg.resizable(True, True)
        dlg.grab_set()

        self.update_idletasks()
        w, h = 600, 580
        x = self.winfo_x() + self.winfo_width() // 2 - w // 2
        y = self.winfo_y() + self.winfo_height() // 2 - h // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.configure(bg=CARD_BG)

        tk.Label(dlg, text="☁ Google Drive 연동 설정 방법",
                 font=FONT_H2, bg=CARD_BG, fg=TEXT).pack(pady=(16, 4), padx=20, anchor="w")
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=6)

        guide_text = (
            "【 개요 】\n"
            "각 사용자가 본인의 Google Cloud 프로젝트에서\n"
            "OAuth 2.0 자격증명을 직접 발급하여 사용합니다.\n"
            "이 방식은 사용자 본인의 Drive에만 저장되므로 안전합니다.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "【 Step 1. Google Cloud Console 접속 】\n"
            "  → console.cloud.google.com 접속\n"
            "  → Google 계정으로 로그인\n\n"
            "【 Step 2. 프로젝트 생성 】\n"
            "  → 상단 프로젝트 선택 → '새 프로젝트' → 이름 입력 → 만들기\n\n"
            "【 Step 3. Google Drive API 사용 설정 】\n"
            "  → 좌측 메뉴 'API 및 서비스' → '라이브러리'\n"
            "  → 'Google Drive API' 검색 → '사용' 클릭\n\n"
            "【 Step 4. OAuth 동의 화면 설정 】\n"
            "  → '사용자 인증 정보' → 'OAuth 동의 화면'\n"
            "  → 유형: '외부' 선택 → 앱 이름 입력 → 저장\n"
            "  → '테스트 사용자'에 본인 Gmail 추가\n\n"
            "【 Step 5. OAuth 클라이언트 ID 생성 】\n"
            "  → '사용자 인증 정보' → '+ 사용자 인증 정보 만들기'\n"
            "  → 'OAuth 클라이언트 ID' 선택\n"
            "  → 애플리케이션 유형: '데스크톱 앱' 선택\n"
            "  → 이름 입력 → '만들기'\n\n"
            "【 Step 6. JSON 다운로드 】\n"
            "  → 생성된 클라이언트 ID 옆 다운로드 버튼(↓) 클릭\n"
            "  → JSON 파일 저장 (예: client_secret_xxx.json)\n\n"
            "【 Step 7. 이 앱에 등록 】\n"
            "  → 설정 탭 → '📂 파일 선택' → 다운로드한 JSON 선택\n"
            "  → '🔐 Google 인증' 클릭 → 브라우저에서 Google 로그인\n"
            "  → 완료!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ 이후 변환 완료 시 자동으로 본인 Drive에 업로드됩니다.\n"
            "⚠ 다른 사람의 Drive가 아닌 본인 Drive에만 업로드됩니다."
        )

        txt = scrolledtext.ScrolledText(
            dlg, font=FONT_BODY, wrap="word", bg="#FAFAFA",
            relief="solid", bd=1, height=22)
        txt.pack(fill="both", expand=True, padx=20, pady=4)
        txt.insert("1.0", guide_text)
        txt.config(state="disabled")

        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=10)
        self._btn(btn_row, "🌐 Google Cloud Console 열기", ACCENT,
                  lambda: webbrowser.open("https://console.cloud.google.com/apis/credentials"),
                  w=30).pack(side="left", padx=6)
        self._btn(btn_row, "닫기", TEXT_LIGHT,
                  dlg.destroy, w=8).pack(side="left", padx=6)

    # ── 네트워크 프린터 설정 메서드 ─────────────────────
    def _save_net_printer(self):
        """네트워크 프린터 IP / 이름 저장"""
        ip   = self._net_printer_ip_var.get().strip()
        name = self._net_printer_name_var.get().strip() or "printer"
        self._cfg["net_printer_ip"]   = ip
        self._cfg["net_printer_name"] = name
        config.save_config(self._cfg)
        self._net_printer_status_var.set(
            f"✅ 저장 완료 ({ip})" if ip else "✅ 저장 완료 (로컬 전용)")

    def _refresh_printer_list(self):
        """로컬 PC 프린터 목록 조회 및 Listbox 갱신"""
        self._net_printer_status_var.set("프린터 목록 조회 중...")
        self.update_idletasks()
        printers = []
        try:
            import win32print  # type: ignore
            raw = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS,
                None, 2)
            default_name = ""
            try:
                default_name = win32print.GetDefaultPrinter()
            except Exception:
                pass
            for info in raw:
                name = info["pPrinterName"]
                label = f"★ {name} (기본)" if name == default_name else f"  {name}"
                printers.append((label, name))
        except ImportError:
            # pywin32 미설치 — 대체 방법 (wmic)
            import subprocess, sys
            if sys.platform == "win32":
                try:
                    result = subprocess.run(
                        ["wmic", "printer", "get", "Name"],
                        capture_output=True, text=True, timeout=8)
                    for line in result.stdout.splitlines():
                        line = line.strip()
                        if line and line.lower() != "name":
                            printers.append((line, line))
                except Exception:
                    pass
        except Exception as e:
            self._net_printer_status_var.set(f"❌ 조회 실패: {str(e)[:60]}")
            return

        self._printer_listbox.delete(0, "end")
        self._printer_data = [p[1] for p in printers]  # 실제 프린터명 저장
        for label, _ in printers:
            self._printer_listbox.insert("end", label)

        if printers:
            self._net_printer_status_var.set(f"✅ {len(printers)}개 프린터 조회 완료")
        else:
            self._net_printer_status_var.set("프린터를 찾을 수 없습니다.")

    def _set_default_printer(self):
        """선택한 프린터를 기본 프린터로 설정"""
        sel = self._printer_listbox.curselection()
        if not sel:
            messagebox.showwarning("알림", "목록에서 프린터를 선택해주세요.")
            return
        idx = sel[0]
        printer_data = getattr(self, "_printer_data", [])
        if idx >= len(printer_data):
            return
        printer_name = printer_data[idx]
        try:
            import win32print  # type: ignore
            win32print.SetDefaultPrinter(printer_name)
            self._cfg["net_printer_name"] = printer_name
            self._cfg["net_printer_ip"]   = ""
            config.save_config(self._cfg)
            self._net_printer_status_var.set(f"✅ 기본 프린터 설정 완료: {printer_name}")
            # 목록 새로고침 (기본 표시 업데이트)
            self.after(200, self._refresh_printer_list)
        except ImportError:
            # pywin32 없이 레지스트리 방법 시도
            try:
                import subprocess
                subprocess.run(
                    ["rundll32", "printui.dll,PrintUIEntry",
                     "/y", "/n", printer_name],
                    timeout=5)
                self._cfg["net_printer_name"] = printer_name
                config.save_config(self._cfg)
                self._net_printer_status_var.set(f"✅ 기본 프린터 설정 완료: {printer_name}")
                self.after(200, self._refresh_printer_list)
            except Exception as e:
                self._net_printer_status_var.set(f"❌ 설정 실패: {str(e)[:60]}")
        except Exception as e:
            self._net_printer_status_var.set(f"❌ 설정 실패: {str(e)[:60]}")

    def _test_net_printer(self):
        """네트워크 프린터 연결 테스트 (ping)"""
        ip = self._net_printer_ip_var.get().strip()
        if not ip:
            messagebox.showwarning("알림", "프린터 IP를 입력해주세요.")
            return
        self._net_printer_status_var.set("연결 확인 중...")
        self.update_idletasks()

        def _ping():
            import subprocess, sys
            msg = "❌ 알 수 없는 오류"   # 명시적 초기화 (Agent 검증 반영)
            try:
                if sys.platform == "win32":
                    result = subprocess.run(
                        ["ping", "-n", "1", "-w", "2000", ip],
                        capture_output=True, text=True, timeout=5)
                else:
                    result = subprocess.run(
                        ["ping", "-c", "1", "-W", "2", ip],
                        capture_output=True, text=True, timeout=5)
                ok = result.returncode == 0
                msg = f"✅ {ip} 응답 확인" if ok else f"❌ {ip} 응답 없음 (방화벽 또는 IP 확인)"
            except Exception as e:
                msg = f"❌ 테스트 실패: {str(e)[:60]}"
            final_msg = msg   # lambda closure 안전 캡처
            self.after(0, lambda: self._net_printer_status_var.set(final_msg))

        threading.Thread(target=_ping, daemon=True).start()

    def _toggle_gpt_key_vis(self):
        self._gpt_show = not self._gpt_show
        self._gpt_entry.config(show="" if self._gpt_show else "*")

    def _save_gpt_key(self):
        self._cfg["chatgpt_api_key"] = self._gpt_key_var.get().strip()
        config.save_config(self._cfg)
        self._gpt_status_var.set("✅ API 키 저장 완료")

    def _test_gpt(self):
        key = self._gpt_key_var.get().strip()
        if not key:
            messagebox.showwarning("알림", "OpenAI API 키를 입력해주세요.")
            return
        self._gpt_status_var.set("연결 테스트 중...")
        self.update_idletasks()

        def _run():
            try:
                import openai
                client = openai.OpenAI(api_key=key)
                models = list(client.models.list())
                msg = f"연결 성공! (gpt-4o 포함 {len(models)}개 모델)"
                self.after(0, lambda: self._gpt_status_var.set(f"✅ {msg}"))
            except ImportError:
                self.after(0, lambda: self._gpt_status_var.set(
                    "❌ openai 패키지 미설치: pip install openai"))
            except Exception as e:
                err_msg = str(e)[:80]
                self.after(0, lambda: self._gpt_status_var.set(f"❌ {err_msg}"))

        threading.Thread(target=_run, daemon=True).start()

    def _toggle_gem_key_vis(self):
        self._gem_show = not self._gem_show
        self._gem_entry.config(show="" if self._gem_show else "*")

    def _toggle_cl_key_vis(self):
        self._cl_show = not self._cl_show
        self._cl_entry.config(show="" if self._cl_show else "*")

    def _save_cl_key(self):
        self._cfg["claude_api_key"] = self._cl_key_var.get().strip()
        config.save_config(self._cfg)
        self._cl_status_var.set("✅ API 키 저장 완료")

    def _test_cl(self):
        key = self._cl_key_var.get().strip()
        if not key:
            messagebox.showwarning("알림", "Claude API 키를 입력해주세요.")
            return
        self._cl_status_var.set("연결 테스트 중...")
        self.update_idletasks()
        def _run():
            ok, msg = claude.test_connection(key)
            self.after(0, lambda: self._cl_status_var.set(
                f"{'✅' if ok else '❌'} {msg}"))
        threading.Thread(target=_run, daemon=True).start()

    def _save_custom_prompt(self):
        self._cfg["custom_prompt_enabled"] = self._cp_enabled_var.get()
        self._cfg["custom_prompt_text"] = self._cp_text.get("1.0", "end").strip()
        config.save_config(self._cfg)
        messagebox.showinfo("저장 완료", "커스텀 프롬프트가 저장되었습니다.")

    def _reset_custom_prompt(self):
        self._cp_text.delete("1.0", "end")
        self._cp_enabled_var.set(False)

    def _refresh_prompt_templates(self):
        templates = self._cfg.get("custom_prompts", [])
        names = [t["name"] for t in templates]
        self._cp_tmpl_cb["values"] = names
        if names:
            self._cp_tmpl_cb.current(0)

    def _load_prompt_template(self):
        sel = self._cp_tmpl_cb.current()
        templates = self._cfg.get("custom_prompts", [])
        if sel < 0 or sel >= len(templates):
            messagebox.showwarning("알림", "불러올 템플릿을 선택해주세요.")
            return
        self._cp_text.delete("1.0", "end")
        self._cp_text.insert("1.0", templates[sel]["text"])

    def _save_prompt_template(self):
        name = simpledialog.askstring("템플릿 이름", "저장할 템플릿 이름:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        text = self._cp_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("알림", "저장할 내용을 입력해주세요.")
            return
        templates = self._cfg.get("custom_prompts", [])
        for t in templates:
            if t["name"] == name:
                t["text"] = text
                break
        else:
            templates = templates[-4:] + [{"name": name, "text": text}]  # 최대 5개
        self._cfg["custom_prompts"] = templates
        config.save_config(self._cfg)
        self._refresh_prompt_templates()
        messagebox.showinfo("저장 완료", f"템플릿 '{name}' 저장 완료!")

    def _delete_prompt_template(self):
        sel = self._cp_tmpl_cb.current()
        templates = self._cfg.get("custom_prompts", [])
        if sel < 0 or sel >= len(templates):
            messagebox.showwarning("알림", "삭제할 템플릿을 선택해주세요.")
            return
        name = templates[sel]["name"]
        if not messagebox.askyesno("삭제 확인", f"템플릿 '{name}'을(를) 삭제하시겠습니까?"):
            return
        templates.pop(sel)
        self._cfg["custom_prompts"] = templates
        config.save_config(self._cfg)
        self._refresh_prompt_templates()

    # ── CLOVA Speech 설정 메서드 ─────────────────────────

    def _toggle_clova_id_vis(self):
        self._clova_id_show = not self._clova_id_show
        self._clova_id_entry.config(show="" if self._clova_id_show else "*")

    def _toggle_clova_secret_vis(self):
        self._clova_secret_show = not self._clova_secret_show
        self._clova_secret_entry.config(show="" if self._clova_secret_show else "*")

    def _save_clova_keys(self):
        self._cfg["clova_invoke_url"] = self._clova_id_var.get().strip()
        self._cfg["clova_secret_key"] = self._clova_secret_var.get().strip()
        config.save_config(self._cfg)
        self._clova_status_var.set("✅ CLOVA API 키 저장 완료")
        # 파이프라인 STT 엔진도 동기화
        self._pipeline_stt_engine = self._cfg.get("stt_engine", "gemini")

    def _save_stt_engine(self):
        eng = self._stt_engine_var.get()
        self._cfg["stt_engine"] = eng
        self._pipeline_stt_engine = eng
        config.save_config(self._cfg)

    def _save_default_sum_mode(self):
        mode = self._default_sum_mode_var.get()
        self._cfg["summary_mode"] = mode
        self._pipeline_sum_mode = mode
        config.save_config(self._cfg)

    def _save_summary_engine(self):
        eng = self._summary_engine_var.get()
        self._cfg["summary_engine"] = eng
        self._pipeline_ai_engine = eng
        config.save_config(self._cfg)

    def _test_clova(self):
        invoke_url = self._clova_id_var.get().strip()
        secret_key = self._clova_secret_var.get().strip()
        if not invoke_url or not secret_key:
            messagebox.showwarning("알림", "Invoke URL과 Secret Key를 모두 입력해주세요.")
            return
        self._clova_status_var.set("연결 테스트 중...")
        self.update()
        ok, msg = clova.test_connection(invoke_url, secret_key)
        self._clova_status_var.set(("✅ " if ok else "❌ ") + msg)

    # ── Gemini 설정 메서드 ───────────────────────────────

    # ── Google Drive 폴더 설정 메서드 ──────────────────────

    def _save_drive_folder_settings(self):
        self._cfg["drive_mp3_folder_name"] = self._drv_mp3_name_var.get().strip() or "녹음파일"
        self._cfg["drive_txt_folder_name"] = self._drv_txt_name_var.get().strip() or "회의록(요약)"
        # URL 또는 ID 모두 허용 — parse_folder_id로 자동 추출
        mp3_raw = self._drv_mp3_id_var.get().strip()
        txt_raw = self._drv_txt_id_var.get().strip()
        mp3_id  = gdrive.parse_folder_id(mp3_raw)
        txt_id  = gdrive.parse_folder_id(txt_raw)
        self._cfg["drive_mp3_folder_id"] = mp3_id
        self._cfg["drive_txt_folder_id"] = txt_id
        if mp3_id != mp3_raw:
            self._drv_mp3_id_var.set(mp3_id)
        if txt_id != txt_raw:
            self._drv_txt_id_var.set(txt_id)
        config.save_config(self._cfg)
        self._drv_folder_status_var.set("✅ 폴더 ID 저장 완료")

    def _ensure_mp3_folder(self):
        name = self._drv_mp3_name_var.get().strip() or "녹음파일"
        self._drv_folder_status_var.set(f"Drive에서 '{name}' 폴더 찾는 중...")
        self.update()

        def _run():
            ok, fid, msg = gdrive.ensure_folder(name)
            def _done():
                if ok:
                    self._drv_mp3_id_var.set(fid)
                    self._cfg["drive_mp3_folder_id"]   = fid
                    self._cfg["drive_mp3_folder_name"] = name
                    config.save_config(self._cfg)
                    self._drv_folder_status_var.set(f"✅ MP3 폴더: {msg}")
                else:
                    self._drv_folder_status_var.set(f"❌ MP3 폴더 실패: {msg}")
            self.after(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    def _ensure_txt_folder(self):
        name = self._drv_txt_name_var.get().strip() or "회의록(요약)"
        self._drv_folder_status_var.set(f"Drive에서 '{name}' 폴더 찾는 중...")
        self.update()

        def _run():
            ok, fid, msg = gdrive.ensure_folder(name)
            def _done():
                if ok:
                    self._drv_txt_id_var.set(fid)
                    self._cfg["drive_txt_folder_id"]   = fid
                    self._cfg["drive_txt_folder_name"] = name
                    config.save_config(self._cfg)
                    self._drv_folder_status_var.set(f"✅ TXT 폴더: {msg}")
                else:
                    self._drv_folder_status_var.set(f"❌ TXT 폴더 실패: {msg}")
            self.after(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    def _ensure_both_folders(self):
        mp3_name = self._drv_mp3_name_var.get().strip() or "녹음파일"
        txt_name = self._drv_txt_name_var.get().strip() or "회의록(요약)"
        self._drv_folder_status_var.set("Drive에서 두 폴더 생성/찾는 중...")
        self.update()

        def _run():
            result = gdrive.init_drive_folders(mp3_name, txt_name)
            def _done():
                msgs = []
                if result["mp3_ok"]:
                    self._drv_mp3_id_var.set(result["mp3_id"])
                    self._cfg["drive_mp3_folder_id"]   = result["mp3_id"]
                    self._cfg["drive_mp3_folder_name"] = mp3_name
                    msgs.append(f"MP3: {result['mp3_msg']}")
                else:
                    msgs.append(f"MP3 실패: {result['mp3_msg']}")
                if result["txt_ok"]:
                    self._drv_txt_id_var.set(result["txt_id"])
                    self._cfg["drive_txt_folder_id"]   = result["txt_id"]
                    self._cfg["drive_txt_folder_name"] = txt_name
                    msgs.append(f"TXT: {result['txt_msg']}")
                else:
                    msgs.append(f"TXT 실패: {result['txt_msg']}")
                config.save_config(self._cfg)
                self._drv_folder_status_var.set(" | ".join(msgs))
            self.after(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    # ── Gemini 설정 메서드 ───────────────────────────────

    def _save_gem_key(self):
        self._cfg["gemini_api_key"] = self._gem_key_var.get().strip()
        config.save_config(self._cfg)
        self._gem_status_var.set("✅ API 키 저장 완료")

    def _test_gem(self):
        key = self._gem_key_var.get().strip()
        if not key:
            messagebox.showwarning("알림", "API 키를 입력해주세요.")
            return
        self._gem_status_var.set("연결 테스트 중...")
        self.update()
        ok, msg = gemini.test_connection(key)
        self._gem_status_var.set(("✅ " if ok else "❌ ") + msg)

    def _change_recording_dir(self):
        """루트 저장 폴더 변경 (v3 — 3폴더 모두 하위로 이동)"""
        d = filedialog.askdirectory(
            title="루트 저장 폴더 선택",
            initialdir=self._cfg.get("recording_dir", str(Path.home() / "Documents")))
        if d:
            self._cfg["recording_dir"] = d
            config.save_config(self._cfg)
            config.reload_paths()
            self._rec_dir_var.set(d)
            if hasattr(self, "_mp3_path_lbl"):
                self._mp3_path_lbl.config(text=str(config.MP3_SAVE_DIR))
            if hasattr(self, "_stt_path_lbl"):
                self._stt_path_lbl.config(text=str(config.STT_SAVE_DIR))
            if hasattr(self, "_sum_path_lbl"):
                self._sum_path_lbl.config(text=str(config.SUMMARY_SAVE_DIR))
            messagebox.showinfo("저장 경로 변경",
                                f"✅ 루트 경로가 변경되었습니다.\n\n"
                                f"① MP3: {config.MP3_SAVE_DIR}\n"
                                f"② STT: {config.STT_SAVE_DIR}\n"
                                f"③ 회의록: {config.SUMMARY_SAVE_DIR}")

    def _save_subdir_settings(self):
        """MP3/STT/회의록 서브폴더명 저장 (v3 — 3폴더)"""
        mp3_sub     = self._mp3_sub_var.get().strip()
        stt_sub     = self._stt_sub_var.get().strip() if hasattr(self, "_stt_sub_var") else "STT변환본"
        summary_sub = self._sum_sub_var.get().strip()
        if not mp3_sub or not stt_sub or not summary_sub:
            messagebox.showwarning("알림", "폴더명을 비워둘 수 없습니다.")
            return
        self._cfg["mp3_subdir"]     = mp3_sub
        self._cfg["audio_subdir"]   = mp3_sub   # 하위 호환
        self._cfg["stt_subdir"]     = stt_sub
        self._cfg["summary_subdir"] = summary_sub
        config.save_config(self._cfg)
        config.reload_paths()
        if hasattr(self, "_mp3_path_lbl"):
            self._mp3_path_lbl.config(text=str(config.MP3_SAVE_DIR))
        if hasattr(self, "_stt_path_lbl"):
            self._stt_path_lbl.config(text=str(config.STT_SAVE_DIR))
        if hasattr(self, "_sum_path_lbl"):
            self._sum_path_lbl.config(text=str(config.SUMMARY_SAVE_DIR))
        messagebox.showinfo("저장 완료",
                            f"✅ 폴더명이 변경되었습니다.\n\n"
                            f"① MP3: {config.MP3_SAVE_DIR}\n"
                            f"② STT: {config.STT_SAVE_DIR}\n"
                            f"③ 회의록: {config.SUMMARY_SAVE_DIR}")

    # ════════════════════════════════════════════════════
    # 유틸
    # ════════════════════════════════════════════════════
    def _card(self, parent, title: str, row: int = None):
        frame = tk.Frame(parent, bg=CARD_BG,
                         relief="flat", bd=0,
                         highlightthickness=1,
                         highlightbackground=BORDER)
        inner = tk.Frame(frame, bg=CARD_BG)
        inner.pack(fill="both", expand=True, padx=12, pady=8)
        tk.Label(inner, text=title, font=FONT_H2,
                 bg=CARD_BG, fg=TEXT).pack(anchor="w", pady=(0, 8))
        ttk.Separator(inner).pack(fill="x", pady=(0, 8))
        self._last_card = inner
        return frame

    @staticmethod
    def _btn(parent, text, color, cmd, w=10):
        b = tk.Button(parent, text=text, bg=color, fg=WHITE,
                      font=FONT_BTN, width=w, relief="flat",
                      activebackground=ACCENT_DARK, activeforeground=WHITE,
                      cursor="hand2", command=cmd, pady=6)
        return b

    @staticmethod
    def _set_prog(bar, value):
        bar["value"] = value

    def _tick(self):
        if self._recorder.state in ("recording", "paused"):
            self._elapsed_var.set(self._recorder.get_elapsed_str())
            self._level_bar["value"] = self._recorder.get_level() * 100
        else:
            self._level_bar["value"] = 0
        self.after(300, self._tick)

    # ── 영역 B 메서드들 ─────────────────────────────────

    def _b_pick_stt_file(self):
        """STT 파일 선택 (*.md)"""
        path = filedialog.askopenfilename(
            title="STT 변환 파일 선택",
            filetypes=[("Markdown 파일", "*.md"), ("텍스트 파일", "*.txt"), ("모든 파일", "*.*")],
            initialdir=str(config.STT_SAVE_DIR)
        )
        if path:
            self._b_stt_path = path
            self._b_stt_file_var.set(Path(path).name)
            self._b_status_var.set("")

    def _b_stop_convert(self):
        """영역 B 변환 중지"""
        if hasattr(self, "_b_cancel_event") and self._b_cancel_event:
            self._b_cancel_event.set()

    def _b_convert_meeting(self):
        """영역 B: STT 파일 → 회의록 변환"""
        if not self._b_stt_path or not Path(self._b_stt_path).exists():
            messagebox.showwarning("알림", "STT 파일을 선택해주세요.")
            return

        # 요약 방식 선택 팝업
        dlg = tk.Toplevel(self)
        dlg.title("요약 방식 선택")
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text="요약 방식을 선택하세요:", font=FONT_BODY,
                 bg=BG, fg=TEXT).pack(padx=20, pady=(16, 8))

        default_mode = self._cfg.get("summary_mode", "speaker")
        sum_mode_var = tk.StringVar(value=default_mode)
        frm = tk.Frame(dlg, bg=BG)
        frm.pack(padx=20, pady=4)
        for label, val in [
            ("주간회의 — K-Run Ventures 파트너 주간회의록", "speaker"),
            ("다자간 협의 — 기관협의·다자간 공식회의·다자간 네트워킹", "topic"),
            ("회의록(업무) — 직전 투자심사 외부 미팅·투자업체 사후관리", "formal_md"),
            ("IR 미팅회의록 ★신규★ — 피투자사 IR 미팅 전문 정리", "ir_md"),
            ("강의 요약 — 학습/세미나 특화", "lecture_md"),
            ("네트워킹(티타임) — 티타임·비공식 네트워킹 대화 정리", "flow"),
            ("전화통화 메모 — 통화 내용 주제별 요약 + 질의응답", "phone"),
        ]:
            fg = SUCCESS if val == "ir_md" else TEXT
            tk.Radiobutton(frm, text=label, variable=sum_mode_var, value=val,
                           bg=BG, font=FONT_BODY, fg=fg,
                           activebackground=BG).pack(anchor="w")

        confirmed = {"ok": False}
        def _ok():
            confirmed["ok"] = True
            dlg.destroy()
        def _cancel():
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(pady=12)
        self._btn(btn_row, "변환 시작", ACCENT, _ok, w=12).pack(side="left", padx=6)
        self._btn(btn_row, "취소", TEXT_LIGHT, _cancel, w=8).pack(side="left", padx=6)
        dlg.wait_window()

        if not confirmed["ok"]:
            return

        chosen_mode = sum_mode_var.get()

        # IR 미팅 모드 선택 시 기업명 입력 (혁신의숲 API 조회용)
        chosen_company_name = ""
        if chosen_mode == "ir_md":
            name = simpledialog.askstring(
                "기업명 입력",
                "혁신의숲 조회 기업명을 입력하세요:\n(정확한 법인명 입력 권장, 빈칸 시 API 조회 생략)",
                parent=self,
            )
            chosen_company_name = (name or "").strip()

        # STT 텍스트 읽기
        try:
            stt_text = Path(self._b_stt_path).read_text(encoding="utf-8")
        except Exception as e:
            messagebox.showerror("오류", f"STT 파일 읽기 실패: {e}")
            return

        # 커스텀 프롬프트 (1회성)
        custom_inst = self._b_custom_prompt.get().strip()
        # 설정 탭 전역 프롬프트 + 1회성 프롬프트 결합
        global_prompt = ""
        if self._cfg.get("custom_prompt_enabled") and self._cfg.get("custom_prompt_text"):
            global_prompt = self._cfg["custom_prompt_text"]
        combined_inst = "\n".join(filter(None, [global_prompt, custom_inst]))

        # UI 초기화
        self._b_cancel_event = threading.Event()
        self._btn_b_convert.config(state="disabled")
        self._btn_b_stop.config(state="normal")
        self._b_result_box.config(state="normal")
        self._b_result_box.delete("1.0", "end")
        self._b_result_box.config(state="disabled")
        self._b_status_var.set("요약 중...")

        mode_label_map = {
            "speaker": "주간회의", "topic": "다자간 협의",
            "formal_md": "회의록(업무)", "ir_md": "IR미팅회의록",
            "lecture_md": "강의요약", "flow": "네트워킹(티타임)", "phone": "전화통화메모"
        }
        mode_label = mode_label_map.get(chosen_mode, chosen_mode)

        def _run():
            import gemini_service as gs
            import claude_service as cs

            engine = self._cfg.get("summary_engine", "gemini")
            has_chatgpt = bool(self._cfg.get("chatgpt_api_key", "").strip())
            has_claude  = bool(self._cfg.get("claude_api_key", "").strip())
            has_gemini  = bool(self._cfg.get("gemini_api_key", "").strip())

            def prog(v):
                self._b_status_var.set(f"요약 중... {v}%")

            if engine == "claude" and has_claude:
                ok, result = cs.summarize(
                    stt_text, self._cfg.get("claude_api_key"),
                    progress_cb=prog, summary_mode=chosen_mode,
                    cancel_event=self._b_cancel_event,
                    custom_instruction=combined_inst)
            elif engine == "chatgpt" and has_chatgpt:
                ok, result = self._summarize_with_chatgpt(
                    stt_text, self._cfg.get("chatgpt_api_key"),
                    progress_cb=prog, summary_mode=chosen_mode,
                    cancel_event=self._b_cancel_event,
                    custom_instruction=combined_inst)
            else:
                ok, result = gs.summarize(
                    stt_text, self._cfg.get("gemini_api_key", ""),
                    progress_cb=prog, summary_mode=chosen_mode,
                    cancel_event=self._b_cancel_event,
                    custom_instruction=combined_inst,
                    company_name=chosen_company_name)

            if self._b_cancel_event.is_set():
                self.after(0, lambda: self._b_status_var.set("중지되었습니다."))
                self.after(0, lambda: self._btn_b_convert.config(state="normal"))
                self.after(0, lambda: self._btn_b_stop.config(state="disabled"))
                return

            if ok:
                self.after(0, lambda r=result: self._b_on_success(r, mode_label, combined_inst, chosen_mode))
            else:
                err = result
                self.after(0, lambda e=err: self._b_status_var.set(f"❌ 오류: {e}"))
                self.after(0, lambda: self._btn_b_convert.config(state="normal"))
                self.after(0, lambda: self._btn_b_stop.config(state="disabled"))

        threading.Thread(target=_run, daemon=True).start()

    def _b_on_success(self, summary_text: str, mode_label: str, custom_inst: str,
                      sum_mode: str = ""):
        """영역 B 변환 완료 처리"""
        # 결과 표시
        self._b_result_box.config(state="normal")
        self._b_result_box.delete("1.0", "end")
        self._b_result_box.insert("1.0", summary_text)
        self._b_result_box.config(state="disabled")
        self._btn_b_convert.config(state="normal")
        self._btn_b_stop.config(state="disabled")

        # 파일명 suffix 결정
        suffix = f"_{mode_label}"
        if custom_inst.strip():
            suffix += "_커스텀요약"

        # 기본 파일명 (STT 파일명 기반)
        stt_stem = Path(self._b_stt_path).stem
        # _stt 제거
        if stt_stem.endswith("_stt"):
            stt_stem = stt_stem[:-4]
        default_name = stt_stem + suffix + ".md"

        # 저장 다이얼로그
        out_path = filedialog.asksaveasfilename(
            title="회의록 저장",
            initialfile=default_name,
            initialdir=str(config.SUMMARY_SAVE_DIR),
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("모든 파일", "*.*")]
        )
        if not out_path:
            self._b_status_var.set("저장 취소됨. 텍스트는 위에서 복사 가능합니다.")
            return

        try:
            Path(out_path).write_text(summary_text, encoding="utf-8")
            self._b_status_var.set(f"✅ 저장 완료: {Path(out_path).name}")
            # DB 저장
            import database as db
            mid = db.save_meeting(
                file_name=Path(out_path).stem,
                summary_text=summary_text,
                summary_local_path=out_path,
                stt_local_path=self._b_stt_path,
                summary_mode=mode_label,
            )
            # 회의목록 갱신
            self._refresh_list()

            # Obsidian 저장 (자동 저장 ON인 경우)
            if self._cfg.get("obsidian_auto_save", True):
                obs_result = self._save_obsidian_note(
                    summary_text,
                    Path(out_path).stem,
                    mode=sum_mode or self._pipeline_sum_mode,
                )
                self._b_status_var.set(
                    self._b_status_var.get() + f"  |  {obs_result}"
                )

            if messagebox.askyesno("저장 완료",
                                   f"회의록이 저장되었습니다.\n\n{out_path}\n\n파일 위치를 탐색기에서 열겠습니까?"):
                import file_manager as fm
                fm.open_file_in_explorer(out_path)
        except Exception as e:
            messagebox.showerror("저장 오류", str(e))


# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
