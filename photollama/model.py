from __future__ import annotations

from PySide6.QtGui import QImage


class Document:
    def __init__(self, path: str, image: QImage):
        self.path = path
        self.original = image
        self._ops: list = []
        self._redo: list = []
        self._cache: QImage | None = None

    @property
    def is_modified(self) -> bool:
        return bool(self._ops)

    @property
    def ops(self) -> tuple:
        return tuple(self._ops)

    @property
    def can_undo(self) -> bool:
        return bool(self._ops)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def apply(self, op) -> None:
        self._ops.append(op)
        self._redo.clear()
        self._invalidate()

    def undo(self) -> None:
        if self._ops:
            self._redo.append(self._ops.pop())
            self._invalidate()

    def redo(self) -> None:
        if self._redo:
            self._ops.append(self._redo.pop())
            self._invalidate()

    def render(self) -> QImage:
        if self._cache is None:
            image = self.original
            for op in self._ops:
                image = op.apply(image)
            self._cache = image
        return self._cache

    def commit(self) -> None:
        if not self._ops:
            return
        self.original = self.render()
        self._ops.clear()
        self._redo.clear()
        self._cache = None

    def _invalidate(self) -> None:
        self._cache = None
