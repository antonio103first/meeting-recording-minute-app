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
import json
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
                f"발언 내용·자기소개·호칭·맥락을 파악하여 화자를 실명 또는 역할명으로 추정 표기 "
                f"(예: [홍길동 대표], [담당자], [교수님]). 추정 불가 시 [화자1], [화자2] 순번 사용\n")
    else:
        rule = ("- 발언 내용·자기소개·호칭·맥락을 파악하여 화자를 실명 또는 역할명으로 추정 표기 "
                "(예: [홍길동 대표], [담당자], [교수님]). 추정 불가 시 [화자1], [화자2] 순번 사용\n")
    return _STT_PROMPT_TEMPLATE.format(speaker_rule=rule)


# ── 요약 프롬프트 - 회의록 — 외부 미팅·기관협의·다자간 공식회의 ────
_SUMMARY_TOPIC_TEMPLATE = """당신은 전문 비즈니스 회의록 작성자입니다.
아래 회의 전사 내용은 기관 협의, 다자간 공식회의, 주주총회 등 복수의 이해관계자가 참석한 외부 미팅 녹취록입니다.
안건·주제 중심으로 구조화하여 공식 회의록 형식으로 작성해주세요.

[화자 표기 기준]
- 발언 내용·자기소개·호칭·맥락을 파악하여 각 화자를 실명 또는 역할명으로 추정 표기 (예: [원동연 교수], [김과장], [A기관 담당자])
- Antonio(대표이사, 회의 주체) 발언으로 판단되면 → [나]로 표기
- 추정 불가 시 → [화자1], [화자2] 순번 사용
- 발언자 불명확한 경우 → [불명확] 표기

[작성 원칙]
1. 팩트 기반: 대화에서 실제 나눈 내용에만 기초하여 작성. 녹취에 없는 내용 절대 추가 금지
2. 공식 회의록 기준: 안건별로 협의 내용, 각 기관 입장, 결정사항을 명확히 기록
3. 사실·팩트 중심: 녹취록에 명시된 수치·발언·결정만 기록. 추측·임의 추가 금지. 불확실한 수치는 (추정) 표기
4. 상세 서술 원칙: 핵심 논의 내용은 배경·경위·수치·결론을 포함하여 충분히 상세하게 서술. 지나친 압축 금지
5. Q&A 원칙: Q&A로 실제 오고간 내용만 기록. 임의 추정하여 내용 추가 금지
6. Q&A 포착 원칙 — 발표자 외 모든 참석자의 질의·코멘트를 빠짐없이 기록:
   - 발표자(주 발언자)의 설명에 대해 다른 참석자가 질문하거나 의견을 낸 모든 교환을 Q&A로 기록
   - 참석 기관 간 의견 교환도 Q&A 형식으로 기록
   - Q와 A는 각각 별도 blockquote(>) 줄로 작성하며, Q와 A 사이에 반드시 빈 줄 1줄 삽입
   - 서로 다른 Q&A 블록 사이에도 반드시 빈 줄 1줄 삽입
   형식 예시:
   > **Q [나]** 질의 내용

   > **A [상대방 실명]** 답변 내용

   > **Q [나]** 다음 질의

   > **A [상대방 실명]** 다음 답변
5. 소제목 내용 구조화: 소제목 아래 내용은 나열식 서술 대신 **배경**, **주요 내용**, **합의** 등 굵은 소항목으로 구분하여 정리
6. 결정사항 명확화: 합의·결정·보류·재협의 여부를 명시

[전사 내용]
{text}

[출력 양식]
# 회의록

| 항목 | 내용 |
|------|------|
| 일 시 | {dt} |
| 장 소 | |
| 회의명 / 안건 | (녹취록에서 자동 식별) |
| 참 석 기 관 | (참석 기관 및 인원 자동 식별) |

| 작 성 자 | AI 자동 생성 |

---

## 회의 요약
(회의 목적, 주요 협의사항, 결론을 3줄 내외 경영진 보고 수준으로 요약. 문체는 "~음" 종결)

---

## 협의 내용

# 1. [안건 제목]

## 1.1 [소제목]

**배경**
(경위·맥락·수치 포함 서술. 문체는 "~음" 종결)

**주요 내용**
(핵심 협의 내용 서술)

> **Q [나]** (질의 내용)

> **A [상대방 실명]** (답변 내용)

> **Q [나]** (다음 질의)

> **A [상대방 실명]** (다음 답변)

## 1.2 [소제목]
(소제목 수에 따라 반복)

---

# 2. [안건 2 제목]
(안건 수에 따라 반복)

---
*본 회의록은 녹취 텍스트를 기반으로 AI가 자동 작성하였습니다.*

---
회의록 앱 자동 생성"""





