from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

HANDLE = 9
ASPECTS = [
    ("Free", None),
    ("Original", "original"),
    ("1:1", 1.0),
    ("4:3", 4 / 3),
    ("3:2", 3 / 2),
    ("16:9", 16 / 9),
    ("9:16", 9 / 16),
]


class CropView(QGraphicsView):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem(QPixmap.fromImage(image))
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignCenter)
        self.setFrameShape(QGraphicsView.NoFrame)

        self._w = image.width()
        self._h = image.height()
        self._crop = QRectF(self._w * 0.05, self._h * 0.05, self._w * 0.9, self._h * 0.9)
        self._aspect: float | None = None
        self._mode: str | None = None
        self._start = QPoint()
        self._orig = QRectF(self._crop)
        self._scene.setSceneRect(QRectF(0, 0, self._w, self._h))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def set_aspect(self, aspect) -> None:
        if aspect == "original":
            self._aspect = self._w / self._h if self._h else None
        else:
            self._aspect = aspect
        if self._aspect:
            self._crop = self._apply_aspect_to(QRectF(self._crop))
        self._crop = self._clamp(self._crop)
        self.viewport().update()

    def crop_rect(self) -> QRect:
        rect = self._crop.normalized()
        return QRect(
            int(rect.left()), int(rect.top()),
            max(1, int(rect.width())), max(1, int(rect.height())),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def _handle_points(self) -> dict[str, QPoint]:
        rect = self._crop_viewport_rect()
        return {
            "tl": rect.topLeft(),
            "tr": rect.topRight(),
            "bl": rect.bottomLeft(),
            "br": rect.bottomRight(),
            "t": QPoint((rect.left() + rect.right()) // 2, rect.top()),
            "b": QPoint((rect.left() + rect.right()) // 2, rect.bottom()),
            "l": QPoint(rect.left(), (rect.top() + rect.bottom()) // 2),
            "r": QPoint(rect.right(), (rect.top() + rect.bottom()) // 2),
        }

    def _handle_at(self, pos: QPoint) -> str:
        tolerance = HANDLE // 2 + 3
        for name, point in self._handle_points().items():
            if abs(pos.x() - point.x()) <= tolerance and abs(pos.y() - point.y()) <= tolerance:
                return name
        if self._crop_viewport_rect().contains(pos):
            return "move"
        return "new"

    def _crop_viewport_rect(self) -> QRect:
        return self.mapFromScene(self._crop).boundingRect()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        self._mode = self._handle_at(pos)
        self._start = pos
        self._orig = QRectF(self._crop)
        if self._mode == "new":
            scene_pos = self.mapToScene(pos)
            self._crop = QRectF(scene_pos, scene_pos)
        self.viewport().update()

    def mouseMoveEvent(self, event):
        if self._mode is None:
            return
        pos = event.position().toPoint()
        scene_pos = self.mapToScene(pos)
        if self._mode == "move":
            delta = scene_pos - self.mapToScene(self._start)
            self._crop = self._clamp(QRectF(self._orig).translated(delta))
        elif self._mode == "new":
            rect = QRectF(self.mapToScene(self._start), scene_pos).normalized()
            if self._aspect:
                rect = self._apply_aspect_to(rect)
            self._crop = self._clamp(rect)
        else:
            self._resize(self._mode, scene_pos)
        self.viewport().update()

    def mouseReleaseEvent(self, event):
        if self._crop.width() < 8 or self._crop.height() < 8:
            self._crop = QRectF(0, 0, self._w, self._h)
        self._mode = None
        self.viewport().update()

    def _resize(self, handle: str, scene_pos: QPointF) -> None:
        x = min(max(scene_pos.x(), 0.0), float(self._w))
        y = min(max(scene_pos.y(), 0.0), float(self._h))
        rect = QRectF(self._crop)
        if "l" in handle:
            rect.setLeft(x)
        if "r" in handle:
            rect.setRight(x)
        if "t" in handle:
            rect.setTop(y)
        if "b" in handle:
            rect.setBottom(y)
        rect = rect.normalized()
        if self._aspect:
            rect = self._apply_aspect_to(rect, handle)
        self._crop = self._clamp(rect)

    def _apply_aspect_to(self, rect: QRectF, handle: str | None = None) -> QRectF:
        aspect = self._aspect
        if not aspect or rect.height() <= 0 or rect.width() <= 0:
            return rect
        center = rect.center()
        width = rect.width()
        height = width / aspect
        if height > self._h:
            height = self._h
            width = height * aspect
        if width > self._w:
            width = self._w
            height = width / aspect
        if handle in ("t", "b") or (handle is None and rect.height() > rect.width()):
            width = rect.height() * aspect
            height = rect.height()
        return QRectF(
            center.x() - width / 2, center.y() - height / 2, width, height
        )

    def _clamp(self, rect: QRectF) -> QRectF:
        rect = rect.normalized()
        if rect.width() > self._w:
            rect.setWidth(float(self._w))
        if rect.height() > self._h:
            rect.setHeight(float(self._h))
        if rect.left() < 0:
            rect.moveLeft(0.0)
        if rect.top() < 0:
            rect.moveTop(0.0)
        if rect.right() > self._w:
            rect.moveRight(float(self._w))
        if rect.bottom() > self._h:
            rect.moveBottom(float(self._h))
        return rect

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)

        image_rect = self.mapFromScene(QRectF(0, 0, self._w, self._h)).boundingRect()
        crop_rect = self._crop_viewport_rect()

        shade = QPainterPath()
        shade.setFillRule(Qt.OddEvenFill)
        shade.addRect(QRectF(image_rect))
        shade.addRect(QRectF(crop_rect))
        painter.fillPath(shade, QColor(0, 0, 0, 140))

        accent = QColor("#7fbbb3")
        pen = QPen(accent)
        pen.setCosmetic(True)
        pen.setWidth(1)
        painter.setPen(pen)
        for i in (1, 2):
            x = crop_rect.left() + crop_rect.width() * i / 3.0
            y = crop_rect.top() + crop_rect.height() * i / 3.0
            painter.drawLine(QPointF(x, crop_rect.top()), QPointF(x, crop_rect.bottom()))
            painter.drawLine(QPointF(crop_rect.left(), y), QPointF(crop_rect.right(), y))

        border = QPen(accent)
        border.setCosmetic(True)
        border.setWidth(2)
        painter.setPen(border)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(crop_rect))

        painter.setBrush(QBrush(accent))
        for point in self._handle_points().values():
            painter.drawRect(
                QRectF(point.x() - HANDLE / 2, point.y() - HANDLE / 2, HANDLE, HANDLE)
            )
        painter.end()


class CropDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop")
        self.setMinimumSize(720, 560)

        self.view = CropView(image)

        self.aspect = QComboBox()
        for label, value in ASPECTS:
            self.aspect.addItem(label, value)
        self.aspect.currentIndexChanged.connect(self._aspect_changed)

        ratio_row = QHBoxLayout()
        ratio_row.addWidget(QLabel("Aspect ratio:"))
        ratio_row.addWidget(self.aspect)
        ratio_row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view, 1)
        layout.addLayout(ratio_row)
        layout.addWidget(buttons)

    def _aspect_changed(self, index: int) -> None:
        self.view.set_aspect(self.aspect.itemData(index))

    def crop_rect(self) -> QRect:
        return self.view.crop_rect()
