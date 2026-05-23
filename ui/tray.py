"""System tray icon. Right-click menu: enable/disable, settings, quit."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


def _make_icon(color: str = "#1e90ff") -> QIcon:
    pix = QPixmap(QSize(32, 32))
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    # Stylized microphone: rounded capsule + base bar.
    p.drawRoundedRect(10, 4, 12, 18, 6, 6)
    p.setBrush(QColor("white"))
    p.drawRect(15, 23, 2, 5)
    p.drawRect(11, 27, 10, 2)
    p.end()
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        on_toggle_enabled: Callable[[bool], None],
        on_open_settings: Callable[[], None],
        on_quit: Callable[[], None],
        hotkey: str,
    ) -> None:
        super().__init__(_make_icon())
        self._on_toggle_enabled = on_toggle_enabled
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit
        self.setToolTip(f"语音输入法 - 按住 [{hotkey.upper()}] 说话")

        menu = QMenu()
        self._enabled_action = QAction("启用 (按住 " + hotkey.upper() + " 说话)", self)
        self._enabled_action.setCheckable(True)
        self._enabled_action.setChecked(True)
        self._enabled_action.toggled.connect(self._on_toggle_enabled)
        menu.addAction(self._enabled_action)

        menu.addSeparator()
        settings_action = QAction("设置...", self)
        settings_action.triggered.connect(self._on_open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def set_hotkey_label(self, hotkey: str) -> None:
        self.setToolTip(f"语音输入法 - 按住 [{hotkey.upper()}] 说话")
        self._enabled_action.setText("启用 (按住 " + hotkey.upper() + " 说话)")

    def notify(self, title: str, msg: str) -> None:
        self.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 2000)
