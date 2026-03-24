"""
회의녹음요약 앱 - 자동화 테스트 스위트
Sub-agent 검증을 위한 테스트 모음
"""

import sys
import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# 앱 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import config as cfg
import database as db
import naver_stt as stt
import perplexity_summary as perplexity


class TestConfig(unittest.TestCase):
    """설정 모듈 테스트"""

    def setUp(self):
        """테스트 전 임시 설정 파일 경로 설정"""
        self.temp_dir = tempfile.mkdtemp()
        # config 모듈의 경로를 임시 디렉토리로 패치
        self.original_config_file = cfg.CONFIG_FILE
        cfg.CONFIG_FILE = Path(self.temp_dir) / "config.json"
        cfg.APP_DATA_DIR = Path(self.temp_dir)
        cfg.DB_FILE = Path(self.temp_dir) / "meetings.db"

    def tearDown(self):
        cfg.CONFIG_FILE = self.original_config_file

    def test_default_config_structure(self):
        """기본 설정 구조 확인"""
        config = cfg.load_config()
        required_keys = [
            "naver_client_id",
            "naver_client_secret",
            "perplexity_api_key",
            "google_drive_folder_id",
            "google_drive_folder_name",
        ]
        for key in required_keys:
            self.assertIn(key, config, f"설정에 {key}가 없습니다")

    def test_save_and_load_config(self):
        """설정 저장/불러오기 테스트"""
        test_config = {
            "naver_client_id": "test_id_123",
            "naver_client_secret": "test_secret_456",
            "perplexity_api_key": "test_key_789",
            "google_drive_folder_id": "",
            "google_drive_folder_name": "회의녹음요약",
        }
        cfg.save_config(test_config)
        loaded = cfg.load_config()
        self.assertEqual(loaded["naver_client_id"], "test_id_123")
        self.assertEqual(loaded["naver_client_secret"], "test_secret_456")
        self.assertEqual(loaded["perplexity_api_key"], "test_key_789")

    def test_config_complete_check_all_missing(self):
        """모든 API 키 미입력 시 검증 실패 확인"""
        empty_config = {
            "naver_client_id": "",
            "naver_client_secret": "",
            "perplexity_api_key": "",
        }
        ok, missing = cfg.is_config_complete(empty_config)
        self.assertFalse(ok)
        self.assertEqual(len(missing), 3)

    def test_config_complete_check_all_present(self):
        """모든 API 키 입력 시 검증 성공 확인"""
        full_config = {
            "naver_client_id": "id",
            "naver_client_secret": "secret",
            "perplexity_api_key": "key",
        }
        ok, missing = cfg.is_config_complete(full_config)
        self.assertTrue(ok)
        self.assertEqual(len(missing), 0)

    def test_config_complete_check_partial(self):
        """일부 API 키 누락 시 검증 결과 확인"""
        partial_config = {
            "naver_client_id": "id",
            "naver_client_secret": "",
            "perplexity_api_key": "key",
        }
        ok, missing = cfg.is_config_complete(partial_config)
        self.assertFalse(ok)
        self.assertEqual(len(missing), 1)
        self.assertIn("네이버 Client Secret", missing)


class TestDatabase(unittest.TestCase):
    """데이터베이스 모듈 테스트"""

    def setUp(self):
        """테스트용 임시 DB 설정"""
        self.temp_dir = tempfile.mkdtemp()
        cfg.DB_FILE = Path(self.temp_dir) / "test_meetings.db"
        cfg.APP_DATA_DIR = Path(self.temp_dir)
        db.init_database()

    def test_init_database(self):
        """DB 초기화 및 테이블 생성 확인"""
        import sqlite3
        conn = sqlite3.connect(str(cfg.DB_FILE))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meetings'"
        )
        result = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(result, "meetings 테이블이 생성되지 않았습니다")

    def test_save_and_retrieve_meeting(self):
        """회의 저장 및 조회 테스트"""
        meeting_id = db.save_meeting(
            file_name="테스트회의_20240119",
            original_audio_path="/test/audio.mp3",
            stt_text="안녕하세요 테스트 회의입니다.",
            summary_text="## 회의록\n테스트 요약",
            drive_stt_link="https://drive.google.com/test1",
            drive_summary_link="https://drive.google.com/test2",
        )
        self.assertIsInstance(meeting_id, int)
        self.assertGreater(meeting_id, 0)

        meeting = db.get_meeting_by_id(meeting_id)
        self.assertEqual(meeting["file_name"], "테스트회의_20240119")
        self.assertEqual(meeting["stt_text"], "안녕하세요 테스트 회의입니다.")
        self.assertIn("테스트 요약", meeting["summary_text"])

    def test_get_all_meetings_order(self):
        """회의 목록 최신순 정렬 확인"""
        for i in range(3):
            db.save_meeting(
                file_name=f"회의_{i}",
                original_audio_path="",
                stt_text=f"내용 {i}",
                summary_text=f"요약 {i}",
            )

        meetings = db.get_all_meetings()
        self.assertEqual(len(meetings), 3)
        # 최신순 정렬 확인
        self.assertEqual(meetings[0]["file_name"], "회의_2")

    def test_delete_meeting(self):
        """회의 삭제 테스트"""
        meeting_id = db.save_meeting(
            file_name="삭제테스트",
            original_audio_path="",
            stt_text="삭제될 내용",
            summary_text="삭제될 요약",
        )
        db.delete_meeting(meeting_id)
        meeting = db.get_meeting_by_id(meeting_id)
        self.assertEqual(meeting, {})

    def test_nonexistent_meeting(self):
        """존재하지 않는 회의 조회 시 빈 딕셔너리 반환 확인"""
        result = db.get_meeting_by_id(99999)
        self.assertEqual(result, {})


