#!/usr/bin/env python3
"""
wedding_card_generator.py
description: Generate a Karnataka Royal Heritage wedding invitation card PDF (Sowjanya & Ruturaj)
inputs: No CLI args — names and event details are hardcoded in the script
outputs: output/wedding_card_sowjanya_ruturaj.pdf (or similar in output/)
"""

import math
import requests
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE   = Path(__file__).parent.parent.parent
ASSETS = BASE / "assets"
OUTPUT = BASE / "output"
FONTS  = BASE / ".tmp" / "fonts"
for d in [ASSETS, OUTPUT, FONTS]:
    d.mkdir(parents=True, exist_ok=True)

PDF_OUT = str(OUTPUT / "wedding_card_sowjanya_ruturaj.pdf")

# ─── Colors ───────────────────────────────────────────────────────────────────
GOLD      = HexColor("#C8860A")
DEEP_GOLD = HexColor("#D4AF37")
IVORY     = HexColor("#FFF8E7")
BROWN     = HexColor("#2C1A0E")
MAROON    = HexColor("#7B1818")
GREEN     = HexColor("#2A5C27")
SAFFRON   = HexColor("#E8730A")
STONE     = HexColor("#8B7040")
LT_GOLD   = HexColor("#E8C46A")
CREAM     = HexColor("#F5EDD5")

# ─── Fonts ────────────────────────────────────────────────────────────────────
FONT_SOURCES = {
    "Cormorant-Regular":
        "https://github.com/CatharsisFonts/Cormorant/raw/refs/heads/master/fonts/ttf/Cormorant-Regular.ttf",
    "Cormorant-Bold":
        "https://github.com/CatharsisFonts/Cormorant/raw/refs/heads/master/fonts/ttf/Cormorant-Bold.ttf",
    "Cormorant-Italic":
        "https://github.com/CatharsisFonts/Cormorant/raw/refs/heads/master/fonts/ttf/Cormorant-Italic.ttf",
    "Cormorant-BoldItalic":
        "https://github.com/CatharsisFonts/Cormorant/raw/refs/heads/master/fonts/ttf/Cormorant-BoldItalic.ttf",
}

def setup_fonts():
    for name, url in FONT_SOURCES.items():
        path = FONTS / f"{name}.ttf"
        if not path.exists():
            print(f"Downloading {name}...")
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            path.write_bytes(r.content)
        pdfmetrics.registerFont(TTFont(name, str(path)))
    # Register font families
    pdfmetrics.registerFontFamily(
        "Cormorant",
        normal="Cormorant-Regular",
        bold="Cormorant-Bold",
        italic="Cormorant-Italic",
        boldItalic="Cormorant-BoldItalic",
    )
    print("Fonts ready.")

# ─── Asset Preprocessing ──────────────────────────────────────────────────────

def crop_swami_portraits():
    """Crop the combined Swami image into two individual portraits."""
    src = ASSETS / "extracted_p2_img4.png"
    out1 = ASSETS / "swami1.png"
    out2 = ASSETS / "swami2.png"

    img = Image.open(src).convert("RGB")
    w, h = img.size  # 316 x 473

    # The combined image has thumbnail strips on left/right edges (~18% each side).
    # Crop horizontally to the center ~64% to get the main face areas.
    mx = int(w * 0.18)
    mid = h // 2
    # Top half = Swami 1 (glasses, rudraksha beads); bottom = Swami 2 (red turban)
    swami1 = img.crop((mx, 0, w - mx, mid + 25))
    swami2 = img.crop((mx, mid - 25, w - mx, h))

    for out, sw in [(out1, swami1), (out2, swami2)]:
        # Sharpen and enhance
        sw = sw.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3))
        sw = ImageEnhance.Contrast(sw).enhance(1.2)
        sw = ImageEnhance.Sharpness(sw).enhance(1.5)
        # Upscale 2x with LANCZOS for crispness
        sw = sw.resize((sw.width * 2, sw.height * 2), Image.LANCZOS)
        sw.save(out, dpi=(300, 300))
    print("Swami portraits cropped and sharpened.")
    return out1, out2


def make_circular_photo(img_path, size_px=400):
    """Return a PIL Image: circular crop of the photo on transparent background."""
    img = Image.open(img_path).convert("RGBA")
    # Center-crop to square
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top  = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((size_px, size_px), Image.LANCZOS)
    # Make circular mask
    mask = Image.new("L", (size_px, size_px), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size_px, size_px), fill=255)
    result = Image.new("RGBA", (size_px, size_px), (0, 0, 0, 0))
    result.paste(img, (0, 0))
    result.putalpha(mask)
    return result


