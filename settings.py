"""JSON-backed settings stored next to the executable/script."""

import json
import os
import sys

_DEFAULTS = {
    # Steering feel
    "sensitivity": 50,
    "deadzone": 4,
    "smoothing": 55,
    "invert": False,

    # Gyro-integrated steering (rotation about the controller's Z / hub axis)
    "gyro_scale": 0.001065,  # rad/s per LSB (DualSense/DS4 ~2000 dps full scale)
    "still_thresh": 60,      # LSB; below this the pad is "still" (bias tracking)

    # Right stick -> camera look passthrough
    "look_enabled": True,
    "look_deadzone": 12,    # % stick deadzone for camera

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

    def save(self):
        try:
            data = {k: getattr(self, k) for k in _DEFAULTS}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
