<#
.SYNOPSIS
    FileNest Desktop & Storage Manager - Windows Launch & Supervision Script
.DESCRIPTION
    Starts the FastAPI backend service and Tauri 2 desktop client with health supervision.
#>

[CmdletBinding()]
param (
    [switch]$BuildFirst,
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  FileNest Desktop & Storage Manager" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python virtual environment
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Please initialize using: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# 2. Build frontend if requested
if ($BuildFirst) {
    Write-Host "[1/3] Building frontend production bundle..." -ForegroundColor Yellow
    pnpm run build
}

# 3. Launch FastAPI backend
Write-Host "[2/3] Starting backend service at http://${HostAddress}:${Port}..." -ForegroundColor Yellow
$BackendProcess = Start-Process -FilePath $PythonExe `
    -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", $HostAddress, "--port", "$Port" `
    -WorkingDirectory $ProjectRoot `
    -PassThru

# 4. Wait for backend health
Write-Host "Waiting for backend health endpoint..." -NoNewline
$Healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $res = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/api/v1/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($res.status -eq "ok") {
            $Healthy = $true
            break
        }
    } catch {
        # Waiting
    }
    Start-Sleep -Milliseconds 500
    Write-Host "." -NoNewline
}
Write-Host ""

if (-not $Healthy) {
    Write-Host "[ERROR] Backend service failed to start or report health." -ForegroundColor Red
    Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "[OK] Backend healthy! PID: $($BackendProcess.Id)" -ForegroundColor Green

# 5. Launch Tauri desktop app
Write-Host "[3/3] Launching Tauri desktop application..." -ForegroundColor Yellow
try {
    pnpm run desktop
} finally {
    Write-Host "Shutting down background services..." -ForegroundColor Cyan
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "FileNest session ended cleanly." -ForegroundColor Green
}