def recolor_silhouette(img_path, fill_color=(123, 24, 24), bg_color=(255, 248, 231)):
    """Recolor a black-on-white silhouette to maroon-on-ivory."""
    img = Image.open(img_path).convert("RGBA")
    data = img.getdata()
    new_data = []
    for px in data:
        r, g, b, a = px
        brightness = (r + g + b) / 3
        if brightness < 128:  # dark pixel = silhouette
            new_data.append((*fill_color, 255))
        else:
            new_data.append((*bg_color, 0))  # transparent background
    img.putdata(new_data)
    return img


def pil_to_reader(pil_img):
    """Convert PIL image to ReportLab ImageReader."""
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)

# ─── Drawing Utilities ────────────────────────────────────────────────────────

def draw_hoysala_star(c, cx, cy, r_outer, r_inner=None, n=16, color=None):
    """Draw an n-pointed Hoysala stellate star."""
    if r_inner is None:
        r_inner = r_outer * 0.45
    if color:
        c.setFillColor(color)
    points = []
    for i in range(n * 2):
        angle = math.pi / n * i - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        points.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])
    p = c.beginPath()
    p.moveTo(points[0], points[1])
    for i in range(2, len(points), 2):
        p.lineTo(points[i], points[i+1])
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def draw_lotus_petal_ring(c, cx, cy, r_frame, n_petals=8, color=None):
    """Draw n lotus petals radiating outward from center — used for Swami frames."""
    if color:
        c.setFillColor(color)
    petal_len = r_frame * 0.55
    petal_w   = r_frame * 0.28
    for i in range(n_petals):
        angle = 2 * math.pi / n_petals * i - math.pi / 2
        px = cx + r_frame * math.cos(angle)
        py = cy + r_frame * math.sin(angle)
        c.saveState()
        c.translate(px, py)
        c.rotate(math.degrees(angle) + 90)
        p = c.beginPath()
        p.moveTo(0, 0)
        p.curveTo(-petal_w, petal_len * 0.4, -petal_w * 0.5, petal_len * 0.85, 0, petal_len)
        p.curveTo(petal_w * 0.5, petal_len * 0.85, petal_w, petal_len * 0.4, 0, 0)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.restoreState()


def draw_swami_frame(c, cx, cy, radius, img_path):
    """Draw circular photo with ornate gold lotus-petal frame."""
    # Outer petal ring (large petals)
    c.setFillColor(DEEP_GOLD)
    draw_lotus_petal_ring(c, cx, cy, radius + 4*mm, n_petals=12, color=DEEP_GOLD)
    # Gold ring
    c.setStrokeColor(GOLD)
    c.setFillColor(GOLD)
    c.setLineWidth(2)
    c.circle(cx, cy, radius + 1.5*mm, fill=0, stroke=1)
    # Maroon inner ring
    c.setStrokeColor(MAROON)
    c.setLineWidth(1)
    c.circle(cx, cy, radius, fill=0, stroke=1)
    # Photo
    circ = make_circular_photo(img_path, size_px=500)
    ir = pil_to_reader(circ)
    d = radius * 2
    c.drawImage(ir, cx - radius, cy - radius, width=d, height=d, mask="auto")


def draw_leaf(c, cx, cy, length, width, angle_deg, color):
    """Draw a single leaf shape at given center, angle."""
    c.setFillColor(color)
    c.saveState()
    c.translate(cx, cy)
    c.rotate(angle_deg)
    p = c.beginPath()
    p.moveTo(0, -length / 2)
    p.curveTo(-width, 0, -width, 0, 0, length / 2)
    p.curveTo(width, 0, width, 0, 0, -length / 2)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def draw_torana(c, page_w, page_h, margin):
    """Draw a mango-leaf torana arch across the top of the page."""
    arch_h   = 22 * mm
    arch_y   = page_h - margin - arch_h
    leaf_l   = 10 * mm
    leaf_w   = 3.2 * mm
    n_leaves = 22
    usable_w = page_w - 2 * margin

    # Arch spine (gold curved line)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    p = c.beginPath()
    p.moveTo(margin, arch_y + arch_h * 0.25)
    p.curveTo(
        margin + usable_w * 0.15, arch_y + arch_h,
        margin + usable_w * 0.85, arch_y + arch_h,
        margin + usable_w, arch_y + arch_h * 0.25,
    )
    c.drawPath(p, stroke=1, fill=0)

    # Leaves hung from arch
    for i in range(n_leaves):
        t = i / (n_leaves - 1)
        # Position on arch (parametric)
        lx = margin + usable_w * t
        # Height of arch at this t (parabola approximation)
        ly = arch_y + arch_h * 0.25 + arch_h * 0.75 * 4 * t * (1 - t)
        angle = -90 + (t - 0.5) * 40  # tilt leaves outward at edges
        color = GREEN if i % 2 == 0 else HexColor("#3A7A35")
        draw_leaf(c, lx, ly - leaf_l * 0.35, leaf_l, leaf_w, angle, color)
        # Marigold dot between some leaves
        if i % 3 == 1:
            c.setFillColor(SAFFRON)
            c.circle(lx, ly - leaf_l * 0.1, 1.8 * mm, fill=1, stroke=0)


