"""
CLOVA Speech Long API 서비스 모듈
NAVER Cloud CLOVA Speech (긴문장 인식) — Invoke URL + Secret Key 방식
엔드포인트: {invoke_url}/recognizer/upload
인증: X-CLOVASPEECH-API-KEY 헤더
"""
import os
import json
import threading
import requests

# ── 상수 ──────────────────────────────────────────────
_UPLOAD_PATH     = "/recognizer/upload"
_REQUEST_TIMEOUT = 600   # 긴 녹음 대응 (최대 10분)
_MAX_FILE_MB     = 200


def test_connection(invoke_url: str, secret_key: str) -> tuple[bool, str]:
    """Invoke URL + Secret Key 연결 테스트"""
    if not invoke_url.strip() or not secret_key.strip():
        return False, "Invoke URL과 Secret Key를 모두 입력해주세요."
    url = invoke_url.rstrip("/") + _UPLOAD_PATH
    try:
        r = requests.post(
            url,
            headers={"X-CLOVASPEECH-API-KEY": secret_key.strip()},
            timeout=10,
        )
        # 400 Bad Request = 인증 성공, 파라미터 누락 (정상 키)
        if r.status_code in (400, 200):
            return True, "CLOVA Speech 연결 성공"
        elif r.status_code == 401:
            return False, "인증 실패 (HTTP 401): Secret Key를 다시 확인해주세요."
        elif r.status_code == 403:
            return False, "접근 거부 (HTTP 403): CLOVA Speech 서비스 이용 신청을 확인해주세요."
        else:
            return True, f"응답 확인 (HTTP {r.status_code}) — 정상 연결"
    except requests.exceptions.ConnectionError:
        return False, "연결 오류: Invoke URL을 확인해주세요."
    except requests.exceptions.Timeout:
        return False, "연결 시간 초과"
    except Exception as e:
        return False, f"오류: {e}"


def transcribe(
    audio_path: str,
    invoke_url: str,
    secret_key: str,
    progress_cb=None,
    num_speakers: int = 0,
    cancel_event: threading.Event = None,
    status_cb=None,
) -> tuple[bool, str]:
    """
    CLOVA Speech Long API로 음성 파일 변환.
    반환: (성공여부, 텍스트 또는 오류 메시지)
    """
    if not os.path.exists(audio_path):
        return False, f"파일을 찾을 수 없습니다: {audio_path}"
    if not invoke_url.strip() or not secret_key.strip():
        return False, "Invoke URL과 Secret Key를 설정 탭에서 입력해주세요."

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb > _MAX_FILE_MB:
        return False, f"파일 크기({file_size_mb:.1f}MB)가 최대 {_MAX_FILE_MB}MB를 초과합니다."

    _status(status_cb, f"CLOVA Speech 변환 시작... ({file_size_mb:.1f}MB)")
    _progress(progress_cb, 5)

    if cancel_event and cancel_event.is_set():
        return False, "사용자에 의해 중단됨"

    # 파라미터 구성
    params = {
        "language": "ko-KR",
        "completion": "sync",
        "resultToDisplay": True,
        "noiseFiltering": True,
        "wordAlignment": False,
    }
    if num_speakers and num_speakers > 0:
        params["diarization"] = {
            "enable": True,
            "speakerCountMax": int(num_speakers),
            "speakerCountMin": 1,
        }
    else:
        params["diarization"] = {
            "enable": True,
            "speakerCountMax": 8,
            "speakerCountMin": 1,
        }

    url = invoke_url.rstrip("/") + _UPLOAD_PATH
    _status(status_cb, "서버에 업로드 중...")
    _progress(progress_cb, 15)

    try:
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단됨"

        _status(status_cb, "변환 처리 중... (긴 녹음은 수 분 소요)")
        _progress(progress_cb, 30)

        resp = requests.post(
            url,
            headers={"X-CLOVASPEECH-API-KEY": secret_key.strip()},
            files={"media": (os.path.basename(audio_path), audio_data)},
            data={"params": json.dumps(params, ensure_ascii=False)},
            timeout=_REQUEST_TIMEOUT,
        )

        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단됨"

        _progress(progress_cb, 80)

        if resp.status_code != 200:
            try:
                err = resp.json()
                msg = err.get("message") or err.get("errorMessage") or resp.text[:200]
            except Exception:
                msg = resp.text[:200]
            return False, f"API 오류 (HTTP {resp.status_code}): {msg}"

        data = resp.json()
        if data.get("result") not in ("COMPLETED", None):
            return False, f"변환 실패: {data.get('message', '알 수 없는 오류')}"

        _progress(progress_cb, 90)
        _status(status_cb, "결과 정리 중...")

        text = _format_result(data)
        if not text.strip():
            return False, "변환 결과가 비어 있습니다. 오디오 품질을 확인해주세요."

        _progress(progress_cb, 100)
        _status(status_cb, "✅ CLOVA Speech 변환 완료")
        return True, text

    except requests.exceptions.Timeout:
        return False, "요청 시간 초과 — 파일이 너무 크거나 네트워크 상태가 불안정합니다."
    except requests.exceptions.ConnectionError:
        return False, "연결 오류 — Invoke URL과 인터넷 연결을 확인해주세요."
    except Exception as e:
        return False, f"오류: {e}"


def _format_result(data: dict) -> str:
    """API 응답을 [화자N] 형식 텍스트로 변환"""
    segments = data.get("segments", [])
    if not segments:
        return data.get("text", "")

    lines = []
    current_speaker = None
    current_texts = []

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        diar = seg.get("diarization") or {}
        speaker_label = diar.get("label", "")
        speaker = f"[화자{speaker_label}]" if speaker_label else ""

        if speaker != current_speaker:
            if current_speaker is not None and current_texts:
                block = ''.join(current_texts)
                lines.append(f"{current_speaker} {block}" if current_speaker else block)
            current_speaker = speaker
            current_texts = [text]
        else:
            current_texts.append(" " + text)

    if current_texts:
        block = ''.join(current_texts)
        lines.append(f"{current_speaker} {block}" if current_speaker else block)

    return "\n".join(lines)


def _status(cb, msg: str):
    if cb:
        try:
            cb(msg)
        except Exception:
            pass


def _progress(cb, value: int):
    if cb:
        try:
            cb(value)
        except Exception:
            pass
