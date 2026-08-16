@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 exit /b 10

if not exist "data" mkdir "data"
call :log "runtime setup: checking project-local Python"
call :status "runtime setup" "Подготовка локальной среды Python" ""

call :validate_python
if not errorlevel 1 (
  call :validate_dependencies
  if not errorlevel 1 goto launch
  call :log "runtime setup: dependencies need repair"
  call :install_requirements
  if not errorlevel 1 (
    call :validate_dependencies
    if not errorlevel 1 goto launch
  )
  call :log "runtime setup: repair failed; rebuilding runtime only"
  rmdir /s /q "runtime"
) else if exist "runtime" (
  call :log "runtime setup: incomplete or damaged runtime; rebuilding runtime only"
  rmdir /s /q "runtime"
)

call :prepare_runtime
if errorlevel 1 goto failed
call :validate_python
if errorlevel 1 goto failed
call :validate_dependencies
if errorlevel 1 goto failed

:launch
call :log "runtime setup: runtime is ready"
"runtime\python.exe" "launcher.py"
set "SCOZ_EXIT=%ERRORLEVEL%"
if not "%SCOZ_EXIT%"=="0" call :log "failed: launcher returned exit code %SCOZ_EXIT%"
exit /b %SCOZ_EXIT%

:prepare_runtime
call :log "runtime setup: downloading Python 3.13.14"
mkdir "runtime" || exit /b 20
set "PYTHON_ZIP=runtime\python-3.13.14-embed-amd64.zip"
set "PYTHON_PART=%PYTHON_ZIP%.part"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip' -OutFile '%PYTHON_PART%'; if (!(Test-Path -LiteralPath '%PYTHON_PART%') -or (Get-Item -LiteralPath '%PYTHON_PART%').Length -lt 5000000) { throw 'Python archive is missing or too small' }; Add-Type -AssemblyName System.IO.Compression.FileSystem; $z=[IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath '%PYTHON_PART%')); try { if ($z.Entries.Count -eq 0) { throw 'Python archive is empty' } } finally { $z.Dispose() }; Move-Item -Force -LiteralPath '%PYTHON_PART%' -Destination '%PYTHON_ZIP%'; [IO.Compression.ZipFile]::ExtractToDirectory((Resolve-Path -LiteralPath '%PYTHON_ZIP%'), (Resolve-Path -LiteralPath 'runtime'))"
if errorlevel 1 exit /b 21

>"runtime\python313._pth" echo python313.zip
>>"runtime\python313._pth" echo .
>>"runtime\python313._pth" echo Lib\site-packages
>>"runtime\python313._pth" echo ..
>>"runtime\python313._pth" echo import site
if not exist "runtime\Lib\site-packages" mkdir "runtime\Lib\site-packages"

call :log "runtime setup: downloading pip bootstrap"
set "GET_PIP=runtime\get-pip.py"
set "GET_PIP_PART=%GET_PIP%.part"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GET_PIP_PART%'; if (!(Test-Path -LiteralPath '%GET_PIP_PART%') -or (Get-Item -LiteralPath '%GET_PIP_PART%').Length -lt 100000) { throw 'get-pip.py is missing or too small' }; if (-not (Select-String -Quiet -LiteralPath '%GET_PIP_PART%' -SimpleMatch 'pip')) { throw 'get-pip.py content check failed' }; Move-Item -Force -LiteralPath '%GET_PIP_PART%' -Destination '%GET_PIP%'"
if errorlevel 1 exit /b 22
"runtime\python.exe" "runtime\get-pip.py"
if errorlevel 1 exit /b 23
call :install_requirements
exit /b %ERRORLEVEL%

:install_requirements
call :log "runtime setup: installing requirements"
"runtime\python.exe" -m pip install -r "requirements.txt"
exit /b %ERRORLEVEL%

:validate_python
if not exist "runtime\python.exe" exit /b 1
"runtime\python.exe" -c "import platform,sys; raise SystemExit(0 if sys.version_info[:3] == (3,13,14) and sys.platform == 'win32' and platform.machine().upper() in ('AMD64','X86_64') else 1)" >nul 2>&1
exit /b %ERRORLEVEL%

:validate_dependencies
"runtime\python.exe" -c "import importlib.metadata as m; import fastapi,uvicorn; raise SystemExit(0 if m.version('fastapi') == '0.139.2' and m.version('uvicorn') == '0.51.0' else 1)" >nul 2>&1
exit /b %ERRORLEVEL%

:log
echo [%date% %time%] %~1
>>"data\launcher.log" echo [%date% %time%] %~1
exit /b 0

:status
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$p=@{stage='%~1';message='%~2';updated_at=[DateTimeOffset]::UtcNow.ToString('o')}; if ('%~3' -ne '') {$p.ok=[bool]::Parse('%~3')}; $p | ConvertTo-Json | Set-Content -LiteralPath 'data\startup_status.json.tmp' -Encoding utf8; Move-Item -Force -LiteralPath 'data\startup_status.json.tmp' -Destination 'data\startup_status.json'" >nul 2>&1
exit /b 0

:failed
set "SCOZ_EXIT=%ERRORLEVEL%"
call :log "failed: portable runtime setup failed with exit code %SCOZ_EXIT%"
call :status "failed" "Не удалось подготовить локальную среду Python" "False"
exit /b %SCOZ_EXIT%
