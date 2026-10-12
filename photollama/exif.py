from __future__ import annotations

import struct

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

ORIENTATION = {
    1: "Normal",
    2: "Mirrored horizontal",
    3: "Rotated 180°",
    4: "Mirrored vertical",
    5: "Mirrored horizontal + rotated 270°",
    6: "Rotated 90° CW",
    7: "Mirrored horizontal + rotated 90°",
    8: "Rotated 270° CW",
}

TAGS = {
    0x010F: ("Make", "ascii"),
    0x0110: ("Model", "ascii"),
    0x0112: ("Orientation", "orientation"),
    0x0132: ("DateTime", "ascii"),
    0x829A: ("ExposureTime", "rational"),
    0x829D: ("FNumber", "rational"),
    0x8827: ("ISO", "short"),
    0x9003: ("DateTimeOriginal", "ascii"),
    0x920A: ("FocalLength", "rational"),
    0xA002: ("PixelXDimension", "long"),
    0xA003: ("PixelYDimension", "long"),
    0x011A: ("XResolution", "rational"),
    0x011B: ("YResolution", "rational"),
}

EXIF_POINTER = 0x8769
ORDER = [
    "Make", "Model", "DateTimeOriginal", "DateTime", "ExposureTime",
    "FNumber", "ISO", "FocalLength", "Orientation",
]


def read_exif(path: str) -> dict[str, str]:
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return {}
    if data[:2] == b"\xff\xd8":
        block = _jpeg_exif(data)
    elif data[:4] in (b"II\x2a\x00", b"MM\x00\x2a"):
        block = data
    else:
        return {}
    if not block:
        return {}
    found = _parse_tiff(block)
    return {name: found[name] for name in ORDER if name in found}


def _jpeg_exif(data: bytes) -> bytes | None:
    offset = 2
    end = len(data)
    while offset + 4 <= end:
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        if marker == 0xDA or marker == 0xD9:
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            offset += 2
            continue
        length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        if marker == 0xE1 and data[offset + 4:offset + 10] == b"Exif\x00\x00":
            return data[offset + 10:offset + 2 + length]
        offset += 2 + length
    return None


def _parse_tiff(block: bytes) -> dict[str, str]:
    if len(block) < 8:
        return {}
    if block[:2] == b"II":
        endian = "<"
    elif block[:2] == b"MM":
        endian = ">"
    else:
        return {}
    if struct.unpack(endian + "H", block[2:4])[0] != 42:
        return {}
    ifd_offset = struct.unpack(endian + "I", block[4:8])[0]
    result: dict[str, str] = {}
    entries = _read_ifd(block, ifd_offset, endian, result)
    pointer = entries.get(EXIF_POINTER)
    if isinstance(pointer, int) and pointer > 0:
        _read_ifd(block, pointer, endian, result)
    return result


def _read_ifd(block: bytes, offset: int, endian: str, out: dict) -> dict:
    if offset + 2 > len(block) or offset < 0:
        return {}
    count = struct.unpack_from(endian + "H", block, offset)[0]
    entries: dict[int, object] = {}
    pos = offset + 2
    for _ in range(count):
        if pos + 12 > len(block):
            break
        tag, tag_type, tag_count = struct.unpack_from(endian + "HHI", block, pos)
        value = _decode(block, endian, tag_type, tag_count, block[pos + 8:pos + 12])
        entries[tag] = value
        spec = TAGS.get(tag)
        if spec:
            formatted = _format(spec[0], spec[1], value)
            if formatted is not None:
                out[spec[0]] = formatted
        pos += 12
    return entries


def _decode(block: bytes, endian: str, tag_type: int, count: int, inline: bytes):
    size = TYPE_SIZE.get(tag_type, 1) * count
    if size > 4:
        start = struct.unpack(endian + "I", inline)[0]
        raw = block[start:start + size]
    else:
        raw = inline[:size]
    if tag_type == 2:
        return raw.split(b"\x00", 1)[0].decode("utf-8", "ignore")
    if tag_type == 3:
        values = struct.unpack(endian + "H" * count, raw[: 2 * count])
        return values[0] if count == 1 else values
    if tag_type == 4:
        values = struct.unpack(endian + "I" * count, raw[: 4 * count])
        return values[0] if count == 1 else values
    if tag_type in (5, 10):
        fmt = "II" if tag_type == 5 else "ii"
        rationals = []
        for i in range(count):
            numerator, denominator = struct.unpack_from(endian + fmt, raw, i * 8)
            rationals.append((numerator, denominator))
        return rationals[0] if count == 1 else rationals
    return raw


def _format(name: str, kind: str, value):
    if kind == "orientation":
        return ORIENTATION.get(value, str(value))
    if kind == "ascii":
        text = value.strip() if isinstance(value, str) else ""
        return text or None
    if kind in ("short", "long"):
        return str(value)
    if kind == "rational":
        if isinstance(value, tuple) and len(value) == 2:
            numerator, denominator = value
            if denominator == 0:
                return None
            ratio = numerator / denominator
            if name == "ExposureTime":
                return f"{ratio:g}s" if ratio >= 1 else f"1/{round(1 / ratio)}s"
            if name == "FNumber":
                return f"f/{ratio:.1f}"
            if name == "FocalLength":
                return f"{ratio:.0f} mm"
            return f"{ratio:g}"
        return None
    return None
