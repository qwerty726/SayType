"""FunASR streaming backend.

Uses `paraformer-zh-streaming` to emit incremental partial results during
recording, and `ct-punc` to add Chinese punctuation to the final text.

Design notes
------------
- Audio is delivered as ~100ms chunks (sounddevice). The streaming model
  consumes 600ms windows by default (chunk_size=[0, 10, 5]). We buffer
  internally and process whenever 600ms have accumulated.
- The model maintains state in a `cache` dict between calls. begin_stream()
  resets that cache; end_stream() flushes the residual with is_final=True.
- The model output is character-by-character with no punctuation. We
  append to a rolling string and call the partial callback so the UI shows
  live text. On end_stream we run the punctuation model once on the full
  string for the clean final result.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

import numpy as np

from .base import ASRBackend


_CHUNK_SIZE = [0, 10, 5]      # ~600ms latency
_ENC_LOOK_BACK = 4
_DEC_LOOK_BACK = 1
_CHUNK_STRIDE_16K = _CHUNK_SIZE[1] * 960   # 9600 samples at 16kHz = 600ms


class FunASRStreaming(ASRBackend):
    name = "funasr_streaming"

    def __init__(self, device: str = "cpu") -> None:
        self._device = device
        self._model_stream = None
        self._model_punc = None
        self._load_lock = threading.Lock()
        self._load_error: Optional[str] = None

        # Per-utterance streaming state.
        self._state_lock = threading.Lock()
        self._buffer = np.zeros(0, dtype=np.float32)
        self._cache: dict = {}
        self._accumulated = ""
        self._partial_cb: Optional[Callable[[str], None]] = None
        self._sr = 16000

    # ------------------------------------------------------------------ load
    def ensure_loaded(self) -> None:
        if (self._model_stream is not None and self._model_punc is not None) or self._load_error:
            return
        with self._load_lock:
            if (self._model_stream is not None and self._model_punc is not None) or self._load_error:
                return
            try:
                from funasr import AutoModel  # type: ignore
                self._model_stream = AutoModel(
                    model="paraformer-zh-streaming",
                    device=self._device,
                    disable_update=True,
                )
                self._model_punc = AutoModel(
                    model="ct-punc",
                    device=self._device,
                    disable_update=True,
                )
            except Exception as e:  # noqa: BLE001
                self._load_error = f"FunASR streaming load failed: {e}"

    def warmup_async(self) -> None:
        threading.Thread(target=self.ensure_loaded, daemon=True).start()

    # --------------------------------------------------------------- stream
    def begin_stream(self, partial_callback: Optional[Callable[[str], None]] = None) -> None:
        self.ensure_loaded()
        if self._load_error:
            raise RuntimeError(self._load_error)
        with self._state_lock:
            self._buffer = np.zeros(0, dtype=np.float32)
            self._cache = {}
            self._accumulated = ""
            self._partial_cb = partial_callback

    def push_chunk(self, chunk: np.ndarray, sample_rate: int) -> None:
        if chunk.size == 0:
            return
        if sample_rate != 16000:
            chunk = _resample_linear(chunk, sample_rate, 16000)
        self._sr = 16000

        with self._state_lock:
            self._buffer = np.concatenate([self._buffer, chunk.astype(np.float32)])
            # Process every complete 600ms window.
            while self._buffer.size >= _CHUNK_STRIDE_16K:
                window = self._buffer[:_CHUNK_STRIDE_16K]
                self._buffer = self._buffer[_CHUNK_STRIDE_16K:]
                cb = self._partial_cb
            # Run inference outside the lock so audio thread isn't blocked
            # if it ever calls push_chunk again concurrently.
                self._infer(window, is_final=False, cb=cb)

    def end_stream(self) -> str:
        with self._state_lock:
            residual = self._buffer
            self._buffer = np.zeros(0, dtype=np.float32)
            cb = self._partial_cb

        # Pad residual to at least one stride so the model accepts it.
        if residual.size < _CHUNK_STRIDE_16K:
            pad = np.zeros(_CHUNK_STRIDE_16K - residual.size, dtype=np.float32)
            residual = np.concatenate([residual, pad])
        self._infer(residual, is_final=True, cb=cb)

        text = self._accumulated.strip()
        if not text:
            return ""

        # Punctuation restore on the final string.
        try:
            res = self._model_punc.generate(input=text)
            if res and isinstance(res, list) and res[0].get("text"):
                text = res[0]["text"]
        except Exception:
            pass
        return text

    # --------------------------------------------------------------- one-shot
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        self.begin_stream(partial_callback=None)
        # Feed in one big chunk; push_chunk will slice into 600ms windows.
        self.push_chunk(audio, sample_rate)
        return self.end_stream()

    # --------------------------------------------------------------- internal
    def _infer(self, window: np.ndarray, is_final: bool, cb: Optional[Callable[[str], None]]) -> None:
        try:
            res = self._model_stream.generate(
                input=window,
                cache=self._cache,
                is_final=is_final,
                chunk_size=_CHUNK_SIZE,
                encoder_chunk_look_back=_ENC_LOOK_BACK,
                decoder_chunk_look_back=_DEC_LOOK_BACK,
            )
        except Exception:
            return
        if not res:
            return
        piece = res[0].get("text", "") if isinstance(res, list) else ""
        if piece:
            self._accumulated += piece
            if cb is not None:
                try:
                    cb(self._accumulated)
                except Exception:
                    pass


def _resample_linear(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    duration = audio.shape[0] / sr_in
    n_out = int(duration * sr_out)
    x_in = np.linspace(0, duration, audio.shape[0], endpoint=False)
    x_out = np.linspace(0, duration, n_out, endpoint=False)
    return np.interp(x_out, x_in, audio).astype(np.float32)
