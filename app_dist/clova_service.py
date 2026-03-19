"""
회의녹음요약 - NAVER Cloud CLOVA Speech Recognition (STT)
CLOVA Speech Recognition (CSR) API 사용
- 엔드포인트: https://naveropenapi.apigw.ntruss.com/recog/v1/stt
- 인증: X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY
- 장시간 파일: ffmpeg로 청크 분할 처리 (Gemini 타임아웃 문제 해소)
"""
import os
import time
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# ── 상수 ──────────────────────────────────────────────────
_CSR_URL      = "https://naveropenapi.apigw.ntruss.com/recog/v1/stt?lang=Kor"
_CHUNK_SEC    = 50          # 청크당 최대 초 (CSR 권장 50초 이하)
_MAX_DIRECT_MB = 5          # 이 크기 미만은 청크 없이 직접 전송
_REQUEST_TIMEOUT = 120      # 단일 요청 타임아웃(초)

_MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}

# ── 공개 함수 ─────────────────────────────────────────────

def test_connection(client_id: str, client_secret: str) -> tuple:
    """API 키 유효성 확인 (최소 오디오 데이터로 ping)"""
    if not client_id or not client_secret:
        return False, "CLOVA Speech Client ID / Secret을 입력해주세요."
    if requests is None:
        return False, "requests 패키지가 없습니다. 'pip install requests' 후 재시도하세요."
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY":    client_secret,
        "Content-Type":           "application/octet-stream",
    }
    # 빈 WAV 헤더로 연결만 확인 (인증 오류 여부 체크)
    minimal_wav = bytes([
        0x52,0x49,0x46,0x46, 0x24,0x00,0x00,0x00,  # RIFF....
        0x57,0x41,0x56,0x45, 0x66,0x6D,0x74,0x20,  # WAVEfmt
        0x10,0x00,0x00,0x00, 0x01,0x00, 0x01,0x00, # chunk size, PCM, 1ch
        0x44,0xAC,0x00,0x00, 0x88,0x58,0x01,0x00, # 44100 Hz
        0x02,0x00, 0x10,0x00,                       # block align, 16bit
        0x64,0x61,0x74,0x61, 0x00,0x00,0x00,0x00,  # data....
    ])
    try:
        resp = requests.post(
            _CSR_URL, headers=headers, data=minimal_wav, timeout=15)
        # 401/403 → 인증 실패, 400/200 → 연결 성공 (빈 오디오 파싱 오류는 정상)
        if resp.status_code in (401, 403):
            return False, f"인증 실패 (HTTP {resp.status_code}): Client ID / Secret을 다시 확인해주세요."
        return True, f"연결 성공! (CLOVA Speech Recognition, HTTP {resp.status_code})"
    except Exception as e:
        return False, f"연결 오류: {str(e)[:200]}"


def transcribe(audio_path: str, client_id: str, client_secret: str,
               progress_cb=None, num_speakers: int = 0,
               cancel_event=None, status_cb=None) -> tuple:
    """오디오 파일 → 한국어 텍스트 (STT).

    - 소형 파일: 직접 전송
    - 대형 파일: ffmpeg로 청크 분할 후 순차 전송 → 결과 합산
    """
    if requests is None:
        return False, "requests 패키지가 없습니다. 'pip install requests' 를 실행해주세요."
    if not client_id or not client_secret:
        return False, "CLOVA Speech API 키가 없습니다. 설정 탭에서 입력해주세요."
    if not os.path.exists(audio_path):
        return False, f"파일을 찾을 수 없습니다: {audio_path}"

    ext  = Path(audio_path).suffix.lower()
    size_mb = os.path.getsize(audio_path) / 1024 / 1024

    try:
        if progress_cb: progress_cb(5)
        if status_cb: status_cb(f"CLOVA STT 준비 중... ({size_mb:.1f}MB)")

        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        # 소형 파일: 직접 전송
        if size_mb <= _MAX_DIRECT_MB:
            if status_cb: status_cb(f"CLOVA STT 변환 중... ({size_mb:.1f}MB)")
            result = _send_to_clova(audio_path, ext, client_id, client_secret,
                                    cancel_event, status_cb)
            if progress_cb: progress_cb(100)
            return True, result

        # 대형 파일: 청크 분할
        if status_cb: status_cb(f"대용량 파일 분할 처리 중... ({size_mb:.1f}MB)")
        result = _chunked_transcribe(
            audio_path, ext, client_id, client_secret,
            progress_cb, cancel_event, status_cb)
        if progress_cb: progress_cb(100)
        return True, result

    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, _friendly_error(str(e))


