"""生成应用图标 packaging/worklog.ico（蓝色圆角方块 + 「记」）。

运行：.venv\\Scripts\\python.exe packaging\\make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_PATH = Path(__file__).resolve().parent / "worklog.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
BG = (47, 107, 255, 255)
FG = (255, 255, 255, 255)
TEXT = "记"


def _load_font(size: int):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        "msyhbd.ttc",
        "msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render(size: int) -> Image.Image:
    scale = 4  # 先大后缩，边缘更平滑
    canvas = size * scale
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = max(1, round(canvas * 0.035))
    radius = round(canvas * 0.22)
    draw.rounded_rectangle(
        [margin, margin, canvas - margin, canvas - margin],
        radius=radius,
        fill=BG,
    )

    font = _load_font(round(canvas * 0.54))
    bbox = draw.textbbox((0, 0), TEXT, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text(
        ((canvas - width) / 2 - bbox[0], (canvas - height) / 2 - bbox[1]),
        TEXT,
        font=font,
        fill=FG,
    )
    return img.resize((size, size), Image.LANCZOS)


def main() -> int:
    images = [_render(size) for size in SIZES]
    images[-1].save(
        OUT_PATH,
        format="ICO",
        sizes=[(size, size) for size in SIZES],
        append_images=images[:-1],
    )
    print(f"图标已生成：{OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
