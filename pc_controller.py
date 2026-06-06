"""Translate a controller frame into the vJoy virtual wheel/device.

  gyro       -> steering (wheel axis, full range)
  R2 / L2    -> throttle / brake axes
  right stick-> camera look axes
  buttons + d-pad -> vJoy buttons
"""

_BUTTON_SLOTS = ["cross", "circle", "square", "triangle", "l1", "r1",
                 "l3", "r3", "share", "options", "ps", "touchpad"]


def _dpad_dirs(dpad):
    return {
        "dpad_up": dpad in (7, 0, 1),
        "dpad_right": dpad in (1, 2, 3),
        "dpad_down": dpad in (3, 4, 5),
        "dpad_left": dpad in (5, 6, 7),
    }


class PCController:
    def __init__(self, settings, vjoy):
        self.s = settings
        self.vjoy = vjoy

    def update(self, state, steering_norm):
        look_x = look_y = 0.0
        if self.s.look_enabled:
            dz = self.s.look_deadzone / 100.0
            look_x = _dz((state.rx - 128) / 127.0, dz)
            look_y = _dz((state.ry - 128) / 127.0, dz)  # down stick -> down look

        buttons = {slot: state.btn(slot) for slot in _BUTTON_SLOTS}
        buttons.update(_dpad_dirs(state.dpad))

        self.vjoy.apply(_c(steering_norm), state.r2 / 255.0, state.l2 / 255.0,
                        _c(look_x), _c(look_y), buttons)

    def release_all(self):
        self.vjoy.neutral()


def _dz(v, dz):
    if abs(v) <= dz:
        return 0.0
    return (v - (dz if v > 0 else -dz)) / (1.0 - dz)


def _c(v):
    return -1.0 if v < -1.0 else 1.0 if v > 1.0 else v
