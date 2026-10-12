from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QTransform


class RotateAngle:
    def __init__(self, degrees: float, autocrop: bool = True):
        self.degrees = float(degrees)
        self.autocrop = autocrop

    def apply(self, image: QImage) -> QImage:
        angle = self.degrees % 360.0
        if angle == 0.0:
            return image
        rotated = image.transformed(QTransform().rotate(angle), Qt.SmoothTransformation)
        if not self.autocrop:
            return rotated
        return _autocrop(rotated, image.width(), image.height(), angle)


def _autocrop(rotated: QImage, width: int, height: int, angle: float) -> QImage:
    scale = _largest_scale(width, height, angle)
    crop_w = max(1, int(width * scale))
    crop_h = max(1, int(height * scale))
    x = (rotated.width() - crop_w) // 2
    y = (rotated.height() - crop_h) // 2
    return rotated.copy(x, y, crop_w, crop_h)


def _largest_scale(width: int, height: int, angle: float) -> float:
    theta = math.radians(angle)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    half_w, half_h = width / 2.0, height / 2.0

    def fits(scale: float) -> bool:
        corner_w, corner_h = half_w * scale, half_h * scale
        for sx in (-corner_w, corner_w):
            for sy in (-corner_h, corner_h):
                x = sx * cos_t + sy * sin_t
                y = -sx * sin_t + sy * cos_t
                if abs(x) > half_w + 1e-6 or abs(y) > half_h + 1e-6:
                    return False
        return True

    low, high = 0.0, 1.0
    for _ in range(48):
        mid = (low + high) / 2.0
        if fits(mid):
            low = mid
        else:
            high = mid
    return low
