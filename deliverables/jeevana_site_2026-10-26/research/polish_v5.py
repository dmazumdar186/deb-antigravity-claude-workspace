"""polish_v5.py: clean, upscale and grade the four v5 Instagram screenshots.

Brief: research/brief_v5.md, section "Photos".
  python3 research/polish_v5.py --models /tmp/jvmodels [--work /tmp/jv]

Pipeline per photo:
  1. crop out every Instagram UI element (arrows, carousel dots, avatar, partial circles);
  2. super-resolve on CPU with ONNX models (Real-ESRGAN x4plus, RealPLKSR x2 from Hugging Face);
     the GAN output is blended with a Lanczos upscale of the same crop so skin keeps its texture;
     falls back to Lanczos 2x + unsharp + mild denoise when no model is available;
  3. gentle grade toward the parchment palette (warm, soft, lifted blacks, not orange);
  4. WebP q84 at 800/1400/2000 (+2400 for sun), manifest entries in the existing shape.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "_raw_assets" / "v5"
OUT = ROOT / "site" / "assets" / "photos"

# crop boxes (left, top, right, bottom) in source pixels; chosen by eye from zoomed crops
PHOTOS = {
    "sun": {
        "file": "sun.png",
        # "<" arrow spans x 12-36 (y 417-441); carousel dots at y >= 834; 1 px dark border at x 0
        "box": (43, 12, 643, 812),
        "widths": [800, 1400, 2000, 2400],
        "alt_en": "Jeevana against a sunlit grey wall, eyes closed and face turned to the sun, arms folded, in a black dress, her hair lifting in the wind.",
        "alt_fr": "Jeevana contre un mur gris baigné de soleil, les yeux fermés, le visage tourné vers le soleil, les bras croisés, en robe noire, les cheveux soulevés par le vent.",
    },
    "diwali": {
        "file": "diwali.webp",
        # '>' arrow spans x 610-634, y 413-437
        "box": (0, 8, 603, 812),
        "widths": [800, 1400, 2000],
        "alt_en": "Jeevana in a blue saree, sitting on the floor and lighting a diya beside a marigold rangoli for Diwali.",
        "alt_fr": "Jeevana en saree bleu, assise par terre, allume une diya près d'une rangoli de soucis pour Diwali.",
    },
    "saree-eiffel": {
        "file": "saree-eiffel.png",
        # avatar circle x 12-40, y 815-843; partial circle on the right edge x >= 625, y 445-505
        "box": (46, 76, 620, 842),
        "widths": [800, 1400, 2000],
        "alt_en": "Jeevana in a deep red saree with a gold border, smiling in front of the Eiffel Tower in Paris.",
        "alt_fr": "Jeevana en saree rouge profond bordé d'or, souriante devant la tour Eiffel à Paris.",
    },
    "lobby": {
        "file": "lobby.webp",
        # no UI found; trim a 2 px edge to drop resampling fringes
        "box": (2, 2, 479, 781),
        "widths": [800, 1400, 1800],
        "alt_en": "Jeevana in a green and gold lehenga with a yellow dupatta, standing before white orchids in a hotel lobby.",
        "alt_fr": "Jeevana en lehenga vert et or avec un dupatta jaune, debout devant des orchidées blanches dans le hall d'un hôtel.",
    },
}


# ---------------------------------------------------------------- super-resolution
def _tiled(sess, img: np.ndarray, tile: int, scale: int, pad: int) -> np.ndarray:
    """Run a fixed-shape SR model over img (H,W,3 float 0-1) with overlapping tiles."""
    h, w, _ = img.shape
    core = tile - 2 * pad
    ph = (-(h) % core)
    pw = (-(w) % core)
    src = np.pad(img, ((pad, pad + ph), (pad, pad + pw), (0, 0)), mode="reflect")
    out = np.zeros(((h + ph) * scale, (w + pw) * scale, 3), np.float32)
    name = sess.get_inputs()[0].name
    for y in range(0, h + ph, core):
        for x in range(0, w + pw, core):
            t = src[y:y + tile, x:x + tile]
            if t.shape[0] < tile or t.shape[1] < tile:
                t = np.pad(t, ((0, tile - t.shape[0]), (0, tile - t.shape[1]), (0, 0)), mode="reflect")
            r = sess.run(None, {name: t.transpose(2, 0, 1)[None].astype(np.float32)})[0][0].transpose(1, 2, 0)
            s = pad * scale
            out[y * scale:(y + core) * scale, x * scale:(x + core) * scale] = r[s:s + core * scale, s:s + core * scale]
    return np.clip(out[:h * scale, :w * scale], 0, 1)


def sr(im: Image.Image, models: Path, kind: str) -> Image.Image | None:
    try:
        import onnxruntime as ort
    except ImportError:
        return None
    spec = {"esrgan": ("realesrgan_x4.onnx", 64, 4, 8), "plksr": ("realplksr_x2.onnx", 512, 2, 24)}[kind]
    f = models / spec[0]
    if not f.exists():
        return None
    sess = ort.InferenceSession(str(f), providers=["CPUExecutionProvider"])
    a = np.asarray(im.convert("RGB"), np.float32) / 255.0
    r = _tiled(sess, a, spec[1], spec[2], spec[3])
    return Image.fromarray((r * 255 + 0.5).astype(np.uint8))


def lanczos_fallback(im: Image.Image, scale: int = 2) -> Image.Image:
    up = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    up = up.filter(ImageFilter.UnsharpMask(radius=1.0, percent=50, threshold=2))
    return Image.blend(up, up.filter(ImageFilter.GaussianBlur(0.6)), 0.25)


def upscale(im: Image.Image, models: Path, work: Path, key: str) -> tuple[Image.Image, str]:
    tag = f"{key}_{im.width}x{im.height}"  # cache keyed on the crop size
    cache = work / f"{tag}_esrgan.png"
    g = Image.open(cache) if cache.exists() else sr(im, models, "esrgan")
    if g is None:
        return lanczos_fallback(im), "lanczos2x"
    g.save(cache)
    w, h = g.size
    # second opinion: RealPLKSR x2 (fidelity-trained, no GAN texture) then Lanczos to 4x
    cache2 = work / f"{tag}_plksr.png"
    p = Image.open(cache2) if cache2.exists() else sr(im, models, "plksr")
    if p is not None:
        p.save(cache2)
        base = p.resize((w, h), Image.LANCZOS)
        method = "realesrgan_x4plus+realplksr_x2 blend"
    else:
        base = im.resize((w, h), Image.LANCZOS)
        method = "realesrgan_x4plus+lanczos blend"
    # GAN gives crisp edges but waxy skin; the fidelity base keeps grain and facial detail honest
    out = Image.blend(base.convert("RGB"), g.convert("RGB"), 0.55)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
    return out, method


# ---------------------------------------------------------------- grade
def grade(im: Image.Image) -> Image.Image:
    """Warm, soft, parchment-leaning; never orange. Lift blacks toward ink #2B1E14, ease highlights."""
    a = np.asarray(im.convert("RGB"), np.float32) / 255.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    # gentle warm balance: +R, -B, scaled by midtone weight
    mid = 4 * lum * (1 - lum)
    a[..., 0] += 0.018 * mid
    a[..., 1] += 0.006 * mid
    a[..., 2] -= 0.022 * mid
    # soft toe: blacks lift slightly toward warm ink
    ink = np.array([0x2B, 0x1E, 0x14], np.float32) / 255.0
    sh = np.clip(1 - lum / 0.35, 0, 1)[..., None] ** 2
    a = a * (1 - 0.22 * sh) + ink * 0.22 * sh
    # soft shoulder: highlights toward parchment #EAD9B8 just a touch
    paper = np.array([0xEA, 0xD9, 0xB8], np.float32) / 255.0
    hi = np.clip((lum - 0.75) / 0.25, 0, 1)[..., None] ** 2
    a = a * (1 - 0.12 * hi) + paper * 0.12 * hi
    # slight desaturation (soft, not orange)
    lum2 = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    a = lum2 + (a - lum2) * 0.94
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def lqip(im: Image.Image) -> str:
    t = im.copy()
    t.thumbnail((24, 24), Image.LANCZOS)
    b = io.BytesIO()
    t.save(b, "WEBP", quality=40)
    return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()


