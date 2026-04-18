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
                f"[화자1], [화자2]"
                f"{', [화자3]' if num_speakers >= 3 else ''} 형식으로 구분\n")
    else:
        rule = "- 여러 화자는 [화자1], [화자2] 형식으로 구분\n"
    return _STT_PROMPT_TEMPLATE.format(speaker_rule=rule)


# ── 요약 프롬프트 - 주간회의 (화자 중심) ───────────────
_SUMMARY_SPEAKER_TEMPLATE = """당신은 벤처캐피탈(K-Run Ventures) 파트너 주간회의의 전문 회의록 작성자입니다.
아래 회의 전사 내용을 바탕으로 화자 중심의 한국어 회의록을 작성해주세요.

[화자 구분 코드 — 이름·호칭 기반 추정]
녹취록에 등장하는 이름, 호칭, 발언 패턴을 분석하여 아래 규칙으로 자동 매핑하세요.
- [K1]: 녹취록에서 "김진호", "김대표", "김진호대표" 등으로 호칭될 때 추정
- [K2]: 녹취록에서 "김정현", "대표님", "김정현대표" 등으로 호칭될 때 추정
- [K3]: 녹취록에서 "김신근", "김부사장", "신근", "김신근부사장" 등으로 호칭될 때 추정
- [S1]: 녹취록에서 "유환기", "심사역", "환기", "유심사역" 등으로 호칭될 때 추정
- 위 기준으로도 불명확한 경우: [불명확]으로 표기

※ 출력 시 대표이사, 부사장, 파트너 등 직함을 명시하지 말 것. 반드시 코드([K1], [K2], [K3], [S1])만 사용.

[작성 원칙]
1. 팩트 기반: 대화에서 실제 나눈 내용에만 기초하여 작성. 녹취에 없는 내용 절대 추가 금지
2. 주제 중심 구조: 화자 중심이 아니라 주제(회사·프로젝트·일정·우선순위) 중심으로 구성
3. 간략·명확·서술형: 주제별 내용은 서술형 문장으로 간략하고 명확하게 요약
4. 화자 코드 표기: 발언 화자는 [K1]/[K2]/[K3]/[S1] 코드로 표기. 직함·역할명 기재 금지
5. 데이터 정밀도: 수치·금액·일자 정확히 기록. 불확실한 경우 (추정) 표기
6. Q&A 원칙: 실제 질의응답 내용만 기록. 임의 추정하여 내용 추가 금지
7. Q&A 포착: 주제별 보고 중 다른 참석자의 질의·코멘트 전수 기록

[Q&A 형식]
> **Q [코드]** 질의 내용

> **A [코드]** 답변 내용

[전사 내용]
{text}

[회의록 출력 양식]
# 주간회의록
생성 일시: {dt}

---

## 주요 내용

### [주제명] (회사명·프로젝트명·일정·우선순위 기준으로 구분)

[K?] [해당 주제에 대한 보고·협의 내용을 서술형으로 간략 요약]

> **Q [K?]** (질의 내용)

> **A [K?]** (답변 내용)

### [주제명]

[K?] [내용 서술]

(주제 수에 따라 반복)

---
*본 회의록은 녹취 텍스트를 기반으로 AI가 자동 작성하였습니다. 수치·사실관계 확인이 필요한 사항은 추가 검토 바랍니다.*

---
회의녹음요약 앱 자동 생성"""

# ── 요약 프롬프트 - 다자간 협의 — 일반 외부미팅·기관협의·다자간 공식회의 ────
_SUMMARY_TOPIC_TEMPLATE = """당신은 전문 비즈니스 회의록 작성자입니다.
아래 회의 전사 내용은 기관 협의, 다자간 공식회의, 주주총회 등 복수의 이해관계자가 참석한 외부 미팅 녹취록입니다.
안건·주제 중심으로 구조화하여 공식 회의록 형식으로 작성해주세요.

[화자 표기 기준]
- K-Run Ventures 소속 참석자: [케이런]으로 통일 표기
- 외부 참석자: 실명·직함·소속으로 표기 (예: [원동연 대표], [IBK 심사역], [A기관 부장])
- 발언자 불명확한 경우: [불명확] 표기

[작성 원칙]
1. 팩트 기반: 대화에서 실제 나눈 내용에만 기초하여 작성. 녹취에 없는 내용 절대 추가 금지
2. 공식 회의록 기준: 안건별로 협의 내용, 각 기관 입장, 결정사항을 명확히 기록
3. 사실·팩트 중심: 녹취록에 명시된 수치·발언·결정만 기록. 추측·임의 추가 금지. 불확실한 수치는 (추정) 표기
4. 상세 서술 원칙: 핵심 논의 내용은 배경·경위·수치·결론을 포함하여 충분히 상세하게 서술. 지나친 압축 금지
5. Q&A 원칙: Q&A로 실제 오고간 내용만 기록. 임의 추정하여 내용 추가 금지
6. Q&A 포착 원칙 — 발표자 외 모든 참석자의 질의·코멘트를 빠짐없이 기록:
   - 발표자(주 발언자)의 설명에 대해 다른 참석자(케이런 포함)가 질문하거나 의견을 낸 모든 교환을 Q&A로 기록
   - 참석 기관 간 의견 교환도 Q&A 형식으로 기록
   - Q와 A는 각각 별도 blockquote(>) 줄로 작성하며, Q와 A 사이에 반드시 빈 줄 1줄 삽입
   - 서로 다른 Q&A 블록 사이에도 반드시 빈 줄 1줄 삽입
   형식 예시:
   > **Q [케이런]** 질의 내용

   > **A [상대방 실명]** 답변 내용

   > **Q [케이런]** 다음 질의

   > **A [상대방 실명]** 다음 답변
5. 소제목 내용 구조화: 소제목 아래 내용은 나열식 서술 대신 **배경**, **주요 내용**, **합의** 등 굵은 소항목으로 구분하여 정리
6. 결정사항 명확화: 합의·결정·보류·재협의 여부를 명시

[전사 내용]
{text}

[출력 양식]
# 다자간 협의

| 항목 | 내용 |
|------|------|
| 일 시 | {dt} |
| 장 소 | |
| 회의명 / 안건 | (녹취록에서 자동 식별) |
| 참 석 기 관 | (참석 기관 및 인원 자동 식별) |
| 케이런 참석자 | [케이런] |
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

> **Q [케이런]** (질의 내용)

> **A [상대방 실명]** (답변 내용)

> **Q [케이런]** (다음 질의)

> **A [상대방 실명]** (다음 답변)

## 1.2 [소제목]
(소제목 수에 따라 반복)

---

# 2. [안건 2 제목]
(안건 수에 따라 반복)

---
*본 회의록은 녹취 텍스트를 기반으로 AI가 자동 작성하였습니다.*

---
회의녹음요약 앱 자동 생성"""


