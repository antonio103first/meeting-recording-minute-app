"""
회의녹음요약 - Google Drive 연동 (배포용 A방식)
각 사용자가 Google Cloud Console에서 직접 발급한 OAuth 자격증명 사용

[수정 이력]
- 하드코딩 폴더 ID 제거 → 사용자별 폴더 자동 생성/조회
- ensure_folder() 추가: 폴더 없으면 자동 생성
- list_drive_folders() 추가: 드라이브 폴더 목록 조회
- upload_meeting_files(): config 기반 폴더 ID 동적 전달
"""
import os
import re
import json
from pathlib import Path
from config import CREDENTIALS_FILE, TOKEN_FILE, GOOGLE_SCOPES, APP_DATA_DIR


def parse_folder_id(value: str) -> str:
    """
    Google Drive 폴더 URL 또는 ID를 입력받아 순수 폴더 ID만 반환.
    예: https://drive.google.com/drive/folders/1Yu6snQ... → 1Yu6snQ...
    이미 ID 형식이면 그대로 반환.
    """
    if not value:
        return ""
    value = value.strip()
    # URL에서 folders/{ID} 추출
    m = re.search(r"folders/([a-zA-Z0-9_-]+)", value)
    if m:
        return m.group(1)
    # ?id= 파라미터 형식
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", value)
    if m:
        return m.group(1)
    # 이미 순수 ID인 경우 (영숫자+하이픈+언더스코어)
    if re.fullmatch(r"[a-zA-Z0-9_-]+", value):
        return value
    return value

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
        # credentials.json 클라이언트 유형 사전 검증
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            import json as _json
            cred_data = _json.load(f)
        if "web" in cred_data and "installed" not in cred_data:
            return False, (
                "OAuth 클라이언트 유형 오류\n\n"
                "현재 'Web 애플리케이션' 유형으로 설정되어 있습니다.\n"
                "Google Cloud Console에서 새 OAuth 클라이언트 ID를\n"
                "『데스크톱 앱』 유형으로 생성 후 다시 등록해주세요.\n\n"
                "경로: Cloud Console → API 및 서비스 → 사용자 인증 정보\n"
                "→ OAuth 2.0 클라이언트 ID 만들기 → 데스크톱 앱"
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), GOOGLE_SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return True, "Google Drive 인증 완료!"
    except Exception as e:
        err = str(e)
        if "invalid_client" in err or "unauthorized_client" in err:
            return False, (
                "OAuth 클라이언트 오류 (개발자 오류)\n\n"
                "Google Cloud Console에서 OAuth 클라이언트 ID를\n"
                "『데스크톱 앱』 유형으로 새로 생성해주세요.\n"
                "(Android / Web 유형은 사용 불가)"
            )
        if "redirect_uri_mismatch" in err:
            return False, (
                "리디렉션 URI 불일치 오류\n\n"
                "OAuth 클라이언트 유형이 『데스크톱 앱』인지 확인해주세요."
            )
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


# ── 폴더 관리 ────────────────────────────────────────────

def ensure_folder(folder_name: str, parent_id: str = "root") -> tuple:
    """Drive에서 폴더를 찾거나 없으면 생성. (ok, folder_id, folder_name) 반환"""
    if not GDRIVE_AVAILABLE:
        return False, "", "google-auth 패키지가 없습니다."
    parent_id = parse_folder_id(parent_id) or "root"  # URL 입력도 자동 파싱
    try:
        service = _get_service()

        # 동일 이름 폴더 검색
        q = (f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
             f" and '{parent_id}' in parents and trashed=false")
        res = service.files().list(
            q=q, spaces="drive", fields="files(id, name)", pageSize=1
        ).execute()
        files = res.get("files", [])

        if files:
            fid = files[0]["id"]
            return True, fid, f"기존 폴더 사용: '{folder_name}' (ID: {fid[:12]}...)"

        # 폴더 신규 생성
        meta = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        created = service.files().create(body=meta, fields="id").execute()
        fid = created.get("id")
        return True, fid, f"새 폴더 생성: '{folder_name}' (ID: {fid[:12]}...)"

    except RuntimeError as e:
        return False, "", str(e)
    except Exception as e:
        return False, "", f"폴더 생성 오류: {str(e)[:200]}"


