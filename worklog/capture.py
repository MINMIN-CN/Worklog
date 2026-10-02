"""屏幕截取、图像压缩与去重指纹。"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from datetime import datetime

from PIL import Image


def average_hash(img: Image.Image, size: int = 8) -> int:
    """均值哈希（aHash），用于判断两帧画面是否基本相同。"""
    gray = img.convert("L").resize((size, size), Image.LANCZOS)
    pixels = list(gray.getdata())
    avg = sum(pixels) / max(1, len(pixels))
    bits = 0
    for index, value in enumerate(pixels):
        if value >= avg:
            bits |= 1 << index
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def encode_jpeg(img: Image.Image, max_width: int, quality: int) -> bytes:
    if img.width > max_width > 0:
        ratio = max_width / img.width
        img = img.resize(
            (max_width, max(1, int(img.height * ratio))), Image.LANCZOS
        )
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def to_data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


def grab_screen(sct, monitor_index: int = 1) -> tuple[Image.Image, int]:
    """抓取指定显示器，返回 (PIL 图像, 实际使用的显示器序号)。"""
    monitors = sct.monitors
    index = int(monitor_index)
    if index < 1 or index >= len(monitors):
        index = 1 if len(monitors) > 1 else 0
    shot = sct.grab(monitors[index])
    img = Image.frombytes("RGB", shot.size, shot.rgb)
    return img, index


@dataclass
class Capture:
    ts: datetime
    app: str
    title: str
    jpeg: bytes
    ahash: int
    monitor: int
