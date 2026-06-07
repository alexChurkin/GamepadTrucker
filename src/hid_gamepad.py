"""DualShock 4 / DualSense reading over USB or Bluetooth via raw HID.

Both controllers expose motion sensors (gyroscope + accelerometer) only inside
their *extended* HID input report. Over USB that report is sent by default;
over Bluetooth the host must first request a feature report to switch the pad
into "full" mode (DS4: feature 0x02, DualSense: feature 0x05). We do that on
open and then detect the transport from the report id of each incoming packet:

    DualShock 4 : 0x01 = USB layout      0x11 = Bluetooth extended layout
    DualSense   : 0x01 = USB layout      0x31 = Bluetooth extended layout

A short 0x01 report over Bluetooth means full mode was not enabled and no gyro
is available; we surface that so the UI can tell the user.
"""

import threading
import time

import hid

SONY_VID = 0x054C

# product_id -> (kind, human name)
KNOWN = {
    0x05C4: ("ds4", "DualShock 4 (v1)"),
    0x09CC: ("ds4", "DualShock 4 (v2)"),
    0x0BA0: ("ds4", "DualShock 4 (USB adapter)"),
    0x0CE6: ("dualsense", "DualSense"),
    0x0DF2: ("dualsense", "DualSense Edge"),
}


def _s16(lo, hi):
    """Little-endian signed 16-bit from two bytes."""
    v = lo | (hi << 8)
    return v - 0x10000 if v >= 0x8000 else v


class GamepadState:
    """Normalized snapshot of a controller frame."""

    __slots__ = (
        "lx", "ly", "rx", "ry", "l2", "r2",
        "buttons", "dpad", "gyro", "accel", "has_motion",
        "touch_active", "touch_x", "touch_y",
    )

    def __init__(self):
        self.lx = self.ly = self.rx = self.ry = 128
        self.l2 = self.r2 = 0
        # button name -> bool
        self.buttons = {}
        self.dpad = 8          # 8 = released
        self.gyro = (0, 0, 0)  # raw int16 (pitch, yaw, roll) device frame
        self.accel = (0, 0, 0) # raw int16 (x, y, z)
        self.has_motion = False
        self.touch_active = False
        self.touch_x = 0       # 0..1919
        self.touch_y = 0       # 0..1079

    def btn(self, name):
        return self.buttons.get(name, False)


# Offset tables. Index is into the raw report buffer (report id at [0]).
# Keys: sticks lx/ly/rx/ry, triggers l2/r2, button bytes b0/b1/b2, gyro g, accel a,
# touch t (first touch point: id byte, then 3 bytes of packed 12-bit X/Y).
_DS4_USB = dict(lx=1, ly=2, rx=3, ry=4, b0=5, b1=6, b2=7, l2=8, r2=9, g=13, a=19, t=36)
_DS4_BT = dict(lx=3, ly=4, rx=5, ry=6, b0=7, b1=8, b2=9, l2=10, r2=11, g=15, a=21, t=38)
_DSENSE_USB = dict(lx=1, ly=2, rx=3, ry=4, l2=5, r2=6, b0=8, b1=9, b2=10, g=16, a=22, t=33)
_DSENSE_BT = dict(lx=2, ly=3, rx=4, ry=5, l2=6, r2=7, b0=9, b1=10, b2=11, g=17, a=23, t=34)


def _parse(kind, data):
    """Return a GamepadState or None if this report carries no usable layout."""
    rid = data[0]
    if kind == "ds4":
        if rid == 0x01 and len(data) >= 64:
            o, motion = _DS4_USB, True
        elif rid == 0x11 and len(data) >= 78:
            o, motion = _DS4_BT, True
        else:
            return None  # short BT basic report -> no motion
    else:  # dualsense
        if rid == 0x01 and len(data) >= 64:
            o, motion = _DSENSE_USB, True
        elif rid == 0x31 and len(data) >= 78:
            o, motion = _DSENSE_BT, True
        else:
            return None

    st = GamepadState()
    st.lx, st.ly, st.rx, st.ry = data[o["lx"]], data[o["ly"]], data[o["rx"]], data[o["ry"]]
    st.l2, st.r2 = data[o["l2"]], data[o["r2"]]

    b0, b1, b2 = data[o["b0"]], data[o["b1"]], data[o["b2"]]
    st.dpad = b0 & 0x0F
    st.buttons = {
        "square":   bool(b0 & 0x10),
        "cross":    bool(b0 & 0x20),
        "circle":   bool(b0 & 0x40),
        "triangle": bool(b0 & 0x80),
        "l1":       bool(b1 & 0x01),
        "r1":       bool(b1 & 0x02),
        "l2btn":    bool(b1 & 0x04),
        "r2btn":    bool(b1 & 0x08),
        "share":    bool(b1 & 0x10),
        "options":  bool(b1 & 0x20),
        "l3":       bool(b1 & 0x40),
        "r3":       bool(b1 & 0x80),
        "ps":       bool(b2 & 0x01),
        "touchpad": bool(b2 & 0x02),
    }

    g, a = o["g"], o["a"]
    st.gyro = (_s16(data[g], data[g + 1]),
               _s16(data[g + 2], data[g + 3]),
               _s16(data[g + 4], data[g + 5]))
    st.accel = (_s16(data[a], data[a + 1]),
                _s16(data[a + 2], data[a + 3]),
                _s16(data[a + 4], data[a + 5]))
    st.has_motion = motion

    t = o["t"]
    if t + 3 < len(data):
        st.touch_active = (data[t] & 0x80) == 0
        st.touch_x = data[t + 1] | ((data[t + 2] & 0x0F) << 8)
        st.touch_y = (data[t + 2] >> 4) | (data[t + 3] << 4)
    return st


