"""
회의녹음요약 - Gemini API (STT + 요약)
gemini-2.0-flash 사용
"""
import os
import time
import tempfile
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types
from config import GEMINI_STT_MODEL, GEMINI_SUMMARY_MODEL, GEMINI_INLINE_LIMIT_MB

_MIME = {
    ".mp3": "audio/mp3", ".wav": "audio/wav",
    ".m4a": "audio/mp4", ".mp4": "audio/mp4",
    ".ogg": "audio/ogg", ".flac": "audio/flac",
}

_INLINE_LIMIT_MB  = GEMINI_INLINE_LIMIT_MB
_FILES_API_MAX_MB = 50   # 50MB 초과는 청크 분할 처리 (출력 토큰 한도 문제 방지)
_CHUNK_MB         = 10   # 10MB 청크 → 인라인 처리 가능, 토큰 부족 문제 없음

# ── STT 프롬프트 ────────────────────────────────────────
_STT_PROMPT_TEMPLATE = """이 오디오 파일을 한국어 텍스트로 정확히 전사해주세요.

규칙:
{speaker_rule}- 불명확한 부분은 [불명확] 표시
- 의미 없는 짧은 반복(어, 음 등)은 생략
- 전사 결과만 출력하고 설명 없이 바로 시작"""


def _make_stt_prompt(num_speakers: int = 0) -> str:
    if num_speakers == 1:
        rule = "- 화자가 1명이므로 화자 구분 없이 전사\n"
    elif num_speakers >= 2:
        rule = (f"- 화자가 {num_speakers}명입니다. "
                f"[화자1], [화자2]"
                f"{', [화자3]' if num_speakers >= 3 else ''} 형식으로 구분\n")
    else:
        rule = "- 여러 화자는 [화자1], [화자2] 형식으로 구분\n"
    return _STT_PROMPT_TEMPLATE.format(speaker_rule=rule)


# ── 요약 프롬프트 - 화자 중심 ───────────────────────────
_SUMMARY_SPEAKER_TEMPLATE = """당신은 전문 회의록 작성 전문가입니다.
다음 회의 전사 내용을 바탕으로 화자(참석자) 중심의 한국어 회의록을 작성해주세요.

[전사 내용]
{text}

[회의록 양식]
## 📋 회의록 (화자 중심)
생성 일시: {dt}

### 1. 회의 개요
- 주요 안건:
- 참석자:

### 2. 참석자별 주요 내용

### 3. 액션 아이템
| 담당자 | 내용 | 기한 |
|--------|------|------|

---
회의녹음요약 앱 자동 생성"""

# ── 요약 프롬프트 - 주제 중심 ───────────────────────────
_SUMMARY_TOPIC_TEMPLATE = """당신은 전문 회의록 작성 전문가입니다.
다음 회의 전사 내용을 바탕으로 주제/안건 중심의 한국어 회의록을 작성해주세요.

[전사 내용]
{text}

[회의록 양식]
## 📋 회의록 (주제 중심)
생성 일시: {dt}

### 1. 회의 개요
- 참석자(언급된 경우):
- 회의요약: 3줄내외(경영진보고 수준)

### 2. 논의 내용

### 3. 추가 논의 필요사항

---
회의녹음요약 앱 자동 생성"""