class TestNaverSTT(unittest.TestCase):
    """네이버 STT 모듈 테스트"""

    def test_get_mime_type_mp3(self):
        """MP3 파일 MIME 타입 확인"""
        mime = stt.get_audio_mime_type("test.mp3")
        self.assertEqual(mime, "audio/mpeg")

    def test_get_mime_type_wav(self):
        """WAV 파일 MIME 타입 확인"""
        mime = stt.get_audio_mime_type("test.wav")
        self.assertEqual(mime, "audio/wav")

    def test_get_mime_type_m4a(self):
        """M4A 파일 MIME 타입 확인"""
        mime = stt.get_audio_mime_type("test.m4a")
        self.assertEqual(mime, "audio/mp4")

    def test_get_mime_type_unknown(self):
        """알 수 없는 형식 기본값 확인"""
        mime = stt.get_audio_mime_type("test.xyz")
        self.assertEqual(mime, "audio/mpeg")

    def test_transcribe_nonexistent_file(self):
        """존재하지 않는 파일 변환 시 에러 처리"""
        success, msg = stt.transcribe_audio(
            "/nonexistent/path/audio.mp3",
            client_id="test",
            client_secret="test"
        )
        self.assertFalse(success)
        self.assertIn("찾을 수 없", msg)

    @patch("naver_stt.requests.post")
    def test_transcribe_success(self, mock_post):
        """STT API 성공 응답 처리 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "안녕하세요 회의를 시작하겠습니다."
        }
        mock_post.return_value = mock_response

        # 임시 오디오 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            temp_path = f.name

        try:
            success, result = stt.transcribe_audio(
                temp_path, client_id="test_id", client_secret="test_secret"
            )
            self.assertTrue(success)
            self.assertEqual(result, "안녕하세요 회의를 시작하겠습니다.")
        finally:
            os.unlink(temp_path)

    @patch("naver_stt.requests.post")
    def test_transcribe_auth_failure(self, mock_post):
        """STT API 인증 실패 처리 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"code": "AUTH_ERROR", "message": "Invalid"}
        mock_post.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            temp_path = f.name

        try:
            success, result = stt.transcribe_audio(
                temp_path, client_id="wrong_id", client_secret="wrong_secret"
            )
            self.assertFalse(success)
            self.assertIn("인증 실패", result)
        finally:
            os.unlink(temp_path)

    @patch("naver_stt.requests.post")
    def test_api_key_validation_success(self, mock_post):
        """API 키 검증 성공 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 400  # 빈 데이터 → 400이지만 인증은 성공
        mock_post.return_value = mock_response

        success, msg = stt.test_api_connection("valid_id", "valid_secret")
        self.assertTrue(success)

    @patch("naver_stt.requests.post")
    def test_api_key_validation_failure(self, mock_post):
        """API 키 검증 실패 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        success, msg = stt.test_api_connection("invalid_id", "invalid_secret")
        self.assertFalse(success)


