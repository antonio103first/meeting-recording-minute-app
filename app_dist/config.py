"""
회의녹음요약 - 설정 관리 (배포용)
Google Drive A방식: 각 사용자가 직접 OAuth 자격증명 설정
"""
import json
from pathlib import Path

# ── 앱 데이터 경로 ──────────────────────────────────────
APP_DATA_DIR = Path.home() / "회의녹음요약_데이터"
CONFIG_FILE  = APP_DATA_DIR / "config.json"
DB_FILE      = APP_DATA_DIR / "meetings.db"

# ── Google Drive (A방식: 사용자 직접 설정) ───────────────
CREDENTIALS_FILE   = APP_DATA_DIR / "google_credentials.json"
TOKEN_FILE         = APP_DATA_DIR / "google_token.json"
GOOGLE_SCOPES      = ["https://www.googleapis.com/auth/drive"]


def _resolve_drive_folder_ids() -> tuple:
    """config.json에서 Drive 폴더 ID 읽기 (없으면 빈 문자열)"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return (d.get("drive_mp3_folder_id", ""),
                        d.get("drive_txt_folder_id", ""))
        except Exception:
            pass
    return "", ""

# ── Gemini 모델 ─────────────────────────────────────────
GEMINI_STT_MODEL       = "gemini-2.5-flash"
GEMINI_SUMMARY_MODEL   = "gemini-2.5-flash"
GEMINI_INLINE_LIMIT_MB = 10   # 이 크기 미만 → base64 인라인 (10MB 초과는 Files API 사용)

CLAUDE_MODEL           = "claude-sonnet-4-6"  # Claude 요약 엔진

# ── CLOVA Speech Recognition ────────────────────────────
CLOVA_STT_CHUNK_SEC    = 50   # 청크당 최대 초 (CSR 권장치)

# ── 지원 오디오 형식 ────────────────────────────────────
SUPPORTED_AUDIO = [".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac"]


def _resolve_recording_base() -> Path:
    """config.json에서 저장 경로 읽기, 없으면 ~/Documents/회의녹음요약"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("recording_dir"):
                    return Path(d["recording_dir"])
        except Exception:
            pass
    return Path.home() / "Documents" / "Meeting recording"


def _resolve_subdirs() -> tuple:
    """config.json에서 서브폴더명 읽기"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                audio   = d.get("audio_subdir", "녹음파일") or "녹음파일"
                summary = d.get("summary_subdir", "회의록(요약)") or "회의록(요약)"
                return audio, summary
        except Exception:
            pass
    return "녹음파일", "회의록(요약)"


RECORDING_BASE   = _resolve_recording_base()
_audio_sub, _summary_sub = _resolve_subdirs()
AUDIO_SAVE_DIR   = RECORDING_BASE / _audio_sub
SUMMARY_SAVE_DIR = AUDIO_SAVE_DIR / _summary_sub   # 녹음파일\회의록(요약)


def reload_paths():
    """저장 경로 재계산 (설정 변경 후 호출)"""
    global RECORDING_BASE, AUDIO_SAVE_DIR, SUMMARY_SAVE_DIR
    RECORDING_BASE          = _resolve_recording_base()
    audio_sub, summary_sub  = _resolve_subdirs()
    AUDIO_SAVE_DIR          = RECORDING_BASE / audio_sub
    SUMMARY_SAVE_DIR        = AUDIO_SAVE_DIR / summary_sub   # 녹음파일\회의록(요약)
    AUDIO_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_SAVE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_dirs():
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_SAVE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "gemini_api_key": "",
        "claude_api_key": "",
        "clova_client_id": "",
        "clova_client_secret": "",
        "stt_engine": "gemini",   # "gemini" | "clova"
        "recording_dir": str(Path.home() / "Documents" / "Meeting recording"),
        "audio_subdir": "녹음파일",
        "summary_subdir": "회의록(요약)",
        "drive_mp3_folder_name": "녹음파일",
        "drive_txt_folder_name": "회의록(요약)",
        "drive_mp3_folder_id": "",
        "drive_txt_folder_id": "",
        "drive_auto_upload": True,
        "custom_prompt_enabled": False,
        "custom_prompt_text": "",
        "custom_prompts": [],
    }


def save_config(data: dict):
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_config_complete(data: dict) -> tuple:
    missing = []
    has_gemini = bool(data.get("gemini_api_key", "").strip())
    has_clova  = bool(data.get("clova_client_id", "").strip()) and \
                 bool(data.get("clova_client_secret", "").strip())
    if not has_gemini and not has_clova:
        missing.append("Gemini API 키 또는 CLOVA Speech API 키")
    return len(missing) == 0, missing