# ── 요약 프롬프트 - 회의록(업무) — 투자업체 사후관리 외부 미팅 ────────
_SUMMARY_FORMAL_MD_TEMPLATE = """당신은 벤처캐피탈(K-Run Ventures)의 전문 투자사후관리 회의록 작성자입니다.
아래 회의 전사 내용은 투자업체 또는 포트폴리오사와의 외부 미팅 녹취록입니다.
투자 집행 이후 사후관리 목적의 업무 협의(경영현황 보고, 추가 지원 협의, 이슈 점검, 상장·Exit 전략 논의 등)에 특화하여 회의록을 작성합니다.

[화자 표기 기준]
- K-Run Ventures 소속 참석자: [케이런]으로 통일 표기
- 투자업체(포트폴리오사) 참석자: 역할 또는 이름으로 표기 (예: [대표], [CFO], [담당자])
- 불명확한 경우: [불명확]으로 표기

[작성 원칙]
1. 팩트 기반: 대화에서 실제 나눈 내용에만 기초하여 작성. 녹취에 없는 내용 절대 추가 금지
2. Q&A 원칙: Q&A로 실제 오고간 내용만 기록. 임의 추정하여 내용 추가 금지
3. 전수 포착 원칙: 녹취록에서 논의된 모든 주제를 빠짐없이 대제목(#)으로 분류하여 작성. 분량이 작거나 부수적으로 언급된 내용도 생략하지 않음
4. 사실 중심 기록: 녹취록에 명시된 내용만 기록. 임의 추가·추론 금지
5. 데이터 정밀도: 매출·수치·일자·인명·기관명을 정확히 기록. 불확실한 경우 (추정) 표기
6. 포착 필수 주제 (아래 항목이 녹취에서 언급된 경우 반드시 별도 대제목으로 작성):
   - 재무 실적: 매출, 영업손익, 현금흐름, 공헌이익, 일회성 비용 등
   - 사업 전략: 신사업, 기존 사업 고도화, 조직 개편, 비용 절감 등
   - 분기/월별 실적 트렌드: 직전 분기 또는 당해 분기 매출·손익 흐름
   - 상장(IPO) 추진 현황: 거래소 사전 협의, 주관사, 청구 일정, 거래소 피드백, 상장 요건
   - 투자·자금 조달: Pre-IPO, 후속 투자, 구주 매각, 밸류에이션, 투자사 펀드 만기 이슈
   - 케이런 펀드 관련: 만기·연장 현황, 회수 전략, 조합원 보고 사항
   - 주요 고객·파트너십: 계약 현황, 신규 계약, 해지·리스크
   - 인력·조직: 채용, 감원, 조직 개편, 핵심 인력 이슈
   - 기타 케이런이 질의한 모든 사항
7. Q&A 형식 필수 준수:
   - Q와 A는 각각 별도 blockquote(>) 줄로 작성하며, Q와 A 사이에 반드시 빈 줄 1줄 삽입
   - 서로 다른 Q&A 블록 사이에도 반드시 빈 줄 1줄 삽입
   형식 예시:
   > **Q [케이런]** (질의 내용)

   > **A [상대방]** (답변 내용)

   > **Q [케이런]** (다음 질의)

   > **A [상대방]** (다음 답변)
8. 소제목 내용 구조화: 소제목 아래 내용은 나열식 서술 대신 해당 소제목의 주요 내용 흐름에 맞는 굵은 소항목 레이블(예: **매출 구성**, **거래소 피드백**, **청구 요건** 등)로 구분하여 정리. 고정 구조 없이 내용에 따라 자유롭게 명명함
9. 문체: 모든 서술 문장은 "~음" 종결 (예: "진행 중임", "완료함", "검토 중임")

[전사 내용]
{text}

[출력 양식]
# 회의록(업무)

| 항목 | 내용 |
|------|------|
| 일 시 | {dt} |
| 장 소 | |
| 대 상 기 업 | (투자업체명 자동 식별) |
| 참 석 자 | [케이런] / (상대방 자동 식별) |
| 미팅 목적 | (사후관리 / 경영현황 점검 / 추가 지원 / 이슈 논의 / 후속 투자 협의 중 해당 항목) |
| 작 성 자 | AI 자동 생성 |

---

## 미팅 요약

**미팅 목적**
(이번 미팅의 주요 목적·배경을 1~2줄로 기술. 문체는 "~음" 종결)

**핵심 논의 내용**
(녹취에서 다뤄진 주요 주제를 항목별로 요약. 수치·결정사항 포함. 문체는 "~음" 종결)

**주요 결론 및 후속 조치**
(합의된 사항, 보류된 사항, 후속 액션이 있다면 간략히 기재. 문체는 "~음" 종결)

---

## 경영현황 점검

| 지표 | 내용 | 출처 (녹취 발언) |
|------|------|----------------|
| (매출 / ARR) | | |
| (현금 잔고 / 런웨이) | | |
| (인력 현황) | | |

※ 녹취록에서 언급된 수치만 기재. 미언급 항목은 행 자체를 생략. 각 수치는 화자의 실제 발언을 출처 컬럼에 인용.

---

## 주요 논의

※ 아래는 구조 예시임. 녹취에서 다뤄진 모든 주제를 대제목(#)으로 분류하여 빠짐없이 작성할 것.
※ 예시 주제: 재무 실적 점검 / 사업 전략 / 분기 실적 트렌드 / 상장(IPO) 추진 현황 / 투자·자금 조달 / 조직·인력 / 기타 논의사항

# 1. [주제명]

## 1.1 [소제목]

**[내용 흐름에 맞는 소항목 레이블 1]**
(해당 내용 서술. 문체는 "~음" 종결)

**[내용 흐름에 맞는 소항목 레이블 2]**
(해당 내용 서술)

> **Q [케이런]** (질의 내용)

> **A [상대방]** (답변 내용)

> **Q [케이런]** (다음 질의)

> **A [상대방]** (다음 답변)

## 1.2 [소제목]
(소제목 수에 따라 반복)

---

# 2. [주제명]
(주제 수에 따라 반복. 녹취에서 논의된 주제 수만큼 대제목을 생성할 것)

---
*본 회의록은 녹취 텍스트를 기반으로 AI가 자동 작성하였습니다.*

---
회의녹음요약 앱 자동 생성"""


