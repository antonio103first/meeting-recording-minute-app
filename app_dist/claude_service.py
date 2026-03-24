"""
회의녹음요약 - Claude API (Anthropic) 요약 서비스
요약 전용 (STT는 Gemini 또는 외부 도구 사용)
"""
import time
import threading
from datetime import datetime

CLAUDE_MODEL = "claude-sonnet-4-6"


def _get_template(summary_mode: str):
    from gemini_service import (
        _SUMMARY_SPEAKER_TEMPLATE,
        _SUMMARY_TOPIC_TEMPLATE,
        _SUMMARY_FORMAL_MD_TEMPLATE,
        _SUMMARY_FORMAL_TEXT_TEMPLATE,
        _SUMMARY_LECTURE_MD_TEMPLATE,
        _SUMMARY_FLOW_TEMPLATE,
        _trim_summary,
    )
    if summary_mode == "topic":
        return _SUMMARY_TOPIC_TEMPLATE, _trim_summary
    elif summary_mode == "formal_md":
        return _SUMMARY_FORMAL_MD_TEMPLATE, _trim_summary
    elif summary_mode in ("formal_text", "formal"):
        return _SUMMARY_FORMAL_TEXT_TEMPLATE, _trim_summary
    elif summary_mode == "lecture_md":
        return _SUMMARY_LECTURE_MD_TEMPLATE, _trim_summary
    elif summary_mode == "flow":
        return _SUMMARY_FLOW_TEMPLATE, _trim_summary
    else:
        return _SUMMARY_SPEAKER_TEMPLATE, _trim_summary


def test_connection(api_key: str) -> tuple:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        # 가벼운 호출로 연결 확인
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "안녕"}],
        )
        return True, f"연결 성공! ({CLAUDE_MODEL})"
    except ImportError:
        return False, "anthropic 패키지가 설치되지 않았습니다."
    except Exception as e:
        return False, _friendly_error(str(e))


def summarize(stt_text: str, api_key: str, progress_cb=None,
              summary_mode: str = "speaker", cancel_event=None,
              custom_instruction: str = "") -> tuple:
    """STT 텍스트 → 회의록 요약 (Claude API)"""
    if not api_key:
        return False, "Claude API 키가 없습니다. 설정 탭에서 입력해주세요."
    if not stt_text.strip():
        return False, "변환된 텍스트가 비어 있습니다."

    try:
        import anthropic
    except ImportError:
        return False, "anthropic 패키지가 설치되지 않았습니다.\n명령 프롬프트에서 'python -m pip install anthropic' 실행 후 재시도해주세요."

    template, trim_fn = _get_template(summary_mode)

    try:
        if progress_cb: progress_cb(10)
        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        prompt = template.format(
            text=stt_text[:500000],
            dt=datetime.now().strftime("%Y년 %m월 %d일 %H:%M"),
        )
        if custom_instruction and custom_instruction.strip():
            prompt += f"\n\n[추가 지시사항]\n{custom_instruction.strip()}"

        if progress_cb: progress_cb(30)

        # 하트비트: API 응답 대기 중 진행 바 서서히 증가
        _stop_beat = threading.Event()
        _beat_start = time.time()
        def _beat():
            while not _stop_beat.is_set():
                _stop_beat.wait(10)
                if not _stop_beat.is_set():
                    elapsed = int(time.time() - _beat_start)
                    if progress_cb and elapsed > 0:
                        pct = min(95, 30 + elapsed // 3)
                        progress_cb(pct)
        threading.Thread(target=_beat, daemon=True).start()

        try:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
        finally:
            _stop_beat.set()

        if cancel_event and cancel_event.is_set():
            return False, "사용자에 의해 중단되었습니다."

        if progress_cb: progress_cb(100)
        result_text = message.content[0].text
        if not result_text:
            return False, "요약 응답이 비어 있습니다. 다시 시도해주세요."
        return True, trim_fn(result_text)

    except Exception as e:
        return False, _friendly_error(str(e))


def _friendly_error(msg: str) -> str:
    if "중단" in msg:
        return msg
    if "authentication_error" in msg.lower() or "invalid x-api-key" in msg.lower():
        return "Claude API 키가 올바르지 않습니다. 설정 탭에서 다시 확인해주세요."
    if "permission_error" in msg.lower() or "403" in msg:
        return "Claude API 키 권한이 없습니다. Anthropic Console에서 키를 확인하세요."
    if "rate_limit_error" in msg.lower() or "429" in msg:
        return "Claude API 요청 한도 초과입니다. 잠시 후 다시 시도해주세요."
    if "overloaded_error" in msg.lower():
        return "Claude 서버가 일시적으로 과부하 상태입니다. 잠시 후 다시 시도해주세요."
    if "timeout" in msg.lower():
        return "Claude API 응답 시간이 초과되었습니다. 다시 시도해주세요."
    return f"Claude 오류: {msg[:300]}"
