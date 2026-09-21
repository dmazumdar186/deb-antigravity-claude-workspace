"""
make_golden.py
description: Generate 6 synthetic PNGs (3 modern, 3 dated) as a golden set for the vision_audit prompt.
inputs: None (no CLI args); requires Pillow.
outputs: {modern,dated}_{1,2,3}.png in this directory + golden.json with expected score bands.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent
WIDTH, HEIGHT = 390, 844

# Expected vision_audit.md anchor bands: modern = 0-4, dated = 7-10.
GOLDEN_SPEC = {
    "modern_1": {"band": "modern", "min_score": 0, "max_score": 4},
    "modern_2": {"band": "modern", "min_score": 0, "max_score": 4},
    "modern_3": {"band": "modern", "min_score": 0, "max_score": 4},
    "dated_1": {"band": "dated", "min_score": 7, "max_score": 10},
    "dated_2": {"band": "dated", "min_score": 7, "max_score": 10},
    "dated_3": {"band": "dated", "min_score": 7, "max_score": 10},
}


def _modern_image(seed: int) -> Image.Image:
    """Whitespace-driven, large single heading, one big CTA button — anchor 0-2 territory."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(250, 249, 246))
    draw = ImageDraw.Draw(img)
    accent = [(124, 92, 255), (28, 130, 110), (200, 90, 60)][seed % 3]
    # Large "heading" block (big type proxy: a tall filled bar).
    draw.rectangle([32, 90 + seed * 4, 358, 160 + seed * 4], fill=(30, 30, 30))
    # Generous whitespace, then one big CTA button near the bottom of the first viewport.
    draw.rounded_rectangle([32, 620, 358, 690], radius=16, fill=accent)
    draw.text((150, 645), "Book Now", fill=(255, 255, 255))
    return img


def _dated_image(seed: int) -> Image.Image:
    """Cluttered nav, small dense text blocks, a gradient hero, many boxes — anchor 7-8 territory."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(235, 235, 235))
    draw = ImageDraw.Draw(img)
    # Gradient-ish hero band (skeuomorphic banding).
    for y in range(0, 140):
        shade = 180 - int(y * 0.6) + seed * 5
        draw.line([(0, y), (WIDTH, y)], fill=(shade, shade // 2, shade // 3))
    # Cluttered nav: many small boxes in a row.
    for i in range(8):
        x = 4 + i * 48
        draw.rectangle([x, 145, x + 40, 170], outline=(90, 90, 90), fill=(210, 210, 210))
    # Dense small text blocks (many thin lines simulating small body type).
    for row in range(30):
        y = 190 + row * 18
        draw.line([(20, y), (370, y)], fill=(120, 120, 120), width=2)
    # A few bevel/drop-shadow style boxes scattered around.
    for i in range(4):
        x = 20 + i * 90
        y = 760
        draw.rectangle([x + 3, y + 3, x + 70, y + 40], fill=(140, 140, 140))
        draw.rectangle([x, y, x + 67, y + 37], fill=(200, 200, 200), outline=(90, 90, 90))
    return img


def main() -> None:
    for i in range(1, 4):
        _modern_image(i).save(OUT_DIR / f"modern_{i}.png")
        _dated_image(i).save(OUT_DIR / f"dated_{i}.png")

    (OUT_DIR / "golden.json").write_text(json.dumps(GOLDEN_SPEC, indent=2) + "\n", encoding="utf-8")
    print(f'{{"script": "make_golden", "images": 6, "out_dir": "{OUT_DIR}"}}')


if __name__ == "__main__":
    main()
