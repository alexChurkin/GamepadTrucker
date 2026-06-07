# Install vJoy (if missing) and configure device #1 for GamepadTrucker.
#   powershell -ExecutionPolicy Bypass -File setup_vjoy.ps1
# Self-elevates (driver install + device config need admin).

$ErrorActionPreference = "Stop"

# --- self-elevate ----------------------------------------------------------
$admin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host "Requesting administrator rights..."
    Start-Process powershell -Verb RunAs -ArgumentList `
        "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

function Find-vJoyConfig {
    @("C:\Program Files\vJoy\x64\vJoyConfig.exe",
      "C:\Program Files\vJoy\vJoyConfig.exe",
      "${env:ProgramFiles}\vJoy\x64\vJoyConfig.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}

# --- install vJoy if needed ------------------------------------------------
$cfg = Find-vJoyConfig
if (-not $cfg) {
    $url = "https://github.com/jshafer817/vJoy/releases/download/v2.1.9.1/vJoySetup.exe"
    $exe = "$env:TEMP\vJoySetup.exe"
    Write-Host "vJoy not found. Downloading installer..."
    Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
    Write-Host "Installing vJoy silently..."
    Start-Process -FilePath $exe -ArgumentList "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" -Wait
    Start-Sleep -Seconds 3
    $cfg = Find-vJoyConfig
}

if (-not $cfg) {
    Write-Host "vJoy still not detected. A reboot may be required - reboot and run this again." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

# --- configure device #1: 8 axes + 16 buttons ------------------------------
Write-Host "Configuring vJoy device #1 (8 axes + 16 buttons)..."
& $cfg 1 -f -a X Y Z Rx Ry Rz Sl0 Sl1 -b 16
Start-Sleep -Seconds 1
Write-Host ""
Write-Host "Done. vJoy device #1 ready (X=steering, Z=throttle, RZ=brake, RX/RY=look, 16 buttons)." -ForegroundColor Green
Read-Host "Press Enter to close"
