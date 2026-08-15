param([ValidateSet('Full')][string]$Mode='Full')
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
$Source=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Base=Join-Path $env:TEMP "scoz-smoke-$PID"; $Work=Join-Path $Base 'SCOZ тест\Аналитика'
function Assert($Value,[string]$Message) { if (!$Value) { throw $Message } }
function Wait-PortFree { for($i=0;$i-lt 80;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',17842);$c.Dispose()}catch{return};Start-Sleep -Milliseconds 250};throw 'Port did not become free' }
function Run-Scoz([string]$At) { Push-Location $At; try { $env:SCOZ_NO_BROWSER='1'; $env:CI='1'; cmd /c start.bat; if($LASTEXITCODE){throw "start.bat failed: $LASTEXITCODE"} } finally { Pop-Location } }
function Stop-Scoz([string]$At) { $p=Join-Path $At 'data\server.pid'; if(Test-Path $p){$serverPid=[int](Get-Content $p);Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue;Wait-PortFree} }
try {
  New-Item -ItemType Directory -Force $Work|Out-Null
  Get-ChildItem -Force $Source | Where-Object {$_.Name -notin @('.git','runtime','data','.venv','frontend\node_modules')} | Copy-Item -Destination $Work -Recurse -Force
  Run-Scoz $Work
  Assert (Test-Path (Join-Path $Work 'runtime\python.exe')) 'runtime missing'
  Assert (Test-Path (Join-Path $Work 'runtime\.scoz_runtime.json')) 'marker missing'
  $health=Invoke-RestMethod 'http://127.0.0.1:17842/api/health'; Assert ($health.app -eq 'SCOZ' -and $health.version -eq '0.1.0') 'health mismatch'
  @('launcher.log','startup_status.json','server_console.log','server.pid')|ForEach-Object { Assert (Test-Path (Join-Path $Work "data\$_")) "missing $_" }
  Assert ((Get-Content -Raw (Join-Path $Work 'data\startup_status.json')|ConvertFrom-Json).stage -eq 'ready') 'not ready'
  $marker=(Get-Content -Raw (Join-Path $Work 'runtime\.scoz_runtime.json')|ConvertFrom-Json).createdAt; $pidBefore=Get-Content (Join-Path $Work 'data\server.pid')
  Run-Scoz $Work
  Assert ((Get-Content -Raw (Join-Path $Work 'runtime\.scoz_runtime.json')|ConvertFrom-Json).createdAt -eq $marker) 'runtime rebuilt on second run'
  Assert ((Get-Content (Join-Path $Work 'data\server.pid')) -eq $pidBefore) 'already-running changed PID'
  Stop-Scoz $Work
  $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,17842);$listener.Start()
  Push-Location $Work; try { cmd /c start.bat; Assert ($LASTEXITCODE -ne 0) 'foreign port unexpectedly succeeded'; Assert $listener.Server.IsBound 'listener was stopped' } finally { Pop-Location;$listener.Stop() };Wait-PortFree
  Set-Content (Join-Path $Work 'data\sentinel.txt') 'keep'; $m=Get-Content -Raw (Join-Path $Work 'runtime\.scoz_runtime.json')|ConvertFrom-Json;$m.lockHash='bad';$m|ConvertTo-Json|Set-Content (Join-Path $Work 'runtime\.scoz_runtime.json')
  Run-Scoz $Work; Assert (Test-Path (Join-Path $Work 'data\sentinel.txt')) 'data removed by repair'; Stop-Scoz $Work
  $Bad=Join-Path $Base 'bad checksum';New-Item -ItemType Directory $Bad|Out-Null;Get-ChildItem -Force $Source|Where-Object{$_.Name -notin @('.git','runtime','data','.venv')}|Copy-Item -Destination $Bad -Recurse -Force
  $manifest=Get-Content -Raw (Join-Path $Bad 'runtime_manifest.json')|ConvertFrom-Json;$manifest.python.sha256='0'*64;$manifest|ConvertTo-Json -Depth 5|Set-Content (Join-Path $Bad 'runtime_manifest.json')
  Push-Location $Bad;try{cmd /c start.bat;Assert ($LASTEXITCODE -ne 0) 'bad checksum succeeded'}finally{Pop-Location}
  Assert (!(Test-Path (Join-Path $Bad 'runtime\python.exe'))) 'bad runtime published';Assert (@(Get-ChildItem $Bad -Filter 'runtime.__staging*').Count -eq 0) 'staging remained'
  Assert ((Get-Content -Raw (Join-Path $Bad 'data\launcher.log')) -match 'Checksum mismatch') 'checksum diagnostic missing'
  Write-Host 'PASS: PR1 portable Windows smoke scenarios'
} finally { Remove-Item Env:SCOZ_NO_BROWSER,Env:CI -ErrorAction SilentlyContinue;Stop-Scoz $Work;Remove-Item -Recurse -Force $Base -ErrorAction SilentlyContinue }
