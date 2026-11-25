"""Roundtable 자동 업데이트.

흐름:
  1) Google Drive 의 latest.json(고정 파일 ID) 을 읽어 최신 버전·설치파일 ID 확인
  2) 현재 버전보다 높으면 설치 파일을 내려받아 sha256 검증
  3) 설치 파일을 /VERYSILENT 로 실행 → 앱 종료 → 설치기가 교체 후 앱 재실행

실패는 삼키지 않는다: 호출자에게 예외로 올리고, 시작 시 자동 점검은 update.log 에 남긴다.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

try:
    from update_channel import LATEST_JSON_ID   # release.py 가 생성
except ImportError:
    LATEST_JSON_ID = ""

_DL = "https://drive.usercontent.google.com/download"
_TIMEOUT = 20


class UpdateError(Exception):
    pass


def is_frozen() -> bool:
    """설치형(PyInstaller)으로 실행 중일 때만 자동 업데이트 대상."""
    return bool(getattr(sys, "frozen", False))


def parse_version(v: str) -> tuple:
    out = []
    for p in str(v).strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def _drive_get(file_id: str, **kw):
    # confirm=t : 대용량 파일의 '바이러스 검사 불가' 확인 페이지를 건너뜀
    return requests.get(_DL, params={"id": file_id, "export": "download", "confirm": "t"},
                        timeout=_TIMEOUT, **kw)


def fetch_latest() -> dict:
    """latest.json 을 읽어 dict 반환. 설정/네트워크/형식 오류는 UpdateError."""
    if not LATEST_JSON_ID:
        raise UpdateError("업데이트 채널이 설정되지 않은 빌드입니다.")
    try:
        r = _drive_get(LATEST_JSON_ID)
    except requests.RequestException as e:
        raise UpdateError(f"업데이트 서버 접속 실패: {e}") from e
    if r.status_code != 200:
        raise UpdateError(f"업데이트 정보를 받지 못했습니다 (HTTP {r.status_code}). "
                          "공유 설정을 확인해 주세요.")
    try:
        info = json.loads(r.content.decode("utf-8-sig"))
        info["version"], info["installer_id"], info["sha256"]
    except Exception as e:
        raise UpdateError(f"latest.json 형식 오류: {e}") from e
    return info


def check(current_version: str):
    """새 버전 정보 dict 또는 None(최신)."""
    info = fetch_latest()
    if parse_version(info["version"]) > parse_version(current_version):
        return info
    return None


def download_installer(info: dict, progress_cb=None) -> str:
    """설치 파일 다운로드 + sha256 검증. 로컬 경로 반환."""
    dest_dir = Path(tempfile.gettempdir()) / "roundtable_update"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"Roundtable_Setup_{info['version']}.exe"
    h = hashlib.sha256()
    try:
        with _drive_get(info["installer_id"], stream=True) as r:
            if r.status_code != 200:
                raise UpdateError(f"설치 파일 다운로드 실패 (HTTP {r.status_code})")
            total = int(info.get("size") or r.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if progress_cb and total:
                        progress_cb(min(done / total, 1.0))
    except requests.RequestException as e:
        raise UpdateError(f"다운로드 중 네트워크 오류: {e}") from e
    if h.hexdigest().lower() != str(info["sha256"]).lower():
        try:
            dest.unlink()
        except OSError:
            pass
        raise UpdateError("설치 파일 무결성 검증 실패(sha256 불일치). 다시 시도해 주세요.")
    return str(dest)


def launch_installer(path: str) -> None:
    """설치기를 분리 실행. 호출자는 이후 즉시 앱을 종료해야 한다."""
    flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
        creationflags=flags, close_fds=True)


def log(msg: str) -> None:
    try:
        from config import APP_DATA_DIR
        with open(Path(APP_DATA_DIR) / "update.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass
