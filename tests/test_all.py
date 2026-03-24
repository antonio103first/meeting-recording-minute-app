"""
회의녹음요약 앱 - 전체 자동화 테스트
API 호출 없이 mock으로 모든 기능 검증
"""
import sys
import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 모듈 경로 설정
APP_DIR = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

import config as cfg
import database as db
import recorder as rec
import gemini_service as gemini
import file_manager as fm


# ─── 임시 경로 패치 픽스처 ────────────────────────────
def _patch_paths(tmp: str):
    cfg.APP_DATA_DIR      = Path(tmp)
    cfg.CONFIG_FILE       = Path(tmp) / "config.json"
    cfg.DB_FILE           = Path(tmp) / "meetings.db"
    cfg.CREDENTIALS_FILE  = Path(tmp) / "google_credentials.json"
    cfg.TOKEN_FILE        = Path(tmp) / "google_token.json"
    cfg.AUDIO_SAVE_DIR    = Path(tmp) / "녹음파일"
    cfg.SUMMARY_SAVE_DIR  = Path(tmp) / "회의록(요약)"


# ═══════════════════════════════════════════════
#  1. config 테스트
# ═══════════════════════════════════════════════
class TestConfig(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _patch_paths(self.tmp)

    def test_default_config_has_gemini_key(self):
        c = cfg.load_config()
        self.assertIn("gemini_api_key", c)

    def test_save_and_load(self):
        cfg.save_config({"gemini_api_key": "TEST_KEY_123"})
        loaded = cfg.load_config()
        self.assertEqual(loaded["gemini_api_key"], "TEST_KEY_123")

    def test_incomplete_config_detected(self):
        ok, missing = cfg.is_config_complete({"gemini_api_key": ""})
        self.assertFalse(ok)
        self.assertTrue(len(missing) > 0)

    def test_complete_config_passes(self):
        ok, missing = cfg.is_config_complete({"gemini_api_key": "VALID_KEY"})
        self.assertTrue(ok)
        self.assertEqual(len(missing), 0)


# ═══════════════════════════════════════════════
#  2. database 테스트
# ═══════════════════════════════════════════════
class TestDatabase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _patch_paths(self.tmp)
        db.init_database()

    def test_table_created(self):
        import sqlite3
        conn = sqlite3.connect(str(cfg.DB_FILE))
        cur  = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meetings'"
        )
        self.assertIsNotNone(cur.fetchone())
        conn.close()

    def test_save_and_retrieve(self):
        mid = db.save_meeting(
            file_name="테스트_녹음",
            mp3_local_path="/tmp/test.mp3",
            stt_text="테스트 STT 내용",
            summary_text="테스트 요약",
        )
        self.assertGreater(mid, 0)
        m = db.get_meeting(mid)
        self.assertEqual(m["file_name"], "테스트_녹음")
        self.assertEqual(m["stt_text"], "테스트 STT 내용")

    def test_get_all_meetings_latest_first(self):
        import time
        for i in range(3):
            db.save_meeting(file_name=f"회의_{i}", stt_text="", summary_text="")
            time.sleep(0.01)  # created_at 시간 차이 보장
        all_m = db.get_all_meetings()
        self.assertEqual(len(all_m), 3)
        self.assertEqual(all_m[0]["file_name"], "회의_2")  # 최신순

    def test_delete_meeting(self):
        mid = db.save_meeting(file_name="삭제테스트", stt_text="", summary_text="")
        db.delete_meeting(mid)
        self.assertEqual(db.get_meeting(mid), {})

    def test_nonexistent_returns_empty(self):
        self.assertEqual(db.get_meeting(99999), {})


# ═══════════════════════════════════════════════
#  3. recorder 테스트
# ═══════════════════════════════════════════════
class TestRecorder(unittest.TestCase):

    def test_default_filename_format(self):
        name = rec.get_default_file_name()
        import re
        self.assertRegex(name, r"^\d{8}_\d{6}_녹음$")

    def test_check_ffmpeg_returns_bool(self):
        result = rec.check_ffmpeg()
        self.assertIsInstance(result, bool)

    def test_initial_state_is_idle(self):
        r = rec.AudioRecorder()
        self.assertEqual(r.state, "idle")

    def test_elapsed_str_format(self):
        r = rec.AudioRecorder()
        self.assertRegex(r.get_elapsed_str(), r"^\d{2}:\d{2}:\d{2}$")

    def test_get_level_within_range(self):
        r = rec.AudioRecorder()
        self.assertGreaterEqual(r.get_level(), 0.0)
        self.assertLessEqual(r.get_level(), 1.0)

    def test_stop_when_idle_returns_error(self):
        r = rec.AudioRecorder()
        ok, msg = r.stop_recording()
        self.assertFalse(ok)

    def test_get_available_devices_returns_list(self):
        devices = rec.get_available_devices()
        self.assertIsInstance(devices, list)


