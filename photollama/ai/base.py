from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage


@dataclass
class AIResult:
    image: QImage
    raw_bytes: bytes
    mime_type: str = "image/png"


class AIProviderError(Exception):
    pass


def image_to_png_data_uri(image: QImage) -> str:
    """Encode a QImage as a PNG data URI."""
    if image.isNull():
        raise AIProviderError("Cannot enhance a null image")
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    ok = image.save(buffer, "PNG")
    buffer.close()
    if not ok:
        raise AIProviderError("Failed to encode image as PNG")
    b64 = base64.b64encode(bytes(data)).decode("ascii")
    return f"data:image/png;base64,{b64}"


def image_to_png_bytes(image: QImage) -> bytes:
    if image.isNull():
        raise AIProviderError("Cannot enhance a null image")
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    ok = image.save(buffer, "PNG")
    buffer.close()
    if not ok:
        raise AIProviderError("Failed to encode image as PNG")
    return bytes(data)
