from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ..fileops import human_size, mime_for


class PropertiesDialog(QDialog):
    def __init__(self, path: str, image, details: list[tuple[str, str]] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Properties")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        try:
            stat = os.stat(path)
            size_text = human_size(stat.st_size)
            modified_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        except OSError:
            size_text = "?"
            modified_text = "?"

        rows = [
            ("Name", os.path.basename(path)),
            ("Folder", os.path.dirname(path)),
            ("Type", mime_for(path)),
        ]
        if image is not None and not image.isNull():
            rows.append(("Dimensions", f"{image.width()} × {image.height()}"))
            rows.append(("Color space", image.colorSpace().description() or "sRGB"))
        rows.append(("File size", size_text))
        rows.append(("Modified", modified_text))
        if details:
            rows.extend(details)

        for label, value in rows:
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setWordWrap(True)
            form.addRow(f"{label}:", value_label)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
