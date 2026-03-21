# 회의녹음요약 — 개발 기획서

> 작성일: 2026-03-22 | 작성: K-Run Ventures 대표이사실
> 프로젝트명: 회의녹음요약 (Meeting Recording & Summarizer)
> 버전: v2.0

---

## 1. 기획 배경 및 목적

### 1.1 배경

K-Run Ventures는 투자심사·포트폴리오 관리·조합원 보고 등 다수의 내부 회의를 정기적으로 운영한다. 기존에는 회의 내용을 수기로 기록하거나 별도의 외부 서비스(Clova Note, Otter.ai 등)에 의존하여 아래와 같은 문제가 발생하였다.

- 회의록 작성에 소요되는 시간 과다 (회의 1시간 기준 약 30~60분 추가 소요)
- 외부 SaaS 서비스 사용 시 기밀 회의 내용의 외부 유출 리스크
- 다수 참석자의 발언이 뒤섞인 경우 화자 구분 불가
- 요약 형식 및 품질의 비일관성

### 1.2 목적

자체 AI 기반 회의 자동화 도구를 구축하여 다음을 달성한다.

- 회의록 작성 시간 **90% 단축** (수동 60분 → 자동화 5분 이내)
- 화자별 발언 분리 및 실명 매핑 자동화
- 사내 Google Drive 기반 체계적 문서 관리
- 외부 서비스 의존도 제거 및 데이터 보안 내재화

---

## 2. 서비스 개요

| 항목 | 내용 |
|------|------|
| 서비스명 | 회의녹음요약 |
| 유형 | Windows 데스크톱 애플리케이션 (단독 실행 EXE) |
| 대상 사용자 | K-Run Ventures 임직원 (非개발자 포함) |
| 배포 방식 | GitHub Actions 자동 빌드 → EXE 다운로드 |
| 데이터 저장 | 로컬 PC + Google Drive (선택) |
| 외부 의존 서비스 | NAVER CLOVA Speech, Google Gemini AI, Google Drive API |

---

## 3. 핵심 기능 요구사항

### 3.1 음성 입력

| 요구사항 | 세부 내용 |
|---------|---------|
| 실시간 녹음 | 마이크 장치 선택 → 녹음 시작/일시정지/중지 |
| 파일 업로드 | MP3, WAV, M4A, MP4, OGG, FLAC 지원 |
| 파일 크기 | 최대 200MB (CLOVA Speech 기준) |
| 출력 포맷 | MP3 자동 변환 저장 |

### 3.2 STT (Speech-to-Text) 변환

| 요구사항 | 세부 내용 |
|---------|---------|
| 한국어 특화 엔진 | NAVER CLOVA Speech Long API (1차 권장) |
| 보조 엔진 | Google Gemini (짧은 파일 또는 CLOVA 장애 시) |
| 화자 분리 | diarization 기반 화자1~8 자동 구분 |
| 화자 이름 매핑 | STT 완료 후 실명 입력 → 전체 텍스트 치환 |
| 타임아웃 대응 | CLOVA Long API 단일 업로드 방식 (최대 10분 대기) |

### 3.3 AI 요약

| 요구사항 | 세부 내용 |
|---------|---------|
| 요약 엔진 | Google Gemini 2.5 Flash |
| 요약 방식 | 화자 중심 / 주제 중심 선택 |
| 커스텀 프롬프트 | 사용자 정의 지시사항 입력 후 재요약 |
| 핵심 지표 추출 | 결정사항, 액션 아이템, 주요 수치 자동 추출 |

### 3.4 파일 관리

| 요구사항 | 세부 내용 |
|---------|---------|
| 로컬 저장 | MP3, STT 텍스트, 요약 텍스트 자동 저장 |
| 저장 경로 | `~/Documents/Meeting recording/` |
| DB 관리 | SQLite 기반 회의 목록 및 메타데이터 관리 |
| Drive 연동 | Google Drive API v3 (OAuth2) 자동 업로드 |
| 폴더 구조 | 녹음파일 폴더 / 회의록(요약) 폴더 분리 |

### 3.5 설정 관리

| 요구사항 | 세부 내용 |
|---------|---------|
| API 키 관리 | CLOVA Invoke URL + Secret Key, Gemini API Key |
| Drive 설정 | OAuth JSON 파일 등록, 폴더 ID 저장 |
| 엔진 선택 | STT 엔진 (CLOVA / Gemini) 전환 |
| 영속성 | `~/회의녹음요약_데이터/config.json` 저장 |

---

## 4. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                  GUI (tkinter)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ 녹음/변환 │  │ 회의목록  │  │      설정        │   │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
└───────┼─────────────┼──────────────────┼─────────────┘
        │             │                  │
        ▼             ▼                  ▼
