# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SayType voice input method.

Build with:
    pyinstaller voice_input.spec --clean --noconfirm

Output: dist/SayType/SayType.exe  (onedir mode)

Notes
-----
- onedir, not onefile: torch+FunASR are huge; onefile unpacks to temp
  on every launch which is slow and RAM-hungry.
- FunASR models are NOT bundled. They download to ~/.cache/modelscope/
  on first run (~800 MB total for the streaming pipeline).
- collect_all is used ONLY for packages without a reliable PyInstaller
  hook (torch / funasr / modelscope). PyQt6 / sounddevice have working
  built-in hooks and over-collecting them tends to cause DLL conflicts
  like "ImportError: DLL load failed while importing QtCore:
  找不到指定的程序" (the loaded Qt DLL is missing a symbol the bundle
  expects, usually because two Qt copies got merged).
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

extra_datas = []
extra_binaries = []
extra_hidden = []

# Heavy ML packages: dynamic imports demand collect_all.
for pkg in ("torch", "torchaudio", "funasr", "modelscope"):
    try:
        datas, binaries, hiddenimports = collect_all(pkg)
        extra_datas += datas
        extra_binaries += binaries
        extra_hidden += hiddenimports
    except Exception:
        pass

# PyQt6 and sounddevice: rely on PyInstaller's built-in hooks; only add
# the submodules we actually import as explicit hidden imports so the
# hook is forced to include them.
extra_hidden += [
    "PyQt6.sip",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "sounddevice",
    "_sounddevice",
    "keyboard",
    "pyperclip",
    "pyautogui",
    "websocket",
    "websocket._app",
    "numpy",
    "requests",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=extra_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyi_rth_dll_path.py"],
    excludes=[
        # Aggressively keep out anything that could ship a competing Qt.
        "PyQt5",
        "PyQt5.QtCore",
        "PySide2",
        "PySide6",
        "shiboken2",
        "shiboken6",
        # Heavy unused libs that PyInstaller might otherwise drag in.
        "matplotlib",
        "pandas",
        "tensorflow",
        "jupyter",
        "IPython",
        "tkinter",
        "test",
        "tests",
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
    upx=False,           # UPX is notorious for breaking torch / Qt DLLs
    console=False,       # windowed (tray) app
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
