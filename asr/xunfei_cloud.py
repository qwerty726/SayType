"""Xunfei (iFlytek) IAT real-time ASR backend.

Uses the iat-api.xfyun.cn WebSocket endpoint with HMAC-SHA256 URL auth.
The audio is 16kHz / 16-bit PCM mono, sent in ~40ms frames base64-encoded
inside JSON wrappers. Each response contains an incremental result; we
accumulate `pgs=apd` segments and emit partial text via the streaming
callback.

Free tier: 500 calls/day (per account). Production tier: 0.0015 RMB/sec.

Setup steps for the user:
1. Sign up at https://www.xfyun.cn/
2. Create a "Real-time Voice Dictation" (语音听写流式版) application
3. Copy APPID, APIKey, APISecret into Settings.

This module never imports `websocket` at module load - we only need it when
the user actually selects this backend, so the dependency stays optional.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import queue
import ssl
import threading
import time
from datetime import datetime
from time import mktime
from typing import Callable, Optional
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import numpy as np

from .base import ASRBackend


_HOST = "iat-api.xfyun.cn"
_PATH = "/v2/iat"
_FRAME_MS = 40
_FRAME_BYTES_16K = int(16000 * 2 * _FRAME_MS / 1000)  # 40ms at 16k mono 16bit = 1280 bytes
_STATUS_FIRST = 0
_STATUS_CONT = 1
_STATUS_LAST = 2


class XunfeiCloud(ASRBackend):
    name = "xunfei_cloud"

    def __init__(self, app_id: str, api_key: str, api_secret: str) -> None:
        self.app_id = app_id or ""
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""

        self._ws = None
        self._ws_thread: Optional[threading.Thread] = None
        self._send_q: queue.Queue = queue.Queue()
        self._partial_cb: Optional[Callable[[str], None]] = None

        # Output accumulator. Xunfei emits replacing / appending updates;
        # we track the assembled text per-segment.
        self._lock = threading.Lock()
        self._segments: list[str] = []   # finalized segments
        self._current: str = ""          # in-progress segment, may be replaced

        self._connected = threading.Event()
        self._closed = threading.Event()
        self._error: Optional[str] = None

    def warmup_async(self) -> None:
        # No model loading; nothing to warm.
        pass

    # ----------------------------------------------------- streaming API
    def begin_stream(self, partial_callback: Optional[Callable[[str], None]] = None) -> None:
        if not (self.app_id and self.api_key and self.api_secret):
            raise RuntimeError("讯飞凭据未配置 (APPID/APIKey/APISecret)")
        # Lazy import keeps the dep optional for users who don't use this backend.
        try:
            import websocket  # type: ignore  # noqa: F401
        except ImportError as e:  # noqa: BLE001
            raise RuntimeError("缺少 websocket-client，请先 pip install websocket-client") from e

        self._partial_cb = partial_callback
        with self._lock:
            self._segments = []
            self._current = ""
        self._error = None
        self._connected.clear()
        self._closed.clear()
        # Drain stale messages from any prior aborted session.
        try:
            while True:
                self._send_q.get_nowait()
        except queue.Empty:
            pass

        url = self._build_url()
        self._open_ws(url)
        # Wait briefly for handshake so the first push_chunk knows the
        # session is alive; if it never opens we'll surface the error on
        # end_stream() rather than blocking the audio path forever.
        self._connected.wait(timeout=5.0)
        # Send the first frame (empty payload, just the business config).
        self._enqueue_send_first()

    def push_chunk(self, chunk: np.ndarray, sample_rate: int) -> None:
        if chunk.size == 0:
            return
        if sample_rate != 16000:
            chunk = _resample_linear(chunk, sample_rate, 16000)
        # Convert float32 [-1,1] to int16 little-endian PCM.
        clipped = np.clip(chunk, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16).tobytes()
        # Slice into 40ms frames so the cloud sees a steady stream.
        for off in range(0, len(pcm), _FRAME_BYTES_16K):
            frame = pcm[off:off + _FRAME_BYTES_16K]
            if not frame:
                continue
            self._send_q.put(("cont", frame))

    def end_stream(self) -> str:
        # Tell the sender thread we're done; it will flush the last frame
        # with status=LAST and the server will respond with the final text.
        self._send_q.put(("last", b""))
        # Wait for the server to close (it does after sending the final result).
        self._closed.wait(timeout=10.0)
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        if self._error:
            raise RuntimeError(self._error)
        with self._lock:
            parts = self._segments[:]
            if self._current:
                parts.append(self._current)
            return "".join(parts).strip()

    # ----------------------------------------------------- one-shot
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        self.begin_stream()
        self.push_chunk(audio, sample_rate)
        return self.end_stream()

    # ----------------------------------------------------- WebSocket plumbing
    def _build_url(self) -> str:
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        sig_origin = f"host: {_HOST}\ndate: {date}\nGET {_PATH} HTTP/1.1"
        sig_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            sig_origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(sig_sha).decode()
        auth_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(auth_origin.encode("utf-8")).decode()
        params = {"authorization": authorization, "date": date, "host": _HOST}
        return f"wss://{_HOST}{_PATH}?" + urlencode(params)

    def _open_ws(self, url: str) -> None:
        import websocket  # type: ignore
        self._ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._ws_thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}},
            daemon=True,
        )
        self._ws_thread.start()

    def _on_open(self, _ws) -> None:
        self._connected.set()
        # Spawn sender that drains the queue and pushes audio frames.
        threading.Thread(target=self._sender_loop, daemon=True).start()

    def _sender_loop(self) -> None:
        first = True
        while True:
            try:
                kind, frame = self._send_q.get(timeout=8.0)
            except queue.Empty:
                # Idle for too long - bail to avoid leaking the connection.
                return

            if kind == "first":
                payload = self._build_payload(_STATUS_FIRST, frame)
                first = False
            elif kind == "last":
                payload = self._build_payload(_STATUS_LAST, frame)
                self._safe_send(payload)
                return
            else:
                status = _STATUS_FIRST if first else _STATUS_CONT
                payload = self._build_payload(status, frame)
                first = False

            self._safe_send(payload)
            # Pace at ~40ms; Xunfei expects a stream, not a flood.
            time.sleep(_FRAME_MS / 1000.0)

    def _enqueue_send_first(self) -> None:
        # Send an empty FIRST frame to register business params early.
        self._send_q.put(("first", b""))

    def _build_payload(self, status: int, frame: bytes) -> str:
        body: dict = {
            "data": {
                "status": status,
                "format": "audio/L16;rate=16000",
                "audio": base64.b64encode(frame).decode("ascii"),
                "encoding": "raw",
            },
        }
        if status == _STATUS_FIRST:
            body["common"] = {"app_id": self.app_id}
            body["business"] = {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "dwa": "wpgs",         # enable streaming-replace results
                "vad_eos": 5000,
            }
        return json.dumps(body)

    def _safe_send(self, payload: str) -> None:
        try:
            if self._ws is not None:
                self._ws.send(payload)
        except Exception as e:  # noqa: BLE001
            self._error = f"WebSocket send failed: {e}"

    def _on_message(self, _ws, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        code = data.get("code", 0)
        if code != 0:
            self._error = f"讯飞错误 code={code} msg={data.get('message')}"
            return

        result = data.get("data", {}).get("result", {})
        if not result:
            return

        # Assemble text from the words array.
        ws = result.get("ws", [])
        text = "".join(cw.get("w", "") for w in ws for cw in w.get("cw", []))

        # pgs=apd: append (new segment); pgs=rpl: replace previous range.
        pgs = result.get("pgs")
        with self._lock:
            if pgs == "rpl":
                rg = result.get("rg", [])
                # Replace the in-progress segment with this new candidate.
                # The replace range refers to prior segment indices; in
                # practice for our use we just overwrite the rolling
                # current segment.
                self._current = text
            elif pgs == "apd":
                # Previous current is now confirmed; push it and start new.
                if self._current:
                    self._segments.append(self._current)
                self._current = text
            else:
                # Final result for this utterance.
                self._current = text

            assembled = "".join(self._segments) + self._current

        if self._partial_cb:
            try:
                self._partial_cb(assembled)
            except Exception:
                pass

        # status=2 in the response means the server is done.
        if data.get("data", {}).get("status") == 2:
            self._closed.set()

    def _on_error(self, _ws, err) -> None:
        self._error = f"WebSocket error: {err}"
        self._closed.set()

    def _on_close(self, _ws, *_args) -> None:
        self._closed.set()


def _resample_linear(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    duration = audio.shape[0] / sr_in
    n_out = int(duration * sr_out)
    x_in = np.linspace(0, duration, audio.shape[0], endpoint=False)
    x_out = np.linspace(0, duration, n_out, endpoint=False)
    return np.interp(x_out, x_in, audio).astype(np.float32)
