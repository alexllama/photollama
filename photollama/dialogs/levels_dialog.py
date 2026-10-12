from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..imaging import apply_lut, build_levels_lut, histogram
from ..ops import Levels


class HistogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hist = None
        self.setMinimumHeight(130)

    def set_histogram(self, hist) -> None:
        self._hist = hist
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101010"))
        if not self._hist:
            return
        width = self.width()
        height = self.height()
        peak = max(1, max(int(channel.max()) for channel in self._hist))
        colors = (QColor(235, 90, 90), QColor(100, 215, 100), QColor(95, 145, 245))
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for values, base in zip(self._hist, colors):
            path = QPainterPath()
            path.moveTo(0, height)
            for i in range(256):
                level = float(values[i]) / peak
                path.lineTo(width * i / 255.0, height - level * height)
            path.lineTo(width, height)
            color = QColor(base)
            color.setAlpha(150)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(color)
            painter.drawPath(path)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)


class LevelsDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Levels")
        self.setMinimumWidth(520)
        self._image = image

        self.histogram = HistogramWidget()
        self.histogram.set_histogram(histogram(image))

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(460, 300)

        self.in_black = self._slider(0, 255, 0)
        self.in_white = self._slider(0, 255, 255)
        self.gamma = self._slider(5, 500, 100)
        self.out_black = self._slider(0, 255, 0)
        self.out_white = self._slider(0, 255, 255)

        rows = [
            ("Input black", self.in_black),
            ("Input white", self.in_white),
            ("Gamma", self.gamma),
            ("Output black", self.out_black),
            ("Output white", self.out_white),
        ]
        controls = QVBoxLayout()
        for label, slider in rows:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setMinimumWidth(110)
            value = QLabel()
            value.setMinimumWidth(40)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._bind_value(slider, value)
            row.addWidget(name)
            row.addWidget(slider, 1)
            row.addWidget(value)
            controls.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        reset_button = buttons.addButton("Reset", QDialogButtonBox.ResetRole)
        reset_button.clicked.connect(self.reset)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.histogram)
        layout.addLayout(controls)
        layout.addWidget(buttons)

        for slider in (self.in_black, self.in_white, self.gamma, self.out_black, self.out_white):
            slider.valueChanged.connect(self._update_preview)
        self._update_preview()

    @staticmethod
    def _slider(low: int, high: int, value: int) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        return slider

    @staticmethod
    def _bind_value(slider: QSlider, label: QLabel) -> None:
        def update(value):
            if slider is None:
                return
            if slider.maximum() == 500:
                label.setText(f"{value / 100:.2f}")
            else:
                label.setText(str(value))
        slider.valueChanged.connect(update)
        update(slider.value())

    def _params(self):
        in_black = self.in_black.value()
        in_white = self.in_white.value()
        if in_white <= in_black:
            in_white = min(255, in_black + 1)
        return (
            in_black, in_white, self.gamma.value() / 100.0,
            self.out_black.value(), self.out_white.value(),
        )

    def op(self) -> Levels:
        return Levels(*self._params())

    def reset(self) -> None:
        for slider, value in (
            (self.in_black, 0), (self.in_white, 255), (self.gamma, 100),
            (self.out_black, 0), (self.out_white, 255),
        ):
            slider.setValue(value)

    def _update_preview(self) -> None:
        lut = build_levels_lut(*self._params())
        result = apply_lut(self._image, lut)
        pixmap = QPixmap.fromImage(result)
        self.preview.setPixmap(
            pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
