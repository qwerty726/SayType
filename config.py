"""Configuration manager - persists user settings to JSON."""
import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".voice_input"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "hotkey": "f2",
    "asr_backend": "funasr_streaming",   # funasr_streaming | funasr_local | xunfei_cloud
    "sample_rate": 16000,
    "auto_punctuation": True,
    "llm_polish_enabled": False,
    "llm_api_key": "",
    "llm_model": "deepseek-chat",
    "llm_base_url": "https://api.deepseek.com/v1",
    "voice_commands_enabled": True,
    "custom_vocabulary": [],
    "inject_method": "clipboard",        # clipboard | typewrite
    "show_floating_bar": True,
    "xunfei_app_id": "",
    "xunfei_api_key": "",
    "xunfei_api_secret": "",
}


class Config:
    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    @property
    def all(self) -> dict[str, Any]:
        return dict(self._data)


config = Config()
