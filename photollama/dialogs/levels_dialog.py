from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..imaging import apply_lut, gamma_to_handle, handle_to_gamma, histogram, levels_lut
from ..ops import Levels

CHANNELS = (("Value", None), ("Red", 0), ("Green", 1), ("Blue", 2))
CHANNEL_COLORS = {
    0: QColor(235, 90, 90),
    1: QColor(100, 215, 100),
    2: QColor(95, 145, 245),
    None: QColor(205, 205, 205),
}
DEFAULTS = {"in_black": 0, "in_white": 255, "gamma": 1.0, "out_black": 0, "out_white": 255}

OUT_BAR_H = 16
HANDLE_H = 11
HANDLE_W = 11
GRAB = 8


class LevelsView(QWidget):
    """GIMP-style histogram with draggable input/output level handles."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self._hist: list[np.ndarray] | None = None
        self.channel: int | None = None
        self.in_black = 0
        self.in_white = 255
        self.gamma = 1.0
        self.out_black = 0
        self.out_white = 255
        self._drag: str | None = None

    def set_histogram(self, hist) -> None:
        self._hist = hist
        self.update()

    def set_channel(self, channel: int | None) -> None:
        self.channel = channel
        self.update()

    def set_values(self, in_black, in_white, gamma, out_black, out_white) -> None:
        self.in_black = int(in_black)
        self.in_white = int(in_white)
        self.gamma = float(gamma)
        self.out_black = int(out_black)
        self.out_white = int(out_white)
        self.update()

    def values(self) -> tuple:
        return (self.in_black, self.in_white, self.gamma, self.out_black, self.out_white)

    # -- geometry ---------------------------------------------------------
    def _baseline(self) -> float:
        return float(max(HANDLE_H, self.height() - OUT_BAR_H - HANDLE_H - 6))

    def _hist_rect(self) -> QRect:
        return QRect(0, 0, max(1, self.width()), max(1, int(self._baseline())))

    def _out_rect(self) -> QRect:
        top = max(0, self.height() - OUT_BAR_H)
        return QRect(0, top, max(1, self.width()), OUT_BAR_H)

    def _out_handle_y(self) -> float:
        return float(self._out_rect().top() + 2)

    def _x_for(self, value: float) -> float:
        span = max(1, self.width() - 1)
        return min(max(value, 0.0), 255.0) / 255.0 * span

    def _value_for(self, x: float) -> int:
        span = max(1, self.width() - 1)
        return int(round(min(max(x, 0.0), span) / span * 255))

    def _gamma_x(self) -> float:
        return self._x_for(gamma_to_handle(self.in_black, self.in_white, self.gamma))

    # -- interaction ------------------------------------------------------
    def _hit_input(self, pos: QPointF) -> str | None:
        baseline = self._baseline()
        if not (baseline - HANDLE_H - 2 <= pos.y() <= baseline + 2):
            return None
        candidates = [
            ("in_black", self._x_for(self.in_black)),
            ("gamma", self._gamma_x()),
            ("in_white", self._x_for(self.in_white)),
        ]
        name, x = min(candidates, key=lambda c: abs(c[1] - pos.x()))
        return name if abs(x - pos.x()) <= GRAB else None

    def _hit_output(self, pos: QPointF) -> str | None:
        base_y = self._out_handle_y()
        if not (base_y - HANDLE_H - 2 <= pos.y() <= base_y + 3):
            return None
        candidates = [
            ("out_black", self._x_for(self.out_black)),
            ("out_white", self._x_for(self.out_white)),
        ]
        name, x = min(candidates, key=lambda c: abs(c[1] - pos.x()))
        return name if abs(x - pos.x()) <= GRAB else None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position()
        self._drag = self._hit_input(pos) or self._hit_output(pos)
        if self._drag:
            self.setCursor(Qt.SizeHorCursor)

    def mouseMoveEvent(self, event):
        if self._drag is None:
            return
        value = self._value_for(event.position().x())
        if self._drag == "in_black":
            self.in_black = min(value, self.in_white - 1)
        elif self._drag == "in_white":
            self.in_white = max(value, self.in_black + 1)
        elif self._drag == "gamma":
            self.gamma = min(max(handle_to_gamma(self.in_black, self.in_white, value), 0.10), 10.0)
        elif self._drag == "out_black":
            self.out_black = min(value, self.out_white - 1)
        elif self._drag == "out_white":
            self.out_white = max(value, self.out_black + 1)
        self.changed.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None
        self.unsetCursor()

    # -- painting ---------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101010"))
        hist_rect = self._hist_rect()
        out_rect = self._out_rect()
        self._paint_histogram(painter, hist_rect)
        self._paint_output(painter, out_rect)

        baseline = self._baseline()
        out_y = self._out_handle_y()
        self._handle(painter, self._x_for(self.in_black), baseline, QColor(20, 20, 20))
        self._handle(painter, self._gamma_x(), baseline, QColor(150, 150, 150))
        self._handle(painter, self._x_for(self.in_white), baseline, QColor(245, 245, 245))
        self._handle(painter, self._x_for(self.out_black), out_y, QColor(20, 20, 20))
        self._handle(painter, self._x_for(self.out_white), out_y, QColor(245, 245, 245))
        painter.end()

    def _paint_histogram(self, painter: QPainter, rect: QRect) -> None:
        if not self._hist:
            return
        if self.channel is None:
            values = self._hist[0].astype(np.int64) + self._hist[1] + self._hist[2]
        else:
            values = self._hist[self.channel]
        color = CHANNEL_COLORS[self.channel]
        peak = max(1, int(values.max()))
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        for i in range(256):
            level = float(values[i]) / peak
            path.lineTo(
                rect.left() + rect.width() * i / 255.0,
                rect.bottom() - level * (rect.height() - 6),
            )
        path.lineTo(rect.right(), rect.bottom())
        fill = QColor(color)
        fill.setAlpha(90)
        painter.setBrush(QBrush(fill))
        painter.setPen(color)
        painter.drawPath(path)

    def _paint_output(self, painter: QPainter, rect: QRect) -> None:
        gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        gradient.setColorAt(0.0, Qt.black)
        gradient.setColorAt(1.0, Qt.white)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRect(rect)

    def _handle(self, painter: QPainter, x: float, base_y: float, color: QColor) -> None:
        points = QPolygonF([
            QPointF(x, base_y - HANDLE_H),
            QPointF(x - HANDLE_W / 2, base_y),
            QPointF(x + HANDLE_W / 2, base_y),
        ])
        painter.setBrush(QBrush(color))
        painter.setPen(QColor(15, 15, 15))
        painter.drawPolygon(points)


class LevelsDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Levels")
        self.setMinimumWidth(600)
        self._image = image
        self._state = {key: dict(DEFAULTS) for _, key in CHANNELS}
        self._channel: int | None = None
        self._updating = False

        self.view = LevelsView()
        self.view.set_histogram(histogram(image))
        self.view.changed.connect(self._view_changed)

        self.channel = QComboBox()
        for label, key in CHANNELS:
            self.channel.addItem(label, key)
        self.channel.currentIndexChanged.connect(self._channel_changed)

        self.in_black = self._int_spin()
        self.in_white = self._int_spin()
        self.out_black = self._int_spin()
        self.out_white = self._int_spin()
        self.gamma = QDoubleSpinBox()
        self.gamma.setRange(0.10, 10.00)
        self.gamma.setSingleStep(0.01)
        self.gamma.setDecimals(2)
        for spin in (self.in_black, self.in_white, self.gamma, self.out_black, self.out_white):
            spin.valueChanged.connect(self._spin_changed)

        self.preview_check = QCheckBox("Preview")
        self.preview_check.setChecked(True)
        self.preview_check.toggled.connect(self._update_preview)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(520, 250)

        channel_row = QHBoxLayout()
        channel_row.addWidget(QLabel("Channel:"))
        channel_row.addWidget(self.channel)
        channel_row.addStretch(1)
        channel_row.addWidget(self.preview_check)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.addWidget(QLabel("Input:"), 0, 0)
        grid.addWidget(QLabel("Black"), 0, 1)
        grid.addWidget(self.in_black, 0, 2)
        grid.addWidget(QLabel("Gamma"), 0, 3)
        grid.addWidget(self.gamma, 0, 4)
        grid.addWidget(QLabel("White"), 0, 5)
        grid.addWidget(self.in_white, 0, 6)
        grid.addWidget(QLabel("Output:"), 1, 0)
        grid.addWidget(QLabel("Black"), 1, 1)
        grid.addWidget(self.out_black, 1, 2)
        grid.addWidget(QLabel("White"), 1, 3)
        grid.addWidget(self.out_white, 1, 4)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        reset_button = buttons.addButton("Reset", QDialogButtonBox.ResetRole)
        reset_button.clicked.connect(self.reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addLayout(channel_row)
        layout.addWidget(self.view)
        layout.addLayout(grid)
        layout.addWidget(buttons)

        self._load_channel(None)

    @staticmethod
    def _int_spin() -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 255)
        return spin

    def _load_channel(self, key: int | None) -> None:
        self._channel = key
        state = self._state[key]
        self._updating = True
        self.in_black.setValue(state["in_black"])
        self.in_white.setValue(state["in_white"])
        self.gamma.setValue(state["gamma"])
        self.out_black.setValue(state["out_black"])
        self.out_white.setValue(state["out_white"])
        self._updating = False
        self.view.set_channel(key)
        self._sync_view_from_spins()
        self._update_preview()

    def _store_current(self) -> None:
        self._state[self._channel] = {
            "in_black": self.in_black.value(),
            "in_white": self.in_white.value(),
            "gamma": self.gamma.value(),
            "out_black": self.out_black.value(),
            "out_white": self.out_white.value(),
        }

    def _sync_view_from_spins(self) -> None:
        self.view.set_values(
            self.in_black.value(), self.in_white.value(), self.gamma.value(),
            self.out_black.value(), self.out_white.value(),
        )

    def _channel_changed(self, index: int) -> None:
        key = self.channel.itemData(index)
        if key == self._channel:
            return
        self._store_current()
        self._load_channel(key)

    def _spin_changed(self, _=None) -> None:
        if self._updating:
            return
        self._updating = True
        if self.in_white.value() <= self.in_black.value():
            if self.sender() is self.in_black:
                self.in_black.setValue(max(0, self.in_white.value() - 1))
            else:
                self.in_white.setValue(min(255, self.in_black.value() + 1))
        if self.out_white.value() <= self.out_black.value():
            if self.sender() is self.out_black:
                self.out_black.setValue(max(0, self.out_white.value() - 1))
            else:
                self.out_white.setValue(min(255, self.out_black.value() + 1))
        self._updating = False
        self._sync_view_from_spins()
        self._store_current()
        self._update_preview()

    def _view_changed(self) -> None:
        self._updating = True
        in_black, in_white, gamma, out_black, out_white = self.view.values()
        self.in_black.setValue(in_black)
        self.in_white.setValue(in_white)
        self.gamma.setValue(gamma)
        self.out_black.setValue(out_black)
        self.out_white.setValue(out_white)
        self._updating = False
        self._store_current()
        self._update_preview()

    def op(self) -> Levels:
        state = self._state[self._channel]
        return Levels(
            state["in_black"], state["in_white"], state["gamma"],
            state["out_black"], state["out_white"], self._channel,
        )

    def reset(self) -> None:
        self._state[self._channel] = dict(DEFAULTS)
        self._load_channel(self._channel)

    def _update_preview(self, *_) -> None:
        if not self.preview_check.isChecked():
            self.preview.setText("Preview off")
            return
        state = self._state[self._channel]
        lut = levels_lut(
            state["in_black"], state["in_white"], state["gamma"],
            state["out_black"], state["out_white"], self._channel,
        )
        result = apply_lut(self._image, lut)
        pixmap = QPixmap.fromImage(result)
        self.preview.setPixmap(
            pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