# 하위 호환용 alias
_SUMMARY_FORMAL_TEMPLATE = _SUMMARY_FORMAL_MD_TEMPLATE


# ── 혁신의숲 API ────────────────────────────────────────
_INNOFOREST_LOGIN_URL    = "https://live-api.innoforest.co.kr/leaf/users/v1/login"
# 검색 URL: 두 도메인 모두 시도 (서버 라우팅 차이 대응)
_INNOFOREST_SEARCH_URLS  = [
    "https://liveapi.innoforest.co.kr/seed/search/v1/findcorp",   # 하이픈 없음 (1순위)
    "https://live-api.innoforest.co.kr/seed/search/v1/findcorp",  # 하이픈 있음  (폴백)
]
_INNOFOREST_BASE_URL     = "https://live-api.innoforest.co.kr/corporations/v1"
_INNOFOREST_CREDENTIALS  = {"username": "krunventures@krunventures.com", "password": "krun1028@"}
_INNOFOREST_HEADERS_BASE = {"Origin": "https://www.innoforest.co.kr",
                             "Referer": "https://www.innoforest.co.kr/"}

# JWT 캐시 (모듈 레벨 — 프로세스 내 재사용, 만료 시 재로그인)
_innoforest_jwt_cache: dict = {"token": "", "expires_at": 0.0}


def _innoforest_login(requests_mod) -> str:
    """혁신의숲 로그인 → JWT 반환. 1시간 캐시 재사용."""
    import time
    now = time.time()
    if _innoforest_jwt_cache["token"] and _innoforest_jwt_cache["expires_at"] > now + 60:
        return _innoforest_jwt_cache["token"]

    r = requests_mod.post(
        _INNOFOREST_LOGIN_URL,
        json=_INNOFOREST_CREDENTIALS,
        headers=_INNOFOREST_HEADERS_BASE,
        timeout=15,
    )
    r.raise_for_status()
    jwt = r.json().get("jwt", "") or r.json().get("token", "")
    if not jwt:
        raise RuntimeError("혁신의숲 로그인 실패 — JWT 없음 (자격증명 확인 필요)")

    _innoforest_jwt_cache["token"]      = jwt
    _innoforest_jwt_cache["expires_at"] = now + 3600  # 1시간 유효
    return jwt


def _innoforest_search(requests_mod, hdrs: dict, keyword: str, size: int = 5) -> list:
    """기업명 키워드로 혁신의숲 검색. 두 도메인 순차 시도."""
    for url in _INNOFOREST_SEARCH_URLS:
        try:
            r = requests_mod.get(
                url,
                params={"keyword": keyword, "page": 1, "size": size},
                headers=hdrs,
                timeout=15,
            )
            if r.status_code == 200:
                content = r.json().get("data", {}).get("content", [])
                if content:
                    return content
        except Exception:
            continue
    return []


def _best_corp_match(corps: list, company_name: str) -> dict | None:
    """검색 결과 중 법인명이 가장 유사한 기업 반환."""
    if not corps:
        return None
    name_lower = company_name.lower().replace(" ", "")
    scored = []
    for c in corps:
        corp_name = (c.get("corpName") or c.get("companyName") or "").lower().replace(" ", "")
        # 정확 일치
        if corp_name == name_lower:
            return c
        # 포함 관계 점수
        score = 0
        if name_lower in corp_name:
            score = len(name_lower) / max(len(corp_name), 1)
        elif corp_name in name_lower:
            score = len(corp_name) / max(len(name_lower), 1)
        # 공통 접두 길이
        prefix = 0
        for a, b in zip(name_lower, corp_name):
            if a == b:
                prefix += 1
            else:
                break
        score = max(score, prefix / max(len(name_lower), 1))
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    return best if best_score > 0.3 else corps[0]  # 최소 0.3 점 이상 or 첫 번째


