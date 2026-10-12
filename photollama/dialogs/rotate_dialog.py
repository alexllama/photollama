from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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


class RotateDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rotate")
        self.setMinimumWidth(460)
        self._image = image

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(400, 280)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(-180, 180)
        self.spin = QSpinBox()
        self.spin.setRange(-180, 180)
        self.spin.setSuffix("°")
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self._update_preview)

        self.autocrop = QCheckBox("Auto-crop to fit")
        self.autocrop.setChecked(True)
        self.autocrop.toggled.connect(self._update_preview)

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
        layout.addWidget(self.preview, 1)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._update_preview()

    def op(self) -> RotateAngle:
        return RotateAngle(self.spin.value(), self.autocrop.isChecked())

    def _update_preview(self) -> None:
        result = self.op().apply(self._image)
        pixmap = QPixmap.fromImage(result)
        self.preview.setPixmap(
            pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
