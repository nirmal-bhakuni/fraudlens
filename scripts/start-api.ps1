# Start the FraudLens API cleanly (Windows PowerShell).
# Run from the repo root:  .\scripts\start-api.ps1
$root = Split-Path -Parent $PSScriptRoot

# 1) The Docker engine must be running
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Docker engine is not running. Start Docker Desktop, wait for 'Engine running', then run this script again." -ForegroundColor Red
  exit 1
}

# 2) The database must be up and healthy
docker compose -f "$root\docker-compose.yml" up -d db
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
  $state = docker inspect --format "{{.State.Health.Status}}" fraudlens-db-1 2>$null
  if ($state -eq "healthy") { $healthy = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $healthy) {
  Write-Host "Database container is not healthy. Run: docker compose logs db" -ForegroundColor Red
  exit 1
}

# 3) Free port 8000 (this stops WHATEVER listens there) and clear leftover GEMINI_* variables
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Remove-Item Env:GEMINI_TIMEOUT, Env:GEMINI_MODEL, Env:GEMINI_FALLBACK_MODEL, Env:GEMINI_THINKING_LEVEL -ErrorAction SilentlyContinue

# 4) Start the API
Set-Location "$root\backend"
& "$root\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --reload-dir app
