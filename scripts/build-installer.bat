@echo off
setlocal
cd /d "%~dp0.."

set INTERACTIVE=0
set PS_ARGS=-Mode lite

if /I "%~1"=="quick" (
    set PS_ARGS=-Mode lite -SkipBackend
    goto :run
)
if /I "%~1"=="lite" (
    set PS_ARGS=-Mode lite
    goto :run
)
if /I "%~1"=="full" (
    set PS_ARGS=-Mode full
    goto :run
)
if /I "%~1"=="test" (
    set PS_ARGS=-Mode lite -RunTests
    goto :run
)

set INTERACTIVE=1
echo ==========================================================
echo   FileNest Desktop - Windows Installer Builder
echo ==========================================================
echo.
echo Choose installer build mode:
echo   [1] Lite Installer (Default - Fast ~39 MB, Native Windows OCR)
echo   [2] Quick Rebuild  (Frontend + Tauri only - ~20s, reuses backend)
echo   [3] Full Offline   (Includes PaddleOCR offline models)
echo.
set /p CHOICE="Enter choice (1, 2, or 3, default 1): "

if "%CHOICE%"=="2" (
    set PS_ARGS=-Mode lite -SkipBackend
) else if "%CHOICE%"=="3" (
    set PS_ARGS=-Mode full
) else (
    set PS_ARGS=-Mode lite
)

:run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-installer.ps1" %PS_ARGS%
set EXIT_CODE=%ERRORLEVEL%

if "%INTERACTIVE%"=="1" (
    echo.
    pause
)
endlocal & exit /b %EXIT_CODE%
