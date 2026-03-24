"""
회의녹음요약 v3 - 설정 관리 (배포용)
Google Drive A방식: 각 사용자가 직접 OAuth 자격증명 설정
v3 변경: 3폴더 분리 저장 구조 (MP3 / STT .md / 회의록 .md)
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

# ── AI 모델 설정 ─────────────────────────────────────────
GEMINI_STT_MODEL       = "gemini-2.5-flash"
GEMINI_SUMMARY_MODEL   = "gemini-2.5-flash"
GEMINI_INLINE_LIMIT_MB = 10   # 이 크기 미만 → base64 인라인 (10MB 초과는 Files API 사용)

CLAUDE_MODEL           = "claude-sonnet-4-6"   # Claude 요약 엔진
CHATGPT_MODEL          = "gpt-4o"              # ChatGPT 요약 엔진

# ── CLOVA Speech Long API ───────────────────────────────
# Invoke URL + Secret Key 방식 (긴문장 인식)

# ── 지원 오디오 형식 ────────────────────────────────────
SUPPORTED_AUDIO = [".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac"]


def _resolve_recording_base() -> Path:
    """config.json에서 저장 경로 읽기, 없으면 ~/Documents/Meeting recording"""
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
    """config.json에서 서브폴더명 읽기 (mp3, stt, summary 3폴더)"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                mp3     = d.get("mp3_subdir",     "녹음파일")      or "녹음파일"
                stt     = d.get("stt_subdir",     "STT변환본")      or "STT변환본"
                summary = d.get("summary_subdir", "회의록(요약)")   or "회의록(요약)"
                return mp3, stt, summary
        except Exception:
            pass
    return "녹음파일", "STT변환본", "회의록(요약)"


RECORDING_BASE = _resolve_recording_base()
_mp3_sub, _stt_sub, _summary_sub = _resolve_subdirs()
AUDIO_SAVE_DIR   = RECORDING_BASE / _mp3_sub        # MP3 저장 폴더 (하위 호환 유지)
MP3_SAVE_DIR     = RECORDING_BASE / _mp3_sub        # v3 명칭
STT_SAVE_DIR     = RECORDING_BASE / _stt_sub        # STT .md 저장 폴더
SUMMARY_SAVE_DIR = RECORDING_BASE / _summary_sub    # 회의록 .md 저장 폴더


def reload_paths():
    """저장 경로 재계산 (설정 변경 후 호출)"""
    global RECORDING_BASE, AUDIO_SAVE_DIR, MP3_SAVE_DIR, STT_SAVE_DIR, SUMMARY_SAVE_DIR
    RECORDING_BASE  = _resolve_recording_base()
    mp3_sub, stt_sub, summary_sub = _resolve_subdirs()
    MP3_SAVE_DIR     = RECORDING_BASE / mp3_sub
    AUDIO_SAVE_DIR   = MP3_SAVE_DIR          # 하위 호환
    STT_SAVE_DIR     = RECORDING_BASE / stt_sub
    SUMMARY_SAVE_DIR = RECORDING_BASE / summary_sub
    MP3_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    STT_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_SAVE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_dirs():
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    MP3_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    STT_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_SAVE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # v2 → v3 마이그레이션: audio_subdir → mp3_subdir
            if "audio_subdir" in data and "mp3_subdir" not in data:
                data["mp3_subdir"] = data.get("audio_subdir", "녹음파일")
            return data
        except Exception:
            pass
    return {
        "gemini_api_key": "",
        "claude_api_key": "",
        "chatgpt_api_key": "",
        "clova_invoke_url": "",
        "clova_secret_key": "",
        "stt_engine": "clova",          # "gemini" | "clova" | "chatgpt"
        "summary_engine": "gemini",     # "gemini" | "claude" | "chatgpt"
        "summary_mode": "speaker",      # "speaker"|"topic"|"formal_md"|"lecture_md"|"flow"
        "recording_dir": str(Path.home() / "Documents" / "Meeting recording"),
        "mp3_subdir":     "녹음파일",
        "stt_subdir":     "STT변환본",
        "summary_subdir": "회의록(요약)",
        # 하위 호환
        "audio_subdir": "녹음파일",
        "drive_mp3_folder_name": "녹음파일",
        "drive_txt_folder_name": "회의록(요약)",
        "drive_mp3_folder_id": "",
        "drive_txt_folder_id": "",
        "drive_auto_upload": True,
        "custom_prompt_enabled": False,
        "custom_prompt_text": "",
        "custom_prompts": [],
        "net_printer_ip":   "",
        "net_printer_name": "printer",
    }


def save_config(data: dict):
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_config_complete(data: dict) -> tuple:
    missing = []
    has_gemini = bool(data.get("gemini_api_key", "").strip())
    has_clova  = bool(data.get("clova_invoke_url", "").strip()) and \
                 bool(data.get("clova_secret_key", "").strip())
    if not has_gemini and not has_clova:
        missing.append("Gemini API 키 또는 CLOVA Speech API 키")
    return len(missing) == 0, missing
