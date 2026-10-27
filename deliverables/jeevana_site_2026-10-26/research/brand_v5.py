"""brand_v5.py: rebuild the brand kit from Concept 2 (the circular seal), "Jeevana Yoga & Wellness", G1A.

Brief: research/brief_v5.md, last section ("Brand change ... Concept 2"). Supersedes the Concept 3 brand in polish_v5.py.
  pip install potracer opencv-python-headless fonttools brotli cairosvg pillow numpy
  python3 research/brand_v5.py

Seal (400 x 400 units, centre 200,200), measured from _raw_assets/v5/logo-concepts.jpg (seal centre 999.5,480; outer r 182 px):
  sage outer ring, thin terracotta ring, ring text (top arc "JEEVANA YOGA & WELLNESS", bottom arc "G1A") set glyph by glyph
  on the arc from Cormorant Garamond outlines (fontTools), sage arcs between the two texts, thin gold ring round the figure,
  terracotta seated figure with a light chest panel, "G1A" across her (sage G and A, terracotta 1).
Figure: the right half of the source figure (the left half is hidden by the G) is upscaled x8, thresholded on colour, mirrored
  about the head axis, smoothed and traced with potracer, so she is symmetric and calm. No font files are referenced by any
  output; every letter is a path.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_raw_assets" / "v5" / "logo-concepts.jpg"
BRAND = ROOT / "site" / "assets" / "brand"
PHOTOS = ROOT / "site" / "assets" / "photos"
FONTS = ROOT / "site" / "assets" / "fonts"

INK, SAGE, TERRA, TERRA_DK, GOLD, PAPER, PANEL = "#2B1E14", "#7E8C6E", "#B9744B", "#9E5D3B", "#B8862B", "#EAD9B8", "#F6EBDC"
TITLE = "G1A — Jeevana Yoga &amp; Wellness"

# source geometry (px in the 2000 x 1116 concept sheet)
CX, CY, F = 999.5, 480.0, 1.05  # seal centre and px -> unit factor
CROP, K = (878, 358, 1122, 582), 8  # figure crop and upscale
FIG_DY = 12  # figure + G1A sit a little lower in the seal than in the sketch, centring them in the gold ring


# ---------------------------------------------------------------- figure
def figure_masks() -> tuple[np.ndarray, np.ndarray]:
    """Return (body, panel) masks in x8 crop pixels; body excludes the arm/torso gaps, panel is the light chest."""
    import cv2

    im = cv2.imread(str(SRC))
    x0, y0, x1, y1 = CROP
    c = cv2.resize(im[y0:y1, x0:x1], None, fx=K, fy=K, interpolation=cv2.INTER_CUBIC)
    c = cv2.GaussianBlur(c, (0, 0), K * 0.5)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV).astype(int)
    s, v = hsv[..., 1], hsv[..., 2]
    b, g, r = (c[..., i].astype(int) for i in range(3))
    sage = (g >= r - 4) & (s > 25) & (v < 220)
    terra = (r - b > 45) & ~sage

    def u8(m):
        return m.astype(np.uint8)

    def ell(k):
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    closed = cv2.morphologyEx(u8(terra), cv2.MORPH_CLOSE, ell(K * 14)) > 0
    body = terra | (closed & (cv2.dilate(u8(sage), ell(K * 2)) > 0))
    n, lab, st, _ = cv2.connectedComponentsWithStats(u8(body), 8)
    body = lab == (1 + np.argmax(st[1:, 4]))

    # mirror the clean right half about the head axis
    ys, xs = np.nonzero(body[160:440])
    ax = int(round(xs.mean()))
    right = body[:, ax:]
    body = np.concatenate([right[:, ::-1], right], axis=1)
    body = cv2.GaussianBlur(body.astype(np.float32), (0, 0), K * 1.3) > 0.5

    # holes: the biggest is the chest panel, the rest (arm gaps, mudra loops, leg line) stay open
    H, W = body.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats(u8(~body), 4)
    holes = sorted(((st[i, 4], i) for i in range(1, n)
                    if not (st[i, 0] == 0 or st[i, 1] == 0 or st[i, 0] + st[i, 2] == W or st[i, 1] + st[i, 3] == H)),
                   reverse=True)
    panel = lab == holes[0][1]
    # tidy the panel: cut its lap drip and side tails, round it off, keep it inset from the body edge
    yy = np.arange(H)[:, None]
    panel &= yy < 1368
    panel = cv2.morphologyEx(u8(panel), cv2.MORPH_OPEN, ell(K * 7)) > 0
    panel = cv2.GaussianBlur(panel.astype(np.float32), (0, 0), K * 2.0) > 0.5
    panel = cv2.erode(u8(panel), ell(K * 1)) > 0
    pr = panel[:, W // 2:]
    panel = np.concatenate([pr[:, ::-1], pr], axis=1)
    solid = body.copy()
    for _, i in holes:
        solid |= lab == i
    keep_open = np.zeros_like(body)
    for a, i in holes[1:]:
        if a > K * K * 24:  # arm gaps and the leg line; the tiny mudra loops close
            keep_open |= lab == i
    body = solid & ~keep_open
    return body, panel


def trace(mask: np.ndarray, alphamax: float = 1.15) -> str:
    """Trace a x8 crop mask into seal units."""
    import potrace

    plist = potrace.Bitmap(~mask).trace(turdsize=200, alphamax=alphamax, opticurve=True, opttolerance=0.5)

    def f(pt) -> str:
        ux = 200 + F * (CROP[0] + pt.x / K - CX)
        uy = 200 + F * (CROP[1] + pt.y / K - CY)
        return f"{ux:.2f} {uy:.2f}"

    parts = []
    for curve in plist:
        parts.append("M" + f(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                parts.append("L" + f(seg.c) + "L" + f(seg.end_point))
            else:
                parts.append("C" + f(seg.c1) + " " + f(seg.c2) + " " + f(seg.end_point))
        parts.append("Z")
    return "".join(parts).replace(" -", "-")


# ---------------------------------------------------------------- type
_FONTS: dict[int, object] = {}
KERN = {("V", "A"): -60, ("A", "V"): -60, ("Y", "O"): -30, ("G", "A"): -10, ("A", "N"): -10, ("W", "E"): -25,
        ("J", "e"): -40, ("Y", "o"): -60, ("W", "e"): -50, ("v", "a"): -10}


def font(weight: int):
    from fontTools.ttLib import TTFont

    if weight not in _FONTS:
        _FONTS[weight] = TTFont(str(FONTS / f"cormorant-garamond-latin-{weight}-normal.woff2"))
    return _FONTS[weight]


ALT = {"1": "one.lf"}  # Cormorant's default figures are old-style; G1A wants the lining 1


def gname(ch: str, weight: int) -> str:
    return ALT.get(ch) or font(weight).getBestCmap()[ord(ch)]


def glyph(ch: str, weight: int, m: tuple[float, ...]) -> str:
    """Outline one character with affine matrix m = (a, b, c, d, e, f) applied to font units."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    ft = font(weight)
    gs = ft.getGlyphSet()
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}")
    gs[gname(ch, weight)].draw(TransformPen(pen, m))
    return pen.getCommands()


