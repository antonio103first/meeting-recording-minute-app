"""
audio_player.py — 회의 녹음파일(MP3/WAV 등) 미니 재생기

목적: 녹음/변환 탭의 "파일 선택"과 회의목록 탭의 목록 항목 선택 직후,
      Explorer 등 외부 프로그램 없이 앱 안에서 바로 청취할 수 있게 한다.

엔진은 기존 의존성(sounddevice + soundfile, recorder.py와 동일)만 사용 — 신규 패키지 불필요.

주의: 긴 회의 녹음(1시간 이상)을 통째로 디코딩하면 수 초가 걸리고 메모리도
수백 MB를 차지한다(실측: 107분 파일 → 디코딩 4.2초 / int16 기준 540MB).
그래서 ① dtype=int16로 읽어 float32 대비 메모리를 절반으로 줄이고,
② 디코딩은 반드시 백그라운드 스레드에서 수행해 회의목록 항목을 연속으로
클릭해도 UI가 멈추지 않게 한다(AudioPlayerWidget.load 참고).
"""
import os
import queue
import threading

import sounddevice as sd
import soundfile as sf


def _fmt_time(sec: float) -> str:
    if sec is None or sec < 0 or sec != sec:  # nan 방어
        sec = 0
    m, s = divmod(int(sec + 0.5), 60)
    return f"{m:02d}:{s:02d}"


def _decode(path: str):
    """오디오 파일을 통째로 디코딩. (data, samplerate, ok) 반환 — 백그라운드 스레드 전용."""
    try:
        data, sr = sf.read(path, dtype="int16", always_2d=True)
    except Exception:
        return None, None, False
    if len(data) == 0:
        return None, None, False
    return data, sr, True