# ── 요약 프롬프트 - 전화통화 메모 ──────────────────────
_SUMMARY_PHONE_TEMPLATE = """당신은 비즈니스 전화통화 내용을 간결하고 정확하게 정리하는 전문 기록자입니다.
아래 전사 내용은 전화통화 녹음입니다.
통화 목적과 핵심 내용을 주제별로 1~2줄 요약하고, 보충 설명은 Q&A 주석 형태로 추가하세요.

[화자 표기 기준]
- 발언 내용·자기소개·호칭·맥락을 파악하여 각 화자를 실명 또는 역할명으로 추정 표기 (예: [서동조 대표], [대표], [담당자])
- Antonio(대표이사, 회의 주체) 발언으로 판단되면 → [나]로 표기
- 추정 불가 시 → [화자1], [화자2] 순번 사용

[작성 원칙]
1. 팩트 기반: 대화에서 실제 나눈 내용에만 기초하여 작성. 녹취에 없는 내용 절대 추가 금지
2. Q&A 원칙: Q&A로 실제 오고간 내용만 기록. 임의 추정하여 내용 추가 금지
3. 사실 중심 기록: 녹취록에 명시된 내용만 기록
4. 데이터 정밀도: 수치·금액·일자는 정확히 기록. 불확실한 경우 (추정) 표기
5. 추측 금지: 녹취록에 없는 내용은 절대 추가하지 않음. 미확인 사항은 "미확인/미언급"으로 명시
6. 주제별 압축: 각 주제는 1~2줄 핵심 요약으로 서술
7. Q&A 주석: 각 주제 하단에 보충이 필요한 사항을 아래 형식으로 추가. 팩트 기반만 작성.
   Q와 A는 각각 별도 blockquote(>) 줄로 작성하며, Q와 A 사이에 반드시 빈 줄 1줄 삽입.
   다른 Q&A 블록 사이에도 반드시 빈 줄 1줄 삽입.
   > **Q [나]** (질문 내용)

   > **A [상대방]** (답변 내용)
6. 출처 명시: A 항목에는 가능한 한 발언자와 실제 발언 내용을 인용
7. 문체: 모든 서술 문장은 "~음" 종결 (예: "진행 중임", "완료함")

[전사 내용]
{text}

[출력 양식]
# 전화통화 메모

| 항목 | 내용 |
|------|------|
| 일 시 | {dt} |
| 상 대 방 | [이름 및 소속/직함] |
| 통화 목적 | [핵심 목적 한 줄] |
| 통화 당사자 | [나] ↔ [상대방] |

---

## 통화 내용 요약

(전체 통화를 2~3줄로 압축 요약. 문체는 "~음" 종결)

---

## 주요 내용

# 1. [첫 번째 주제명]

**현황**
(주제 핵심을 1~2줄로 압축 서술)

> **Q [나]** [보충 질문]

> **A [상대방]** [팩트 기반 답변 — 발언자 및 발언 내용 인용. 미확인 시 명시]

> **Q [나]** [추가 보충 질문 — 필요한 경우만]

> **A [상대방]** [답변]

---

# 2. [두 번째 주제명]

**현황**
(주제 핵심을 1~2줄로 압축 서술)

> **Q [나]** [보충 질문]

> **A [상대방]** [팩트 기반 답변]

(주제 수에 따라 반복)

---

*AI 자동 생성 — 회의녹음요약 앱 | STT 원문 기반 팩트 한정 작성*"""


