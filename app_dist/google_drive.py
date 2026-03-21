"""
회의녹음요약 - Google Drive 연동 (배포용 A방식)
각 사용자가 Google Cloud Console에서 직접 발급한 OAuth 자격증명 사용
"""
import os
import json
from pathlib import Path
from config import (CREDENTIALS_FILE, TOKEN_FILE, GOOGLE_SCOPES,
                    APP_DATA_DIR, DRIVE_MP3_FOLDER_ID, DRIVE_TXT_FOLDER_ID)

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False


def is_available() -> bool:
    return GDRIVE_AVAILABLE


def get_credentials_status() -> dict:
    """현재 인증 상태 반환"""
    if not GDRIVE_AVAILABLE:
        return {"status": "no_package", "msg": "google-auth 패키지 없음"}
    if not CREDENTIALS_FILE.exists():
        return {"status": "no_credentials", "msg": "OAuth 클라이언트 파일 없음"}
    if TOKEN_FILE.exists():
        return {"status": "authenticated", "msg": "Google Drive 연결됨"}
    return {"status": "need_auth", "msg": "인증 필요"}


def save_credentials_file(src_path: str) -> tuple:
    """사용자가 선택한 OAuth 클라이언트 JSON을 앱 데이터 폴더로 복사"""
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(src_path, str(CREDENTIALS_FILE))
        return True, "클라이언트 파일 저장 완료"
    except Exception as e:
        return False, f"파일 저장 실패: {e}"


def authenticate() -> tuple:
    """OAuth 인증 흐름 실행 (브라우저 팝업)"""
    if not GDRIVE_AVAILABLE:
        return False, "google-auth 패키지가 설치되지 않았습니다."
    if not CREDENTIALS_FILE.exists():
        return False, "OAuth 클라이언트 파일이 없습니다. 설정 탭에서 파일을 등록해주세요."
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), GOOGLE_SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return True, "Google Drive 인증 완료!"
    except Exception as e:
        return False, f"인증 실패: {e}"


def revoke_token() -> tuple:
    """토큰 삭제 (연결 해제)"""
    try:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
        return True, "Google Drive 연결 해제 완료"
    except Exception as e:
        return False, f"연결 해제 실패: {e}"


def _get_service():
    if not CREDENTIALS_FILE.exists():
        raise RuntimeError("OAuth 클라이언트 파일이 없습니다.")
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GOOGLE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError("Google Drive 인증이 필요합니다. 설정 탭에서 인증해주세요.")
    return build("drive", "v3", credentials=creds)


def upload_file(local_path: str, folder_id: str) -> tuple:
    """파일을 Google Drive의 지정 폴더 ID에 업로드, 공유 링크 반환"""
    if not GDRIVE_AVAILABLE:
        return False, "google-auth 패키지 없음", ""
    try:
        service   = _get_service()
        file_name = Path(local_path).name
        ext       = Path(local_path).suffix.lower()
        mime_map  = {
            ".mp3": "audio/mpeg", ".wav": "audio/wav",
            ".m4a": "audio/mp4", ".txt": "text/plain",
        }
        mime  = mime_map.get(ext, "application/octet-stream")
        meta  = {"name": file_name, "parents": [folder_id]}
        media = MediaFileUpload(local_path, mimetype=mime, resumable=True)
        f = service.files().create(
            body=meta, media_body=media, fields="id").execute()
        fid = f.get("id")
        service.permissions().create(
            fileId=fid,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        link = f"https://drive.google.com/file/d/{fid}/view"
        return True, "업로드 완료", link
    except RuntimeError as e:
        return False, str(e), ""
    except Exception as e:
        return False, f"업로드 실패: {e}", ""


def upload_meeting_files(mp3_path: str, stt_path: str, summary_path: str,
                         mp3_folder_id: str = DRIVE_MP3_FOLDER_ID,
                         txt_folder_id: str = DRIVE_TXT_FOLDER_ID) -> dict:
    """회의 파일 3개 일괄 업로드 — MP3와 TXT를 각각 다른 폴더에 저장"""
    results = {}
    for label, path, fid in [
        ("mp3",     mp3_path,     mp3_folder_id),
        ("stt",     stt_path,     txt_folder_id),
        ("summary", summary_path, txt_folder_id),
    ]:
        if path and os.path.exists(path):
            ok, msg, link = upload_file(path, fid)
            results[label] = {"ok": ok, "msg": msg, "link": link}
        else:
            results[label] = {"ok": False, "msg": "파일 없음", "link": ""}
    return results
