"""ETS2 / ATS telemetry via the SCS SDK plugin (RenCloud/scs-sdk-plugin).

The plugin (`scs-telemetry.dll`) is copied into the game's `bin/win_x64/plugins`
folder; the game then publishes telemetry to the shared memory map
`Local\\SCSTelemetry`. We open that map read-only and read engine RPM.

Field offsets are from scs-telemetry-common.hpp (map size 32 KiB):
  sdkActive  bool   @ 0      game        uint32 @ 52
  paused     bool   @ 4      engineRpmMax float  @ 740
  engineRpm  float  @ 952    engineEnabled bool  @ 1576
"""

import ctypes
from ctypes import wintypes
import os
import struct
import sys

MMF_NAME = "Local\\SCSTelemetry"
MMF_SIZE = 32 * 1024
PLUGIN_DLL = "scs-telemetry.dll"

_OFF_SDK_ACTIVE = 0
_OFF_GAME = 52          # scs_values.game (0=unknown,1=ETS2,2=ATS)
_OFF_RPM_MAX = 740
_OFF_RPM = 952
_OFF_ENGINE_ON = 1576

GAME_NAMES = {1: "ETS2", 2: "ATS"}


def _res_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Shared-memory reader (open only if the game created the map)
# ---------------------------------------------------------------------------
class Telemetry:
    FILE_MAP_READ = 0x0004

    def __init__(self):
        self._k = ctypes.windll.kernel32
        # Set return/arg types so 64-bit handles and pointers aren't truncated.
        self._k.OpenFileMappingW.restype = wintypes.HANDLE
        self._k.MapViewOfFile.restype = ctypes.c_void_p
        self._k.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                          wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
        self._k.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        self._k.CloseHandle.argtypes = [wintypes.HANDLE]
        self._h = None
        self._view = None

    def _ensure_open(self):
        if self._view:
            return True
        h = self._k.OpenFileMappingW(self.FILE_MAP_READ, False, MMF_NAME)
        if not h:
            return False
        view = self._k.MapViewOfFile(h, self.FILE_MAP_READ, 0, 0, MMF_SIZE)
        if not view:
            self._k.CloseHandle(h)
            return False
        self._h, self._view = h, view
        return True

    def close(self):
        if self._view:
            self._k.UnmapViewOfFile(ctypes.c_void_p(self._view))
            self._view = None
        if self._h:
            self._k.CloseHandle(self._h)
            self._h = None

    def _raw(self, offset, n):
        return ctypes.string_at(self._view + offset, n)

    def read(self):
        """Return dict(active, game, rpm, rpm_max, engine_on) or None if the
        telemetry map isn't available (game/plugin not running)."""
        if not self._ensure_open():
            return None
        try:
            active = self._raw(_OFF_SDK_ACTIVE, 1)[0] != 0
            game = struct.unpack_from("<I", self._raw(_OFF_GAME, 4))[0]
            rpm = struct.unpack_from("<f", self._raw(_OFF_RPM, 4))[0]
            rpm_max = struct.unpack_from("<f", self._raw(_OFF_RPM_MAX, 4))[0]
            engine_on = self._raw(_OFF_ENGINE_ON, 1)[0] != 0
        except Exception:
            self.close()
            return None
        return {"active": active, "game": GAME_NAMES.get(game, "?"),
                "rpm": rpm, "rpm_max": rpm_max, "engine_on": engine_on}


# ---------------------------------------------------------------------------
# Plugin installation into the games
# ---------------------------------------------------------------------------
def _steam_path():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        val, _ = winreg.QueryValueEx(k, "SteamPath")
        return val.replace("/", "\\")
    except Exception:
        return None


def _library_paths(steam):
    """Steam library roots (default + extra libraries from libraryfolders.vdf)."""
    roots = []
    if not steam:
        return roots
    roots.append(steam)
    vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    try:
        import re
        text = open(vdf, "r", encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r'"path"\s*"([^"]+)"', text):
            roots.append(m.group(1).replace("\\\\", "\\"))
    except Exception:
        pass
    return roots


def find_games():
    """Return list of (name, game_dir) for installed ETS2/ATS."""
    found = []
    names = {"Euro Truck Simulator 2": "ETS2", "American Truck Simulator": "ATS"}
    for root in _library_paths(_steam_path()):
        for folder, label in names.items():
            d = os.path.join(root, "steamapps", "common", folder)
            if os.path.isfile(os.path.join(d, "base.scs")) and \
               os.path.isdir(os.path.join(d, "bin")) and \
               not any(label == f[0] for f in found):
                found.append((label, d))
    return found


def install_plugins():
    """Copy the SCS telemetry plugin into every detected game. Returns a list of
    (game, message) results."""
    import shutil
    results = []
    games = find_games()
    if not games:
        return [("", "No ETS2/ATS Steam install found")]
    for label, gdir in games:
        ok = []
        for arch, dll in (("win_x64", os.path.join(_res_dir(), "plugins", "win_x64", PLUGIN_DLL)),
                          ("win_x86", os.path.join(_res_dir(), "plugins", "win_x86", PLUGIN_DLL))):
            bindir = os.path.join(gdir, "bin", arch)
            if not os.path.isdir(bindir) or not os.path.isfile(dll):
                continue
            try:
                pdir = os.path.join(bindir, "plugins")
                os.makedirs(pdir, exist_ok=True)
                shutil.copy2(dll, os.path.join(pdir, PLUGIN_DLL))
                ok.append(arch)
            except Exception as e:
                results.append((label, "failed: %s" % e))
                ok = None
                break
        if ok:
            results.append((label, "installed (%s)" % ", ".join(ok)))
    return results