┌───────────┐  ┌───────────┐   ┌──────────────────┐
│  recorder │  │ database  │   │     config       │
│ (sounddev)│  │ (SQLite)  │   │  (config.json)   │
└───────────┘  └───────────┘   └──────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│              Pipeline                     │
│  ┌──────────────┐   ┌──────────────────┐ │
│  │ clova_service│   │  gemini_service  │ │
│  │ (CLOVA STT)  │   │ (Gemini STT/요약)│ │
│  └──────────────┘   └──────────────────┘ │
│  ┌──────────────┐   ┌──────────────────┐ │
│  │ file_manager │   │  google_drive    │ │
│  │ (로컬 저장)  │   │ (Drive 업로드)   │ │
│  └──────────────┘   └──────────────────┘ │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│           External APIs                   │
│  NAVER CLOVA Speech Long API             │
│  Google Gemini 2.5 Flash                 │
│  Google Drive API v3                     │
└──────────────────────────────────────────┘
```

---

## 5. 기술 스택

| 분류 | 기술 | 선정 이유 |
|------|------|---------|
| 언어 | Python 3.10+ | 풍부한 AI/오디오 라이브러리 생태계 |
| GUI | tkinter | Python 기본 내장, 추가 설치 불필요 |
| STT (주) | NAVER CLOVA Speech Long API | 한국어 최고 수준 정확도, 장시간 파일 지원 |
| STT (보조) | Google Gemini | 간단한 API 구성, 단기 파일 처리 |
| 요약 AI | Google Gemini 2.5 Flash | 비용 효율적, 한국어 요약 품질 우수 |
| 오디오 | sounddevice, soundfile, ffmpeg | 크로스 포맷 지원, 실시간 스트리밍 |
| DB | SQLite | 로컬 경량 DB, 별도 서버 불필요 |
| Drive | Google Drive API v3 + OAuth2 | 사내 Google Workspace 연동 |
| 패키징 | PyInstaller (--onefile) | 단일 EXE 배포, Python 미설치 환경 지원 |
| CI/CD | GitHub Actions (Windows runner) | 자동 빌드 + Artifact 배포 |

---

## 6. 보안 설계

| 항목 | 설계 방침 |
|------|---------|
| API 키 저장 | 로컬 `config.json`에만 저장, Git 미포함 |
| OAuth 토큰 | 로컬 `token.json`에만 저장, Git 미포함 |
| 회의 내용 | 외부 서버 저장 없음 (API 처리 후 로컬/Drive에만 보관) |
| EXE 서명 | 자체 서명 인증서 (K-Run Ventures) 적용 |
| Git 보안 | `.gitignore`로 config.json, token.json, credentials.json 제외 |

---

## 7. 배포 전략

### 7.1 배포 흐름

```
개발자 Push (master 브랜치)
       ↓
GitHub Actions 자동 트리거
       ↓
Windows Runner (windows-latest)
├─ Python 3.11 설치
├─ 패키지 설치 (requirements.txt)
├─ Pillow로 앱 아이콘 생성
├─ ffmpeg 설치
├─ PyInstaller EXE 빌드
├─ 자체 서명 인증서 생성 및 서명
└─ Artifact 업로드 (30일 보관)
       ↓
사용자: Artifact 다운로드 → EXE 실행
```

### 7.2 SmartScreen 대응

자체 서명 인증서는 Microsoft 평판 DB에 등록되지 않아 SmartScreen이 경고를 표시한다. MANUAL.md에 4가지 해제 방법을 제공하여 非개발자도 쉽게 설치할 수 있도록 한다.

---

## 8. 개발 일정

| 단계 | 내용 | 상태 |
|------|------|------|
| Phase 1 | 기본 GUI + 녹음 + Gemini STT | ✅ 완료 |
| Phase 2 | Google Drive 연동 + 파일 관리 | ✅ 완료 |
| Phase 3 | CLOVA Speech Long API 전환 | ✅ 완료 |
| Phase 4 | Drive 폴더 동적 설정 + URL 파싱 | ✅ 완료 |
| Phase 5 | GitHub Actions CI/CD + EXE 자동 빌드 | ✅ 완료 |
| Phase 6 | 앱 아이콘 적용 + MANUAL.md 정비 | ✅ 완료 |
| Phase 7 | Claude API 보조 엔진 추가 (검토 중) | 🔄 예정 |

---

## 9. 향후 개선 방향

| 우선순위 | 항목 | 설명 |
|---------|------|------|
| 상 | 자동 실행 스케줄러 | 특정 시간 또는 파일 감지 시 자동 변환 |
| 상 | 다국어 지원 | 영어·일본어 회의 처리 |
| 중 | Whisper 로컬 STT | 인터넷 없는 환경 대응 |
| 중 | 회의록 템플릿 | 투자심사·이사회·팀미팅 등 양식별 출력 |
| 중 | 코드 서명 인증서 구매 | SmartScreen 경고 완전 제거 |
| 하 | 모바일 앱 연동 | iOS/Android 녹음 파일 자동 동기화 |

---

*본 기획서는 회의녹음요약 v2.0 기준으로 작성되었습니다.*
