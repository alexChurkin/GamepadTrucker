"""DualSense / DualShock 4 lightbar control via a HID output report.

The lightbar RGB is set by an output report sent on the same HID handle we read
from. Bluetooth reports carry a trailing CRC32 (seeded with the 0xA2 BT
output-report tag). Layouts follow the common reports used by pydualsense /
DS4Windows.

  DualSense : USB 0x02 (RGB @ 45..47)   BT 0x31 (RGB @ 46..48, +CRC)
  DualShock4: USB 0x05 (RGB @ 6..8)     BT 0x11 (RGB @ 8..10,  +CRC)
"""

import struct
import zlib

# Surgical flags: change ONLY the lightbar, leave rumble/haptics untouched so we
# don't fight the game's force feedback (which otherwise made the lightbar blink
# back to default on bumps).
_DS_FLAG0 = 0x00       # DualSense: don't touch rumble/triggers
_DS_FLAG1 = 0x04       # DualSense: 0x04 = allow lightbar color
_DS4_FLAGS = 0x06      # DS4: 0x02 lightbar color | 0x04 flash (no rumble bit 0x01)


def build_report(kind, bt, r, g, b):
    if kind == "ds4":
        return _ds4_report(bt, r, g, b)
    return _dualsense_report(bt, r, g, b)


def _crc_tail(buf):
    crc = zlib.crc32(b"\xA2" + bytes(buf[0:74])) & 0xFFFFFFFF
    struct.pack_into("<I", buf, 74, crc)


def _dualsense_report(bt, r, g, b):
    r &= 0xFF; g &= 0xFF; b &= 0xFF
    if bt:
        buf = bytearray(78)
        buf[0] = 0x31
        buf[1] = 0x02          # sequence/tag
        buf[2] = _DS_FLAG0
        buf[3] = _DS_FLAG1
        buf[46] = r; buf[47] = g; buf[48] = b
        _crc_tail(buf)
        return bytes(buf)
    buf = bytearray(48)
    buf[0] = 0x02
    buf[1] = _DS_FLAG0
    buf[2] = _DS_FLAG1
    buf[45] = r; buf[46] = g; buf[47] = b
    return bytes(buf)


def _ds4_report(bt, r, g, b):
    r &= 0xFF; g &= 0xFF; b &= 0xFF
    if bt:
        buf = bytearray(78)
        buf[0] = 0x11
        buf[1] = 0xC0          # HID + CRC, poll rate 0
        buf[2] = 0xA0
        buf[3] = _DS4_FLAGS
        buf[8] = r; buf[9] = g; buf[10] = b
        _crc_tail(buf)
        return bytes(buf)
    buf = bytearray(32)
    buf[0] = 0x05
    buf[1] = _DS4_FLAGS
    buf[6] = r; buf[7] = g; buf[8] = b
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