def output_report_length(path):
    """Windows OutputReportByteLength for a HID device path (writes must be this
    long). Returns 0 if it can't be determined."""
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        hidd = ctypes.windll.hid
        p = path.decode() if isinstance(path, bytes) else path
        h = k.CreateFileW(ctypes.c_wchar_p(p), 0x80000000 | 0x40000000, 3,
                          None, 3, 0, None)
        if h == 0 or h == -1 or h == 0xFFFFFFFFFFFFFFFF:
            return 0

        class CAPS(ctypes.Structure):
            _fields_ = [("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
                        ("In", wintypes.USHORT), ("Out", wintypes.USHORT),
                        ("Feat", wintypes.USHORT), ("Res", wintypes.USHORT * 17),
                        ("f", wintypes.USHORT * 10)]
        pp = ctypes.c_void_p()
        out = 0
        if hidd.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            c = CAPS()
            hidd.HidP_GetCaps(pp, ctypes.byref(c))
            out = int(c.Out)
            hidd.HidD_FreePreparsedData(pp)
        k.CloseHandle(h)
        return out
    except Exception:
        return 0


def find_controller():
    """Return (path, kind, name) of the first connected Sony pad, or None."""
    best = None
    for d in hid.enumerate():
        if d["vendor_id"] != SONY_VID or d["product_id"] not in KNOWN:
            continue
        kind, name = KNOWN[d["product_id"]]
        # Prefer the Generic Desktop / gamepad interface when usage info exists.
        usage_ok = (d.get("usage_page", 0) == 0x01 and d.get("usage", 0) in (0x04, 0x05))
        cand = (d["path"], kind, name)
        if usage_ok:
            return cand
        if best is None:
            best = cand
    return best


class GamepadManager:
    """Owns a background thread that connects, reads and parses controller frames.

    Callbacks (all optional):
      on_state(state)   - called for every parsed frame (hot path; keep it quick)
      on_status(text, connected, has_motion) - connection/status changes
    """

    def __init__(self, on_state=None, on_status=None):
        self.on_state = on_state
        self.on_status = on_status
        self._thread = None
        self._running = False
        self.connected = False
        self.kind = None
        self.name = None
        self.has_motion = False
        self.bt = False                 # DualSense over Bluetooth (output 0x31)
        self._out_len = 0               # device OutputReportByteLength (pad writes)
        self._led = None                # pending (r,g,b) for the lightbar
        self._led_sent = None
        self._led_t = 0.0

    def set_led(self, rgb):
        """rgb: (r,g,b) tuple or None. Applied on the read thread (DualSense)."""
        self._led = rgb

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    # -- internals ----------------------------------------------------------
    def _status(self, text, connected, motion):
        self.connected = connected
        self.has_motion = motion
        if self.on_status:
            self.on_status(text, connected, motion)

    def _loop(self):
        dev = None
        while self._running:
            if dev is None:
                found = find_controller()
                if not found:
                    self._status("Waiting for controller...", False, False)
                    time.sleep(1.0)
                    continue
                path, kind, name = found
                try:
                    dev = hid.device()
                    dev.open_path(path)
                    dev.set_nonblocking(False)
                    self.kind, self.name = kind, name
                    self._out_len = output_report_length(path)
                    self._enable_full_mode(dev, kind)
                    self._status("{} connected".format(name), True, False)
                except Exception as e:
                    self._status("Open failed: {}".format(e), False, False)
                    dev = None
                    time.sleep(1.0)
                    continue

            try:
                data = dev.read(78, timeout_ms=500)
                if not data:
                    continue
                st = _parse(self.kind, data)
                if st is None:
                    # Connected but only basic (no-motion) reports arriving.
                    if self.has_motion or not self.connected:
                        self._status(
                            "{} connected - NO gyro (enable BT full mode)".format(self.name),
                            True, False)
                    continue
                if not self.has_motion:
                    self._status("{} active (gyro on)".format(self.name), True, True)
                if self.kind in ("dualsense", "ds4"):
                    self.bt = data[0] in (0x31, 0x11)   # DualSense/DS4 BT report
                    self._apply_led(dev)
                if self.on_state:
                    self.on_state(st)
            except Exception:
                # Device unplugged / BT dropped -> reconnect.
                try:
                    dev.close()
                except Exception:
                    pass
                dev = None
                self._status("Controller disconnected", False, False)
                time.sleep(0.5)

        if dev is not None:
            try:
                dev.close()
            except Exception:
                pass

    def _apply_led(self, dev):
        rgb = self._led
        if rgb is None:
            return
        # Send on change, or every ~0.3 s as a keepalive.
        now = time.time()
        if rgb == self._led_sent and (now - self._led_t) < 0.3:
            return
        try:
            import dualsense_led
            report = bytearray(dualsense_led.build_report(self.kind, self.bt, rgb[0], rgb[1], rgb[2]))
            if self._out_len and len(report) < self._out_len:   # Windows wants full length
                report += bytes(self._out_len - len(report))
            dev.write(bytes(report))
            self._led_sent = rgb
            self._led_t = now
        except Exception:
            pass

    @staticmethod
    def _enable_full_mode(dev, kind):
        """Trigger extended (motion) reports over Bluetooth. Harmless on USB."""
        try:
            if kind == "ds4":
                dev.get_feature_report(0x02, 37)
            else:
                dev.get_feature_report(0x05, 41)
        except Exception:
            pass
