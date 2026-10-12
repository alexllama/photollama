from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage


class Crop:
    def __init__(self, rect: QRect):
        self.rect = QRect(rect)

    def apply(self, image: QImage) -> QImage:
        rect = self.rect.intersected(image.rect())
        if rect.isEmpty():
            return image
        return image.copy(rect)
