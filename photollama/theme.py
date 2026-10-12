from __future__ import annotations

import os
import tomllib

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor, QPalette

COLORS_PATH = os.path.expanduser("~/.local/state/omarchy/current/theme/colors.toml")

DEFAULTS = {
    "mode": "dark",
    "background": "#1e1e1e",
    "dark_background": "#161616",
    "darker_background": "#101010",
    "lighter_background": "#2a2a2a",
    "foreground": "#dcdcdc",
    "dark_foreground": "#6a6a6a",
    "light_foreground": "#a0a0a0",
    "bright_foreground": "#ffffff",
    "muted": "#5a5a5a",
    "accent": "#4aa3df",
    "selection": "#334455",
}


class Theme(QObject):
    changed = Signal()

    def __init__(self, path: str = COLORS_PATH, parent=None):
        super().__init__(parent)
        self._path = path
        self.colors = dict(DEFAULTS)
        self._mtime: float | None = None
        self.reload()
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _poll(self) -> None:
        try:
            mtime = os.stat(self._path).st_mtime
        except OSError:
            return
        if mtime != self._mtime:
            self.reload()

    def reload(self) -> None:
        data = {}
        try:
            with open(self._path, "rb") as handle:
                loaded = tomllib.load(handle)
            data = {k: v for k, v in loaded.items() if isinstance(v, str)}
        except (OSError, tomllib.TOMLDecodeError):
            pass
        self.colors = {**DEFAULTS, **data}
        try:
            self._mtime = os.stat(self._path).st_mtime
        except OSError:
            self._mtime = None
        self.changed.emit()

    def color(self, key: str) -> QColor:
        value = self.colors.get(key, DEFAULTS.get(key, "#000000"))
        color = QColor(value)
        if not color.isValid():
            color = QColor(DEFAULTS.get(key, "#000000"))
        return color

    def qpalette(self) -> QPalette:
        palette = QPalette()
        background = self.color("background")
        dark = self.color("darker_background")
        mid = self.color("dark_background")
        foreground = self.color("foreground")
        accent = self.color("accent")
        muted = self.color("muted")

        palette.setColor(QPalette.Window, background)
        palette.setColor(QPalette.WindowText, foreground)
        palette.setColor(QPalette.Base, dark)
        palette.setColor(QPalette.AlternateBase, mid)
        palette.setColor(QPalette.Text, foreground)
        palette.setColor(QPalette.Button, mid)
        palette.setColor(QPalette.ButtonText, foreground)
        palette.setColor(QPalette.BrightText, self.color("bright_foreground"))
        palette.setColor(QPalette.Highlight, accent)
        palette.setColor(QPalette.HighlightedText, dark)
        palette.setColor(QPalette.ToolTipBase, mid)
        palette.setColor(QPalette.ToolTipText, foreground)
        palette.setColor(QPalette.PlaceholderText, muted)
        palette.setColor(QPalette.Link, accent)

        for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
            palette.setColor(QPalette.Disabled, role, muted)
        return palette

    def stylesheet(self) -> str:
        c = self.colors
        return f"""
        QMainWindow, QWidget {{ background: {c['background']}; color: {c['foreground']}; }}
        QLabel#TopBar {{
            padding: 4px 10px;
            background: {c['dark_background']};
            color: {c['foreground']};
        }}
        QStatusBar {{ background: {c['dark_background']}; color: {c['foreground']}; }}
        QStatusBar::item {{ border: none; }}
        QMenuBar {{ background: {c['dark_background']}; color: {c['foreground']}; }}
        QMenuBar::item {{ padding: 4px 8px; background: transparent; }}
        QMenuBar::item:selected {{ background: {c['accent']}; color: {c['background']}; }}
        QMenu {{ background: {c['dark_background']}; color: {c['foreground']};
                 border: 1px solid {c['muted']}; }}
        QMenu::item {{ padding: 4px 22px 4px 18px; }}
        QMenu::item:selected {{ background: {c['accent']}; color: {c['background']}; }}
        QToolTip {{ background: {c['dark_background']}; color: {c['foreground']};
                    border: 1px solid {c['muted']}; }}
        """
