from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from .ops import Flip, Rotate90

JPEG_EXTS = {".jpg", ".jpeg", ".jpe", ".jfif"}


def is_lossless_for(path: str, ops) -> bool:
    if os.path.splitext(path)[1].lower() not in JPEG_EXTS:
        return False
    if not ops:
        return False
    return all(isinstance(op, (Rotate90, Flip)) for op in ops)


def _op_args(op) -> list[str] | None:
    if isinstance(op, Rotate90):
        return ["-rotate", "90" if op.clockwise else "270"]
    if isinstance(op, Flip):
        return ["-flip", "horizontal" if op.horizontal else "vertical"]
    return None


def lossless_transform(path: str, ops, out_path: str) -> bool:
    exe = shutil.which("jpegtran")
    if not exe:
        return False
    arg_sets = [_op_args(op) for op in ops]
    if any(arg_set is None for arg_set in arg_sets):
        return False
    tmpdir = tempfile.mkdtemp(prefix="photollama-")
    try:
        current = os.path.abspath(path)
        for index, op_args in enumerate(arg_sets):
            destination = os.path.join(tmpdir, f"step{index}.jpg")
            result = subprocess.run(
                [exe, *op_args, "-copy", "all", "-outfile", destination, current],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            if result.returncode != 0 or not os.path.exists(destination):
                return False
            current = destination
        shutil.copyfile(current, out_path)
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
