@echo off
setlocal
cd /d "%~dp0"
if not exist "data" mkdir "data"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$out='%CD%\data\server_console.out.part'; $err='%CD%\data\server_console.err.part'; $p = Start-Process -FilePath '%CD%\runtime\python.exe' -ArgumentList @('launcher.py','--serve') -WorkingDirectory '%CD%' -RedirectStandardOutput $out -RedirectStandardError $err -PassThru; Set-Content -LiteralPath '%CD%\data\server.pid' -Value $p.Id -Encoding ascii; $p.WaitForExit(); if (Test-Path $out) { Get-Content $out | Add-Content '%CD%\data\server_console.log'; Remove-Item $out -Force }; if (Test-Path $err) { Get-Content $err | Add-Content '%CD%\data\server_console.log'; Remove-Item $err -Force }; Add-Content -LiteralPath '%CD%\data\server_console.log' -Value ('Server exit code: ' + $p.ExitCode); exit $p.ExitCode"
exit /b %ERRORLEVEL%
