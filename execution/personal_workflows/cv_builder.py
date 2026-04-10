#!/usr/bin/env python3
"""
cv_builder.py
Generate an ATS-optimised, French-language PDF CV for Debanjan Mazumdar.

Usage:
    py execution/personal_workflows/cv_builder.py --company sahar --role "AI Product Manager"

Output: .tmp/cv_{company}_debanjan_mazumdar.pdf
Dependencies: pip install reportlab
"""

import argparse
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
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
except ImportError:
    print("ERROR: pip install reportlab")
    sys.exit(1)

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_LR = 1.8 * cm
MARGIN_TB = 1.5 * cm
TEXT_W = PAGE_W - 2 * MARGIN_LR

# ── Colours ────────────────────────────────────────────────────────────────────
NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')


# ── Font registration ──────────────────────────────────────────────────────────
def _register_fonts():
    """Use Arial (Windows) for full Unicode; fall back to Helvetica."""
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    regular = os.path.join(win_fonts, 'arial.ttf')
    bold    = os.path.join(win_fonts, 'arialbd.ttf')
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont('CV',      regular))
        pdfmetrics.registerFont(TTFont('CV-Bold', bold))
        registerFontFamily('CV', normal='CV', bold='CV-Bold',
                           italic='CV', boldItalic='CV-Bold')
        return 'CV', 'CV-Bold'
    registerFontFamily('Helvetica', normal='Helvetica', bold='Helvetica-Bold',
                       italic='Helvetica-Oblique', boldItalic='Helvetica-BoldOblique')
    return 'Helvetica', 'Helvetica-Bold'

FONT, FONT_BOLD = _register_fonts()


# ── Custom flowable: coloured section header ────────────────────────────────────
class SectionHeader(Flowable):
    HEIGHT = 19

    def __init__(self, text, width=TEXT_W):
        super().__init__()
        self.text   = text
        self.width  = width
        self.height = self.HEIGHT

    def draw(self):
        c = self.canv
        c.setFillColor(TEAL)
        c.rect(0, 3, 3.5, 13, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont(FONT_BOLD, 10)
        c.drawString(9, 4, self.text.upper())
        c.setStrokeColor(HexColor('#DDDDDD'))
        c.setLineWidth(0.4)
        c.line(0, 0, self.width, 0)


# ── Paragraph styles ────────────────────────────────────────────────────────────
def _s(**kw):
    defaults = dict(fontName=FONT, fontSize=8.4, textColor=DKGRY,
                    leading=12.5, spaceAfter=0)
    defaults.update(kw)
    return ParagraphStyle('', **defaults)

S = {
    'name':      _s(fontName=FONT_BOLD, fontSize=22, textColor=NAVY,
                    leading=26, spaceAfter=2),
    'subtitle':  _s(fontSize=9.8, textColor=TEAL, leading=13, spaceAfter=3),
    'contact':   _s(fontSize=8.1, textColor=MDGRY, leading=11, spaceAfter=0),
    'accroche':  _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=13),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.3, textColor=NAVY,
                    leading=12, spaceAfter=1),
    'employer':  _s(fontSize=8.3, textColor=MDGRY, leading=11, spaceAfter=3),
    # bulletIndent=0 places the bullet; leftIndent=11 is where ALL text lines start.
    # This guarantees wrapped lines are flush with the first line of text, not the bullet.
    'bullet':    _s(fontSize=8.3, alignment=TA_JUSTIFY, leading=12.5,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.5),
    'oneliner':  _s(fontSize=8.2, textColor=MDGRY, leading=11, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.4, textColor=NAVY,
                    leading=11, spaceAfter=0),
    'skill_val': _s(fontSize=8.2, alignment=TA_JUSTIFY, leading=12, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=9, textColor=DKGRY,
                    leading=12, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.2, textColor=MDGRY, leading=11, spaceAfter=5),
    'lang':      _s(fontSize=8.5, leading=12, spaceAfter=2),
    'project':   _s(fontSize=8.2, alignment=TA_JUSTIFY, leading=12,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.5),
}


# ── Content helpers ─────────────────────────────────────────────────────────────
def accroche(text, kpi_line):
    inner = Paragraph(text + '<br/><br/>' + kpi_line, S['accroche'])
    t = Table([[inner]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LTBLUE),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 9),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 9),
    ]))
    return t