# ---------------------------------------------------------------- brand (Concept 3)
BRAND = ROOT / "site" / "assets" / "brand"
FONT = ROOT / "site" / "assets" / "fonts" / "cormorant-garamond-latin-500-normal.woff2"
INK, SAGE, GOLD, PAPER = "#2B1E14", "#6E7F5E", "#B8862B", "#EAD9B8"
C3_BOX = (1450, 260, 1800, 510)  # Concept 3 in logo-concepts.jpg (2000x1116)
# letter regions in the x4 crop (1400x1000): G, A, and the "Concept 3" label digit
G_BOX, A_BOX, LABEL_BOX = (290, 410, 680, 790), (990, 490, 1350, 905), (0, 0, 60, 260)


def _inside(st_row, box) -> bool:
    x, y, w, h = st_row[:4]
    return x >= box[0] and y >= box[1] and x + w <= box[2] and y + h <= box[3]


def _clean(m: np.ndarray, close: int = 5, sigma: float = 1.6, min_area: int = 150) -> np.ndarray:
    import cv2

    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close, close)))
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), sigma) > 0.5
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, 4] >= min_area
    return keep[lab]


def concept3_layers(models: Path, work: Path) -> dict[str, np.ndarray]:
    import cv2

    cache = work / "c3_x4.png"
    if cache.exists():
        up = Image.open(cache).convert("RGB")
    else:
        crop = Image.open(RAW / "logo-concepts.jpg").convert("RGB").crop(C3_BOX)
        up = sr(crop, models, "esrgan") or crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
        up.save(cache)
    a = np.asarray(up).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = (r * 299 + g * 587 + b * 114) // 1000
    sat = a.max(-1) - a.min(-1)
    dark = lum < 120
    sage = (~dark) & (lum < 215) & (g >= r - 4) & (g > b) & (sat < 60)
    gold = (~dark) & (r > g) & (g > b) & (r - b > 45) & (lum < 220)

    n, lab, st, _ = cv2.connectedComponentsWithStats(dark.astype(np.uint8), 8)
    is_g = np.array([i > 0 and _inside(st[i], G_BOX) for i in range(n)])
    is_a = np.array([i > 0 and _inside(st[i], A_BOX) for i in range(n)])
    is_lbl = np.array([i > 0 and _inside(st[i], LABEL_BOX) for i in range(n)])
    figure = dark & ~(is_g | is_a | is_lbl)[lab]
    letter_g, letter_a = is_g[lab], is_a[lab]
    # the A was painted over the sage sweep: fill the sage back in where the A covered it
    a_zone = cv2.dilate(letter_a.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    closed = cv2.morphologyEx(sage.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))) > 0
    sage_full = sage | (closed & a_zone)
    n, lab, st, cen = cv2.connectedComponentsWithStats(gold.astype(np.uint8), 8)
    big = max(range(1, n), key=lambda i: st[i, 4] if cen[i][0] > 1000 and cen[i][1] < 400 else -1)
    moon = lab == big
    one = gold & ~moon
    return {
        "figure": _clean(figure),
        "sage": _clean(sage_full, close=9, sigma=2.2, min_area=400),
        "moon": _clean(moon, close=7, sigma=2.0, min_area=400),
        "g": _clean(letter_g),
        "a": _clean(letter_a),
        "one": _clean(one, min_area=300),
    }


