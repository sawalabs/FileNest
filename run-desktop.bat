@echo off
title FileNest — Desktop & Storage Manager Launcher
cd /d "%~dp0"

echo ====================================================
echo   FileNest - Desktop & Storage Manager Launcher
echo ====================================================
echo.

echo [1/2] Checking Python FastAPI backend (port 8000)...
netstat -ano | findstr /R ":8000 .*LISTENING" >nul
if %errorlevel% neq 0 (
    echo Starting Python backend in background...
    start /b "" .venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
    timeout /t 2 /nobreak >nul
) else (
    echo Python backend is already running on port 8000.
)

echo.
echo [2/2] Launching Tauri Desktop Shell...
pnpm run desktop

pause
