# 회의녹음요약 v3.0 — 전체 QA 테스트 보고서

**작성일:** 2026-03-24
**검토 대상:** `app_dist/` 전체 (main.py 2,639줄 포함 5개 핵심 파일)
**검토 방식:** 정적 분석 (pyflakes + AST 파싱) + 코드 로직 수동 추적
**검토 결과:** **통과 (버그 1건 발견·즉시 수정 완료)**

---

## 1. 검사 범위 및 결과 요약

| 검사 항목 | 파일 | 결과 |
|---|---|---|
| Python 문법 오류 | config.py, file_manager.py, claude_service.py, gemini_service.py, main.py | ✅ 전원 PASS |
| 3폴더 저장 구조 (MP3/STT/SUMMARY) | config.py, file_manager.py, main.py | ✅ 정상 |
| 요약 엔진 3종 분기 (Gemini/Claude/ChatGPT) | main.py | ✅ 정상 |
| flow 요약 모드 템플릿 및 분기 | gemini_service.py, claude_service.py, main.py | ✅ 정상 |
| 회의목록 탭 UX (Notebook 분리뷰 + 4개 버튼) | main.py | ✅ 정상 |
| 설정 탭 (ChatGPT API 키, 3폴더 경로) | main.py | ✅ 정상 |
| DB 스키마 (stt_text, summary_text 필드) | database.py | ✅ 정상 |
| v2→v3 마이그레이션 (audio_subdir→mp3_subdir) | config.py | ✅ 정상 |
| **Critical 버그** | main.py:2319 | ⚠️ **발견·수정 완료** |

---

## 2. 버그 상세 보고

### [B-01] CRITICAL — Lambda Closure 버그 (즉시 수정 완료)

**위치:** `app_dist/main.py` 라인 2318–2319 `_test_gpt()` 함수 내부

**현상:** ChatGPT 연결 테스트 실패 시 앱이 에러 메시지를 표시하는 대신 내부적으로 `NameError: name 'e' is not defined` 발생

**원인:**
Python 3 명세상 `except Exception as e:` 블록이 종료되면 `e` 변수가 스코프에서 즉시 삭제된다. 해당 코드는 `self.after(0, lambda: ...)` 를 통해 메인 스레드에 콜백을 예약한 뒤 `_run()` 스레드가 종료되므로, 람다 실행 시점에 `e` 가 이미 사라진 상태.

**수정 전:**
```python
except Exception as e:
    self.after(0, lambda: self._gpt_status_var.set(f"❌ {str(e)[:80]}"))
```

**수정 후:**
```python
except Exception as e:
    err_msg = str(e)[:80]
    self.after(0, lambda: self._gpt_status_var.set(f"❌ {err_msg}"))
```

**커밋:** `c9ed02a` — `fix: ChatGPT 연결 테스트 lambda closure 버그 수정 (B-01)`

---

## 3. 경고 (기능 영향 없음)

### [W-01] 미사용 변수 `drive_sum_link` (main.py:1855)

`_on_resummarize_done()` 함수에서 `drive_sum_link = ""` 초기화 후, Drive 비연결 경로에서 리터럴 `""` 를 직접 전달하므로 변수가 실제 참조되지 않음.
기능 오류 없음 — 코드 가독성 개선 수준으로 차기 리팩터링 시 처리 예정.

### [W-02] 미사용 변수 `msg` (claude_service.py:41)

`test_connection()` 함수에서 `msg = f"연결 성공!..."` 대입 후 `return True, f"연결 성공! ({CLAUDE_MODEL})"` 로 리터럴 직접 반환.
기능 오류 없음. 차기 리팩터링 시 중복 제거 예정.

---

## 4. 기능별 검증 상세

### 4-1. 3폴더 저장 구조 (F-06-S)

`config.py` 검증 결과:

- `MP3_SAVE_DIR`, `STT_SAVE_DIR`, `SUMMARY_SAVE_DIR` 독립 경로 계산 ✅
- `AUDIO_SAVE_DIR = MP3_SAVE_DIR` 하위 호환 alias 유지 ✅
- `reload_paths()` 호출 시 3폴더 동시 갱신 및 자동 mkdir ✅
- v2 `audio_subdir` → v3 `mp3_subdir` 자동 마이그레이션 ✅
- `load_config()` 기본값에 `mp3_subdir`, `stt_subdir`, `summary_subdir` 포함 ✅

`main.py` 저장 경로 사용 검증:

- STT 저장: `fm.save_stt_text(..., str(config.STT_SAVE_DIR), ...)` ✅
- 요약 저장: `fm.save_summary_text(..., str(config.SUMMARY_SAVE_DIR), ...)` ✅
- 설정 탭 경로 라벨: `config.STT_SAVE_DIR`, `config.SUMMARY_SAVE_DIR` 실시간 반영 ✅