# ── 요약 프롬프트 - 공식 양식 (MD) ──────────────────────
_SUMMARY_FORMAL_MD_TEMPLATE = """너는 복잡한 회의 녹취록을 분석하여 핵심 정보를 체계적으로 정리하는 비즈니스 컨설턴트야.
제공된 텍스트의 모든 논의 사항을 놓치지 않으면서도, 읽기 쉽게 요약하여 마크다운(MD) 형식으로 회의록을 작성해줘.

[작성 가이드라인]
1. 완결성: 회의에서 언급된 모든 수치, 업체명, 전략, 리스크 및 결정 사항을 빠짐없이 포함할 것.
2. 구조화: 주요 내용을 아래 위계에 따라 분류할 것.
   * 1. 대제목 (## 사용)
   * 1.1 중제목 (### 사용)
   * 1.1.1 소제목 (#### 사용, 필요 시 하위 불렛 포인트 활용)
3. 간결성: 문장은 서술형보다는 명사형 종결이나 '~함', '~임' 등의 간결한 문체를 사용할 것.
4. Action Item: 회의 중 언급된 담당자, 기한, 구체적인 실행 과제를 명확히 추출할 것.

[전사 내용]
{text}

[회의록 출력 양식 — 마크다운]
# 회 의 록
생성 일시: {dt}

---

| 항목 | 내용 |
|------|------|
| 일 시 | {dt} |
| 장 소 | |
| 주 제 | |
| 참 석 자 | |
| 작 성 자 | AI 자동 생성 |

---

## 1. 회의 배경 및 목적

### 1.1 [배경]
- [내용]

### 1.2 [목적]
- [내용]

---

## 2. 주요 논의 내용

### 2.1 [중제목]

#### 2.1.1 [소제목]
- [내용]
  - [세부 내용]

---

## 3. 결정 사항

- [결정 1]
- [결정 2]

---

## 4. 리스크 및 우려 사항

| 우려 사항 | 답변 / 추가 검토 사항 |
|-----------|----------------------|
| [우려 1] | [답변 1] |

---

## 5. Action Items

| No. | 액션 아이템 | 담당자 | 기한 |
|:---:|------------|:------:|:----:|
| 1 | | | |
| 2 | | | |
| 3 | | | |

---

*본 회의록은 녹취 텍스트를 기반으로 AI가 자동 작성하였습니다. 사실관계 확인이 필요한 사항은 추가 검토 바랍니다.*

---
회의녹음요약 앱 자동 생성"""


# 하위 호환용 alias
_SUMMARY_FORMAL_TEMPLATE = _SUMMARY_FORMAL_MD_TEMPLATE


# ── 요약 프롬프트 - 흐름 중심 (v3 신규) ──────────────────
_SUMMARY_FLOW_TEMPLATE = """너는 회의의 흐름과 맥락을 깊이 이해하는 비즈니스 분석가야.
제공된 회의 전사 내용을 바탕으로, 회의가 어떻게 시작되어 어떤 흐름으로 진행되었으며
어떤 결론에 도달했는지를 시간순으로 서술하는 흐름 중심 회의록을 마크다운 형식으로 작성해줘.

[작성 가이드라인]
1. 시간적 흐름: 회의 시작 → 논의 전개 → 쟁점 부각 → 결론 순으로 서술
2. 맥락 보존: 발언자의 의도, 논리적 연결, 반응과 상호작용을 자연스럽게 서술
3. 인과관계 명시: 각 논의가 왜 이 방향으로 전개되었는지 설명
4. 분위기/온도: 합의, 이견, 갈등, 협력 등 회의 분위기를 간결히 반영
5. Action Items: 결정사항과 후속 과제를 마지막에 명확히 정리

[전사 내용]
{text}

[회의록 출력 양식 — 흐름 중심 마크다운]
# 회의록 (흐름 중심)
생성 일시: {dt}

---

| 항목 | 내용 |
|------|------|
| 일 시 | {dt} |
| 주 제 | |
| 참 석 자 | |
| 작 성 자 | AI 자동 생성 |

---

## 1. 회의 배경 및 시작

(회의가 왜 소집되었는지, 어떤 분위기로 시작되었는지 2~3문장으로 서술)

---

## 2. 회의 전개 흐름

(회의의 시간적 흐름을 자연스러운 문장으로 서술. 논의 순서, 쟁점 부각 과정, 의견 교환 등을 포함)

### 2.1 초반 논의 — [주요 주제]

(초반 논의 내용과 참석자 반응을 흐름 있게 서술)

### 2.2 핵심 쟁점 부각 — [쟁점명]

(핵심 쟁점이 어떻게 드러났고, 어떤 의견들이 오갔는지 서술)

### 2.3 결론 도출 과정

(논의가 어떤 방향으로 수렴되었는지, 최종 합의에 이르는 과정 서술)

---

## 3. 결정 사항

- [결정 1]: (결정 배경 포함)
- [결정 2]: (결정 배경 포함)

---

## 4. 미결 사항 및 후속 과제

| No. | 내용 | 담당자 | 기한 | 비고 |
|:---:|------|:------:|:----:|------|
| 1 | | | | |
| 2 | | | | |

---

*본 회의록은 녹취 텍스트를 기반으로 AI가 자동 작성하였습니다. 사실관계 확인이 필요한 사항은 추가 검토 바랍니다.*

---
회의녹음요약 앱 자동 생성"""