def apply_speaker_labels(text: str) -> str:
    """CLOVA CSR은 화자 분리 미지원 → 텍스트 그대로 반환
    (화자 구분이 필요한 경우 요약 단계에서 AI가 문맥 기반 구분)"""
    return text


# ── 내부 함수 ─────────────────────────────────────────────

def _send_to_clova(audio_path: str, ext: str,
                   client_id: str, client_secret: str,
                   cancel_event=None, status_cb=None) -> str:
    """단일 오디오 파일을 CLOVA CSR API로 전송하여 텍스트 반환"""
    mime = _MIME.get(ext, "audio/mpeg")
    headers = {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY":    client_secret,
        "Content-Type":           mime,
    }

    # 한글 경로 안전 처리: 영문 임시 경로로 복사
    tmp_dir  = tempfile.mkdtemp(prefix="clova_stt_")
    safe_path = os.path.join(tmp_dir, f"audio{ext}")
    try:
        shutil.copy2(audio_path, safe_path)
        with open(safe_path, "rb") as f:
            audio_data = f.read()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if cancel_event and cancel_event.is_set():
        raise RuntimeError("사용자에 의해 중단되었습니다.")

    try:
        resp = requests.post(
            _CSR_URL, headers=headers, data=audio_data,
            timeout=_REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "CLOVA API 요청 시간이 초과되었습니다. 네트워크를 확인하거나 청크 크기를 줄여주세요.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("CLOVA API 서버에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.")

    if resp.status_code == 401:
        raise RuntimeError("CLOVA API 인증 실패: Client ID / Secret을 다시 확인해주세요.")
    if resp.status_code == 403:
        raise RuntimeError("CLOVA API 권한 없음: API 사용 설정 또는 요금제를 확인해주세요.")
    if resp.status_code == 429:
        raise RuntimeError("CLOVA API 요청 한도 초과: 잠시 후 다시 시도해주세요.")

    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(f"CLOVA API 응답 오류 (HTTP {resp.status_code}): {resp.text[:200]}")

    if resp.status_code != 200:
        msg = data.get("error", {}).get("message", resp.text[:200])
        raise RuntimeError(f"CLOVA API 오류 (HTTP {resp.status_code}): {msg}")

    text = data.get("text", "").strip()
    if not text:
        raise RuntimeError("CLOVA STT 응답이 비어 있습니다. 파일을 다시 확인해주세요.")
    return text


def _find_ffmpeg() -> str:
    """시스템에서 ffmpeg 실행 파일 탐색"""
    candidates = [
        "ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        str(Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe"),
    ]
    # WinGet 설치 경로
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local.exists():
        for p in local.rglob("ffmpeg.exe"):
            candidates.insert(0, str(p))
            break
    # 앱 번들 내 ffmpeg (PyInstaller 빌드 시)
    bundle_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / "ffmpeg_bundle"
    bundle_exe = bundle_dir / "ffmpeg.exe"
    if bundle_exe.exists():
        candidates.insert(0, str(bundle_exe))

    for c in candidates:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    raise RuntimeError(
        "FFmpeg를 찾을 수 없습니다.\n"
        "명령 프롬프트에서 'winget install ffmpeg' 를 실행 후 다시 시도해주세요.")


def _get_duration(ffmpeg: str, audio_path: str) -> float:
    """ffmpeg로 오디오 재생 시간(초) 조회"""
    probe = subprocess.run(
        [ffmpeg, "-i", audio_path],
        capture_output=True, timeout=30,
        encoding="utf-8", errors="replace")
    for line in (probe.stdout + probe.stderr).splitlines():
        if "Duration:" in line:
            try:
                raw = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = raw.split(":")
                total = int(h) * 3600 + int(m) * 60 + float(s)
                if total > 0:
                    return total
            except Exception:
                pass
    raise RuntimeError("오디오 재생 시간을 파악할 수 없습니다. 파일이 손상되었을 수 있습니다.")


