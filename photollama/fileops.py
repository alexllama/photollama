from __future__ import annotations

import mimetypes
import os
import subprocess

from PySide6.QtGui import QImage

EXT_FORMAT = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".jpe": "JPEG", ".jfif": "JPEG",
    ".png": "PNG", ".webp": "WEBP", ".tif": "TIFF", ".tiff": "TIFF",
    ".bmp": "BMP", ".gif": "GIF", ".ico": "ICO", ".jp2": "JP2",
    ".ppm": "PPM", ".pgm": "PGM", ".pbm": "PBM", ".xbm": "XBM", ".xpm": "XPM",
}


def save_image(image: QImage, path: str, quality: int = 95) -> bool:
    fmt = EXT_FORMAT.get(os.path.splitext(path)[1].lower(), "PNG")
    if fmt == "JPEG":
        return image.save(path, fmt, quality)
    return image.save(path, fmt)


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{num_bytes} B"


def mime_for(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def trash(path: str) -> bool:
    try:
        subprocess.run(
            ["gio", "trash", "--", path], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def open_default(path: str) -> bool:
    return _spawn(["xdg-open", path])


def open_with(path: str, desktop_id: str) -> bool:
    return _spawn(["gio", "launch", desktop_id, path])


def _spawn(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def rename(path: str, new_name: str) -> str | None:
    new_name = new_name.strip()
    if not new_name or os.sep in new_name:
        return None
    target = os.path.join(os.path.dirname(path), new_name)
    if os.path.abspath(target) != os.path.abspath(path) and os.path.exists(target):
        return None
    try:
        os.rename(path, target)
    except OSError:
        return None
    return target


def applications_for(path: str) -> list[tuple[str, str]]:
    mime = mime_for(path)
    try:
        result = subprocess.run(
            ["gio", "mime", mime], capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    apps: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.endswith(".desktop") and ":" not in line and line not in seen:
            seen.add(line)
            apps.append((_app_label(line), line))
    return apps


def _app_label(desktop_id: str) -> str:
    for base in (
        os.path.expanduser("~/.local/share/applications"),
        "/usr/local/share/applications",
        "/usr/share/applications",
    ):
        candidate = os.path.join(base, desktop_id)
        if os.path.exists(candidate):
            try:
                with open(candidate, encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        if line.startswith("Name=") and "[" not in line.split("=", 1)[0]:
                            return line.strip().split("=", 1)[1]
            except OSError:
                pass
    return desktop_id[:-8] if desktop_id.endswith(".desktop") else desktop_id
