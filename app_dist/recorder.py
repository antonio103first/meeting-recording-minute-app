"""
회의녹음요약 - 마이크 녹음 + 저장 모듈 (배포용)
sounddevice + soundfile + FFmpeg (MP3 변환)
pydub 미사용 (Python 3.14 호환)
"""
import os
import sys
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000   # 음성 최적화 (44100→16000: STT 표준, RAM 절약)
CHANNELS    = 1

# FFmpeg 후보 경로 (범용 — 사용자별 경로 없음)
_FFMPEG_CANDIDATES = [
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
]


def _find_ffmpeg() -> str | None:
    # 1. PyInstaller 번들 FFmpeg (EXE 내 포함)
    if hasattr(sys, '_MEIPASS'):
        bundled = Path(sys._MEIPASS) / 'ffmpeg.exe'
        if bundled.exists():
            return str(bundled)
    # 2. 환경변수 PATH
    p = shutil.which("ffmpeg")
    if p:
        return p
    # 3. 범용 설치 경로
    for c in _FFMPEG_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


FFMPEG_PATH = _find_ffmpeg()


def get_default_file_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S") + "_녹음"


def get_available_devices() -> list:
    devices = []
    try:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                devices.append({"index": i, "name": d["name"]})
    except Exception:
        pass
    return devices


class AudioRecorder:
    def __init__(self):
        self.state    = "idle"
        self._frames  = []
        self._stream  = None
        self._elapsed = 0
        self._level   = 0.0
        self._timer_thread = None
        self._timer_stop   = threading.Event()

    def start_recording(self, device_index=None) -> tuple:
        if self.state != "idle":
            return False, "이미 녹음 중입니다."
        try:
            self._frames  = []
            self._elapsed = 0
            self._stream  = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS,
                dtype="float32", device=device_index,
                callback=self._callback,
            )
            self._stream.start()
            self.state = "recording"
            self._start_timer()
            return True, "녹음 시작"
        except Exception as e:
            self.state = "idle"
            return False, f"마이크 오류: {e}"

    def pause_recording(self):
        if self.state == "recording":
            self._stream.stop()
            self.state = "paused"
            self._timer_stop.set()

    def resume_recording(self):
        if self.state == "paused":
            self._stream.start()
            self.state = "recording"
            self._timer_stop.clear()
            self._start_timer()

    def stop_recording(self) -> tuple:
        if self.state not in ("recording", "paused"):
            return False, "녹음 중이 아닙니다."
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            self._timer_stop.set()
            self.state = "idle"
            if not self._frames:
                return False, "녹음 데이터가 없습니다."
            audio = np.concatenate(self._frames, axis=0)
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="meeting_rec_")
            sf.write(tmp.name, audio, SAMPLE_RATE)
            return True, tmp.name
        except Exception as e:
            self.state = "idle"
            return False, f"중지 오류: {e}"

    def save_as_mp3(self, wav_path: str, save_dir: str, file_name: str) -> tuple:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        if FFMPEG_PATH:
            out = save_dir / (file_name + ".mp3")
            try:
                r = subprocess.run(
                    [FFMPEG_PATH, "-y", "-i", wav_path,
                     "-codec:a", "libmp3lame",
                     "-b:a", "32k",      # 음성 최적화: 2시간 약 29MB
                     "-ar", "16000",     # 샘플레이트 16kHz (STT 표준)
                     "-ac", "1",         # 모노 강제
                     str(out)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
                if r.returncode != 0:
                    raise Exception(f"ffmpeg 오류 코드: {r.returncode}")
                os.unlink(wav_path)
                return True, str(out)
            except Exception as e:
                return False, f"MP3 변환 실패: {e}"
        else:
            # FFmpeg 없으면 WAV로 저장
            out = save_dir / (file_name + ".wav")
            shutil.copy2(wav_path, str(out))
            os.unlink(wav_path)
            return True, str(out)

    def get_elapsed_str(self) -> str:
        h, rem = divmod(self._elapsed, 3600)
        m, s   = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def get_level(self) -> float:
        return min(self._level, 1.0)

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())
        rms = float(np.sqrt(np.mean(indata ** 2)))
        self._level = min(rms * 10, 1.0)

    def _start_timer(self):
        self._timer_stop.clear()
        def _tick():
            while not self._timer_stop.is_set():
                time.sleep(1)
                if self.state == "recording":
                    self._elapsed += 1
        self._timer_thread = threading.Thread(target=_tick, daemon=True)
        self._timer_thread.start()
