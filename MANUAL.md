# 🎙 회의녹음요약 — 사용자 설명서 v3.0

> 버전 3.0 | 2026-03-26 | K-Run Ventures

---

## 1. 개요

**회의녹음요약**은 회의·강의 음성을 자동으로 텍스트로 변환(STT)하고, AI가 회의록을 요약·정리한 후 로컬 저장 및 Google Drive 자동 업로드까지 처리하는 Windows 데스크톱 애플리케이션입니다.

### 주요 워크플로우

```
[녹음 또는 파일 선택]
       ↓
[STT 변환: CLOVA Speech / Gemini / ChatGPT]
       ↓
[화자 이름 변경 (선택)]
       ↓
[회의록 요약: 화자중심 / 주제중심 / 흐름중심 등 5가지 방식]
       ↓
[로컬 저장: MP3 + STT(.txt) + 요약(.md)]
       ↓
[Google Drive 자동 업로드 (설정 시)]
```

---

## 2. 설치

### 2.1 다운로드

최신 버전은 아래 링크에서 누구나 로그인 없이 다운로드 가능합니다.

**👉 https://github.com/antonio103first/meeting-recording-minute-app/releases/latest**

다운로드 파일 2개:

| 파일 | 용도 |
|------|------|
| `회의녹음요약.exe` | 앱 실행 파일 |
| `KRunVentures_인증서.cer` | SmartScreen 경고 해제용 (최초 1회) |

---

### 2.2 인증서 설치 (최초 1회 필수)

SmartScreen 경고 없이 실행하려면 인증서를 먼저 설치해야 합니다.

1. `KRunVentures_인증서.cer` 더블클릭
2. **인증서 설치** 클릭
3. **로컬 컴퓨터** 선택 → **다음**
4. **모든 인증서를 다음 저장소에 저장** 선택
5. **찾아보기** → **신뢰할 수 있는 게시자** 선택 → **확인**
6. **다음** → **마침**

> 인증서 설치 후에는 매번 SmartScreen 경고 없이 바로 실행됩니다.

---

### 2.3 SmartScreen 경고 우회 (인증서 없이)

인증서 설치 없이 바로 실행하려면:

**방법 1 — 파일 속성에서 차단 해제 (권장)**
1. `회의녹음요약.exe` 우클릭 → **속성**
2. 하단 보안 섹션 → **"차단 해제"** 체크
3. **확인** 클릭

**방법 2 — SmartScreen 경고 화면에서**
1. 빨간 경고 화면에서 **"추가 정보"** 클릭
2. **"실행"** 버튼 클릭

---

### 2.4 실행

`회의녹음요약.exe` 더블클릭 → 최초 실행 시 데이터 폴더 자동 생성

---

## 3. 초기 설정

앱 실행 후 **⚙ 설정** 탭에서 API 키를 입력합니다.

---

### 3.1 CLOVA Speech API (STT 권장)

한국어 특화, 장시간 녹음에 가장 적합합니다.

#### API 키 발급

1. [console.ncloud.com](https://console.ncloud.com) 접속 → 로그인
2. **AI Service → CLOVA Speech** 클릭
3. 도메인(앱) 선택 → **설정 탭 → 연동 정보 탭**
4. **Invoke URL** 및 **Secret Key** 복사

> ⚠️ NAVER 계정 이메일/비밀번호가 아닌 **Invoke URL**과 **Secret Key**를 입력해야 합니다.

#### 앱에 입력

1. **설정** 탭 → **🎤 CLOVA Speech API 설정**
2. Invoke URL, Secret Key 입력 → **저장**
3. **연결 테스트** 버튼으로 ✅ 확인
4. 기본 STT 엔진을 **CLOVA Speech (권장)** 으로 선택

---

### 3.2 Gemini API (요약 필수)

회의록 요약에 필수입니다. STT에 CLOVA를 사용해도 Gemini 키는 반드시 설정해야 합니다.

1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey) 접속
2. **Create API Key** → 키 복사
3. **설정** 탭 → **🤖 Gemini API 설정** → API 키 입력 → **저장**
4. **연결 테스트** 버튼으로 ✅ 확인

---

### 3.3 ChatGPT API (선택)

OpenAI Whisper STT 또는 GPT 요약을 사용할 경우만 설정합니다.

