"""brand_v6.py: rebuild the brand kit from the client's new seal (Revised Concept 2, LEFTMOST seal), 2026-10-28.

What / why: the client switched from the v5 seal (dark-brown figure, "& WELLNESS", G1A under her) to the leftmost seal on
  research/brand_v6_src/logo-concepts-revised.jpg: sage outer ring, thin terracotta ring, "JEEVANA YOGA" / "AND WELLNESS"
  arc text, sage side arcs, gold ring, terracotta figure with a pale lotus and a gold crescent, "G1A" across her.
Approach: raster-in-SVG. The seal is rendered with embossed shading, a translucent lotus and highlights that potrace cannot
  reproduce faithfully, and fidelity to the client's logo beats vector purity. The seal disc (centre 431.5,601.5, outer
  radius 301 px in the 2000x1116 sheet) is cut out with an anti-aliased circular alpha mask (transparent outside the sage
  ring; the inner cream stays), upscaled with Pillow LANCZOS + a light unsharp mask, and embedded as WebP (data URI) in each
  SVG. The wordmark "Jeevana Yoga & Wellness" stays vector (Cormorant outlines via brand_v5.line), so no font is referenced.
  Header + favicons use the inner part only (figure, lotus, moon, G1A, gold ring; r 210 px) inside vector sage/terracotta
  rings, because the arc text is illegible below ~60 px.
Same filenames and viewBoxes as v5 (logo 1834x400, logo-stacked 627x495, logo-header 895x312, mark 400x400), so no HTML change.
Run:  pip install pillow numpy fonttools brotli cairosvg
      python3 research/brand_v6.py
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_v5 import INK, line  # noqa: E402  (Cormorant glyph outlines)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "research" / "brand_v6_src" / "logo-concepts-revised.jpg"
BRAND = ROOT / "site" / "assets" / "brand"
PHOTOS = ROOT / "site" / "assets" / "photos"

CX, CY, R_OUT, R_IN = 431.5, 601.5, 301.0, 210.0  # source px
SAGE, TERRA, CREAM = "#7A8C6C", "#B25C38", "#FAF6EE"
PAPER = "#D4BC8E"  # v6 aged-papyrus --paper (icon tiles, og ground)
TITLE = "G1A — Jeevana Yoga &amp; Wellness"
NAME = "Jeevana Yoga & Wellness"


def disc(r: float, out: int, ss: int = 4) -> Image.Image:
    """Seal cut to radius r (source px) about the centre, upscaled to out x out RGBA, transparent outside r."""
    src = Image.open(SRC).convert("RGB")
    pad = r + 2
    box = (CX - pad, CY - pad, CX + pad, CY + pad)
    big = src.resize((out * ss, out * ss), Image.LANCZOS, box=box)
    m = Image.new("L", big.size, 0)
    k = out * ss / (2 * pad)
    c = out * ss / 2
    ImageDraw.Draw(m).ellipse((c - r * k, c - r * k, c + r * k, c + r * k), fill=255)
    big.putalpha(m)
    im = big.resize((out, out), Image.LANCZOS)
    rgb = im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    rgb.putalpha(im.getchannel("A"))
    return rgb


def webp_uri(im: Image.Image, q: int = 86) -> str:
    b = io.BytesIO()
    im.save(b, "WEBP", quality=q, method=6, alpha_quality=90)
    return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()


def svg(w: float, h: float, body: str, vb: str | None = None, size: bool = True) -> str:
    wh = f' width="{w:.0f}" height="{h:.0f}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb or f"0 0 {w:.0f} {h:.0f}"}"{wh} role="img" '
            f'aria-label="{TITLE}"><title>{TITLE}</title>{body}</svg>\n')


def image(uri: str, x: float, y: float, s: float) -> str:
    return f'<image href="{uri}" x="{x:.1f}" y="{y:.1f}" width="{s:.1f}" height="{s:.1f}"/>'


def inner_seal(uri: str) -> str:
    """400-unit box, centre 200,200: cream disc, inner raster (r 134), thin terracotta ring, sage ring (outer edge 155)."""
    ri = 134.0
    return (f'<circle cx="200" cy="200" r="150" fill="{CREAM}" stroke="{SAGE}" stroke-width="10"/>'
            + image(uri, 200 - ri * (R_IN + 2) / R_IN, 200 - ri * (R_IN + 2) / R_IN, 2 * ri * (R_IN + 2) / R_IN)
            + f'<circle cx="200" cy="200" r="139" fill="none" stroke="{TERRA}" stroke-width="2.6"/>')


def inner_png(size: int, r_src: float = R_IN) -> Image.Image:
    """Inner seal rasterised in Pillow (better downsampling than cairo for 16-512 px icons). A smaller r_src crops tighter
    to the figure + G1A (16/32 px favicons: no gold ring, no terracotta ring, heavier sage ring)."""
    tight = r_src < R_IN
    ss = 4
    S = size * ss
    k = S / 310  # 310-unit frame (ring outer edge 155) fills the tile
    can = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(can)
    c = S / 2
    d.ellipse((c - 155 * k, c - 155 * k, c + 155 * k, c + 155 * k), fill=SAGE)
    rc = 138 if tight else 145
    d.ellipse((c - rc * k, c - rc * k, c + rc * k, c + rc * k), fill=CREAM)
    ri = (rc + 2) * k if tight else 134 * k
    ins = disc(r_src, int(2 * ri * (r_src + 2) / r_src))
    can.alpha_composite(ins, (int(c - ins.width / 2), int(c - ins.height / 2)))
    if tight:
        return can.resize((size, size), Image.LANCZOS)
    w = max(1, round(2.6 * k))
    d = ImageDraw.Draw(can)
    d.ellipse((c - 139 * k - w / 2, c - 139 * k - w / 2, c + 139 * k + w / 2, c + 139 * k + w / 2), outline=TERRA, width=w)
    return can.resize((size, size), Image.LANCZOS)


def build() -> None:
    import cairosvg

    full = webp_uri(disc(R_OUT, 760), 84)
    inner = webp_uri(disc(R_IN, 640))
    S = image(full, 0, 0, 400)  # full seal fills the 400-unit box (outer ring edge at r 200)

    (BRAND / "mark.svg").write_text(svg(400, 400, S), encoding="utf-8")

    # header lockup: inner seal (left 312 square) + two-line name, same frame as v5 so CSS crops keep working
    s1, s2 = 150, 80
    _, w1 = line("Jeevana", 500, s1, 0, 0)
    _, w2 = line("Yoga & Wellness", 500, s2, 0, 0, 0.02)
    x0 = 312 + 30
    d1, _ = line("Jeevana", 500, s1, x0, 152)
    d2, _ = line("Yoga & Wellness", 500, s2, x0 + 4, 242, 0.02)
    W = x0 + max(w1, w2 + 4) + 8
    (BRAND / "logo-header.svg").write_text(
        svg(895, 312, f'<g transform="translate(-44 -44)">{inner_seal(inner)}</g>'
                      f'<path fill="{INK}" d="{d1}"/><path fill="{INK}" d="{d2}"/>'), encoding="utf-8")
    assert abs(W - 895) < 2, W

    # horizontal lockup: seal, then the name with the x-height centred on the seal
    size = 145
    _, tw = line(NAME, 500, size, 0, 0)
    d, _ = line(NAME, 500, size, 400 + 34, 200 + 0.625 * size / 2)
    (BRAND / "logo.svg").write_text(svg(1834, 400, S + f'<path fill="{INK}" d="{d}"/>'), encoding="utf-8")

    # stacked lockup (footer): full seal above the name
    size = 64
    _, tw = line(NAME, 500, size, 0, 0)
    Wst = max(400, tw) + 12
    Hst = 400 + 36 + 0.924 * size
    d, _ = line(NAME, 500, size, (Wst - tw) / 2, 400 + 36 + 0.625 * size)
    (BRAND / "logo-stacked.svg").write_text(
        svg(627, 495, f'<g transform="translate({(Wst - 400) / 2:.1f} 0)">{S}</g><path fill="{INK}" d="{d}"/>'),
        encoding="utf-8")

    # favicons: inner seal only
    fav_uri = webp_uri(inner_png(192), 88)
    (BRAND / "favicon.svg").write_text(svg(64, 64, image(fav_uri, 0, 0, 64), size=False), encoding="utf-8")
    for n in (16, 32):
        inner_png(n, 178).save(BRAND / f"favicon-{n}.png", optimize=True)

    def tile(size: int, fill: float, im: Image.Image) -> Image.Image:
        t = Image.new("RGBA", (size, size), PAPER)
        s = round(size * fill)
        t.alpha_composite(im.resize((s, s), Image.LANCZOS), ((size - s) // 2, (size - s) // 2))
        return t.convert("RGB")

    tile(180, 0.9, inner_png(720)).save(BRAND / "apple-touch-icon.png", optimize=True)
    tile(512, 0.8, disc(R_OUT, 1024)).save(BRAND / "icon-512.png", optimize=True)  # 80 % maskable safe zone

    # og.jpg 1200x630: stacked seal + name on papyrus at left, the sun photo at right
    og = Image.new("RGB", (1200, 630), PAPER)
    sun = Image.open(PHOTOS / "sun@1400.webp").convert("RGB")
    pw = 560
    ph = round(sun.height * pw / sun.width)
    sun = sun.resize((pw, ph), Image.LANCZOS)
    top = max(0, min(ph - 630, round(ph * 0.04)))
    og.paste(sun.crop((0, top, pw, top + 630)), (1200 - pw, 0))
    lw = 470
    seal = disc(R_OUT, 1000).resize((round(lw * 400 / 627),) * 2, Image.LANCZOS)
    name_svg = svg(627, 495, f'<path fill="{INK}" d="{d}"/>')
    name = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=name_svg.encode(), output_width=lw))).convert("RGBA")
    x, y = (1200 - pw - lw) // 2, (630 - name.height) // 2
    og.paste(name, (x, y), name)
    og.paste(seal, (x + (lw - seal.width) // 2, y), seal)
    og.save(BRAND / "og.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    for p in sorted(BRAND.iterdir()):
        print(f"{p.name:22} {p.stat().st_size:>8}")


if __name__ == "__main__":
    build()
