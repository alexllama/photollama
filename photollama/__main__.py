from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import single_instance
from .theme import Theme
from .window import MainWindow


def _app_icon() -> QIcon:
    icon = QIcon.fromTheme("photollama")
    if not icon.isNull():
        return icon
    bundled = os.path.join(os.path.dirname(__file__), "resources", "photollama.png")
    return QIcon(bundled)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    args = [arg for arg in argv[1:] if not arg.startswith("-")]

    if args and single_instance.forward(args):
        return 0

    app = QApplication(argv)
    app.setApplicationName("photollama")
    app.setApplicationDisplayName("Photollama")
    app.setDesktopFileName("photollama")
    app.setWindowIcon(_app_icon())

    theme = Theme()
    app.setPalette(theme.qpalette())
    app.setStyleSheet(theme.stylesheet())

    window = MainWindow(theme)
    server = single_instance.Server(window.open_path)
    if args:
        window.open_path(args[0])

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
