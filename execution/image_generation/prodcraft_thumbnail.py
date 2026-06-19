"""
description: Generate a 1280x720 ProdCraft YouTube thumbnail from a title + optional subtitle. $0 path — pure Pillow, no API. Matches Living PRD bookend brand (dark navy bg, teal accent rail, big white sans-serif title).
inputs:
    CLI:
        --title "..."        thumbnail headline (required; auto-wraps)
        --subtitle "..."     optional second line
        --eyebrow "..."      short uppercase kicker (default: "PRODCRAFT")
        --handle "..."       channel handle (default: "@ProdCraft")
        --out PATH           output PNG (default: .tmp/prodcraft/thumb.png)
        --font-bold PATH     bold TTF (default: probes common system fonts)
        --font-regular PATH  regular TTF (default: probes common system fonts)
        --accent "#hex"      accent color (default: #1c8b7c)
outputs:
    {out}                    1280x720 PNG
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Install: py -m pip install pillow") from exc

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "thumb.png"

W, H = 1280, 720
BG_TOP = (11, 18, 32)
BG_BOTTOM = (5, 10, 22)
TEXT_PRIMARY = (250, 251, 253)
TEXT_MUTED = (250, 251, 253, 180)
TEXT_DIM = (250, 251, 253, 110)

FONT_BOLD_CANDIDATES = [
    r"C:\Windows\Fonts\Inter-Bold.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
FONT_REGULAR_CANDIDATES = [
    r"C:\Windows\Fonts\Inter-Regular.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _probe_font(candidates: list[str], explicit: str | None, size: int) -> ImageFont.FreeTypeFont:
    paths = ([explicit] if explicit else []) + candidates
    for p in paths:
        if p and Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def generate(
    title: str,
    subtitle: str,
    eyebrow: str,
    handle: str,
    out: Path,
    font_bold: str | None,
    font_regular: str | None,
    accent_hex: str,
) -> None:
    accent = _hex_to_rgb(accent_hex)

    img = Image.new("RGB", (W, H), BG_TOP)
    for y in range(H):
        ratio = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * ratio)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * ratio)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * ratio)
        for x in range(W):
            img.putpixel((x, y), (r, g, b))
    img = Image.new("RGB", (W, H), BG_TOP)  # gradient by row instead
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(H):
        ratio = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * ratio)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * ratio)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    draw.rectangle([(0, 0), (8, H)], fill=accent)
    draw.rectangle([(80, H - 180), (280, H - 174)], fill=accent)

    f_eyebrow = _probe_font(FONT_BOLD_CANDIDATES, font_bold, 28)
    f_title = _probe_font(FONT_BOLD_CANDIDATES, font_bold, 92)
    f_subtitle = _probe_font(FONT_REGULAR_CANDIDATES, font_regular, 38)
    f_handle = _probe_font(FONT_BOLD_CANDIDATES, font_bold, 26)

    eyebrow_text = (eyebrow or "PRODCRAFT").upper()
    draw.text((80, 86), eyebrow_text, font=f_eyebrow, fill=TEXT_DIM)

    title_lines = _wrap(draw, title, f_title, max_w=W - 200)
    if len(title_lines) > 3:
        title_lines = title_lines[:3]
        title_lines[-1] = title_lines[-1] + "…"

    y = 180
    for ln in title_lines:
        bbox = draw.textbbox((0, 0), ln, font=f_title)
        h = bbox[3] - bbox[1]
        draw.text((80, y), ln, font=f_title, fill=TEXT_PRIMARY)
        y += h + 12

    if subtitle:
        y_sub = max(y + 30, H - 280)
        sub_lines = _wrap(draw, subtitle, f_subtitle, max_w=W - 200)[:2]
        for ln in sub_lines:
            draw.text((80, y_sub), ln, font=f_subtitle, fill=TEXT_MUTED)
            y_sub += 50

    draw.text((80, H - 70), handle, font=f_handle, fill=accent)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out), format="PNG", optimize=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a ProdCraft YouTube thumbnail.")
    p.add_argument("--title", required=True)
    p.add_argument("--subtitle", default="")
    p.add_argument("--eyebrow", default="PRODCRAFT")
    p.add_argument("--handle", default="@ProdCraft")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--font-bold", default=None)
    p.add_argument("--font-regular", default=None)
    p.add_argument("--accent", default="#1c8b7c")
    args = p.parse_args()
    out = Path(args.out).resolve()
    generate(args.title, args.subtitle, args.eyebrow, args.handle, out, args.font_bold, args.font_regular, args.accent)
    import json

    print(json.dumps({"ok": True, "out": str(out), "size": [W, H]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
