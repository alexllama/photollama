from __future__ import annotations

import os

from PySide6.QtCore import QSettings

SETTINGS = QSettings("photollama", "photollama")
GROUP = "ai"


def _get(group: str, key: str, default: str = "") -> str:
    SETTINGS.beginGroup(group)
    value = SETTINGS.value(key, default)
    SETTINGS.endGroup()
    if value is None:
        return default
    return str(value)


def _set(group: str, key: str, value: str) -> None:
    SETTINGS.beginGroup(group)
    SETTINGS.setValue(key, value)
    SETTINGS.endGroup()


class AIConfig:
    @property
    def openrouter_key(self) -> str:
        return _get(GROUP, "openrouter_key") or os.environ.get("OPENROUTER_API_KEY", "")

    @openrouter_key.setter
    def openrouter_key(self, value: str) -> None:
        _set(GROUP, "openrouter_key", value or "")

    @property
    def gemini_key(self) -> str:
        return _get(GROUP, "gemini_key") or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

    @gemini_key.setter
    def gemini_key(self, value: str) -> None:
        _set(GROUP, "gemini_key", value or "")

    @property
    def provider(self) -> str:
        return _get(GROUP, "provider", "pollinations")

    @provider.setter
    def provider(self, value: str) -> None:
        _set(GROUP, "provider", value)

    @property
    def openrouter_model(self) -> str:
        return _get(GROUP, "openrouter_model", "google/gemini-2.5-flash-image")

    @openrouter_model.setter
    def openrouter_model(self, value: str) -> None:
        _set(GROUP, "openrouter_model", value)

    @property
    def gemini_model(self) -> str:
        value = _get(GROUP, "gemini_model", "gemini-nano-banana-2.1")
        if value in {
            "gemini-2.0-flash-preview-image-generation",
            "gemini-2.0-flash-exp-image-generation",
        }:
            return "gemini-nano-banana-2.1"
        return value

    @gemini_model.setter
    def gemini_model(self, value: str) -> None:
        _set(GROUP, "gemini_model", value)


config = AIConfig()