def get_folder_name(folder_id: str) -> str:
    """폴더 ID로 폴더 이름 조회. 실패 시 빈 문자열 반환"""
    if not GDRIVE_AVAILABLE or not folder_id:
        return ""
    try:
        service = _get_service()
        res = service.files().get(fileId=folder_id, fields="name").execute()
        return res.get("name", "")
    except Exception:
        return ""


def list_drive_folders(parent_id: str = "root", page_size: int = 50) -> list:
    """Drive 폴더 목록 반환 → [{"id": ..., "name": ...}, ...]"""
    if not GDRIVE_AVAILABLE:
        return []
    try:
        service = _get_service()
        q = (f"mimeType='application/vnd.google-apps.folder'"
             f" and '{parent_id}' in parents and trashed=false")
        res = service.files().list(
            q=q, spaces="drive",
            fields="files(id, name)",
            orderBy="name",
            pageSize=page_size,
        ).execute()
        return res.get("files", [])
    except Exception:
        return []


def init_drive_folders(mp3_folder_name: str = "녹음파일",
                       txt_folder_name: str = "회의록(요약)") -> tuple:
    """MP3/TXT 두 폴더를 Drive에서 찾거나 생성, 폴더 IDs 반환"""
    ok1, fid1, msg1 = ensure_folder(mp3_folder_name)
    ok2, fid2, msg2 = ensure_folder(txt_folder_name)
    return {
        "mp3_ok": ok1, "mp3_id": fid1, "mp3_msg": msg1,
        "txt_ok": ok2, "txt_id": fid2, "txt_msg": msg2,
    }


# ── 파일 업로드 ──────────────────────────────────────────

def upload_file(local_path: str, folder_id: str) -> tuple:
    """파일을 Google Drive의 지정 폴더 ID에 업로드, 공유 링크 반환"""
    if not GDRIVE_AVAILABLE:
        return False, "google-auth 패키지 없음", ""
    if not local_path or not os.path.exists(local_path):
        return False, f"파일 없음: {local_path}", ""
    folder_id = parse_folder_id(folder_id)   # URL 입력도 자동 파싱
    if not folder_id:
        return False, "업로드 폴더 미설정 — 설정 탭 → ☁ Google Drive → 업로드 폴더 설정에서 폴더를 생성/지정해주세요.", ""
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
        media = MediaFileUpload(local_path, mimetype=mime, resumable=False)
        f = service.files().create(
            body=meta, media_body=media, fields="id, webViewLink").execute()
        fid  = f.get("id", "")
        link = f.get("webViewLink", f"https://drive.google.com/file/d/{fid}/view")

        # 공유 링크 설정 — 조직 정책으로 막혀 있어도 업로드 자체는 성공 처리
        try:
            service.permissions().create(
                fileId=fid,
                body={"type": "anyone", "role": "reader"},
            ).execute()
        except Exception:
            pass   # 공유 설정 실패는 무시 (조직 정책 제한 등)

        return True, "업로드 완료", link
    except RuntimeError as e:
        return False, str(e), ""
    except Exception as e:
        err = str(e)
        # 흔한 오류에 대한 친절한 메시지
        if "invalid_grant" in err or "Token has been expired" in err:
            return False, "Drive 토큰 만료 — 설정 탭에서 '연결 해제' 후 재인증해주세요.", ""
        if "insufficientPermissions" in err or "forbidden" in err.lower():
            return False, "Drive 권한 오류 — Google Cloud Console에서 Drive API 권한을 확인해주세요.", ""
        if "notFound" in err:
            return False, f"폴더를 찾을 수 없음 (ID: {folder_id[:12]}…) — 설정 탭에서 폴더를 다시 생성해주세요.", ""
        return False, f"업로드 실패: {err[:200]}", ""


def upload_meeting_files(mp3_path: str, stt_path: str, summary_path: str,
                         mp3_folder_id: str = "",
                         txt_folder_id: str = "") -> dict:
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