_SUMMARY_LECTURE_MD_TEMPLATE = """당신은 전문 강의 노트 작성자입니다.
아래 [강의 녹취록]을 분석하여 수강생이 복습과 학습에 바로 활용할 수 있는
구조화된 마크다운 강의 요약문을 작성해주세요.

강의 주제에 따라 자동으로 맥락에 맞는 용어와 구조를 사용하세요.
예를 들어, 신앙/종교 강의라면 말씀·묵상·실천 중심으로,
업무/실무 강의라면 개념·방법론·적용 중심으로 구성합니다.
반드시 아래 녹취록의 실제 내용만을 바탕으로 작성하고, 임의로 내용을 추가하거나 가상의 시나리오를 작성하지 마세요.

[강의 녹취록]
{text}

[작성 양식]
생성 일시: {dt}

# 📚 강의 요약 노트

**주요 주제**: (녹취록에서 파악한 핵심 주제 한 줄 요약)

---

## 1. 강의 개요
(이 강의에서 다루는 핵심 내용을 2~3문장으로 요약)

---

## 2. 주요 내용 정리
(강의에서 다룬 소주제들을 논리적 흐름과 인과관계에 따라 순서대로 구조화)
(각 소주제는 독립적으로 이해할 수 있도록 충분히 서술)

### 2.1 (소주제명)
-
-

### 2.2 (소주제명)
-
-

(소주제 수에 따라 반복)

---

## 3. 핵심 요약 (3줄 정리)
1.
2.
3.

---
강의녹음요약 앱 자동 생성"""


def _client(api_key: str):
    # timeout=1800000ms(=30분) — HttpOptions의 timeout 단위는 밀리초(ms)
    try:
        return genai.Client(api_key=api_key,
                            http_options=types.HttpOptions(timeout=1800000))
    except Exception:
        return genai.Client(api_key=api_key)


def _trim_summary(text: str) -> str:
    """요약 출력 끝에 전사 내용이 포함된 경우 회의록 끝 마커 이후를 제거"""
    marker = "회의녹음요약 앱 자동 생성"
    idx = text.find(marker)
    if idx != -1:
        return text[:idx + len(marker)].strip()
    return text.strip()


# ── 공개 함수 ───────────────────────────────────────────

def test_connection(api_key: str) -> tuple:
    try:
        client = _client(api_key)
        models = list(client.models.list())
        gemini_models = [m.name for m in models if "gemini" in m.name.lower()]
        if not gemini_models:
            return False, "사용 가능한 Gemini 모델이 없습니다."
        available = any(GEMINI_SUMMARY_MODEL in m for m in gemini_models)
        if available:
            return True, f"연결 성공! ({GEMINI_SUMMARY_MODEL} 사용 가능)"
        return True, f"연결 성공! (사용 가능 모델: {len(gemini_models)}개)"
    except Exception as e:
        return False, _friendly_error(str(e))


