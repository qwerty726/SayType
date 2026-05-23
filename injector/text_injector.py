"""Insert text into whatever application currently has focus.

The clipboard+paste path is the most reliable across Chinese apps (WeChat,
QQ, Word, browsers) since pyautogui's typewrite() can't produce CJK
characters on Windows.
"""
from __future__ import annotations

import time

import pyautogui
import pyperclip


def inject_text(text: str, method: str = "clipboard", restore_clipboard: bool = True) -> None:
    if not text:
        return

    if method == "typewrite":
        # ASCII-only fallback. Not useful for Chinese but kept for completeness.
        pyautogui.typewrite(text, interval=0.005)
        return

    # Default: clipboard + Ctrl+V.
    prev = ""
    if restore_clipboard:
        try:
            prev = pyperclip.paste()
        except Exception:
            prev = ""

    pyperclip.copy(text)
    # Tiny delay so the clipboard write is observable by the target app.
    time.sleep(0.03)
    pyautogui.hotkey("ctrl", "v")

    if restore_clipboard:
        # Restore after the paste has been consumed by the target app.
        def _restore() -> None:
            time.sleep(0.4)
            try:
                pyperclip.copy(prev)
            except Exception:
                pass

        import threading
        threading.Thread(target=_restore, daemon=True).start()
