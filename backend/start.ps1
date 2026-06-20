# Start Conditia API — kills anything on port 8000 first, then starts v0.2.0
$ErrorActionPreference = "SilentlyContinue"

Write-Host "Stopping processes on port 8001..."
Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { $_.OwningProcess } |
    Select-Object -Unique |
    ForEach-Object {
        if ($_ -gt 0) {
            Write-Host "  Killing PID $_"
            Stop-Process -Id $_ -Force
        }
    }

Start-Sleep -Seconds 2

Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "Creating venv and installing deps..."
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
} else {
    .\.venv\Scripts\Activate.ps1
}

Write-Host ""
Write-Host "Starting Conditia API on http://127.0.0.1:8001"
Write-Host "After startup, verify: Invoke-RestMethod http://127.0.0.1:8001/health"
Write-Host ""

python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