def transcribe(audio_path: str, api_key: str, progress_cb=None,
               num_speakers: int = 0, speaker_names: dict = None,
               cancel_event=None, status_cb=None) -> tuple:
    """오디오 → 텍스트 (STT). cancel_event가 set되면 중단."""
    if not api_key:
        return False, "Gemini API 키가 없습니다. 설정 탭에서 입력해주세요."
    if not os.path.exists(audio_path):
        return False, f"파일을 찾을 수 없습니다: {audio_path}"

    ext  = Path(audio_path).suffix.lower()
    mime = _MIME.get(ext, "audio/mp3")
    size = os.path.getsize(audio_path) / 1024 / 1024
    stt_prompt = _make_stt_prompt(num_speakers)

    try:
        client = _client(api_key)
        if progress_cb: progress_cb(5)
        if status_cb: status_cb(f"STT 변환 준비 중... ({size:.1f}MB)")
        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        if size < _INLINE_LIMIT_MB:
            if status_cb: status_cb(f"변환 중... ({size:.1f}MB, 인라인 처리)")
            text = _inline(client, audio_path, mime, progress_cb, stt_prompt,
                           status_cb=status_cb, cancel_event=cancel_event)
        elif size <= _FILES_API_MAX_MB:
            text = _upload_and_transcribe(client, audio_path, mime, stt_prompt,
                                          progress_cb, 10, 95, cancel_event,
                                          status_cb=status_cb)
        else:
            if status_cb: status_cb(f"대용량 파일 분할 처리 중... ({size:.1f}MB)")
            text = _chunked_transcribe(client, audio_path, mime, stt_prompt,
                                       progress_cb, num_speakers, cancel_event)

        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        if speaker_names:
            text = apply_speaker_names(text, speaker_names)
        if progress_cb: progress_cb(100)
        return True, text
    except Exception as e:
        return False, _friendly_error(str(e))


def summarize(stt_text: str, api_key: str, progress_cb=None,
              summary_mode: str = "speaker", cancel_event=None,
              custom_instruction: str = "") -> tuple:
    """STT 텍스트 → 회의록 요약"""
    if not api_key:
        return False, "Gemini API 키가 없습니다."
    if not stt_text.strip():
        return False, "변환된 텍스트가 비어 있습니다."

    if summary_mode == "topic":
        template = _SUMMARY_TOPIC_TEMPLATE
    elif summary_mode in ("formal_md", "official", "formal_text", "formal"):
        # v3: 공식양식(텍스트) 폐지 → 전부 회의양식(MD)로 통합
        template = _SUMMARY_FORMAL_MD_TEMPLATE
    elif summary_mode == "lecture_md":
        template = _SUMMARY_LECTURE_MD_TEMPLATE
    elif summary_mode == "flow":
        template = _SUMMARY_FLOW_TEMPLATE
    else:
        template = _SUMMARY_SPEAKER_TEMPLATE
    try:
        client = _client(api_key)
        if progress_cb: progress_cb(10)
        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        prompt = template.format(
            text=stt_text[:500000],  # gemini-2.5-flash 컨텍스트 한도(1M토큰) 내 최대 활용
            dt=datetime.now().strftime("%Y년 %m월 %d일 %H:%M"),
        )
        if custom_instruction and custom_instruction.strip():
            prompt += f"\n\n[추가 지시사항]\n{custom_instruction.strip()}"
        if progress_cb: progress_cb(30)

        # 하트비트: 요약 API 응답 대기 중 10초마다 경과 시간 표시
        _stop_beat = threading.Event()
        _beat_start = time.time()
        def _beat():
            while not _stop_beat.is_set():
                _stop_beat.wait(10)
                if not _stop_beat.is_set():
                    elapsed = int(time.time() - _beat_start)
                    if progress_cb and elapsed > 0:
                        # 30~95 범위에서 경과 시간에 따라 서서히 증가 (최대 95)
                        pct = min(95, 30 + elapsed // 3)
                        progress_cb(pct)
        threading.Thread(target=_beat, daemon=True).start()

        try:
            resp = client.models.generate_content(
                model=GEMINI_SUMMARY_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=65536),
            )
        finally:
            _stop_beat.set()

        if progress_cb: progress_cb(100)
        result_text = resp.text
        if not result_text:
            try:
                result_text = resp.candidates[0].content.parts[0].text
            except Exception:
                return False, "요약 응답이 비어 있습니다. 다시 시도해주세요."
        return True, _trim_summary(result_text)
    except Exception as e:
        return False, _friendly_error(str(e))


