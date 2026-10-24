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
    ("Gentle Enhance (Recommended)", "Enhance the colors and remove noise. Make no other changes to the content, composition, text, or people. Preserve fine details and natural lighting."),
    ("Photo Cleanup", "Subtly clean up this photo. Reduce sensor noise, correct mild color cast, improve micro-contrast. Keep it photorealistic. Do not add, remove, or redraw objects."),
    ("Upscale & Refine", "Upscale and refine this image with minimal hallucinations. Restore natural textures and sharpen only where needed. Do not change facial features, text, or layout."),
    ("Old Photo Restoration", "Gently restore an old photograph. Reduce dust and grain, fix faded colors while keeping period-accurate tones. Do not modernize clothing, faces, or backgrounds."),
    ("Sharpen Details", "Apply very light detail enhancement for improved clarity. Avoid oversharpening, halos, or AI smoothing. Keep the original look as much as possible."),
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
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-preview-image-generation",
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
        self.provider.addItem("Google Gemini (direct)", "gemini")
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

        hint = QLabel("Gemini key: Google AI Studio → Get API key (https://aistudio.google.com/apikey)")
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
        config.provider = self.provider.currentData() or "openrouter"
        config.openrouter_model = self.model.currentText().strip()
        if self.provider.currentData() == "gemini":
            config.gemini_model = self.model.currentText().strip()

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
