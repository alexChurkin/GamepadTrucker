"""Turn controller motion into a steering-wheel angle.

Neutral is simply the gravity direction captured at recenter (`g0`). The wheel
angle is HOW FAR gravity has rotated away from neutral - the angle between the
current gravity vector and `g0`:

    magnitude = acos(g . g0)          # 0 at neutral, grows as you rotate away
    sign      = side of the turn, from the rotation axis (gyro-estimated)

The magnitude is purely geometric and axis-independent, so it is always defined
and **always knows neutral**: no matter how you twist or flip the pad it never
jams - it just saturates at full lock and returns to center the instant the pad
is back at its neutral pose. Only the left/right sign uses the gyro, and small
axis errors there are harmless.
"""

import math
import time


class GyroSteering:
    # Rotation away from neutral (radians) that gives full lock at sensitivity 50.
    FULL_LOCK_REF = 1.30   # ~74 deg

    def __init__(self, settings):
        self.s = settings
        self._axis = [0.0, 0.0, 1.0]   # steering axis estimate (for sign only)
        self._g0 = None
        self._bias = None
        self._g_prev = None
        self._sign = 1.0
        self._last_t = None
        self._recenter_pending = True
        self.value = 0.0

    def request_recenter(self):
        self._recenter_pending = True

    def update(self, state):
        now = time.perf_counter()
        dt = 0.0 if self._last_t is None else (now - self._last_t)
        self._last_t = now

        gyro = state.gyro
        g = _unit(state.accel)

        # Gyro bias learned while still (stillness from accel -> bias-independent).
        still = self._g_prev is not None and _dot(g, self._g_prev) > 0.9998
        self._g_prev = g
        if self._bias is None:
            self._bias = list(gyro)
        if still:
            for i in range(3):
                self._bias[i] += 0.10 * (gyro[i] - self._bias[i])
        sc = self.s.gyro_scale
        w = [(gyro[i] - self._bias[i]) * sc for i in range(3)]
        speed = math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2])

        if self._recenter_pending or self._g0 is None:
            self._g0 = list(g)
            self._recenter_pending = False

        # Steering axis (sign only): track the gyro direction while turning.
        if speed > 0.6:
            d = [w[0] / speed, w[1] / speed, w[2] / speed]
            if _dot(d, self._axis) < 0.0:
                d = [-d[0], -d[1], -d[2]]
            self._axis = _unit([self._axis[i] + 0.04 * (d[i] - self._axis[i])
                                for i in range(3)])

        # Magnitude: angle between current gravity and neutral (axis-independent).
        mag = math.acos(max(-1.0, min(1.0, _dot(g, self._g0))))

        # Sign: which side of neutral, from the rotation axis. Hold the sign near
        # the 180-deg seam (upside down) so it can't flicker there.
        if mag < 2.4:
            s = _dot(_cross(self._g0, g), self._axis)
            if abs(s) > 1e-4:
                self._sign = 1.0 if s > 0.0 else -1.0
        angle = self._sign * mag

        gain = (self.s.sensitivity / 50.0) / self.FULL_LOCK_REF
        target = angle * gain
        if self.s.invert:
            target = -target
        target = max(-1.0, min(1.0, target))

        dz = self.s.deadzone / 100.0
        if dz > 0.0:
            if abs(target) <= dz:
                target = 0.0
            else:
                target = (target - math.copysign(dz, target)) / (1.0 - dz)

        k = 1.0 - max(0.0, min(0.95, self.s.smoothing / 100.0))
        self.value += k * (target - self.value)
        return self.value


def _unit(v):
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) + 1e-9
    return [v[0] / m, v[1] / m, v[2] / m]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]
