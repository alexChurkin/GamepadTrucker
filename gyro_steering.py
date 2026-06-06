"""Turn controller motion into a steering-wheel angle.

Only rotation about the *steering axis* (turning the pad left/right like a wheel)
counts. Tilting it toward/away from you (pitch) is ignored.

How: the wheel angle is the signed angle of gravity within the plane
perpendicular to the steering axis, relative to neutral (captured at recenter).
Projecting gravity onto that plane removes the tilt-toward/away component, so
pitch does not move the wheel. The measure is absolute (gravity-based), so it is
drift-free and returns to center at the neutral pose, and - unlike acos of the
raw tilt - it is smooth around center, so the center is steady.

  * The steering axis is learned from the gyro direction on the first clear turn
    and only refined by motions consistent with it, so flips can't corrupt it.
  * If the pad is tilted so far that gravity nears the axis (the projection
    becomes tiny and the angle ambiguous), the wheel simply holds its last value
    instead of jamming, and resumes when the pad comes back.
"""

import math
import time


class GyroSteering:
    # Wheel rotation (radians) that gives full lock at sensitivity 50.
    FULL_LOCK_REF = 1.30

    def __init__(self, settings):
        self.s = settings
        self._angle = 0.0
        self._axis = [0.0, 0.0, 1.0]
        self._axis_init = False
        self._g0 = None
        self._bias = None
        self._g_prev = None
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
            self._angle = 0.0
            self._recenter_pending = False

        # Learn / refine the steering axis from the gyro direction.
        if speed > 0.6:
            d = [w[0] / speed, w[1] / speed, w[2] / speed]
            if not self._axis_init:
                if speed > 1.0:
                    self._axis = d
                    self._axis_init = True
            else:
                if _dot(d, self._axis) < 0.0:
                    d = [-d[0], -d[1], -d[2]]
                if _dot(d, self._axis) > 0.5:          # only consistent motions
                    self._axis = _unit([self._axis[i] + 0.03 * (d[i] - self._axis[i])
                                        for i in range(3)])
        s = self._axis

        # Gravity projected onto the plane perpendicular to the steering axis.
        # While genuinely steering, gravity stays in that plane (projection
        # large). While the pad is tilted/tumbled out of the plane the
        # projection shrinks; then the angle is meaningless, so we HOLD it - and
        # we use the bounded angle directly (no winding accumulator), so circling
        # the pad can never wind up the wheel and jam it.
        a0 = _proj_perp(self._g0, s)
        a = _proj_perp(g, s)
        # Valid steering pose: gravity in the steering plane AND not tilted too
        # far from neutral (a real turn reaches ~90 deg; beyond that the pad is
        # being tumbled, not steered).
        in_plane = _dot(a, a) > 0.36 and _dot(a0, a0) > 0.10
        near_neutral = _dot(g, self._g0) > -0.17        # tilt < ~100 deg
        if in_plane and near_neutral:
            self._angle = math.atan2(_dot(_cross(a0, a), s), _dot(a0, a))
        # else: out of steering range -> keep the last angle (no jam, no swing)

        gain = (self.s.sensitivity / 50.0) / self.FULL_LOCK_REF
        t = max(-1.0, min(1.0, self._angle * gain))

        dz = self.s.deadzone / 100.0
        if dz > 0.0:
            if abs(t) <= dz:
                t = 0.0
            else:
                t = (t - math.copysign(dz, t)) / (1.0 - dz)

        # Expo: softer near center (steadier) while still reaching full lock.
        e = max(0.0, min(0.9, self.s.expo))
        t = (1.0 - e) * t + e * t * t * t
        if self.s.invert:
            t = -t

        k = 1.0 - max(0.0, min(0.95, self.s.smoothing / 100.0))
        self.value += k * (t - self.value)
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


def _proj_perp(v, s):
    d = _dot(v, s)
    return [v[0] - d * s[0], v[1] - d * s[1], v[2] - d * s[2]]


def _wrap(a):
    while a > math.pi:
        a -= 2.0 * math.pi
    while a <= -math.pi:
        a += 2.0 * math.pi
    return a
