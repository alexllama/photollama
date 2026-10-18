from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from ..ops import RotateAngle


def _normalize_degrees(value: float) -> int:
    return int(round((value + 180.0) % 360.0 - 180.0))


class RotateDialog(QDialog):
    changed = Signal()

    def __init__(self, parent=None, degrees: float = 0.0, autocrop: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Rotate")
        self.setMinimumWidth(420)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(-180, 180)
        self.slider.setValue(int(round(degrees)))
        self.spin = QSpinBox()
        self.spin.setRange(-180, 180)
        self.spin.setSuffix("°")
        self.spin.setValue(int(round(degrees)))
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.spin.valueChanged.connect(self._emit_changed)

        self.autocrop = QCheckBox("Auto-crop to fit")
        self.autocrop.setChecked(autocrop)
        self.autocrop.toggled.connect(self._emit_changed)

        hint = QLabel("The image in the main window rotates as you adjust the angle.")
        hint.setWordWrap(True)

        angle_row = QHBoxLayout()
        angle_row.addWidget(self.slider, 1)
        angle_row.addWidget(self.spin)

        form = QFormLayout()
        form.addRow("Angle:", angle_row)
        form.addRow("", self.autocrop)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def _emit_changed(self, *_) -> None:
        self.changed.emit()

    def degrees(self) -> float:
        return float(self.spin.value())

    def set_degrees(self, value: float) -> None:
        self.spin.setValue(_normalize_degrees(value))

    def op(self) -> RotateAngle:
        return RotateAngle(self.spin.value(), self.autocrop.isChecked())
