@echo off
chcp 65001 > nul
title 회의녹음요약

echo ================================================
echo   회의녹음요약 앱 시작 중...
echo ================================================
echo.

:: Python 경로 확인
set PYTHON=
where python >nul 2>&1 && set PYTHON=python
if "%PYTHON%"=="" (
    where py >nul 2>&1 && set PYTHON=py
)
if "%PYTHON%"=="" (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo   https://www.python.org 에서 Python을 설치해주세요.
    pause
    exit /b 1
)

echo [1/2] 필요 패키지 확인 및 설치 중...
%PYTHON% -m pip install -q -r "%~dp0requirements.txt" 2>&1
if errorlevel 1 (
    echo [경고] 일부 패키지 설치에 실패했습니다. 계속 진행합니다.
)

echo [2/2] 앱 실행 중...
echo.
cd /d "%~dp0app"
%PYTHON% main.py

if errorlevel 1 (
    echo.
    echo ================================================
    echo [오류] 앱 실행 중 문제가 발생했습니다.
    echo 위의 오류 메시지를 확인해주세요.
    echo ================================================
    pause
)
