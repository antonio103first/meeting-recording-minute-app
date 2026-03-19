# 🎙 회의녹음요약

회의·강의 음성을 녹음하거나 MP3 파일을 불러와
**STT 변환 → 회의록/강의 요약 → 로컬 저장 → Google Drive 자동 업로드**
까지 한 번에 처리하는 Windows 데스크톱 앱입니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🎙 실시간 녹음 | 마이크로 녹음 후 MP3 자동 저장 |
| 📂 파일 불러오기 | MP3/WAV/M4A 등 기존 파일 선택 |
| 📝 STT 변환 | CLOVA Speech(NAVER) 또는 Gemini(Google)로 음성 → 텍스트 |
| 📋 회의록 요약 | 화자 중심 / 주제 중심 방식 선택 |
| ☁ Google Drive 업로드 | 변환 완료 후 녹음·요약 각각 지정 폴더에 자동 업로드 |

### STT 엔진 선택

| 엔진 | 특징 | 권장 상황 |
|------|------|-----------|
| **CLOVA Speech** (NAVER) ★권장★ | 한국어 특화, 50초 청크 분할 처리로 타임아웃 없음 | 긴 회의 녹음 (30분 이상) |
| **Gemini** (Google) | 무료 API, 설정 간편 | 짧은 녹음 (5분 이내) |

### 요약 방식

1. **화자 중심** — 참석자별 발언 정리
2. **주제 중심** — 안건별 논의 정리

---

## 파일 저장 구조

```
C:\Users\{사용자}\Documents\Meeting recording\
├── 녹음파일\          ← MP3 녹음 파일
│   └── {날짜시간}_녹음.mp3
└── 회의록(요약)\      ← STT 텍스트 + 요약 텍스트
    ├── {날짜시간}_녹음.txt
    └── {날짜시간}_요약.txt
```

Google Drive 업로드 구조:
- **녹음 MP3** → Drive `녹음파일` 폴더 (별도 지정 가능)
- **STT/요약 TXT** → Drive `회의록(요약)` 폴더 (별도 지정 가능)

---

## 설치 및 실행

### 방법 A — EXE 파일 실행 (권장)

1. `dist_배포/회의녹음요약.exe` 실행
2. 설정 탭에서 API 키 입력
3. 녹음/변환 탭에서 바로 사용

### 방법 B — 소스코드 직접 실행

```bash
git clone <repo-url>
cd 회의녹음요약
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app_dist/main.py
```

### 방법 C — EXE 빌드

```bash
build_dist.bat
```

---

## 초기 설정 가이드

### Step 1. CLOVA Speech API 키 발급 (STT 권장)

1. [console.ncloud.com](https://console.ncloud.com) → AI·NAVER API → CLOVA Speech
2. 앱 생성 → **Client ID** / **Client Secret** 복사
3. 앱 **설정 탭 → CLOVA Speech API 설정**에 입력 후 저장

### Step 2. Gemini API 키 발급 (요약·지표 추출 필수)

1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey) 접속
2. **Create API Key** 클릭
3. 앱 **설정 탭 → Gemini API 설정**에 입력 후 저장

### Step 3. Google Drive 연동 (선택)

1. [console.cloud.google.com](https://console.cloud.google.com) → Google Drive API 활성화
2. **OAuth 2.0 클라이언트 ID** 생성 (데스크톱 앱 유형)
3. 다운로드 JSON 파일을 설정 탭에서 등록
4. **🔐 Google 인증** 버튼 클릭 → 브라우저 승인
5. **업로드 폴더 설정**에서 폴더명 지정 후 **🚀 두 폴더 한번에 생성** 클릭

---

## 시스템 요구사항

- OS: Windows 10 / 11
- Python: 3.10 이상 (소스 실행 시)
- ffmpeg: CLOVA STT 사용 시 필요 (자동 감지)
- 인터넷 연결 필수

---

## 의존성 패키지

```
google-genai
anthropic
requests
sounddevice
soundfile
google-auth
google-auth-oauthlib
google-api-python-client
```

전체 목록: `requirements.txt` 참고

---

## 변경 이력

| 버전 | 날짜 | 주요 변경 |
|------|------|-----------|
| v2.0 | 2026-03-19 | CLOVA Speech STT 추가, Google Drive 폴더 동적 관리, 업로드 폴더 분리 |
| v1.0 | 2025-03-18 | 최초 릴리스 (Gemini STT, 하드코딩 Drive 폴더) |
