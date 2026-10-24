from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .base import AIProviderError, AIResult, image_to_png_data_uri


class OpenRouterClient:
    def __init__(self, manager: QNetworkAccessManager):
        self.manager = manager
        self._reply: QNetworkReply | None = None

    def enhance(self, image: QImage, prompt: str, api_key: str, model: str) -> None:
        if not api_key:
            raise AIProviderError("OpenRouter API key not set")
        if image.isNull():
            raise AIProviderError("No image to enhance")

        data_uri = image_to_png_data_uri(image)
        url = QUrl("https://openrouter.ai/api/v1/chat/completions")
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        request.setRawHeader(b"Authorization", f"Bearer {api_key}".encode("utf-8"))
        request.setRawHeader(b"HTTP-Referer", b"http://localhost")
        request.setRawHeader(b"X-Title", b"Photollama")

        body = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "modalities": ["image", "text"],
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
        raise AIProviderError(f"Invalid JSON from OpenRouter: {exc}")

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIProviderError(f"Unexpected OpenRouter response: {data[:200]}")

    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "image_url" and part.get("image_url"):
                    url = part["image_url"].get("url", "")
                    if url.startswith("data:"):
                        return _from_data_uri(url)
                if part.get("type") == "image" and part.get("image_url"):
                    url = part["image_url"].get("url", "")
                    if url.startswith("data:"):
                        return _from_data_uri(url)
                if part.get("image"):
                    img = part["image"]
                    if isinstance(img, dict) and img.get("url", "").startswith("data:"):
                        return _from_data_uri(img["url"])
        raise AIProviderError("OpenRouter response did not contain an image")
    if isinstance(content, str):
        # Some models return markdown with data URI
        if "data:image" in content:
            start = content.find("data:image")
            end = content.find(")", start)
            if end == -1:
                end = content.find('"', start)
            if end == -1:
                end = len(content)
            return _from_data_uri(content[start:end])
        raise AIProviderError("OpenRouter response did not contain an image")

    raise AIProviderError("Unexpected OpenRouter response format")


def _from_data_uri(uri: str) -> AIResult:
    try:
        header, b64 = uri.split(",", 1)
        mime = header.split(";")[0].replace("data:", "") or "image/png"
        raw = __import__("base64").b64decode(b64)
    except Exception as exc:
        raise AIProviderError(f"Failed to decode image from response: {exc}")
    image = QImage.fromData(raw)
    if image.isNull():
        raise AIProviderError("Failed to decode image from response")
    return AIResult(image=image, raw_bytes=raw, mime_type=mime)