def _build_search_keywords(company_name: str) -> list[str]:
    """법인명에서 멀티 검색 키워드 생성 (순서대로 시도).
    예) '주식회사 서메어' → ['서메어', '서메', '서'], '(주)솔리드뷰' → ['솔리드뷰', '솔리드']
    """
    import re as _re
    # 법인 형태 제거
    clean = _re.sub(r'(주식회사|유한회사|\(주\)|\(유\)|㈜)', '', company_name, flags=_re.IGNORECASE).strip()
    keywords = [clean] if clean != company_name else []
    keywords.insert(0, company_name)  # 원본 항상 1순위

    # 2글자 이상 단어 순서대로 추가 (부분 키워드 폴백)
    words = [w for w in _re.split(r'[\s\-_]+', clean) if len(w) >= 2]
    for w in words:
        if w not in keywords:
            keywords.append(w)

    # 앞 2글자 / 3글자 단축 키워드
    if len(clean) >= 4:
        keywords.append(clean[:3])
    if len(clean) >= 3:
        keywords.append(clean[:2])

    # 중복 제거 (순서 유지)
    seen = set()
    result = []
    for k in keywords:
        k = k.strip()
        if k and k not in seen:
            seen.add(k)
            result.append(k)
    return result


def fetch_innoforest_data(company_name: str) -> dict:
    """혁신의숲 API로 기업 투자유치·재무·기본정보 조회.
    반환: {"company_info": dict, "investments": list, "financials": list,
           "matched_name": str, "error": str|None}
    """
    try:
        import requests
    except ImportError:
        return {"error": "requests 패키지 미설치 (pip install requests)"}

    result = {
        "company_info": None, "investments": None,
        "financials": None, "matched_name": "", "error": None,
    }
    try:
        # 1) 로그인 → JWT (캐시 활용)
        jwt  = _innoforest_login(requests)
        hdrs = {**_INNOFOREST_HEADERS_BASE, "Authorization": f"Bearer {jwt}"}

        # 2) 멀티 키워드 검색 전략 — 첫 결과가 있으면 최적 매칭 선택
        keywords = _build_search_keywords(company_name)
        corps    = []
        used_keyword = ""
        for kw in keywords:
            corps = _innoforest_search(requests, hdrs, kw, size=5)
            if corps:
                used_keyword = kw
                break

        if not corps:
            # JWT 만료 가능성 → 강제 재로그인 후 1회 재시도
            _innoforest_jwt_cache["expires_at"] = 0.0
            jwt  = _innoforest_login(requests)
            hdrs = {**_INNOFOREST_HEADERS_BASE, "Authorization": f"Bearer {jwt}"}
            corps = _innoforest_search(requests, hdrs, keywords[0], size=5)

        if not corps:
            result["error"] = f"혁신의숲 미등록: '{company_name}' (키워드 {keywords[:3]} 모두 결과 없음)"
            return result

        best  = _best_corp_match(corps, company_name)
        corp_id    = best.get("cpCode") or best.get("corpCode") or best.get("id", "")
        corp_name  = best.get("corpName") or best.get("companyName") or company_name
        if not corp_id:
            result["error"] = "기업 ID(CP코드) 획득 실패"
            return result
        result["matched_name"] = corp_name

        # 3) 기업 기본정보 (설립일·대표자·소재지·직원 수)
        r = requests.get(f"{_INNOFOREST_BASE_URL}/{corp_id}/summary/similar",
                         headers=hdrs, timeout=15)
        if r.status_code == 200:
            result["company_info"] = r.json().get("data", {})

        # 4) 투자유치 현황 (라운드별 금액·밸류·투자사)
        r = requests.get(f"{_INNOFOREST_BASE_URL}/{corp_id}/investments/history",
                         headers=hdrs, timeout=15)
        if r.status_code == 200:
            result["investments"] = r.json().get("data", [])

        # 5) 재무현황 (NICE 기반: 매출·영업이익·순이익·직원 수)
        r = requests.get(f"{_INNOFOREST_BASE_URL}/{corp_id}/finances/nice-only",
                         headers=hdrs, timeout=15)
        if r.status_code == 200:
            result["financials"] = r.json().get("data", [])

    except Exception as e:
        result["error"] = f"혁신의숲 API 오류: {e}"

    return result


def format_innoforest_data(data: dict) -> str:
    """혁신의숲 조회 결과를 IR 템플릿 주입용 텍스트로 변환."""
    if not data or data.get("error"):
        msg = data.get("error", "조회 결과 없음") if data else "데이터 없음"
        return f"*(혁신의숲 {msg})*"

    matched = data.get("matched_name", "")
    header  = f"[혁신의숲 자동 조회 데이터] 매칭 법인명: {matched}" if matched else "[혁신의숲 자동 조회 데이터]"
    lines   = [header]

    info = data.get("company_info") or {}
    if info:
        lines.append(f"- 대표자: {info.get('ceoName') or info.get('representativeName') or '미확인'}")
        lines.append(f"- 설립일: {info.get('establishDate') or info.get('foundedDate') or '미확인'}")
        lines.append(f"- 소재지: {info.get('address') or info.get('location') or '미확인'}")
        emp = info.get('employeeCount') or info.get('employees')
        lines.append(f"- 직원 수: {emp if emp else '미확인'}명" if emp else "- 직원 수: 미확인")

    investments = data.get("investments") or []
    if investments:
        lines.append("- 투자유치 현황:")
        for inv in investments[:6]:
            rnd   = inv.get("roundName")  or inv.get("round", "")
            amt   = inv.get("investAmount") or inv.get("amount", "")
            val   = inv.get("postValuation") or inv.get("valuation", "")
            invst = inv.get("investorNames") or inv.get("investors", "")
            val_str = f" / 기업가치 {val}억원" if val else ""
            lines.append(f"  · {rnd}: {amt}억원{val_str} — {invst}")
    else:
        lines.append("- 투자유치 현황: 미등록")

    financials = data.get("financials") or []
    if financials:
        lines.append("- 재무현황 (NICE):")
        for fin in financials[:3]:
            yr  = fin.get("year",  "")
            rev = fin.get("revenue") or fin.get("sales", "")
            op  = fin.get("operatingProfit") or fin.get("operatingIncome", "")
            net = fin.get("netIncome") or fin.get("netProfit", "")
            emp = fin.get("employeeCount") or fin.get("employees", "")
            parts = []
            if rev: parts.append(f"매출 {rev}억원")
            if op:  parts.append(f"영업이익 {op}억원")
            if net: parts.append(f"순이익 {net}억원")
            if emp: parts.append(f"직원 {emp}명")
            lines.append(f"  · {yr}년: {' / '.join(parts) if parts else '정보 없음'}")
    else:
        lines.append("- 재무현황: 미등록")

    return "\n".join(lines)


