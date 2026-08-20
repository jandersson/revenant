"""Generate the Windows icon (revenant.ico) from revenant.svg.

Renders the SVG at each taskbar/Start-Menu size with Qt and packs the
PNGs into one .ico (PNG-in-ICO, valid since Vista) — no dependencies
beyond PyQt6, which the client already ships. Rerun after editing the
SVG:  uv run python tools/make_icon.py
"""

import struct
import sys
from pathlib import Path

from PyQt6.QtCore import QBuffer
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

GUI_DIR = Path(__file__).parents[1] / "client" / "client" / "gui"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def pack_ico(pngs: dict[int, bytes]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(pngs))
    entries, blobs = b"", b""
    offset = len(header) + 16 * len(pngs)
    for size, png in sorted(pngs.items()):
        entries += struct.pack(
            "<BBBBHHII",
            size % 256,  # 0 means 256
            size % 256,
            0,
            0,
            1,
            32,
            len(png),
            offset,
        )
        blobs += png
        offset += len(png)
    return header + entries + blobs


def main():
    QGuiApplication(sys.argv[:1])
    renderer = QSvgRenderer(str(GUI_DIR / "revenant.svg"))
    target = GUI_DIR / "revenant.ico"
    target.write_bytes(pack_ico({size: render_png(renderer, size) for size in SIZES}))
    print(f"wrote {target} ({target.stat().st_size} bytes, sizes {SIZES})")


if __name__ == "__main__":
    main()
