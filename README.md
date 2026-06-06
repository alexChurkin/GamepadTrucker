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

Bind the **vJoy axes** in the game; the **buttons need no setup** (they emulate
the game's default keyboard shortcuts):

1. ETS2/ATS → *Options → Controls* → select the **vJoy** device.
2. Bind the axes: **Steering → X**, **Throttle → Z**, **Brake → RZ**,
   **Camera look → RX / RY**. (Don't bind steering to the raw gamepad stick.)
3. Buttons already work via the default keyboard binds:

| Button | Action | Key |
|--------|--------|-----|
| L1 / R1 | Turn signals | `,` / `.` |
| Square | Parking brake | Space |
| Triangle | Lights cycle | L |
| Circle | High beam | K |
| Cross | Horn | H |
| R3 | Air horn | N |
| L3 | Wipers | P |
| Options | Cruise control | C |
| Share | Hazard lights | F |
| Touchpad | Engine start/stop | E |
| D-pad | Camera views | 1 / 2 / 4 / 5 |
| PS | Menu | Esc |

Because steering is a vJoy wheel axis, you get full lock at any speed. If a key
above differs from your keyboard binds, change it in the game's keyboard controls.

## Steering tuning (in-app)

- **Recenter wheel** — hold the pad in your neutral grip, then click.
- **Sensitivity** — how much rotation reaches full lock.
- **Smoothing** — higher = smoother but laggier (kills jitter).
- **Dead zone** — ignore small rotation near center.
- **Expo** — softer near center for a steadier middle, full lock still reachable.
- **Invert steering** — flip left/right.
- **Right stick = camera look** — toggle, with its own deadzone.
- **Reset to defaults** — restore the tuned default settings.

Settings save to `settings.json` next to the app.
