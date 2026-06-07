# Build a single-file GamepadTrucker.exe with PyInstaller.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
# Output: dist\GamepadTrucker.exe

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[build] Creating virtual environment..."
    py -3 -m venv .venv
}

Write-Host "[build] Installing dependencies + PyInstaller..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
& $venvPython -m pip install pyinstaller

Write-Host "[build] Running PyInstaller..."
& $venvPython -m PyInstaller gamepad_trucker.spec --noconfirm --clean

if (Test-Path ".\dist\GamepadTrucker.exe") {
    Write-Host ""
    Write-Host "[build] Done -> dist\GamepadTrucker.exe" -ForegroundColor Green
    Write-Host "[build] Ship that single .exe. The vJoy driver must be installed on the target PC."
} else {
    Write-Error "[build] Build failed: dist\GamepadTrucker.exe not found."
}