1. [platform.openai.com/api-keys](https://platform.openai.com/api-keys) 접속
2. **Create new secret key** → 키 복사
3. **설정** 탭 → **🔑 ChatGPT API 설정** → API 키 입력 → **저장**

---

### 3.4 Google Drive 연동 (선택)

요약 완료 후 자동으로 Drive에 업로드됩니다.

1. [Google Cloud Console](https://console.cloud.google.com) → 프로젝트 생성
2. **API 및 서비스 → 라이브러리** → `Google Drive API` 활성화
3. **사용자 인증 정보 → OAuth 클라이언트 ID** 생성 (애플리케이션 유형: 데스크톱 앱)
4. JSON 파일 다운로드
5. **설정** 탭 → **☁ Google Drive 설정** → JSON 파일 선택 → **등록**
6. **🔐 Google 인증 (브라우저)** 클릭 → 브라우저에서 계정 로그인 및 권한 승인
7. **🚀 두 폴더 한번에 생성** 클릭 → 폴더 자동 생성 및 ID 저장

---

### 3.5 PC 저장 폴더 설정

MP3, STT 변환본, 회의록 요약 파일을 각각 다른 폴더에 저장할 수 있습니다.

1. **설정** 탭 → **💾 PC 저장 폴더 설정**
2. 각 항목 옆 **📂 찾아보기** 버튼 클릭 → 원하는 폴더 선택

| 항목 | 기본 경로 | 저장 형식 |
|------|----------|---------|
| ① MP3 녹음파일 | `~/Documents/Meeting recording/녹음파일/` | `.mp3` |
| ② STT 변환본 | `~/Documents/Meeting recording/회의록(요약)/` | `.txt` |
| ③ 회의록 요약 | `~/Documents/Meeting recording/회의록(요약)/` | `.md` |

---

## 4. 사용 방법

### 4.1 탭 구성

| 탭 | 기능 |
|----|------|
| 🎙 녹음/변환 | 녹음, 파일 업로드, STT 변환, 요약 실행 |
| 📋 회의목록 | 저장된 회의록 조회, 출력, 공유, PDF 저장 |
| ⚙ 설정 | API 키, Drive, 저장 폴더, 프린터 설정 |

---

### 4.2 녹음/변환 탭 — 영역 A (자동 파이프라인)

**① 음성 입력**

- **실시간 녹음**: 마이크 선택 → **● 녹음 시작** → **■ 중지** (MP3 자동 저장)
- **기존 파일**: **📂 파일 선택** → MP3, WAV, M4A, MP4, OGG, FLAC 지원

**② 화자 수 설정**

변환 전 실제 참석자 수를 설정합니다 (1~8명 또는 자동).

**③ 변환 시작**

**▶ 변환 시작** 클릭 → 설정에서 지정한 엔진과 요약 방식이 자동 적용되어 바로 진행됩니다.

```
STT 변환 (진행률 표시)
       ↓
요약 생성 중...
       ↓
파일명 입력
       ↓
로컬 저장 + Drive 업로드
```

> ⚙ 기본 STT 엔진 및 요약 방식은 **설정 탭 → 🗂 기본 요약 방식**에서 사전 지정합니다.

---

### 4.3 녹음/변환 탭 — 영역 B (STT 파일로 즉시 요약)

STT 변환을 건너뛰고 기존 `.txt` 파일로 바로 요약할 수 있습니다.

1. **📂 STT 파일 선택** 버튼 클릭 → `.txt` 파일 선택
2. (선택) 커스텀 프롬프트 입력란에 특별 지시사항 입력
3. **▶ 회의록 변환** 버튼 클릭

---

### 4.4 기본 요약 방식 설정

**설정** 탭 → **🗂 기본 요약 방식**에서 5가지 중 선택합니다.

| 방식 | 특징 |
|------|------|
| 화자 중심 | 발화자별로 발언 내용을 정리 |
| 주제 중심 | 논의된 주제별로 분류 |
| 흐름 중심 | 회의 진행 순서대로 서술 |
| 결정사항 중심 | 결정된 사항과 액션 아이템 중심 |
| 커스텀 | 직접 입력한 프롬프트로 요약 |

---

### 4.5 화자 이름 변경

STT 결과의 `[화자1]`, `[화자2]`를 실제 이름으로 바꿉니다.

1. 변환 후 **회의목록** 탭 → 해당 회의 선택 → **✏ 화자이름** 클릭
2. 각 화자 번호에 실제 이름 입력 → **✔ 적용**

---

### 4.6 회의목록 탭

저장된 모든 회의를 조회하고 다양한 작업을 수행합니다.

**목록에서 항목 선택 후 버튼 사용:**

| 버튼 | 기능 |
|------|------|
| 👁 전체보기 | 전체 회의록 팝업 + 📂 파일 열기 |
| 🖨 출력·인쇄 | 회의록 인쇄 |
| ✏ 화자이름 | 화자 이름 변경 |
| 📤 공유 ▼ | 공유 메뉴 |
| 📥 PDF 저장 | 회의록을 PDF 파일로 저장 |
| 🗑 삭제 | 항목 삭제 (파일 유지, DB에서만 삭제) |

**분리뷰 탭:**
- **📋 회의록 요약** — 요약 내용 표시
- **📝 STT 원문** — 원본 음성 텍스트 표시

---

## 5. STT 엔진 및 요약 엔진 비교

### 5.1 STT 엔진

| 항목 | CLOVA Speech (권장) | Gemini | ChatGPT (Whisper) |
|------|---------------------|--------|-------------------|
| 한국어 정확도 | ★★★★★ | ★★★★ | ★★★★ |
| 화자 구분 | ✅ | ✅ | ❌ |
| 파일 크기 제한 | 최대 1GB | 20MB (인라인) | 25MB |
| 장시간 처리 | 제한 없음 ✅ | 1시간 이내 권장 | 30분 이내 권장 |

> **STT 변환 가능**: CLOVA Speech, Gemini, ChatGPT(Whisper)
> **요약 전용 (STT 불가)**: Claude

### 5.2 권장 조합

| 시나리오 | STT 엔진 | 요약 엔진 |
|---------|---------|---------|
| 일반 회의 (30분 이하) | CLOVA Speech | Gemini |
| 장시간 회의 (1시간+) | CLOVA Speech | Claude |
| 다국어 혼용 | ChatGPT (Whisper) | GPT-4o |
| 비용 최소화 | Gemini | Gemini |

---

## 6. 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| "API 키를 입력해주세요" | 설정 미완료 | 설정 탭에서 해당 API 키 입력 후 저장 |
| CLOVA 연결 테스트 실패 (401) | Secret Key 오입력 | NAVER Console → 연동 정보의 Secret Key 사용 |
| CLOVA 연결 테스트 실패 (403) | 서비스 미신청 | NAVER Cloud Console에서 CLOVA Speech 신청 |
| Gemini 타임아웃 반복 | 긴 파일 처리 한계 | STT 엔진을 CLOVA로 전환 |
| Drive "미연결" | 인증 안 됨 | 설정 탭 → 🔐 Google 인증 |
| 회의목록에 파일이 안 보임 | 경로 설정 불일치 | 설정 탭 → PC 저장 폴더 경로 확인 |
| 앱 실행 차단 | SmartScreen | 섹션 2.3 참고 |

---

## 7. PC 재설치 후 복구

1. Release 페이지에서 exe 재다운로드
2. 설정 탭에서 API 키 재입력
3. Google Drive 재연동 (OAuth JSON 파일 백업이 있으면 그대로 등록)
4. **🚀 두 폴더 한번에 생성** 클릭

> 💡 `C:\Users\{사용자}\회의녹음요약_데이터\config.json`을 백업해두면 모든 설정이 보존됩니다.

---

## 8. 소스코드 접근

개발·수정이 필요한 경우 GitHub 저장소에서 소스코드를 확인할 수 있습니다.

**저장소**: https://github.com/antonio103first/meeting-recording-minute-app

```bash
# Python 3.11 이상 필요
git clone https://github.com/antonio103first/meeting-recording-minute-app.git
cd meeting-recording-minute-app
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app_dist/main.py
```

---

## 9. 기술 사양

| 항목 | 내용 |
|------|------|
| 버전 | v3.0 |
| 개발 언어 | Python 3.11 |
| GUI | tkinter |
| STT | NAVER CLOVA Speech Long API / Google Gemini / OpenAI Whisper |
| 요약 AI | Google Gemini / Anthropic Claude / OpenAI GPT |
| Drive API | Google Drive API v3 (OAuth2) |
| PDF 출력 | fpdf2 + 맑은 고딕 |
| 오디오 처리 | sounddevice, soundfile, ffmpeg |
| 패키징 | PyInstaller (--onefile --windowed) |
| 빌드 | GitHub Actions (Windows Server 2022) |

---

*K-Run Ventures | 회의녹음요약 v3.0 | 2026-03-26*
