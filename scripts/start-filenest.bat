@echo off
setlocal
cd /d "%~dp0.."
echo ==========================================================
echo   FileNest Desktop ^& Storage Manager - Windows Launcher
echo ==========================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-filenest.ps1" %*
endlocal
