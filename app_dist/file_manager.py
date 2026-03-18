"""
회의녹음요약 - 파일 저장 관리
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from config import AUDIO_SAVE_DIR, SUMMARY_SAVE_DIR


def get_default_base_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_stt_text(text: str, save_dir: str, file_name: str) -> tuple:
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        out = path / (file_name + ".txt")
        out.write_text(text, encoding="utf-8")
        return True, str(out)
    except Exception as e:
        return False, f"STT 파일 저장 실패: {e}"


def save_summary_text(text: str, save_dir: str, file_name: str) -> tuple:
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        out = path / (file_name + ".txt")
        out.write_text(text, encoding="utf-8")
        return True, str(out)
    except Exception as e:
        return False, f"요약 파일 저장 실패: {e}"


def copy_audio_to_save_dir(src_path: str, save_dir: str, file_name: str) -> tuple:
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        ext = Path(src_path).suffix
        out = path / (file_name + ext)
        shutil.copy2(src_path, str(out))
        return True, str(out)
    except Exception as e:
        return False, f"오디오 파일 복사 실패: {e}"


def get_file_size_mb(file_path: str) -> float:
    try:
        return os.path.getsize(file_path) / 1024 / 1024
    except Exception:
        return 0.0


def list_audio_files() -> list:
    files = []
    for ext in [".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac"]:
        for f in Path(AUDIO_SAVE_DIR).rglob(f"*{ext}"):
            files.append(str(f))
    return sorted(files, reverse=True)


def list_summary_files() -> list:
    files = []
    for f in Path(SUMMARY_SAVE_DIR).rglob("*.txt"):
        files.append(str(f))
    return sorted(files, reverse=True)
