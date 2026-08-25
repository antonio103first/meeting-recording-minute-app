# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**Roundtable** (구 회의녹음요약, PC 데스크톱) — 윈도우용 **회의 녹음·STT·AI 요약 + 예비검토보고서** 통합 앱.

- **GitHub (origin, 사설)**: `antonio103first/meeting-recording-minute-app`
- **GitHub (public, 배포용)**: `antonio103first/meeting-recording-for-pc-app`
- **현재 버전**: v4.0.1 (2026-08-25 본당 프롬프트 성당형식화 + Q&A 대화체 전면 폐지 + STT 반복루프 수정 + 요약방식 UI 이동)
- **연관 모바일 앱**: `회의녹음요약(모바일)/meeting-recording-mobile/` (별도 Android 프로젝트)

> ⚠️ **개명은 표시명·exe명에만 적용한다.** 저장 경로(`~/회의녹음요약_데이터`, `recording_dir`),
> Drive 폴더명(`drive_folder_name`), 설정 키는 **그대로 두어야** 기존 녹음·회의록·연동이 끊기지 않는다.

## 핵심 기능

- 음성 녹음 (MP3) + Gemini STT 변환
- 7개 AI 요약 양식 + 1개 신규(컨퍼런스) → **총 8개 양식**
- AI 엔진: Gemini / Claude / ChatGPT 선택 (`gemini_service.py`, `claude_service.py`, ChatGPT 인라인)
- 로컬 저장 + Google Drive 자동 업로드 + Obsidian 볼트 자동 저장 (3중 저장)
- 혁신의숲 API 연동 (IR 미팅 모드 전용)
- 이전 회의록 비교 분석 (IR 모드 / 일반 모드 공통)
- DB 기반 회의 목록 관리 (4탭: 녹음 / STT / 요약 / 전체)
- ⭐ **예비검토보고서 자동 생성** (v4.0.0) — IR 자료(PDF/PPTX/이미지) 선택 → 보고서 → Obsidian 이중 저장

## 예비검토보고서 탭 (v4.0.0)

**엔진은 앱에 복사하지 않고 `Prescreening_Report` 저장소에서 런타임 로드**한다(SSOT 유지).
경로는 설정 탭 「예비검토 엔진 경로」에서 지정하며, 없으면 **탭 자체를 노출하지 않는다**.

| 모드 | 구현 | 품질(실측) | 소요 | 전제 |
|------|------|-----------|------|------|
| **엔진 모드**(기본) | Python 엔진(`engine/`), 판단은 Gemini 또는 `claude` CLI | 43,927~55,935자 · 인용 도메인 2종 | 5~15분 | 없음 |
| **스킬 모드** | `claude --print`로 `krun-prescreening-report` 스킬 원본 실행 | 65,244자(위더스 백지 생성) · 도메인 12종 · 확인필요 160건 | 7~40분 | Claude Code 설치 |

> 운용 방침: **평소엔 엔진 모드로 빠르게 초안**을 뽑고, 투심에 올릴 건처럼
> 품질이 필요할 때 스킬 모드로 올린다. 보고서 말미에 어느 모드로 생성했는지 표기된다
> (`*생성: Roundtable v4.0.0 · 엔진 모드(gemini) · YYYY-MM-DD*`).

- **둘 다 Claude 구독을 쓴다** — API 크레딧 불필요 (`PRESCREEN_CLAUDE_VIA=api`로만 API 사용)
- Claude Code 미설치 시 스킬 모드는 **차단**하고 안내(조용한 폴백 금지)
- **녹음 중 실행 시 경고** — 녹음은 복구 불가이므로 사용자가 그 자리에서 판단
- 저장: `00_Inbox/companies`(필수) + `08_회의록`(보관)
- 관련 문서: `docs/기획서_Roundtable_예비검토보고서탭.md`

## 디렉토리 구조

