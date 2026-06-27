"""
description: Generate a per-clinic FR pitch one-pager + QR code from the template. Reads
docs/sales/vitry_dental_one_pager.md, substitutes the {{ }} tokens, writes a PDF + a PNG QR.

inputs:
    --clinic-name TEXT          required, e.g. "Centre Dentaire Dentylis Stalingrad"
    --clinic-contact TEXT       e.g. "Mme la gérante" or owner name (defaults to "Mme/M. la/le gérant(e)")
    --demo-url URL              required, the Modal deploy URL
    --out-dir DIR               default: .tmp/sales/<slug>
    --phone TEXT                operator's mobile to print on the pitch (defaults to env PITCH_PHONE)

outputs:
    <out-dir>/pitch_<slug>.md   filled markdown
    <out-dir>/qr_<slug>.png     QR PNG (300x300, embed-ready)
    <out-dir>/pitch_<slug>.pdf  rendered PDF (if reportlab available)

Stays deterministic (no LLM calls). Run once per clinic before the walk-in / email.
"""

from __future__ import annotations

import argparse
import locale
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "docs" / "sales" / "vitry_dental_one_pager.md"


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", norm).strip("_").lower()
    return s or "clinic"


def today_fr() -> str:
    months = ["janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    d = date.today()
    return f"{d.day} {months[d.month - 1]} {d.year}"


def render_md(template: str, clinic_name: str, clinic_contact: str, demo_url: str, phone: str) -> str:
    out = template
    out = out.replace("{{CLINIC_OWNER_OR_MANAGER}}", clinic_contact)
    out = out.replace("{{TODAY_FR}}", today_fr())
    out = out.replace("{{DEMO_URL}}", demo_url)
    out = out.replace("[opérateur à compléter]", phone)
    # Replace the default Dentylis reference with the clinic name in the headline area
    out = out.replace("Centre Dentaire Dentylis Stalingrad", clinic_name)
    return out


def write_qr(demo_url: str, dest: Path) -> None:
    try:
        import qrcode
    except ImportError:
        print(f"WARN  qrcode not installed; skipping QR. pip install qrcode[pil]")
        return
    img = qrcode.make(demo_url)
    img.save(dest)
    print(f"  wrote {dest}")


def write_pdf(md_text: str, qr_path: Path, dest: Path, clinic_name: str) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        print(f"WARN  reportlab not installed; skipping PDF. pip install reportlab")
        return

    # Register Arial for Unicode (per workspace memory feedback_cv_builder.md)
    try:
        pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
        pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
        base_font, bold_font = "Arial", "Arial-Bold"
    except Exception:
        base_font, bold_font = "Helvetica", "Helvetica-Bold"

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontName=base_font, fontSize=10.5, leading=14, spaceAfter=6)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName=bold_font, fontSize=15, leading=18, textColor=colors.HexColor("#0b3d2e"), spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName=bold_font, fontSize=12, leading=15, textColor=colors.HexColor("#0b3d2e"), spaceBefore=10, spaceAfter=4)
    footer = ParagraphStyle("footer", parent=styles["Normal"], fontName=base_font, fontSize=9, leading=11, textColor=colors.HexColor("#888"))

    doc = SimpleDocTemplate(
        str(dest), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title=f"Pitch — {clinic_name}",
    )

    story = []
    in_code = False
    for line in md_text.splitlines():
        if line.startswith("# "):
            story.append(Paragraph(line[2:].strip(), h1))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:].strip(), h2))
        elif line.startswith("---"):
            story.append(Spacer(1, 0.3 * cm))
        elif line.strip() == "":
            story.append(Spacer(1, 0.15 * cm))
        elif line.startswith("- "):
            story.append(Paragraph("• " + line[2:].strip(), body))
        elif line.startswith("**") and line.endswith("**"):
            story.append(Paragraph(f"<b>{line[2:-2]}</b>", body))
        else:
            # Convert markdown bold inline
            t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
            story.append(Paragraph(t, body))

    # Append QR page
    if qr_path.exists():
        story.append(PageBreak())
        story.append(Paragraph("Démo en direct — scannez :", h2))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Image(str(qr_path), width=8 * cm, height=8 * cm))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Ouvrez le lien depuis votre téléphone. Cliquez sur « Parler à Lisa » et essayez : <i>« Bonjour, je voudrais une consultation »</i>.", body))

    doc.build(story)
    print(f"  wrote {dest}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--clinic-name", required=True)
    p.add_argument("--clinic-contact", default="Mme/M. la/le gérant(e)")
    p.add_argument("--demo-url", required=True)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--phone", default=os.environ.get("PITCH_PHONE", "[opérateur à compléter]"))
    args = p.parse_args()

    slug = slugify(args.clinic_name)
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / ".tmp" / "sales" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    md = render_md(TEMPLATE.read_text(encoding="utf-8"),
                   clinic_name=args.clinic_name,
                   clinic_contact=args.clinic_contact,
                   demo_url=args.demo_url,
                   phone=args.phone)

    md_path = out_dir / f"pitch_{slug}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  wrote {md_path}")

    qr_path = out_dir / f"qr_{slug}.png"
    write_qr(args.demo_url, qr_path)

    pdf_path = out_dir / f"pitch_{slug}.pdf"
    write_pdf(md, qr_path, pdf_path, args.clinic_name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
