# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**회의녹음요약 (PC 데스크톱 버전)** — 윈도우용 회의 녹음·STT·AI 요약 통합 데스크톱 앱.

- **GitHub (origin, 사설)**: `antonio103first/meeting-recording-minute-app`
- **GitHub (public, 배포용)**: `antonio103first/meeting-recording-for-pc-app`
- **현재 버전**: v3.0.5
- **연관 모바일 앱**: `회의녹음요약(모바일)/meeting-recording-mobile/` (별도 Android 프로젝트)

## 핵심 기능

- 음성 녹음 (MP3) + Gemini STT 변환
- 7개 AI 요약 양식 + 1개 신규(컨퍼런스) → **총 8개 양식**
- AI 엔진: Gemini / Claude / ChatGPT 선택 (`gemini_service.py`, `claude_service.py`, ChatGPT 인라인)
- 로컬 저장 + Google Drive 자동 업로드 + Obsidian 볼트 자동 저장 (3중 저장)
- 혁신의숲 API 연동 (IR 미팅 모드 전용)
- 이전 회의록 비교 분석 (IR 모드 / 일반 모드 공통)
- DB 기반 회의 목록 관리 (4탭: 녹음 / STT / 요약 / 전체)

## 디렉토리 구조

```
회의녹음요약/
├── app_dist/               # 메인 소스 (배포·개발 공용)
│   ├── main.py             # Tkinter UI + 파이프라인 (4000+ lines)
│   ├── gemini_service.py   # Gemini STT + 요약 (4개 템플릿 코드화)
│   ├── claude_service.py   # Claude API 요약
│   ├── google_drive.py     # Drive 업로드
│   ├── file_manager.py
│   ├── database.py         # SQLite 회의록 DB
│   └── config.py           # 경로·모델 상수
├── dist_배포(태윤)/         # 배포본(가공) — 외부 사용자용
├── ffmpeg_bundle/          # 번들 ffmpeg.exe
├── build_dist.bat          # 메인 빌드 스크립트 (Drive 미포함)
├── build_taeyun.bat        # 태윤 배포본 빌드
├── 회의녹음요약_회의록템플릿.md      # 프롬프트 전집 (캐노니컬 — v3.2)
├── 회의녹음요약_모바일_프롬프트.md    # 모바일 앱용 프롬프트(부분)
├── 회의녹음요약 메뉴얼 v3.0.pdf       # 사용자 매뉴얼
└── 회의녹음요약 v3.0.3 설치 및 사용 매뉴얼.html
```

## 회의록 양식 (8종) — `summary_mode` 키

| 모드 키 | 양식명 | 용도 | 캐노니컬 위치 |
|---------|--------|------|--------------|
| `speaker` | 주간회의록 | K-Run 파트너 주간회의 (4인 화자코드) | 템플릿.md 양식 1 |
| `topic` | 다자간 협의 | 기관협의·주주총회·다자간 공식회의 | 템플릿.md 양식 2 + `_SUMMARY_TOPIC_TEMPLATE` |
| `formal_md` | 회의록(업무) | 투자업체·포트폴리오사 사후관리 | 템플릿.md 양식 3 |
| `ir_md` | IR 미팅회의록 | 피투자사 IR (혁신의숲 + 펀드적합성) | 템플릿.md 양식 4 |
| `flow` | 네트워킹(티타임) | 비공식 미팅·네트워킹 | 템플릿.md 양식 5 + `_SUMMARY_FLOW_TEMPLATE` |
| `phone` | 전화통화 메모 | 전화통화 녹음 | 템플릿.md 양식 6 + `_SUMMARY_PHONE_TEMPLATE` |
| `lecture_md` | 강의 요약 | 업무·신앙 강의 | 템플릿.md 양식 7 + `_SUMMARY_LECTURE_MD_TEMPLATE` |
| `conference` | 컨퍼런스/간담회 | 다수 발표자 행사·세미나·라운드테이블 (v3.2 신설) | 템플릿.md 양식 8 |

> ⚠️ **코드/문서 sync 주의**: `gemini_service.py`에는 5개 템플릿(`TOPIC`, `PHONE`, `FLOW`, `LECTURE_MD`, `CONFERENCE`)이 코드화되어 있음. `ir_md`, `formal_md`, `speaker` 모드는 현재 `_SUMMARY_TOPIC_TEMPLATE`로 fall-through 처리됨. 신규 모드 코드 반영 필요 시 `summarize()` dispatcher elif 분기 + 신규 `_SUMMARY_*_TEMPLATE` 변수 추가.

> ⚠️ **claude_service.py 기존 버그**: `_get_template()`에서 `_SUMMARY_SPEAKER_TEMPLATE`, `_SUMMARY_FORMAL_MD_TEMPLATE`, `_SUMMARY_FORMAL_TEXT_TEMPLATE` 등 존재하지 않는 템플릿을 import → Claude 엔진 선택 시 ImportError. 사용 시 수정 필요.

## 파일명 저장 규칙 (v3.0.3 통일)

