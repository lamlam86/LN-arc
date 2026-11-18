#!/usr/bin/env python3
"""Generate LN-AI brand PNG/ICO assets from the same geometry as logo.svg.

No third-party dependencies: draws into an RGBA buffer with 4x supersampling,
downsamples, and writes PNG (zlib) plus a PNG-backed ICO.

Run from the repository root:
    python3 tools/generate_brand.py
"""
from __future__ import annotations

import math
import pathlib
import struct
import zlib

OUT = 512
SS = 4
SIZE = OUT * SS

BG1 = (7, 11, 20)
BG2 = (15, 23, 42)
BORDER = (30, 41, 59)
ACCENT1 = (34, 211, 238)
ACCENT2 = (99, 102, 241)
DOT = (103, 232, 249)


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def accent_at(x: int) -> tuple[int, int, int]:
    t = min(1.0, max(0.0, x / SIZE))
    return (
        lerp(ACCENT1[0], ACCENT2[0], t),
        lerp(ACCENT1[1], ACCENT2[1], t),
        lerp(ACCENT1[2], ACCENT2[2], t),
    )


def blend(buf: bytearray, idx: int, rgb: tuple[int, int, int], alpha: float = 1.0) -> None:
    if alpha <= 0:
        return
    if alpha >= 1:
        buf[idx] = rgb[0]
        buf[idx + 1] = rgb[1]
        buf[idx + 2] = rgb[2]
        buf[idx + 3] = 255
        return
    inv = 1.0 - alpha
    buf[idx] = int(rgb[0] * alpha + buf[idx] * inv)
    buf[idx + 1] = int(rgb[1] * alpha + buf[idx + 1] * inv)
    buf[idx + 2] = int(rgb[2] * alpha + buf[idx + 2] * inv)
    buf[idx + 3] = int(255 * alpha + buf[idx + 3] * inv)


def in_round_rect(x: float, y: float, x0: float, y0: float, x1: float, y1: float, r: float) -> bool:
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def fill_round_rect(buf: bytearray, x0: float, y0: float, x1: float, y1: float, r: float, rgb: tuple[int, int, int]):
    for py in range(int(y0), int(y1) + 1):
        for px in range(int(x0), int(x1) + 1):
            if in_round_rect(px + 0.5, py + 0.5, x0, y0, x1, y1, r):
                blend(buf, (py * SIZE + px) * 4, rgb)


def segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def stroke_polyline(buf: bytearray, pts: list[tuple[float, float]], width: float):
    half = width / 2.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    for py in range(int(min(ys) - half) - 1, int(max(ys) + half) + 2):
        for px in range(int(min(xs) - half) - 1, int(max(xs) + half) + 2):
            if px < 0 or py < 0 or px >= SIZE or py >= SIZE:
                continue
            d = min(segment_distance(px + 0.5, py + 0.5, *a, *b) for a, b in zip(pts, pts[1:]))
            if d <= half:
                blend(buf, (py * SIZE + px) * 4, accent_at(px))


def circle(buf: bytearray, cx: float, cy: float, r: float, rgb: tuple[int, int, int], alpha: float = 1.0):
    for py in range(int(cy - r) - 1, int(cy + r) + 2):
        for px in range(int(cx - r) - 1, int(cx + r) + 2):
            if px < 0 or py < 0 or px >= SIZE or py >= SIZE:
                continue
            if (px + 0.5 - cx) ** 2 + (py + 0.5 - cy) ** 2 <= r * r:
                blend(buf, (py * SIZE + px) * 4, rgb, alpha)


def ring(buf: bytearray, cx: float, cy: float, r: float, width: float, rgb: tuple[int, int, int], alpha: float):
    outer, inner = r + width / 2, max(0.0, r - width / 2)
    for py in range(int(cy - outer) - 1, int(cy + outer) + 2):
        for px in range(int(cx - outer) - 1, int(cx + outer) + 2):
            if px < 0 or py < 0 or px >= SIZE or py >= SIZE:
                continue
            d = math.hypot(px + 0.5 - cx, py + 0.5 - cy)
            if inner <= d <= outer:
                blend(buf, (py * SIZE + px) * 4, rgb, alpha)


