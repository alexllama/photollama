from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..ai.config import config

PRESETS = [
    (
        "Gentle Enhance (Recommended)",
        "Perform light color balancing and noise reduction on this image while strictly retaining 100% of the original content, composition, and details. Preserve exact facial features, existing text, line art, and natural lighting. Do not invent new elements, sharpen excessively, or apply AI-smoothing effects."
    ),
    (
        "Photo Cleanup",
        "Subtly clean up noise and compression artifacts from this photo. Correct mild color casts and improve micro-contrast while maintaining strict photorealism. Maintain original facial proportions, body features, background details, and text. Absolutely zero redrawing, addition, or deletion of subjects or scene elements."
    ),
    (
        "Upscale & Refine",
        "Upscale and refine image details with zero hallucinations or alterations to the core content. Restore natural skin textures, hair, fabrics, and fine edges. Strictly preserve the original layout, text glyphs, geometry, and facial identity without warping or smoothing."
    ),
    (
        "Old Photo Restoration",
        "Restoration of an archival photograph. Carefully remove dust spots, scratches, and film grain while repairing faded color saturation and tone. Keep period-accurate photographic characteristics, grain texture, and historical color profiles. Do not modernize faces, clothing, hair, or backgrounds, and avoid plastic skin effects."
    ),
    (
        "Sharpen Details",
        "Apply targeted micro-contrast and light detail sharpening for subtle edge clarity. Avoid halo artifacts, over-sharpening, ringing, or digital smoothing. Retain exact color values, grain structure, lighting, composition, and subject details as in the input image."
    ),
    ("Custom", ""),
]


POLLINATIONS_MODELS = [
    "flux",
    "turbo",
    "gptimage",
]

OPENROUTER_MODELS = [
    "google/gemini-2.5-flash-image",
    "black-forest-labs/flux-kontext-dev",
    "black-forest-labs/flux-kontext-pro",
]

GEMINI_MODELS = [
    "gemini-nano-banana-2.1",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
]


class AIEnhanceDialog(QDialog):
    def __init__(self, parent=None, preview_pixmap: QPixmap | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI Enhance")
        self.resize(520, 520)
        self._preview = preview_pixmap

        layout = QVBoxLayout(self)

        if preview_pixmap and not preview_pixmap.isNull():
            prev = QLabel()
            prev.setAlignment(Qt.AlignCenter)
            prev.setPixmap(preview_pixmap.scaled(500, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            layout.addWidget(prev)

        provider_group = QGroupBox("Provider")
        pf = QFormLayout(provider_group)
        self.provider = QComboBox()
        self.provider.addItem("Pollinations (Free, no key)", "pollinations")
        self.provider.addItem("OpenRouter", "openrouter")
        self.provider.addItem("Google Gemini / Nano Banana", "gemini")
        idx = self.provider.findData(config.provider)
        if idx >= 0:
            self.provider.setCurrentIndex(idx)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        pf.addRow("Provider:", self.provider)

        self.model = QComboBox()
        self.model.setEditable(True)
        pf.addRow("Model:", self.model)
        self._populate_models()
        self.model.setCurrentText(self._default_model())
        layout.addWidget(provider_group)

        keys_group = QGroupBox("API Keys (saved locally)")
        kf = QFormLayout(keys_group)
        self.openrouter_key = QLineEdit()
        self.openrouter_key.setEchoMode(QLineEdit.Password)
        self.openrouter_key.setPlaceholderText("sk-or-v1-...")
        self.openrouter_key.setText(config.openrouter_key)
        or_row = QHBoxLayout()
        or_row.addWidget(self.openrouter_key)
        self.toggle_or = QPushButton("Show")
        self.toggle_or.clicked.connect(lambda: self._toggle(self.openrouter_key, self.toggle_or))
        or_row.addWidget(self.toggle_or)
        or_widget = self._wrap(or_row)
        kf.addRow("OpenRouter:", or_widget)

        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.Password)
        self.gemini_key.setPlaceholderText("AIza...")
        self.gemini_key.setText(config.gemini_key)
        gr_row = QHBoxLayout()
        gr_row.addWidget(self.gemini_key)
        self.toggle_gr = QPushButton("Show")
        self.toggle_gr.clicked.connect(lambda: self._toggle(self.gemini_key, self.toggle_gr))
        gr_row.addWidget(self.toggle_gr)
        gr_widget = self._wrap(gr_row)
        kf.addRow("Gemini:", gr_widget)

        hint = QLabel(
            "Google key: https://aistudio.google.com/apikey "
        )
        hint.setWordWrap(True)
        kf.addRow("", hint)
        self.keys_group = keys_group
        layout.addWidget(keys_group)
        self._update_key_visibility()

        prompt_group = QGroupBox("Prompt")
        pvl = QVBoxLayout(prompt_group)
        self.preset = QComboBox()
        for label, text in PRESETS:
            self.preset.addItem(label, text)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        pvl.addWidget(self.preset)
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText("Describe how you want to enhance the image...")
        self.prompt.setPlainText(PRESETS[0][1])
        self.prompt.setMinimumHeight(90)
        pvl.addWidget(self.prompt)
        layout.addWidget(prompt_group)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Enhance")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _wrap(self, layout):
        w = __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget()
        w.setLayout(layout)
        return w

    def _toggle(self, edit: QLineEdit, btn: QPushButton):
        if edit.echoMode() == QLineEdit.Password:
            edit.setEchoMode(QLineEdit.Normal)
            btn.setText("Hide")
        else:
            edit.setEchoMode(QLineEdit.Password)
            btn.setText("Show")

    def _provider_changed(self):
        self._populate_models()
        self.model.setCurrentText(self._default_model())
        self._update_key_visibility()

    def _populate_models(self):
        self.model.clear()
        provider = self.provider.currentData()
        if provider == "openrouter":
            for m in OPENROUTER_MODELS:
                self.model.addItem(m)
        elif provider == "gemini":
            for m in GEMINI_MODELS:
                self.model.addItem(m)
        elif provider == "pollinations":
            for m in POLLINATIONS_MODELS:
                self.model.addItem(m)

    def _default_model(self):
        provider = self.provider.currentData()
        if provider == "openrouter":
            return config.openrouter_model
        if provider == "gemini":
            return config.gemini_model
        if provider == "pollinations":
            return "flux"
        return ""

    def _update_key_visibility(self):
        provider = self.provider.currentData()
        if provider == "pollinations":
            self.keys_group.setVisible(False)
        else:
            self.keys_group.setVisible(True)

    def _preset_changed(self):
        text = self.preset.currentData()
        if text is None:
            return
        if text == "":
            self.prompt.setFocus()
            return
        self.prompt.setPlainText(text)

    def save_config(self):
        config.openrouter_key = self.openrouter_key.text().strip()
        config.gemini_key = self.gemini_key.text().strip()
        provider = self.provider.currentData() or "openrouter"
        config.provider = provider
        model = self.model.currentText().strip()
        if provider == "openrouter":
            config.openrouter_model = model
        elif provider == "gemini":
            config.gemini_model = model

    def provider_id(self) -> str:
        return self.provider.currentData() or "openrouter"

    def model_id(self) -> str:
        return self.model.currentText().strip()

    def prompt_text(self) -> str:
        return self.prompt.toPlainText().strip()

    def key_for_provider(self) -> str:
        if self.provider_id() == "openrouter":
            return self.openrouter_key.text().strip()
        if self.provider_id() == "gemini":
            return self.gemini_key.text().strip()
        return ""
