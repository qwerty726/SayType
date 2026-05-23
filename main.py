"""Voice Input Method - main entry.

Architecture:
    keyboard hotkey thread  --press/release-->  Controller (Qt signals)
                                                |
        +---------------------+-----------------+----------------------+
        v                     v                                        v
    Recorder            FloatingBar (UI)                     ASR worker thread
    (sounddevice)       (PyQt6 widget)                       (FunASR / cloud)
                                                                       |
                                                                       v
                                              postprocess.commands  -> injector
                                              postprocess.llm_polish
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback

# Silence noisy ML framework banners before any heavy imports.
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("MODELSCOPE_LOG_LEVEL", "40")

import keyboard
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from config import config
from audio.recorder import Recorder
from asr.funasr_local import FunASRLocal
from injector.text_injector import inject_text
from postprocess.commands import parse_command
from postprocess.llm_polish import polish
from ui.floating_bar import FloatingBar
from ui.settings_dialog import SettingsDialog
from ui.tray import TrayIcon


class Controller(QObject):
    """Bridges the keyboard listener thread with the Qt UI thread.

    The `keyboard` library callbacks run on their own thread. They emit Qt
    signals into here; the actual Recorder.start / stop and UI updates then
    happen on the Qt main thread (sounddevice itself is thread-safe but Qt
    widgets are not).
    """

    sig_press = pyqtSignal()
    sig_release = pyqtSignal()
    sig_inject = pyqtSignal(str)
    sig_show_error = pyqtSignal(str)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.enabled = True
        self.bar = FloatingBar()
        self.recorder = Recorder(sample_rate=config.get("sample_rate"))
        self.asr = self._make_backend()
        self.asr.warmup_async()

        self.tray = TrayIcon(
            on_toggle_enabled=self._on_toggle_enabled,
            on_open_settings=self._open_settings,
            on_quit=self._quit,
            hotkey=config.get("hotkey"),
        )
        self.tray.show()
        self.tray.notify("语音输入法", f"已启动，按住 [{config.get('hotkey').upper()}] 说话")

        self.sig_press.connect(self._on_press)
        self.sig_release.connect(self._on_release)
        self.sig_inject.connect(self._do_inject)
        self.sig_show_error.connect(self.bar.sig_show_error.emit)

        self._press_time = 0.0
        self._suppress_release_until = 0.0

        self._register_hotkey()

    def _make_backend(self) -> FunASRLocal:
        # Only one backend wired for phase 1/2; settings dropdown is single-item.
        return FunASRLocal()

    def _register_hotkey(self) -> None:
        hotkey = config.get("hotkey")
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        # Use on_press_key / on_release_key for push-to-talk semantics.
        # For multi-key combos like "ctrl+space" we'd need a different scheme;
        # phase 1 sticks to single-key hotkeys.
        try:
            keyboard.on_press_key(hotkey, self._kb_press, suppress=False)
            keyboard.on_release_key(hotkey, self._kb_release, suppress=False)
        except Exception as e:  # noqa: BLE001
            print(f"[hotkey] failed to register '{hotkey}': {e}", file=sys.stderr)

    def _kb_press(self, _evt) -> None:
        if not self.enabled:
            return
        # Filter OS-level key repeat: ignore presses fired while already recording.
        if self.recorder.is_recording:
            return
        self.sig_press.emit()

    def _kb_release(self, _evt) -> None:
        if not self.enabled:
            return
        if not self.recorder.is_recording:
            return
        self.sig_release.emit()

    def _on_press(self) -> None:
        self._press_time = time.time()
        try:
            self.recorder.start()
            self.bar.sig_show_recording.emit()
        except Exception as e:  # noqa: BLE001
            self.sig_show_error.emit(f"录音启动失败: {e}")

    def _on_release(self) -> None:
        try:
            audio = self.recorder.stop()
        except Exception as e:  # noqa: BLE001
            self.sig_show_error.emit(f"录音停止失败: {e}")
            return

        dur = time.time() - self._press_time
        if dur < 0.25 or audio.size < 0.25 * config.get("sample_rate"):
            # Too short - likely an accidental tap.
            self.bar.sig_hide.emit()
            return

        self.bar.sig_show_processing.emit()
        threading.Thread(target=self._transcribe_and_inject, args=(audio,), daemon=True).start()

    def _transcribe_and_inject(self, audio) -> None:
        try:
            text = self.asr.transcribe(audio, self.recorder.sample_rate)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sig_show_error.emit(f"识别失败: {e}")
            return

        if not text:
            self.sig_show_error.emit("未识别到内容")
            return

        # 1) Voice command? Then dispatch as an action instead of typing.
        if config.get("voice_commands_enabled"):
            kind, payload = parse_command(text)
            if kind == "text":
                self.sig_inject.emit(payload)
                return
            if kind == "key":
                self._press_hotkey(payload)
                self.bar.sig_hide.emit()
                return

        # 2) Optional LLM polish for written-style output.
        if config.get("llm_polish_enabled") and config.get("llm_api_key"):
            text = polish(
                text,
                api_key=config.get("llm_api_key"),
                base_url=config.get("llm_base_url"),
                model=config.get("llm_model"),
            )

        self.sig_inject.emit(text)

    def _do_inject(self, text: str) -> None:
        try:
            inject_text(text, method=config.get("inject_method"))
        finally:
            self.bar.sig_hide.emit()

    def _press_hotkey(self, combo: str) -> None:
        import pyautogui
        keys = [k.strip() for k in combo.split("+") if k.strip()]
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)

    def _on_toggle_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled and self.recorder.is_recording:
            self.recorder.stop()
            self.bar.sig_hide.emit()

    def _open_settings(self) -> None:
        dlg = SettingsDialog()
        if dlg.exec():
            # Re-register hotkey in case it changed; rebuild backend if changed.
            self._register_hotkey()
            self.tray.set_hotkey_label(config.get("hotkey"))

    def _quit(self) -> None:
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.app.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _controller = Controller(app)  # noqa: F841 (held by the Qt event loop)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
