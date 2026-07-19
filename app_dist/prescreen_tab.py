# -*- coding: utf-8 -*-
"""
예비검토보고서 탭 (Roundtable v4.0)
────────────────────────────────────
IR 자료(PPT/PDF/이미지)를 선택하면 예비검토보고서를 만들어 Obsidian에 저장한다.

엔진은 이 앱에 복사하지 않고 Prescreening_Report 저장소에서 **런타임 로드**한다.
복사하면 스킬을 고칠 때마다 두 벌이 갈라진다 — 엔진이 SSOT다.
엔진 경로가 없으면 기능을 잠그고 안내한다(조용히 실패하지 않는다).
"""
import os
import queue
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext

import config

BG = "#F5F6FA"
CARD_BG = "#FFFFFF"
BORDER = "#E0E0E0"
TEXT = "#2C3E50"
TEXT_LIGHT = "#7F8C8D"
ACCENT = "#3498DB"
SUCCESS = "#27AE60"
DANGER = "#E74C3C"
WARNING = "#F39C12"

FONT_H2 = ("맑은 고딕", 12, "bold")
FONT_BODY = ("맑은 고딕", 10)
FONT_SMALL = ("맑은 고딕", 9)
FONT_BTN = ("맑은 고딕", 10, "bold")

DEFAULT_ENGINE_HOME = r"C:\Users\anton\Documents\Claude AI_Personal\Prescreening_Report"
IR_FILETYPES = [
    ("IR 자료", "*.pdf *.pptx *.png *.jpg *.jpeg *.webp"),
    ("PDF", "*.pdf"), ("PowerPoint", "*.pptx"),
    ("이미지", "*.png *.jpg *.jpeg *.webp"), ("모든 파일", "*.*"),
]


def engine_home(cfg) -> str:
    return (cfg.get("prescreen_home") or "").strip() or DEFAULT_ENGINE_HOME


def claude_cli_available() -> bool:
    """Claude Code CLI 존재 여부 — 스킬 모드·Claude 판단의 전제."""
    import shutil

    for name in ("claude", "claude.cmd", "claude.exe"):
        if shutil.which(name):
            return True
    return os.path.exists(os.path.expanduser(r"~\.local\bin\claude.exe"))


def engine_available(cfg) -> bool:
    """엔진 실체가 있는지 — 경로만 보지 않고 진입 모듈까지 확인한다."""
    h = Path(engine_home(cfg))
    return (h / "engine" / "runner.py").exists() and (h / "scripts" / "build_md_report.py").exists()


