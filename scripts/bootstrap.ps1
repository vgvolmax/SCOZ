$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:SCOZ_STARTUP_STARTED_AT = [DateTime]::UtcNow.ToString('o')
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Data = Join-Path $Root 'data'; New-Item -ItemType Directory -Force -Path $Data | Out-Null
$Log = Join-Path $Data 'launcher.log'

function Write-Log([string]$Message) { Add-Content -LiteralPath $Log -Encoding UTF8 -Value "$([DateTime]::UtcNow.ToString('o')) $Message" }
function Write-Status([string]$Stage,[string]$Message) {
  $status = @{stage=$Stage;message=$Message;startedAt=$env:SCOZ_STARTUP_STARTED_AT;updatedAt=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json
  $tmp = Join-Path $Data 'startup_status.json.tmp'; [IO.File]::WriteAllText($tmp,$status,(New-Object Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $tmp -Destination (Join-Path $Data 'startup_status.json') -Force
}
function Get-VerifiedFile([string]$Uri,[string]$Path,[string]$ExpectedSha) {
  $part = "$Path.part"; Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
  for ($attempt=1; $attempt -le 3; $attempt++) { try { Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $part; break } catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds $attempt } }
  $actual = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $ExpectedSha.ToLowerInvariant()) { Remove-Item $part -Force; throw "Checksum mismatch for $Uri" }
  Move-Item -LiteralPath $part -Destination $Path -Force
}
function File-Sha([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

$ManifestPath=Join-Path $Root 'runtime_manifest.json'; $LockPath=Join-Path $Root 'requirements.lock.txt'
$Manifest=Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
$Runtime=Join-Path $Root 'runtime'; $Python=Join-Path $Runtime 'python.exe'
$ManifestHash=File-Sha $ManifestPath; $LockHash=File-Sha $LockPath
function Test-Runtime {
  if (!(Test-Path -LiteralPath $Python)) { return $false }
  try {
    $marker=Get-Content -Raw -LiteralPath (Join-Path $Runtime '.scoz_runtime.json') | ConvertFrom-Json
    if ($marker.manifestHash -ne $ManifestHash -or $marker.lockHash -ne $LockHash) { return $false }
    & $Python (Join-Path $Root 'scripts\validate_runtime.py') $Root *> $null; return $LASTEXITCODE -eq 0
  } catch { return $false }
}
function Write-Marker([string]$Directory) {
  @{schemaVersion=1;pythonVersion=$Manifest.pythonVersion;architecture=$Manifest.architecture;manifestHash=$ManifestHash;lockHash=$LockHash;createdAt=[DateTime]::UtcNow.ToString('o')} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Directory '.scoz_runtime.json') -Encoding UTF8
}
function Build-Runtime {
  $Staging=Join-Path $Root "runtime.__staging.$PID"; $Old=Join-Path $Root "runtime.__old.$PID"
  Remove-Item -Recurse -Force -LiteralPath $Staging -ErrorAction SilentlyContinue
  try {
    New-Item -ItemType Directory -Path $Staging | Out-Null
    $archive=Join-Path $Staging 'python.zip'; Get-VerifiedFile $Manifest.python.url $archive $Manifest.python.sha256
    Expand-Archive -LiteralPath $archive -DestinationPath $Staging; Remove-Item $archive
    $pth=Get-ChildItem -LiteralPath $Staging -Filter 'python*._pth' | Select-Object -First 1
    @('python313.zip','.','Lib\site-packages','..','import site') | Set-Content -LiteralPath $pth.FullName -Encoding ASCII
    New-Item -ItemType Directory -Force -Path (Join-Path $Staging 'Lib\site-packages') | Out-Null
    $getpip=Join-Path $Staging 'get-pip.py'; Get-VerifiedFile $Manifest.pipBootstrap.url $getpip $Manifest.pipBootstrap.sha256
    & (Join-Path $Staging 'python.exe') $getpip --no-warn-script-location; if ($LASTEXITCODE) { throw 'pip bootstrap failed' }; Remove-Item $getpip
    & (Join-Path $Staging 'python.exe') -m pip install --disable-pip-version-check --only-binary=:all: --no-deps -r $LockPath; if ($LASTEXITCODE) { throw 'dependency install failed' }
    & (Join-Path $Staging 'python.exe') (Join-Path $Root 'scripts\validate_runtime.py') $Root; if ($LASTEXITCODE) { throw 'runtime validation failed' }
    Write-Marker $Staging
    if (Test-Path $Runtime) { Move-Item $Runtime $Old }
    Move-Item $Staging $Runtime
    Remove-Item -Recurse -Force $Old -ErrorAction SilentlyContinue
  } catch { Remove-Item -Recurse -Force $Staging -ErrorAction SilentlyContinue; throw }
}

try {
  Write-Status 'runtime_setup' 'Подготавливаем локальную среду SCOZ'; Write-Log 'Checking project-local runtime'
  if (!(Test-Runtime)) {
    $repaired=$false
    if (Test-Path $Python) { try { & $Python -m pip install --disable-pip-version-check --only-binary=:all: --no-deps -r $LockPath; & $Python (Join-Path $Root 'scripts\validate_runtime.py') $Root; if ($LASTEXITCODE -eq 0) { Write-Marker $Runtime; $repaired=$true } } catch {} }
    if (!$repaired) { Write-Log 'Building verified runtime'; Build-Runtime }
  } else { Write-Log 'Reusing verified runtime' }
  & $Python (Join-Path $Root 'launcher.py') --start; exit $LASTEXITCODE
} catch { Write-Log "Runtime setup failed: $($_.Exception.Message)"; Write-Status 'failed' 'Не удалось подготовить SCOZ. Подробности в launcher.log'; exit 1 }