def extract_key_metrics(summary_text: str, api_key: str,
                        cancel_event=None, status_cb=None) -> tuple:
    """요약 텍스트 → 핵심 지표 추출 (결정사항 / 액션아이템 / 일정 / 수치 / 키워드)"""
    if not api_key:
        return False, "Gemini API 키가 없습니다."
    if not summary_text.strip():
        return False, "요약 텍스트가 비어 있습니다."

    prompt = f"""다음 회의록 요약에서 핵심 정보를 추출해주세요.

[요약 텍스트]
{summary_text[:100000]}

[출력 형식 — 반드시 아래 항목과 이모지를 그대로 사용하고, 없는 항목은 "없음"으로 표시]

📋 결정사항
- (결정된 사항 나열, 없으면 "없음")

✅ 액션 아이템
- 담당자: X | 업무: Y | 기한: Z (없으면 "없음")

📅 주요 일정
- (날짜/기한 포함 일정, 없으면 "없음")

🔢 핵심 수치
- (금액, 기간, 비율 등 주요 숫자, 없으면 "없음")

🏷️ 키워드
- (3~7개, 쉼표로 구분)"""

    try:
        if status_cb: status_cb("핵심 지표 추출 중...")
        client = _client(api_key)
        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."
        resp = client.models.generate_content(
            model=GEMINI_SUMMARY_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=4096),
        )
        result_text = resp.text
        if not result_text:
            try:
                result_text = resp.candidates[0].content.parts[0].text
            except Exception:
                return False, "핵심 지표 응답이 비어 있습니다."
        if status_cb: status_cb("핵심 지표 추출 완료!")
        return True, result_text
    except Exception as e:
        return False, _friendly_error(str(e))


def apply_speaker_names(text: str, speaker_names: dict) -> str:
    """[화자N] → 실제 이름으로 치환"""
    if not text or not speaker_names:
        return text or ""
    for num, name in speaker_names.items():
        if name and name.strip():
            text = text.replace(f"[화자{num}]", f"[{name}]")
    return text


# ── 내부 함수 ───────────────────────────────────────────

def _inline(client, audio_path, mime, progress_cb, stt_prompt,
            status_cb=None, cancel_event=None):
    with open(audio_path, "rb") as f:
        data = f.read()
    if progress_cb: progress_cb(40)
    if status_cb: status_cb("Gemini STT 변환 중... (1~10분 소요, 응답 대기 중)")

    # 하트비트: API 응답 대기 중 10초마다 경과 시간 표시
    _stop_beat = threading.Event()
    _start = time.time()
    def _beat():
        while not _stop_beat.is_set():
            _stop_beat.wait(10)
            if not _stop_beat.is_set() and status_cb:
                elapsed = int(time.time() - _start)
                status_cb(f"Gemini STT 변환 중... ({elapsed}초 경과, 응답 대기 중)")
    threading.Thread(target=_beat, daemon=True).start()

    try:
        resp = client.models.generate_content(
            model=GEMINI_STT_MODEL,
            contents=[stt_prompt,
                      types.Part.from_bytes(data=data, mime_type=mime)],
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=65536),
        )
    finally:
        _stop_beat.set()

    if progress_cb: progress_cb(90)
    result_text = resp.text
    if not result_text:
        try:
            result_text = resp.candidates[0].content.parts[0].text
        except Exception:
            raise RuntimeError("Gemini STT 응답이 비어 있습니다. 파일을 다시 시도해주세요.")
    return result_text


