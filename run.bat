@echo off
REM Run GamepadTrucker from source.
REM Creates a local virtual environment on first run, installs dependencies,
REM then launches the app. Just double-click this file.

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment...
    py -3 -m venv .venv || python -m venv .venv
    echo [setup] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

REM Ensure vJoy is installed & device #1 configured (auto-install if missing).
".venv\Scripts\python.exe" -c "import pyvjoy; pyvjoy.VJoyDevice(1)" 1>nul 2>nul
if errorlevel 1 (
    echo [setup] vJoy not ready - launching installer/configurator...
    powershell -ExecutionPolicy Bypass -File setup_vjoy.ps1
)

".venv\Scripts\pythonw.exe" main.py
endlocal
