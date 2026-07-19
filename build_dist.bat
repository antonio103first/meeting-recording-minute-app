@echo off
chcp 65001 > nul
title Roundtable - 배포용 빌드 중...

echo ================================================
echo   Roundtable - 배포용 EXE 빌드 스크립트
echo   (Google Drive 없음 / FFmpeg 번들 포함)
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

echo [0/4] FFmpeg 번들 준비 중...
echo.
set FFMPEG_ARG=
where ffmpeg >nul 2>&1
if %errorlevel% == 0 (
    for /f "tokens=*" %%i in ('where ffmpeg') do (
        if "!FFMPEG_FOUND!"=="" (
            set FFMPEG_FOUND=%%i
        )
    )
    for /f "tokens=*" %%i in ('where ffmpeg') do (
        if not exist "%~dp0ffmpeg_bundle" mkdir "%~dp0ffmpeg_bundle"
        copy /Y "%%i" "%~dp0ffmpeg_bundle\ffmpeg.exe" >nul
        echo   FFmpeg 복사 완료: %%i
        set FFMPEG_ARG=--add-binary "ffmpeg_bundle\ffmpeg.exe;."
        goto :ffmpeg_done
    )
) else (
    echo   [경고] FFmpeg을 찾을 수 없습니다. FFmpeg 없이 빌드합니다.
    echo   (사용자가 FFmpeg을 별도 설치해야 MP3 변환 가능)
)
:ffmpeg_done

echo.
echo [1/4] 패키지 설치 중...
%PYTHON% -m pip install -q -r "%~dp0requirements.txt"
%PYTHON% -m pip install -q pyinstaller

echo.
echo [2/4] 배포용 EXE 빌드 중... (1~3분 소요)
echo.

cd /d "%~dp0"

:: onedir — 실행할 때마다 346MB를 임시폴더에 푸는 onefile 방식은 기동에 30~90초가
:: 걸렸다(ffmpeg 201MB가 58%). onedir은 압축 해제 단계가 없어 수 초 만에 뜬다.
:: 배포는 폴더 통째로 전달하고, 바탕화면에는 바로가기를 둔다.
%PYTHON% -m PyInstaller ^
    --onedir ^
    --windowed ^
    --name "Roundtable" ^
    --icon "app_icon.ico" ^
    %FFMPEG_ARG% ^
    --add-data "app_dist\config.py:." ^
    --add-data "app_dist\database.py:." ^
    --add-data "app_dist\recorder.py:." ^
    --add-data "app_dist\gemini_service.py:." ^
    --add-data "app_dist\claude_service.py:." ^
    --add-data "app_dist\clova_service.py:." ^
    --add-data "app_dist\file_manager.py:." ^
    --add-data "app_dist\google_drive.py:." ^
    --add-data "app_dist\prescreen_tab.py:." ^
    --hidden-import "fitz" ^
    --hidden-import "pptx" ^
    --hidden-import "yaml" ^
    --hidden-import "win32com.client" ^
    --hidden-import "pythoncom" ^
    --hidden-import "sounddevice" ^
    --hidden-import "soundfile" ^
    --hidden-import "google.genai" ^
    --hidden-import "google.genai.types" ^
    --hidden-import "google.oauth2.credentials" ^
    --hidden-import "google_auth_oauthlib.flow" ^
    --hidden-import "google.auth.transport.requests" ^
    --hidden-import "googleapiclient.discovery" ^
    --hidden-import "googleapiclient.http" ^
    --hidden-import "googleapiclient.errors" ^
    --hidden-import "anthropic" ^
    --hidden-import "openai" ^
    --hidden-import "markdown" ^
    --hidden-import "requests" ^
    --hidden-import "tkinter" ^
    --hidden-import "tkinter.ttk" ^
    --hidden-import "sqlite3" ^
    --hidden-import "webbrowser" ^
    --distpath "%~dp0dist_배포" ^
    --workpath "%~dp0build_dist_temp" ^
    --specpath "%~dp0." ^
    "app_dist\main.py"

if errorlevel 1 (
    echo.
    echo [오류] 빌드 실패! 위의 오류 메시지를 확인해주세요.
    pause
    exit /b 1
)

echo.
echo [3/4] 빌드 완료!
echo.

echo [4/4] 바탕화면 바로가기 생성 중...
if exist "%USERPROFILE%\Desktop\Roundtable.exe" (
    del /f "%USERPROFILE%\Desktop\Roundtable.exe" >nul 2>&1
)
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\Roundtable.lnk');" ^
  "$s.TargetPath='%~dp0dist_배포\Roundtable\Roundtable.exe';" ^
  "$s.WorkingDirectory='%~dp0dist_배포\Roundtable';" ^
  "$s.IconLocation='%~dp0app_icon.ico';" ^
  "$s.Description='Roundtable - 회의 녹음/요약 + 예비검토보고서';" ^
  "$s.Save()"
if %errorlevel% == 0 (
    echo   바탕화면 바로가기 생성 완료!
) else (
    echo   [경고] 바로가기 생성 실패. 폴더에서 직접 실행하세요.
)

echo.
echo ================================================
echo  실행 파일 위치:
echo  %~dp0dist_배포\Roundtable\Roundtable.exe
echo  (폴더 전체가 필요합니다. exe 하나만 옮기면 실행되지 않습니다)
echo.
echo  배포 방법:
echo  Roundtable.exe 파일 하나만 전달하면 됩니다.
echo  (FFmpeg, Python 별도 설치 불필요)
echo.
echo  수신자 안내:
echo  1. EXE 실행
echo  2. 첫 실행 시 설정 마법사 자동 표시
echo  3. CLOVA Speech API 키 또는 Gemini API 키 입력
echo  4. 설정 탭 -^> Drive 폴더 생성 버튼 클릭 후 업로드 사용
echo ================================================
echo.
pause
