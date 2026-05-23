"""Floating status bar shown at the bottom of the screen while recording.

States: idle (hidden), recording (red dot + live partial text), processing
(spinner + "识别中..."), error (red text). The bar is frameless, click-through
ignored, and always-on-top so it never steals focus from the user's target app.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QFont
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget


class FloatingBar(QWidget):
    # Signals so non-UI threads can drive state without touching widgets directly.
    sig_show_recording = pyqtSignal()
    sig_update_partial = pyqtSignal(str)
    sig_show_processing = pyqtSignal()
    sig_show_error = pyqtSignal(str)
    sig_hide = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color: #ff3b30; font-size: 14px;")
        self._label = QLabel("按住说话")
        f = QFont()
        f.setPointSize(11)
        self._label.setFont(f)
        self._label.setStyleSheet("color: white;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)
        layout.addWidget(self._dot)
        layout.addWidget(self._label)

        self.resize(360, 44)
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_dot)
        self._dot_on = True

        self.sig_show_recording.connect(self._on_show_recording)
        self.sig_update_partial.connect(self._on_update_partial)
        self.sig_show_processing.connect(self._on_show_processing)
        self.sig_show_error.connect(self._on_show_error)
        self.sig_hide.connect(self._on_hide)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(20, 20, 20, 220))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 18, 18)

    def _position_bottom_center(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + screen.height() - self.height() - 80
        self.move(x, y)

    def _toggle_dot(self) -> None:
        self._dot_on = not self._dot_on
        self._dot.setStyleSheet(
            "color: #ff3b30; font-size: 14px;"
            if self._dot_on
            else "color: rgba(255,59,48,80); font-size: 14px;"
        )

    def _on_show_recording(self) -> None:
        self._dot.setText("●")
        self._dot.setStyleSheet("color: #ff3b30; font-size: 14px;")
        self._label.setText("聆听中...")
        self._position_bottom_center()
        self.show()
        self._blink_timer.start(500)

    def _on_update_partial(self, text: str) -> None:
        # Trim if too long; show the tail so the latest words are visible.
        display = text if len(text) <= 36 else "..." + text[-33:]
        self._label.setText(display or "聆听中...")

    def _on_show_processing(self) -> None:
        self._blink_timer.stop()
        self._dot.setText("◌")
        self._dot.setStyleSheet("color: #ffd60a; font-size: 14px;")
        self._label.setText("识别中...")

    def _on_show_error(self, msg: str) -> None:
        self._blink_timer.stop()
        self._dot.setText("✕")
        self._dot.setStyleSheet("color: #ff453a; font-size: 14px;")
        self._label.setText(msg)
        QTimer.singleShot(2200, self.hide)

    def _on_hide(self) -> None:
        self._blink_timer.stop()
        self.hide()
