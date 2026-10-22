from __future__ import annotations

import math

import numpy as np
from PySide6.QtGui import QImage


def to_rgb_array(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGB888)
    width, height = converted.width(), converted.height()
    if width == 0 or height == 0:
        return np.zeros((0, 0, 3), np.uint8)
    raw = np.frombuffer(converted.constBits(), np.uint8)
    raw = raw[: converted.sizeInBytes()]
    rows = raw.reshape((height, converted.bytesPerLine()))[:, : width * 3]
    # copy() is essential: without it this is a view into the QImage buffer,
    # which is freed when ``converted`` goes out of scope (dangling pointer).
    return rows.reshape((height, width, 3)).copy()


def array_to_image(array: np.ndarray) -> QImage:
    height, width = array.shape[:2]
    buffer = np.ascontiguousarray(array).tobytes()
    return QImage(buffer, width, height, width * 3, QImage.Format_RGB888).copy()


def histogram(image: QImage) -> list[np.ndarray] | None:
    array = to_rgb_array(image)
    if array.size == 0:
        return None
    flat = array.reshape((-1, 3))
    return [np.bincount(flat[:, channel], minlength=256) for channel in range(3)]


def apply_lut(image: QImage, lut: np.ndarray) -> QImage:
    array = to_rgb_array(image)
    if array.size == 0:
        return image
    result = np.empty_like(array)
    for channel in range(3):
        result[:, :, channel] = lut[channel][array[:, :, channel]]
    return array_to_image(result)


def _as3(value) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        array = np.repeat(array, 3)
    return np.clip(array.reshape(3), 0, 255)


def build_levels_lut(in_black, in_white, gamma, out_black, out_white) -> np.ndarray:
    black = _as3(in_black)
    white = _as3(in_white)
    out_black = _as3(out_black)
    out_white = _as3(out_white)
    gamma = np.maximum(_as3(gamma), 0.01)
    span = white - black
    span[span == 0] = 1.0
    values = np.arange(256, dtype=float)[None, :]
    normalized = np.clip((values - black[:, None]) / span[:, None], 0.0, 1.0)
    shaped = np.power(normalized, 1.0 / gamma[:, None])
    output = out_black[:, None] + shaped * (out_white - out_black)[:, None]
    return np.clip(output, 0, 255).round().astype(np.uint8)


def levels_lut(in_black, in_white, gamma, out_black, out_white,
               channel: int | None = None) -> np.ndarray:
    """Levels LUT as a (3, 256) array.

    ``channel`` of ``None`` adjusts all channels (GIMP's "Value"); 0/1/2 targets
    only that colour channel and leaves the others untouched.
    """
    adjusted = build_levels_lut(in_black, in_white, gamma, out_black, out_white)
    if channel is None:
        return adjusted
    lut = np.tile(np.arange(256, dtype=np.uint8), (3, 1))
    lut[channel] = adjusted[channel]
    return lut


def gamma_to_handle(in_black: float, in_white: float, gamma: float) -> float:
    """Input value where the gamma (grey) point sits, for the given gamma."""
    span = max(in_white - in_black, 1.0)
    return in_black + (0.5 ** gamma) * span


def handle_to_gamma(in_black: float, in_white: float, value: float) -> float:
    """Gamma implied by the grey point sitting at ``value``."""
    span = max(in_white - in_black, 1.0)
    t = min(max((value - in_black) / span, 0.001), 0.999)
    return math.log(t) / math.log(0.5)

