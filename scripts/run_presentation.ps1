# Metro Grid Digital Twin — Presentation Launch Script
# Run this from the project root directory to start everything for the demo.

$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location -LiteralPath $root

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Metro Grid Digital Twin — Launching"   -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Kill any existing servers ---
Write-Host "[1/4] Cleaning old processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "uvicorn" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "vite" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# --- 2. Set up environment ---
Write-Host "[2/4] Setting up environment..." -ForegroundColor Yellow
$env:GRID_TYPE = "ieee14"
$env:DT_LOG_LEVEL = "INFO"
$env:PYTHONPATH = @(
    "$root\platform\dt-contracts\python\src"
    "$root\platform\dt-sim-pandapower"
    "$root\platform\dt-orchestrator"
    "$root\platform\dt-ml"
    "$root\platform\dt-scada-protocols\src"
    "$root\platform\dt-compliance\src"
    "$root\platform\dt-cim\src"
    "$root\platform\dt-bescom\src"
    "$root\platform\dt_security"
    "$root\platform"
) -join ";"

# --- 3. Start the API server ---
Write-Host "[3/4] Starting API server (port 8000)..." -ForegroundColor Yellow
$apiLog = "$root\api_server.log"
Start-Process -NoNewWindow -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", "dt_orchestrator.api.app:app"
    "--host", "127.0.0.1"
    "--port", "8000"
    "--app-dir", "platform/dt-orchestrator"
    "--log-level", "info"
) -RedirectStandardOutput "$root\api_stdout.log" -RedirectStandardError "$root\api_stderr.log"

# Wait for API to start
Start-Sleep -Seconds 5

# Check if it's running
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
    $health = $resp.Content | ConvertFrom-Json
    Write-Host "  API Server: RUNNING (grid=$($health.grid_type), ticks=$($health.metrics.ticks_total))" -ForegroundColor Green
} catch {
    Write-Host "  API Server: FAILED — check api_stderr.log" -ForegroundColor Red
    Get-Content -LiteralPath "$root\api_stderr.log" -Tail 5
    exit 1
}

# --- 4. Start the Dashboard ---
Write-Host "[4/4] Starting Dashboard (port 5173)..." -ForegroundColor Yellow
Set-Location -LiteralPath "$root\platform\dt-dashboard"
Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "run dev" -RedirectStandardOutput "$root\dash_out.log" -RedirectStandardError "$root\dash_err.log"
Set-Location -LiteralPath $root

Start-Sleep -Seconds 3

# Open browser
Start-Process "http://127.0.0.1:5173"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SYSTEM IS LIVE"                        -ForegroundColor Green
Write-Host "  Dashboard : http://127.0.0.1:5173"     -ForegroundColor Green
Write-Host "  API       : http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "  Health    : http://127.0.0.1:8000/health" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers when done."
Write-Host "Logs: api_stdout.log, api_stderr.log, dash_out.log, dash_err.log"

# Keep script alive
while ($true) {
    Start-Sleep -Seconds 10
    # Periodic health check
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 3
    } catch {
        Write-Host "`n[WARN] API server not responding — check api_stderr.log" -ForegroundColor Red
    }
}
