# 🎙 회의녹음요약 (Meeting Recording & Summary)

> **Windows PC용 AI 회의록 자동 생성 앱** — 음성 녹음부터 STT 변환, AI 요약, PDF 저장, Google Drive 업로드까지 자동화

[![Version](https://img.shields.io/badge/version-3.0.3-blue.svg)](https://github.com/antonio103first/meeting-recording-for-pc-app/releases/latest)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)]()
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

---

## 📥 다운로드

**[⬇ 최신 버전 다운로드 (v3.0.3)](https://github.com/antonio103first/meeting-recording-for-pc-app/releases/latest)**

| 파일 | 설명 |
|------|------|
| `회의녹음요약.exe` | 앱 실행 파일 (Windows 64-bit) |
| `KRunVentures_인증서.cer` | SmartScreen 경고 해제용 인증서 (최초 1회 설치) |

> **설치 없이 실행** — exe 파일을 다운로드 후 바로 실행합니다.
> SmartScreen 경고 시: exe 우클릭 → 속성 → **차단 해제** 체크 → 확인

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 🎙 **실시간 녹음** | 마이크로 녹음하며 MP3 자동 저장 |
| 📂 **파일 업로드** | MP3/WAV/M4A/MP4/OGG/FLAC 업로드 지원 |
| 🗣 **STT 변환** | CLOVA Speech / Gemini / ChatGPT Whisper — 화자 구분 지원 |
| 🤖 **AI 요약** | 5가지 요약 방식 (화자중심/주제중심/흐름중심/결정사항중심/커스텀) |
| 📄 **PDF 저장** | 회의록을 PDF 파일로 저장 (한글 완벽 지원) |
| ☁ **Google Drive** | 녹음 파일·STT·요약본 자동 업로드 |
| 📋 **회의목록 관리** | 전체 회의록 조회·편집·화자 이름 변경 |

---

## 🔄 워크플로우

```
[녹음 또는 파일 선택]
        ↓
   [STT 변환]
        ↓
 [화자 이름 변경]
        ↓
  [회의록 요약]
        ↓
   [로컬 저장]
        ↓
[Google Drive 업로드]
```

---

## ⚙ 시스템 요구사항

| 항목 | 요구사항 |
|------|----------|
| OS | Windows 10 / 11 (64-bit) |
| 메모리 | 4GB RAM 이상 권장 |
| 저장공간 | 500MB 이상 여유 공간 |
| 인터넷 | API 호출을 위한 인터넷 연결 필요 |

---

## 🔑 API 키 설정

앱 실행 후 **[설정] 탭**에서 API 키를 입력합니다.

### Gemini API (요약 기능 — **필수**)
1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey) 접속
2. **Create API Key** → 키 복사
3. 앱 설정 탭 → Gemini API → 입력 → 저장

### CLOVA Speech API (STT — **권장**)
1. [console.ncloud.com](https://console.ncloud.com) → AI Service → CLOVA Speech
2. 도메인 생성 → 연동 정보 탭 → **Invoke URL + Secret Key** 복사
3. 앱 설정 탭 → CLOVA Speech API → 입력 → 저장 → 연결 테스트

### ChatGPT API (STT+요약 — **선택**)
1. [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. **Create new secret key** → 복사
3. 앱 설정 탭 → ChatGPT API → 입력 → 저장

---

## ☁ Google Drive 연동 (선택)

1. [Google Cloud Console](https://console.cloud.google.com) → 새 프로젝트 생성
2. **Google Drive API** 활성화
3. OAuth 클라이언트 ID 생성 → 유형: **데스크톱 앱** (⚠ Web 애플리케이션 선택 시 오류 발생)
4. JSON 파일 다운로드
5. 앱 설정 탭 → Google Drive 설정 → JSON 등록 → Google 인증
6. **두 폴더 한번에 생성** 클릭

---

## 🤖 STT 엔진 비교

| 엔진 | 한국어 정확도 | 화자 구분 | 파일 크기 | 장시간 |
|------|:---:|:---:|:---:|:---:|
| **CLOVA Speech** | ⭐⭐⭐⭐⭐ | ✅ | 최대 1GB | 무제한 |
| **Gemini** | ⭐⭐⭐⭐ | ✅ | 20MB | ~1시간 |
| **ChatGPT Whisper** | ⭐⭐⭐⭐ | ❌ | 25MB | ~30분 |

### 시나리오별 권장 조합

| 시나리오 | STT | 요약 |
|---------|-----|------|
| 일반 회의 (30분 이하) | CLOVA Speech | Gemini |
| 장시간 회의 (1시간+) | CLOVA Speech | Claude |
| 다국어 혼용 | ChatGPT Whisper | GPT-4o |
| 비용 최소화 | Gemini | Gemini |

---

## 📁 저장 폴더 구조

```
~/Documents/Meeting recording/
├── 녹음파일/          ← MP3 녹음 파일
└── 회의록(요약)/      ← STT 변환본(.txt) + 요약본(.md)
```

---

## 🛠 자주 발생하는 문제

<details>
<summary><b>CLOVA 연결 테스트 실패 (401)</b></summary>

NAVER Console → 연동 정보 탭의 **Secret Key**를 사용해야 합니다. 계정 비밀번호가 아닙니다.
</details>

<details>
<summary><b>CLOVA 연결 테스트 실패 (403)</b></summary>

NAVER Cloud Console에서 **CLOVA Speech 서비스 신청**이 필요합니다.
</details>

<details>
<summary><b>Google 로그인 "개발자 오류"</b></summary>

OAuth 클라이언트 ID 유형이 잘못되었습니다. **데스크톱 앱** 유형으로 재생성하세요.
</details>

<details>
<summary><b>앱 실행 차단 (Windows SmartScreen)</b></summary>

`exe 우클릭` → `속성` → `차단 해제` 체크 → `확인`
또는 `KRunVentures_인증서.cer` 설치 (신뢰할 수 있는 게시자 등록)
</details>

<details>
<summary><b>Gemini STT 타임아웃 반복</b></summary>

음성 파일이 긴 경우 **CLOVA Speech**로 STT 엔진을 전환하세요.
</details>

---

## 📖 전체 매뉴얼

> 자세한 설치·사용 방법은 **[설치 및 사용 매뉴얼 (PDF)](https://github.com/antonio103first/meeting-recording-for-pc-app/releases/latest)** 를 참고하세요.

---

## 📋 변경 이력

### v3.0.3 (2026.03) — 최신
- ✅ GitHub Actions `contents: write` 권한 추가 → Release 자동 업로드 안정화
- ✅ Google OAuth 클라이언트 유형 사전 검증 및 구체적 오류 안내
- ✅ 회의록 넘버링 구조 개선: `(1)/(A)` → `1.1 / 1.1.1` 계층 방식
- ✅ 카카오톡 공유 개선: MD 텍스트 전송 → PDF 생성 후 파일 공유

### v3.0.0 (2026.02)
- 5가지 요약 방식 지원
- PDF 저장 기능 추가
- 회의목록 DB 관리 기능

### v2.0.0
- CLOVA Speech STT 엔진 추가
- Google Drive 자동 업로드

---

<div align="center">

**Made with ❤ by [K-Run Ventures](https://github.com/antonio103first)**

</div>
