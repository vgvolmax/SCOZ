param([ValidateSet('Full')][string]$Mode = 'Full')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('SCOZ тест путь ' + [guid]::NewGuid())
$copy = Join-Path $tempRoot 'репозиторий с пробелом'

function Assert($condition, $message) { if (-not $condition) { throw $message } }
function Invoke-Start([switch]$ExpectFailure) {
  $env:SCOZ_NO_BROWSER = '1'
  & cmd.exe /d /c (Join-Path $copy 'start.bat')
  $code = $LASTEXITCODE
  if ($ExpectFailure) { Assert ($code -ne 0) 'start.bat unexpectedly succeeded' } else { Assert ($code -eq 0) "start.bat failed: $code" }
}
function Wait-Health([switch]$Foreign) {
  for ($i=0; $i -lt 120; $i++) { try { $h=Invoke-RestMethod 'http://127.0.0.1:17842/api/health' -TimeoutSec 1; if ($Foreign -or ($h.status -eq 'ok' -and $h.app -eq 'SCOZ' -and $h.version -eq '0.1.0')) { return $h } } catch {}; Start-Sleep -Milliseconds 500 }
  throw 'health timeout'
}
function Stop-Scoz {
  $pidFile=Join-Path $copy 'data/server.pid'; if (Test-Path $pidFile) { $serverPid=[int](Get-Content $pidFile); Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1 }
}

try {
  New-Item -ItemType Directory -Force $copy | Out-Null
  # Release-equivalent tracked copy: git archive excludes .git and every untracked/generated directory.
  $archive=Join-Path $tempRoot 'repo.zip'; & git -C $root archive --format=zip -o $archive HEAD; Assert ($LASTEXITCODE -eq 0) 'git archive failed'
  Expand-Archive $archive $copy
  Assert (-not (Test-Path (Join-Path $copy 'runtime'))) 'runtime leaked into smoke copy'
  Assert (-not (Test-Path (Join-Path $copy 'data'))) 'data leaked into smoke copy'
  Assert (-not (Test-Path (Join-Path $copy 'frontend/node_modules'))) 'node_modules leaked into smoke copy'

  Write-Host '1 FIRST RUN'; Invoke-Start; Wait-Health | Out-Null
  foreach($file in 'startup_status.json','launcher.log','server_console.log','server.pid') { Assert (Test-Path (Join-Path $copy "data/$file")) "missing $file" }

  Write-Host '2 SECOND RUN / RUNTIME REUSE'; Stop-Scoz; $python=Join-Path $copy 'runtime/python.exe'; $before=(Get-Item $python).LastWriteTimeUtc; Invoke-Start; Wait-Health | Out-Null; Assert ((Get-Item $python).LastWriteTimeUtc -eq $before) 'runtime was rebuilt'

  Write-Host '3 ALREADY RUNNING / SAME PID'; $pidBefore=(Get-Content (Join-Path $copy 'data/server.pid')); Invoke-Start; $pidAfter=(Get-Content (Join-Path $copy 'data/server.pid')); Assert ($pidBefore -eq $pidAfter) 'PID changed'; Assert (Get-Process -Id ([int]$pidBefore) -ErrorAction SilentlyContinue) 'server stopped'

  Write-Host '4 DEPENDENCY REPAIR and 8 DATA PRESERVATION'; Stop-Scoz; Set-Content (Join-Path $copy 'data/sentinel.txt') 'keep'; & $python -m pip uninstall -y fastapi | Out-Null; Invoke-Start; Wait-Health | Out-Null; Assert (Test-Path (Join-Path $copy 'data/sentinel.txt')) 'data lost on repair'

  Write-Host '5 DAMAGED RUNTIME / REBUILD'; Stop-Scoz; Set-Content $python 'damaged'; Invoke-Start; Wait-Health | Out-Null; Assert ((Get-Item $python).Length -gt 100000) 'runtime not rebuilt'; Assert (Test-Path (Join-Path $copy 'data/sentinel.txt')) 'data lost on rebuild'

  Write-Host '6 FOREIGN OCCUPIED PORT'; Stop-Scoz
  $foreignScript=Join-Path $tempRoot 'foreign.py'; Set-Content $foreignScript "from http.server import HTTPServer,BaseHTTPRequestHandler`nclass H(BaseHTTPRequestHandler):`n def do_GET(self): self.send_response(200);self.end_headers();self.wfile.write(b'foreign')`n def log_message(self,*a): pass`nHTTPServer(('127.0.0.1',17842),H).serve_forever()"
  $foreign=Start-Process python -ArgumentList $foreignScript -PassThru -WindowStyle Hidden; Start-Sleep -Seconds 1; Invoke-Start -ExpectFailure; Assert (-not $foreign.HasExited) 'foreign listener was killed'; Stop-Process -Id $foreign.Id -Force

  Write-Host '7 SPACES + CYRILLIC passed as all scenarios used the isolated path.'
  Write-Host 'All eight Windows portable scenarios passed.'
} finally { Stop-Scoz; Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
