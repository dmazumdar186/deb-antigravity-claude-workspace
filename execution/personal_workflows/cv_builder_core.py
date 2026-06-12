#!/usr/bin/env python3
"""
cv_builder_core.py
description: Shared reportlab rendering primitives for cv_builder*.py variants.
inputs: Imported as a module — not run directly.
outputs: N/A (library module)

Exposes:
  - _register_fonts() -> (FONT, FONT_BOLD)     # font registration, Arial→Helvetica fallback
  - make_styles(FONT, FONT_BOLD, colors)        # build the paragraph-style dict S
  - SectionHeaderBase                           # base Flowable; subclass for custom drawing
  - accroche(text, kpi_line, styles, layout)   # coloured highlight box (FR/EN variants)
  - exp_entry(title, company_line, bullets,    # experience entry flowables
              styles, keep_first_bullet)
  - skill_row(cat, val, styles, layout)         # two-column skill row
  - build_cv_doc(output, story, **doc_kw)       # assemble + render BaseDocTemplate

Variants (cv_builder.py, cv_builder_en.py, cv_builder_skott.py) import what they
need, define their own colour palette, SectionHeader subclass, style overrides,
and build_story() — no rendering logic lives in the variants.

Dependencies: pip install reportlab
"""

import os
import sys
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame,
        Paragraph, Spacer, Table, TableStyle,
        Flowable, KeepTogether, HRFlowable,
    )
    from reportlab.lib.enums import TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
except ImportError:
    print("ERROR: pip install reportlab")
    sys.exit(1)

# ── Re-export platypus names so variants only need one import ──────────────────
__all__ = [
    # reportlab re-exports
    'A4', 'ParagraphStyle', 'cm', 'HexColor',
    'BaseDocTemplate', 'PageTemplate', 'Frame',
    'Paragraph', 'Spacer', 'Table', 'TableStyle',
    'Flowable', 'KeepTogether', 'HRFlowable',
    'TA_JUSTIFY',
    # core helpers
    '_register_fonts',
    'make_style',
    'SectionHeader',
    'accroche',
    'exp_entry',
    'skill_row',
    'build_cv_doc',
]

# ── Standard page geometry (variants may override with their own constants) ────
PAGE_W, PAGE_H = A4
_DEFAULT_MARGIN_LR = 1.8 * cm
_DEFAULT_MARGIN_TB = 1.5 * cm


# ── Font registration ──────────────────────────────────────────────────────────
def _register_fonts(*, with_italic: bool = False) -> tuple[str, str]:
    """Register Arial (Windows) TTFonts or fall back to Helvetica.

    Args:
        with_italic: When True, also registers the italic face (ariali.ttf).
                     cv_builder_skott uses italic; the FR/EN variants do not.

    Returns:
        (FONT, FONT_BOLD) — the base and bold face names to use in styles.
    """
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    regular = os.path.join(win_fonts, 'arial.ttf')
    bold    = os.path.join(win_fonts, 'arialbd.ttf')
    italic  = os.path.join(win_fonts, 'ariali.ttf')

    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont('CV',      regular))
        pdfmetrics.registerFont(TTFont('CV-Bold', bold))
        if with_italic:
            pdfmetrics.registerFont(
                TTFont('CV-Ital', italic if os.path.exists(italic) else regular)
            )
            registerFontFamily('CV', normal='CV', bold='CV-Bold',
                               italic='CV-Ital', boldItalic='CV-Bold')
        else:
            registerFontFamily('CV', normal='CV', bold='CV-Bold',
                               italic='CV', boldItalic='CV-Bold')
        return 'CV', 'CV-Bold'

    registerFontFamily('Helvetica', normal='Helvetica', bold='Helvetica-Bold',
                       italic='Helvetica-Oblique', boldItalic='Helvetica-BoldOblique')
    return 'Helvetica', 'Helvetica-Bold'


# ── Section header base (subclass this in each variant; override draw()) ────────
class SectionHeader(Flowable):
    """Abstract base for CV section headers.

    Subclasses must override ``draw()`` to implement variant-specific styling.
    The ``__init__`` signature is standardised: ``(text, width=TEXT_W)`` where
    TEXT_W is the variant's own computed text width constant.
    """
    HEIGHT = 19

    def __init__(self, text: str, width: float = 0.0):
        super().__init__()
        self.text   = text
        self.width  = width
        self.height = self.HEIGHT

    def draw(self):  # pragma: no cover
        raise NotImplementedError("Subclass must implement draw()")


