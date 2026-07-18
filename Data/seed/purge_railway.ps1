# =========================================================
# purge_railway.ps1 - purge Railway DBs via public TCP proxy
# Set env vars first (same as load_seed_railway.ps1).
# =========================================================
$ErrorActionPreference = 'Stop'
$Repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $Repo 'Backend\scripts\purge_db_railway.py'))) {
  $Repo = (Get-Location).Path
}

if (-not $env:DATABASE_PUBLIC_URL) { throw "Set DATABASE_PUBLIC_URL first." }
if (-not $env:NEO4J_PASSWORD) { throw "Set NEO4J_PASSWORD first." }

$py = Join-Path $Repo 'Backend\scripts\purge_db_railway.py'
$extra = $args
if ($extra.Count -eq 0) { $extra = @('--scope', 'legal', '--yes') }

Write-Host "Running purge_db_railway.py $extra ..." -ForegroundColor Cyan
& python $py @extra
if ($LASTEXITCODE -ne 0) { throw "purge_db_railway.py failed (exit $LASTEXITCODE)" }
