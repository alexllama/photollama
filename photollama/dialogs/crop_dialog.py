from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSettings, QSize, Qt
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
    ("3:4", 3 / 4),
    ("3:2", 3 / 2),
    ("2:3", 2 / 3),
    ("16:9", 16 / 9),
    ("9:16", 9 / 16),
]

_SETTINGS_ORG = "photollama"
_SETTINGS_APP = "photollama"


def load_crop_state() -> tuple[str | None, QSize | None]:
    """Last used aspect label and crop size (in source pixels), if any."""
    settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    label = settings.value("crop/aspect")
    width = settings.value("crop/width")
    height = settings.value("crop/height")
    size = None
    try:
        if width is not None and height is not None:
            w, h = int(width), int(height)
            if w > 0 and h > 0:
                size = QSize(w, h)
    except (TypeError, ValueError):
        size = None
    return (str(label) if label else None, size)


def save_crop_state(label: str, size: QSize) -> None:
    settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    settings.setValue("crop/aspect", label)
    settings.setValue("crop/width", size.width())
    settings.setValue("crop/height", size.height())


class CropView(QGraphicsView):
    def __init__(self, image, parent=None, crop_size: QSize | None = None):
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
        if crop_size is not None and crop_size.width() > 0 and crop_size.height() > 0:
            w = min(crop_size.width(), self._w)
            h = min(crop_size.height(), self._h)
            self._crop = QRectF((self._w - w) / 2, (self._h - h) / 2, w, h)
        else:
            self._crop = QRectF(self._w * 0.05, self._h * 0.05, self._w * 0.9, self._h * 0.9)
        self._aspect: float | None = None
        self._mode: str | None = None
        self._start = QPoint()
        self._orig = QRectF(self._crop)
        self._anchor_scene = QPointF()
        self._scene.setSceneRect(QRectF(0, 0, self._w, self._h))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def set_aspect(self, aspect) -> None:
        if aspect == "original":
            self._aspect = self._w / self._h if self._h else None
        else:
            self._aspect = aspect
        if self._aspect:
            self._crop = self._fit_aspect(self._crop)
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
            self._anchor_scene = scene_pos
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
            self._crop = self._clamp(self._rect_from_anchor(self._anchor_scene, scene_pos))
        else:
            self._crop = self._clamp(self._resize(self._mode, scene_pos))
        self.viewport().update()

    def mouseReleaseEvent(self, event):
        if self._crop.width() < 8 or self._crop.height() < 8:
            self._crop = QRectF(0, 0, self._w, self._h)
        self._mode = None
        self.viewport().update()

    def _resize(self, handle: str, scene_pos: QPointF) -> QRectF:
        x = min(max(scene_pos.x(), 0.0), float(self._w))
        y = min(max(scene_pos.y(), 0.0), float(self._h))
        rect = QRectF(self._crop).normalized()
        left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
        if "l" in handle:
            left = x
        if "r" in handle:
            right = x
        if "t" in handle:
            top = y
        if "b" in handle:
            bottom = y
        rect = QRectF(
            QPointF(min(left, right), min(top, bottom)),
            QPointF(max(left, right), max(top, bottom)),
        )
        if self._aspect:
            rect = self._apply_aspect_to(rect, handle)
        return rect

    def _apply_aspect_to(self, rect: QRectF, handle: str) -> QRectF:
        aspect = self._aspect
        if not aspect:
            return rect
        if handle == "br":
            ax, ay = rect.left(), rect.top()
        elif handle == "tl":
            ax, ay = rect.right(), rect.bottom()
        elif handle == "tr":
            ax, ay = rect.left(), rect.bottom()
        elif handle == "bl":
            ax, ay = rect.right(), rect.top()
        elif handle == "r":
            ax, ay = rect.left(), rect.center().y()
        elif handle == "l":
            ax, ay = rect.right(), rect.center().y()
        elif handle == "b":
            ax, ay = rect.center().x(), rect.top()
        else:
            ax, ay = rect.center().x(), rect.bottom()

        if handle in ("l", "r", "tl", "tr", "bl", "br"):
            by_width = (rect.width(), rect.width() / aspect)
            by_height = (rect.height() * aspect, rect.height())
            width, height = by_width if by_width[0] * by_width[1] >= by_height[0] * by_height[1] else by_height
        else:
            width, height = rect.height() * aspect, rect.height()

        width = max(width, 1.0)
        height = max(height, 1.0)
        if handle == "br":
            x, y = ax, ay
        elif handle == "bl":
            x, y = ax - width, ay
        elif handle == "tr":
            x, y = ax, ay - height
        elif handle == "tl":
            x, y = ax - width, ay - height
        elif handle == "r":
            x, y = ax, ay - height / 2
        elif handle == "l":
            x, y = ax - width, ay - height / 2
        elif handle == "b":
            x, y = ax - width / 2, ay
        else:
            x, y = ax - width / 2, ay - height
        return QRectF(x, y, width, height)

    def _rect_from_anchor(self, anchor: QPointF, current: QPointF) -> QRectF:
        if not self._aspect:
            return QRectF(anchor, current).normalized()
        aspect = self._aspect
        dx = abs(current.x() - anchor.x())
        dy = abs(current.y() - anchor.y())
        if dx >= dy * aspect:
            width = max(dx, 1.0)
            height = width / aspect
        else:
            height = max(dy, 1.0)
            width = height * aspect
        x = anchor.x() if current.x() >= anchor.x() else anchor.x() - width
        y = anchor.y() if current.y() >= anchor.y() else anchor.y() - height
        return QRectF(x, y, width, height)

    def _fit_aspect(self, rect: QRectF) -> QRectF:
        aspect = self._aspect
        if not aspect:
            return QRectF(rect)
        center = rect.center()
        width = min(rect.width(), float(self._w))
        height = width / aspect
        if height > self._h:
            height = float(self._h)
            width = height * aspect
        return QRectF(center.x() - width / 2, center.y() - height / 2, width, height)

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
    def __init__(self, image, parent=None, aspect_label: str | None = None,
                 crop_size: QSize | None = None):
        super().__init__(parent)
        self.setWindowTitle("Crop")
        self.setMinimumSize(720, 560)

        self.view = CropView(image, crop_size=crop_size)

        self.aspect = QComboBox()
        default_index = 0
        wanted_index = None
        for i, (label, value) in enumerate(ASPECTS):
            self.aspect.addItem(label, value)
            if label == "Original":
                default_index = i
            if aspect_label and label == aspect_label:
                wanted_index = i
        self.aspect.currentIndexChanged.connect(self._aspect_changed)
        self.aspect.setCurrentIndex(wanted_index if wanted_index is not None else default_index)

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

    def aspect_label(self) -> str:
        return self.aspect.currentText()