# ── 요약 프롬프트 - 네트워킹(티타임) — 비공식 대화·티타임 ──────
_SUMMARY_FLOW_TEMPLATE = """당신은 비공식 비즈니스 네트워킹 대화를 정확하게 정리하는 전문 기록자입니다.
아래 전사 내용은 티타임·비공식 미팅·네트워킹 자리에서 오간 대화입니다.
주제별로 핵심을 1~2줄로 요약하고, 보충 설명이 필요한 부분은 Q&A 주석 형태로 추가하세요.

[화자 표기 기준]
- 발언 내용·자기소개·호칭·맥락을 파악하여 각 화자를 실명 또는 역할명으로 추정 표기 (예: [김상무], [대표], [담당자])
- Antonio(대표이사, 회의 주체) 발언으로 판단되면 → [나]로 표기
- 추정 불가 시 → [화자1], [화자2] 순번 사용

[작성 원칙]
1. 팩트 기반: 대화에서 실제 나눈 내용에만 기초하여 작성. 녹취에 없는 내용 절대 추가 금지
2. Q&A 원칙: Q&A로 실제 오고간 내용만 기록. 임의 추정하여 내용 추가 금지
3. 사실 중심 기록: 녹취록에 명시된 내용만 기록
4. 데이터 정밀도: 수치·금액·일자는 정확히 기록. 불확실한 경우 (추정) 표기
5. 추측 금지: 녹취록에 없는 내용은 절대 추가하지 않음. 확인되지 않은 사항은 "미확인/미언급"으로 명시
6. 주제별 압축: 각 주제는 1~2줄 핵심 요약으로 서술
7. Q&A 주석: 각 주제 하단에 보충이 필요한 사항을 아래 형식으로 추가. 팩트 기반 내용만 작성.
   Q와 A는 각각 별도 blockquote(>) 줄로 작성하며, Q와 A 사이에 반드시 빈 줄 1줄 삽입.
   다른 Q&A 블록 사이에도 반드시 빈 줄 1줄 삽입.
   > **Q [나]** (질문 내용)

   > **A [상대방]** (답변 내용)
6. 출처 명시: A 항목에는 가능한 한 발언자와 실제 발언 내용을 인용
7. 소제목 내용 구조화: 소제목 아래 내용은 나열식 서술 대신 **현황**, **주요 내용** 등 굵은 소항목으로 구분하여 정리
8. 문체: 모든 서술 문장은 "~음" 종결

[전사 내용]
{text}

[출력 양식]
# 네트워킹(티타임)

| 항목 | 내용 |
|------|------|
| 일 시 | {dt} |
| 장 소 | [장소 또는 미상] |
| 상 대 방 | [참석자] |
| 작 성 자 | AI 자동 생성 |

---

## 회의 요약
(전체 대화를 2~3줄로 압축 요약. 문체는 "~음" 종결)

---

## 주요 논의

# 1. [첫 번째 주제명]

## 1.1 [소제목]

**현황**
(주제 핵심을 1~2줄로 압축 서술)

**주요 내용**
(상세 내용 서술)

> **Q [나]** [보충 질문]

> **A [상대방]** [팩트 기반 답변 — 발언자 및 발언 내용 인용. 미확인 시 명시]

> **Q [나]** [추가 보충 질문 — 필요한 경우만]

> **A [상대방]** [답변]

---

# 2. [두 번째 주제명]

## 2.1 [소제목]

**현황**
(주제 핵심을 1~2줄로 압축 서술)

**주요 내용**
(상세 내용 서술)

> **Q [나]** [보충 질문]

> **A [상대방]** [팩트 기반 답변]

(주제 수에 따라 반복)

---

*AI 자동 생성 — 회의녹음요약 앱 | STT 원문 기반 팩트 한정 작성*"""