**3개 저장처 모두 동일 포맷 적용**:
```
{회사명}_{YYYYMMDD}({모드명})
```
예) `서메어_20260504(IR미팅).md`, `테라릭스_20260504(업무미팅).md`, `20260504(주간회의).md`

| 저장처 | 함수 | 컨펌 다이얼로그 |
|---|---|---|
| 로컬 | `_make_default_name()` → `simpledialog.askstring` | ✅ |
| Google Drive | 로컬 파일명 그대로 업로드 | ✅ (로컬 컨펌 공유) |
| Obsidian | `_save_obsidian_note()` → `simpledialog.askstring` | ✅ |

**모드 라벨 매핑** (`_make_default_name`, `_save_obsidian_note` 양쪽 동일):
- topic→회의록 / formal_md→업무미팅 / ir_md→IR미팅 / flow→티타임
- phone→전화통화메모 / lecture_md→강의요약 / speaker→주간회의 / conference→컨퍼런스

## IR / 컨퍼런스 Q&A 규칙 (v3.2~v3.3 개정)

`ir_md` 와 `conference` 양식은 다른 양식과 **다른 줄간격 규칙** 적용:
- ❌ STT 원문 그대로 옮기지 말 것 → ✅ 핵심 의도를 1~2문장으로 **요약**
- ✅ 모든 Q&A 빠짐없이 전수 포착 (분량 짧아도 생략 금지)
- **Q와 A는 붙여 쓴다** (사이에 빈 줄 없음)
- **A와 다음 Q 사이에만 빈 줄 1줄**

```
> **Q [케이런]** 질의 핵심 요약
> **A [IR회사명]** 답변 핵심 요약

> **Q [케이런]** 다음 질의
> **A [IR회사명]** 다음 답변
```

> 다른 양식(`topic`, `formal_md`, `flow`, `phone`, `lecture_md`, `speaker`)은 종전 규칙 유지 (Q↔A 사이 빈 줄 1줄, Q&A 블록 간 빈 줄 1줄).

## 빌드 / 실행

### 개발 실행
```bash
cd app_dist
python main.py
```

### 배포 빌드 (PyInstaller)
```bash
# 메인 빌드 (Drive 포함)
build_dist.bat

# 태윤 배포본 (Drive 없음, FFmpeg 번들 포함)
build_taeyun.bat
```
- 출력: `dist/회의녹음요약.exe` 또는 `dist_배포(태윤)/`
- spec 파일: `회의녹음요약.spec`
- FFmpeg는 빌드 시 PATH에서 자동 탐색 → `ffmpeg_bundle/ffmpeg.exe`로 번들

### 의존성
```
pip install -r requirements.txt
```
주요: `google-genai`, `anthropic`, `openai`, `google-api-python-client`, `pydub`, `requests`

## 환경/설정

- **API 키 저장**: 사용자 SharedPreferences 격 → `config.py`의 SQLite/`config_store` (앱 내 설정 탭)
- **저장 경로 기본값**:
  - 로컬: `Documents/회의녹음요약/`
  - Obsidian 회의록 디렉토리: `C:\Users\anton\Documents\Obsidian_KRUN_Antonio\08_회의록`
  - Drive 폴더: 자동 생성 (`녹음파일`, `회의록(요약)`)

## Git 운영

```bash
# 사설 origin (개발 메인)
git push origin <branch>

# 공개 배포 미러
git push public master
```

- 커밋 메시지 prefix: `feat:` `fix:` `docs:` `refactor:` `chore:`
- 한국어 커밋 메시지 OK

## 버전 이력 (요약)

| 버전 | 주요 변경 |
|------|----------|
| v3.0 | 7개 요약 양식 정착 |
| v3.0.2 | 회의목록 4탭 개편 + 마크다운 뷰어 + 편집 저장 |
| v3.0.3 | IR Q&A 규칙 개편(STT 금지·전수 요약·Q/A 붙여쓰기) + 양식 8 컨퍼런스/간담회 신설 + 3중 저장처 파일명 포맷 통일(`{회사}_{YYYYMMDD}({모드})`) |
| v3.0.4 | 컨퍼런스 양식 코드 반영(`_SUMMARY_CONFERENCE_TEMPLATE`+dispatcher+UI 라디오) + TXT첨부 다이얼로그 높이 540→620 + 모든 라디오버튼 검은색 통일·★신규★ 마커 제거 |
| v3.0.5 | 컨퍼런스 Q&A 줄간격 IR과 동일 규칙 적용(Q/A 붙여쓰기·A↔Q만 줄간격) + Gemini 네트워크 오류 친절 메시지 추가(errno 11001 DNS 해석 실패·10060/10061 연결거부·SSL 오류 안내) |

## 관련 프로젝트 (참고)

- 모바일 앱: `회의녹음요약(모바일)/meeting-recording-mobile/` (Kotlin/Compose)
- Obsidian 자동화 허브: `C:\Users\anton\Documents\Obsidian_KRUN_Antonio\_automation\` (v2.17)
- 상세 컨텍스트: 상위 디렉토리 `Claude AI_Personal/CLAUDE.md`
