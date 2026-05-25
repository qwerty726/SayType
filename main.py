"""Voice Input Method - main entry.

Architecture (with streaming wired in):

    keyboard listener thread  --press/release-->  Controller (Qt signals)
                                                       |
       +------------+-------------------+--------------+--------------+
       v            v                   v                             v
   Recorder    FloatingBar     audio-chunk Queue --> ASR worker --> ASR backend
   (sndev)     (PyQt6)         (thread-safe)         thread        (FunASR /
                                                       |             Xunfei)
                                                  partial cb
                                                       |
                                                 Qt signal -> FloatingBar
                                                       |
                                              end_stream() on release
                                                       |
                                      commands / polish -> injector
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import traceback

# Silence noisy ML framework banners before any heavy imports.
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("MODELSCOPE_LOG_LEVEL", "40")

import keyboard
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from config import config
from audio.recorder import Recorder
from asr.base import ASRBackend
from asr.funasr_local import FunASRLocal
from asr.funasr_streaming import FunASRStreaming
from asr.xunfei_cloud import XunfeiCloud
from injector.text_injector import inject_text
from postprocess.commands import parse_command
from postprocess.history import append_history
from postprocess.llm_polish import polish
from ui.floating_bar import FloatingBar
from ui.history_dialog import HistoryDialog
from ui.settings_dialog import SettingsDialog
from ui.tray import TrayIcon


class Controller(QObject):
    """Coordinates hotkey, recorder, ASR streaming, and text injection."""

    sig_press = pyqtSignal()
    sig_release = pyqtSignal()
    sig_inject = pyqtSignal(str)
    sig_show_error = pyqtSignal(str)
    sig_partial = pyqtSignal(str)

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.enabled = True
        self.bar = FloatingBar()
        self.recorder = Recorder(sample_rate=config.get("sample_rate"))
        self.asr: ASRBackend = self._make_backend()
        if hasattr(self.asr, "warmup_async"):
            self.asr.warmup_async()

        self.tray = TrayIcon(
            on_toggle_enabled=self._on_toggle_enabled,
            on_open_settings=self._open_settings,
            on_open_history=self._open_history,
            on_quit=self._quit,
            hotkey=config.get("hotkey"),
        )
        self.tray.show()
        self.tray.notify("语音输入法", f"已启动，按住 [{config.get('hotkey').upper()}] 说话")

        self.sig_press.connect(self._on_press)
        self.sig_release.connect(self._on_release)
        self.sig_inject.connect(self._do_inject)
        self.sig_show_error.connect(self.bar.sig_show_error.emit)
        self.sig_partial.connect(self.bar.sig_update_partial.emit)

        # Streaming pipeline state.
        self._press_time = 0.0
        self._chunk_q: queue.Queue = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._worker_alive = False

        self._register_hotkey()

    # --------------------------------------------------------------- backend
    def _make_backend(self) -> ASRBackend:
        name = config.get("asr_backend")
        if name == "funasr_streaming":
            return FunASRStreaming()
        if name == "xunfei_cloud":
            return XunfeiCloud(
                app_id=config.get("xunfei_app_id"),
                api_key=config.get("xunfei_api_key"),
                api_secret=config.get("xunfei_api_secret"),
            )
        return FunASRLocal()

    # --------------------------------------------------------------- hotkey
    def _register_hotkey(self) -> None:
        hotkey = config.get("hotkey")
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        try:
            keyboard.on_press_key(hotkey, self._kb_press, suppress=False)
            keyboard.on_release_key(hotkey, self._kb_release, suppress=False)
        except Exception as e:  # noqa: BLE001
            print(f"[hotkey] failed to register '{hotkey}': {e}", file=sys.stderr)

    def _kb_press(self, _evt) -> None:
        if not self.enabled or self.recorder.is_recording:
            return
        self.sig_press.emit()

    def _kb_release(self, _evt) -> None:
        if not self.enabled or not self.recorder.is_recording:
            return
        self.sig_release.emit()

    # --------------------------------------------------------------- press
    def _on_press(self) -> None:
        self._press_time = time.time()
        # Drain any leftover chunks before starting a new utterance.
        try:
            while True:
                self._chunk_q.get_nowait()
        except queue.Empty:
            pass

        try:
            self.asr.begin_stream(partial_callback=self._on_partial)
        except Exception as e:  # noqa: BLE001
            self.sig_show_error.emit(f"模型未就绪: {e}")
            return

        # Spin up the worker that drains audio chunks into the ASR.
        self._worker_alive = True
        self._worker_thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._worker_thread.start()

        self.recorder.set_chunk_callback(self._on_audio_chunk)
        try:
            self.recorder.start()
            self.bar.sig_show_recording.emit()
        except Exception as e:  # noqa: BLE001
            self.sig_show_error.emit(f"录音启动失败: {e}")
            self._worker_alive = False
            self._chunk_q.put(None)

    def _on_audio_chunk(self, chunk) -> None:
        # Audio callback context - must be non-blocking.
        self._chunk_q.put(chunk)

    def _stream_worker(self) -> None:
        sr = self.recorder.sample_rate
        while self._worker_alive:
            try:
                chunk = self._chunk_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if chunk is None:
                break
            try:
                self.asr.push_chunk(chunk, sr)
            except Exception:
                traceback.print_exc()

    def _on_partial(self, text: str) -> None:
        # Called from the worker thread; bounce onto the Qt UI thread.
        self.sig_partial.emit(text)

    # ------------------------------------------------------------- release
    def _on_release(self) -> None:
        self.recorder.set_chunk_callback(None)
        try:
            audio = self.recorder.stop()
        except Exception as e:  # noqa: BLE001
            self.sig_show_error.emit(f"录音停止失败: {e}")
            self._shutdown_worker()
            return

        # Signal worker to drain remaining queue, then stop.
        self._chunk_q.put(None)
        self._shutdown_worker(join=True)

        dur = time.time() - self._press_time
        if dur < 0.25 or audio.size < 0.25 * self.recorder.sample_rate:
            # Too short - treat as accidental tap. Still finalize ASR state.
            self.bar.sig_hide.emit()
            threading.Thread(target=self._discard_stream, daemon=True).start()
            return

        self.bar.sig_show_processing.emit()
        threading.Thread(target=self._finalize_and_inject, daemon=True).start()

    def _shutdown_worker(self, join: bool = False) -> None:
        self._worker_alive = False
        if join and self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3)
        self._worker_thread = None

    def _discard_stream(self) -> None:
        try:
            self.asr.end_stream()
        except Exception:
            pass

    def _finalize_and_inject(self) -> None:
        try:
            text = self.asr.end_stream()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sig_show_error.emit(f"识别失败: {e}")
            return

        if not text:
            self.sig_show_error.emit("未识别到内容")
            return

        # 1) Voice command short-circuit.
        if config.get("voice_commands_enabled"):
            kind, payload = parse_command(text)
            if kind == "text":
                self.sig_inject.emit(payload)
                return
            if kind == "key":
                self._press_hotkey(payload)
                self.bar.sig_hide.emit()
                return

        # 2) Optional LLM polish.
        original = text
        polished: str | None = None
        if config.get("llm_polish_enabled") and config.get("llm_api_key"):
            text = polish(
                text,
                api_key=config.get("llm_api_key"),
                base_url=config.get("llm_base_url"),
                model=config.get("llm_model"),
            )
            polished = text

        append_history(original, polished, backend=config.get("asr_backend"))

        self.sig_inject.emit(text)

    # ------------------------------------------------------------- inject
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

    # -------------------------------------------------------------- toggle / settings
    def _on_toggle_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled and self.recorder.is_recording:
            self.recorder.set_chunk_callback(None)
            self.recorder.stop()
            self._chunk_q.put(None)
            self._shutdown_worker(join=False)
            self.bar.sig_hide.emit()

    def _open_settings(self) -> None:
        dlg = SettingsDialog()
        if dlg.exec():
            # Rebuild backend if it changed, then re-register hotkey.
            new_backend_name = config.get("asr_backend")
            if new_backend_name != getattr(self.asr, "name", ""):
                self.asr = self._make_backend()
                if hasattr(self.asr, "warmup_async"):
                    self.asr.warmup_async()
            self._register_hotkey()
            self.tray.set_hotkey_label(config.get("hotkey"))

    def _open_history(self) -> None:
        dlg = HistoryDialog()
        if dlg.exec() and dlg.text_to_inject:
            # Delay so the OS hands focus back to the previously-active app
            # before we send Ctrl+V; otherwise the paste lands nowhere useful.
            text = dlg.text_to_inject
            QTimer.singleShot(
                200,
                lambda: inject_text(text, method=config.get("inject_method")),
            )

    def _quit(self) -> None:
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.app.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _controller = Controller(app)  # noqa: F841
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