class TestPerplexitySummary(unittest.TestCase):
    """Perplexity 요약 모듈 테스트"""

    def test_empty_text_returns_error(self):
        """빈 텍스트 입력 시 에러 반환 확인"""
        success, msg = perplexity.summarize_meeting("", "test_key")
        self.assertFalse(success)

    def test_whitespace_text_returns_error(self):
        """공백만 있는 텍스트 입력 시 에러 반환 확인"""
        success, msg = perplexity.summarize_meeting("   \n\t  ", "test_key")
        self.assertFalse(success)

    def test_empty_api_key_returns_error(self):
        """빈 API 키 입력 시 에러 반환 확인"""
        success, msg = perplexity.summarize_meeting("회의 내용", "")
        self.assertFalse(success)

    def test_prompt_contains_text(self):
        """프롬프트에 STT 텍스트가 포함되는지 확인"""
        test_text = "안녕하세요 테스트 회의입니다."
        prompt = perplexity.create_meeting_summary_prompt(test_text)
        self.assertIn(test_text, prompt)
        self.assertIn("회의록", prompt)

    def test_long_text_truncation(self):
        """긴 텍스트 처리 (내부 로직 확인)"""
        long_text = "테스트 " * 20000  # 매우 긴 텍스트
        prompt = perplexity.create_meeting_summary_prompt(long_text)
        # 프롬프트 생성은 성공해야 함
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)

    @patch("perplexity_summary.requests.post")
    def test_summarize_success(self, mock_post):
        """요약 API 성공 응답 처리 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "## 회의록\n\n### 1. 회의 개요\n테스트 회의"
                }
            }]
        }
        mock_post.return_value = mock_response

        success, result = perplexity.summarize_meeting(
            "테스트 회의 내용입니다.", "test_api_key"
        )
        self.assertTrue(success)
        self.assertIn("회의록", result)

    @patch("perplexity_summary.requests.post")
    def test_summarize_auth_failure(self, mock_post):
        """요약 API 인증 실패 처리 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {"message": "Invalid API key"}
        }
        mock_post.return_value = mock_response

        success, result = perplexity.summarize_meeting(
            "테스트 내용", "wrong_key"
        )
        self.assertFalse(success)
        self.assertIn("인증 실패", result)


class TestIntegration(unittest.TestCase):
    """통합 테스트 - 전체 처리 흐름"""

    def setUp(self):
        """통합 테스트 환경 설정"""
        self.temp_dir = tempfile.mkdtemp()
        cfg.APP_DATA_DIR = Path(self.temp_dir)
        cfg.DB_FILE = Path(self.temp_dir) / "integration_test.db"
        cfg.CONFIG_FILE = Path(self.temp_dir) / "config.json"
        db.init_database()

    @patch("naver_stt.requests.post")
    @patch("perplexity_summary.requests.post")
    def test_full_pipeline_mock(self, mock_perp, mock_stt):
        """전체 파이프라인 모의 테스트 (API 호출 없이)"""
        # STT API 모의 응답
        stt_response = MagicMock()
        stt_response.status_code = 200
        stt_response.json.return_value = {
            "text": "오늘 회의에서 프로젝트 진행 상황을 점검했습니다. 다음 주까지 개발 완료 예정입니다."
        }
        mock_stt.return_value = stt_response

        # Perplexity API 모의 응답
        perp_response = MagicMock()
        perp_response.status_code = 200
        perp_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": (
                        "## 회의록\n\n"
                        "### 1. 회의 개요\n프로젝트 진행 상황 점검\n\n"
                        "### 2. 결정사항\n다음 주까지 개발 완료"
                    )
                }
            }]
        }
        mock_perp.return_value = perp_response

        # 임시 오디오 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data for testing")
            audio_path = f.name

        try:
            # 1. STT 변환
            stt_ok, stt_text = stt.transcribe_audio(
                audio_path, "test_id", "test_secret"
            )
            self.assertTrue(stt_ok, f"STT 실패: {stt_text}")

            # 2. 요약
            sum_ok, summary = perplexity.summarize_meeting(stt_text, "test_key")
            self.assertTrue(sum_ok, f"요약 실패: {summary}")

            # 3. DB 저장
            meeting_id = db.save_meeting(
                file_name="통합테스트_회의",
                original_audio_path=audio_path,
                stt_text=stt_text,
                summary_text=summary,
                drive_stt_link="https://drive.google.com/stt_test",
                drive_summary_link="https://drive.google.com/sum_test",
            )
            self.assertGreater(meeting_id, 0)

            # 4. 조회 확인
            saved = db.get_meeting_by_id(meeting_id)
            self.assertEqual(saved["file_name"], "통합테스트_회의")
            self.assertIn("점검", saved["stt_text"])
            self.assertIn("회의록", saved["summary_text"])

        finally:
            os.unlink(audio_path)


def run_tests():
    """테스트 실행 및 결과 출력"""
    print("=" * 60)
    print("  회의녹음요약 앱 - 자동화 테스트 시작")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestConfig,
        TestDatabase,
        TestNaverSTT,
        TestPerplexitySummary,
        TestIntegration,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"  총 테스트: {result.testsRun}개")
    print(f"  성공: {result.testsRun - len(result.failures) - len(result.errors)}개")
    print(f"  실패: {len(result.failures)}개")
    print(f"  오류: {len(result.errors)}개")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
