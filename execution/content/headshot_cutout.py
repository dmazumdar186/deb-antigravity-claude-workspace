"""
description: Cut the operator's studio headshot out of its dark-blue vignette background with PIL/numpy only (no ML): a chroma feature (green-minus-red, blue-minus-red) separates the blue backdrop from hair, skin and shirt; a border flood-fill keeps only backdrop connected to the edge; the navy jacket differs from the backdrop by ~4 units of green-minus-red, recovered by a 15px median; the alpha edge is eroded 1px and feathered 1.5px so no blue halo lands on paper.
inputs: --src <png> (default execution/content/assets/debanjan_headshot.png); --out <png with alpha> (default .tmp/banners/headshot_cutout.png); --debug <png> optional composite over paper for eyeballing; --bottom <source row where the bust is cut, default 1120>
outputs: RGBA PNG cut-out (bust, cropped to content), optional debug composite; prints the bounding box and the share of edge pixels still blue-tinted (halo check)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
PAPER = (243, 241, 236)


def backdrop_mask(rgb: np.ndarray) -> np.ndarray:
    """Boolean mask of backdrop pixels: median-smoothed green-minus-red chroma (backdrop >= 7, navy jacket <= 6,
    hair/skin negative), blue-minus-red and darkness gates, then only the region connected to the image border."""
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    gr = Image.fromarray(np.clip((g - r) * 8 + 64, 0, 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(15))
    cand = (np.array(gr).astype(np.int16) >= 7 * 8 + 64) & ((b - r) >= 18) & ((r + g + b) < 460)
    h, w = cand.shape
    lab = Image.fromarray(np.where(cand, 0, 255).astype(np.uint8)).copy()  # fromarray is read-only; floodfill needs a writable buffer
    for sx, sy in [(2, 2), (w - 3, 2), (2, h // 2), (w - 3, h // 2), (w // 2, 2), (2, h - 3), (w - 3, h - 3)]:
        if lab.getpixel((sx, sy)) == 0:
            ImageDraw.floodfill(lab, (sx, sy), 128)
    bg = np.array(lab) == 128
    # drop floating specks: keep only the foreground component that contains the image centre (the face)
    fg = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8)).copy()
    ImageDraw.floodfill(fg, (w // 2, h // 2), 128)
    return np.array(fg) != 128


def cut(src: Path, bottom: int) -> tuple[Image.Image, float]:
    im = Image.open(src).convert("RGB")
    rgb = np.array(im)[:bottom]  # bust: the darkest bottom corners of the vignette match the jacket; the card crops there anyway
    bg = backdrop_mask(rgb)
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.MinFilter(3))  # erode 1px: drops the blue-mixed rim pixels
    alpha = alpha.filter(ImageFilter.GaussianBlur(1.5))  # feather
    a = np.array(alpha)
    # halo check: among edge pixels (alpha 20-235) how many are still clearly blue-tinted (b-r >= 20)?
    # measured on the head only (rows above 55%): the navy jacket is blue by nature, hair and skin are not
    edge = (a > 20) & (a < 235)
    edge[int(a.shape[0] * .55):] = False
    r, b = rgb[..., 0].astype(np.int16), rgb[..., 2].astype(np.int16)
    halo = float(((b - r) >= 20)[edge].mean()) if edge.any() else 0.0
    # decontaminate: pull edge pixels toward their nearest opaque neighbour colour (simple: blend with a 5px blurred foreground)
    fg = np.array(Image.fromarray(rgb).filter(ImageFilter.GaussianBlur(3)))
    mix = np.clip(edge[..., None] * 0.6, 0, 1)
    out_rgb = (rgb * (1 - mix) + fg * mix).astype(np.uint8)
    out = Image.fromarray(np.dstack([out_rgb, a]))
    bbox = out.getbbox()
    return out.crop(bbox), halo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(ROOT / "execution/content/assets/debanjan_headshot.png"))
    ap.add_argument("--out", default=str(ROOT / ".tmp/banners/headshot_cutout.png"))
    ap.add_argument("--debug", default="")
    ap.add_argument("--bottom", type=int, default=1120, help="source row where the bust is cut (default 1120 of 1254)")
    a = ap.parse_args()
    out, halo = cut(Path(a.src), a.bottom)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out)
    if a.debug:
        paper = Image.new("RGB", out.size, PAPER)
        paper.paste(out, (0, 0), out)
        paper.save(a.debug)
    print(f"cutout {out.size[0]}x{out.size[1]} -> {a.out}; blue-tinted edge share {halo:.3f} (want < 0.05)")
    return 0 if halo < 0.05 else 1


if __name__ == "__main__":
    sys.exit(main())
