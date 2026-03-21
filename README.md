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
| 📝 STT 변환 | Gemini 2.5 Flash로 음성 → 텍스트 |
| 📎 TXT 첨부 | 기존 STT 텍스트 파일 직접 첨부해 요약 |
| 📋 회의록 요약 | 5가지 요약 방식 선택 |
| ☁ Google Drive 업로드 | 변환 완료 후 지정 폴더에 자동 업로드 |

### 요약 방식 5가지

1. **화자 중심** — 참석자별 발언 정리
2. **주제 중심** — 안건별 논의 정리
3. **업무미팅 회의록 (MD)** — 비즈니스 컨설턴트 스타일, 마크다운
4. **업무미팅 회의록 (텍스트)** — 비즈니스 컨설턴트 스타일, 일반 텍스트
5. **강의 요약 (MD)** — 소주제별 논리적 정리 (신앙/업무 강의 자동 적응)

### AI 엔진 선택
- **Gemini** (Google) — 기본값, API 키만 있으면 바로 사용
- **Claude** (Anthropic) — 선택 사항, 설정 탭에서 API 키 입력

---

## 파일 저장 구조

```
C:\Users\{사용자}\Documents\Meeting recording\
├── 녹음파일\                        ← MP3 녹음 파일
│   ├── 20250318_093012_녹음.mp3
│   └── 회의록(요약)\                ← STT 텍스트 + 요약 텍스트
│       ├── 20250318_093012_녹음.txt
│       └── 20250318_093012_요약.txt
```

Google Drive 폴더 구조도 동일:
- **녹음 MP3** → Drive `녹음파일` 폴더
- **STT/요약 TXT** → Drive `회의록(요약)` 폴더

---

## 설치 및 실행 방법

### 방법 A — EXE 파일 실행 (권장, 비개발자용)

1. `dist_배포/회의녹음요약.exe` 실행
2. 최초 실행 시 설정 마법사 안내에 따라 API 키 입력
3. 녹음/변환 탭에서 바로 사용

### 방법 B — 소스코드 직접 실행 (개발자용)

```bash
# 1. 저장소 클론
git clone https://github.com/antonio103/meeting-recorder-summarizer.git
cd meeting-recorder-summarizer

# 2. 가상환경 생성 및 패키지 설치
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. 실행
python app_dist/main.py
```

### 방법 C — EXE 직접 빌드

```bash
# build.bat 실행 또는 아래 명령어 직접 실행
py -m PyInstaller --onefile --windowed --name "회의녹음요약" ^
  --icon app_icon.ico ^
  --add-data "app_dist/config.py;." ^
  --add-data "app_dist/database.py;." ^
  --add-data "app_dist/recorder.py;." ^
  --add-data "app_dist/gemini_service.py;." ^
  --add-data "app_dist/claude_service.py;." ^
  --add-data "app_dist/file_manager.py;." ^
  --add-data "app_dist/google_drive.py;." ^
  app_dist/main.py
```

---

## 초기 설정 가이드

### Step 1. Gemini API 키 발급 (필수)

1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey) 접속
2. **Create API Key** 클릭
3. 발급된 키를 앱 **설정 탭 → Gemini API 키** 에 입력

### Step 2. Claude API 키 (선택)

1. [console.anthropic.com](https://console.anthropic.com) 접속
2. API Keys → Create Key
3. 앱 **설정 탭 → Claude API 키** 에 입력

### Step 3. Google Drive 연동 (선택)

Drive 자동 업로드를 사용하려면 Google Cloud Console에서 OAuth 설정이 필요합니다.

1. [console.cloud.google.com](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성
3. **API 및 서비스 → 라이브러리** → `Google Drive API` 활성화
4. **사용자 인증 정보 → OAuth 2.0 클라이언트 ID** 생성
   - 애플리케이션 유형: **데스크톱 앱**
5. 다운로드된 JSON 파일을 앱 **설정 탭 → OAuth 자격증명 파일 선택** 에서 등록
6. **🔐 Google 인증** 버튼 클릭 → 브라우저에서 구글 계정 로그인 승인

> ⚠️ PC 포맷 후 재설치 시: Google Cloud 프로젝트와 OAuth JSON 파일은 보관해두면 재사용 가능합니다.

---

## PC 포맷 후 재설치 절차

1. Git에서 소스코드 클론 또는 EXE 빌드
2. Gemini API 키는 [aistudio.google.com](https://aistudio.google.com/apikey)에서 재확인
3. Claude API 키는 [console.anthropic.com](https://console.anthropic.com)에서 재확인
4. Google OAuth JSON 파일은 백업해뒀다면 그대로 등록, 없으면 Step 3 재진행
5. 앱 실행 → 설정 탭에서 API 키 입력 → 완료

---

## 시스템 요구사항

- OS: Windows 10 / 11
- 마이크: 실시간 녹음 사용 시 필요
- 인터넷: Gemini/Claude API 호출 시 필요

---

## 의존성 패키지

```
google-genai
anthropic
sounddevice
soundfile
google-auth
google-auth-oauthlib
google-api-python-client
```

전체 목록: `requirements.txt` 참고
