# Truck Remote Server V2 — gamepad + gyro

Drive **Euro Truck Simulator 2 / American Truck Simulator** with a
**DualShock 4** or **DualSense** over **Bluetooth** (or USB). The controller's
**gyroscope is the steering wheel** — hold the pad like a wheel and tilt it.

> Русская версия: [README_ru.md](README_ru.md)

---

## How it works

Everything is routed through **one vJoy device**. Because vJoy is a generic
DirectInput device, ETS2/ATS treats its steering axis as a **wheel** — full
lock-to-lock at any speed, with no gamepad steering assist:

- gyro tilt → **steering** (X axis, smoothed, full range)
- R2 / L2 → **throttle / brake** (Z / RZ axes)
- right stick → **camera look** (RX / RY axes)
- buttons + d-pad → **vJoy buttons** (16)

## What you need

- **vJoy** driver. The app installs and configures it automatically if missing
  (`run.bat` → `setup_vjoy.ps1`).
- A **DualShock 4** or **DualSense** over Bluetooth or USB.
- From source: **Python 3.9+**. Packaged build: nothing extra.

## Run it

- **Packaged:** double-click `dist\TruckRemoteServerV2.exe`
  (install vJoy once via `setup_vjoy.ps1` if you don't have it).
- **From source:** double-click **`run.bat`** — sets up the venv, installs deps,
  installs/configures vJoy if needed, and starts the app.

## Build the .exe

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Single-file `dist\TruckRemoteServerV2.exe` (PyInstaller). `hidapi` and pyvjoy's
`vJoyInterface.dll` are bundled; the target PC still needs the **vJoy driver**.

## Set up the game (one time)

The physical controller is also visible to Windows, so bind **only the vJoy
device** in the game and leave the gamepad unbound:

1. ETS2/ATS → *Options → Controls* → select the **vJoy** device.
2. Bind: **Steering → X axis** (turn the wheel), **Throttle → Z**,
   **Brake → RZ**, **Camera look → right-stick axes (RX/RY)**, and buttons as
   you like (16 vJoy buttons map to the pad's buttons + d-pad).
3. Don't bind anything to the raw DualSense, so the two never fight.

Because it's a wheel axis, you get full steering range at any speed.

## Steering tuning (in-app)

- **Recenter wheel** — hold the pad in your neutral grip, then click.
- **Sensitivity** — tilt needed for full lock.
- **Smoothing** — higher = smoother but laggier (kills jitter).
- **Dead zone** — ignore small tilt near center.
- **Gyro fusion** — `0` = pure tilt (robust); higher adds gyro for snappier feel.
- **Invert steering** — on by default.
- **Right stick = camera look** — toggle, with its own deadzone.

Settings save to `settings.json` next to the app.
