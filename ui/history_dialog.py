"""History viewer dialog. Shows all recorded transcriptions in a table.

Actions:
- 复制: copy selected row's injected text to clipboard
- 再次注入: store text on the dialog and accept(); caller injects after the
  dialog closes so focus has returned to the previous application
- 清空全部: confirm + delete the JSONL file
"""
from __future__ import annotations

from datetime import datetime

import pyperclip
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from postprocess.history import clear_history, read_history


_BACKEND_LABELS = {
    "funasr_streaming": "流式",
    "funasr_local": "离线",
    "xunfei_cloud": "讯飞",
}


class HistoryDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("语音输入法 - 历史")
        self.resize(640, 480)

        # Set by "再次注入" so caller (Controller) injects after exec() returns.
        self.text_to_inject: str | None = None

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["时间", "文本", "引擎"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_button_state)

        self.copy_btn = QPushButton("复制")
        self.inject_btn = QPushButton("再次注入")
        self.clear_btn = QPushButton("清空全部")
        self.close_btn = QPushButton("关闭")
        self.copy_btn.clicked.connect(self._copy_selected)
        self.inject_btn.clicked.connect(self._inject_selected)
        self.clear_btn.clicked.connect(self._clear_all)
        self.close_btn.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self.copy_btn)
        buttons.addWidget(self.inject_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self._reload()

    def _reload(self) -> None:
        records = read_history()
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            original = rec.get("original", "")
            polished = rec.get("polished")
            shown = polished if polished else original
            other = original if polished else ""
            tooltip = f"ASR 原文: {original}" if polished else ""

            ts_item = QTableWidgetItem(_format_ts(rec.get("ts", "")))
            text_item = QTableWidgetItem(shown)
            if tooltip:
                text_item.setToolTip(tooltip)
            backend_item = QTableWidgetItem(_BACKEND_LABELS.get(rec.get("backend", ""), rec.get("backend", "")))

            # Stash the injected text on the row for retrieval by buttons.
            ts_item.setData(Qt.ItemDataRole.UserRole, shown)

            self.table.setItem(row, 0, ts_item)
            self.table.setItem(row, 1, text_item)
            self.table.setItem(row, 2, backend_item)

        self.setWindowTitle(f"语音输入法 - 历史 (共 {len(records)} 条)")
        self._update_button_state()

    def _update_button_state(self) -> None:
        has_selection = bool(self.table.selectionModel().selectedRows())
        self.copy_btn.setEnabled(has_selection)
        self.inject_btn.setEnabled(has_selection)
        self.clear_btn.setEnabled(self.table.rowCount() > 0)

    def _selected_text(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        ts_item = self.table.item(rows[0].row(), 0)
        if ts_item is None:
            return None
        return ts_item.data(Qt.ItemDataRole.UserRole)

    def _copy_selected(self) -> None:
        text = self._selected_text()
        if text:
            try:
                pyperclip.copy(text)
            except Exception:
                pass

    def _inject_selected(self) -> None:
        text = self._selected_text()
        if not text:
            return
        self.text_to_inject = text
        self.accept()

    def _clear_all(self) -> None:
        reply = QMessageBox.warning(
            self,
            "清空历史",
            "确定要删除全部历史记录吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_history()
            self._reload()


def _format_ts(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%m-%d %H:%M")
    except ValueError:
        return ts
