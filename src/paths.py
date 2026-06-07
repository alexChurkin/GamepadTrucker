"""Resolve resource and config paths for both source runs and the frozen exe.

  resource(rel)  - read-only bundled file (app_icon.ico, plugins/...). From the
                   PyInstaller _MEIPASS when frozen, else the project root.
  config_dir()   - writable dir for settings.json / data logs. Next to the exe
                   when frozen, else the project root.
"""

import os
import sys


def _root():
    # project root = parent of this src/ directory (source mode)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource(rel):
    base = getattr(sys, "_MEIPASS", None) or _root()
    return os.path.join(base, rel)


def config_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return _root()