def downsample(buf: bytearray, factor: int) -> bytes:
    out = bytearray((OUT * OUT) * 4)
    area = factor * factor
    for y in range(OUT):
        for x in range(OUT):
            r = g = b = a = 0
            for sy in range(factor):
                base = ((y * factor + sy) * SIZE + x * factor) * 4
                for sx in range(factor):
                    i = base + sx * 4
                    r += buf[i]
                    g += buf[i + 1]
                    b += buf[i + 2]
                    a += buf[i + 3]
            i = (y * OUT + x) * 4
            out[i] = r // area
            out[i + 1] = g // area
            out[i + 2] = b // area
            out[i + 3] = a // area
    return bytes(out)


def resize_rgba(src: bytes, sw: int, sh: int, dw: int, dh: int) -> bytes:
    out = bytearray(dw * dh * 4)
    for y in range(dh):
        y0, y1 = y * sh // dh, max((y + 1) * sh // dh, y * sh // dh + 1)
        for x in range(dw):
            x0, x1 = x * sw // dw, max((x + 1) * sw // dw, x * sw // dw + 1)
            r = g = b = a = n = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    i = (yy * sw + xx) * 4
                    r += src[i]
                    g += src[i + 1]
                    b += src[i + 2]
                    a += src[i + 3]
                    n += 1
            i = (y * dw + x) * 4
            out[i] = r // n
            out[i + 1] = g // n
            out[i + 2] = b // n
            out[i + 3] = a // n
    return bytes(out)


def png_bytes(rgba: bytes, w: int, h: int) -> bytes:
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def ico_bytes(png: bytes, w: int, h: int) -> bytes:
    return (
        struct.pack("<HHH", 0, 1, 1)
        + struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(png), 22)
        + png
    )


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    buf = bytearray(SIZE * SIZE * 4)

    # Background: border ring then gradient interior.
    fill_round_rect(buf, 8 * SS, 8 * SS, 504 * SS, 504 * SS, 116 * SS, BORDER)
    for y in range(SIZE):
        for x in range(SIZE):
            if in_round_rect(x + 0.5, y + 0.5, 14 * SS, 14 * SS, 498 * SS, 498 * SS, 110 * SS):
                t = (x + y) / (2 * SIZE)
                rgb = (lerp(BG1[0], BG2[0], t), lerp(BG1[1], BG2[1], t), lerp(BG1[2], BG2[2], t))
                blend(buf, (y * SIZE + x) * 4, rgb)

    # Subtle circuit accents.
    stroke_polyline(buf, [(64 * SS, 168 * SS), (108 * SS, 168 * SS), (108 * SS, 212 * SS)], 3 * SS)
    stroke_polyline(buf, [(448 * SS, 344 * SS), (404 * SS, 344 * SS), (404 * SS, 300 * SS)], 3 * SS)
    circle(buf, 64 * SS, 168 * SS, 5 * SS, ACCENT1, 0.35)
    circle(buf, 448 * SS, 344 * SS, 5 * SS, ACCENT2, 0.35)

    # LN monogram.
    stroke_polyline(buf, [(128 * SS, 150 * SS), (128 * SS, 340 * SS), (244 * SS, 340 * SS)], 46 * SS)
    stroke_polyline(
        buf,
        [(300 * SS, 340 * SS), (300 * SS, 150 * SS), (388 * SS, 340 * SS), (388 * SS, 150 * SS)],
        46 * SS,
    )

    # AI node.
    circle(buf, 420 * SS, 110 * SS, 18 * SS, DOT)
    ring(buf, 420 * SS, 110 * SS, 38 * SS, 3 * SS, ACCENT1, 0.45)

    rgba = downsample(buf, SS)
    png = png_bytes(rgba, OUT, OUT)

    targets = [
        root / "web/public/logo.png",
        root / "web/src/app/icon.png",
    ]
    for target in targets:
        target.write_bytes(png)
        print(f"wrote {target.relative_to(root)} ({OUT}x{OUT})")

    # PNG-backed ICO (64x64). Modern browsers support PNG entries.
    small = resize_rgba(rgba, OUT, OUT, 64, 64)
    ico = ico_bytes(png_bytes(small, 64, 64), 64, 64)
    favicon = root / "web/src/app/favicon.ico"
    favicon.write_bytes(ico)
    print(f"wrote {favicon.relative_to(root)} (64x64)")


if __name__ == "__main__":
    main()