# ── 요약 프롬프트 - IR 미팅회의록 ────────────────────────
_SUMMARY_IR_TEMPLATE = """당신은 벤처캐피탈 K-Run Ventures의 전문 IR 미팅 노트 작성자임.
아래 전사 내용은 피투자사와의 IR 미팅 녹취록임.

■ 이 노트의 핵심 목적: 실제 질의응답을 통해서만 확인할 수 있었던 정보·뉘앙스·판단 근거를 기록하는 것임.

[서술 원칙 — 전체 문서에 적용]
- 모든 서술 문장은 "~임", "~함", "~됨", "~있음" 형태로 마무리함
  예) "매출 구조는 SaaS 기반 구독 모델임." / "대표가 직접 확인함." / "구체 답변이 불가한 것으로 확인됨."
- 발언 인용은 "~라고 설명함", "~고 강조함", "~임을 인정함" 형태로 기술함
- "우수하다", "유망하다" 등 주관적 형용사 사용 금지

[화자 표기 기준]
- K-Run Ventures 소속 참석자(심사역·파트너·대표이사 등): [케이런]으로 통일 표기
- 피투자사 대표이사: 녹취록에서 파악한 회사명 또는 대표 역할로 [IR회사명]으로 표기
  예) 회사명이 "어썸"이면 → [어썸], "솔리드뷰"이면 → [솔리드뷰]
  ※ 회사명 확인 불가 시 [대표]로 표기
- 그 외 피투자사 참석자: 역할명 (예: [CTO], [CFO])
- 불명확한 경우: [불명확]

[정보 출처 태그]
- *(혁신의숲)*: 혁신의숲 API 자동 조회 데이터
- *(추정)*: 녹취록·자료에 명시되지 않아 추정한 내용 (반드시 표시)

[Q&A 밀도 원칙 — 필수]
- 각 아젠다 섹션에 최소 2~3개의 실제 Q&A를 인라인 배치해야 함
- 녹취록에서 [케이런]이 질문하고 [IR회사명]이 답변한 모든 유의미한 교환을 빠짐없이 포착
- Q&A는 반드시 아래 형식으로 작성함. Q와 A는 각각 별도 줄로 작성하고, Q&A 블록 사이에는 반드시 빈 줄 1줄을 삽입하여 각 Q&A를 시각적으로 구분함:

  > **Q [케이런]** 질의 내용을 한 문장으로 서술

  > **A [IR회사명]** 답변 내용 서술. (추정 내용이 있는 경우에만 (추정) 표기)

  > **Q [케이런]** 다음 질의

  > **A [IR회사명]** 다음 답변

- 특히 기록해야 할 항목:
  a. 케이런이 반복 질문하거나 추궁한 지점: 투자 판단에 크리티컬한 이슈
  b. IR회사가 회피하거나 못 답한 질문: [답변 회피] 또는 [구체 답변 불가]로 명시
  c. 추정한 내용은 반드시 (추정) 표기

[3대 핵심 분석 축 — 각 축에서 "미팅에서 새로 확인된 것"과 "IR에 이미 있던 것" 반드시 구분]
1. 기술 경쟁력: 경쟁사 기술 비교(최소 3~5개사), 해당 기업만의 차별점 vs 범용 기술, 기술 해자 냉정 평가
   → 미팅에서 경쟁사 대비 우위를 물었을 때 대표가 어떻게 답했는지가 핵심
2. 사업 경쟁력: 고객 lock-in 구조, 파이프라인 확정성, 매출 구조(단가×수량 분해), 리커링 비중, 해외 확장성
   → 매출 달성 근거·고객 계약 상태를 물었을 때의 답변이 핵심
3. 시장 크기: TAM/SAM/SOM, 시장 성장률(CAGR), "이 회사가 실제로 먹을 수 있는 규모"를 단가×수량으로 역산
   → "시장이 크다"는 IR Deck 주장을 그대로 옮기지 말고 실제 먹을 수 있는 규모를 냉정하게 역산할 것

[작성 원칙]
1. 팩트 기반: 대화에서 실제 나눈 내용에만 기초하여 작성. 녹취에 없는 내용 절대 추가 금지
2. Q&A 원칙: Q&A로 실제 오고간 내용만 기록. 임의 추정하여 내용 추가 금지
3. 외부자료 인용 허용: 시장자료·용어정리·기술적 설명 등 외부 자료 인용 가능. 단, 인용 시 반드시 출처 명시
   형식: *(출처: [출처명])* 예) *(출처: Gartner 2024)*, *(출처: Wikipedia)*, *(출처: 업계 일반)*
4. 사실 중심: 녹취록에 명시된 내용만 기록. 불분명한 부분은 [불명확] 표기
5. 데이터 정밀도: 수치·금액·일자 정확히 기록. 불확실하거나 추정한 경우 반드시 (추정) 표기
6. 전문 용어: 첫 출현 시 괄호 안에 설명 추가. 예) EPM(Electro Permanent Magnet, 전자영구자석)
7. STT 오인식: 기업명·인명이 어색하면 *(STT 오인식 의심)* 표기 후 IR 자료와 대조
8. IR 자료 vs 녹취록 수치 불일치: IR 자료 우선 채택 + *(녹취록 "X" → IR 자료 기준 "Y" 교정)* 주석

[기술 분석 프레임 — 핵심 기술 1~2개에 적용]
아래 6개 항목으로 구분하여 분석. 외부 자료 인용 시 반드시 출처 명시.

(1) 회사 의견: 미팅에서 회사가 직접 밝힌 기술·사업에 대한 주장 및 설명 (녹취록 기반)
(2) 기술 경쟁력: 해당 기술의 실질적 난이도, 차별점, 독자 개발 여부 vs 범용 기술 여부
    *(출처: [외부자료 인용 시 명시])*
(3) 시장 경쟁력: 고객 lock-in 구조, 매출 구조(단가×수량), 리커링 비중, 파이프라인 확정성
(4) 경쟁사 분석: 주요 경쟁사 3~5개사 비교. 정보 확인 불가 항목은 셀에 "해당없음" 또는 "확인불가" 기재. 경쟁사가 전혀 없는 경우 테이블 대신 "경쟁사 없음 — 해당없음" 단순 표기
    *(출처: [외부자료 인용 시 명시])*
(5) 시장 예상 규모: TAM/SAM/SOM, 이 회사가 실제로 달성 가능한 규모를 단가×수량으로 역산
    *(출처: [외부자료 인용 시 명시])*
(6) 결론: 투자 관점에서의 핵심 판단 — 기술 해자 강도(구조적/시간우위/약함), 투자 매력도 요약

[펀드 적합성 Quick Check — 기업 개요 테이블의 펀드 적합성 행에 반영]
아래 4가지 항목을 평가하여 기업 개요 테이블에 기재함:
1. 섹터 적합성: 핵심 제품·기술이 모빌리티·물류·교통·에너지 분야에 해당하는지 판정 → ★☆☆☆☆~★★★★★
2. 규약 해당:
   - 모태(국토교통): 국토·교통·건설·철도·항공·물류 등 인프라 관련 산업 → 🟢 해당 / △ 확장 해석 / ❌ 미해당
   - IBK(모빌리티): 모빌리티·자동차·부품·센서·소프트웨어 관련 → 🟢 / △ / ❌
   - KDB(남부권): 부산·울산·경남·광주·전남·전북 소재 또는 해당 지역 전략산업 → 🟢 / △ / ❌
3. 지역: 본사·연구소 소재지 → 남부권(동남권: 부산·울산·경남 / 서남권: 광주·전남·전북) 여부
4. 투자 유형 판정:
   - 주목적 적격: 출자자 투자의무에 직접 해당 (IBK/모태/KDB 중 🟢 1개 이상)
   - 비목적 가능: 주목적 미해당, 약정총액 30% 한도 내 비목적 투자 가능
   - 부적합: 펀드 규약상 투자 근거 없음

[혁신의숲 데이터]
{innoforest}
※ 혁신의숲 데이터와 녹취록·IR 자료 수치가 다를 경우: 대표가 직접 언급한 수치를 우선하고
   *(혁신의숲 "X" vs IR Deck "Y" vs 대표 발언 "Z" — 대표 발언 기준)* 형태로 교차 주석 처리할 것

[STT 녹취록]
{text}

[출력 양식]
생성 일시: {dt}

# IR 미팅회의록

---

## 기업 개요

| 항목 | 내용 |
|------|------|
| 기업명 | |
| 섹터 | |
| 투자 단계 | |
| 소재지 | (혁신의숲 데이터 우선 반영, 미등록 시 녹취록 기준) |
| 설립 | (혁신의숲 데이터 우선 반영) |
| 직원 수 | (혁신의숲 데이터 우선 반영) |
| 참석자 (회사) | |
| 참석자 (케이런) | |
| 미팅 일시 | |
| **펀드 적합성** | ★☆☆☆☆ (1/5) — **주목적 적격 / 비목적 가능 / 부적합** |
| 　· 섹터 매칭 | [매칭 섹터 — 직접 매칭 / 밸류체인 / 확장 해석] |
| 　· 지역 | [소재지] (남부권 🟢/❌) |
| 　· 규약 해당 | 모태(국토교통) 🟢/△/❌ · IBK(모빌리티) 🟢/△/❌ · KDB(남부권) 🟢/△/❌ |

---

## 1. 사업 개요

(비즈니스 모델, 핵심 제품·서비스, 수익 구조, 주요 양산 실적을 상세히 기술. 단가×수량 역산 포함.)

> **Q [케이런]** (질의 내용)

> **A [IR회사명]** (답변 내용)

(Q&A 최소 2~3개. Q/A는 각각 별도 blockquote 줄, 각 Q&A 블록 사이 빈 줄 1줄로 구분)

---

## 2. 팀

| 이름 | 역할 | 경력 |
|------|------|------|
| | | |

(팀 정보가 부족하면 서술형으로 작성)

---

## 3. 기술 및 제품

| 제품명 | 유형 | 핵심 역할 | 적용처 |
|--------|------|----------|--------|
| | | | |

> **[핵심 기술명] — 기술 분석**

**(1) 회사 의견**
(미팅에서 회사가 직접 밝힌 기술 주장 및 설명 — 녹취록 기반)

**(2) 기술 경쟁력**
(실질적 난이도, 차별점, 독자 개발 여부 서술. 외부자료 인용 시 출처 명시)
*(출처: )*

**(3) 시장 경쟁력**
(고객 lock-in, 매출 구조, 파이프라인 확정성)

**(4) 경쟁사 분석**

| 구분 | 당사 | 경쟁사A | 경쟁사B | 경쟁사C |
|------|------|---------|---------|---------|
| 핵심 기술 | | | | |
| 성능 지표 | | | | |
| 가격 | | | | |
| 양산 실적 | | | | |

*(확인 불가 항목: 해당없음 / 확인불가 기재. 경쟁사 없는 경우: 해당없음)*
*(출처: )*

**(5) 시장 예상 규모**
(TAM/SAM/SOM, 단가×수량 역산. 외부자료 인용 시 출처 명시)
*(출처: )*

**(6) 결론**
(기술 해자 강도 판정 및 투자 매력도 요약)

> **Q [케이런]** (기술 관련 질의)

> **A [IR회사명]** (기술 관련 답변)

(Q&A 최소 2~3개. Q/A 각각 별도 blockquote 줄, 각 Q&A 사이 빈 줄 1줄)

---

## 4. 파트너십 및 고객

(주요 고객사, 계약 구조, 파이프라인 확정성 분석. 매출 단가×수량 분해 포함.)

파이프라인 확정성 분류:
- **확정**: [고객명] — [계약 현황]
- **높은 확률**: [고객명] — [근거]
- **미확정**: [고객명] — [상태]

> **Q [케이런]** (고객·계약 관련 질의)

> **A [IR회사명]** (답변)

(Q&A 최소 2~3개. Q/A 각각 별도 blockquote 줄, 각 Q&A 사이 빈 줄 1줄)

---

## 5. 재무 및 펀딩

**[데이터 우선순위 원칙]**
- 1순위: IR 자료(Deck·사업계획서) — 회사가 공식 제출한 수치
- 2순위: 녹취록 대표 발언 — 미팅에서 직접 언급한 수치
- 3순위: 혁신의숲 API 자동 조회 — 공개 등기·공시 데이터로 보완
- 출처 표기 규칙: IR 자료만 있으면 *(IR 자료)*, 혁신의숲으로 보완한 항목은 *(혁신의숲)*, 수치 불일치 시 *(IR "X" vs 혁신의숲 "Y" — IR 자료 기준)* 형태로 교차 주석 처리

### 5-1. 재무 현황

| 연도 | 매출 (억원) | 영업이익 (억원) | 순이익 (억원) | 직원 수 | 주요 이벤트 |
|------|------------|---------------|-------------|--------|------------|
| | | *(IR 자료)* | *(IR 자료)* | *(혁신의숲)* | |

*(IR 자료 수치 우선 기재. 혁신의숲 데이터로 보완한 항목은 셀 내 *(혁신의숲)* 태그 명시.
수치 불일치 시 해당 셀 하단에 *(IR "X" vs 혁신의숲 "Y" — IR 자료 기준 채택)* 주석 추가)*

### 5-2. 펀딩 현황

| 라운드 | 금액 (억원) | 기업가치 (억원) | 투자사 | 일시 |
|--------|-----------|--------------|--------|------|
| | *(IR 자료)* | *(IR 자료)* | *(IR 자료 / 혁신의숲)* | *(IR 자료 / 혁신의숲)* |

*(혁신의숲에만 있는 투자 이력은 *(혁신의숲)* 태그로 별도 행에 추가. IR 자료와 혁신의숲 투자 이력 불일치 시 교차 주석 처리)*

| 항목 | 내용 |
|------|------|
| 금번 모집 목표 | (IR 자료 기준) *(IR 자료)* |
| 밸류에이션 | (IR 자료 기준. 혁신의숲 데이터 비교 가능 시 병기) *(IR 자료 / 혁신의숲)* |
| 기투자사 팔로온 여부 | (미팅 발언 또는 IR 자료 기준) |

---

## 6. 핵심 논의 포인트

**최소 3~5개 논점 수록 필수. 딜 브레이커급 이슈뿐 아니라 투자 판단에 유의미한 모든 공방을 논점 단위로 정리.**
**Q&A 중 해당 아젠다 섹션에 자연스럽게 녹아드는 일반 질의응답은 각 섹션에 인라인 배치. 이 섹션에 중복 기재하지 않음.**

논점 선정 기준:
① 케이런이 반복 질문하거나 추궁한 지점
② IR회사가 회피하거나 구체 답변을 못한 질문 — [답변 회피] / [구체 답변 불가] 명시
③ IR Deck 주장이 미팅에서 반박·약화된 지점
④ IR Deck에 없는 새로운 정보를 IR회사가 공개한 지점
⑤ 밸류에이션·딜 구조·펀딩 현황에 관한 논의

### [논점 제목]
- **논의 내용**:

  > **Q [케이런]** 질의 또는 반론 내용을 한 문장으로 서술.

  > **A [IR회사명]** 답변 내용 서술. ([답변 회피] / [구체 답변 불가] 해당 시 명시)

  (케이런이 반론 제기 시 빈 줄 후 추가: **[케이런 반론]** 반론 내용)
  ※ 논점 내에서 Q&A가 연속될 경우 각 Q&A 블록 사이 빈 줄 1줄로 구분

- **투자 검토 포인트**: 이 논의가 투자 판단에 어떤 영향을 미치는지 서술. 미해소 시 후속 확인 방법 명시.

---

## 합의 사항
- [합의 사항 1]
- [합의 사항 2]

---

## 액션 아이템

| 담당 | 내용 | 기한 |
|------|------|------|
| 회사 | | |
| 케이런 | | |

---

## 투자 관점 초기 메모
*(녹취록·혁신의숲 데이터 기반 — 투자자 시점의 초기 판단)*

**투자 매력도 스코어링 (녹취록 기반 초기 판단)**

| 항목 | 점수 (1~10) | 근거 |
|------|:-----------:|------|
| 기술 경쟁력 | | |
| 사업 경쟁력 (고객 견인) | | |
| 시장 크기 | | |
| 팀 역량 | | |
| 재무·펀딩 상태 | | |
| 리스크 수준 | | |
| **종합 (가중 평균)** | | |

**[긍정 시그널]**
- (미팅에서 확인된 강점·차별점)

**[우려 사항]**
- (미해소 리스크·[답변 회피] 항목·IR Deck 주장 중 검증 안 된 것)

**[추가 확인 필요]**
- (다음 미팅 또는 실사에서 반드시 확인해야 할 사항)

---
*본 회의록은 STT 녹취 텍스트 및 혁신의숲 자동 조회 데이터를 기반으로 AI가 자동 작성하였음. 사실관계 확인이 필요한 사항은 추가 검토 바람.*

---
회의녹음요약 앱 자동 생성"""


