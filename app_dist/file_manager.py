"""
회의녹음요약 v3 - 파일 저장 관리
v3 변경: 3폴더 분리 저장 (MP3 / STT .md / 회의록 .md)
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from config import MP3_SAVE_DIR, STT_SAVE_DIR, SUMMARY_SAVE_DIR
# 하위 호환 alias
AUDIO_SAVE_DIR = MP3_SAVE_DIR


def get_default_base_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_stt_text(text: str, save_dir: str, file_name: str) -> tuple:
    """STT 변환본을 .md 파일로 저장"""
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        # .md 확장자로 저장 (이전 .txt도 허용)
        stem = file_name if not file_name.endswith((".txt", ".md")) else Path(file_name).stem
        out = path / (stem + ".md")
        out.write_text(text, encoding="utf-8")
        return True, str(out)
    except Exception as e:
        return False, f"STT 파일 저장 실패: {e}"


def save_summary_text(text: str, save_dir: str, file_name: str) -> tuple:
    """회의록 요약을 .md 파일로 저장"""
    try:
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        stem = file_name if not file_name.endswith((".txt", ".md")) else Path(file_name).stem
        out = path / (stem + ".md")
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
    """MP3 저장 폴더에서 오디오 파일 목록 반환"""
    files = []
    for ext in [".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac"]:
        for f in Path(MP3_SAVE_DIR).rglob(f"*{ext}"):
            files.append(str(f))
    return sorted(files, reverse=True)


def list_stt_files() -> list:
    """STT 변환본 .md 파일 목록 반환"""
    files = []
    for ext in [".md", ".txt"]:
        for f in Path(STT_SAVE_DIR).rglob(f"*{ext}"):
            files.append(str(f))
    return sorted(files, reverse=True)


def list_summary_files() -> list:
    """회의록 요약 .md 파일 목록 반환"""
    files = []
    for ext in [".md", ".txt"]:
        for f in Path(SUMMARY_SAVE_DIR).rglob(f"*{ext}"):
            files.append(str(f))
    return sorted(files, reverse=True)


def open_file_in_explorer(file_path: str):
    """파일 탐색기에서 파일 위치 열기"""
    import subprocess
    import sys
    try:
        path = Path(file_path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except Exception:
        pass


def print_file(file_path: str):
    """기본 프린터로 파일 인쇄 (Windows)"""
    import subprocess
    import sys
    try:
        if sys.platform == "win32":
            subprocess.Popen(["notepad.exe", "/p", str(file_path)])
        else:
            subprocess.Popen(["lpr", str(file_path)])
        return True, "인쇄 요청 완료"
    except Exception as e:
        return False, f"인쇄 실패: {e}"