def draw_lotus_divider(c, x, y, width, n=3):
    """Draw n lotus blooms as a horizontal divider."""
    spacing = width / (n + 1)
    petal_r  = 3.2 * mm
    for i in range(n):
        cx = x + spacing * (i + 1)
        # Petals
        c.setFillColor(HexColor("#D4705A"))
        for j in range(8):
            angle = 2 * math.pi / 8 * j
            px = cx + (petal_r * 1.45) * math.cos(angle)
            py = y + (petal_r * 1.45) * math.sin(angle)
            draw_leaf(c, px, py, petal_r * 1.3, petal_r * 0.55,
                      math.degrees(angle) + 90, HexColor("#D4705A"))
        # Centre
        c.setFillColor(GOLD)
        c.circle(cx, y, petal_r * 0.45, fill=1, stroke=0)
    # Thin gold rules either side
    total_w = spacing * (n + 1)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.6)
    pad = 6 * mm
    c.line(x, y, x + spacing - petal_r * 2 - pad, y)
    c.line(x + total_w - spacing + petal_r * 2 + pad, y, x + total_w, y)


def draw_kalasha(c, cx, cy, scale=1.0):
    """Draw a Purna Kalasha (sacred pot) with mango leaves and coconut."""
    s = scale
    # Pot body (golden ellipse + trapezoid neck)
    pot_w = 18 * mm * s
    pot_h = 20 * mm * s
    neck_w = 9 * mm * s
    neck_h = 5 * mm * s
    base_w = 14 * mm * s
    base_h = 3 * mm * s

    c.setFillColor(DEEP_GOLD)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)

    # Base
    p = c.beginPath()
    p.moveTo(cx - base_w / 2, cy)
    p.lineTo(cx + base_w / 2, cy)
    p.lineTo(cx + neck_w / 2, cy + base_h)
    p.lineTo(cx - neck_w / 2, cy + base_h)
    p.close()
    c.drawPath(p, fill=1, stroke=1)

    # Pot ellipse (body)
    c.ellipse(cx - pot_w / 2, cy + base_h, cx + pot_w / 2, cy + base_h + pot_h, fill=1, stroke=1)

    # Neck
    neck_y = cy + base_h + pot_h
    p = c.beginPath()
    p.moveTo(cx - neck_w / 2, neck_y)
    p.lineTo(cx + neck_w / 2, neck_y)
    p.lineTo(cx + neck_w * 0.6, neck_y + neck_h)
    p.lineTo(cx - neck_w * 0.6, neck_y + neck_h)
    p.close()
    c.drawPath(p, fill=1, stroke=1)

    # Swastika on pot body
    c.setStrokeColor(MAROON)
    c.setLineWidth(1.2)
    sw_cx = cx
    sw_cy = cy + base_h + pot_h * 0.45
    sw_s  = 3.5 * mm * s
    # Horizontal bar
    c.line(sw_cx - sw_s, sw_cy, sw_cx + sw_s, sw_cy)
    # Vertical bar
    c.line(sw_cx, sw_cy - sw_s, sw_cx, sw_cy + sw_s)
    # Swastika arms
    for dx, dy, adx, ady in [(0, sw_s, sw_s * 0.55, 0),
                               (sw_s, 0, 0, -sw_s * 0.55),
                               (0, -sw_s, -sw_s * 0.55, 0),
                               (-sw_s, 0, 0, sw_s * 0.55)]:
        x1, y1 = sw_cx + dx, sw_cy + dy
        c.line(x1, y1, x1 + adx, y1 + ady)

    # Mango leaves fanning from neck
    leaf_base_y = neck_y + neck_h
    n_leaves = 5
    for i in range(n_leaves):
        t = (i - (n_leaves - 1) / 2) / max(n_leaves - 1, 1)
        angle = 90 + t * 70
        lx = cx + neck_w * 0.4 * t
        draw_leaf(c, lx, leaf_base_y + 4 * mm * s,
                  12 * mm * s, 3.5 * mm * s, angle, GREEN)

    # Coconut
    coconut_y = leaf_base_y + 13 * mm * s
    c.setFillColor(HexColor("#8B6340"))
    c.ellipse(cx - 5 * mm * s, coconut_y, cx + 5 * mm * s,
              coconut_y + 7 * mm * s, fill=1, stroke=0)
    c.setFillColor(HexColor("#C8956A"))
    c.ellipse(cx - 3.5 * mm * s, coconut_y + 1 * mm * s,
              cx + 3.5 * mm * s, coconut_y + 5 * mm * s, fill=1, stroke=0)