def trace(mask: np.ndarray, scale: float, ox: float, oy: float, alphamax: float = 1.1) -> str:
    import potrace

    # potracer treats True as paper, so the ink mask is inverted
    plist = potrace.Bitmap(~mask).trace(turdsize=60, alphamax=alphamax, opticurve=True, opttolerance=0.4)

    def f(pt) -> str:
        return f"{(pt.x - ox) * scale:.1f} {(pt.y - oy) * scale:.1f}"

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


def bbox(*masks: np.ndarray, pad: int = 24) -> tuple[int, int, int, int]:
    m = np.logical_or.reduce(masks)
    ys, xs = np.nonzero(m)
    return xs.min() - pad, ys.min() - pad, xs.max() + pad, ys.max() + pad


def text_path(text: str, size: float, x0: float, baseline: float, tracking: float = 0.16) -> tuple[str, float, float]:
    """Outline `text` in Cormorant Garamond 500; returns (path d, advance width, cap height)."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    font = TTFont(str(FONT))
    upm = font["head"].unitsPerEm
    cmap, gs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    cap = getattr(font["OS/2"], "sCapHeight", 0) or 630
    kern = {("V", "A"): -70, ("A", "V"): -70, ("Y", "O"): -40, ("G", "A"): -15, ("E", "V"): -20}
    s = size / upm
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}")
    x = x0
    prev = None
    for ch in text:
        if ch == " ":
            x += (hmtx["space"][0] * 1.4 + tracking * upm) * s
            prev = None
            continue
        if prev and (prev, ch) in kern:
            x += kern[(prev, ch)] * s
        gn = cmap[ord(ch)]
        gs[gn].draw(TransformPen(pen, (s, 0, 0, -s, x, baseline)))
        x += (hmtx[gn][0] + tracking * upm) * s
        prev = ch
    width = x - x0 - tracking * upm * s
    return pen.getCommands(), width, cap * s


def _svg(w: float, h: float, body: str, title: str = "Jeevana Yoga", bg: str | None = None) -> str:
    rect = f'<rect width="{w:.0f}" height="{h:.0f}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{rect}{body}</svg>\n')


def mark_group(L: dict[str, np.ndarray], box, scale: float, dx: float = 0, dy: float = 0) -> str:
    """Concept 3 as drawn: sage sweep under the ink figure, gold moon, brush "G1A" ("Jeevana" ~ G-1-A)."""
    ox, oy = box[0], box[1]
    tr = f' transform="translate({dx:.1f} {dy:.1f})"' if (dx or dy) else ""
    return (f'<g{tr}><path fill="{SAGE}" d="{trace(L["sage"], scale, ox, oy, 1.2)}"/>'
            f'<path fill="{INK}" d="{trace(L["figure"] | L["g"] | L["a"], scale, ox, oy)}"/>'
            f'<path fill="{GOLD}" d="{trace(L["moon"], scale, ox, oy, 1.3)}"/>'
            f'<path fill="{GOLD}" d="{trace(L["one"], scale, ox, oy)}"/></g>')


def favicon_layers(L: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Brush "G1A" alone, letters pulled together and thickened so it reads at 16 px.

    The full figure turns to mush below 32 px (checked by eye), so the favicon keeps only the letters.
    """
    import cv2

    def fat(m: np.ndarray, r: int) -> np.ndarray:
        return cv2.dilate(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r))) > 0

    def largest(m: np.ndarray) -> np.ndarray:
        n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
        return lab == (1 + int(np.argmax(st[1:, 4])))

    parts = [("g", fat(L["g"], 25)), ("one", fat(largest(L["one"]), 25)), ("a", fat(L["a"], 25))]
    H, W = L["g"].shape
    out = {k: np.zeros((H, W * 2), bool) for k, _ in parts}
    x = 40
    for k, m in parts:
        ys, xs = np.nonzero(m)
        sub = m[:, xs.min():xs.max() + 1]
        out[k][:, x:x + sub.shape[1]] = sub
        x += sub.shape[1] + 18
    # the concept's A has no bar of its own: the sage sweep crosses it. Keep that crossing as a short
    # rising sage stroke so the A does not read as a lambda at 16 px.
    ys, xs = np.nonzero(out["a"])
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    h = y1 - y0
    bar = np.zeros_like(out["a"], np.uint8)
    cv2.line(bar, (int(x0 - 6), int(y0 + 0.78 * h)), (int(x1 + 4), int(y0 + 0.52 * h)), 1, 46, cv2.LINE_AA)
    return {"sage": _clean(bar > 0, 5, 2.0, 500), "g": _clean(out["g"], 9, 2.5, 2000),
            "one": _clean(out["one"], 9, 2.5, 2000), "a": _clean(out["a"], 9, 2.5, 2000)}