### 4-2. 요약 엔진 3종 분기 (F-05)

`main.py` `_start_pipeline_summary()` 분기 검증:

```
if   engine == "claude"   → claude.summarize()       ✅
elif engine == "chatgpt"  → self._summarize_with_chatgpt()  ✅
else (default "gemini")   → gemini.summarize()        ✅
```

동일 패턴이 재요약(`_on_resummarize_requested()`)에서도 동일하게 구현됨 ✅

`_summarize_with_chatgpt()` 구현 검증:
- `openai` 패키지 미설치 시 안내 메시지 반환 ✅
- API 키 미입력 시 사전 반환 ✅
- `claude_service._get_template()` 재사용으로 템플릿 일관성 유지 ✅
- `config.CHATGPT_MODEL = "gpt-4o"` 참조 ✅
- `temperature=0.3`, `max_tokens=8192` 설정 ✅

### 4-3. flow 요약 모드 (F-04)

- `gemini_service.py`: `_SUMMARY_FLOW_TEMPLATE` 정의 (255번째 줄), `summarize()` 내 `"flow"` 분기 ✅
- `claude_service.py`: `_SUMMARY_FLOW_TEMPLATE` import, `_get_template()` 내 `"flow"` 분기 ✅
- `main.py`: 녹음 탭 변환 다이얼로그 `"흐름 중심(flow)"` 라디오버튼 ✅
- `main.py`: 파일 탭 변환 다이얼로그 동일 옵션 ✅

### 4-4. 회의목록 탭 UX (F-01)

`ttk.Notebook` 분리뷰 구현 검증:

- `self._detail_nb = ttk.Notebook(bot_frame)` 생성 ✅
- `"📋 회의록 요약"` 탭 + `ScrolledText` 연결 ✅
- `"📝 STT 원문"` 탭 + `ScrolledText` 연결 ✅
- `self._detail_box = self._sum_detail_box` 하위 호환 alias ✅
- `_on_list_select()`: 두 탭 동시 업데이트 ✅

4개 액션 버튼 검증:

| 버튼 | 구현 메서드 | 동작 |
|---|---|---|
| 📄 전체 보기 | `_view_meeting_full()` | 별도 창(요약/STT/정보 3탭) ✅ |
| 🖨 출력·인쇄 | `_print_meeting()` | `fm.print_file()` 호출, 파일 없으면 임시 생성 ✅ |
| 📤 공유 | `_share_meeting()` | `fm.open_file_in_explorer()` 파일 탐색기 열기 ✅ |
| 🗑 삭제 | `_delete_meeting()` | DB 레코드 삭제, 로컬 파일 유지 명시 ✅ |

### 4-5. 설정 탭 (F-05)

- ChatGPT API 키 입력 필드 (`_gpt_key_var`) ✅
- 👁 키 표시/숨김 토글 (`_toggle_gpt_key_vis()`) ✅
- 💾 저장 버튼 (`_save_gpt_key()`) ✅
- 🔌 연결 테스트 (`_test_gpt()`) → **B-01 수정 완료** ✅
- 3폴더 경로 설정 (MP3/STT/요약 각각 폴더명 입력) ✅
- 저장 후 `config.reload_paths()` 호출 ✅

---

## 5. DB 스키마 적합성

`database.py` CREATE TABLE 검증:

```sql
stt_local_path      TEXT   -- STT .md 파일 경로
summary_local_path  TEXT   -- 요약 .md 파일 경로
stt_text            TEXT   -- STT 전문 (DB 저장)
summary_text        TEXT   -- 요약 전문 (DB 저장)
drive_stt_link      TEXT   -- Drive STT 링크
```

`_finalize_save()` 에서 모든 필드 올바르게 매핑 ✅

---

## 6. 최종 판정

| 등급 | 건수 | 내용 |
|---|---|---|
| Critical (즉시 수정 필요) | 1 → **0** | B-01 수정 완료 |
| Warning (기능 영향 없음) | 2 | W-01, W-02 — 차기 리팩터링 예정 |
| Pass | 21 | 주요 기능 전원 통과 |

**→ v3.0 출시 기준 충족. 다음 단계 진행 가능.**

---

## 7. 권장 Push 명령

GitHub 자격증명 환경 제약으로 로컬 커밋 완료 상태. 터미널에서 아래 명령으로 반영:

```bash
git push origin master
```

---

*보고서 작성: Claude Sonnet 4.6 | 검토 기준일: 2026-03-24*
