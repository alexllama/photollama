from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QColorSpace,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from .theme import Theme

MIN_ZOOM = 0.05
MAX_ZOOM = 40.0


class Canvas(QGraphicsView):
    zoom_changed = Signal(float)

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignCenter)
        self.setFrameShape(QGraphicsView.NoFrame)

        self._image: QImage | None = None
        self._zoom = 1.0
        self._fit_mode = True
        self._hist: list | None = None
        self._panning = False
        self._pan_last = QPoint()
        self.show_thirds = False
        self.show_histogram = False
        self.apply_theme()

    def apply_theme(self) -> None:
        self.setBackgroundBrush(self.theme.color("darker_background"))
        self.viewport().update()

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_image(self, image: QImage | None, reset_view: bool = True) -> None:
        if image is None or image.isNull():
            self._image = None
            self._item.setPixmap(QPixmap())
            self._scene.setSceneRect(QRectF())
            self._hist = None
            self.viewport().update()
            self._update_cursor()
            return
        self._image = image
        pixmap = QPixmap.fromImage(_to_srgb(image))
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._hist = None
        if reset_view:
            self.fit_to_window()
        else:
            self.viewport().update()
        self._update_cursor()

    def wheelEvent(self, event):
        if self._image is None:
            return
        step = event.angleDelta().y()
        if step == 0:
            return
        self._zoom_by(1.25 if step > 0 else 0.8)

    def zoom_in(self) -> None:
        self._zoom_by(1.25)

    def zoom_out(self) -> None:
        self._zoom_by(0.8)

    def zoom_actual(self) -> None:
        if self._image is None:
            return
        self.resetTransform()
        self._zoom = 1.0
        self._fit_mode = False
        self.centerOn(self._item)
        self.zoom_changed.emit(self._zoom)
        self._update_cursor()

    def fit_to_window(self) -> None:
        if self._image is None:
            return
        viewport = self.viewport().size()
        image_w = self._image.width()
        image_h = self._image.height()
        if image_w <= 0 or image_h <= 0 or viewport.width() <= 0:
            return
        scale = min(viewport.width() / image_w, viewport.height() / image_h)
        self.resetTransform()
        self.scale(scale, scale)
        self._zoom = scale
        self._fit_mode = True
        self.centerOn(self._item)
        self.zoom_changed.emit(self._zoom)
        self._update_cursor()

    def _zoom_by(self, factor: float) -> None:
        target = max(MIN_ZOOM, min(self._zoom * factor, MAX_ZOOM))
        if abs(target - self._zoom) < 1e-9:
            return
        applied = target / self._zoom
        self.scale(applied, applied)
        self._zoom = target
        self._fit_mode = False
        self.zoom_changed.emit(self._zoom)
        self._update_cursor()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit_to_window()
        self._update_cursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._image is not None:
            self._panning = True
            self._pan_last = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            pos = event.position().toPoint()
            delta = pos - self._pan_last
            self._pan_last = pos
            hbar = self.horizontalScrollBar()
            vbar = self.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() == Qt.LeftButton:
            self._panning = False
            self._update_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _update_cursor(self) -> None:
        if self._image is None:
            self.unsetCursor()
            return
        if (self.horizontalScrollBar().maximum() > 0
                or self.verticalScrollBar().maximum() > 0):
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._image is None:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        if self.show_thirds:
            self._draw_thirds(painter)
        if self.show_histogram:
            self._draw_histogram(painter)
        painter.end()

    def _draw_thirds(self, painter: QPainter) -> None:
        rect = self.mapFromScene(self._item.sceneBoundingRect()).boundingRect()
        color = self.theme.color("muted")
        color.setAlpha(170)
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidth(1)
        painter.setPen(pen)
        for i in (1, 2):
            x = rect.left() + rect.width() * i / 3.0
            y = rect.top() + rect.height() * i / 3.0
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    def _compute_histogram(self) -> list | None:
        if self._image is None:
            return None
        image = self._image.convertToFormat(QImage.Format_RGB888)
        width, height = image.width(), image.height()
        if width == 0 or height == 0:
            return None
        raw = np.frombuffer(image.constBits(), np.uint8)
        raw = raw[: image.sizeInBytes()]
        pixels = raw.reshape((height, image.bytesPerLine()))[:, : width * 3]
        pixels = pixels.reshape((height * width, 3))
        return [np.bincount(pixels[:, channel], minlength=256) for channel in range(3)]

    def _draw_histogram(self, painter: QPainter) -> None:
        if self._hist is None:
            self._hist = self._compute_histogram()
        if not self._hist:
            return
        box_w, box_h, margin = 240, 130, 14
        viewport = self.viewport().rect()
        x = viewport.right() - box_w - margin
        y = viewport.bottom() - box_h - margin
        background = self.theme.color("dark_background")
        background.setAlpha(205)
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(x, y, box_w, box_h), 6, 6)

        peak = max(1, max(int(channel.max()) for channel in self._hist))
        colors = (QColor(235, 90, 90), QColor(100, 215, 100), QColor(95, 145, 245))
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for values, base in zip(self._hist, colors):
            path = QPainterPath()
            path.moveTo(x, y + box_h)
            for i in range(256):
                level = float(values[i]) / peak
                path.lineTo(x + box_w * i / 255.0, y + box_h - level * (box_h - 8))
            path.lineTo(x + box_w, y + box_h)
            line = QColor(base)
            line.setAlpha(150)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(line, 1))
            painter.drawPath(path)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)


def _to_srgb(image: QImage) -> QImage:
    space = image.colorSpace()
    if space.isValid() and space != QColorSpace(QColorSpace.SRgb):
        try:
            return image.convertedToColorSpace(QColorSpace(QColorSpace.SRgb))
        except Exception:
            return image
    return image
