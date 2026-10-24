from __future__ import annotations

import json
import base64

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .base import AIProviderError, AIResult


class GeminiClient:
    def __init__(self, manager: QNetworkAccessManager):
        self.manager = manager
        self._reply: QNetworkReply | None = None

    def enhance(self, image: QImage, prompt: str, api_key: str, model: str) -> None:
        if not api_key:
            raise AIProviderError("Gemini API key not set")
        if image.isNull():
            raise AIProviderError("No image to enhance")

        data = QByteArray()
        from PySide6.QtCore import QBuffer, QIODevice
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        ok = image.save(buffer, "PNG")
        buffer.close()
        if not ok:
            raise AIProviderError("Failed to encode image as PNG")
        b64 = base64.b64encode(bytes(data)).decode("ascii")

        url = QUrl(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}")
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "image/png", "data": b64}},
                    ]
                }
            ],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        payload = json.dumps(body).encode("utf-8")
        self._reply = self.manager.post(request, QByteArray(payload))

    def cancel(self) -> None:
        if self._reply and self._reply.isRunning():
            self._reply.abort()


def parse_response(reply: QNetworkReply) -> AIResult:
    if reply.error() != QNetworkReply.NoError:
        err = reply.errorString()
        data = bytes(reply.readAll())
        try:
            msg = json.loads(data.decode("utf-8"))
            if isinstance(msg, dict):
                err = msg.get("error", {}).get("message") if isinstance(msg.get("error"), dict) else msg.get("error") or err
        except Exception:
            pass
        raise AIProviderError(err)

    data = bytes(reply.readAll())
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise AIProviderError(f"Invalid JSON from Gemini: {exc}")

    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise AIProviderError(f"Unexpected Gemini response: {data[:200]}")

    for part in parts:
        if isinstance(part, dict) and part.get("inlineData"):
            inline = part["inlineData"]
            raw = base64.b64decode(inline.get("data", ""))
            mime = inline.get("mimeType", "image/png")
            image = QImage.fromData(raw)
            if image.isNull():
                raise AIProviderError("Failed to decode image from Gemini response")
            return AIResult(image=image, raw_bytes=raw, mime_type=mime)
    raise AIProviderError("Gemini response did not contain an image")