# ── 요약 프롬프트 - 전화통화 메모 ──────────────────────
_SUMMARY_PHONE_TEMPLATE = """당신은 비즈니스 전화통화 내용을 간결하고 정확하게 정리하는 전문 기록자입니다.
아래 전사 내용은 전화통화 녹음입니다.
통화 목적과 핵심 내용을 주제별로 1~2줄 요약하고, 보충 설명은 Q&A 주석 형태로 추가하세요.

[화자 표기 기준]
- 녹취록에서 K-Run Ventures 대표이사(파트너, 회의 주체) 발언 → [Antonio]로 표기
- 그 외 K-Run Ventures 동석자 → [케이런]으로 표기
- 상대방 → 실명 또는 역할명 (예: [서동조 대표], [대표], [담당자])

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
   > **Q [케이런]** (질문 내용)

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
| 통화 당사자 | [케이런] ↔ [상대방] |

---

## 통화 내용 요약

(전체 통화를 2~3줄로 압축 요약. 문체는 "~음" 종결)

---

## 주요 내용

# 1. [첫 번째 주제명]

**현황**
(주제 핵심을 1~2줄로 압축 서술)

> **Q [케이런]** [보충 질문]

> **A [상대방]** [팩트 기반 답변 — 발언자 및 발언 내용 인용. 미확인 시 명시]

> **Q [케이런]** [추가 보충 질문 — 필요한 경우만]

> **A [상대방]** [답변]

---

# 2. [두 번째 주제명]

**현황**
(주제 핵심을 1~2줄로 압축 서술)

> **Q [케이런]** [보충 질문]

> **A [상대방]** [팩트 기반 답변]

(주제 수에 따라 반복)

---

*AI 자동 생성 — 회의녹음요약 앱 | STT 원문 기반 팩트 한정 작성*"""


