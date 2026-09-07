"""Generate PWA/iOS app icons (pure stdlib PNG writer, 512->180/192/512px).

Draws the DataMind mark: sky-gradient rounded square, white bar chart with an
orange trend line. Run once; icons are committed to the repo.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "static" / "icons"


def _chunks(png_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + png_type
        + data
        + struct.pack(">I", zlib.crc32(png_type + data) & 0xFFFFFFFF)
    )


def write_png(path: Path, width: int, height: int, pixel: bytes) -> None:
    raw = b"".join(
        b"\x00" + pixel[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunks(b"IHDR", ihdr)
        + _chunks(b"IDAT", zlib.compress(raw, 9))
        + _chunks(b"IEND", b"")
    )


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def rounded_square_mask(x: int, y: int, size: int, radius: float) -> bool:
    if not (0 <= x < size and 0 <= y < size):
        return False
    r = radius
    cx = min(max(x, r), size - 1 - r)
    cy = min(max(y, r), size - 1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def render(size: int) -> bytes:
    px = bytearray(size * size * 3)
    top = (64, 150, 210)
    bottom = (90, 190, 235)
    white = (255, 255, 255)
    orange = (224, 123, 57)

    bars = [0.52, 0.34, 0.66]
    bw = size * 0.13
    gap = size * 0.085
    base_y = size * 0.78
    line = [
        (size * 0.22, size * 0.62),
        (size * 0.46, size * 0.42),
        (size * 0.72, size * 0.26),
    ]

    for y in range(size):
        for x in range(size):
            t = y / size
            r, g, b = (lerp(top[i], bottom[i], t) for i in range(3))

            in_any = False
            for i, h in enumerate(bars):
                x0 = size * 0.17 + i * (bw + gap)
                if x0 <= x < x0 + bw and base_y - size * h <= y < base_y:
                    in_any = True
            if in_any:
                r, g, b = white

            for (x1, y1), (x2, y2) in zip(line, line[1:]):
                steps = 40
                for s in range(steps + 1):
                    sx = lerp(x1, x2, s / steps)
                    sy = lerp(y1, y2, s / steps)
                    if (x - sx) ** 2 + (y - sy) ** 2 <= (size * 0.018) ** 2:
                        r, g, b = orange
                        break

            o = (y * size + x) * 3
            px[o : o + 3] = (int(r), int(g), int(b))
    return bytes(px)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = render(512)
    # full-bleed square: iOS applies its own corner mask on the home screen
    write_png(OUT_DIR / "icon-512.png", 512, 512, base)
    write_png(OUT_DIR / "icon-192.png", 192, 192, _resize(base, 512, 192))
    write_png(OUT_DIR / "apple-touch-icon.png", 180, 180, _resize(base, 512, 180))
    for f in sorted(OUT_DIR.iterdir()):
        print(f"{f.name}: {f.stat().st_size / 1024:.1f} KB")


def _resize(src: bytes, src_size: int, dst_size: int) -> bytes:
    """Nearest-neighbour downscale of an RGB byte buffer."""
    out = bytearray(dst_size * dst_size * 3)
    ratio = src_size / dst_size
    for y in range(dst_size):
        sy = min(int(y * ratio), src_size - 1)
        for x in range(dst_size):
            sx = min(int(x * ratio), src_size - 1)
            o = (y * dst_size + x) * 3
            s = (sy * src_size + sx) * 3
            out[o : o + 3] = src[s : s + 3]
    return bytes(out)


if __name__ == "__main__":
    main()
