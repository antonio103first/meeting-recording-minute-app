@echo off
chcp 65001 > nul
title 회의녹음요약 - 빌드 중...

echo ================================================
echo   회의녹음요약 v3 - exe 빌드 스크립트
echo ================================================
echo.

:: Python 확인
set PYTHON=
where python >nul 2>&1 && set PYTHON=python
if "%PYTHON%"=="" (
    where py >nul 2>&1 && set PYTHON=py
)
if "%PYTHON%"=="" (
    echo [오류] Python이 설치되어 있지 않습니다.
    pause
    exit /b 1
)

echo [1/4] 패키지 설치 중...
%PYTHON% -m pip install -q -r "%~dp0requirements.txt"
%PYTHON% -m pip install -q pyinstaller pillow

echo.
echo [2/4] 앱 아이콘 생성 중...
if exist "%~dp0make_icon.py" (
    %PYTHON% "%~dp0make_icon.py"
) else (
    echo   [건너뜀] make_icon.py 없음
)

echo.
echo [3/4] exe 빌드 중... (1~3분 소요)
echo.

cd /d "%~dp0"

%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "회의녹음요약" ^
    --icon "app_icon.ico" ^
    --add-data "app_dist\config.py:." ^
    --add-data "app_dist\database.py:." ^
    --add-data "app_dist\recorder.py:." ^
    --add-data "app_dist\gemini_service.py:." ^
    --add-data "app_dist\claude_service.py:." ^
    --add-data "app_dist\clova_service.py:." ^
    --add-data "app_dist\file_manager.py:." ^
    --add-data "app_dist\google_drive.py:." ^
    --hidden-import "sounddevice" ^
    --hidden-import "soundfile" ^
    --hidden-import "google.genai" ^
    --hidden-import "google.genai.types" ^
    --hidden-import "google.oauth2.credentials" ^
    --hidden-import "google.auth.transport.requests" ^
    --hidden-import "google_auth_oauthlib.flow" ^
    --hidden-import "googleapiclient.discovery" ^
    --hidden-import "googleapiclient.http" ^
    --hidden-import "googleapiclient.errors" ^
    --hidden-import "anthropic" ^
    --hidden-import "openai" ^
    --hidden-import "requests" ^
    --hidden-import "markdown" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "sqlite3" ^
    --hidden-import "webbrowser" ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build_temp" ^
    --specpath "%~dp0" ^
    "app_dist\main.py"

if errorlevel 1 (
    echo.
    echo [오류] 빌드 실패! 위의 오류 메시지를 확인해주세요.
    pause
    exit /b 1
)

echo.
echo [4/4] 빌드 완료!
echo.
echo ================================================
echo  실행 파일 위치:
echo  %~dp0dist\회의녹음요약.exe
echo ================================================
echo.
echo 위 경로의 exe 파일을 바탕화면에 복사해서 사용하세요.
echo.
pause