def draw_kolam_border(c, x, y, w, h, margin_in=5 * mm):
    """Draw a Hoysala-inspired border with double gold lines and corner stars."""
    # Outer gold rectangle
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.rect(x, y, w, h, fill=0, stroke=1)
    # Inner maroon rectangle
    c.setStrokeColor(MAROON)
    c.setLineWidth(0.8)
    c.rect(x + 3, y + 3, w - 6, h - 6, fill=0, stroke=1)
    # Inner gold thin
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.4)
    c.rect(x + margin_in, y + margin_in, w - 2 * margin_in, h - 2 * margin_in,
           fill=0, stroke=1)
    # Corner stars
    c.setFillColor(GOLD)
    for sx, sy in [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]:
        draw_hoysala_star(c, sx, sy, 6 * mm, n=8, color=GOLD)


def draw_event_box(c, x, y, w, h, title, lines, title_font, body_font):
    """Draw a framed event box with gold header and details."""
    # Background fill
    c.setFillColor(HexColor("#FDF5E0"))
    c.rect(x, y, w, h, fill=1, stroke=0)
    # Gold top border
    c.setFillColor(GOLD)
    c.rect(x, y + h - 9 * mm, w, 9 * mm, fill=1, stroke=0)
    # Outer border
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.rect(x, y, w, h, fill=0, stroke=1)
    c.setStrokeColor(MAROON)
    c.setLineWidth(0.5)
    c.rect(x + 1.5, y + 1.5, w - 3, h - 3, fill=0, stroke=1)

    # Title text (white on gold header)
    c.setFillColor(white)
    c.setFont(title_font, 10)
    tw = c.stringWidth(title, title_font, 10)
    c.drawString(x + (w - tw) / 2, y + h - 6.5 * mm, title)

    # Body lines
    c.setFillColor(BROWN)
    line_h = 5.2 * mm
    start_y = y + h - 9 * mm - 6.5 * mm
    for i, (label, value) in enumerate(lines):
        ty = start_y - i * line_h
        if label:
            c.setFont(title_font, 7.5)
            c.setFillColor(STONE)
            c.drawString(x + 4 * mm, ty, label)
        c.setFont(body_font, 9)
        c.setFillColor(BROWN)
        vw = c.stringWidth(value, body_font, 9)
        c.drawString(x + (w - vw) / 2, ty - 3.8 * mm, value)


def draw_ornate_rule(c, x, y, w):
    """A decorative gold horizontal rule with diamond center."""
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.0)
    c.line(x, y, x + w * 0.42, y)
    c.line(x + w * 0.58, y, x + w, y)
    # Diamond center
    c.setFillColor(GOLD)
    dm = 2.5 * mm
    p = c.beginPath()
    p.moveTo(x + w / 2, y + dm)
    p.lineTo(x + w / 2 + dm, y)
    p.lineTo(x + w / 2, y - dm)
    p.lineTo(x + w / 2 - dm, y)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def draw_trishoola(c, cx, cy, size):
    """Draw a Shiva Trishoola (trident) above Swami frames."""
    s = size
    c.setStrokeColor(GOLD)
    c.setFillColor(GOLD)
    c.setLineWidth(1.2)
    # Handle
    c.line(cx, cy, cx, cy + s * 1.8)
    # Center prong
    c.line(cx, cy + s, cx, cy + s * 2.2)
    # Left prong
    c.line(cx - s * 0.5, cy + s, cx - s * 0.5, cy + s * 1.8)
    c.line(cx - s * 0.5, cy + s, cx, cy + s * 1.3)
    # Right prong
    c.line(cx + s * 0.5, cy + s, cx + s * 0.5, cy + s * 1.8)
    c.line(cx + s * 0.5, cy + s, cx, cy + s * 1.3)
    # Damru
    c.setFillColor(DEEP_GOLD)
    c.circle(cx, cy + s * 0.8, s * 0.35, fill=1, stroke=0)


