@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
if not exist "data" mkdir "data"
set "LOG=data\launcher.log"
set "PYTHON_URL=https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "PYTHON_ARCHIVE=runtime\python-3.13.14-embed-amd64.zip"

call :stage "runtime setup" "Проверяем локальную среду Python"
if not exist "runtime\python.exe" goto rebuild
call :python_valid
if errorlevel 1 goto rebuild
call :dependencies_valid
if not errorlevel 1 goto launch

call :stage "runtime setup" "Восстанавливаем зависимости"
"runtime\python.exe" -m pip install -r "requirements.txt" >>"%LOG%" 2>&1
if errorlevel 1 goto rebuild
call :dependencies_valid
if not errorlevel 1 goto launch

:rebuild
call :stage "runtime setup" "Подготавливаем локальную среду Python"
if exist "runtime" rmdir /s /q "runtime"
mkdir "runtime" || goto fail
call :download_python || goto fail
call :configure_runtime || goto fail
call :bootstrap_pip || goto fail
"runtime\python.exe" -m pip install -r "requirements.txt" >>"%LOG%" 2>&1 || goto fail
call :python_valid || goto fail
call :dependencies_valid || goto fail

:launch
call :stage "runtime setup" "Локальная среда готова"
"runtime\python.exe" "launcher.py"
exit /b %errorlevel%

:download_python
set "PART=%PYTHON_ARCHIVE%.part"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri '%PYTHON_URL%' -OutFile '%PART%'; if ((Get-Item '%PART%').Length -lt 10000000) { throw 'Архив Python слишком мал' }; Add-Type -AssemblyName System.IO.Compression.FileSystem; $z=[IO.Compression.ZipFile]::OpenRead((Resolve-Path '%PART%')); try { if ($z.Entries.Count -eq 0) { throw 'Архив Python пуст' } } finally { $z.Dispose() }; Move-Item -Force '%PART%' '%PYTHON_ARCHIVE%'; [IO.Compression.ZipFile]::ExtractToDirectory((Resolve-Path '%PYTHON_ARCHIVE%'), (Resolve-Path 'runtime'))" >>"%LOG%" 2>&1
exit /b %errorlevel%

:configure_runtime
>"runtime\python313._pth" (
 echo python313.zip
 echo .
 echo Lib\site-packages
 echo ..
 echo import site
)
if not exist "runtime\Lib\site-packages" mkdir "runtime\Lib\site-packages"
exit /b 0

:bootstrap_pip
set "PIP_FILE=runtime\get-pip.py"
set "PIP_PART=runtime\get-pip.py.part"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri '%GET_PIP_URL%' -OutFile '%PIP_PART%'; $f=Get-Item '%PIP_PART%'; if ($f.Length -lt 1000000) { throw 'get-pip.py слишком мал' }; $head=[IO.File]::ReadAllText($f.FullName); if ($head -notmatch 'pip') { throw 'Некорректный get-pip.py' }; Move-Item -Force '%PIP_PART%' '%PIP_FILE%'" >>"%LOG%" 2>&1 || exit /b 1
"runtime\python.exe" "%PIP_FILE%" >>"%LOG%" 2>&1
exit /b %errorlevel%

:python_valid
"runtime\python.exe" -c "import platform,sys; raise SystemExit(0 if sys.version_info[:3] == (3,13,14) and sys.platform == 'win32' and platform.machine().lower() in ('amd64','x86_64') else 1)" >>"%LOG%" 2>&1
exit /b %errorlevel%

:dependencies_valid
"runtime\python.exe" -c "import importlib.metadata as m; import fastapi,uvicorn; raise SystemExit(0 if m.version('fastapi') == '0.139.2' and m.version('uvicorn') == '0.51.0' else 1)" >>"%LOG%" 2>&1
exit /b %errorlevel%

:stage
echo [%~1] %~2
echo [%date% %time%] [%~1] %~2>>"%LOG%"
exit /b 0

:fail
call :stage "failed" "Не удалось подготовить SCOZ. Подробности: data\launcher.log"
if exist "%PYTHON_ARCHIVE%.part" del /q "%PYTHON_ARCHIVE%.part"
if exist "runtime\get-pip.py.part" del /q "runtime\get-pip.py.part"
exit /b 1
