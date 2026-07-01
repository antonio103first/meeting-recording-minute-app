# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**회의녹음요약 (PC 데스크톱 버전)** — 윈도우용 회의 녹음·STT·AI 요약 통합 데스크톱 앱.

- **GitHub (origin, 사설)**: `antonio103first/meeting-recording-minute-app`
- **GitHub (public, 배포용)**: `antonio103first/meeting-recording-for-pc-app`
- **현재 버전**: v3.1.4
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

> ✅ **v3.1.3 sync 완료**: `gemini_service.py`에 **9개 양식 전부 코드화**됨(`SPEAKER`·`TOPIC`·`FORMAL_MD`·`IR_MD`·`PHONE`·`FLOW`·`LECTURE_MD`·`CONFERENCE`·`ORG`). 이전엔 `speaker`·`ir_md`가 `TOPIC`로 fall-through 됐으나 v3.1.3에서 모바일 텍스트를 이식하여 해소. `summarize()` dispatcher + `claude_service._get_template()` 모두 9개 분기 완비.

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

## Q&A 규칙 (v3.4 — 전 양식 통일)

**8개 양식 전체에 동일 규칙 적용**:
- ❌ STT 원문 그대로 옮기지 말 것 → ✅ 핵심 의도를 한·두 문장으로 **요약**
- ✅ 모든 Q&A 빠짐없이 포착 (분량 짧아도 생략 금지)
- **Q와 A는 붙여 쓴다** (사이에 빈 줄 없음)
- **A와 다음 Q 사이에만 빈 줄 1줄**

```
> **Q [화자]** 질의 핵심 요약
> **A [상대방]** 답변 핵심 요약

> **Q [화자]** 다음 질의
> **A [상대방]** 다음 답변
```

