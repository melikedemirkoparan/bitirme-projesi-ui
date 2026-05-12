# Patent Drafting Tool - dev environment launcher
# Usage: .\start_dev.ps1
#
# Steps:
#   1) Verify Docker Desktop is running (start it if not)
#   2) Bring up Postgres container, stop the stale app container
#   3) Verify Ollama is reachable
#   4) Activate venv and start uvicorn with --reload limited to app/ and static/

$ErrorActionPreference = "Continue"
$projectRoot = "C:\Users\melike\paten_draft_backend"
Set-Location $projectRoot

Write-Host "=== Patent Drafting Tool - Dev start ===" -ForegroundColor Cyan

# 1) Docker Desktop check
Write-Host "[1/4] Checking Docker Desktop..." -ForegroundColor Yellow
$dockerRunning = $false
try { docker info 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) { $dockerRunning = $true } } catch {}

if (-not $dockerRunning) {
    Write-Host "  Docker Desktop is not running. Starting it..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "  Waiting up to 60 seconds for Docker to be ready..." -ForegroundColor Gray
    $tries = 0
    while ($tries -lt 30) {
        Start-Sleep -Seconds 2
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $dockerRunning = $true; break }
        $tries++
    }
}
if ($dockerRunning) { Write-Host "  OK: Docker is running" -ForegroundColor Green }
else { Write-Host "  ERROR: Docker did not start. Open it manually." -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1 }

# 2) Postgres up + stale app container down
Write-Host "[2/4] Bringing up Postgres container..." -ForegroundColor Yellow
docker-compose up -d db 2>&1 | Out-Null
docker stop paten_draft_backend-app-1 2>&1 | Out-Null
Write-Host "  OK: db is Up; stale app container stopped (port 8000 free)" -ForegroundColor Green

# 3) Ollama check
Write-Host "[3/4] Checking Ollama..." -ForegroundColor Yellow
$ollamaOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ollamaOk = $true }
} catch {}
if ($ollamaOk) { Write-Host "  OK: Ollama is running" -ForegroundColor Green }
else {
    Write-Host "  WARNING: Cannot reach Ollama. Document Assistant will fail." -ForegroundColor Yellow
    Write-Host "  Fix: open the Ollama app or run 'ollama serve'." -ForegroundColor Gray
}

# 4) Activate venv + start uvicorn
Write-Host "[4/4] Starting uvicorn..." -ForegroundColor Yellow
Write-Host ""
Write-Host "App URL: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

& ".\.venv\Scripts\Activate.ps1"
uvicorn app.main:app --reload --reload-dir app --reload-dir static
