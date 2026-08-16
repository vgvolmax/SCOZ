param([ValidateSet('Full')][string]$Mode = 'Full')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cyrillicTest = -join @(
    [char]0x0422,
    [char]0x0435,
    [char]0x0441,
    [char]0x0442
)
$cyrillicApp = -join @(
    [char]0x043F,
    [char]0x0440,
    [char]0x0438,
    [char]0x043B,
    [char]0x043E,
    [char]0x0436,
    [char]0x0435,
    [char]0x043D,
    [char]0x0438,
    [char]0x0435
)
$sandbox = Join-Path ([IO.Path]::GetTempPath()) ("SCOZ smoke $cyrillicTest with spaces " + [guid]::NewGuid())
$app = Join-Path $sandbox "SCOZ $cyrillicApp"
$env:SCOZ_NO_BROWSER = '1'

function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Invoke-Start([bool]$ExpectSuccess = $true) {
    Push-Location $app
    try { & cmd.exe /d /c start.bat; $code = $LASTEXITCODE }
    finally { Pop-Location }
    if ($ExpectSuccess -and $code -ne 0) { throw "start.bat failed: $code" }
    if (-not $ExpectSuccess -and $code -eq 0) { throw 'start.bat unexpectedly succeeded' }
    return $code
}
function Health {
    $h = Invoke-RestMethod -Uri 'http://127.0.0.1:17842/api/health' -TimeoutSec 3
    Assert-True ($h.status -eq 'ok' -and $h.app -eq 'SCOZ' -and $h.version -eq '0.1.0') 'Health identity mismatch'
}
function Stop-Scoz {
    $pidFile = Join-Path $app 'data/server.pid'
    if (Test-Path $pidFile) { $serverId = [int](Get-Content $pidFile); Stop-Process -Id $serverId -Force -ErrorAction SilentlyContinue; Start-Sleep 2 }
}

try {
    New-Item -ItemType Directory -Path $app -Force | Out-Null
    & robocopy.exe $root $app /E /XD (Join-Path $root 'runtime') (Join-Path $root 'data') (Join-Path $root '.venv') (Join-Path $root '.git') '__pycache__' '.pytest_cache' /XF '*.pyc' | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $LASTEXITCODE" }

    Write-Host '1. CLEAN FIRST RUN'
    Invoke-Start | Out-Null; Health
    Assert-True (Test-Path (Join-Path $app 'runtime/python.exe')) 'Runtime was not prepared'

    Write-Host '2. SECOND RUN / REUSE'
    Stop-Scoz
    $pythonTime = (Get-Item (Join-Path $app 'runtime/python.exe')).LastWriteTimeUtc
    $countBefore = @(
        Select-String -Path (Join-Path $app 'data/launcher.log') -SimpleMatch 'runtime setup: installing requirements' -ErrorAction SilentlyContinue
    ).Count
    Invoke-Start | Out-Null; Health
    $countAfter = @(
        Select-String -Path (Join-Path $app 'data/launcher.log') -SimpleMatch 'runtime setup: installing requirements' -ErrorAction SilentlyContinue
    ).Count
    Assert-True ((Get-Item (Join-Path $app 'runtime/python.exe')).LastWriteTimeUtc -eq $pythonTime) 'Runtime was rebuilt instead of reused'
    Assert-True ($countAfter -eq $countBefore) 'Reuse unexpectedly installed packages'

    Write-Host '3. ALREADY RUNNING'
    $originalPid = [int](Get-Content (Join-Path $app 'data/server.pid'))
    Invoke-Start | Out-Null
    Assert-True ([int](Get-Content (Join-Path $app 'data/server.pid')) -eq $originalPid) 'PID changed'
    Assert-True ($null -ne (Get-Process -Id $originalPid -ErrorAction SilentlyContinue)) 'Original server stopped'

    Write-Host '4. DEPENDENCY REPAIR'
    Stop-Scoz
    Set-Content (Join-Path $app 'data/sentinel.txt') 'preserve'
    Remove-Item (Join-Path $app 'runtime/Lib/site-packages/fastapi') -Recurse -Force
    Invoke-Start | Out-Null; Health
    Assert-True ((Get-Content (Join-Path $app 'data/launcher.log') -Tail 20) -match 'dependencies need repair') 'Repair was not recorded'
    Assert-True (Test-Path (Join-Path $app 'data/sentinel.txt')) 'data/ sentinel was lost during repair'
    Assert-True ((Get-Content (Join-Path $app 'data/sentinel.txt')) -eq 'preserve') 'data/ sentinel changed during repair'

    Write-Host '5 + 8. DAMAGED RUNTIME / DATA PRESERVATION'
    Stop-Scoz
    Set-Content (Join-Path $app 'runtime/python.exe') 'damaged'
    Invoke-Start | Out-Null; Health
    Assert-True (Test-Path (Join-Path $app 'data/sentinel.txt')) 'data/ sentinel was lost during rebuild'
    Assert-True ((Get-Content (Join-Path $app 'data/sentinel.txt')) -eq 'preserve') 'data/ sentinel changed during rebuild'

    Write-Host '6. FOREIGN PORT'
    Stop-Scoz
    $foreign = Start-Process -FilePath (Join-Path $app 'runtime/python.exe') -ArgumentList @('-m','http.server','17842','--bind','127.0.0.1') -WorkingDirectory $app -PassThru -WindowStyle Hidden
    Start-Sleep 2
    Invoke-Start $false | Out-Null
    Assert-True ($null -ne (Get-Process -Id $foreign.Id -ErrorAction SilentlyContinue)) 'Foreign listener was killed'
    Stop-Process -Id $foreign.Id -Force

    Write-Host '7. SPACES + CYRILLIC PATH'
    Invoke-Start | Out-Null; Health
    Write-Host 'PASS: all 8 PR1 Windows smoke scenarios'
}
finally {
    Stop-Scoz
    Remove-Item $sandbox -Recurse -Force -ErrorAction SilentlyContinue
}