# ═══════════════════════════════════════════════
#  4. gemini_service 테스트 (mock)
# ═══════════════════════════════════════════════
class TestGeminiService(unittest.TestCase):

    def test_empty_api_key_fails(self):
        ok, msg = gemini.transcribe("/some/file.mp3", api_key="")
        self.assertFalse(ok)
        self.assertIn("API 키", msg)

    def test_nonexistent_file_fails(self):
        ok, msg = gemini.transcribe("/nonexistent/audio.mp3", api_key="TEST")
        self.assertFalse(ok)
        self.assertIn("찾을 수 없", msg)

    def test_empty_text_summarize_fails(self):
        ok, msg = gemini.summarize("   ", api_key="TEST")
        self.assertFalse(ok)

    def test_no_key_summarize_fails(self):
        ok, msg = gemini.summarize("회의 내용", api_key="")
        self.assertFalse(ok)

    def test_stt_prompt_has_korean_instruction(self):
        prompt = gemini._STT_PROMPT
        self.assertIn("한국어", prompt)
        self.assertIn("화자", prompt)

    def test_summary_template_has_sections(self):
        for section in ["개요", "논의", "결정사항", "액션"]:
            self.assertIn(section, gemini._SUMMARY_TEMPLATE)

    @patch("gemini_service.genai")
    def test_transcribe_small_file_success(self, mock_genai):
        mock_resp = MagicMock()
        mock_resp.text = "안녕하세요 회의를 시작합니다."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai.Client.return_value = mock_client

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio" * 100)
            path = f.name
        try:
            ok, result = gemini.transcribe(path, api_key="FAKE_KEY")
            self.assertTrue(ok, f"실패: {result}")
            self.assertIn("회의", result)
        finally:
            os.unlink(path)

    @patch("gemini_service.genai")
    def test_summarize_success(self, mock_genai):
        mock_resp = MagicMock()
        mock_resp.text = "## 회의록\n### 결정사항\n완료"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai.Client.return_value = mock_client

        ok, result = gemini.summarize("오늘 회의 내용입니다.", api_key="FAKE_KEY")
        self.assertTrue(ok, f"실패: {result}")
        self.assertIn("회의록", result)


# ═══════════════════════════════════════════════
#  5. file_manager 테스트
# ═══════════════════════════════════════════════
class TestFileManager(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _patch_paths(self.tmp)

    def test_generate_filename_suffix_녹음(self):
        name = fm.generate_default_filename("녹음")
        self.assertTrue(name.endswith("_녹음"))

    def test_generate_filename_suffix_요약(self):
        name = fm.generate_default_filename("요약")
        self.assertTrue(name.endswith("_요약"))

    def test_validate_removes_invalid_chars(self):
        ok, cleaned = fm.validate_filename('test:file*name?<>.txt')
        self.assertTrue(ok)
        for ch in ':*?<>':
            self.assertNotIn(ch, cleaned)

    def test_validate_empty_returns_false(self):
        ok, _ = fm.validate_filename("   ")
        self.assertFalse(ok)

    def test_save_stt_creates_utf8_bom_file(self):
        ok, path = fm.save_stt_text("테스트 STT 내용", "20260219_143022_녹음")
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as f:
            bom = f.read(3)
        self.assertEqual(bom, b'\xef\xbb\xbf')  # UTF-8 BOM

    def test_save_summary_goes_to_correct_folder(self):
        ok, path = fm.save_summary_text("요약 내용", "20260219_143022_녹음")
        self.assertTrue(ok)
        self.assertIn("요약", str(path))
        self.assertTrue(os.path.exists(path))

    def test_get_file_size_nonexistent(self):
        size = fm.get_file_size_mb("/nonexistent/file.mp3")
        self.assertEqual(size, 0.0)


# ═══════════════════════════════════════════════
#  6. 통합 테스트 (전체 파이프라인 mock)
# ═══════════════════════════════════════════════
class TestIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _patch_paths(self.tmp)
        db.init_database()

    @patch("gemini_service.genai")
    def test_full_pipeline_mock(self, mock_genai):
        """STT → 요약 → DB 저장 → 조회 전체 흐름"""
        # mock 설정: client → models.generate_content → resp.text
        mock_resp = MagicMock()
        mock_resp.text = "오늘 프로젝트 점검 회의를 진행했습니다."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai.Client.return_value = mock_client

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake_audio" * 50)
            audio_path = f.name

        try:
            # STT
            ok, stt_text = gemini.transcribe(audio_path, api_key="FAKE")
            self.assertTrue(ok, f"STT 실패: {stt_text}")

            # 요약
            ok2, summ_text = gemini.summarize(stt_text, api_key="FAKE")
            self.assertTrue(ok2)

            # 로컬 파일 저장
            ok3, stt_path  = fm.save_stt_text(stt_text, "20260219_143022_녹음")
            ok4, summ_path = fm.save_summary_text(summ_text, "20260219_143022_녹음")
            self.assertTrue(ok3)
            self.assertTrue(ok4)

            # DB 저장
            mid = db.save_meeting(
                file_name="20260219_143022_녹음",
                mp3_local_path=audio_path,
                stt_local_path=stt_path,
                summary_local_path=summ_path,
                stt_text=stt_text,
                summary_text=summ_text,
            )
            self.assertGreater(mid, 0)

            # 조회
            m = db.get_meeting(mid)
            self.assertEqual(m["file_name"], "20260219_143022_녹음")
            self.assertTrue(len(m["stt_text"]) > 0)

        finally:
            os.unlink(audio_path)


# ═══════════════════════════════════════════════
#  실행
# ═══════════════════════════════════════════════
def run():
    print("=" * 60)
    print("  회의녹음요약 앱 - 자동화 테스트")
    print("=" * 60)
    suite  = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("\n" + "=" * 60)
    total  = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"  결과: {passed}/{total} 통과  |  "
          f"실패: {len(result.failures)}  |  오류: {len(result.errors)}")
    print("=" * 60)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
