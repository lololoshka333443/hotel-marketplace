#!/usr/bin/env python3
"""Optimize room photos for the web.

Reads raw photos under web/public/rooms/<n>/ (large JPGs straight from a camera)
and writes <name>.webp next to them, capped at 1600px wide, quality 82.
Run once after dropping in new photos:

    uv run python scripts/optimize_photos.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "public" / "rooms"

MAX_WIDTH = 1600
QUALITY = 82
COVER_SUFFIX = "_cover"


def optimize_one(path: Path, width: int = MAX_WIDTH) -> Path:
    out = path.with_suffix(".webp")
    if out.exists():
        return out
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)  # honor camera orientation
        if im.width > width:
            ratio = width / im.width
            im = im.resize((width, round(im.height * ratio)), Image.LANCZOS)
        im.save(out, "WEBP", quality=QUALITY, method=6)
    return out


def main() -> int:
    if not SRC.is_dir():
        print(f"no {SRC}")
        return 1
    total_in = 0
    total_out = 0
    for jpg in sorted(SRC.rglob("*.JPG")) + sorted(SRC.rglob("*.jpg")):
        webp = optimize_one(jpg)
        total_in += jpg.stat().st_size
        total_out += webp.stat().st_size
        print(f"{jpg.relative_to(ROOT)}  {jpg.stat().st_size // 1024}KB -> {webp.stat().st_size // 1024}KB")
    if total_in:
        print(f"\ntotal: {total_in // 1024 // 1024}MB -> {total_out // 1024 // 1024}MB "
              f"({total_out * 100 // total_in}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