def exp_entry(title, company_line, bullets):
    """Returns a list of flowables for one experience entry."""
    elems = [
        KeepTogether([
            Paragraph(title, S['role']),
            Paragraph(company_line, S['employer']),
        ])
    ]
    for b in bullets:
        # <bullet> tag places • at bulletIndent=0; text wraps at leftIndent=11
        elems.append(Paragraph('<bullet>\u2022</bullet>' + b, S['bullet']))
    elems.append(Spacer(1, 5))
    return elems


def skill_row(cat, val):
    t = Table(
        [[Paragraph(cat + '\u00a0:', S['skill_cat']),
          Paragraph(val, S['skill_val'])]],
        colWidths=[3.6 * cm, TEXT_W - 3.6 * cm],
    )
    t.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return t


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'AI Product Manager\u2002|\u2002IA G\u00e9n\u00e9rative\u2002\u2022\u2002'
            'Syst\u00e8mes Multi-Agents\u2002\u2022\u2002LLM\u2002\u2022\u2002'
            'RAG\u2002\u2022\u2002Produits Data',
            S['subtitle']
        ),
        Spacer(1, 3),
        # LinkedIn and GitHub as clickable hyperlinks
        Paragraph(
            'debanjan186@gmail.com\u2002\u2022\u20020755807658\u2002\u2022\u2002Paris, France'
            '\u2002\u2022\u2002'
            '<a href="https://linkedin.com/in/dmazumdar/" color="#1B9AAA">linkedin.com/in/dmazumdar</a>'
            '\u2002\u2022\u2002'
            '<a href="https://github.com/dmazumdar186" color="#1B9AAA">github.com/dmazumdar186</a>',
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 7),
    ]

    # ── Accroche ────────────────────────────────────────────────────────────────
    st.append(accroche(
        "AI Product Manager avec 14 ans d\u2019exp\u00e9rience en environnements data-intensifs, "
        "sp\u00e9cialis\u00e9 dans la conception et le d\u00e9ploiement de capacit\u00e9s IA g\u00e9n\u00e9ratives "
        "en production (LLM, RAG, syst\u00e8mes multi-agents). Expert en cadrage de fonctionnalit\u00e9s IA "
        "complexes \u2014 de la discovery \u00e0 la mise en production \u2014 avec une ma\u00eetrise des enjeux "
        "\u00e9thiques, r\u00e9glementaires (RGPD) et de gouvernance.",
        "<b>R\u00e9sultats\u00a0:</b>\u2002+30\u202f% adoption\u2002\u2022\u2002+20\u202f% CSAT\u2002"
        "\u2022\u2002\u221240\u202f% latence\u2002\u2022\u2002\u221235\u202f% cycles d\u2019it\u00e9ration"
        "\u2002\u2022\u2002+40\u202f% adoption BU",
    ))
    st.append(Spacer(1, 9))

    # ── Expériences professionnelles ────────────────────────────────────────────
    st.append(SectionHeader('Exp\u00e9riences Professionnelles'))
    st.append(Spacer(1, 5))

    for item in exp_entry(
        'AI Product Manager',
        'Wiser Solutions, Paris\u2002|\u2002Nov. 2022 \u2013 Pr\u00e9sent',
        [
            "Con\u00e7u et d\u00e9ploy\u00e9 des capacit\u00e9s IA g\u00e9n\u00e9ratives en production "
            "(triage, recommandation, support client RAG, alertes intelligentes) avec OpenAI Assistants, "
            "Claude et syst\u00e8mes multi-agents (MCP, A2A) \u2192 "
            "<b>\u221240\u202f% latence, +25\u202f% pr\u00e9cision, +25\u202f% adoption</b>",

            "D\u00e9fini la vision IA et la roadmap de capacit\u00e9s avec hypoth\u00e8ses de valeur, "
            "crit\u00e8res go/no-go et plans de rollback\u202f; align\u00e9 <b>5 \u00e9quipes cross-BU</b> "
            "(Data/AI, MLOps, architecture, s\u00e9curit\u00e9, m\u00e9tier) sur une vision commune",

            "R\u00e9dig\u00e9 des PRDs orient\u00e9s IA (contrats API/donn\u00e9es, seuils d\u2019\u00e9valuation, "
            "gestion du non-d\u00e9terminisme, RGPD/privacy-by-design) et pilot\u00e9 les revues de "
            "faisabilit\u00e9 technique avec les \u00e9quipes Data/AI",

            "Orchestr\u00e9 le d\u00e9ploiement GTM mondial avec plans d\u2019enablement et playbooks "
            "terrain \u2192 <b>+40\u202f% adoption BU, +30\u202f% adoption utilisateur, +20\u202f% CSAT</b>",

            "Mis en place des dashboards analytics (usage/couverture/qualit\u00e9) et signaux "
            "op\u00e9rationnels (drift, incidents) \u2192 "
            "<b>+25\u201330\u202f% pr\u00e9cision de livraison, \u221225\u202f% ambigu\u00eft\u00e9</b> "
            "en sprint via DoR/DoD et QA pr\u00e9-prod",
        ]
    ):
        st.append(item)

    for item in exp_entry(
        'Data Product Manager',
        'InfoTnT, Paris\u2002|\u2002Juin 2021 \u2013 Nov. 2022',
        [
            "Pilot\u00e9 la discovery produit pour un moteur de recommandation data-driven "
            "(quant/qual, JTBD) \u2192 "
            "<b>\u221235\u202f% cycles d\u2019it\u00e9ration, +25\u202f% ad\u00e9quation post-lancement</b>",

            "Traduit les enjeux m\u00e9tiers en capacit\u00e9s backend, \u00e9pics et contrats de "
            "donn\u00e9es avec m\u00e9triques de succ\u00e8s et contraintes d\u2019int\u00e9gration",

            "Standardis\u00e9 les prompts, templates et proc\u00e9dures de versioning pour les "
            "composants IA \u2192 comportements pr\u00e9dictibles et d\u00e9ploiements fiables\u202f; "
            "coordonn\u00e9 les releases via PRDs/RFCs et QA fonctionnelle",
        ]
    ):
        st.append(item)

    for item in exp_entry(
        'Senior Data Product Owner',
        'Pitney Bowes Inc, Pune\u2002|\u2002Avr. \u2013 Sept. 2019',
        [
            "R\u00e9duit le time-to-market de <b>\u221220\u202f%</b> en cartographiant les "
            "d\u00e9pendances cross-squads et en am\u00e9liorant la cadence de release",

            "Renforc\u00e9 la stabilit\u00e9 op\u00e9rationnelle via des checklists pr\u00e9-prod, "
            "indicateurs d\u2019incidents et revues RAID structur\u00e9es",
        ]
    ):
        st.append(item)

    for item in exp_entry(
        'Senior Data Product Owner',
        'Evolent International, Pune\u2002|\u2002Juin 2018 \u2013 F\u00e9v. 2019',
        [
            "Am\u00e9lior\u00e9 la scalabilit\u00e9 et la performance de la plateforme "
            "(<b>+30\u202f%</b>) par l\u2019introduction de SLA/SLO pour arbitrer les priorit\u00e9s "
            "run/change\u202f; int\u00e9gr\u00e9 des checkpoints gouvernance et QA dans le flux de livraison",
        ]
    ):
        st.append(item)

    for item in exp_entry(
        'Senior Product Owner',
        'Avaya India Pvt Ltd, Pune\u2002|\u2002Juil. 2015 \u2013 Mars 2018',
        [
            "Acc\u00e9l\u00e9r\u00e9 la v\u00e9locit\u00e9 de livraison (<b>+30\u202f%</b>) via discipline "
            "Scrum renforc\u00e9e et alignement OKR \u2194 roadmap\u202f; r\u00e9duit l\u2019instabilit\u00e9 "
            "des exigences (<b>\u221225\u202f%</b>) pour am\u00e9liorer la pr\u00e9paration aux releases",
        ]
    ):
        st.append(item)

    # One-liner roles
    st.append(Paragraph(
        'QA Engineer / Release Coordinator\u2002\u2014\u2002'
        'IDrive India Pvt Ltd, Bengaluru\u2002|\u2002Avr. 2013 \u2013 Juil. 2015',
        S['oneliner']
    ))
    st.append(Paragraph(
        'Software Engineer\u2002\u2014\u2002'
        'Tata Consultancy Services, Bengaluru\u2002|\u2002Nov. 2010 \u2013 Mars 2013',
        S['oneliner']
    ))
    st.append(Spacer(1, 8))

    # ── Compétences ─────────────────────────────────────────────────────────────
    # KeepTogether forces the entire section (header + all rows) onto the same page,
    # preventing the header from being stranded at the bottom of page 1.
    competences = [
        SectionHeader('Comp\u00e9tences'),
        Spacer(1, 5),
        skill_row(
            'IA & GenAI',
            'LLM, RAG, Agentic AI, Syst\u00e8mes Multi-Agents, OpenAI Assistants, Claude, MCP, A2A, '
            'ML supervis\u00e9/non supervis\u00e9, Frameworks d\u2019\u00e9valuation IA '
            '(pr\u00e9cision, coh\u00e9rence, robustesse), gestion du non-d\u00e9terminisme',
        ),
        skill_row(
            'Product Mgt',
            'Vision & Roadmap, Discovery (quant/qual, JTBD), PRD, Contrats API/donn\u00e9es, '
            'Backlog, KPI/OKR, A/B tests, DoR/DoD, Enablement & GTM',
        ),
        skill_row(
            'Gouvernance',
            'RGPD/privacy-by-design, contr\u00f4le d\u2019acc\u00e8s, pistes d\u2019audit, '
            'souverainet\u00e9 technologique, \u00e9thique IA',
        ),
        skill_row(
            'Collaboration',
            'Cross-fonctionnel (Data/AI, D\u00e9v, CSM, Sales, MLOps, S\u00e9curit\u00e9), '
            'animation d\u2019ateliers, stakeholder management',
        ),
        skill_row(
            'Outils',
            'Jira, Confluence, Google AntiGravity, N8N, Make, Figma, Miro, Mixpanel, SQL, '
            'GenAI APIs (OpenAI, Google, Anthropic)',
        ),
        Spacer(1, 8),
    ]
    st.append(KeepTogether(competences))

    # ── Formation ────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Formation'))
    st.append(Spacer(1, 5))
    st.append(Paragraph('MSc International Strategic Business', S['edu_title']))
    st.append(Paragraph(
        'Toulouse Business School, Paris\u2002|\u20022019\u20132021', S['edu_sub']))
    st.append(Paragraph('BE Information Technology Engineering', S['edu_title']))
    st.append(Paragraph(
        'CMR Institute of Technology, Bengaluru\u2002|\u20022006\u20132010', S['edu_sub']))

    # ── Langues ──────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Langues'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>Anglais</b>\u2002: Bilingue\u2002\u2022\u2002'
        '<b>Fran\u00e7ais</b>\u2002: Bilingue\u2002\u2022\u2002'
        '<b>Hindi</b>\u2002: Natif\u2002\u2022\u2002'
        '<b>Bengali</b>\u2002: Natif',
        S['lang']
    ))
    st.append(Spacer(1, 8))

    # ── Projets personnels ───────────────────────────────────────────────────────
    st.append(SectionHeader('Projets Personnels'))
    st.append(Spacer(1, 5))

    for p in [
        # ProdCraft with clickable YouTube link
        '<a href="https://www.youtube.com/@ProdCraft" color="#1B9AAA">ProdCraft</a> '
        '(YouTube, sept. 2025\u2013pr\u00e9sent)\u2002: Cha\u00eene ed-tech d\u00e9di\u00e9e '
        'aux futurs Product Managers \u2014 fondamentaux &amp; bonnes pratiques',
        'G\u00e9n\u00e9rateur de lettres de motivation narratives \u2014 GPT Plugin (f\u00e9v. 2025)',
        'Optimiseur de CV pour ATS et RH \u2014 GPT Plugin (mars 2025)',
    ]:
        st.append(Paragraph('<bullet>\u2022</bullet>' + p, S['project']))

    return st


# ── Build PDF ────────────────────────────────────────────────────────────────────
def build_cv(output: Path):
    doc = BaseDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        topMargin=MARGIN_TB,
        bottomMargin=MARGIN_TB,
    )
    frame = Frame(
        MARGIN_LR, MARGIN_TB,
        TEXT_W, PAGE_H - 2 * MARGIN_TB,
        id='main', showBoundary=0,
    )
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
    doc.build(build_story())


# ── CLI ──────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--company', default='sahar')
    parser.add_argument('--role',    default='AI Product Manager')
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    tmp  = root / '.tmp'
    tmp.mkdir(exist_ok=True)

    company = args.company.lower().replace(' ', '_')
    out = tmp / f'cv_{company}_debanjan_mazumdar.pdf'

    print(f"Generating CV for: {args.role} @ {args.company}")
    build_cv(out)

    size_kb = out.stat().st_size / 1024
    print(f"Done: {out}  ({size_kb:.0f} KB)")
    print("Open the PDF and verify it is exactly 2 pages.")


if __name__ == '__main__':
    main()
