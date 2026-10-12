from __future__ import annotations

import os
import socket
import tempfile

from PySide6.QtCore import QObject, QSocketNotifier


def socket_path() -> str:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return os.path.join(runtime, f"photollama-{os.getuid()}.sock")


def forward(args: list[str], timeout: float = 0.3) -> bool:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(socket_path())
    except OSError:
        client.close()
        return False
    try:
        client.sendall("\n".join(args).encode("utf-8"))
    except OSError:
        pass
    finally:
        client.close()
    return True


class Server(QObject):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback
        self._path = socket_path()
        if os.path.exists(self._path):
            os.unlink(self._path)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(self._path)
        self._sock.listen(16)
        self._sock.setblocking(False)
        self._connections: list[tuple[socket.socket, QSocketNotifier]] = []
        self._notifier = QSocketNotifier(self._sock.fileno(), QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._accept)

    def _accept(self, *_) -> None:
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        conn.setblocking(False)
        notifier = QSocketNotifier(conn.fileno(), QSocketNotifier.Read, self)
        notifier.activated.connect(lambda *_, c=conn, n=notifier: self._read(c, n))
        self._connections.append((conn, notifier))

    def _read(self, conn: socket.socket, notifier: QSocketNotifier) -> None:
        try:
            data = conn.recv(65536)
        except OSError:
            data = b""
        if not data:
            notifier.setEnabled(False)
            notifier.deleteLater()
            try:
                conn.close()
            except OSError:
                pass
            self._connections = [(c, n) for c, n in self._connections if c is not conn]
            return
        text = data.decode("utf-8", "ignore").strip()
        if text:
            self._callback(text.splitlines()[0])
