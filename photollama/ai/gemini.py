from __future__ import annotations

import base64
import json

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .base import AIProviderError, AIResult, image_to_png_bytes

# Google retired Imagen 3 in November 2025 and all Imagen models in 2026.
# The current Google image models are the Nano Banana family and are reached
# through the Interactions API.
DEFAULT_MODEL = "gemini-nano-banana-2.1"


class GeminiClient:
    def __init__(self, manager: QNetworkAccessManager):
        self.manager = manager
        self._reply: QNetworkReply | None = None

    def enhance(self, image: QImage, prompt: str, api_key: str, model: str) -> None:
        if not api_key:
            raise AIProviderError("Google API key not set")
        if image.isNull():
            raise AIProviderError("No image to enhance")
        if not prompt:
            raise AIProviderError("Please enter a prompt")

        b64 = base64.b64encode(image_to_png_bytes(image)).decode("ascii")

        url = QUrl("https://generativelanguage.googleapis.com/v1beta/interactions")
        request = QNetworkRequest(url)
        request.setRawHeader(b"x-goog-api-key", api_key.encode("utf-8"))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        body = {
            "model": model or DEFAULT_MODEL,
            "input": [
                {"type": "text", "text": prompt},
                {"type": "image", "mime_type": "image/png", "data": b64},
            ],
            "response_format": {"type": "image", "mime_type": "image/jpeg"},
            # Keep the user's photo out of Google's stored interaction history.
            "store": False,
        }
        payload = json.dumps(body).encode("utf-8")
        self._reply = self.manager.post(request, QByteArray(payload))

    def cancel(self) -> None:
        if self._reply and self._reply.isRunning():
            self._reply.abort()


def _decode_image(block: dict) -> AIResult:
    raw = base64.b64decode(block.get("data", ""))
    image = QImage.fromData(raw)
    if image.isNull():
        raise AIProviderError("Failed to decode image from Google response")
    return AIResult(
        image=image,
        raw_bytes=raw,
        mime_type=block.get("mime_type", "image/png"),
    )


def parse_response(reply: QNetworkReply) -> AIResult:
    if reply.error() != QNetworkReply.NoError:
        err = reply.errorString()
        data = bytes(reply.readAll())
        try:
            payload = json.loads(data.decode("utf-8", "ignore"))
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    err = error.get("message") or err
                elif isinstance(error, str):
                    err = error or err
        except Exception:
            pass
        raise AIProviderError(err or "Google request failed")

    data = bytes(reply.readAll())
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise AIProviderError(f"Invalid JSON from Google: {exc}")

    for step in payload.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for block in step.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "image" and block.get("data"):
                return _decode_image(block)

    output_image = payload.get("output_image")
    if isinstance(output_image, dict) and output_image.get("data"):
        return _decode_image(output_image)

    raise AIProviderError(f"Google response did not contain an image: {data[:200]}")