class AudioPlayer:
    """디코딩된 PCM 배열을 sounddevice OutputStream 콜백으로 재생하는 단순 엔진.

    ※ 디코딩(무거운 작업)은 이 클래스 밖(백그라운드 스레드)에서 수행하고,
      결과 배열은 set_data()로 메인 스레드에서만 주입한다 — 클래스 내부
      메서드는 전부 메인 스레드 호출을 전제로 하며 오디오 콜백 스레드와는
      _lock으로만 프레임 포인터를 공유한다.
    """

    def __init__(self):
        self._data = None          # np.ndarray, shape (frames, channels), dtype int16
        self._samplerate = None
        self._frame = 0
        self._stream = None
        self._lock = threading.Lock()

    # ── 로드 / 해제 ──────────────────────────────────────
    def set_data(self, data, samplerate):
        """백그라운드에서 디코딩된 데이터를 메인 스레드에서 주입."""
        self.stop()   # 스트림을 먼저 닫아 콜백이 끝난 뒤 안전하게 교체
        self._data = data
        self._samplerate = samplerate
        self._frame = 0

    def unload(self):
        self.stop()
        self._data = None
        self._samplerate = None

    # ── 상태 조회 ────────────────────────────────────────
    @property
    def loaded(self) -> bool:
        return self._data is not None

    @property
    def duration(self) -> float:
        if self._data is None or not self._samplerate:
            return 0.0
        return len(self._data) / self._samplerate

    @property
    def position(self) -> float:
        if not self._samplerate:
            return 0.0
        return self._frame / self._samplerate

    @property
    def is_playing(self) -> bool:
        return self._stream is not None and self._stream.active

    # ── 재생 제어 ────────────────────────────────────────
    def play(self) -> bool:
        if self._data is None:
            return False
        if self._frame >= len(self._data):
            self._frame = 0
        self._close_stream()
        try:
            self._stream = sd.OutputStream(
                samplerate=self._samplerate,
                channels=self._data.shape[1],
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            self._stream = None
            return False
        return True

    def pause(self):
        self._close_stream()

    def stop(self):
        self._close_stream()
        self._frame = 0

    def seek(self, sec: float):
        if self._data is None or not self._samplerate:
            return
        was_playing = self.is_playing
        self._close_stream()
        with self._lock:
            total = len(self._data)
            self._frame = max(0, min(int(sec * self._samplerate), total))
        if was_playing:
            self.play()

    # ── 내부 ────────────────────────────────────────────
    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            total = len(self._data)
            remaining = total - self._frame
            if remaining <= 0:
                outdata.fill(0)
                raise sd.CallbackStop()
            n = min(frames, remaining)
            outdata[:n] = self._data[self._frame:self._frame + n]
            if n < frames:
                outdata[n:] = 0
            self._frame += n
            if self._frame >= total:
                raise sd.CallbackStop()

    def _close_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


class AudioPlayerWidget:
    """▶/⏸ 버튼 + 진행바 + 시간표시. tk.Frame을 상속하지 않고 self.frame에
    위젯을 채워 넣는 방식(호출부 스타일 상수를 그대로 재사용하기 위함)."""

    def __init__(self, tk, ttk, parent, *, bg, accent, text_light, font_small,
                 on_share=None):
        """on_share(path): '📤 보내기' 버튼 콜백. None이면 버튼을 만들지 않는다."""
        self._tk = tk
        self._ttk = ttk
        self.frame = tk.Frame(parent, bg=bg)

        self._player = AudioPlayer()
        self._seeking = False
        self._poll_job = None
        self._load_token = 0   # 로딩 도중 다른 파일이 선택되면 이전 결과를 폐기하기 위한 카운터
        self._path = None      # 현재 로드된(또는 로드 시도한) 파일 경로 — 보내기용
        self._decode_queue = queue.Queue()   # 워커 스레드 → 메인 스레드 결과 전달
        self._decode_job = None
        self._on_share = on_share

        self._btn_play = tk.Button(
            self.frame, text="▶", width=3, relief="flat",
            bg=accent, fg="white", font=font_small,
            state="disabled", command=self._toggle)
        self._btn_play.pack(side="left", padx=(0, 6))

        self._lbl_time = tk.Label(
            self.frame, text="00:00 / 00:00", font=font_small,
            bg=bg, fg=text_light, width=13)
        self._lbl_time.pack(side="left", padx=(0, 6))

        self._scale_var = tk.DoubleVar(value=0)
        self._scale = ttk.Scale(
            self.frame, from_=0, to=1000, orient="horizontal",
            variable=self._scale_var, command=self._on_scale_drag)
        self._scale.state(["disabled"])
        self._scale.pack(side="left", fill="x", expand=True)
        self._scale.bind("<ButtonPress-1>", self._on_scale_press)
        self._scale.bind("<ButtonRelease-1>", self._on_scale_release)

        # v4.0.5: 녹음파일 보내기(카톡·슬랙 등) — 파일이 존재하면 디코딩 성공 여부와 무관하게 활성화
        self._btn_share = None
        if on_share is not None:
            self._btn_share = tk.Button(
                self.frame, text="📤 보내기", relief="flat",
                bg="#16A085", fg="white", font=font_small,
                state="disabled", cursor="hand2",
                command=lambda: self._on_share(self._path))
            self._btn_share.pack(side="left", padx=(6, 0))

        self._lbl_status = tk.Label(
            self.frame, text="(재생할 녹음파일 없음)", font=font_small,
            bg=bg, fg=text_light)
        self._lbl_status.pack(side="left", padx=(6, 0))

    # 외부에서 pack/grid 하도록 self.frame을 그대로 노출
    def pack(self, **kw):
        self.frame.pack(**kw)

    # ── 공개 API ─────────────────────────────────────────
    def load(self, path):
        """path=None 이거나 로드 실패 시 컨트롤을 비활성화.
        실제 디코딩은 백그라운드 스레드에서 수행 — 긴 녹음이어도 UI가 멈추지 않는다."""
        self._load_token += 1
        token = self._load_token

        self._stop_poll()
        self._player.unload()
        self._btn_play.config(state="disabled", text="▶")
        self._scale.state(["disabled"])
        self._scale_var.set(0)
        self._lbl_time.config(text="00:00 / 00:00")
        self._path = None
        if self._btn_share is not None:
            self._btn_share.config(state="disabled")

        if not path:
            self._lbl_status.config(text="(재생할 녹음파일 없음)")
            return

        if not os.path.isfile(path):
            self._lbl_status.config(text="(녹음파일을 찾을 수 없음)")
            return

        self._path = path
        if self._btn_share is not None:
            self._btn_share.config(state="normal")
        self._lbl_status.config(text="⏳ 불러오는 중...")

        # 워커 스레드에서 Tk 메서드(after 등)를 직접 부르면
        # "main thread is not in main loop" RuntimeError가 난다(실측).
        # → 결과는 큐에만 넣고, 메인 스레드가 after()로 폴링해 꺼낸다.
        def _worker():
            data, sr, ok = _decode(path)
            self._decode_queue.put((token, data, sr, ok))

        threading.Thread(target=_worker, daemon=True).start()
        self._start_decode_poll()

    def _start_decode_poll(self):
        if self._decode_job is None:
            self._decode_job = self.frame.after(100, self._poll_decode)

    def _poll_decode(self):
        self._decode_job = None
        try:
            token, data, sr, ok = self._decode_queue.get_nowait()
        except queue.Empty:
            self._decode_job = self.frame.after(100, self._poll_decode)
            return
        if token != self._load_token:
            # 그 사이 다른 파일이 선택됨 — 결과 폐기, 최신 로드의 결과를 계속 기다림
            self._decode_job = self.frame.after(100, self._poll_decode)
            return
        self._on_decoded(token, data, sr, ok)

    def clear(self):
        self.load(None)

    def shutdown(self):
        """앱 종료 등에서 확실히 정지시킬 때 사용."""
        self._load_token += 1   # 진행 중인 백그라운드 디코딩 결과를 무시
        self._stop_poll()
        if self._decode_job is not None:
            try:
                self.frame.after_cancel(self._decode_job)
            except Exception:
                pass
            self._decode_job = None
        try:
            self._player.stop()
        except Exception:
            pass

    # ── 내부 콜백 ────────────────────────────────────────
    def _on_decoded(self, token, data, sr, ok):
        if token != self._load_token:
            return  # 그 사이 다른 파일이 선택됨 — 결과 폐기
        if not ok:
            self._lbl_status.config(text="(재생 불가 — 지원하지 않는 형식)")
            return
        self._player.set_data(data, sr)
        self._btn_play.config(state="normal")
        self._scale.state(["!disabled"])
        self._lbl_status.config(text="")
        self._update_time_label(0, self._player.duration)

    def _toggle(self):
        if self._player.is_playing:
            self._player.pause()
            self._btn_play.config(text="▶")
            self._stop_poll()
            return
        ok = self._player.play()
        if not ok:
            from tkinter import messagebox
            messagebox.showerror("재생 오류", "오디오 장치를 열 수 없거나 파일을 재생할 수 없습니다.")
            return
        self._btn_play.config(text="⏸")
        self._start_poll()

    def _on_scale_press(self, _event):
        self._seeking = True

    def _on_scale_drag(self, _val):
        if self._seeking:
            dur = self._player.duration
            sec = dur * (self._scale_var.get() / 1000.0)
            self._update_time_label(sec, dur)

    def _on_scale_release(self, _event):
        dur = self._player.duration
        sec = dur * (self._scale_var.get() / 1000.0)
        self._player.seek(sec)
        self._seeking = False

    def _start_poll(self):
        self._stop_poll()
        self._poll()

    def _stop_poll(self):
        if self._poll_job is not None:
            try:
                self.frame.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None

    def _poll(self):
        if not self._player.is_playing:
            # 재생이 끝까지 진행되어 자연 종료된 경우 (일시정지/정지는 _toggle에서
            # 폴링을 먼저 멈추므로 여기로 오지 않음)
            self._player.stop()
            self._btn_play.config(text="▶")
            self._scale_var.set(0)
            self._update_time_label(0, self._player.duration)
            self._poll_job = None
            return

        if not self._seeking:
            dur = self._player.duration
            pos = self._player.position
            if dur > 0:
                self._scale_var.set(min(1000.0, (pos / dur) * 1000.0))
            self._update_time_label(pos, dur)

        self._poll_job = self.frame.after(200, self._poll)

    def _update_time_label(self, pos, dur):
        self._lbl_time.config(text=f"{_fmt_time(pos)} / {_fmt_time(dur)}")