class PrescreenTab:
    def __init__(self, parent, app):
        self.app = app
        self.parent = parent
        self.files = []
        self._running = False
        self._result = None
        # 워커 스레드는 tkinter를 건드릴 수 없다(after 포함) — 큐로만 주고받는다
        self._q = queue.Queue()
        self._build()
        self._drain()

    # ── UI ────────────────────────────────────────────────
    def _build(self):
        p = self.parent

        top = tk.Frame(p, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        top.pack(fill="x", padx=20, pady=(14, 8))
        inner = tk.Frame(top, bg=CARD_BG)
        inner.pack(fill="x", padx=14, pady=12)

        tk.Label(inner, text="📑 예비검토보고서 생성", font=FONT_H2,
                 bg=CARD_BG, fg=TEXT).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(inner, text="IR 자료를 선택하면 보고서를 만들어 Obsidian에 저장합니다.",
                 font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT
                 ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 10))

        tk.Label(inner, text="회사명", font=FONT_BODY, bg=CARD_BG, fg=TEXT
                 ).grid(row=2, column=0, sticky="w")
        self.company_var = tk.StringVar()
        tk.Entry(inner, textvariable=self.company_var, font=FONT_BODY, width=30
                 ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=3)

        tk.Label(inner, text="IR 자료", font=FONT_BODY, bg=CARD_BG, fg=TEXT
                 ).grid(row=3, column=0, sticky="nw", pady=(8, 0))
        fbox = tk.Frame(inner, bg=CARD_BG)
        fbox.grid(row=3, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0))
        tk.Button(fbox, text="파일 선택…", font=FONT_BODY, command=self._pick,
                  bg=ACCENT, fg="white", relief="flat", padx=12, pady=3).pack(side="left")
        tk.Button(fbox, text="비우기", font=FONT_SMALL, command=self._clear,
                  bg="#95A5A6", fg="white", relief="flat", padx=10).pack(side="left", padx=6)
        self.files_var = tk.StringVar(value="선택된 파일 없음")
        tk.Label(inner, textvariable=self.files_var, font=FONT_SMALL, bg=CARD_BG,
                 fg=TEXT_LIGHT, justify="left", wraplength=620
                 ).grid(row=4, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(4, 0))

        # ── 실행 모드 ─────────────────────────────────────
        mode = tk.Frame(inner, bg=CARD_BG)
        mode.grid(row=5, column=0, columnspan=3, sticky="w", pady=(14, 0))
        tk.Label(mode, text="실행 모드", font=FONT_BODY, bg=CARD_BG, fg=TEXT).pack(anchor="w")
        self.mode_var = tk.StringVar(value=self.app._cfg.get("prescreen_mode", "skill"))
        tk.Radiobutton(mode, text="스킬 모드 — 품질 최상 · Claude 구독 사용 · 10~40분",
                       variable=self.mode_var, value="skill", command=self._sync_mode,
                       font=FONT_SMALL, bg=CARD_BG, fg=TEXT, selectcolor=CARD_BG
                       ).pack(anchor="w")
        tk.Radiobutton(mode, text="엔진 모드 — 빠름 · 5~15분 · Claude Code 없어도 동작",
                       variable=self.mode_var, value="engine", command=self._sync_mode,
                       font=FONT_SMALL, bg=CARD_BG, fg=TEXT, selectcolor=CARD_BG
                       ).pack(anchor="w")

        opt = tk.Frame(inner, bg=CARD_BG)
        self._opt_frame = opt
        opt.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.research_var = tk.BooleanVar(value=True)
        self.pipeline_var = tk.BooleanVar(value=True)
        self.save_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt, text="외부조사(DART·그라운딩)", variable=self.research_var,
                       font=FONT_SMALL, bg=CARD_BG, fg=TEXT, selectcolor=CARD_BG).pack(side="left")
        tk.Checkbutton(opt, text="검증 파이프라인", variable=self.pipeline_var,
                       font=FONT_SMALL, bg=CARD_BG, fg=TEXT, selectcolor=CARD_BG).pack(side="left", padx=10)
        tk.Checkbutton(opt, text="Obsidian 저장", variable=self.save_var,
                       font=FONT_SMALL, bg=CARD_BG, fg=TEXT, selectcolor=CARD_BG).pack(side="left")
        tk.Label(opt, text="판단 엔진", font=FONT_SMALL, bg=CARD_BG, fg=TEXT
                 ).pack(side="left", padx=(16, 4))
        self.provider_var = tk.StringVar(value=self.app._cfg.get("prescreen_provider", "gemini"))
        for label, val in (("Gemini", "gemini"), ("Claude", "claude")):
            tk.Radiobutton(opt, text=label, variable=self.provider_var, value=val,
                           font=FONT_SMALL, bg=CARD_BG, fg=TEXT, selectcolor=CARD_BG).pack(side="left")

        run = tk.Frame(inner, bg=CARD_BG)
        run.grid(row=7, column=0, columnspan=3, sticky="w", pady=(12, 0))
        self.run_btn = tk.Button(run, text="📑  보고서 생성", font=FONT_BTN,
                                 command=self._start, bg=SUCCESS, fg="white",
                                 relief="flat", padx=22, pady=7)
        self.run_btn.pack(side="left")
        self.status_var = tk.StringVar(value="대기 중")
        tk.Label(run, textvariable=self.status_var, font=FONT_SMALL,
                 bg=CARD_BG, fg=TEXT_LIGHT).pack(side="left", padx=12)

        # 진행 로그
        logf = tk.Frame(p, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        logf.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        lh = tk.Frame(logf, bg=CARD_BG)
        lh.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(lh, text="진행 상황", font=FONT_H2, bg=CARD_BG, fg=TEXT).pack(side="left")
        self.open_btn = tk.Button(lh, text="📂 폴더 열기", font=FONT_SMALL,
                                  command=self._open_folder, bg="#95A5A6", fg="white",
                                  relief="flat", padx=10, state="disabled")
        self.open_btn.pack(side="right")
        self.log_box = scrolledtext.ScrolledText(logf, font=("맑은 고딕", 9), height=14,
                                                 wrap="word", relief="flat", bg="#FAFBFC")
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(6, 10))
        self.log_box.configure(state="disabled")

        self._sync_mode()
        if not engine_available(self.app._cfg):
            self._lock()

    def _sync_mode(self):
        """스킬 모드에서는 엔진 전용 옵션을 잠근다(스킬이 스스로 조사·저장한다)."""
        skill = self.mode_var.get() == "skill"
        for w in self._opt_frame.winfo_children():
            try:
                w.configure(state="disabled" if skill else "normal")
            except tk.TclError:
                pass
        if skill and not claude_cli_available():
            self.status_var.set("⚠️ Claude Code 미설치 — 스킬 모드 불가")
        else:
            self.status_var.set("대기 중")

    def _lock(self):
        self.run_btn.configure(state="disabled", bg="#BDC3C7")
        self.status_var.set("엔진 미설치")
        self.log(f"⚠️ 예비검토 엔진을 찾지 못했습니다.\n"
                 f"   경로: {engine_home(self.app._cfg)}\n"
                 f"   설정 탭의 「예비검토 엔진 경로」를 Prescreening_Report 저장소로 지정하세요.\n"
                 f"   (engine/runner.py 와 scripts/build_md_report.py 가 있어야 합니다)")

    # ── 동작 ──────────────────────────────────────────────
    def log(self, msg):
        """워커 스레드에서도 안전 — 큐에만 넣고, 실제 위젯 갱신은 메인 스레드가 한다."""
        self._q.put(("log", msg))

    def _drain(self):
        """메인 스레드 전용. 큐를 비우며 위젯을 갱신하고 스스로를 다시 예약한다."""
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", payload + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind == "done":
                    self._done(payload)
                elif kind == "fail":
                    self._fail(payload)
        except queue.Empty:
            pass
        self.app.after(120, self._drain)

    def _write_log_direct(self, msg):
        """메인 스레드에서 즉시 쓰기 (탭 초기화 시점 등)."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _pick(self):
        paths = filedialog.askopenfilenames(title="IR 자료 선택", filetypes=IR_FILETYPES)
        if paths:
            self.files = list(paths)
            self._refresh_files()
            if not self.company_var.get().strip():
                self.company_var.set(self._guess_company(self.files[0]))

    def _clear(self):
        self.files = []
        self._refresh_files()

    def _refresh_files(self):
        if not self.files:
            self.files_var.set("선택된 파일 없음")
            return
        names = [Path(f).name for f in self.files]
        self.files_var.set(f"{len(names)}개 — " + " · ".join(names))

    @staticmethod
    def _guess_company(path) -> str:
        """파일명에서 회사명 추측 — 어디까지나 초기값이고 사용자가 고칠 수 있다."""
        stem = Path(path).stem
        for token in ("회사소개서", "IR자료", "IR", "소개서", "사업계획서", "제안서"):
            stem = stem.replace(token, " ")
        stem = stem.replace("(주)", " ").replace("㈜", " ").replace("주식회사", " ")
        stem = "".join(c for c in stem if not c.isdigit())
        return stem.strip(" _-·").split()[0] if stem.strip(" _-·") else ""

    def _start(self):
        if self._running:
            return
        company = self.company_var.get().strip()
        if not company:
            messagebox.showwarning("입력 필요", "회사명을 입력하세요.")
            return
        if not self.files:
            messagebox.showwarning("입력 필요", "IR 자료를 선택하세요.")
            return
        if not engine_available(self.app._cfg):
            messagebox.showerror("엔진 없음", "예비검토 엔진 경로를 설정 탭에서 지정하세요.")
            return

        skill = self.mode_var.get() == "skill"
        if skill and not claude_cli_available():
            messagebox.showerror(
                "Claude Code 없음",
                "스킬 모드는 Claude Code CLI가 필요합니다.\n"
                "엔진 모드를 선택하시거나 Claude Code를 설치하세요.")
            return

        # 녹음 중 동시 실행 — 보고서는 다시 만들 수 있지만 녹음은 복구되지 않는다
        recording = getattr(getattr(self.app, "_recorder", None), "state", "idle") != "idle"
        if recording and not messagebox.askyesno(
                "녹음 중입니다",
                "지금 녹음이 진행 중입니다.\n\n"
                "보고서 생성은 검색·판독으로 CPU와 네트워크를 함께 사용합니다.\n"
                "녹음 품질에 영향을 줄 가능성이 있으며, **녹음은 복구할 수 없습니다.**\n\n"
                "그래도 지금 생성할까요?"):
            return

        est = "10~40분" if skill else ("5~15분" if self.pipeline_var.get() else "2~5분")
        detail = ("스킬 모드 — Claude 구독 사용량을 씁니다"
                  if skill else f"엔진 모드 · 판단 {self.provider_var.get()}")
        if not messagebox.askyesno(
                "보고서 생성",
                f"「{company}」 예비검토보고서를 생성합니다.\n\n"
                f"IR 자료 {len(self.files)}개 · 예상 소요 {est}\n"
                f"{detail}\n\n계속할까요?"):
            return

        self.app._cfg["prescreen_provider"] = self.provider_var.get()
        self.app._cfg["prescreen_mode"] = self.mode_var.get()
        config.save_config(self.app._cfg)

        self._running = True
        self._result = None
        self.run_btn.configure(state="disabled", bg="#BDC3C7")
        self.open_btn.configure(state="disabled")
        self.status_var.set("실행 중…")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.log(f"■ {company} — IR 자료 {len(self.files)}개")

        # tkinter 변수는 메인 스레드에서만 읽을 수 있다 — 여기서 값으로 확정해 넘긴다
        opts = {
            "files": list(self.files),
            "home": engine_home(self.app._cfg),
            "mode": self.mode_var.get(),
            "provider": self.provider_var.get(),
            # 엔진 저장소에는 Claude 키가 없다 — 앱 설정의 키를 넘겨준다
            "claude_key": (self.app._cfg.get("claude_api_key") or "").strip(),
            "gemini_key": (self.app._cfg.get("gemini_api_key") or "").strip(),
            "do_research": self.research_var.get(),
            "do_pipeline": self.pipeline_var.get(),
            "save_obsidian": self.save_var.get(),
        }
        threading.Thread(target=self._worker, args=(company, opts), daemon=True).start()

    def _worker(self, company, opts):
        """워커 스레드 — 여기서는 tkinter를 일절 건드리지 않는다(위젯·변수·after 모두)."""
        try:
            home = opts["home"]
            if home not in sys.path:
                sys.path.insert(0, home)
            os.environ["PRESCREENING_HOME"] = home
            # 엔진은 env → config.local.yaml 순으로 키를 찾는다
            if opts.get("claude_key"):
                os.environ["ANTHROPIC_API_KEY"] = opts["claude_key"]
            if opts.get("gemini_key"):
                os.environ.setdefault("GEMINI_API_KEY", opts["gemini_key"])
            if opts["mode"] == "skill":
                # 스킬 원본을 실행한다 — 조사·작성·Obsidian 저장까지 스킬이 수행
                from engine import skill_runner    # 런타임 로드 (SSOT는 저장소 쪽)
                res = skill_runner.run(opts["files"], company, progress=self.log)
            else:
                from engine import runner
                res = runner.run_full(
                    opts["files"], company,
                    provider=opts["provider"],
                    do_research=opts["do_research"],
                    do_pipeline=opts["do_pipeline"],
                    save_obsidian=opts["save_obsidian"],
                    progress=self.log)
            self._result = res
            self._q.put(("done", res))
        except Exception as e:                                   # noqa: BLE001
            self.log(f"\n❌ 실패: {e}\n{traceback.format_exc(limit=6)}")
            self._q.put(("fail", e))

    def _done(self, res):
        self._running = False
        self.run_btn.configure(state="normal", bg=SUCCESS)
        self.open_btn.configure(state="normal")
        missing = res.get("missing") or []
        self.status_var.set(f"완료 — 확인 필요 {len(missing)}건")
        self.log("\n──────── 완료 ────────")
        self.log(f"보고서: {res['report']}")
        for s in res.get("saved") or []:
            self.log(f"저장  : {s}")
        if not res.get("saved"):
            self.log("※ Obsidian 저장은 수행되지 않았습니다.")
        if missing:
            self.log(f"\n확인 필요 {len(missing)}건 — 보고서 하단에 실렸습니다:")
            for m in missing[:12]:
                self.log(f"  · {m}")
            if len(missing) > 12:
                self.log(f"  … 외 {len(missing) - 12}건")
        messagebox.showinfo("완료", f"보고서를 생성했습니다.\n\n{Path(res['report']).name}\n\n"
                                    f"확인 필요 항목 {len(missing)}건은 보고서 하단을 보세요.")

    def _fail(self, e):
        self._running = False
        self.run_btn.configure(state="normal", bg=SUCCESS)
        self.status_var.set("실패")
        messagebox.showerror("실패", f"보고서 생성에 실패했습니다.\n\n{e}\n\n진행 로그를 확인하세요.")

    def _open_folder(self):
        if not self._result:
            return
        target = (self._result.get("saved") or [None])[0] or self._result.get("report")
        if target:
            os.startfile(Path(target).parent)
