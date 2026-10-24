from __future__ import annotations

import json
from urllib.parse import quote

from PySide6.QtCore import QByteArray, QUrl
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QHttpMultiPart, QHttpPart, QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .base import AIProviderError, AIResult, image_to_png_bytes


class PollinationsClient:
    def __init__(self, manager: QNetworkAccessManager):
        self.manager = manager
        self._reply: QNetworkReply | None = None

    def enhance(self, image: QImage, prompt: str, api_key: str = "", model: str = "flux") -> None:
        if image.isNull():
            raise AIProviderError("No image to enhance")
        if not prompt:
            raise AIProviderError("Please enter a prompt")

        png_bytes = image_to_png_bytes(image)
        url = QUrl("https://image.pollinations.ai/")
        request = QNetworkRequest(url)
        request.setRawHeader(b"User-Agent", b"Photollama")

        multi = QHttpMultiPart(QHttpMultiPart.FormDataType)

        # prompt
        prompt_part = QHttpPart()
        prompt_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="prompt"')
        prompt_part.setBody(prompt.encode("utf-8"))
        multi.append(prompt_part)

        # model
        if not model:
            model = "flux"
        model_part = QHttpPart()
        model_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="model"')
        model_part.setBody(model.encode("utf-8"))
        multi.append(model_part)

        # image
        img_part = QHttpPart()
        img_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name="image"; filename="image.png"')
        img_part.setHeader(QNetworkRequest.ContentTypeHeader, "image/png")
        img_part.setBody(png_bytes)
        multi.append(img_part)

        self._reply = self.manager.post(request, multi)
        multi.setParent(self._reply)

    def cancel(self) -> None:
        if self._reply and self._reply.isRunning():
            self._reply.abort()


def parse_response(reply: QNetworkReply) -> AIResult:
    if reply.error() != QNetworkReply.NoError:
        err = reply.errorString()
        data = bytes(reply.readAll())
        try:
            # try json
            msg = json.loads(data.decode("utf-8", "ignore"))
            if isinstance(msg, dict):
                err = msg.get("error") or msg.get("message") or err
        except Exception:
            if data:
                err = data[:200].decode("utf-8", "ignore")
        raise AIProviderError(err or "Pollinations request failed")

    data = bytes(reply.readAll())
    if not data:
        raise AIProviderError("Empty response from Pollinations")
    image = QImage.fromData(data)
    if image.isNull():
        # maybe html error
        raise AIProviderError("Pollinations returned invalid image data")
    return AIResult(image=image, raw_bytes=data, mime_type="image/png")