# ── 요약 프롬프트 - 네트워킹(티타임) — 비공식 대화·티타임 ──────
_SUMMARY_FLOW_TEMPLATE = """당신은 비공식 비즈니스 네트워킹 대화를 정확하게 정리하는 전문 기록자입니다.
아래 전사 내용은 티타임·비공식 미팅·네트워킹 자리에서 오간 대화입니다.
주제별로 핵심을 1~2줄로 요약하고, 보충 설명이 필요한 부분은 Q&A 주석 형태로 추가하세요.

[화자 표기 기준]
- 녹취록에서 K-Run Ventures 대표이사(파트너, 회의 주체) 발언 → [Antonio]로 표기
- 그 외 K-Run Ventures 동석자 → [케이런]으로 표기
- 상대방 → 실명 또는 역할명 (예: [김상무], [대표], [담당자])

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
   > **Q [케이런]** (질문 내용)

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

> **Q [케이런]** [보충 질문]

> **A [상대방]** [팩트 기반 답변 — 발언자 및 발언 내용 인용. 미확인 시 명시]

> **Q [케이런]** [추가 보충 질문 — 필요한 경우만]

> **A [상대방]** [답변]

---

# 2. [두 번째 주제명]

## 2.1 [소제목]

**현황**
(주제 핵심을 1~2줄로 압축 서술)

**주요 내용**
(상세 내용 서술)

> **Q [케이런]** [보충 질문]

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
6. Q&A 주석 불필요 — 강의 양식이므로 Q&A 방식의 주석은 작성하지 않습니다.

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
              custom_instruction: str = "",
              company_name: str = "",
              prev_notes: str = "") -> tuple:
    """STT 텍스트 → 회의록 요약"""
    if not api_key:
        return False, "Gemini API 키가 없습니다."
    if not stt_text.strip():
        return False, "변환된 텍스트가 비어 있습니다."

    if summary_mode == "topic":
        template = _SUMMARY_TOPIC_TEMPLATE
    elif summary_mode in ("formal_md", "official", "formal_text", "formal"):
        # v3: 공식양식(텍스트) 폐지 → 전부 업무협의록(MD)로 통합
        template = _SUMMARY_FORMAL_MD_TEMPLATE
    elif summary_mode == "ir_md":
        template = _SUMMARY_IR_TEMPLATE
    elif summary_mode == "lecture_md":
        template = _SUMMARY_LECTURE_MD_TEMPLATE
    elif summary_mode == "flow":
        template = _SUMMARY_FLOW_TEMPLATE
    elif summary_mode == "phone":
        template = _SUMMARY_PHONE_TEMPLATE
    else:
        template = _SUMMARY_SPEAKER_TEMPLATE
    try:
        client = _client(api_key)
        if progress_cb: progress_cb(10)
        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        # IR 미팅 모드: 혁신의숲 API 조회
        if summary_mode == "ir_md" and company_name.strip():
            if progress_cb: progress_cb(15)
            innoforest_data = fetch_innoforest_data(company_name.strip())
            innoforest_text = format_innoforest_data(innoforest_data)
        else:
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
