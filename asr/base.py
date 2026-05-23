"""ASR backend abstract interface.

A backend exposes two modes:
- transcribe(audio): one-shot recognition of a full utterance.
- streaming push_chunk(audio) / streaming_finalize(): incremental recognition
  used by the floating bar for real-time display. Backends that don't support
  true streaming fall back to buffering and full transcribe on finalize.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

import numpy as np


class ASRBackend(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """One-shot: take full PCM float32 mono audio, return text."""
        ...

    # Streaming API. Default implementation just buffers and runs a final
    # transcribe at the end - good enough as a fallback.
    def begin_stream(self, partial_callback: Optional[Callable[[str], None]] = None) -> None:
        self._stream_buf: list[np.ndarray] = []
        self._partial_cb = partial_callback

    def push_chunk(self, chunk: np.ndarray, sample_rate: int) -> None:
        if not hasattr(self, "_stream_buf"):
            self.begin_stream()
        self._stream_buf.append(chunk)
        self._stream_sr = sample_rate

    def end_stream(self) -> str:
        if not hasattr(self, "_stream_buf") or not self._stream_buf:
            return ""
        audio = np.concatenate(self._stream_buf).astype(np.float32)
        sr = getattr(self, "_stream_sr", 16000)
        self._stream_buf = []
        return self.transcribe(audio, sr)