# ── Style factory ──────────────────────────────────────────────────────────────
def make_style(font: str, **kw) -> ParagraphStyle:
    """Create a ParagraphStyle with sensible CV defaults.

    Args:
        font: The base font name (FONT constant from the variant).
        **kw:  Any ParagraphStyle kwargs that override the defaults.

    Returns:
        A ParagraphStyle instance.
    """
    defaults = dict(fontName=font, fontSize=8.4, textColor=HexColor('#2C2C2C'),
                    leading=12.5, spaceAfter=0)
    defaults.update(kw)
    return ParagraphStyle('', **defaults)


# ── Content helpers ─────────────────────────────────────────────────────────────

def accroche(text: str, kpi_line: str, *, style: ParagraphStyle,
             text_w: float, bg_color: HexColor = HexColor('#EAF4F7')) -> Table:
    """Coloured highlight box used as the CV summary/accroche.

    Args:
        text:      Main paragraph text (may contain HTML tags).
        kpi_line:  KPI / results line appended below the main text.
        style:     ParagraphStyle for the combined text (typically S['accroche']).
        text_w:    Available text width (PAGE_W - 2 * MARGIN_LR).
        bg_color:  Background colour of the box; defaults to light blue #EAF4F7.

    Returns:
        A single-cell Table that renders as the highlight box.
    """
    inner = Paragraph(text + '<br/><br/>' + kpi_line, style)
    t = Table([[inner]], colWidths=[text_w])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), bg_color),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 9),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 9),
    ]))
    return t


def exp_entry(
    title: str,
    company_line: str,
    bullets: list[str],
    *,
    role_style: ParagraphStyle,
    employer_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
    keep_first_bullet: bool = False,
) -> list:
    """Build flowables for one experience entry.

    Args:
        title:             Job title text (may contain HTML).
        company_line:      Company + date line.
        bullets:           List of bullet strings (may contain HTML).
        role_style:        ParagraphStyle for the title.
        employer_style:    ParagraphStyle for the company line.
        bullet_style:      ParagraphStyle for bullet paragraphs.
        keep_first_bullet: When True, wraps title + employer + first bullet in
                           KeepTogether so a title never strands at the bottom of
                           a page without at least one bullet. The EN variant uses
                           this; the FR and Skott variants keep only title+employer.

    Returns:
        List of Flowable objects to extend into the story.
    """
    title_p    = Paragraph(title, role_style)
    employer_p = Paragraph(company_line, employer_style)

    if keep_first_bullet and bullets:
        first_bullet = Paragraph('<bullet>•</bullet>' + bullets[0], bullet_style)
        elems: list = [KeepTogether([title_p, employer_p, first_bullet])]
        remaining = bullets[1:]
    else:
        elems = [KeepTogether([title_p, employer_p])]
        remaining = bullets

    for b in remaining:
        elems.append(Paragraph('<bullet>•</bullet>' + b, bullet_style))
    elems.append(Spacer(1, 5))
    return elems


def skill_row(cat: str, val: str, *,
              cat_style: ParagraphStyle,
              val_style: ParagraphStyle,
              text_w: float,
              cat_col_w: float = 3.6,
              separator: str = ' :') -> Table:
    """Two-column skill row: bold category label | wrapped value text.

    Args:
        cat:        Category label (e.g. 'AI & GenAI').
        val:        Skill values as a string (may contain HTML).
        cat_style:  ParagraphStyle for the category label.
        val_style:  ParagraphStyle for the value text.
        text_w:     Full available text width.
        cat_col_w:  Width of the category column in cm (default 3.6 cm).
        separator:  Separator appended to cat label (default NBSP + colon).

    Returns:
        A two-column Table.
    """
    cat_w = cat_col_w * cm
    t = Table(
        [[Paragraph(cat + separator, cat_style),
          Paragraph(val, val_style)]],
        colWidths=[cat_w, text_w - cat_w],
    )
    t.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return t


# ── PDF document assembly ──────────────────────────────────────────────────────

def build_cv_doc(output: Path, story: list, *,
                 margin_lr: float = _DEFAULT_MARGIN_LR,
                 margin_tb: float = _DEFAULT_MARGIN_TB,
                 **doc_kwargs) -> None:
    """Assemble a BaseDocTemplate and render the story to a PDF.

    Args:
        output:     Destination path for the PDF.
        story:      List of Flowable objects returned by the variant's build_story().
        margin_lr:  Left/right margin in points (default: 1.8 cm).
        margin_tb:  Top/bottom margin in points (default: 1.5 cm).
        **doc_kwargs: Extra kwargs forwarded to BaseDocTemplate (e.g. title, author).
    """
    _, page_h = A4
    text_w = A4[0] - 2 * margin_lr

    doc = BaseDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=margin_lr,
        rightMargin=margin_lr,
        topMargin=margin_tb,
        bottomMargin=margin_tb,
        **doc_kwargs,
    )
    frame = Frame(
        margin_lr, margin_tb,
        text_w, page_h - 2 * margin_tb,
        id='main', showBoundary=0,
    )
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
    doc.build(story)
