@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo SCOZ не удалось запустить.
  echo Лог: %~dp0data\launcher.log
  pause
)
exit /b %EXIT_CODE%
