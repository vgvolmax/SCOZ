param([ValidateSet('Full')][string]$Mode = 'Full')
$ErrorActionPreference = 'Stop'
$Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Base = Join-Path ([IO.Path]::GetTempPath()) "SCOZ тест $PID"
$Work = Join-Path $Base 'Аналитика'
$Bad = Join-Path $Base 'Плохая сумма'
$env:SCOZ_NO_BROWSER = '1'

function New-ReleaseCopy([string]$Destination) {
  New-Item -ItemType Directory -Force $Destination | Out-Null
  $archive = Join-Path $Base "tracked-$([guid]::NewGuid()).zip"
  & git -C $Source archive --format=zip -o $archive HEAD
  if ($LASTEXITCODE -ne 0) { throw 'Could not create tracked-files release copy' }
  Expand-Archive -LiteralPath $archive -DestinationPath $Destination
  Remove-Item $archive
  foreach ($forbidden in @('.git','runtime','data','.venv','.lock-venv','frontend\node_modules')) {
    if (Test-Path (Join-Path $Destination $forbidden)) { throw "Generated path copied: $forbidden" }
  }
}
function Invoke-Start([string]$Directory, [bool]$ExpectSuccess = $true) {
  Push-Location $Directory
  try { & cmd.exe /d /c start.bat '<nul'; $code = $LASTEXITCODE }
  finally { Pop-Location }
  if ($ExpectSuccess -and $code -ne 0) { throw "start.bat failed: $code" }
  if (-not $ExpectSuccess -and $code -eq 0) { throw 'start.bat unexpectedly succeeded' }
}
function Wait-PortFree { for ($i=0;$i -lt 80;$i++) { try { $c=[Net.Sockets.TcpClient]::new('127.0.0.1',17842); $c.Dispose() } catch { return }; Start-Sleep -Milliseconds 250 }; throw 'Port did not become free' }

try {
  Remove-Item -Recurse -Force $Base -ErrorAction SilentlyContinue
  New-ReleaseCopy $Work
  Invoke-Start $Work
  foreach ($path in @('runtime\python.exe','runtime\.scoz_runtime.json','data\launcher.log','data\startup_status.json','data\server_console.log','data\server.pid')) {
    if (-not (Test-Path (Join-Path $Work $path))) { throw "First run missing $path" }
  }
  $health = Invoke-RestMethod 'http://127.0.0.1:17842/api/health'
  if ($health.status -ne 'ok' -or $health.app -ne 'SCOZ' -or $health.version -ne '0.1.0') { throw 'Exact health failed' }
  $created = (Get-Content -Raw (Join-Path $Work 'runtime\.scoz_runtime.json') | ConvertFrom-Json).createdAt
  $pidBefore = [int](Get-Content (Join-Path $Work 'data\server.pid'))
  Invoke-Start $Work
  $marker = Get-Content -Raw (Join-Path $Work 'runtime\.scoz_runtime.json') | ConvertFrom-Json
  if ($marker.createdAt -ne $created) { throw 'Second run rebuilt runtime' }
  Invoke-Start $Work
  if ([int](Get-Content (Join-Path $Work 'data\server.pid')) -ne $pidBefore) { throw 'Already-running replaced server PID' }
  Stop-Process -Id $pidBefore -Force; Wait-PortFree

  $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,17842); $listener.Start()
  try { Invoke-Start $Work $false; if (-not $listener.Server.IsBound) { throw 'Foreign listener was stopped' } } finally { $listener.Stop() }
  Wait-PortFree

  Set-Content -LiteralPath (Join-Path $Work 'data\sentinel.txt') -Value 'keep'
  $marker.lockSha256 = ('0' * 64)
  $marker | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Work 'runtime\.scoz_runtime.json')
  Invoke-Start $Work
  if (-not (Test-Path (Join-Path $Work 'data\sentinel.txt'))) { throw 'Data sentinel was lost' }
  $pidRepaired = [int](Get-Content (Join-Path $Work 'data\server.pid')); Stop-Process -Id $pidRepaired -Force; Wait-PortFree

  New-ReleaseCopy $Bad
  $manifestPath = Join-Path $Bad 'runtime_manifest.json'
  $manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json; $manifest.python.sha256 = ('0' * 64)
  $manifest | ConvertTo-Json -Depth 5 | Set-Content $manifestPath
  Invoke-Start $Bad $false
  if (Test-Path (Join-Path $Bad 'runtime\python.exe')) { throw 'Bad artifact was published' }
  if (Get-ChildItem $Bad -Directory -Filter 'runtime.__staging.*') { throw 'Staging was left behind' }
  Write-Host 'All PR1 Windows smoke scenarios passed.'
} finally {
  Remove-Item Env:SCOZ_NO_BROWSER -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force $Base -ErrorAction SilentlyContinue
}