def _wait_for_active(client, uploaded, max_wait=600, cancel_event=None):
    waited = 0
    while waited < max_wait:
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("사용자에 의해 중단되었습니다.")
        raw   = str(getattr(uploaded, "state", "UNKNOWN"))
        state = raw.split(".")[-1] if "." in raw else raw
        if state == "ACTIVE":
            return uploaded
        elif state in ("FAILED", "PERMANENTLY_DELETED"):
            raise RuntimeError(f"Files API 처리 실패 (state={state})")
        elif state == "PROCESSING":
            time.sleep(10); waited += 10
            try:
                uploaded = client.files.get(name=uploaded.name)
            except Exception:
                pass
        else:
            return uploaded
    raise RuntimeError(f"Files API 처리 시간 초과 ({waited}s)")


def _upload_and_transcribe(client, audio_path, mime, stt_prompt,
                           progress_cb, pct_start, pct_end, cancel_event=None,
                           status_cb=None):
    ext = Path(audio_path).suffix.lower()
    safe_display = f"audio{ext}"
    size_mb = os.path.getsize(audio_path) / 1024 / 1024

    if progress_cb: progress_cb(pct_start)
    if status_cb: status_cb(f"파일 준비 중... ({size_mb:.1f}MB)")

    # 한글 경로 우회: 영문 임시 경로로 복사 후 업로드
    tmp_dir = tempfile.mkdtemp(prefix="stt_upload_")
    tmp_path = os.path.join(tmp_dir, safe_display)
    try:
        shutil.copy2(audio_path, tmp_path)
        if status_cb: status_cb(f"Gemini에 업로드 중... ({size_mb:.1f}MB, 잠시 기다려주세요)")
        uploaded = client.files.upload(
            file=Path(tmp_path),
            config=types.UploadFileConfig(mime_type=mime, display_name=safe_display),
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if progress_cb: progress_cb(pct_start + int((pct_end - pct_start) * 0.3))
    if status_cb: status_cb("서버에서 파일 처리 중... (ACTIVE 대기)")
    uploaded = _wait_for_active(client, uploaded, cancel_event=cancel_event)

    if progress_cb: progress_cb(pct_start + int((pct_end - pct_start) * 0.5))
    if status_cb: status_cb("STT 변환 중... (AI 처리 중, 파일이 클수록 시간이 걸립니다)")
    resp = client.models.generate_content(
        model=GEMINI_STT_MODEL,
        contents=[stt_prompt, uploaded],
        config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=65536),
    )
    try:
        client.files.delete(name=uploaded.name)
    except Exception:
        pass
    if progress_cb: progress_cb(pct_end)

    # resp.text가 None인 경우 candidates에서 직접 추출
    result_text = resp.text
    if not result_text:
        try:
            result_text = resp.candidates[0].content.parts[0].text
        except Exception:
            raise RuntimeError("Gemini STT 응답이 비어 있습니다. 파일을 다시 시도해주세요.")
    if status_cb: status_cb("변환 완료!")
    return result_text


def _find_ffmpeg() -> str:
    candidates = [
        "ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        str(Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe"),
    ]
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local.exists():
        for p in local.rglob("ffmpeg.exe"):
            candidates.insert(0, str(p)); break
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


def _get_duration(ffmpeg, audio_path):
    probe = subprocess.run([ffmpeg, "-i", audio_path],
                           capture_output=True, timeout=30,
                           encoding="utf-8", errors="replace")
    for line in (probe.stdout + probe.stderr).splitlines():
        if "Duration:" in line:
            try:
                raw = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = raw.split(":")
                total = int(h)*3600 + int(m)*60 + float(s)
                if total > 0:
                    return total
            except Exception:
                pass
    raise RuntimeError("오디오 재생 시간을 파악할 수 없습니다.")