def advance(ch: str, weight: int) -> float:
    ft = font(weight)
    if ch == " ":
        return ft["hmtx"]["space"][0]
    return ft["hmtx"][gname(ch, weight)][0]


def line(text: str, weight: int, size: float, x0: float, baseline: float, tracking: float = 0.0) -> tuple[str, float]:
    """Straight text as one path; returns (d, width)."""
    s = size / 1000
    x, d, prev = x0, [], None
    for ch in text:
        x += KERN.get((prev, ch), 0) * s if prev else 0
        if ch != " ":
            d.append(glyph(ch, weight, (s, 0, 0, -s, x, baseline)))
        x += (advance(ch, weight) + tracking * 1000) * s
        prev = ch
    return "".join(d), x - x0 - tracking * size


def arc(text: str, weight: int, size: float, rb: float, bottom: bool, tracking: float, space: float = 1.0) -> tuple[str, float]:
    """Glyphs on a circle about (200,200). Top: baseline on rb, tops outward, centred on 12 o'clock.
    Bottom: baseline on rb, upright (tops toward the centre), centred on 6 o'clock. Returns (d, half-span in radians)."""
    s = size / 1000
    adv = []
    prev = None
    for ch in text:
        k = KERN.get((prev, ch), 0) if prev else 0
        a = advance(ch, weight) * (space if ch == " " else 1)
        adv.append((ch, k * s, a * s))
        prev = ch
    total = sum(k + a for _, k, a in adv) + tracking * size * (len(text) - 1)
    span = total / rb
    out = []
    pos = 0.0
    for ch, k, a in adv:
        pos += k
        mid = pos + a / 2
        if bottom:
            th = math.pi + span / 2 - mid / rb
            rot = th - math.pi
        else:
            th = -span / 2 + mid / rb
            rot = th
        px, py = 200 + rb * math.sin(th), 200 - rb * math.cos(th)
        cr, sr = math.cos(rot), math.sin(rot)
        # glyph unit (gx, gy) -> local (s*gx - a/2, -s*gy) -> rotate -> translate
        m = (s * cr, s * sr, s * sr, -s * cr, px - a / 2 * cr, py - a / 2 * sr)
        if ch != " ":
            out.append(glyph(ch, weight, m))
        pos += a + tracking * size
    return "".join(out), span / 2


