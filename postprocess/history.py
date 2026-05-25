"""Transcription history persistence.

Appends each successful transcription to a JSONL file in the user's config
directory. Writes never block the inject pipeline: any I/O error is swallowed
with a stderr warning so a broken history file can't break voice input.

File: ~/.voice_input/history.jsonl
Record: {"ts": ISO8601, "original": str, "polished": str|null, "backend": str}
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime

from config import CONFIG_DIR, config

HISTORY_FILE = CONFIG_DIR / "history.jsonl"

_lock = threading.Lock()


def append_history(original: str, polished: str | None, backend: str) -> None:
    if not config.get("history_enabled"):
        return
    if not original:
        return

    record = {
        "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "original": original,
        "polished": polished if config.get("history_record_polish") else None,
        "backend": backend,
    }

    with _lock:
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            _prune_if_needed()
        except OSError as e:
            print(f"[history] write failed: {e}", file=sys.stderr)


def _prune_if_needed() -> None:
    max_entries = config.get("history_max")
    if not isinstance(max_entries, int) or max_entries <= 0:
        return
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= max_entries:
            return
        tail = lines[-max_entries:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.writelines(tail)
    except OSError as e:
        print(f"[history] prune failed: {e}", file=sys.stderr)


def read_history(limit: int | None = None) -> list[dict]:
    """Return history records, newest first. Returns [] on missing/unreadable file."""
    if not HISTORY_FILE.exists():
        return []
    with _lock:
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            print(f"[history] read failed: {e}", file=sys.stderr)
            return []

    records: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if limit is not None and limit > 0:
        records = records[-limit:]
    return list(reversed(records))


def clear_history() -> None:
    """Delete the history file. Missing file is a no-op."""
    with _lock:
        try:
            HISTORY_FILE.unlink(missing_ok=True)
        except OSError as e:
            print(f"[history] clear failed: {e}", file=sys.stderr)