def g1a_group(F: dict[str, np.ndarray], box, scale: float) -> str:
    ox, oy = box[0], box[1]
    return (f'<path fill="{SAGE}" d="{trace(F["sage"], scale, ox, oy)}"/>'
            f'<path fill="{INK}" d="{trace(F["g"] | F["a"], scale, ox, oy)}"/>'
            f'<path fill="{GOLD}" d="{trace(F["one"], scale, ox, oy)}"/>')


def png(svg: str, out: Path, size: int) -> None:
    import cairosvg

    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out), output_width=size, output_height=size)


def build_brand(models: Path, work: Path) -> None:
    BRAND.mkdir(parents=True, exist_ok=True)
    L = concept3_layers(models, work)
    box = bbox(L["figure"], L["sage"], L["moon"], L["g"], L["a"], L["one"])
    S = 0.25  # x4 crop px -> svg units (1:1 with the 2000 px concept sheet)
    mw, mh = (box[2] - box[0]) * S, (box[3] - box[1]) * S

    (BRAND / "mark.svg").write_text(_svg(mw, mh, mark_group(L, box, S)), encoding="utf-8")

    # horizontal lockup: mark, then the wordmark with caps centred on the mark
    size = mh * 0.25
    _, tw, cap = text_path("JEEVANA YOGA", size, 0, 0)
    gap = mh * 0.10
    W, H = mw + gap + tw + 8, mh
    d, _, _ = text_path("JEEVANA YOGA", size, mw + gap, H * 0.60 + cap / 2)  # caps centred on the G1A letters, not the whole mark
    (BRAND / "logo.svg").write_text(_svg(W, H, mark_group(L, box, S) + f'<path fill="{INK}" d="{d}"/>'), encoding="utf-8")

    # stacked lockup
    size = mw * 0.135
    _, tw, cap = text_path("JEEVANA YOGA", size, 0, 0)
    W = max(mw, tw) + 16
    H = mh + cap * 1.0 + cap + cap * 0.45
    d, _, _ = text_path("JEEVANA YOGA", size, (W - tw) / 2, mh + cap * 1.0 + cap)
    (BRAND / "logo-stacked.svg").write_text(
        _svg(W, H, mark_group(L, box, S, dx=(W - mw) / 2) + f'<path fill="{INK}" d="{d}"/>'), encoding="utf-8")

    # favicon: thickened mark, centred in a square
    F = favicon_layers(L)
    fb = bbox(*F.values(), pad=6)
    fw, fh = (fb[2] - fb[0]) * S, (fb[3] - fb[1]) * S
    side = max(fw, fh)
    fav = f'<g transform="translate({(side - fw) / 2:.1f} {(side - fh) / 2:.1f})">{g1a_group(F, fb, S)}</g>'
    # parchment tile so the ink reads on dark browser chrome too
    fav_bg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side:.0f} {side:.0f}" role="img" aria-label="Jeevana Yoga">'
              f'<title>Jeevana Yoga</title><rect width="{side:.0f}" height="{side:.0f}" rx="{side * 0.18:.0f}" fill="{PAPER}"/>'
              f'<g transform="translate({side * 0.08:.1f} {side * 0.08:.1f}) scale(0.84)">{fav}</g></svg>\n')
    (BRAND / "favicon.svg").write_text(fav_bg, encoding="utf-8")
    png(fav_bg, BRAND / "favicon-32.png", 32)
    png(fav_bg, BRAND / "favicon-16.png", 16)

    # app icons on parchment, full-bleed square (iOS rounds the corners itself)
    def icon(fill: float) -> str:  # mark spans `fill` of the tile width
        side2 = max(mw, mh) / fill
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side2:.0f} {side2:.0f}">'
                f'<rect width="{side2:.0f}" height="{side2:.0f}" fill="{PAPER}"/>'
                + mark_group(L, box, S, dx=(side2 - mw) / 2, dy=(side2 - mh) / 2) + "</svg>")

    png(icon(0.86), BRAND / "apple-touch-icon.png", 180)
    png(icon(0.74), BRAND / "icon-512.png", 512)  # inside the 80 % maskable safe zone

    # og.jpg 1200x630: stacked logo on parchment at left, the sun photo at right
    import cairosvg

    og = Image.new("RGB", (1200, 630), PAPER)
    sun = Image.open(OUT / "sun@1400.webp").convert("RGB")
    pw = 560
    ph = round(sun.height * pw / sun.width)
    sun = sun.resize((pw, ph), Image.LANCZOS).crop((0, 30, pw, 660))
    og.paste(sun, (1200 - pw, 0))
    st = (BRAND / "logo-stacked.svg").read_text(encoding="utf-8")
    lw = 440
    logo = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=st.encode(), output_width=lw))).convert("RGBA")
    og.paste(logo, ((1200 - pw - lw) // 2, (630 - logo.height) // 2), logo)
    og.save(BRAND / "og.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print("brand written:", sorted(p.name for p in BRAND.iterdir()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, default=Path("/tmp/jvmodels"))
    ap.add_argument("--work", type=Path, default=Path("/tmp/jv"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--part", choices=["photos", "brand", "all"], default="all")
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.part in ("photos", "all"):
        photos(args)
    if args.part in ("brand", "all"):
        build_brand(args.models, args.work)


def photos(args: argparse.Namespace) -> None:
    man_path = OUT / "manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    for key, spec in PHOTOS.items():
        if args.only and key not in args.only:
            continue
        src = Image.open(RAW / spec["file"]).convert("RGB").crop(spec["box"])
        src.save(args.work / f"{key}_crop.png")
        up, method = upscale(src, args.models, args.work, key)
        up = grade(up)
        cap = up.width if "lanczos" not in method else src.width * 2
        widths = [w for w in spec["widths"] if w <= cap]
        srcset = []
        for w in widths:
            h = round(up.height * w / up.width)
            f = f"{key}@{w}.webp"
            up.resize((w, h), Image.LANCZOS).save(OUT / f, "WEBP", quality=84, method=6)
            srcset.append([f, w, h])
        W, H = srcset[-1][1], srcset[-1][2]
        manifest[key] = {
            "widths": widths,
            "ratio": f"{spec['box'][2] - spec['box'][0]}/{spec['box'][3] - spec['box'][1]}",
            "w": W,
            "h": H,
            "srcset": srcset,
            "lqip": lqip(up),
            "alt_en": spec["alt_en"],
            "alt_fr": spec["alt_fr"],
            "upscale": method,
        }
        print(key, method, src.size, "->", up.size, widths)
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
