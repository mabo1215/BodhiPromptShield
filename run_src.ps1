# IBPPSVM src runner: create .venv if missing, activate, install deps, run all code.
# Usage: from repo root, run: .\run_src.ps1
# Or:    powershell -ExecutionPolicy Bypass -File .\run_src.ps1

$ErrorActionPreference = "Stop"
$RootDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
Set-Location $RootDir

$venvPath = Join-Path $RootDir ".venv"
$venvScripts = Join-Path $venvPath "Scripts"
$activatePs1 = Join-Path $venvScripts "Activate.ps1"
$pip = Join-Path $venvScripts "pip.exe"
$python = Join-Path $venvScripts "python.exe"

# 1. Create .venv if not present
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at .venv ..."
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw "Failed to create .venv" }
    Write-Host "Done."
} else {
    Write-Host "Using existing .venv"
}

# 2. Activate (so pip/python in this session use venv)
& $activatePs1
if (-not $?) { throw "Failed to activate .venv" }

# 3. Install dependencies
Write-Host "Installing dependencies from src/requirements.txt ..."
& $pip install -q -r (Join-Path $RootDir "src\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Write-Host "Done."

# 4. Run all code (figures + algorithm smoke test)
Write-Host ""
& $python (Join-Path $RootDir "src\run_all.py")
if ($LASTEXITCODE -ne 0) { throw "run_all.py failed" }

Write-Host ""
Write-Host "All done."
exit 0
