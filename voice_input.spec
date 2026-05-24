# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SayType voice input method.

Build with:
    pyinstaller voice_input.spec --clean --noconfirm

Output: dist/SayType/SayType.exe  (onedir mode, ~1.5-3 GB depending on torch)

Notes
-----
- We use onedir (not onefile) because:
    * Startup is far faster (no unpack to temp on every launch)
    * torch + FunASR are huge; onefile bloats RAM and disk I/O
- FunASR models are *not* bundled. They auto-download to
  ~/.cache/modelscope/ on first run. Bundling them would add ~500 MB
  per model and break model updates.
- `collect_all` grabs every submodule, data file, and binary for the
  packages that use dynamic imports - this is what makes torch / funasr
  actually runnable inside the bundle.
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Heavy dynamic-import packages. collect_all returns (datas, binaries, hiddenimports).
_collected = {}
for pkg in ("torch", "torchaudio", "funasr", "modelscope", "sounddevice", "PyQt6"):
    try:
        datas, binaries, hiddenimports = collect_all(pkg)
        _collected[pkg] = (datas, binaries, hiddenimports)
    except Exception:
        _collected[pkg] = ([], [], [])

extra_datas = []
extra_binaries = []
extra_hidden = []
for d, b, h in _collected.values():
    extra_datas += d
    extra_binaries += b
    extra_hidden += h

extra_hidden += [
    "keyboard",
    "pyperclip",
    "pyautogui",
    "websocket",
    "websocket._app",
    "numpy",
    "requests",
]
extra_hidden += collect_submodules("scipy")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=extra_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "pandas",
        "tensorflow",
        "jupyter",
        "IPython",
        "tkinter",
        "test",
        "tests",
        "PyQt5",
        "PySide2",
        "PySide6",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SayType",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX often breaks torch DLLs; keep off
    console=False,       # windowed app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SayType",
)
