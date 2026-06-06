"""Capture live accel/gyro from the controller for analysis."""
import time, math
import hid_gamepad as hg

found = hg.find_controller()
if not found:
    print("NO CONTROLLER"); raise SystemExit
path, kind, name = found
import hid
d = hid.device(); d.open_path(path); d.set_nonblocking(False)
hg.GamepadManager._enable_full_mode(d, kind)
print("logging", name, kind, "for ~20s")
t0 = time.time(); last = 0
while time.time() - t0 < 20:
    data = d.read(78, timeout_ms=500)
    if not data: continue
    st = hg._parse(kind, data)
    if not st: continue
    now = time.time()
    if now - last < 0.1:   # ~10 Hz log
        continue
    last = now
    ax, ay, az = st.accel
    gx, gy, gz = st.gyro
    angle = math.degrees(math.atan2(ax, ay))
    print("angleXY=%6.1f | gx=%6d gy=%6d gz=%6d | ax=%6d ay=%6d az=%6d"
          % (angle, gx, gy, gz, ax, ay, az))
d.close()
print("DONE")
