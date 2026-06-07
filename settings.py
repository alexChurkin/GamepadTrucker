"""JSON-backed settings stored next to the executable/script."""

import json
import os
import sys

_DEFAULTS = {
    # Steering feel (tuned defaults for ETS2/ATS comfort)
    "sensitivity": 42,
    "deadzone": 4,
    "smoothing": 81,        # steady wheel
    "expo": 0.84,           # 0..0.9; softer near center for a steadier middle
    "invert": False,

    # Gyro-integrated steering (rotation about the controller's Z / hub axis)
    "gyro_scale": 0.001065,  # rad/s per LSB (DualSense/DS4 ~2000 dps full scale)
    "still_thresh": 60,      # LSB; below this the pad is "still" (bias tracking)
    "steer_axis": None,      # calibrated steering axis [x,y,z]; None = not set

    # Right stick -> camera look passthrough (always on)
    "look_deadzone": 12,    # % stick deadzone for camera

    # ETS2/ATS telemetry -> DualSense lightbar color by engine RPM
    "led_rpm_enabled": True,

    "enabled": True,
}


def _config_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "settings.json")


class Settings:
    def __init__(self):
        for k, v in _DEFAULTS.items():
            setattr(self, k, v)
        self._path = _config_path()
        self.load()

    def load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        for k in _DEFAULTS:
            if k in data:
                setattr(self, k, data[k])

    def reset_defaults(self):
        keep_axis = getattr(self, "steer_axis", None)
        for k, v in _DEFAULTS.items():
            setattr(self, k, v)
        self.steer_axis = keep_axis      # keep calibration across a feel reset
        self.save()

    def save(self):
        try:
            data = {k: getattr(self, k) for k in _DEFAULTS}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