def circle(r: float, color: str, w: float) -> str:
    return f'<circle cx="200" cy="200" r="{r}" fill="none" stroke="{color}" stroke-width="{w}"/>'


def arc_stroke(r: float, a0: float, a1: float, color: str, w: float) -> str:
    """Arc from angle a0 to a1 (radians clockwise from 12 o'clock), a0 < a1."""
    p0 = (200 + r * math.sin(a0), 200 - r * math.cos(a0))
    p1 = (200 + r * math.sin(a1), 200 - r * math.cos(a1))
    large = 1 if a1 - a0 > math.pi else 0
    return (f'<path d="M{p0[0]:.2f} {p0[1]:.2f}A{r} {r} 0 {large} 1 {p1[0]:.2f} {p1[1]:.2f}" fill="none" '
            f'stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>')


# ---------------------------------------------------------------- seal
DEFS = ('<defs><linearGradient id="jv-skin" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#C98A63"/><stop offset="1" stop-color="#B26C47"/></linearGradient></defs>')


def g1a(weight: int = 500, size: float = 136.0, base: float = 236.0, one_base: float = 246.0, one_size: float = 118.0,
        gx: float = 126.0, axc: float = 286.0, one_col: str = TERRA) -> str:
    """Sage G and A either side of the figure, terracotta 1 on her chest; x are glyph centres."""
    out = []
    for ch, cxp, sz, bl, col in (("G", gx, size, base, SAGE), ("A", axc, size, base, SAGE), ("1", 200.0, one_size, one_base, one_col)):
        w = advance(ch, weight) * sz / 1000
        d, _ = line(ch, weight, sz, cxp - w / 2, bl)
        out.append(f'<path fill="{col}" d="{d}"/>')
    return "".join(out)


def figure_svg(body_d: str, panel_d: str, outline: bool = True) -> str:
    stroke = f' stroke="{TERRA_DK}" stroke-width="1.3" stroke-linejoin="round"' if outline else ""
    return (f'<path fill="url(#jv-skin)"{stroke} d="{body_d}"/>'
            f'<path fill="{PANEL}" d="{panel_d}"/>')


