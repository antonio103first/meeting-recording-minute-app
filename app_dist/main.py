"""
회의녹음요약 - 메인 GUI (배포용)
탭 구성: 녹음/변환 | 회의목록 | 설정
자동화 파이프라인: STT → (화자이름) → 요약 → 로컬 저장 → Drive 업로드(선택)
Google Drive A방식: 각 사용자가 직접 OAuth 자격증명 설정
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

        # 앱 데이터 초기화
        config.ensure_dirs()
        database.init_database()
        self._cfg = config.load_config()

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
        self._pipeline_ai_engine   = "gemini"   # "gemini" | "claude"
        self._pipeline_stt_engine  = self._cfg.get("stt_engine", "gemini")  # "gemini" | "clova"
        self._pipeline_rename_spk  = False
        self._current_sum_path     = None
        self._metrics_text         = ""

        self._build_ui()
        self._apply_style()
        self._refresh_list()
        self._tick()

        # 첫 실행 마법사 (API 키 없을 때)
        if not self._cfg.get("gemini_api_key", "").strip():
            self.after(200, self._show_first_run_wizard)

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
                        font=("맑은 고딕", 10, "bold"),
                        padding=[12, 8],
                        background="#DDE3EA",
                        foreground=TEXT)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", WHITE)])
        style.configure("TProgressbar", troughcolor=BORDER,
                        background=ACCENT, thickness=12)

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
        self._spk_var = tk.IntVar(value=2)
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

        # ─ 섹션 4: 핵심 지표 ────────────────────────────
        self._card(inner, "📊 핵심 지표").pack(fill="x", **pad)
        metrics_card = self._last_card

        self._metrics_prog = ttk.Progressbar(metrics_card, maximum=100, length=500)
        self._metrics_prog.pack(pady=2)
        self._metrics_status_var = tk.StringVar(value="요약 완료 후 자동 추출됩니다.")
        tk.Label(metrics_card, textvariable=self._metrics_status_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack()

        self._metrics_box = scrolledtext.ScrolledText(
            metrics_card, height=6, font=FONT_BODY, wrap="word",
            bg="#FAFAFA", relief="solid", bd=1, state="disabled")
        self._metrics_box.pack(fill="x")

    # ════════════════════════════════════════════════════
    # 탭 2 : 회의 목록
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

        # ─ 하단 패널: 버튼 + 내용보기 ──────────────────
        bot_frame = tk.Frame(paned, bg=BG)

        btn_row = tk.Frame(bot_frame, bg=BG)
        btn_row.pack(fill="x", pady=(4, 4))
        self._btn(btn_row, "📄 내용 보기", ACCENT,
                  self._view_meeting, w=12).pack(side="left", padx=4)
        self._btn(btn_row, "🗑 삭제", DANGER,
                  self._delete_meeting, w=10).pack(side="left", padx=4)

        self._detail_box = scrolledtext.ScrolledText(
            bot_frame, font=FONT_BODY, wrap="word",
            bg=CARD_BG, relief="solid", bd=1)
        self._detail_box.pack(fill="both", expand=True)
        paned.add(bot_frame, weight=1)

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
        tk.Label(drv_card, text="📁 업로드 폴더 설정",
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

        # ─ 저장 경로 설정 ────────────────────────────────
        self._card(inner, "📁 저장 경로 설정").pack(fill="x", **pad)
        path_card = self._last_card

        self._rec_dir_var = tk.StringVar(value=str(config.RECORDING_BASE))
        dir_row = tk.Frame(path_card, bg=CARD_BG)
        dir_row.pack(fill="x", pady=4)
        tk.Label(dir_row, text="녹음 저장 폴더:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        tk.Label(dir_row, textvariable=self._rec_dir_var,
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left", padx=4)
        self._btn(dir_row, "📂 변경", ACCENT,
                  self._change_recording_dir, w=8).pack(side="right")

        # 서브폴더명 편집 — 녹음파일
        audio_row = tk.Frame(path_card, bg=CARD_BG)
        audio_row.pack(fill="x", pady=3)
        tk.Label(audio_row, text="녹음파일 폴더명:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        self._audio_sub_var = tk.StringVar(
            value=self._cfg.get("audio_subdir", "녹음파일"))
        tk.Entry(audio_row, textvariable=self._audio_sub_var,
                 width=18, font=FONT_SMALL).pack(side="left", padx=4)
        self._btn(audio_row, "저장", ACCENT,
                  self._save_subdir_settings, w=6).pack(side="left")
        self._audio_path_lbl = tk.Label(audio_row,
            text=str(config.AUDIO_SAVE_DIR),
            font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT)
        self._audio_path_lbl.pack(side="left", padx=6)

        # 서브폴더명 편집 — 회의록(요약)
        sum_row = tk.Frame(path_card, bg=CARD_BG)
        sum_row.pack(fill="x", pady=3)
        tk.Label(sum_row, text="회의록 폴더명:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        self._sum_sub_var = tk.StringVar(
            value=self._cfg.get("summary_subdir", "회의록(요약)"))
        tk.Entry(sum_row, textvariable=self._sum_sub_var,
                 width=18, font=FONT_SMALL).pack(side="left", padx=4)
        self._btn(sum_row, "저장", ACCENT,
                  self._save_subdir_settings, w=6).pack(side="left")
        self._sum_path_lbl = tk.Label(sum_row,
            text=str(config.SUMMARY_SAVE_DIR),
            font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT)
        self._sum_path_lbl.pack(side="left", padx=6)

        # 앱 데이터 경로 표시
        appdata_row = tk.Frame(path_card, bg=CARD_BG)
        appdata_row.pack(fill="x", pady=2)
        tk.Label(appdata_row, text="앱 데이터:", font=FONT_BODY,
                 bg=CARD_BG, fg=TEXT, width=14, anchor="w").pack(side="left")
        tk.Label(appdata_row, text=str(config.APP_DATA_DIR),
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left")

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
                result, str(config.AUDIO_SAVE_DIR), default_name)
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
        dlg.geometry(f"500x470+{x}+{y}")
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
        tk.Radiobutton(frm1, text="화자 중심 — 참석자별 발언 정리",
                       variable=sum_mode_var, value="speaker",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="주제 중심 — 안건별 논의 정리",
                       variable=sum_mode_var, value="topic",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="업무미팅 회의록 (MD) — 비즈니스 컨설턴트 스타일, 마크다운",
                       variable=sum_mode_var, value="formal_md",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="업무미팅 회의록 (텍스트) — 비즈니스 컨설턴트 스타일, 일반 텍스트",
                       variable=sum_mode_var, value="formal_text",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="강의 요약 (MD) — 소주제별 논리적 정리, 신앙/업무 강의 자동 적응",
                       variable=sum_mode_var, value="lecture_md",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")

        # AI 엔진
        frm_ai = tk.LabelFrame(dlg, text="  AI 요약 엔진  ", font=FONT_BODY,
                               bg=CARD_BG, fg=TEXT, padx=12, pady=6)
        frm_ai.pack(fill="x", padx=20, pady=4)
        ai_var = tk.StringVar(value=self._pipeline_ai_engine)
        has_claude = bool(self._cfg.get("claude_api_key", "").strip())
        tk.Radiobutton(frm_ai, text="Gemini (Google)",
                       variable=ai_var, value="gemini",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm_ai,
                       text="Claude (Anthropic)" + ("" if has_claude else "  ← 설정 탭에서 API 키 입력"),
                       variable=ai_var, value="claude",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       state="normal" if has_claude else "disabled").pack(anchor="w")

        confirmed = {"ok": False}

        def _confirm():
            confirmed["ok"] = True
            self._pipeline_sum_mode  = sum_mode_var.get()
            self._pipeline_ai_engine = ai_var.get()
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        ttk.Separator(dlg).pack(fill="x", padx=20, pady=8)
        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=8)
        self._btn(btn_row, "📋 요약 시작", "#8E44AD", _confirm, w=16).pack(side="left", padx=8)
        self._btn(btn_row, "취소", TEXT_LIGHT, _cancel, w=8).pack(side="left", padx=6)
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

        # ① 팝업: 요약 방식 선택 + 화자 이름 변경 여부
        dlg = tk.Toplevel(self)
        dlg.title("변환 옵션 선택")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.focus_set()

        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() // 2 - 250
        y = self.winfo_y() + self.winfo_height() // 2 - 240
        dlg.geometry(f"520x570+{x}+{y}")
        dlg.configure(bg=CARD_BG)

        tk.Label(dlg, text="변환 옵션 선택", font=FONT_H2,
                 bg=CARD_BG, fg=TEXT).pack(pady=(14, 2))
        ttk.Separator(dlg).pack(fill="x", padx=20, pady=4)

        # ─ 요약 방식 ─────────────────────────────────────
        frm1 = tk.LabelFrame(dlg, text="  요약 방식  ", font=FONT_BODY,
                              bg=CARD_BG, fg=TEXT, padx=12, pady=6)
        frm1.pack(fill="x", padx=20, pady=4)
        sum_mode_var = tk.StringVar(value="speaker")
        tk.Radiobutton(frm1, text="화자 중심 — 참석자별 발언 정리",
                       variable=sum_mode_var, value="speaker",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="주제 중심 — 안건별 논의 정리",
                       variable=sum_mode_var, value="topic",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="업무미팅 회의록 (MD) — 비즈니스 컨설턴트 스타일, 마크다운",
                       variable=sum_mode_var, value="formal_md",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="업무미팅 회의록 (텍스트) — 비즈니스 컨설턴트 스타일, 일반 텍스트",
                       variable=sum_mode_var, value="formal_text",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm1, text="강의 요약 (MD) — 소주제별 논리적 정리, 신앙/업무 강의 자동 적응",
                       variable=sum_mode_var, value="lecture_md",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")

        # ─ STT 엔진 ──────────────────────────────────────
        has_clova = (bool(self._cfg.get("clova_invoke_url", "").strip()) and
                     bool(self._cfg.get("clova_secret_key", "").strip()))
        frm_stt = tk.LabelFrame(dlg, text="  STT 변환 엔진  ", font=FONT_BODY,
                                bg=CARD_BG, fg=TEXT, padx=12, pady=6)
        frm_stt.pack(fill="x", padx=20, pady=4)
        stt_var = tk.StringVar(value=self._pipeline_stt_engine)
        tk.Radiobutton(frm_stt, text="Gemini (Google)",
                       variable=stt_var, value="gemini",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        tk.Radiobutton(frm_stt,
                       text="CLOVA Speech (NAVER) — 한국어 특화, 타임아웃 없음 ★권장★" +
                            ("" if has_clova else "  ← 설정 탭에서 API 키 입력"),
                       variable=stt_var, value="clova",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       state="normal" if has_clova else "disabled").pack(anchor="w")

        # ─ AI 엔진 ───────────────────────────────────────
        frm_ai = tk.LabelFrame(dlg, text="  AI 요약 엔진  ", font=FONT_BODY,
                               bg=CARD_BG, fg=TEXT, padx=12, pady=8)
        frm_ai.pack(fill="x", padx=20, pady=4)
        ai_var = tk.StringVar(value="gemini")
        has_claude = bool(self._cfg.get("claude_api_key", "").strip())
        tk.Radiobutton(frm_ai, text="Gemini (Google)",
                       variable=ai_var, value="gemini",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG).pack(anchor="w")
        claude_rb = tk.Radiobutton(frm_ai, text="Claude (Anthropic)" + ("" if has_claude else "  ← 설정 탭에서 API 키 입력"),
                       variable=ai_var, value="claude",
                       bg=CARD_BG, font=FONT_BODY, activebackground=CARD_BG,
                       state="normal" if has_claude else "disabled")
        claude_rb.pack(anchor="w")

        # ─ 화자 이름 변경 ─────────────────────────────────
        frm2 = tk.LabelFrame(dlg, text="  화자 이름 변경  ", font=FONT_BODY,
                              bg=CARD_BG, fg=TEXT, padx=12, pady=8)
        frm2.pack(fill="x", padx=20, pady=4)
        rename_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frm2, text="STT 완료 후 화자 이름을 직접 입력합니다",
                       variable=rename_var, bg=CARD_BG, font=FONT_BODY,
                       activebackground=CARD_BG).pack(anchor="w")

        confirmed = {"ok": False}

        def _confirm():
            confirmed["ok"] = True
            self._pipeline_sum_mode   = sum_mode_var.get()
            self._pipeline_ai_engine  = ai_var.get()
            self._pipeline_stt_engine = stt_var.get()
            self._pipeline_rename_spk = rename_var.get()
            dlg.destroy()

        def _cancel():
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=CARD_BG)
        btn_row.pack(pady=12)
        self._btn(btn_row, "▶ 변환 시작", ACCENT, _confirm, w=14).pack(side="left", padx=6)
        self._btn(btn_row, "취소", TEXT_LIGHT, _cancel, w=8).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        self.wait_window(dlg)

        if not confirmed["ok"]:
            return

        # ② STT 변환 시작
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
            else:
                ok, text = gemini.summarize(
                    stt_text, api_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_inst,
                )
            self.after(0, lambda: self._on_pipeline_summary_done(ok, text, stt_text))

        threading.Thread(target=run_sum, daemon=True).start()

    def _on_pipeline_summary_done(self, ok: bool, text: str, stt_text: str):
        """④ 요약 완료 → ⑤ 파일명 입력 → ⑥ 로컬 저장"""
        self._processing = False
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
            ok2, path = fm.save_stt_text(stt_text, str(config.SUMMARY_SAVE_DIR),
                                         save_name + "_녹음")
            if ok2:
                stt_path = path
                msgs.append(f"✅ STT 저장: {Path(path).name}")
            else:
                msgs.append(f"❌ STT 저장 실패: {path}")

        if text:
            ok3, path = fm.save_summary_text(text, str(config.SUMMARY_SAVE_DIR),
                                             save_name + "_요약")
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

        if results.get("mp3", {}).get("ok"):
            drive_mp3_link = results["mp3"]["link"]
            msgs.append(f"☁ MP3 Drive 업로드 완료")
        elif "mp3" in results:
            msgs.append(f"❌ MP3 Drive 실패: {results['mp3']['msg'][:40]}")

        if results.get("stt", {}).get("ok"):
            drive_stt_link = results["stt"]["link"]
            msgs.append(f"☁ STT Drive 업로드 완료")
        elif "stt" in results:
            msgs.append(f"❌ STT Drive 실패: {results['stt']['msg'][:40]}")

        if results.get("summary", {}).get("ok"):
            drive_sum_link = results["summary"]["link"]
            msgs.append(f"☁ 요약 Drive 업로드 완료")
        elif "summary" in results:
            msgs.append(f"❌ 요약 Drive 실패: {results['summary']['msg'][:40]}")

        self._finalize_save(mp3_path, stt_path, sum_path, save_name,
                            stt_text, text, msgs,
                            drive_mp3_link, drive_stt_link, drive_sum_link)

    def _finalize_save(self, mp3_path, stt_path, sum_path, save_name,
                       stt_text, text, msgs,
                       drive_mp3_link, drive_stt_link, drive_sum_link):
        """DB 저장 + 완료 팝업"""
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

        # 저장 상태 표시
        self._save_status_var.set(" | ".join(msgs))

        # 완료 팝업
        result_lines = ["🎉 처리 완료!", ""]
        result_lines += msgs
        result_lines += ["", f"📁 저장 위치: {config.RECORDING_BASE}"]
        if drive_mp3_link or drive_stt_link or drive_sum_link:
            result_lines += ["", "☁ Google Drive 링크:", drive_mp3_link or ""]
        messagebox.showinfo("완료", "\n".join(result_lines))

        # ⑧ 핵심 지표 자동 추출
        self._start_metrics_extraction(text)

    def _start_metrics_extraction(self, summary_text: str):
        """⑧ 핵심 지표 자동 추출 (요약 완료 후 자동 실행)"""
        api_key = self._cfg.get("gemini_api_key", "")
        self._metrics_prog["value"] = 0
        self._metrics_status_var.set("핵심 지표 추출 중...")
        self._metrics_box.config(state="normal")
        self._metrics_box.delete("1.0", "end")
        self._metrics_box.config(state="disabled")

        def run():
            ok, text = gemini.extract_key_metrics(
                summary_text, api_key,
                cancel_event=self._cancel_event,
                status_cb=lambda msg: self.after(0, lambda: self._metrics_status_var.set(msg)),
            )
            self.after(0, lambda: self._on_metrics_done(ok, text))

        threading.Thread(target=run, daemon=True).start()

    def _on_metrics_done(self, ok: bool, text: str):
        """핵심 지표 추출 완료 콜백"""
        self._set_prog(self._metrics_prog, 100)
        if ok:
            self._metrics_text = text
            self._metrics_status_var.set("✅ 핵심 지표 추출 완료!")
            self._metrics_box.config(state="normal")
            self._metrics_box.delete("1.0", "end")
            self._metrics_box.insert("1.0", text)
            self._metrics_box.config(state="disabled")
            if self._current_sum_path:
                try:
                    with open(self._current_sum_path, "a", encoding="utf-8") as f:
                        f.write(f"\n\n{'='*40}\n📊 핵심 지표\n{'='*40}\n{text}\n")
                except Exception:
                    pass
        else:
            self._metrics_status_var.set(f"❌ 추출 실패: {text[:60]}")

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
            else:
                ok, text = gemini.summarize(
                    self._stt_text, api_key,
                    progress_cb=lambda v: self.after(0, lambda: self._set_prog(self._sum_prog, v)),
                    summary_mode=self._pipeline_sum_mode,
                    cancel_event=self._cancel_event,
                    custom_instruction=custom_text,
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
                                         save_name + "_요약")
        if ok3:
            sum_path = path
            self._current_sum_path = path
            msgs.append(f"✅ 요약 저장: {Path(path).name}")
        else:
            msgs.append(f"❌ 요약 저장 실패: {path}")

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

        self._start_metrics_extraction(text)

    def _cancel_process(self):
        """■ 중단 버튼"""
        self._cancel_event.set()
        self._stt_status_var.set("중단 요청됨...")
        self._sum_status_var.set("중단 요청됨...")

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
        sel = self._tree.selection()
        if not sel:
            return
        mid  = int(sel[0])
        data = database.get_meeting(mid)
        self._detail_box.delete("1.0", "end")
        self._detail_box.insert("1.0",
            f"=== 요약 ===\n{data.get('summary_text','(없음)')}\n\n"
            f"=== STT 원문 ===\n{data.get('stt_text','(없음)')}")

    def _view_meeting(self):
        self._on_list_select(None)

    def _delete_meeting(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("알림", "삭제할 항목을 선택해주세요.")
            return
        if messagebox.askyesno("확인", "선택한 항목을 삭제할까요?"):
            database.delete_meeting(int(sel[0]))
            self._refresh_list()

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
        self._cfg["drive_mp3_folder_id"]   = self._drv_mp3_id_var.get().strip()
        self._cfg["drive_txt_folder_id"]   = self._drv_txt_id_var.get().strip()
        config.save_config(self._cfg)
        self._drv_folder_status_var.set("✅ 폴더 설정 저장 완료")

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
        """녹음 저장 폴더 변경"""
        d = filedialog.askdirectory(
            title="녹음 저장 폴더 선택",
            initialdir=self._cfg.get("recording_dir", str(Path.home() / "Documents")))
        if d:
            self._cfg["recording_dir"] = d
            config.save_config(self._cfg)
            config.reload_paths()
            self._rec_dir_var.set(d)
            self._audio_path_lbl.config(text=str(config.AUDIO_SAVE_DIR))
            self._sum_path_lbl.config(text=str(config.SUMMARY_SAVE_DIR))
            messagebox.showinfo("저장 경로 변경",
                                f"✅ 저장 경로가 변경되었습니다.\n\n"
                                f"녹음파일: {config.AUDIO_SAVE_DIR}\n"
                                f"회의록(요약): {config.SUMMARY_SAVE_DIR}")

    def _save_subdir_settings(self):
        """녹음파일/회의록(요약) 서브폴더명 저장"""
        audio_sub   = self._audio_sub_var.get().strip()
        summary_sub = self._sum_sub_var.get().strip()
        if not audio_sub or not summary_sub:
            messagebox.showwarning("알림", "폴더명을 비워둘 수 없습니다.")
            return
        self._cfg["audio_subdir"]   = audio_sub
        self._cfg["summary_subdir"] = summary_sub
        config.save_config(self._cfg)
        config.reload_paths()
        self._audio_path_lbl.config(text=str(config.AUDIO_SAVE_DIR))
        self._sum_path_lbl.config(text=str(config.SUMMARY_SAVE_DIR))
        messagebox.showinfo("저장 완료",
                            f"✅ 폴더명이 변경되었습니다.\n\n"
                            f"녹음파일: {config.AUDIO_SAVE_DIR}\n"
                            f"회의록(요약): {config.SUMMARY_SAVE_DIR}")

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


# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
