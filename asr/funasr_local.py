"""FunASR local backend.

Uses Paraformer-zh + FSMN-VAD + CT-Punc for high-quality offline Chinese
transcription. The model is lazy-loaded on first use (the constructor returns
fast so the UI starts immediately).

For phase 1/2 this is one-shot: stop recording -> transcribe full clip. The
streaming variant will be wired in later for partial display in the floating
bar.
"""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np

from .base import ASRBackend


class FunASRLocal(ASRBackend):
    name = "funasr_local"

    def __init__(
        self,
        model: str = "paraformer-zh",
        vad_model: str = "fsmn-vad",
        punc_model: str = "ct-punc",
        device: str = "cpu",
    ) -> None:
        self._model_name = model
        self._vad_name = vad_model
        self._punc_name = punc_model
        self._device = device
        self._model = None
        self._load_lock = threading.Lock()
        self._load_error: Optional[str] = None

    def ensure_loaded(self) -> None:
        if self._model is not None or self._load_error is not None:
            return
        with self._load_lock:
            if self._model is not None or self._load_error is not None:
                return
            try:
                from funasr import AutoModel  # type: ignore
                self._model = AutoModel(
                    model=self._model_name,
                    vad_model=self._vad_name,
                    punc_model=self._punc_name,
                    device=self._device,
                    disable_update=True,
                )
            except Exception as e:  # noqa: BLE001
                self._load_error = f"FunASR load failed: {e}"

    def warmup_async(self) -> None:
        threading.Thread(target=self.ensure_loaded, daemon=True).start()

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if audio.size == 0:
            return ""
        self.ensure_loaded()
        if self._load_error is not None or self._model is None:
            raise RuntimeError(self._load_error or "FunASR model unavailable")

        # FunASR expects float32 mono. Resample if user mic is not 16k.
        if sample_rate != 16000:
            audio = _resample_linear(audio, sample_rate, 16000)

        result = self._model.generate(input=audio, batch_size_s=60)
        if not result:
            return ""
        # result is a list of dicts with at least a "text" key.
        text = result[0].get("text", "").strip()
        return text


def _resample_linear(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    duration = audio.shape[0] / sr_in
    n_out = int(duration * sr_out)
    x_in = np.linspace(0, duration, audio.shape[0], endpoint=False)
    x_out = np.linspace(0, duration, n_out, endpoint=False)
    return np.interp(x_out, x_in, audio).astype(np.float32)