def seal(body_d: str, panel_d: str) -> str:
    """Full seal in a 400 x 400 box."""
    top, top_half = arc("JEEVANA YOGA & WELLNESS", 600, 27.5, 155.5, False, 0.13, 0.9)
    bot, bot_half = arc("G1A", 600, 31.0, 172.5, True, 0.16)
    gap = 0.075
    r_mid = 164.5
    sides = (arc_stroke(r_mid, top_half + gap, math.pi - bot_half - gap, SAGE, 1.6)
             + arc_stroke(r_mid, math.pi + bot_half + gap, 2 * math.pi - top_half - gap, SAGE, 1.6))
    return (DEFS + circle(192, SAGE, 6.5) + circle(182.5, TERRA, 1.6) + sides
            + f'<path fill="{INK}" d="{top}"/><path fill="{INK}" d="{bot}"/>'
            + circle(126, GOLD, 1.5)
            + f'<g transform="translate(0 {FIG_DY})">' + figure_svg(body_d, panel_d) + g1a() + "</g>")


def svg(w: float, h: float, body: str, bg: str | None = None, size: bool = True) -> str:
    rect = f'<rect width="{w:.0f}" height="{h:.0f}" fill="{bg}"/>' if bg else ""
    wh = f' width="{w:.0f}" height="{h:.0f}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}"{wh} role="img" '
            f'aria-label="{TITLE}"><title>{TITLE}</title>{rect}{body}</svg>\n')


def png(svg_text: str, out: Path, size: int) -> None:
    import cairosvg

    cairosvg.svg2png(bytestring=svg_text.encode(), write_to=str(out), output_width=size, output_height=size)


def favicon(body_d: str) -> str:
    """Seal simplified for 16-180 px: sage ring, solid figure, heavy G1A with a parchment halo so the sage letters
    separate from the terracotta body at 16 px; no ring text. The 1 is cut out of her chest in parchment."""
    lite = "#F5ECDB"
    letters = g1a(weight=600, size=146, base=244, one_base=247, one_size=118, gx=124, axc=279, one_col=lite)
    halo = letters.replace(f'fill="{SAGE}"', f'fill="{lite}" stroke="{lite}" stroke-width="16" stroke-linejoin="round"')
    halo = "".join(p + "/>" for p in halo.split("/>") if p and lite + '" stroke' in p)
    heavy = letters.replace(f'fill="{SAGE}"', f'fill="{SAGE}" stroke="{SAGE}" stroke-width="5" stroke-linejoin="round"')
    inner = (f'<circle cx="200" cy="200" r="139" fill="{lite}" stroke="{SAGE}" stroke-width="18"/>'
             f'<g transform="translate(200 204) scale(0.9) translate(-200 -200)"><path fill="{TERRA}" d="{body_d}"/>'
             + halo + heavy + "</g>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="52 52 296 296" role="img" aria-label="{TITLE}">'
            f'<title>{TITLE}</title>{inner}</svg>\n')


def header_seal(body_d: str, panel_d: str) -> str:
    """Seal for the header (v5.1 review: G1A was illegible at ~44 px): no ring text, so the figure and a heavier G1A
    fill the ring. Sage ring r 150, terracotta ring r 138, light disc behind; drawn in the same 400-unit box."""
    letters = g1a(weight=600)
    heavy = letters.replace(f'fill="{SAGE}"', f'fill="{SAGE}" stroke="{SAGE}" stroke-width="3" stroke-linejoin="round"')
    return (DEFS + '<circle cx="200" cy="200" r="150" fill="#F3E7CF" stroke="' + SAGE + '" stroke-width="10"/>'
            + circle(137.5, TERRA, 2.4)
            + f'<g transform="translate(200 {200 + FIG_DY - 4}) scale(1.04) translate(-200 -200)">'
            + figure_svg(body_d, panel_d) + heavy + "</g>")


