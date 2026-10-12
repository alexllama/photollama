from __future__ import annotations

import os
import re

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPainter
from PySide6.QtSvg import QSvgRenderer

RASTER_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".gif", ".webp", ".tif", ".tiff",
    ".bmp", ".ico", ".icns", ".jp2", ".j2k", ".pbm", ".pgm", ".ppm", ".xbm",
    ".xpm", ".tga", ".wbmp", ".mng", ".pdf",
}
VECTOR_EXTS = {".svg", ".svgz"}
SUPPORTED_EXTS = RASTER_EXTS | VECTOR_EXTS


def _natural_key(name: str) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTS


def list_images(folder: str) -> list[str]:
    try:
        entries = os.listdir(folder)
    except OSError:
        return []
    files = [
        name for name in entries
        if is_image(name) and os.path.isfile(os.path.join(folder, name))
    ]
    files.sort(key=_natural_key)
    return [os.path.join(folder, name) for name in files]


def load_image(path: str, target: QSize | None = None) -> QImage:
    ext = os.path.splitext(path)[1].lower()
    if ext in VECTOR_EXTS:
        return _load_svg(path, target)
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    if target is not None and target.isValid():
        size = reader.size()
        if size.isValid():
            size.scale(target, Qt.KeepAspectRatio)
            reader.setScaledSize(size)
    return reader.read()


def _load_svg(path: str, target: QSize | None) -> QImage:
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QImage()
    size = QSize(renderer.defaultSize())
    if size.isEmpty():
        size = QSize(1024, 1024)
    if target is not None and target.isValid():
        scaled = QSize(size)
        scaled.scale(target, Qt.KeepAspectRatio)
        if not scaled.isEmpty():
            size = scaled
    image = QImage(size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image