def _chunked_transcribe(client, audio_path, mime, stt_prompt,
                        progress_cb, num_speakers, cancel_event=None):
    ffmpeg = _find_ffmpeg()
    tmpdir = tempfile.mkdtemp(prefix="meeting_stt_")
    try:
        if progress_cb: progress_cb(8)

        # 한글 경로 우회: 원본 파일을 영문 임시 경로로 복사
        ext = Path(audio_path).suffix.lower()
        safe_src = os.path.join(tmpdir, f"source{ext}")
        shutil.copy2(audio_path, safe_src)

        duration = _get_duration(ffmpeg, safe_src)
        file_mb  = os.path.getsize(safe_src) / 1024 / 1024
        n_chunks = max(2, int(file_mb / _CHUNK_MB) + 1)
        chunk_sec = duration / n_chunks
        chunks = []
        for i in range(n_chunks):
            out = os.path.join(tmpdir, f"chunk_{i:03d}{ext}")
            subprocess.run(
                [ffmpeg, "-y", "-i", safe_src,
                 "-ss", str(i * chunk_sec), "-t", str(chunk_sec),
                 "-acodec", "copy", out],
                capture_output=True, timeout=180)
            if os.path.exists(out) and os.path.getsize(out) > 1024:
                chunks.append(out)

        if not chunks:
            raise RuntimeError("오디오 분할 실패.")
        if progress_cb: progress_cb(15)

        results = []
        n = len(chunks)
        for i, chunk_path in enumerate(chunks):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("사용자에 의해 중단되었습니다.")
            pct_s = 15 + int(i / n * 75)
            pct_e = 15 + int((i+1) / n * 75)
            chunk_ext  = Path(chunk_path).suffix.lower()
            chunk_mime = _MIME.get(chunk_ext, mime)
            chunk_mb   = os.path.getsize(chunk_path) / 1024 / 1024
            if chunk_mb < _INLINE_LIMIT_MB:
                text = _inline(client, chunk_path, chunk_mime, None, stt_prompt)
            else:
                text = _upload_and_transcribe(
                    client, chunk_path, chunk_mime, stt_prompt,
                    progress_cb, pct_s, pct_e, cancel_event)
            results.append(text.strip())
            if progress_cb: progress_cb(pct_e)

        if not results:
            raise RuntimeError("모든 청크 STT 처리 실패.")
        if progress_cb: progress_cb(92)
        return "\n\n".join(results)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _friendly_error(msg: str) -> str:
    if "FFmpeg" in msg or "winget install" in msg:
        return msg
    if "중단" in msg:
        return msg
    if "UNAUTHENTICATED" in msg or "no credentials" in msg.lower():
        return "Gemini API 키가 설정되지 않았습니다. 설정 탭에서 입력해주세요."
    if "API_KEY_INVALID" in msg:
        return "API 키가 올바르지 않습니다. 설정 탭에서 다시 확인해주세요."
    if "PERMISSION_DENIED" in msg or "403" in msg:
        return "API 키 권한이 없습니다. Google AI Studio에서 키를 확인하세요."
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        if "PerDay" in msg or "quota" in msg.lower():
            return "API 일일 사용량이 소진됐습니다. 내일 다시 시도하거나 결제 설정을 확인해주세요."
        return "API 요청이 너무 많습니다. 30초 후 다시 시도해주세요."
    if "SAFETY" in msg:
        return "콘텐츠 안전 정책으로 처리가 거부되었습니다."
    if "timeout" in msg.lower():
        return "처리 시간이 초과되었습니다. 네트워크 상태를 확인하고 다시 시도해주세요."
    if any(c in msg for c in ["500","502","503","504"]):
        return "Gemini 서버 일시 오류입니다. 잠시 후 다시 시도해주세요."
    return f"Gemini 오류: {msg[:300]}"