```
회의녹음요약/
├── app_dist/               # 메인 소스 (배포·개발 공용)
│   ├── main.py             # Tkinter UI + 파이프라인 (4000+ lines)
│   ├── prescreen_tab.py    # ⭐v4.0.0 예비검토보고서 탭 (엔진 런타임 로드·2모드)
│   ├── gemini_service.py   # Gemini STT + 요약 (4개 템플릿 코드화)
│   ├── claude_service.py   # Claude API 요약
│   ├── google_drive.py     # Drive 업로드
│   ├── file_manager.py
│   ├── database.py         # SQLite 회의록 DB
│   └── config.py           # 경로·모델 상수
├── docs/
│   └── 기획서_Roundtable_예비검토보고서탭.md   # ⭐v4.0.0 설계·실측·결함 이력
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
# 메인 빌드 (onedir — 기동 6초)
build_dist.bat

# 태윤 배포본 (Drive 없음, FFmpeg 번들 포함)
build_taeyun.bat
```
- 출력: `dist_배포/Roundtable/Roundtable.exe` (**폴더 전체가 필요**) + 바탕화면 바로가기 자동 생성
- **v4.0.0에서 onefile → onedir 전환**: onefile은 실행할 때마다 346MB(그중 ffmpeg 201MB = 58%)를
  임시폴더에 풀어 기동에 **30~90초**가 걸렸다. onedir은 압축 해제가 없어 **6.4초**(실측).
  대신 폴더 935MB·5,651개 파일이 되므로 배포는 폴더 통째로 전달한다.
  (태윤 배포본은 전달 편의를 위해 onefile 유지)
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
| **v4.0.1** | **본당(org) 프롬프트 성당 형식화 + 전 양식 Q&A 대화체 전면 폐지(V2.0) + STT 반복루프 방지 + 요약방식 UI 이동. PC·모바일 동시 적용.** ① **org 양식 재작성** — 실제 성당 상임위 회의록(`상임위_20260630_회의록.md`) 형식에 맞춰 `_SUMMARY_ORG_TEMPLATE`/모바일 `SUMMARY_ORG` 전면 개편: 표에서 장소 항목 제거, `## N. OO 보고 *(보고: 직책)*` 분과별 대제목, 하위 구획은 `###` 대신 굵은 라벨("6월 활동"·"건의 — 주제")로 구분, 회의 요약은 나열이 아닌 3~5문장 서술 문단, 마지막에 "폐회" 항목. ② **Q&A 대화 형식 전면 폐지(V2.0)** — 주간회의(speaker)·IR미팅(ir_md) 2종을 제외한 전 양식(다자간협의 topic·회의록업무 formal_md·강의요약 lecture_md·컨퍼런스 conference·전화통화메모 phone·티타임 flow·본당 org)에서 `Q [화자]`/`A [화자]` 대화체 나열을 금지하고 논의 내용을 서술 문단(필요 시 `**논의 및 확인사항**` 소라벨 또는 blockquote)으로 통합 — phone·flow는 이미 서술형이라 무변경. ③ **STT 반복루프 버그 수정** — PC `gemini_service.py`가 55분 분량 실제 회의를 "예." 반복만 19191자 출력하는 반복루프에 걸려 있던 것을 발견(모바일은 v3.7.6에서 이미 해결, PC엔 미반영 상태였음). `_is_degenerate()`로 반복 응답 감지 → 구간 분할(`_chunked_transcribe`, 청크 목표 10분 `_CHUNK_TARGET_MIN`으로 duration 기반 재계산) 자동 재시도 추가, STT temperature 0.1→0.4 상향(모바일 fix와 동일값), 청크 내 반복 감지 시 1회 재시도. ④ **요약방식 선택 UI 이동** — PC: 설정 탭 "🗂 기본 요약 방식" 카드 제거 → 녹음/변환 탭 "📂 파일 선택" 버튼 옆에 "🗂 {방식}" 버튼 신설(클릭 시 팝업, 선택 즉시 `_pipeline_sum_mode`+cfg 반영). 모바일: 설정 화면 "요약 방식" 라디오 카드 제거 → 녹음 화면 파일 선택 버튼 옆에 짧은 라벨 버튼 신설(`SummaryModeBottomSheet` 재사용), 재요약 시트의 방식별 설명문도 Q&A 문구 갱신. ⑤ **V1.0/V2.0 프롬프트 버저닝** — 개편 이전 9종 프롬프트 원문을 `docs/prompts_v1.0_baseline.md`에 전문 보존 + git 태그 `prompts-v1.0`(커밋 `ef015bc`)를 부착해 되돌릴 수 있게 함. 검증: PC `gemini_service.py`/`main.py` 문법 파싱 통과, 모바일 `./gradlew compileDebugKotlin` 성공(exit 0). **미해결**: PC exe 재빌드 미실시(소스 실행 시 즉시 반영, exe는 별도 빌드 필요), 실제 상임위 회의록(`상임위_20260825_회의록2`) 생성은 STT 처리 중(결과 미확인). |
| **v4.0.0** | **앱 개명 `회의녹음요약` → `Roundtable` + 예비검토보고서 탭 신설.** ① **탭 신설**(`prescreen_tab.py`) — IR 자료 선택 → 보고서 → Obsidian 이중 저장. 엔진은 `Prescreening_Report` 저장소에서 **런타임 로드**(앱에 복사하면 스킬 개선 시 두 벌이 갈라짐 — SSOT 유지), 엔진 없으면 **탭 미노출**. ② **2모드** — 스킬 모드(`claude --print`로 스킬 원본 실행, 100%·도메인 17종) / 엔진 모드(Python, 66~84%·도메인 2종). **둘 다 Claude 구독 사용**(API 크레딧 불필요). ③ **개명은 표시명·exe만** — 저장경로·Drive 폴더명·설정키 유지해 기존 데이터 보존. ④ **녹음 중 실행 경고** — 녹음은 복구 불가라 사용자가 판단. ⑤ 엔진 자산 신설: `engine/`(ir_reader·extractor·research·llm·valuation·skill_runner), PPT 차트 **원본 데이터 추출**(Vision 눈대중이 7,300→7,000 오독), DART **감사보고서 판독**(사업장·주주·RCPS·감사재무), **밸류에이션 역산**(Pre 320억/Post 490억 — 스킬 수치 재현). ⑥ **잡은 결함 8건**: 재무 type 불일치(13행 증발)·PPT 오독·`sys.executable`(exe가 자기 재실행)·**워커 스레드 tkinter 접근**(버튼 누르면 죽음)·`fund_use` 키 불일치·`_num` 파싱(밸류 0억원)·`gemini_research` 파싱 취약(§11 소실)·Claude `temperature` deprecated. **미해결**: 볼트에 테스트 산출물이 `KRUN/검토중/지엘켐` 폴더를 만들어 기존 `Antonio/검토중/지엘켐`과 갈라짐(정리 필요), 혁신의숲 엔드포인트 미확정, exe 내 탭 실동작 미검증. 문서 `docs/기획서_Roundtable_예비검토보고서탭.md` |
| v3.0 | 7개 요약 양식 정착 |
| v3.0.2 | 회의목록 4탭 개편 + 마크다운 뷰어 + 편집 저장 |
| v3.0.3 | IR Q&A 규칙 개편(STT 금지·전수 요약·Q/A 붙여쓰기) + 양식 8 컨퍼런스/간담회 신설 + 3중 저장처 파일명 포맷 통일(`{회사}_{YYYYMMDD}({모드})`) |
| v3.0.4 | 컨퍼런스 양식 코드 반영(`_SUMMARY_CONFERENCE_TEMPLATE`+dispatcher+UI 라디오) + TXT첨부 다이얼로그 높이 540→620 + 모든 라디오버튼 검은색 통일·★신규★ 마커 제거 |
| v3.0.5 | 컨퍼런스 Q&A 줄간격 IR과 동일 규칙 적용(Q/A 붙여쓰기·A↔Q만 줄간격) + Gemini 네트워크 오류 친절 메시지 추가(errno 11001 DNS 해석 실패·10060/10061 연결거부·SSL 오류 안내) |
| v3.0.6 | 8개 전 양식 Q&A 규칙 통일 (TOPIC/PHONE/FLOW/LECTURE_MD/CONFERENCE 코드 + 회의록템플릿.md 양식 1~7) — STT 원문 금지·핵심 요약·Q/A 붙여쓰기·A↔Q만 줄간격 |
| v3.0.7 | 회의록(업무) `_SUMMARY_FORMAL_MD_TEMPLATE` 전용 코드화 (양식 3 Q&A 요약 규칙 포함) + Obsidian 자동저장 다이얼로그 제거(confirm=False, 결과 messagebox 표시) + 회의록 일시 녹음파일 생성시간 기준 통일(`dt_override`) + `claude_service` 임포트 오류 수정 |
| v3.0.8 | 파일 기본 저장명 포맷 변경: `{회사}_{YYYYMMDD}({모드})` → `{회사}_YYYYMMDD_모드` (괄호 제거, 언더스코어 구분) — PC 앱 + 모바일 앱(FileManager.kt) 동시 적용; Obsidian 저장명 로컬 저장명과 완전 일치 |
| v3.0.9 | 회의록(업무) `_SUMMARY_FORMAL_MD_TEMPLATE` 구조 전환: Q&A 나열 중심 → **주제·내용 중심 서술**이 기본, Q&A는 주요사항(핵심 쟁점·확인사항·중요 의사결정) 보완용으로만 선택적 사용. gemini_service.py + claude_service.py(import 자동반영) + 회의녹음요약_회의록템플릿.md 양식 3 동기화 |
| v3.1.5 | **티타임(네트워킹) 요약 양식 개편 — 모바일과 동일 적용**: `_SUMMARY_FLOW_TEMPLATE`를 모바일 최신본과 **동일하게** 교체. 기존 `## 회의 요약 → 평면적 주제 나열(# 1, # 2 …) → Q&A 주석` 구조를, ① `## 한눈에`(자리 성격 2~3줄 + 핵심 굵게 1~3개), ② `## 주요 논의`를 **맥락 3그룹**(①상대방 사업·근황 ②케이런/본인 공유 ③사적 환담 — 실제 오간 그룹만, 없으면 생략), ③ `## 후속 / 메모`(체크박스, 없으면 생략)로 개편. Q&A 블록 제거. 화자 표기 `[Antonio]`/`[케이런]`/`[상대방]` 및 사실충실성·화자분리 불신·STT 오인식 `*(추정)*` 규칙은 유지. `claude_service.py`가 `_SUMMARY_FLOW_TEMPLATE` import → **claude 엔진 자동 반영**. `.format()` 스모크(text/dt 치환, `{text}`·`{dt}` 외 중괄호 0) + Python 파싱 OK. app_dist(배포 소스) + app(레거시) 동시 적용. ⚠️ **exe 재빌드는 별도**(소스 실행 시 즉시 반영). 실사례(듀셀 골프 티타임 재정리)로 사용자 승인한 양식. |
| v3.1.4 | **STT 안정화(모바일 대응) + 회의록 STT 엔진 표기**: `main.py run_stt`에 ① **네트워크성 오류(abort/socket/timeout/ssl 등) 최대 3회 재시도**(backoff 3s/8s), ② **Clova 재시도 모두 실패 시 Gemini STT 자동 폴백**(PC Gemini는 이미 청크 전사라 긴 파일에 강함) 추가. 실제 성공 엔진을 `_pipeline_stt_engine_used`에 기록해 `_on_pipeline_summary_done`에서 **회의록 끝에 `*STT 엔진: …*` 표기**(폴백 반영). 데스크톱은 화면잠금 절전이 없고 기존 `_set_sleep_prevention`도 있어 WakeLock류는 불필요. 모바일 v3.7.20~22 대응. exe 재빌드 완료. Python 파싱 OK. |
| v3.1.3 | **프롬프트 통일 2단계 — PC 누락 양식 3종 신설(구조 통일 완료)**: PC가 `speaker`(주간회의)·`ir_md`(IR미팅)·`org`(본당/단체)를 고르면 실제로는 다자간협의가 나오던 결함 해소. 모바일 텍스트를 PC로 이식(port-safe 검증: stray 중괄호·`$`·백슬래시 0) → `_SUMMARY_SPEAKER_TEMPLATE`·`_SUMMARY_IR_MD_TEMPLATE`·`_SUMMARY_ORG_TEMPLATE` 추가. `gemini_service.summarize()` 디스패처 + `claude_service._get_template()` 9개 분기 완비. `main.py` 양식 라디오(설정·재요약 다이얼로그 2곳 + 파이프라인) + 파일명 라벨맵에 `org`(단체회의) 추가. 스모크 테스트(3종 `.format()` OK, 라우팅 OK) + **exe 재빌드** 완료. 문서 `회의록템플릿.md` 양식 9 추가. → **PC·모바일 9개 양식 구조 통일 완료.** |
| v3.1.2 | **프롬프트 통일 1단계 — 주체 표기 통일**: PC↔모바일 회의록 프롬프트 통일 작업 일부. PC `gemini_service.py`의 화자 주체 표기를 `[나]`(17곳)에서 **양식군별로 통일** — 다자간협의·회의록업무=`[케이런]`, 전화통화·네트워킹=`[Antonio]`. `(화자 N)` 병기 금지 규칙 추가, 푸터 `회의록 앱`→`회의녹음요약 앱` 통일. `[나]` 0개 확인·Python 파싱 OK. 모바일은 이미 양식군별 표기 + Q&A 임의생성 금지 규율 이식(모바일 v3.7.19). **남은 통일: PC에 주간회의·IR미팅·본당(org) 양식 신설 + main.py UI 배선 + exe 재빌드**(별도 작업). |
| v3.1.1 | **녹음 음량 자동 정규화(dynaudnorm)**: PC 녹음이 작게 담겨도 음성을 일정 크기로 끌어올리도록 `recorder.py`(app_dist + app 레거시 양쪽)의 WAV→MP3 ffmpeg 변환에 `-af dynaudnorm=f=300:m=15:p=0.9:g=15` 추가. 모바일 v3.7.16(녹음 음량 근본 해결)과 동일 목적의 PC 대응 — 모바일은 음원 변경+소프트웨어 AGC, PC는 ffmpeg 동적 정규화. 실측: 조용한 샘플 -19.4dB→-7.9dB peak. |
| v3.1.0 | **회의록 요약 템플릿 정밀화 (전 양식 공통)**: `gemini_service.py`의 6개 코드 템플릿(TOPIC·PHONE·FLOW·LECTURE_MD·CONFERENCE·FORMAL_MD; speaker·ir_md는 TOPIC 공유)에 `[공통 정밀화 규칙]` 3종 삽입 — ① **사실 충실성**(녹취에 없는 회사명·숫자·인명 창작 금지, 불확실하면 비워 둠), ② **화자 분리 불신**(STT diarization이 한 화자로 몰리거나 오배정될 수 있으므로 화자 태그가 아닌 내용·문맥으로 판단, 불분명 시 `[불명확]`), ③ **STT 오인식 표기**(`*(STT 오인식 의심)*`). claude_service.py는 import 자동 반영. 캐노니컬 문서 `회의녹음요약_회의록템플릿.md` `## 공통 작성 원칙`에 6~8항 동기화(전 8양식 적용). 모바일 앱 v3.7.8과 동시 반영. 배경: 2인 티타임 녹음이 화자 분리 실패로 한 화자에 몰려 요약이 화자 귀속·Q&A를 추측으로 메우던 문제 |

## 관련 프로젝트 (참고)

- 모바일 앱: `회의녹음요약(모바일)/meeting-recording-mobile/` (Kotlin/Compose)
- Obsidian 자동화 허브: `C:\Users\anton\Documents\Obsidian_KRUN_Antonio\_automation\` (v2.17)
- 상세 컨텍스트: 상위 디렉토리 `Claude AI_Personal/CLAUDE.md`
