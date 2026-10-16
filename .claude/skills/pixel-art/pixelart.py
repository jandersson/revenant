"""Pixel-art helpers for a DragonRealms scene: a small canvas drawn pixel by
pixel, saved scaled up nearest-neighbour, optionally with a JRPG dialogue box.

    from pixelart import Canvas
    c = Canvas(192, 120, "#140c1e")
    c.rect(0, 40, 192, 80, "#4a1e2c")          # floor
    c.poly([(8, 0), (16, 6), (8, 28), (0, 6)], lambda x, y: "#90e8f0")
    c.glow(96, 53, 13, 11, "#ffffff", 0.35)     # a lamp's light
    c.save("scene.png", scale=5, speaker="KIOSK", text="Partial acquisition\\nauthorized.")

Run a scene with `uv run --no-project --with pillow python scene.py`.
"""

import math

from PIL import Image, ImageDraw, ImageFont


def hexc(colour):
    if not isinstance(colour, str):
        return tuple(colour)
    h = colour.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


class Canvas:
    def __init__(self, width, height, background="#000000"):
        self.w, self.h = width, height
        self.px = [[hexc(background)] * width for _ in range(height)]

    def dot(self, x, y, colour):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = hexc(colour)

    def rect(self, x, y, w, h, colour):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.dot(xx, yy, colour)

    def line(self, x0, y0, x1, y1, colour):
        dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
        dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.dot(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, points, colour_at, edge=None):
        """Fill a polygon; `colour_at(x, y)` picks each pixel's colour (a
        facet, a band), a plain colour string fills it flat. `edge` outlines."""
        pick = colour_at if callable(colour_at) else (lambda x, y: colour_at)
        ys = [p[1] for p in points]
        pairs = list(zip(points, points[1:] + points[:1]))
        for y in range(min(ys), max(ys) + 1):
            xs = sorted(
                x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                for (x0, y0), (x1, y1) in pairs
                if (y0 <= y < y1) or (y1 <= y < y0)
            )
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(math.ceil(a), math.floor(b) + 1):
                    self.dot(x, y, pick(x, y))
        if edge:
            for (x0, y0), (x1, y1) in pairs:
                self.line(x0, y0, x1, y1, edge)

    def blend(self, x, y, colour, amount):
        if 0 <= x < self.w and 0 <= y < self.h:
            target = hexc(colour)
            self.px[y][x] = tuple(round(v + (t - v) * amount) for v, t in zip(self.px[y][x], target))

    def glow(self, cx, cy, rx, ry, colour, amount):
        """A light: three stepped rings, the way a small palette fakes a gradient."""
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if d < 1:
                    self.blend(x, y, colour, amount * (1 if d < 0.3 else 0.6 if d < 0.65 else 0.3))

    def image(self):
        img = Image.new("RGB", (self.w, self.h))
        img.putdata([self.px[y][x] for y in range(self.h) for x in range(self.w)])
        return img

    def save(self, path, scale=5, speaker=None, text=None):
        """Write the PNG scaled `scale` times; with `text`, a dialogue box
        under the scene in Pillow's bitmap font ("\\n" breaks a line)."""
        img = self.image()
        if text:
            rows = text.split("\n")
            box_h = 22 + 10 * len(rows)
            framed = Image.new("RGB", (self.w, self.h + box_h), hexc("#0e1430"))
            framed.paste(img, (0, 0))
            draw = ImageDraw.Draw(framed)
            top, bottom = self.h + 2, self.h + box_h - 3
            draw.rectangle([3, top, self.w - 4, bottom], fill=hexc("#1b2a6b"), outline=hexc("#e8ecff"))
            draw.rectangle([4, top + 1, self.w - 5, bottom - 1], outline=hexc("#3a4fa8"))
            # the bitmap font: Pillow 10.1+ load_default() is a smooth TrueType one
            font = getattr(ImageFont, "load_default_imagefont", ImageFont.load_default)()
            y = top + 4
            if speaker:
                draw.text((9, y), speaker, font=font, fill=hexc("#ffd76a"))
                y += 12
            for row in rows:
                draw.text((9, y), row, font=font, fill=hexc("#f4f6ff"))
                y += 10
            arrow_y = bottom - 6
            draw.polygon(
                [(self.w - 12, arrow_y), (self.w - 8, arrow_y), (self.w - 10, arrow_y + 2)],
                fill=hexc("#f4f6ff"),
            )
            img = framed
        img.resize((img.width * scale, img.height * scale), Image.NEAREST).save(path)
