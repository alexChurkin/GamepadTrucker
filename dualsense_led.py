"""DualSense lightbar control via a HID output report.

The lightbar RGB is set by an output report sent on the same HID handle we read
from. Over USB it's report 0x02; over Bluetooth it's report 0x31 with a trailing
CRC32 (seeded with the 0xA2 BT output-report tag). Layout follows the common
DualSense output report (as used by pydualsense / DS4Windows).
"""

import struct
import zlib

_FLAG0 = 0xFF          # enable rumble/trigger fields (harmless, kept 0 below)
_FLAG1 = 0xF7          # bit 0x04 = allow lightbar color change


def build_report(bt, r, g, b):
    r &= 0xFF; g &= 0xFF; b &= 0xFF
    if bt:
        buf = bytearray(78)
        buf[0] = 0x31
        buf[1] = 0x02          # sequence/tag
        buf[2] = _FLAG0
        buf[3] = _FLAG1
        buf[46] = r; buf[47] = g; buf[48] = b
        crc = zlib.crc32(b"\xA2" + bytes(buf[0:74])) & 0xFFFFFFFF
        struct.pack_into("<I", buf, 74, crc)
        return bytes(buf)
    else:
        buf = bytearray(48)
        buf[0] = 0x02
        buf[1] = _FLAG0
        buf[2] = _FLAG1
        buf[45] = r; buf[46] = g; buf[47] = b
        return bytes(buf)


def rpm_to_rgb(rpm, rpm_max):
    """Green (low) -> yellow -> red (near redline). Off when not revving."""
    if rpm_max <= 0 or rpm < 50:
        return (0, 0, 0)
    frac = max(0.0, min(1.0, rpm / rpm_max))
    # stay green through the economy band, shift to yellow then red near the top
    t = max(0.0, min(1.0, (frac - 0.6) / 0.35))
    hue = 120.0 * (1.0 - t)        # 120=green .. 60=yellow .. 0=red
    return _hsv(hue, 1.0, 1.0)


def _hsv(h, s, v):
    c = v * s
    x = c * (1.0 - abs((h / 60.0) % 2 - 1.0))
    m = v - c
    if h < 60:   rgb = (c, x, 0)
    elif h < 120: rgb = (x, c, 0)
    elif h < 180: rgb = (0, c, x)
    elif h < 240: rgb = (0, x, c)
    elif h < 300: rgb = (x, 0, c)
    else:         rgb = (c, 0, x)
    return tuple(int(round((v + m) * 255)) for v in rgb)