_SUMMARY_LECTURE_MD_TEMPLATE = """당신은 전문 강의 노트 작성자입니다.
아래 [강의 녹취록]을 분석하여 강의를 듣지 않은 사람도 내용을 완전히 이해할 수 있도록
상세하고 구조화된 마크다운 강의 요약문을 작성해주세요.

반드시 아래 녹취록의 실제 내용만을 바탕으로 작성하고, 임의로 내용을 추가하거나 가상의 시나리오를 작성하지 마세요.
강의 주제에 따라 맥락에 맞는 용어를 사용하세요(신앙/종교 강의라면 신앙 용어, 업무/실무 강의라면 전문 용어).

[작성 규칙]
1. 이모지 사용 금지 — 헤더 및 본문 전체에 이모지를 사용하지 않습니다.
2. 서술형 문장 종결 — 모든 서술 문장은 "~임", "~함", "~됨", "~있음" 형태로 마무리합니다.
   예) "성령의 인도를 따르는 교회의 새로운 삶의 방식임." / "이를 통해 신뢰가 형성됨."
3. 너무 요약하지 말 것 — 강의의 모든 주요 내용과 사례, 예시, 근거를 충분히 서술합니다.
4. 소제목(Bold sub-label) 적용 기준:
   - 한 섹션 내에 성격이 뚜렷이 다른 하위 항목이 2개 이상일 때만 **굵은 소제목**을 사용합니다.
   - 단일 흐름으로 연결되는 내용은 소제목 없이 서술형 단락으로 작성합니다.
5. 번호 섹션 구성 — 강의 흐름에 따라 소주제별로 ## 번호. 소주제명 형식으로 구성합니다.
6. Q&A 포함 — 강의 중 질의응답이 있는 경우 해당 섹션 하단에 아래 형식으로 정리합니다.
   Q와 A는 각각 별도 blockquote(>) 줄로 작성하고, 사이에 빈 줄 1줄 삽입합니다.
   > **[Q]** (질문 내용)

   > **[A]** (답변 내용)

[강의 녹취록]
{text}

[작성 양식]
생성 일시: {dt}

# 강의 요약 노트

| 항목 | 내용 |
|------|------|
| 일 시 | (녹취록에서 파악한 날짜·시간, 없으면 생략) |
| 강의명 | (강의 제목 또는 회차 정보) |
| 주 제 | (핵심 주제 한 줄 요약) |
| 대 상 | (수강 대상, 파악 가능한 경우) |

---

## 강의 핵심 요약

1. (핵심 내용 1 — 한 문장)
2. (핵심 내용 2 — 한 문장)
3. (핵심 내용 3 — 한 문장)

---

## 1. (소주제명)

(해당 소주제의 내용을 상세하게 서술. 하위 항목이 2개 이상이고 성격이 다를 때만 아래처럼 굵은 소제목 사용)

**소제목 예시 (해당 시에만 사용)**
내용 서술...

## 2. (소주제명)

(소주제 수에 따라 반복)

---

## Q&A 정리 (강의 중 질의응답이 있는 경우에만 작성)

> **[Q]** (질문 내용)

> **[A]** (답변 내용)

---

## 핵심 개념 정리 (주요 용어나 개념이 있을 경우에만 작성)

| 용어 | 의미 |
|------|------|
| (용어1) | (설명) |
| (용어2) | (설명) |

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
    marker = "회의록 앱 자동 생성"
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
              custom_instruction: str = "",
              company_name: str = "",
              prev_notes: str = "") -> tuple:
    """STT 텍스트 → 회의록 요약"""
    if not api_key:
        return False, "Gemini API 키가 없습니다."
    if not stt_text.strip():
        return False, "변환된 텍스트가 비어 있습니다."

    if summary_mode == "lecture_md":
        template = _SUMMARY_LECTURE_MD_TEMPLATE
    elif summary_mode == "flow":
        template = _SUMMARY_FLOW_TEMPLATE
    elif summary_mode == "phone":
        template = _SUMMARY_PHONE_TEMPLATE
    else:
        # 기본: 회의록 (topic)
        template = _SUMMARY_TOPIC_TEMPLATE
    try:
        client = _client(api_key)
        if progress_cb: progress_cb(10)
        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        innoforest_text = ""

        prompt = template.format(
            text=stt_text[:500000],  # gemini-2.5-flash 컨텍스트 한도(1M토큰) 내 최대 활용
            dt=datetime.now().strftime("%Y년 %m월 %d일 %H:%M"),
            innoforest=innoforest_text,
        )

        # 이전 회의록 비교 분석 주입 (IR 모드 및 일반 모드 공통 지원)
        if prev_notes and prev_notes.strip():
            prompt += f"""

---
## [이전 회의록 비교 분석 지시사항]

아래에 이전 미팅에서 작성된 회의록 파일들이 첨부되어 있습니다.
이전 회의록과 이번 회의 내용을 비교하여, 회의록 맨 뒤에 다음 형식의 비교 테이블을 반드시 추가하십시오:

---
## 🔄 이전 미팅 대비 변경사항

| 구분 | 이전 미팅 내용 | 이번 미팅 내용 | 비고 |
|------|--------------|--------------|------|
| (항목) | (이전 내용) | (이번 내용) | [이전 미팅내용과 상이] |

- 이전 미팅과 동일한 내용은 테이블에서 생략
- 변경/추가/철회된 내용만 기재
- 비고 컬럼: 상이 시 `[이전 미팅내용과 상이]`, 신규 확인 시 `[신규]`, 철회 시 `[철회]`
- 이전 회의록이 여러 개인 경우 가장 최근 것 기준으로 비교하고, 출처 파일명을 명시

### 첨부된 이전 회의록:
{prev_notes[:200000]}
"""

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
