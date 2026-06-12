# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: builds a single-file windowed GamepadTrucker.exe.
#
#   pyinstaller gamepad_trucker.spec --noconfirm
#
# Bundles the pyvjoy native DLL (vJoyInterface.dll) preserving its
# pyvjoy/utils/<arch>/ layout so pyvjoy can locate it at runtime. The hidapi
# extension (hid.*.pyd) is self-contained and picked up automatically.

from PyInstaller.utils.hooks import collect_data_files

# Bundle pyvjoy's native vJoyInterface.dll (under pyvjoy/utils/<arch>/).
datas = collect_data_files('pyvjoy')
datas += [('app_icon.ico', '.')]  # window icon, loaded via iconbitmap
datas += [('VERSION', '.')]  # single source of truth for the version string
datas += [('plugins/win_x64/scs-telemetry.dll', 'plugins/win_x64'),
          ('plugins/win_x86/scs-telemetry.dll', 'plugins/win_x86')]  # telemetry plugin

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=['hid'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GamepadTrucker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon='app_icon.ico',
)
