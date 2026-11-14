@echo off
call "%~dp0scripts\build-installer.bat" %*
exit /b %ERRORLEVEL%
