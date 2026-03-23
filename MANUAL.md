# 🎙 회의녹음요약 — 사용자 설명서

> 버전 2.0 | 2026-03-19 | 대상: 일반 사용자 및 운영 담당자

---

## 1. 개요

**회의녹음요약**은 회의·강의 음성을 자동으로 텍스트로 변환하고, AI가 회의록을 요약·정리한 후 Google Drive에 자동 업로드하는 Windows 데스크톱 애플리케이션입니다.

### 1.1 주요 워크플로우

```
[녹음 또는 파일 선택]
       ↓
[STT 변환: CLOVA Speech 또는 Gemini]
       ↓
[화자 이름 변경 (선택)]
       ↓
[회의록 요약: 화자 중심 또는 주제 중심]
       ↓
[로컬 저장 (MP3 + STT 텍스트 + 요약)]
       ↓
[Google Drive 자동 업로드]
       ↓
[핵심 지표 자동 추출]
```

---

## 2. 설치

### 2.1 EXE 설치 (일반 사용자 권장)

1. GitHub Actions에서 `회의녹음요약-windows-exe.zip` 다운로드 후 압축 해제
2. `회의녹음요약.exe` 를 바탕화면 또는 원하는 위치에 복사
3. **SmartScreen 경고 해제** → 아래 **섹션 2.4** 참고 (최초 1회)
4. 더블클릭으로 실행
5. 최초 실행 시 데이터 폴더가 자동 생성됩니다

---

### 2.4 Windows SmartScreen 차단 해제 (필독)

Microsoft SmartScreen은 인증서 서명과 무관하게 **게시자 평판**이 없는 앱을 차단합니다.
아래 방법 중 하나를 사용하세요.

---

#### ✅ 방법 1 — 파일 속성 차단 해제 (가장 간단, 권장)

1. `회의녹음요약.exe` 파일에서 **마우스 오른쪽 클릭 → 속성**
2. 하단 보안 섹션에서 **"차단 해제"** 체크박스 체크
3. **확인** 클릭 → 이후 더블클릭으로 바로 실행

> 💡 이 방법이 가장 간단하며, 1회만 하면 됩니다.

---

#### ✅ 방법 2 — SmartScreen "추가 정보" 클릭

경고 화면에서 **닫기(X)가 아닌** 아래 순서로 진행합니다.

1. 빨간 경고 화면에서 **"추가 정보"** 클릭 (작은 파란 링크)
2. 하단에 나타나는 **"실행"** 버튼 클릭

---

#### ✅ 방법 3 — PowerShell 명령어 (IT 담당자용)

관리자 권한 PowerShell에서 실행:

```powershell
Unblock-File -Path "C:\Users\사용자명\Desktop\회의녹음요약.exe"
```

여러 PC에 배포할 경우 아래 명령으로 일괄 처리:

```powershell
Get-ChildItem "C:\배포폴더\*.exe" | Unblock-File
```

---

#### ✅ 방법 4 — Windows 평판 기반 보호 설정 변경 (전사 배포 시)

> ⚠️ 아래 설정은 사내 신뢰 앱에 한해 적용하세요.

1. **Windows 보안** 앱 실행 → **앱 및 브라우저 컨트롤**
2. **평판 기반 보호 설정** 클릭
3. **잠재적으로 원치 않는 앱 차단** → 해제
4. 또는 특정 파일에 대해 **허용**으로 표시

---

> **권장 순서**: 방법 1(파일 속성) → 실패 시 방법 2(추가 정보) → IT 담당자는 방법 3(PowerShell)

### 2.2 소스코드 실행 (개발·수정 시)

```bash
# Python 3.10 이상 필요
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app_dist/main.py
```

### 2.3 EXE 직접 빌드

```bash
# 프로젝트 루트에서 실행
build_dist.bat
```

빌드 완료 후 `dist/회의녹음요약.exe` 생성됩니다.

---

## 3. 초기 설정

### 3.1 CLOVA Speech API 설정 (STT 권장)

CLOVA Speech는 한국어 특화 STT 엔진으로, 긴 녹음 파일도 타임아웃 없이 안정적으로 변환합니다.

> ⚠️ **중요**: NAVER 계정 이메일/비밀번호가 아닌, CLOVA Speech 도메인 설정 화면의 **Invoke URL**과 **Secret Key**를 입력해야 합니다.

#### API 키 위치 (NAVER Cloud Console)

