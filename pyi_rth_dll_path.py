"""PyInstaller runtime hook - executed before any user code in the bundle.

Forces Windows to look in the bundle directory FIRST for DLLs. This is the
fix for the canonical "ImportError: DLL load failed while importing QtCore:
找不到指定的程序" error: without this, Windows can pick up a stale Qt /
MSVC DLL from system PATH (e.g. an Anaconda install, or another Python
env) that exports a different ABI than the bundle was built against.
"""
import os
import sys


def _patch_dll_search_path() -> None:
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return

    # 1) Prepend the bundle dir to PATH so legacy LoadLibrary lookups find
    #    our DLLs first.
    sep = os.pathsep
    os.environ["PATH"] = base + sep + os.environ.get("PATH", "")

    # 2) On Windows + Python 3.8+, PATH alone is not enough for some libs:
    #    they use LoadLibraryEx with LOAD_LIBRARY_SEARCH_USER_DIRS. Register
    #    the bundle directory explicitly.
    if sys.platform.startswith("win") and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(base)
        except (OSError, FileNotFoundError):
            pass
        # PyQt6 plugins live in a subfolder; register it too if present.
        plugins = os.path.join(base, "PyQt6", "Qt6", "bin")
        if os.path.isdir(plugins):
            try:
                os.add_dll_directory(plugins)
            except (OSError, FileNotFoundError):
                pass


_patch_dll_search_path()
