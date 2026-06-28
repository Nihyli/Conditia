# Start Conditia API (v0.3.0) - ensures venv, migrations, then uvicorn on :8001
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

# Prefer .venv2 when the original .venv is locked/corrupt on Windows.
$VenvCandidates = @(".venv2", ".venv")

function Stop-AllConditiaPython {
    Write-Host "Stopping processes that may lock .venv..."

    Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { $_.OwningProcess } |
        Select-Object -Unique |
        ForEach-Object {
            if ($_ -gt 0) {
                Write-Host "  Killing listener PID $_"
                Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
            }
        }

    foreach ($name in @("uvicorn", "python", "pythonw")) {
        taskkill /F /IM "$name.exe" /T 2>$null | Out-Null
    }

    $marker = "conditia\backend"
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match "python" -and (
                $_.CommandLine -like "*$marker*" -or
                $_.ExecutablePath -like "*$marker*"
            )
        } |
        ForEach-Object {
            Write-Host "  Killing $($_.Name) PID $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

    Start-Sleep -Seconds 3
}

function Test-VenvHealthy {
    param(
        [string]$PythonExe,
        [switch]$Verbose
    )
    if (-not (Test-Path $PythonExe)) { return $false }
    $code = @'
import alembic
import fastapi
import pydantic
import sqlalchemy
'@
    $output = & $PythonExe -c $code 2>&1
    if ($LASTEXITCODE -ne 0) {
        if ($Verbose) {
            Write-Host "Venv health check failed for $PythonExe"
            if ($output) { Write-Host $output }
        }
        return $false
    }
    return $true
}

function Get-ActiveVenv {
    foreach ($name in $VenvCandidates) {
        $py = Join-Path $PSScriptRoot "$name\Scripts\python.exe"
        if (Test-VenvHealthy -PythonExe $py) {
            return @{
                Name     = $name
                Python   = $py
                Activate = Join-Path $PSScriptRoot "$name\Scripts\Activate.ps1"
            }
        }
    }
    return $null
}

function Remove-VenvDir {
    param([string]$Name)
    $venv = Join-Path $PSScriptRoot $Name
    if (-not (Test-Path $venv)) { return $true }

    for ($i = 1; $i -le 3; $i++) {
        Stop-AllConditiaPython
        try {
            Remove-Item -Recurse -Force $venv -ErrorAction Stop
            Write-Host "Removed $Name"
            return $true
        } catch {
            Write-Host "  $Name still locked (attempt $i/3)..."
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

function Install-Requirements {
    param([string]$PythonExe)
    & $PythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed"
    }
    for ($i = 1; $i -le 3; $i++) {
        Write-Host "pip install attempt $i/3..."
        & $PythonExe -m pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "  pip failed - retrying after cleanup..."
        Stop-AllConditiaPython
        Start-Sleep -Seconds 5
    }
    throw "pip install failed. Close Cursor, open Windows Terminal, run: python -m venv .venv2; .\.venv2\Scripts\Activate.ps1; pip install -r requirements.txt"
}

Stop-AllConditiaPython

$active = Get-ActiveVenv

if ($null -eq $active) {
    Write-Host ""
    Write-Host "No healthy virtualenv found - creating one..."

    $targetName = ".venv2"
    if (-not (Remove-VenvDir -Name $targetName)) {
        throw "Could not prepare $targetName. Reboot, then run start.ps1 again."
    }

    # If .venv is locked, use .venv2 and leave the old folder alone.
    if (Test-Path (Join-Path $PSScriptRoot ".venv")) {
        Write-Host "Note: old .venv is locked; using .venv2 instead (safe to delete .venv later)."
    }

    python -m venv $targetName
    if ($LASTEXITCODE -ne 0) { throw "python -m venv $targetName failed" }

    $py = Join-Path $PSScriptRoot "$targetName\Scripts\python.exe"
    Install-Requirements -PythonExe $py
    $active = Get-ActiveVenv
    if ($null -eq $active) {
        Write-Host ""
        Write-Host "Venv created but health check failed. Diagnostics:"
        & $py -m pip check
        Test-VenvHealthy -PythonExe $py -Verbose | Out-Null
        throw "Fix the errors above, then run: .\.venv2\Scripts\python.exe -m pip install -r requirements.txt"
    }
}

Write-Host ""
Write-Host "Using virtualenv: $($active.Name)"
. $active.Activate

Write-Host ""
Write-Host "Running database migrations (alembic upgrade head)..."
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Alembic failed - Supabase likely has OLD tables from a prior Dev setup."
    Write-Host "1. Open Supabase dashboard -> SQL Editor"
    Write-Host '2. Run: backend\scripts\reset_supabase_dev.sql'
    Write-Host "3. Then: python -m alembic upgrade head"
    exit 1
}

Write-Host ""
Write-Host "Starting Conditia API on http://127.0.0.1:8001"
Write-Host "Health: Invoke-RestMethod http://127.0.0.1:8001/health"
Write-Host ""

python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
