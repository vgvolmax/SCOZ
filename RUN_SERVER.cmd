@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist "data" mkdir "data"
for /f %%P in ('powershell.exe -NoLogo -NoProfile -Command "$p = Start-Process -FilePath ([IO.Path]::GetFullPath('runtime\python.exe')) -ArgumentList 'launcher.py','--serve' -WorkingDirectory ([IO.Path]::GetFullPath('.')) -RedirectStandardOutput ([IO.Path]::GetFullPath('data\server_console.log')) -RedirectStandardError ([IO.Path]::GetFullPath('data\server_console.log.err')) -PassThru; $p.Id"') do set "SERVER_PID=%%P"
if not defined SERVER_PID (
  echo Не удалось запустить сервер SCOZ.>>"data\server_console.log"
  exit /b 1
)
>"data\server.pid" echo %SERVER_PID%
exit /b 0