def draw_ishtalinga(c, cx, cy, size):
    """Draw an Ishtalinga (Veerashaiva sacred symbol)."""
    # Oval linga in dark stone
    c.setFillColor(HexColor("#2C2C2C"))
    lw, lh = size * 0.7, size
    c.ellipse(cx - lw / 2, cy, cx + lw / 2, cy + lh, fill=1, stroke=0)
    # Gold peetha (base)
    c.setFillColor(DEEP_GOLD)
    c.rect(cx - size * 0.6, cy - size * 0.25, size * 1.2, size * 0.28, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.ellipse(cx - size * 0.55, cy - size * 0.12, cx + size * 0.55, cy + size * 0.12,
              fill=1, stroke=0)

# ─── Page 1 ───────────────────────────────────────────────────────────────────

def build_page1(c, page_w, page_h, swami1_path, swami2_path, couple_img):
    """Build the main English invitation page."""
    M = 10 * mm   # margin

    # ── Background ──
    c.setFillColor(IVORY)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Subtle inner cream band
    c.setFillColor(CREAM)
    c.rect(M, M, page_w - 2 * M, page_h - 2 * M, fill=1, stroke=0)

    # ── Outer border ──
    draw_kolam_border(c, M, M, page_w - 2 * M, page_h - 2 * M, margin_in=4 * mm)

    # ── Torana arch ──
    draw_torana(c, page_w, page_h, M + 4 * mm)

    current_y = page_h - M - 28 * mm

    # ── Religious blessing ──
    c.setFont("Cormorant-BoldItalic", 10)
    c.setFillColor(GOLD)
    blessing = "II Sri Marulasiddeshwara Prasanna II"
    bw = c.stringWidth(blessing, "Cormorant-BoldItalic", 10)
    c.drawString((page_w - bw) / 2, current_y, blessing)
    current_y -= 5.5 * mm

    c.setFont("Cormorant-Italic", 8)
    c.setFillColor(STONE)
    math_line = "Sri Sri Sri Dr. Shivamurthi Shivacharya Mahaswamikal"
    mw = c.stringWidth(math_line, "Cormorant-Italic", 8)
    c.drawString((page_w - mw) / 2, current_y, math_line)
    current_y -= 4 * mm

    c.setFont("Cormorant-Italic", 7.5)
    math_line2 = "Taralabalu Bruhan Math, Sirigere"
    mw2 = c.stringWidth(math_line2, "Cormorant-Italic", 7.5)
    c.drawString((page_w - mw2) / 2, current_y, math_line2)
    current_y -= 3 * mm

    # ── Swami portraits row ──
    swami_r = 15 * mm
    swami_y = current_y - swami_r - 4 * mm
    swami1_cx = M + 4 * mm + swami_r + 2 * mm
    swami2_cx = page_w - M - 4 * mm - swami_r - 2 * mm

    draw_swami_frame(c, swami1_cx, swami_y, swami_r, str(swami1_path))
    draw_swami_frame(c, swami2_cx, swami_y, swami_r, str(swami2_path))

    # Kalasha centered between Swamis at the SAME vertical level
    kalasha_cx = page_w / 2
    kalasha_cy = swami_y - 16 * mm  # base of pot aligns ~mid-frame
    draw_kalasha(c, kalasha_cx, kalasha_cy, scale=0.80)

    current_y = swami_y - swami_r - 4 * mm

    usable_w = page_w - 2 * M - 8 * mm

    # ── Request line ──
    c.setFont("Cormorant-Italic", 8.5)
    c.setFillColor(STONE)
    req = "Smt. A.T. Nalina & Sri. Dr. G. Prabhulingaiah, Davanagere"
    rw = c.stringWidth(req, "Cormorant-Italic", 8.5)
    c.drawString((page_w - rw) / 2, current_y, req)
    current_y -= 4 * mm

    c.setFont("Cormorant-Italic", 8)
    req2a = "request the pleasure of your company on the auspicious occasion of the marriage of their daughter"
    rw2 = c.stringWidth(req2a, "Cormorant-Italic", 8)
    if rw2 > usable_w:
        split_at = req2a.rfind(" ", 0, len(req2a) // 2 + 10)
        for ln in [req2a[:split_at], req2a[split_at+1:]]:
            lw = c.stringWidth(ln, "Cormorant-Italic", 8)
            c.drawString((page_w - lw) / 2, current_y, ln)
            current_y -= 3.8 * mm
    else:
        c.drawString((page_w - rw2) / 2, current_y, req2a)
        current_y -= 3.8 * mm

    current_y -= 1 * mm

    # ── Bride name ──
    c.setFont("Cormorant-Bold", 20)
    c.setFillColor(MAROON)
    bname = "Chi. Kum. Sou. SOWJANYA P."
    bnw = c.stringWidth(bname, "Cormorant-Bold", 20)
    c.drawString((page_w - bnw) / 2, current_y, bname)
    current_y -= 6 * mm

    # Joining rule
    draw_ornate_rule(c, M + 4 * mm, current_y + 2 * mm, usable_w)
    current_y -= 3 * mm

    # ── Couple illustration ──
    couple_h = 26 * mm
    couple_w = couple_h
    couple_x = (page_w - couple_w) / 2
    c.drawImage(pil_to_reader(couple_img), couple_x, current_y - couple_h,
                width=couple_w, height=couple_h, mask="auto")
    current_y -= couple_h + 2 * mm

    # Joining rule
    draw_ornate_rule(c, M + 4 * mm, current_y + 2 * mm, usable_w)
    current_y -= 3 * mm

    # ── Groom name ──
    c.setFont("Cormorant-Bold", 20)
    c.setFillColor(MAROON)
    gname = "Chi. Ra. RUTURAJ R."
    gnw = c.stringWidth(gname, "Cormorant-Bold", 20)
    c.drawString((page_w - gnw) / 2, current_y, gname)
    current_y -= 5 * mm

    c.setFont("Cormorant-Italic", 7.5)
    c.setFillColor(STONE)
    gparent = "S/o. Smt. Ashwini R. & Sri. Vivek R., Pune, Maharashtra"
    gpw = c.stringWidth(gparent, "Cormorant-Italic", 7.5)
    c.drawString((page_w - gpw) / 2, current_y, gparent)
    current_y -= 5 * mm

    # Thin divider
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.6)
    c.line(M + 8 * mm, current_y, page_w - M - 8 * mm, current_y)
    current_y -= 4 * mm

    # ── Event boxes ──
    box_w = usable_w * 0.46
    box_h = 22 * mm
    box_gap = usable_w * 0.08
    box1_x = M + 4 * mm
    box2_x = box1_x + box_w + box_gap

    draw_event_box(c, box1_x, current_y - box_h, box_w, box_h,
                   "RECEPTION",
                   [("", "6th May 2026"),
                    ("", "Wednesday"),
                    ("", "7:30 PM onwards")],
                   "Cormorant-Bold", "Cormorant-Regular")

    draw_event_box(c, box2_x, current_y - box_h, box_w, box_h,
                   "MUHURTHAM",
                   [("", "7th May 2026"),
                    ("", "Thursday"),
                    ("", "9:00 – 9:55 AM")],
                   "Cormorant-Bold", "Cormorant-Regular")

    current_y -= box_h + 3 * mm

    # ── Lagnam + Venue ──
    c.setFont("Cormorant-Bold", 8.5)
    c.setFillColor(GOLD)
    lag = "Lagnam: Mithuna"
    lw = c.stringWidth(lag, "Cormorant-Bold", 8.5)
    c.drawString((page_w - lw) / 2, current_y, lag)
    current_y -= 3.8 * mm

    c.setFont("Cormorant-Regular", 8)
    c.setFillColor(STONE)
    for vl in ["Venue: Smt. Sudha Veerendra Patel Samudaya Bhavan",
               "Siramagondanahalli, Davangere"]:
        vw = c.stringWidth(vl, "Cormorant-Regular", 8)
        c.drawString((page_w - vw) / 2, current_y, vl)
        current_y -= 3.5 * mm

    # ── Thin rule ──
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.6)
    c.line(M + 10 * mm, current_y, page_w - M - 10 * mm, current_y)
    current_y -= 3.5 * mm

    # ── Host names ──
    hosts = [
        "Smt. A.T. Nalina & Sri. Dr. G. Prabhulingaiah  |  Chi. P. Santosh Kumar",
        "Smt. P. Sowmya & Sri. C. Manjunath & Sons  |  Chi. Maurya M. & Chi. Amay M.",
        "Smt. Ashwini R. & Sri. Vivek R., Pune, Maharashtra",
    ]
    for hl in hosts:
        fs = 7.5
        c.setFont("Cormorant-Regular", fs)
        hw = c.stringWidth(hl, "Cormorant-Regular", fs)
        while hw > usable_w and fs > 6:
            fs -= 0.5
            c.setFont("Cormorant-Regular", fs)
            hw = c.stringWidth(hl, "Cormorant-Regular", fs)
        c.setFillColor(BROWN)
        c.drawString((page_w - hw) / 2, current_y, hl)
        current_y -= 3.8 * mm

    c.setFont("Cormorant-Italic", 7.5)
    c.setFillColor(STONE)
    bc = "Best Compliments from: Relatives & Friends"
    bcw = c.stringWidth(bc, "Cormorant-Italic", 7.5)
    c.drawString((page_w - bcw) / 2, current_y, bc)


