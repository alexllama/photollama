from __future__ import annotations

import sys

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from .theme import Theme
from .window import MainWindow

APP_KEY = "photollama"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("Photollama")
    app.setApplicationDisplayName("Photollama")
    app.setDesktopFileName("photollama")

    args = [arg for arg in argv[1:] if not arg.startswith("-")]
    if args and _forward_to_existing(args):
        return 0

    theme = Theme()
    app.setPalette(theme.qpalette())
    app.setStyleSheet(theme.stylesheet())

    window = MainWindow(theme)
    if args:
        window.open_path(args[0])

    QLocalServer.removeServer(APP_KEY)
    server = QLocalServer()
    server.listen(APP_KEY)
    connections: list[QLocalSocket] = []

    def on_connection() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connections.append(connection)
            connection.readyRead.connect(
                lambda conn=connection: _handle_command(conn, window)
            )

    server.newConnection.connect(on_connection)
    window.show()
    return app.exec()


def _forward_to_existing(args: list[str]) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(APP_KEY)
    if socket.waitForConnected(200):
        socket.write("\n".join(args).encode("utf-8"))
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def _handle_command(connection: QLocalSocket, window: MainWindow) -> None:
    data = bytes(connection.readAll()).decode("utf-8", "ignore").strip()
    if data:
        window.open_path(data.splitlines()[0])
    connection.disconnectFromServer()


if __name__ == "__main__":
    raise SystemExit(main())
