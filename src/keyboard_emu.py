"""DirectInput scan-code keyboard emulation (Win32 SendInput).

ETS2/ATS read DirectInput scan codes, so we send raw scan codes. Used to map the
gamepad buttons to the game's default keyboard shortcuts, so they work with no
in-game setup.
"""

import ctypes
from ctypes import wintypes

INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

ULONG_PTR = ctypes.c_size_t   # pointer-sized (8 on x64, 4 on x86)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


_SendInput = ctypes.windll.user32.SendInput
_SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_SendInput.restype = wintypes.UINT

# DirectInput scan codes (DIK_*).
DIK = {
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "E": 0x12, "R": 0x13, "T": 0x14, "G": 0x22, "P": 0x19, "O": 0x18,
    "K": 0x25, "L": 0x26, "C": 0x2E, "N": 0x31, "H": 0x23, "F": 0x21, "M": 0x32,
    "Space": 0x39, "Esc": 0x01, "Enter": 0x1C,
    "Comma": 0x33, "Period": 0x34, "LBracket": 0x1A, "RBracket": 0x1B,
}


def _send(scan, key_up):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
    inp = _INPUT(type=INPUT_KEYBOARD)
    inp.u.ki = _KEYBDINPUT(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return _SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def press(name):
    s = DIK.get(name)
    if s is not None:
        _send(s, False)


def release(name):
    s = DIK.get(name)
    if s is not None:
        _send(s, True)


def _mouse(flags):
    inp = _INPUT(type=INPUT_MOUSE)
    inp.u.mi = _MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)
    _SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def mouse_middle_down():
    _mouse(MOUSEEVENTF_MIDDLEDOWN)


def mouse_middle_up():
    _mouse(MOUSEEVENTF_MIDDLEUP)