1. [console.ncloud.com](https://console.ncloud.com) 접속 후 로그인
2. **AI Service** → **CLOVA Speech** 클릭
3. 생성된 도메인(앱) 클릭 → **설정** 탭 → **연동 정보** 탭

| 항목 | NAVER Console 위치 | 앱 입력 필드 |
|------|-------------------|-------------|
| **Invoke URL** | 연동 정보 → Invoke URL | Invoke URL 입력란 |
| **Secret Key** | 연동 정보 → Secret Key | Secret Key 입력란 |

> `https://clovaspeech-gw.ncloud.com/external/v1/...` 형식의 URL이 Invoke URL입니다.

#### 앱에 입력

1. 앱 실행 → **설정** 탭 클릭
2. **🎤 CLOVA Speech API 설정** 섹션 확인
3. **Invoke URL** 필드에 복사한 URL 붙여넣기
4. **Secret Key** 필드에 복사한 키 붙여넣기 (👁 버튼으로 표시/숨김)
5. **저장** 버튼 클릭
6. **연결 테스트** 버튼으로 정상 동작 확인 → ✅ 표시 확인
7. **기본 STT 엔진**을 **CLOVA Speech (권장)** 으로 선택

---

### 3.2 Gemini API 설정 (요약 필수)

Gemini API는 회의록 요약 및 핵심 지표 추출에 반드시 필요합니다.
STT 엔진으로 사용하지 않더라도 반드시 설정해야 합니다.

#### API 키 발급

1. [Google AI Studio](https://aistudio.google.com/apikey) 접속
2. **Create API Key** 클릭
3. 생성된 키 복사

#### 앱에 입력

1. **설정** 탭 → **🤖 Gemini API 설정** 섹션
2. API 키 입력 → **저장**
3. **연결 테스트**로 확인

---

### 3.3 Google Drive 연동 (자동 업로드 선택)

#### OAuth 설정 (최초 1회)

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. **API 및 서비스 → 라이브러리** → `Google Drive API` 검색 → **사용 설정**
4. **사용자 인증 정보 → + 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - 이름: `회의녹음요약` (임의 입력)
5. **다운로드** 버튼으로 JSON 파일 저장

#### 앱에서 연동

1. **설정** 탭 → **☁ Google Drive 설정**
2. **📂 파일 선택** → 다운로드한 JSON 파일 선택 → **등록**
3. **🔐 Google 인증 (브라우저)** 클릭 → 브라우저에서 구글 계정 로그인 및 권한 승인
4. 상태가 🟢 **인증 완료**로 변경 확인

#### 업로드 폴더 설정

연동 후 파일이 저장될 Drive 폴더를 지정합니다.

1. **업로드 폴더 설정** 섹션에서 폴더명 확인 (기본값: `녹음파일` / `회의록(요약)`)
2. **🚀 두 폴더 한번에 생성** 클릭
3. 각 폴더 ID가 자동 저장됩니다
4. 폴더명을 바꾸려면 이름 수정 후 **📁 생성/찾기** 버튼 클릭

> ⚠️ 같은 이름의 폴더가 이미 있으면 기존 폴더 ID를 재사용합니다.

---

## 4. 사용 방법

### 4.1 탭 구성

| 탭 | 기능 |
|----|------|
| 🎙 녹음/변환 | 녹음, STT 변환, 요약 실행 |
| 📋 회의목록 | 과거 회의록 조회 |
| ⚙ 설정 | API 키, Drive, 프롬프트 설정 |

---

### 4.2 녹음 및 변환

#### ① 음성 입력

**실시간 녹음:**
1. **마이크** 드롭다운에서 입력 장치 선택
2. **● 녹음 시작** 클릭 → 녹음 시작
3. **⏸ 일시정지** / **▶ 재개** 버튼으로 제어
4. **■ 중지** 클릭 → MP3 자동 저장

**기존 파일 사용:**
1. **📂 파일 선택** 클릭
2. MP3, WAV, M4A, MP4, OGG, FLAC 파일 선택

#### ② 화자 수 설정

STT 변환 전 화자 수를 설정합니다 (1~8명 또는 자동).
정확한 화자 구분을 위해 실제 참석자 수를 선택하세요.

#### ③ 변환 시작

1. **▶ 변환 시작** 클릭
2. 옵션 다이얼로그에서 설정:
   - **STT 변환 엔진**: CLOVA Speech 또는 Gemini 선택
   - **요약 방식**: 화자 중심 또는 주제 중심
   - **화자 이름 변경**: STT 완료 후 이름 직접 입력 여부
3. **▶ 변환 시작** 클릭

#### ④ 처리 과정

```
STT 변환 진행 (진행률 바 표시)
       ↓
[화자 이름 입력 다이얼로그] (선택 시)
       ↓
요약 생성 중...
       ↓
파일명 입력 팝업
       ↓
로컬 저장 + Drive 업로드 (자동)
       ↓
핵심 지표 자동 추출
```

> 💡 **■ 중단** 버튼으로 언제든 중지할 수 있습니다.

---

### 4.3 화자 이름 변경

STT 결과의 `[화자1]`, `[화자2]` 등을 실제 이름으로 치환합니다.

1. 옵션에서 **"STT 완료 후 화자 이름을 직접 입력합니다"** 체크
2. STT 완료 후 이름 입력 다이얼로그 팝업
3. 각 화자 번호에 실제 이름 입력 → **✔ 적용**
4. 이름이 STT 텍스트에 반영된 후 요약 진행

---

### 4.4 커스텀 재요약

설정 탭에서 별도 지시사항을 입력하면, 기존 STT 결과를 다른 방식으로 재요약할 수 있습니다.

1. **설정** 탭 → **🎯 요약 커스텀 프롬프트**
2. 지시사항 입력 (예: "기술 결정사항과 다음 액션 아이템만 뽑아줘")
3. **활성화** 체크박스 체크 → **저장**
4. 녹음/변환 탭 → **🔄 재요약** 버튼 클릭

---

### 4.5 회의목록 조회

- **📋 회의목록** 탭 → 저장된 모든 회의 목록 표시
- 항목 선택 → **보기** 버튼 또는 더블클릭으로 STT·요약 내용 확인
- **삭제** 버튼으로 항목 제거

---

## 5. STT 엔진 비교 및 주의사항

### 5.1 엔진별 성능 비교

| 항목 | CLOVA Speech (권장) | Gemini | Claude | ChatGPT (OpenAI) |
|------|---------------------|--------|--------|-----------------|
| 한국어 정확도 | ★★★★★ | ★★★★ | ★★★☆ | ★★★★ |
| 긴 녹음 처리 | 단일 업로드, 타임아웃 없음 | 단일 API 콜, 타임아웃 가능 | 텍스트 기반 (음성 직접 처리 불가) | Whisper 기반, 25MB 제한 |
| 화자 구분 | ✅ 지원 | ✅ 지원 | ❌ 미지원 (STT 불가) | ❌ 미지원 (화자 구분 없음) |
| 파일 크기 제한 | 최대 1GB | 최대 2GB (인라인 기준 20MB) | 해당 없음 (STT 불가) | 최대 25MB |
| 최대 녹음 길이 | 제한 없음 (권장) | 약 1시간 이내 권장 | 해당 없음 | 약 30분 이내 권장 |
| 비용 | NAVER Cloud 과금 | Google AI 과금 | Anthropic 과금 | OpenAI 과금 |
| 용도 | STT 전용 | STT + 요약 겸용 | 요약 전용 | STT(Whisper) + 요약 겸용 |

> **STT 변환 가능 엔진: CLOVA Speech, Gemini, ChatGPT(Whisper)**
> **요약 전용 엔진 (STT 불가): Claude**

---

### 5.2 STT 엔진 선택 주의사항

> ⚠️ **반드시 읽어주세요 — STT 엔진 선택 전 확인 사항**

#### CLOVA Speech (NAVER)

- **장시간 회의(30분 이상)에 가장 적합.** 파일 크기 및 시간 제한이 사실상 없음
- NAVER Cloud Console에서 **CLOVA Speech Long API** 서비스 신청 필수 (Short API와 상이)
- Invoke URL과 Secret Key는 **도메인 설정 > 연동 정보** 메뉴에서 확인 (계정 ID/비밀번호 입력 금지)
- 음성 파일이 서버에 업로드되므로 **고도 기밀 회의 녹음 사용 시 사내 보안 정책 확인** 권장
- 과금 기준: 변환 음성 초(秒) 단위 — 장시간 회의 반복 사용 시 월 사용량 모니터링 필요

#### Gemini (Google)

- **인라인 전송(Inline):** 파일을 API 요청에 직접 포함 → 최대 **20MB** 제한
- **Files API 방식:** 최대 2GB 지원, 단 파일이 Google 서버에 48시간 임시 저장됨
- 1시간 초과 녹음 시 타임아웃 또는 정확도 저하 발생 가능 → 60분 초과 녹음은 CLOVA 권장
- 요약 및 분석에 강점, STT 단독 목적보다 **STT+요약 일괄 처리 시 효율적**
- API 무료 티어(Free Tier) 초과 시 과금 발생

#### ChatGPT / Whisper (OpenAI)

- STT는 **Whisper 모델** 사용, 영어 및 다국어 정확도가 높음
- 한국어 지원하나 CLOVA 대비 전문용어·고유명사 정확도 낮을 수 있음
- **파일 크기 25MB 제한** — 장시간 회의 MP3를 분할 없이 전송 불가
- 파일 분할 처리 시 화자 구분 연속성이 끊길 수 있음
- 요약 엔진으로 GPT-4o 사용 시 입력 토큰 한도(128k) 초과 주의 — 장문 STT 원문 입력 시 앞부분 잘림 가능

#### Claude (Anthropic)

- **STT(음성→텍스트) 기능 없음** — 요약 전용으로만 사용 가능
- STT 엔진으로 선택 시 오류 발생, 설정에서 **요약 API 전용**으로만 지정할 것
- 장문 컨텍스트(200k 토큰)에 강점 → 긴 STT 원문 요약에 적합
- API 요금이 상대적으로 높으므로 반복 사용 시 비용 모니터링 권장

---

### 5.3 엔진 조합 권장 설정

| 시나리오 | STT 엔진 | 요약 엔진 | 비고 |
|---------|---------|---------|------|
| **일반 회의 (30분 이하)** | CLOVA Speech | Gemini | 기본 권장 |
| **장시간 회의 (1시간 이상)** | CLOVA Speech | Claude | CLOVA 정확도 + Claude 장문 요약 |
| **다국어 혼용 회의** | ChatGPT (Whisper) | GPT-4o | 영어·한국어 혼용 시 적합 |
| **비용 최소화** | Gemini | Gemini | 무료 티어 활용, 단 긴 파일 주의 |
| **기밀 보안 최우선** | 사내 솔루션 검토 | Claude | 외부 서버 전송 최소화 |

---

## 6. 저장 경로

| 구분 | 경로 |
|------|------|
| 녹음 MP3 | `~/Documents/Meeting recording/녹음파일/` |
| STT 텍스트 | `~/Documents/Meeting recording/회의록(요약)/` |
| 요약 텍스트 | `~/Documents/Meeting recording/회의록(요약)/` |
| 앱 데이터/설정 | `~/회의녹음요약_데이터/config.json` |
| DB | `~/회의녹음요약_데이터/meetings.db` |

---

## 7. 문제 해결

### STT 변환이 안 될 때

| 증상 | 원인 | 해결 |
|------|------|------|
| "API 키를 입력해주세요" | 설정 미완료 | 설정 탭에서 해당 API 키 입력 후 저장 |
| CLOVA 연결 테스트 실패 (401) | Secret Key 오입력 또는 계정 이메일/비밀번호 입력 | NAVER Console → 도메인 설정 → 연동 정보의 **Invoke URL**과 **Secret Key** 사용 |
| CLOVA 연결 테스트 실패 (403) | CLOVA Speech 서비스 미신청 | NAVER Cloud Console에서 CLOVA Speech 이용 신청 |
| Gemini 타임아웃 반복 | 긴 파일 처리 한계 | STT 엔진을 CLOVA Speech로 전환 |

### Google Drive 업로드 실패 시

| 증상 | 원인 | 해결 |
|------|------|------|
| "Drive 미연결" | 인증 안 됨 | 설정 탭 → 🔐 Google 인증 |
| 폴더 생성 실패 | Drive API 비활성화 | Google Cloud Console → Drive API 활성화 |
| 업로드 오류 반복 | 토큰 만료 | 연결 해제 후 재인증 |

### 앱이 실행 안 될 때

- Windows Defender 또는 백신에서 차단되는 경우: 예외 처리 후 재실행
- DLL 오류: Visual C++ 재배포 패키지 설치 (`vcredist_x64.exe`)

---

## 8. PC 재설치 후 복구

1. EXE 파일 재실행 또는 소스코드 재설치
2. 설정 탭에서 API 키 재입력:
   - Gemini API 키: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   - CLOVA Invoke URL / Secret Key: [console.ncloud.com](https://console.ncloud.com) → AI Service → CLOVA Speech → 도메인 설정 → 연동 정보
3. Google Drive 재연동:
   - OAuth JSON 파일 백업이 있으면 그대로 등록
   - 없으면 Google Cloud Console에서 재생성
4. 업로드 폴더 재설정: **🚀 두 폴더 한번에 생성** 클릭

> 💡 `config.json` 파일을 백업해두면 API 키 및 폴더 설정이 보존됩니다.
> 경로: `C:\Users\{사용자}\회의녹음요약_데이터\config.json`

---

## 9. 기술 사양

| 항목 | 내용 |
|------|------|
| 개발 언어 | Python 3.10+ |
| GUI 프레임워크 | tkinter |
| STT 엔진 | NAVER CLOVA Speech Long API, Google Gemini |
| 요약 AI | Google Gemini 2.5 Flash |
| Drive API | Google Drive API v3 (OAuth2) |
| 오디오 처리 | sounddevice, soundfile, ffmpeg |
| 패키징 | PyInstaller (--onefile --windowed) |

---

*본 문서는 회의녹음요약 v2.0 기준으로 작성되었습니다.*
