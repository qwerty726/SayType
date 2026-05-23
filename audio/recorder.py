"""Microphone recorder with push-to-talk semantics.

start() begins capturing audio in a background stream; stop() returns the full
recording as a mono float32 numpy array at the configured sample rate. A
chunk_callback can be registered to receive ~100ms chunks live for streaming
ASR.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


class Recorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream: Optional[sd.InputStream] = None
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._chunk_callback: Optional[Callable[[np.ndarray], None]] = None
        self._recording = False

    def set_chunk_callback(self, cb: Optional[Callable[[np.ndarray], None]]) -> None:
        self._chunk_callback = cb

    @property
    def is_recording(self) -> bool:
        return self._recording

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            # XRuns etc. are non-fatal; we just keep going.
            pass
        chunk = indata.copy().reshape(-1)
        with self._lock:
            self._frames.append(chunk)
        if self._chunk_callback is not None:
            try:
                self._chunk_callback(chunk)
            except Exception:
                # Never let a UI/ASR error kill the audio stream.
                pass

    def start(self) -> None:
        if self._recording:
            return
        with self._lock:
            self._frames = []
        # ~100ms blocks at 16kHz keep streaming ASR snappy.
        block = int(self.sample_rate * 0.1)
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=block,
            callback=self._callback,
        )
        self._stream.start()
        self._recording = True

    def stop(self) -> np.ndarray:
        if not self._recording:
            return np.zeros(0, dtype=np.float32)
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self._recording = False
        with self._lock:
            if not self._frames:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._frames).astype(np.float32)
