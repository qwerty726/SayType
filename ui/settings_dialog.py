"""Minimal settings dialog. Lets the user change hotkey, ASR backend, and
LLM-polish options without editing the JSON file by hand.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from config import config


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("语音输入法 - 设置")
        self.resize(440, 360)

        self.hotkey_edit = QLineEdit(config.get("hotkey"))
        self.hotkey_edit.setPlaceholderText("例如: f2, ctrl+space")

        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["funasr_local"])
        self.backend_combo.setCurrentText(config.get("asr_backend"))

        self.cmds_check = QCheckBox("启用语音指令 (换行/句号/删除 等)")
        self.cmds_check.setChecked(config.get("voice_commands_enabled"))

        self.polish_check = QCheckBox("启用 LLM 润色 (口语 → 书面, 高级模式)")
        self.polish_check.setChecked(config.get("llm_polish_enabled"))

        self.api_key_edit = QLineEdit(config.get("llm_api_key"))
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("DeepSeek / OpenAI 兼容 API Key")

        self.base_url_edit = QLineEdit(config.get("llm_base_url"))
        self.model_edit = QLineEdit(config.get("llm_model"))

        self.vocab_edit = QLineEdit(", ".join(config.get("custom_vocabulary") or []))
        self.vocab_edit.setPlaceholderText("逗号分隔的专业术语，例如: FunASR, Paraformer")

        form = QFormLayout()
        form.addRow("全局热键 (按住说话):", self.hotkey_edit)
        form.addRow("ASR 引擎:", self.backend_combo)
        form.addRow(self.cmds_check)
        form.addRow(self.polish_check)
        form.addRow("LLM API Key:", self.api_key_edit)
        form.addRow("LLM Base URL:", self.base_url_edit)
        form.addRow("LLM Model:", self.model_edit)
        form.addRow("自定义词库:", self.vocab_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _save_and_close(self) -> None:
        config.set("hotkey", self.hotkey_edit.text().strip() or "f2")
        config.set("asr_backend", self.backend_combo.currentText())
        config.set("voice_commands_enabled", self.cmds_check.isChecked())
        config.set("llm_polish_enabled", self.polish_check.isChecked())
        config.set("llm_api_key", self.api_key_edit.text().strip())
        config.set("llm_base_url", self.base_url_edit.text().strip())
        config.set("llm_model", self.model_edit.text().strip())
        vocab = [v.strip() for v in self.vocab_edit.text().split(",") if v.strip()]
        config.set("custom_vocabulary", vocab)
        self.accept()
