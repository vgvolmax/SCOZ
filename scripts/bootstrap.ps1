$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Root 'runtime'
$Data = Join-Path $Root 'data'
$Log = Join-Path $Data 'launcher.log'
$ManifestPath = Join-Path $Root 'runtime_manifest.json'
$LockPath = Join-Path $Root 'requirements.lock.txt'
$env:SCOZ_STARTUP_STARTED_AT = [DateTime]::UtcNow.ToString('o')

New-Item -ItemType Directory -Force -Path $Data | Out-Null
function Write-Log([string]$Message) { Add-Content -LiteralPath $Log -Encoding utf8 -Value "$([DateTime]::UtcNow.ToString('o')) $Message" }
function Write-Status([string]$Stage, [string]$Message) {
  $path = Join-Path $Data 'startup_status.json'; $temp = "$path.tmp"
  @{ stage=$Stage; message=$Message; startedAt=$env:SCOZ_STARTUP_STARTED_AT; updatedAt=[DateTime]::UtcNow.ToString('o') } |
    ConvertTo-Json | Set-Content -LiteralPath $temp -Encoding utf8
  Move-Item -LiteralPath $temp -Destination $path -Force
}
function Get-Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Get-VerifiedFile([string]$Uri, [string]$Destination, [string]$ExpectedSha) {
  $part = "$Destination.part"; Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
  for ($attempt=1; $attempt -le 3; $attempt++) {
    try { Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $part; break }
    catch { if ($attempt -eq 3) { throw }; Start-Sleep -Seconds $attempt }
  }
  $actual = Get-Hash $part
  if ($actual -ne $ExpectedSha.ToLowerInvariant()) { Remove-Item $part -Force; throw "Checksum mismatch for $Uri" }
  Move-Item -LiteralPath $part -Destination $Destination -Force
}
function Test-Runtime([object]$Manifest) {
  if (-not (Test-Path (Join-Path $Runtime 'python.exe'))) { return $false }
  & (Join-Path $Runtime 'python.exe') (Join-Path $Root 'scripts\validate_runtime.py') $Root
  if ($LASTEXITCODE -ne 0) { return $false }
  $markerPath = Join-Path $Runtime '.scoz_runtime.json'
  if (-not (Test-Path $markerPath)) { return $false }
  $marker = Get-Content -Raw $markerPath | ConvertFrom-Json
  return $marker.manifestSha256 -eq (Get-Hash $ManifestPath) -and $marker.lockSha256 -eq (Get-Hash $LockPath)
}
function Install-Lock([string]$Python) {
  & $Python -m pip install --only-binary=:all: --no-deps -r $LockPath
  if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
}
function Build-Runtime([object]$Manifest) {
  $staging = Join-Path $Root "runtime.__staging.$PID"
  $old = Join-Path $Root "runtime.__old.$PID"
  $download = Join-Path $env:TEMP "scoz-python-$PID.zip"
  $getPip = Join-Path $env:TEMP "scoz-get-pip-$PID.py"
  Remove-Item -Recurse -Force $staging,$old -ErrorAction SilentlyContinue
  try {
    Write-Log 'Downloading pinned Python runtime'
    Get-VerifiedFile $Manifest.python.url $download $Manifest.python.sha256
    New-Item -ItemType Directory $staging | Out-Null
    Expand-Archive -LiteralPath $download -DestinationPath $staging
    $pth = Join-Path $staging 'python313._pth'
    @('python313.zip','.','Lib\site-packages','..','import site') | Set-Content -LiteralPath $pth -Encoding ascii
    New-Item -ItemType Directory -Force (Join-Path $staging 'Lib\site-packages') | Out-Null
    Get-VerifiedFile $Manifest.pipBootstrap.url $getPip $Manifest.pipBootstrap.sha256
    & (Join-Path $staging 'python.exe') $getPip --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed' }
    Install-Lock (Join-Path $staging 'python.exe')
    & (Join-Path $staging 'python.exe') (Join-Path $Root 'scripts\validate_runtime.py') $Root
    if ($LASTEXITCODE -ne 0) { throw 'Staging runtime validation failed' }
    @{ schemaVersion=1; pythonVersion=$Manifest.pythonVersion; architecture=$Manifest.architecture;
       manifestSha256=(Get-Hash $ManifestPath); lockSha256=(Get-Hash $LockPath); createdAt=[DateTime]::UtcNow.ToString('o') } |
       ConvertTo-Json | Set-Content -LiteralPath (Join-Path $staging '.scoz_runtime.json') -Encoding utf8
    if (Test-Path $Runtime) { Move-Item -LiteralPath $Runtime -Destination $old }
    try { Move-Item -LiteralPath $staging -Destination $Runtime }
    catch {
      if ((Test-Path $old) -and -not (Test-Path $Runtime)) { Move-Item -LiteralPath $old -Destination $Runtime }
      throw
    }
    Remove-Item -Recurse -Force $old -ErrorAction SilentlyContinue
  } finally {
    Remove-Item -Force $download,$getPip -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $staging -ErrorAction SilentlyContinue
  }
}

try {
  Write-Status 'runtime_setup' 'Подготавливаем локальную среду SCOZ'
  $manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
  if ($manifest.schemaVersion -ne 1 -or $manifest.pythonVersion -ne '3.13.14' -or $manifest.architecture -ne 'amd64') { throw 'Invalid runtime manifest' }
  if (-not (Test-Runtime $manifest)) {
    $repaired = $false
    if (Test-Path (Join-Path $Runtime 'python.exe')) {
      try { Write-Log 'Repairing runtime dependencies'; Install-Lock (Join-Path $Runtime 'python.exe'); $repaired = Test-Runtime $manifest } catch { Write-Log "Repair failed: $_" }
    }
    if (-not $repaired) { Build-Runtime $manifest }
  } else { Write-Log 'Reusing verified runtime' }
  & (Join-Path $Runtime 'python.exe') (Join-Path $Root 'launcher.py') --start
  exit $LASTEXITCODE
} catch {
  Write-Log "Runtime setup failed: $_"
  Write-Status 'failed' 'Не удалось подготовить локальную среду SCOZ'
  exit 1
}
