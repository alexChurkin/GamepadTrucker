"""Turn controller motion into a steering-wheel angle.

Only rotation about the *steering axis* counts as steering; tilting the pad
toward/away (a different axis) is ignored. A single rotation can't tell steering
from tilt on its own (both are horizontal axes), so the steering axis is set by
a quick CALIBRATION: you turn the wheel left<->right once and the dominant
rotation axis is captured and locked. After that, tilting about other axes is
rejected.

The wheel angle itself is the signed angle of gravity within the plane
perpendicular to that axis, relative to neutral (captured at recenter). Being
gravity-based it is drift-free, returns to center at the neutral pose, and is
smooth around center. Bounded (no winding) + pose gating means tumbling/flipping
the pad never winds it up or jams it.
"""

import math
import time


class GyroSteering:
    FULL_LOCK_REF = 1.05   # rotation (rad) for full lock at sensitivity 50
    CALIB_SECONDS = 3.0

    def __init__(self, settings):
        self.s = settings
        self._angle = 0.0
        self._g0 = None
        self._bias = None
        self._g_prev = None
        self._last_t = None
        self._recenter_pending = True
        self.value = 0.0

        ax = getattr(settings, "steer_axis", None)
        if isinstance(ax, (list, tuple)) and len(ax) == 3:
            self._axis = _unit(list(ax))
            self._locked = True
        else:
            self._axis = [0.0, 0.0, 1.0]
            self._locked = False

        self._calib = False
        self._calib_end = None
        self._M = None
        self.calibrating = False

    def request_recenter(self):
        self._recenter_pending = True

    def start_calibration(self):
        self._calib = True
        self.calibrating = True
        self._calib_end = None
        self._M = [[0.0] * 3 for _ in range(3)]

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

        # --- calibration: capture the dominant rotation axis -----------------
        if self._calib:
            if self._calib_end is None:
                self._calib_end = now + self.CALIB_SECONDS
            if speed > 0.8:
                for i in range(3):
                    for j in range(3):
                        self._M[i][j] += w[i] * w[j]
            if now >= self._calib_end:
                v = _principal(self._M)
                if v is not None:
                    self._axis = v
                    self._locked = True
                    self.s.steer_axis = v
                    self.s.save()
                self._calib = False
                self.calibrating = False
                self._recenter_pending = True
            self.value *= 0.7   # relax to center while calibrating
            return self.value

        if self._recenter_pending or self._g0 is None:
            self._g0 = list(g)
            self._angle = 0.0
            self._recenter_pending = False

        # Auto-learn the axis only if it was never calibrated (fallback).
        if not self._locked and speed > 1.0:
            d = [w[0] / speed, w[1] / speed, w[2] / speed]
            self._axis = d
        s = self._axis

        a0 = _proj_perp(self._g0, s)
        a = _proj_perp(g, s)
        in_plane = _dot(a, a) > 0.36 and _dot(a0, a0) > 0.10
        near_neutral = _dot(g, self._g0) > -0.17        # tilt < ~100 deg
        if in_plane and near_neutral:
            self._angle = math.atan2(_dot(_cross(a0, a), s), _dot(a0, a))
        # else: out of steering range -> keep last angle

        gain = (self.s.sensitivity / 50.0) / self.FULL_LOCK_REF
        t = max(-1.0, min(1.0, self._angle * gain))

        dz = self.s.deadzone / 100.0
        if dz > 0.0:
            if abs(t) <= dz:
                t = 0.0
            else:
                t = (t - math.copysign(dz, t)) / (1.0 - dz)

        e = max(0.0, min(0.9, self.s.expo))
        t = (1.0 - e) * t + e * t * t * t
        if self.s.invert:
            t = -t

        k = 1.0 - max(0.0, min(0.95, self.s.smoothing / 100.0))
        self.value += k * (t - self.value)
        return self.value


def _principal(M):
    """Dominant eigenvector of a symmetric 3x3 matrix (power iteration)."""
    v = [1.0, 1.0, 1.0]
    for _ in range(60):
        nv = [M[i][0] * v[0] + M[i][1] * v[1] + M[i][2] * v[2] for i in range(3)]
        n = math.sqrt(nv[0] * nv[0] + nv[1] * nv[1] + nv[2] * nv[2])
        if n < 1e-9:
            return None
        v = [nv[0] / n, nv[1] / n, nv[2] / n]
    return v


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
