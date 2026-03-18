@echo off
chcp 65001 > nul
echo ================================================
echo  회의녹음요약 앱 개발 모드 실행
echo ================================================
echo.

:: 의존성 설치 (최초 1회)
pip install requests google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client > nul 2>&1

:: app 폴더에서 main.py 실행
cd /d "%~dp0app"
python main.py

pause