def _chunked_transcribe(audio_path: str, ext: str,
                        client_id: str, client_secret: str,
                        progress_cb=None, cancel_event=None,
                        status_cb=None) -> str:
    """ffmpeg로 청크 분할 후 각 청크를 CLOVA에 전송, 결과 합산"""
    ffmpeg = _find_ffmpeg()
    tmpdir = tempfile.mkdtemp(prefix="clova_chunk_")
    try:
        if progress_cb: progress_cb(8)

        # 한글 경로 우회: 영문 임시 경로로 원본 복사
        safe_src = os.path.join(tmpdir, f"source{ext}")
        shutil.copy2(audio_path, safe_src)

        duration = _get_duration(ffmpeg, safe_src)
        n_chunks = max(1, int(duration / _CHUNK_SEC) + (1 if duration % _CHUNK_SEC > 1 else 0))

        if status_cb: status_cb(f"분할 처리: 총 {n_chunks}개 청크 ({duration:.0f}초)")

        chunks = []
        for i in range(n_chunks):
            out = os.path.join(tmpdir, f"chunk_{i:03d}{ext}")
            subprocess.run(
                [ffmpeg, "-y", "-i", safe_src,
                 "-ss", str(i * _CHUNK_SEC),
                 "-t",  str(_CHUNK_SEC),
                 "-acodec", "copy", out],
                capture_output=True, timeout=180)
            if os.path.exists(out) and os.path.getsize(out) > 512:
                chunks.append(out)

        if not chunks:
            raise RuntimeError("오디오 분할에 실패했습니다. FFmpeg 버전을 확인해주세요.")

        if progress_cb: progress_cb(15)

        results = []
        n = len(chunks)
        for i, chunk_path in enumerate(chunks):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("사용자에 의해 중단되었습니다.")

            chunk_ext  = Path(chunk_path).suffix.lower()
            pct = 15 + int((i + 1) / n * 80)
            if status_cb:
                status_cb(f"CLOVA STT 변환 중... ({i+1}/{n} 청크, {int((i/n)*100)}% 완료)")

            # 재시도 로직 (최대 3회)
            for attempt in range(3):
                try:
                    text = _send_to_clova(
                        chunk_path, chunk_ext, client_id, client_secret,
                        cancel_event, status_cb)
                    results.append(text.strip())
                    break
                except RuntimeError as e:
                    if "중단" in str(e) or attempt == 2:
                        raise
                    if status_cb:
                        status_cb(f"청크 {i+1} 재시도 중... ({attempt+2}/3)")
                    time.sleep(3)

            if progress_cb: progress_cb(pct)

        if not results:
            raise RuntimeError("모든 청크 STT 처리에 실패했습니다.")

        if progress_cb: progress_cb(95)
        return "\n".join(results)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _friendly_error(msg: str) -> str:
    """사용자 친화적 오류 메시지 변환"""
    if "중단" in msg:
        return msg
    if "FFmpeg" in msg or "winget install" in msg:
        return msg
    if "401" in msg or "인증 실패" in msg:
        return "CLOVA API 인증 실패: Client ID / Secret을 설정 탭에서 다시 확인해주세요."
    if "403" in msg or "권한" in msg:
        return "CLOVA API 권한 없음: NCP 콘솔에서 CLOVA Speech 사용 설정을 확인해주세요."
    if "429" in msg or "한도 초과" in msg:
        return "CLOVA API 요청 한도 초과: 잠시 후 다시 시도해주세요."
    if "timeout" in msg.lower() or "시간 초과" in msg:
        return "CLOVA API 응답 시간 초과: 네트워크 상태를 확인하고 다시 시도해주세요."
    if "ConnectionError" in msg or "연결할 수 없습니다" in msg:
        return "CLOVA API 서버에 연결할 수 없습니다. 인터넷 연결을 확인해주세요."
    return f"CLOVA 오류: {msg[:300]}"
