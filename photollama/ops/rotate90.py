from __future__ import annotations

from PySide6.QtGui import QImage, QTransform


class Rotate90:
    def __init__(self, clockwise: bool = True):
        self.clockwise = clockwise

    def apply(self, image: QImage) -> QImage:
        angle = 90 if self.clockwise else -90
        return image.transformed(QTransform().rotate(angle))
