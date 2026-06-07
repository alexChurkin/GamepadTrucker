"""Translate a controller frame into game output.

  steering / throttle / brake / camera look -> vJoy axes (a real wheel + pedals)
  buttons + d-pad -> default ETS2/ATS keyboard keys (and a mouse action), so they
  work with no in-game setup.
"""

import keyboard_emu as kb

# slot -> action. ("key", <name>) sends a keyboard key; ("mouse", "middle")
# clicks the middle mouse button (view zoom).
BUTTON_ACTIONS = {
    "cross": ("key", "O"),        # beacon
    "circle": ("key", "K"),       # high beam
    "square": ("key", "Space"),   # parking / hand brake
    "triangle": ("key", "L"),     # lights cycle
    "l1": ("key", "N"),           # air horn
    "r1": ("key", "C"),           # cruise control
    "l3": ("key", "P"),           # wipers
    "r3": ("mouse", "middle"),    # view zoom (like clicking the mouse wheel)
    "options": ("key", "Esc"),    # game menu
    "share": ("key", "M"),        # map
    "touchpad": ("key", "H"),     # main horn (press the touchpad to honk)
    "dpad_left": ("key", "LBracket"),   # left turn signal  ([)
    "dpad_right": ("key", "RBracket"),  # right turn signal (])
    "dpad_up": ("key", "F"),          # hazard lights
    "dpad_down": ("key", "E"),        # engine start/stop (ignition)
}

_PLAIN = ("cross", "circle", "square", "triangle", "l1", "r1",
          "l3", "r3", "options", "share", "touchpad")


def _dpad_dirs(dpad):
    return {
        "dpad_up": dpad in (7, 0, 1),
        "dpad_right": dpad in (1, 2, 3),
        "dpad_down": dpad in (3, 4, 5),
        "dpad_left": dpad in (5, 6, 7),
    }


def _press(action):
    kind, val = action
    if kind == "mouse":
        kb.mouse_middle_down()
    else:
        kb.press(val)


def _release(action):
    kind, val = action
    if kind == "mouse":
        kb.mouse_middle_up()
    else:
        kb.release(val)


class PCController:
    def __init__(self, settings, vjoy):
        self.s = settings
        self.vjoy = vjoy
        self._held = {}   # slot -> action currently active

    def update(self, state, steering_norm):
        dz = self.s.look_deadzone / 100.0
        look_x = _dz((state.rx - 128) / 127.0, dz)
        look_y = _dz((state.ry - 128) / 127.0, dz)
        self.vjoy.apply(_c(steering_norm), state.r2 / 255.0, state.l2 / 255.0,
                        _c(look_x), _c(look_y))

        pressed = {slot: state.btn(slot) for slot in _PLAIN}
        pressed.update(_dpad_dirs(state.dpad))
        for slot, action in BUTTON_ACTIONS.items():
            down = pressed.get(slot, False)
            held = self._held.get(slot)
            if down and held is None:
                _press(action)
                self._held[slot] = action
            elif not down and held is not None:
                _release(held)
                self._held[slot] = None

    def release_all(self):
        for slot, action in list(self._held.items()):
            if action:
                _release(action)
                self._held[slot] = None
        self.vjoy.neutral()


def _dz(v, dz):
    if abs(v) <= dz:
        return 0.0
    return (v - (dz if v > 0 else -dz)) / (1.0 - dz)


def _c(v):
    return -1.0 if v < -1.0 else 1.0 if v > 1.0 else v
