# 회의녹음요약 — 개발 히스토리

> 프로젝트: 회의녹음요약 (Meeting Recording & Summarizer)
> 관리: K-Run Ventures 대표이사실

---

## v2.0 (2026-03-22) — 현재 버전

### Phase 6: 앱 아이콘 변경 + 문서 정비

**변경 내용:**
- 앱 아이콘 변경: 마젠타(#CC00BB) 배경 + 흰색 문서 + 채팅 버블 디자인
- `make_icon.py` 추가: Pillow 기반 아이콘 생성 스크립트 (PNG + ICO 멀티 사이즈)
- `build.yml` 개선: 빌드 시 아이콘 자동 생성 스텝 추가
- `app_dist/main.py`, `app/main.py`: 윈도우 타이틀바 아이콘(`wm_iconbitmap`) 적용
- MANUAL.md, PLAN.md, HISTORY.md 문서 체계 정비 및 GitHub 배포

**빌드 이슈 및 해결:**
- 이슈: Windows 빌드 환경(cp1252 인코딩)에서 이모지(`✅`) 출력 시 `UnicodeEncodeError`
- 해결: `make_icon.py` print 문에서 이모지 제거, ASCII 텍스트로 대체

---

### Phase 5: CI/CD 자동 빌드 + SmartScreen 대응

**변경 내용:**
- `.github/workflows/build.yml` 신규 작성
  - Windows runner (`windows-latest`) 기반 PyInstaller EXE 빌드
  - ffmpeg 자동 설치 (Chocolatey)
  - PowerShell `New-SelfSignedCertificate`로 자체 서명 인증서 생성
  - `signtool sign`으로 EXE 서명 (K-Run Ventures 게시자명)
  - Artifact 업로드 (30일 보관): `회의녹음요약.exe` + `KRunVentures_인증서.cer`
  - `v*` 태그 push 시 GitHub Release 자동 생성
- MANUAL.md 작성: SmartScreen 차단 해제 4가지 방법 포함

**빌드 이슈 및 해결:**
- 이슈: `signtool verify /pa` 명령이 자체 서명 인증서에서 실패
- 해결: verify 명령을 파일 존재/크기 검증으로 교체

---

### Phase 4: Google Drive 폴더 동적 설정 + URL 파싱

**변경 내용:**
- `google_drive.py`: `parse_folder_id()` 함수 추가
  - Google Drive 전체 URL 입력 시 자동으로 폴더 ID 추출
  - `https://drive.google.com/drive/folders/{ID}?...` 형식 지원
  - 순수 ID 입력도 그대로 처리
- `google_drive.py`: `permissions().create()` 실패를 치명적 오류에서 제외
  - 기업용 Google Workspace 정책상 공개 권한 설정 실패는 무시
- `main.py`: Drive 폴더 ID 입력란에 URL 붙여넣기 후 자동 ID 추출 및 UI 갱신
- 에러 메시지 40자 제한 제거 → 전체 메시지 표시

**수정 배경:**
- 사용자가 Drive 폴더 URL 전체를 ID 입력란에 붙여넣는 상황 발생
- 기업 Workspace 환경에서 `permissions().create()` 403 오류로 업로드 실패

---

### Phase 3: CLOVA Speech Long API 전환

**변경 내용:**
- `clova_service.py` 전면 재작성
  - 기존: CSR API (`/recog/v1/stt`) + Client ID/Secret 헤더 + FFmpeg 청크 분할
  - 신규: Long API (`{invoke_url}/recognizer/upload`) + `X-CLOVASPEECH-API-KEY` 헤더
  - 파일 단일 업로드 방식 (청크 분할 제거 → 타임아웃 문제 근본 해결)
  - `diarization.enable: true`로 화자 분리 활성화
  - `_format_result()`: `[화자N] 발언내용` 형식 포맷터 구현
  - `test_connection()`: HTTP 400(인증OK+파라미터 누락)을 성공으로 처리
- `config.py`: `clova_client_id`/`clova_client_secret` → `clova_invoke_url`/`clova_secret_key` 변경
- `main.py` 설정 UI: "Client ID" / "Client Secret" 라벨 → "Invoke URL" / "Secret Key" 변경
- `main.py` STT 라우팅: `run_stt()` 함수에서 엔진 분기 처리

**수정 배경:**
- Gemini STT가 긴 녹음 파일(30분+)에서 타임아웃 반복 발생
- CLOVA Speech 설정 UI가 CSR API 기준(Client ID/Secret)으로 되어 있어 Long API 키 입력 불가
- 사용자가 NAVER 계정 이메일/비밀번호를 입력하는 혼란 발생

---

### Phase 2: Google Drive 연동 + 파일 관리

**변경 내용:**
- `google_drive.py` 신규 작성
  - Google Drive API v3 + OAuth2 인증 구현
  - `upload_file()`: MediaFileUpload로 MP3/TXT 파일 업로드
  - `ensure_folder()`: 이름 기반 폴더 검색 또는 자동 생성
  - `init_drive_folders()`: 녹음파일/회의록(요약) 폴더 일괄 생성
  - `upload_meeting_files()`: MP3 + 요약 TXT 쌍 업로드
- `main.py` 설정 탭: Drive 연결, OAuth JSON 등록, 폴더 생성 UI
- `config.py`: Drive 폴더 ID, 폴더명 설정 항목 추가
- `file_manager.py`: 로컬 파일 저장 경로 관리
- `database.py`: SQLite 회의 목록 DB 초기화 및 CRUD

**수정 배경:**
- 파일 업로드 실패 원인: `resumable=True` 불안정 → `resumable=False` 변경
- 폴더 ID를 코드에 하드코딩 → `config.json` 동적 관리로 전환

---

### Phase 1: 초기 프로토타입 (Gemini STT + 기본 GUI)

**구현 내용:**
- Python tkinter 3탭 GUI 구성 (녹음/변환, 회의목록, 설정)
- `recorder.py`: sounddevice 기반 실시간 녹음, MP3 저장
- `gemini_service.py`: Google Gemini API STT + 회의록 요약
- `claude_service.py`: Claude API 보조 요약 엔진
- `config.py`: config.json 기반 사용자 설정 영속화
- `database.py`: SQLite 회의 이력 관리
- 기본 파이프라인: 녹음 → STT → 화자명 변경 → 요약 → 로컬 저장

---

## 주요 기술 결정 이력

| 날짜 | 결정 사항 | 이유 |
|------|---------|------|
| 2026-03 | CLOVA Speech Long API 채택 | Gemini STT 장시간 파일 타임아웃 문제 해결 |
| 2026-03 | PyInstaller 단일 EXE 패키징 | 비개발자 배포 용이성 |
| 2026-03 | GitHub Actions CI/CD 도입 | EXE 자동 빌드 및 Artifact 배포 자동화 |
| 2026-03 | Google Drive API v3 채택 | 사내 Google Workspace 연동, 보안 OAuth2 |
| 2026-03 | SQLite 로컬 DB | 서버 의존성 없는 경량 히스토리 관리 |
| 2026-03 | 자체 서명 인증서 적용 | SmartScreen 게시자 표시 (평판 미등록) |

---

## 알려진 이슈 및 잔여 과제

| 이슈 | 상태 | 비고 |
|------|------|------|
| SmartScreen 완전 제거 | 미해결 | 상용 코드 서명 인증서($) 구매 필요 |
| 200MB 초과 파일 처리 | 미지원 | CLOVA Long API 제한 |
| Claude API STT 통합 | 예정 | `claude_service.py` 기반 구현 |
| Whisper 로컬 STT | 예정 | 오프라인 환경 대응 |
| 다국어(영어) 지원 | 예정 | CLOVA 언어 파라미터 변경으로 대응 가능 |

---

## Git 커밋 이력 요약

| 커밋 | 메시지 | 주요 변경 |
|------|--------|---------|
| `0395371` | fix: make_icon.py Windows cp1252 인코딩 오류 수정 | 이모지 제거 |
| `1939205` | fix: MANUAL.md, clova_service.py 복구 + 아이콘 변경 통합 | 누락 파일 복구 |
| `9cc8bf4` | feat: 앱 아이콘 변경 (마젠타 문서+채팅버블 디자인) | 아이콘 스크립트 추가 |
| `70b96fa` | fix: 누락 파일 복구 | 파일 누락 수정 |
| `2759e4b` | fix: Google Drive 폴더 URL 직접 붙여넣기 지원 | parse_folder_id 추가 |
| `b50f7d3` | fix: Google Drive 업로드 오류 수정 | permissions 비치명화 |
| `44b2349` | fix: CLOVA Speech API → Long API 전환 | clova_service 재작성 |
| `1489f1b` | docs: SmartScreen 차단 해제 4가지 방법 MANUAL.md 추가 | 문서 작성 |

---

*본 문서는 회의녹음요약 v2.0 기준으로 작성되었습니다.*