> 강의 양식(`lecture_md`)은 Q&A가 있을 경우에만 동일 규칙 적용 (강의 특성상 Q&A 없을 수 있음).

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
| v3.0.6 | 8개 전 양식 Q&A 규칙 통일 (TOPIC/PHONE/FLOW/LECTURE_MD/CONFERENCE 코드 + 회의록템플릿.md 양식 1~7) — STT 원문 금지·핵심 요약·Q/A 붙여쓰기·A↔Q만 줄간격 |
| v3.0.7 | 회의록(업무) `_SUMMARY_FORMAL_MD_TEMPLATE` 전용 코드화 (양식 3 Q&A 요약 규칙 포함) + Obsidian 자동저장 다이얼로그 제거(confirm=False, 결과 messagebox 표시) + 회의록 일시 녹음파일 생성시간 기준 통일(`dt_override`) + `claude_service` 임포트 오류 수정 |
| v3.0.8 | 파일 기본 저장명 포맷 변경: `{회사}_{YYYYMMDD}({모드})` → `{회사}_YYYYMMDD_모드` (괄호 제거, 언더스코어 구분) — PC 앱 + 모바일 앱(FileManager.kt) 동시 적용; Obsidian 저장명 로컬 저장명과 완전 일치 |
| v3.0.9 | 회의록(업무) `_SUMMARY_FORMAL_MD_TEMPLATE` 구조 전환: Q&A 나열 중심 → **주제·내용 중심 서술**이 기본, Q&A는 주요사항(핵심 쟁점·확인사항·중요 의사결정) 보완용으로만 선택적 사용. gemini_service.py + claude_service.py(import 자동반영) + 회의녹음요약_회의록템플릿.md 양식 3 동기화 |
| v3.1.4 | **STT 안정화(모바일 대응) + 회의록 STT 엔진 표기**: `main.py run_stt`에 ① **네트워크성 오류(abort/socket/timeout/ssl 등) 최대 3회 재시도**(backoff 3s/8s), ② **Clova 재시도 모두 실패 시 Gemini STT 자동 폴백**(PC Gemini는 이미 청크 전사라 긴 파일에 강함) 추가. 실제 성공 엔진을 `_pipeline_stt_engine_used`에 기록해 `_on_pipeline_summary_done`에서 **회의록 끝에 `*STT 엔진: …*` 표기**(폴백 반영). 데스크톱은 화면잠금 절전이 없고 기존 `_set_sleep_prevention`도 있어 WakeLock류는 불필요. 모바일 v3.7.20~22 대응. exe 재빌드 완료. Python 파싱 OK. |
| v3.1.3 | **프롬프트 통일 2단계 — PC 누락 양식 3종 신설(구조 통일 완료)**: PC가 `speaker`(주간회의)·`ir_md`(IR미팅)·`org`(본당/단체)를 고르면 실제로는 다자간협의가 나오던 결함 해소. 모바일 텍스트를 PC로 이식(port-safe 검증: stray 중괄호·`$`·백슬래시 0) → `_SUMMARY_SPEAKER_TEMPLATE`·`_SUMMARY_IR_MD_TEMPLATE`·`_SUMMARY_ORG_TEMPLATE` 추가. `gemini_service.summarize()` 디스패처 + `claude_service._get_template()` 9개 분기 완비. `main.py` 양식 라디오(설정·재요약 다이얼로그 2곳 + 파이프라인) + 파일명 라벨맵에 `org`(단체회의) 추가. 스모크 테스트(3종 `.format()` OK, 라우팅 OK) + **exe 재빌드** 완료. 문서 `회의록템플릿.md` 양식 9 추가. → **PC·모바일 9개 양식 구조 통일 완료.** |
| v3.1.2 | **프롬프트 통일 1단계 — 주체 표기 통일**: PC↔모바일 회의록 프롬프트 통일 작업 일부. PC `gemini_service.py`의 화자 주체 표기를 `[나]`(17곳)에서 **양식군별로 통일** — 다자간협의·회의록업무=`[케이런]`, 전화통화·네트워킹=`[Antonio]`. `(화자 N)` 병기 금지 규칙 추가, 푸터 `회의록 앱`→`회의녹음요약 앱` 통일. `[나]` 0개 확인·Python 파싱 OK. 모바일은 이미 양식군별 표기 + Q&A 임의생성 금지 규율 이식(모바일 v3.7.19). **남은 통일: PC에 주간회의·IR미팅·본당(org) 양식 신설 + main.py UI 배선 + exe 재빌드**(별도 작업). |
| v3.1.1 | **녹음 음량 자동 정규화(dynaudnorm)**: PC 녹음이 작게 담겨도 음성을 일정 크기로 끌어올리도록 `recorder.py`(app_dist + app 레거시 양쪽)의 WAV→MP3 ffmpeg 변환에 `-af dynaudnorm=f=300:m=15:p=0.9:g=15` 추가. 모바일 v3.7.16(녹음 음량 근본 해결)과 동일 목적의 PC 대응 — 모바일은 음원 변경+소프트웨어 AGC, PC는 ffmpeg 동적 정규화. 실측: 조용한 샘플 -19.4dB→-7.9dB peak. |
| v3.1.0 | **회의록 요약 템플릿 정밀화 (전 양식 공통)**: `gemini_service.py`의 6개 코드 템플릿(TOPIC·PHONE·FLOW·LECTURE_MD·CONFERENCE·FORMAL_MD; speaker·ir_md는 TOPIC 공유)에 `[공통 정밀화 규칙]` 3종 삽입 — ① **사실 충실성**(녹취에 없는 회사명·숫자·인명 창작 금지, 불확실하면 비워 둠), ② **화자 분리 불신**(STT diarization이 한 화자로 몰리거나 오배정될 수 있으므로 화자 태그가 아닌 내용·문맥으로 판단, 불분명 시 `[불명확]`), ③ **STT 오인식 표기**(`*(STT 오인식 의심)*`). claude_service.py는 import 자동 반영. 캐노니컬 문서 `회의녹음요약_회의록템플릿.md` `## 공통 작성 원칙`에 6~8항 동기화(전 8양식 적용). 모바일 앱 v3.7.8과 동시 반영. 배경: 2인 티타임 녹음이 화자 분리 실패로 한 화자에 몰려 요약이 화자 귀속·Q&A를 추측으로 메우던 문제 |

## 관련 프로젝트 (참고)

- 모바일 앱: `회의녹음요약(모바일)/meeting-recording-mobile/` (Kotlin/Compose)
- Obsidian 자동화 허브: `C:\Users\anton\Documents\Obsidian_KRUN_Antonio\_automation\` (v2.17)
- 상세 컨텍스트: 상위 디렉토리 `Claude AI_Personal/CLAUDE.md`
