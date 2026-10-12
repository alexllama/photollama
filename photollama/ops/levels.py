from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage

from ..imaging import apply_lut, build_levels_lut


class Levels:
    def __init__(self, in_black=0, in_white=255, gamma=1.0, out_black=0, out_white=255):
        self.in_black = in_black
        self.in_white = in_white
        self.gamma = gamma
        self.out_black = out_black
        self.out_white = out_white
        self._lut: np.ndarray | None = None

    def lut(self) -> np.ndarray:
        if self._lut is None:
            self._lut = build_levels_lut(
                self.in_black, self.in_white, self.gamma,
                self.out_black, self.out_white,
            )
        return self._lut

    def apply(self, image: QImage) -> QImage:
        return apply_lut(image, self.lut())