def header_lockup(body_d: str, panel_d: str) -> str:
    """logo-header.svg: header seal + two-line name ("Jeevana" / "Yoga & Wellness"), compact enough for a 390 px
    phone header at 48 px tall. The seal is the left 312 x 312 square, so CSS can crop to it on very narrow screens."""
    s1, s2 = 150, 80
    _, w1 = line("Jeevana", 500, s1, 0, 0)
    _, w2 = line("Yoga & Wellness", 500, s2, 0, 0, 0.02)
    x0 = 312 + 30  # in the 312-unit frame (seal centre 156,156); x-heights sit either side of the centre
    d1, _ = line("Jeevana", 500, s1, x0, 152)
    d2, _ = line("Yoga & Wellness", 500, s2, x0 + 4, 242, 0.02)
    W = x0 + max(w1, w2 + 4) + 8
    body = (f'<g transform="translate(-44 -44)">{header_seal(body_d, panel_d)}</g>'
            f'<path fill="{INK}" d="{d1}"/><path fill="{INK}" d="{d2}"/>')
    return svg(W, 312, body)


def build() -> None:
    import cairosvg

    BRAND.mkdir(parents=True, exist_ok=True)
    body, panel = figure_masks()
    body_d, panel_d = trace(body), trace(panel, 1.25)
    S = seal(body_d, panel_d)

    (BRAND / "mark.svg").write_text(svg(400, 400, S), encoding="utf-8")
    (BRAND / "logo-header.svg").write_text(header_lockup(body_d, panel_d), encoding="utf-8")

    # horizontal lockup: seal, then "Jeevana Yoga & Wellness" with the x-height centred on the seal
    name = "Jeevana Yoga & Wellness"
    size = 145
    _, tw = line(name, 500, size, 0, 0)
    gap = 34
    W = 400 + gap + tw + 6
    d, _ = line(name, 500, size, 400 + gap, 200 + 0.625 * size / 2)
    (BRAND / "logo.svg").write_text(svg(W, 400, S + f'<path fill="{INK}" d="{d}"/>'), encoding="utf-8")

    # stacked lockup: seal above the name
    size = 64
    _, tw = line(name, 500, size, 0, 0)
    W = max(400, tw) + 12
    H = 400 + 36 + 0.924 * size
    d, _ = line(name, 500, size, (W - tw) / 2, 400 + 36 + 0.625 * size)
    (BRAND / "logo-stacked.svg").write_text(
        svg(W, H, f'<g transform="translate({(W - 400) / 2:.1f} 0)">{S}</g><path fill="{INK}" d="{d}"/>'), encoding="utf-8")

    fav = favicon(body_d)
    (BRAND / "favicon.svg").write_text(fav, encoding="utf-8")
    png(fav, BRAND / "favicon-32.png", 32)
    png(fav, BRAND / "favicon-16.png", 16)

    def icon(fill: float) -> str:  # seal spans `fill` of the tile
        side = 400 / fill
        o = (side - 400) / 2
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side:.1f} {side:.1f}">'
                f'<rect width="{side:.1f}" height="{side:.1f}" fill="{PAPER}"/><g transform="translate({o:.1f} {o:.1f})">{S}</g></svg>')

    png(icon(0.88), BRAND / "apple-touch-icon.png", 180)
    png(icon(0.78), BRAND / "icon-512.png", 512)  # inside the 80 % maskable safe zone

    # og.jpg 1200x630: seal + name on parchment at left, the sun photo at right
    og = Image.new("RGB", (1200, 630), PAPER)
    sun = Image.open(PHOTOS / "sun@1400.webp").convert("RGB")
    pw = 560
    ph = round(sun.height * pw / sun.width)
    sun = sun.resize((pw, ph), Image.LANCZOS)
    top = max(0, min(ph - 630, round(ph * 0.04)))
    og.paste(sun.crop((0, top, pw, top + 630)), (1200 - pw, 0))
    st = (BRAND / "logo-stacked.svg").read_text(encoding="utf-8")
    lw = 470
    logo = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=st.encode(), output_width=lw))).convert("RGBA")
    og.paste(logo, ((1200 - pw - lw) // 2, (630 - logo.height) // 2), logo)
    og.save(BRAND / "og.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print("brand written:", sorted(p.name for p in BRAND.iterdir()))


if __name__ == "__main__":
    build()
