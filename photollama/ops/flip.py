from __future__ import annotations

from PySide6.QtGui import QImage, QTransform


class Flip:
    def __init__(self, horizontal: bool = True):
        self.horizontal = horizontal
        self.vertical = not horizontal

    def apply(self, image: QImage) -> QImage:
        scale_x = -1 if self.horizontal else 1
        scale_y = -1 if self.vertical else 1
        return image.transformed(QTransform().scale(scale_x, scale_y))
