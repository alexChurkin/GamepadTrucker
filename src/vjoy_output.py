"""vJoy output: one virtual device carrying the whole controller.

vJoy is a generic DirectInput device, so ETS2/ATS treats its steering axis as a
*wheel* (full lock-to-lock at any speed, no gamepad steering assist) - unlike an
emulated Xbox stick. Everything is routed here:

  steering (gyro) -> X axis  (centered, full range)
  throttle (R2)   -> Z axis      brake (L2) -> RZ axis   (rest at minimum)
  camera look     -> RX / RY axes (right stick, centered)
  buttons + d-pad -> vJoy buttons (see BUTTON_MAP)
"""

# DualSense slot -> vJoy button number.
BUTTON_MAP = {
    "cross": 1, "circle": 2, "square": 3, "triangle": 4,
    "l1": 5, "r1": 6, "l3": 7, "r3": 8,
    "share": 9, "options": 10, "ps": 11, "touchpad": 12,
    "dpad_up": 13, "dpad_down": 14, "dpad_left": 15, "dpad_right": 16,
}
MAX_BUTTON = 16


class VJoyController:
    AXIS_CENTER = 0x4000
    AXIS_MIN = 0x0001
    AXIS_MAX = 0x8000

    def __init__(self, device_id=1):
        self.available = False
        self.error = None
        self._d = None
        self._u = None
        try:
            import pyvjoy
            self._d = pyvjoy.VJoyDevice(device_id)
            self._u = pyvjoy
            self._init_device()
            self.available = True
        except Exception as e:
            self.error = str(e)

    def _init_device(self):
        try:
            self._d.reset()
        except Exception:
            pass
        # Center steering, look and any unused axis; rest the pedals at minimum.
        for u in (self._u.HID_USAGE_X, self._u.HID_USAGE_RX, self._u.HID_USAGE_RY,
                  self._u.HID_USAGE_Y, self._u.HID_USAGE_SL0, self._u.HID_USAGE_SL1):
            self._set(u, self.AXIS_CENTER)
        self._set(self._u.HID_USAGE_Z, self.AXIS_MIN)
        self._set(self._u.HID_USAGE_RZ, self.AXIS_MIN)
        for b in range(1, MAX_BUTTON + 1):
            self._btn(b, False)

    def _set(self, usage, value):
        if not self._d:
            return
        value = max(self.AXIS_MIN, min(self.AXIS_MAX, int(value)))
        try:
            self._d.set_axis(usage, value)
        except Exception:
            pass

    def _btn(self, num, on):
        try:
            self._d.set_button(num, 1 if on else 0)
        except Exception:
            pass

    # -- public -------------------------------------------------------------
    def apply(self, steering, throttle, brake, look_x, look_y):
        self._set(self._u.HID_USAGE_X, self.AXIS_CENTER + steering * (self.AXIS_CENTER - 1))
        self._set(self._u.HID_USAGE_RX, self.AXIS_CENTER + look_x * (self.AXIS_CENTER - 1))
        self._set(self._u.HID_USAGE_RY, self.AXIS_CENTER + look_y * (self.AXIS_CENTER - 1))
        self._set(self._u.HID_USAGE_Z, self.AXIS_MIN + throttle * (self.AXIS_MAX - self.AXIS_MIN))
        self._set(self._u.HID_USAGE_RZ, self.AXIS_MIN + brake * (self.AXIS_MAX - self.AXIS_MIN))

    def neutral(self):
        if not self._d:
            return
        self._set(self._u.HID_USAGE_X, self.AXIS_CENTER)
        self._set(self._u.HID_USAGE_RX, self.AXIS_CENTER)
        self._set(self._u.HID_USAGE_RY, self.AXIS_CENTER)
        self._set(self._u.HID_USAGE_Z, self.AXIS_MIN)
        self._set(self._u.HID_USAGE_RZ, self.AXIS_MIN)
        for b in range(1, MAX_BUTTON + 1):
            self._btn(b, False)