# ─── Page 2 ───────────────────────────────────────────────────────────────────

def build_page2(c, page_w, page_h, swami1_path, swami2_path, couple_img, qr_path):
    """Build the personal invitation card (page 2)."""
    M = 10 * mm

    # ── Background ──
    c.setFillColor(IVORY)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    c.setFillColor(CREAM)
    c.rect(M, M, page_w - 2 * M, page_h - 2 * M, fill=1, stroke=0)

    # Subtle diagonal texture lines (very faint)
    c.setStrokeColor(HexColor("#EFE4C8"))
    c.setLineWidth(0.3)
    for i in range(0, int(page_w + page_h), 8):
        c.line(max(0, i - page_h), min(page_h, i), min(page_w, i), max(0, i - page_w))

    draw_kolam_border(c, M, M, page_w - 2 * M, page_h - 2 * M, margin_in=4 * mm)

    # ── Torana (smaller) ──
    draw_torana(c, page_w, page_h, M + 4 * mm)

    current_y = page_h - M - 26 * mm

    # ── Swami portraits ──
    swami_r = 15 * mm
    swami_y = current_y - swami_r - 2 * mm
    swami1_cx = M + 4 * mm + swami_r + 2 * mm
    swami2_cx = page_w - M - 4 * mm - swami_r - 2 * mm

    draw_swami_frame(c, swami1_cx, swami_y, swami_r, str(swami1_path))
    draw_swami_frame(c, swami2_cx, swami_y, swami_r, str(swami2_path))

    # ── "Shubha Vivaaha" between Swamis ──
    sv_img = Image.open(ASSETS / "extracted_p2_img2.png").convert("RGBA")
    # Recolor to gold tones
    sv_data = sv_img.getdata()
    sv_new = []
    for px in sv_data:
        r, g, b, a = px
        brightness = (r + g + b) / 3
        if brightness < 100:
            sv_new.append((139, 90, 20, 255))   # gold-brown
        else:
            sv_new.append((0, 0, 0, 0))
    sv_img.putdata(sv_new)

    sv_w_mm = 55 * mm
    sv_h_mm = sv_w_mm * (sv_img.height / sv_img.width)
    sv_x = (page_w - sv_w_mm) / 2
    sv_y_pos = swami_y + swami_r - sv_h_mm / 2 + 3 * mm
    c.drawImage(pil_to_reader(sv_img), sv_x, sv_y_pos,
                width=sv_w_mm, height=sv_h_mm, mask="auto")

    # Ishtalinga below Shubha Vivaaha text
    draw_ishtalinga(c, page_w / 2, sv_y_pos - 9 * mm, 5 * mm)

    current_y = swami_y - swami_r - 5 * mm

    # ── Ornate circular frame with couple illustration ──
    circle_r = 30 * mm
    circle_cx = page_w / 2
    circle_cy = current_y - circle_r - 3 * mm

    # Outer petal ring
    c.setFillColor(DEEP_GOLD)
    draw_lotus_petal_ring(c, circle_cx, circle_cy, circle_r + 7 * mm, n_petals=12, color=DEEP_GOLD)

    # Gold circle
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.circle(circle_cx, circle_cy, circle_r + 2 * mm, fill=0, stroke=1)

    # Cream fill for circle
    c.setFillColor(CREAM)
    c.circle(circle_cx, circle_cy, circle_r, fill=1, stroke=0)

    # Maroon inner ring
    c.setStrokeColor(MAROON)
    c.setLineWidth(1)
    c.circle(circle_cx, circle_cy, circle_r, fill=0, stroke=1)

    # Couple illustration inside
    couple_size = circle_r * 1.7
    c.drawImage(pil_to_reader(couple_img),
                circle_cx - couple_size / 2, circle_cy - couple_size / 2,
                width=couple_size, height=couple_size, mask="auto")

    # Kolam dot ring around the outer lotus ring
    n_dots = 24
    dot_r = circle_r + 12 * mm
    c.setFillColor(GOLD)
    for i in range(n_dots):
        angle = 2 * math.pi / n_dots * i
        dx = circle_cx + dot_r * math.cos(angle)
        dy = circle_cy + dot_r * math.sin(angle)
        c.circle(dx, dy, 0.8 * mm, fill=1, stroke=0)

    current_y = circle_cy - circle_r - 6 * mm

    # ── Bride name ──
    c.setFont("Cormorant-Bold", 16)
    c.setFillColor(MAROON)
    bn = "Chi. Kum. Sou. Sowjanya P."
    bnw = c.stringWidth(bn, "Cormorant-Bold", 16)
    c.drawString((page_w - bnw) / 2, current_y, bn)
    current_y -= 5.5 * mm

    draw_ornate_rule(c, M + 10 * mm, current_y + 2 * mm, page_w - 2 * M - 20 * mm)
    current_y -= 4.5 * mm

    # ── Groom name ──
    c.setFont("Cormorant-Bold", 16)
    c.setFillColor(MAROON)
    gn = "Chi. Ra. Ruturaj R."
    gnw = c.stringWidth(gn, "Cormorant-Bold", 16)
    c.drawString((page_w - gnw) / 2, current_y, gn)
    current_y -= 5 * mm

    # ── Thin divider ──
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.6)
    c.line(M + 8 * mm, current_y, page_w - M - 8 * mm, current_y)
    current_y -= 4.5 * mm

    # ── Date + invite text ──
    c.setFont("Cormorant-Bold", 9.5)
    c.setFillColor(GOLD)
    date_line = "Thursday, 7th May 2026"
    dw = c.stringWidth(date_line, "Cormorant-Bold", 9.5)
    c.drawString((page_w - dw) / 2, current_y, date_line)
    current_y -= 4.5 * mm

    c.setFont("Cormorant-Italic", 8.5)
    c.setFillColor(STONE)
    invite_text = "You and your family are cordially invited to the wedding ceremony"
    iw = c.stringWidth(invite_text, "Cormorant-Italic", 8.5)
    c.drawString((page_w - iw) / 2, current_y, invite_text)
    current_y -= 4 * mm

    # ── From ──
    c.setFont("Cormorant-Regular", 8)
    c.setFillColor(BROWN)
    from_lines = [
        "Smt. A.T. Nalina & Sri. Dr. G. Prabhulingaiah",
        "#1746/27, 16th Cross, Anjaneyya Badavane, Davangere",
        "Mo: 9741568432 / 8277182037",
    ]
    for fl in from_lines:
        fw = c.stringWidth(fl, "Cormorant-Regular", 8)
        c.drawString((page_w - fw) / 2, current_y, fl)
        current_y -= 4 * mm

    # ── QR code ──
    qr = Image.open(qr_path).convert("RGB")
    qr_size = 18 * mm
    qr_x = page_w - M - 4 * mm - qr_size - 2 * mm
    qr_y = M + 4 * mm + 4 * mm
    c.drawImage(pil_to_reader(qr), qr_x, qr_y, width=qr_size, height=qr_size)
    c.setFont("Cormorant-Italic", 6.5)
    c.setFillColor(STONE)
    scan_txt = "Scan for Location"
    stw = c.stringWidth(scan_txt, "Cormorant-Italic", 6.5)
    c.drawString(qr_x + (qr_size - stw) / 2, qr_y - 3.5 * mm, scan_txt)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Setting up fonts...")
    setup_fonts()

    print("Preparing Swami portraits...")
    swami1_path, swami2_path = crop_swami_portraits()

    print("Preparing couple illustration...")
    couple_raw = recolor_silhouette(
        str(ASSETS / "extracted_p1_img16.png"),
        fill_color=(123, 24, 24),
        bg_color=(255, 248, 231),
    )

    qr_path = ASSETS / "extracted_p2_img1.png"

    page_w, page_h = A5   # 419.53 x 595.28 pts

    print("Building PDF...")
    c = rl_canvas.Canvas(PDF_OUT, pagesize=A5)

    # ── Page 1 ──
    build_page1(c, page_w, page_h, swami1_path, swami2_path, couple_raw)
    c.showPage()

    # ── Page 2 ──
    build_page2(c, page_w, page_h, swami1_path, swami2_path, couple_raw, qr_path)
    c.showPage()

    c.save()
    print(f"\nDone! Output: {PDF_OUT}")


if __name__ == "__main__":
    main()
