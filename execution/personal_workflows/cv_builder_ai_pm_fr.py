#!/usr/bin/env python3
"""
cv_builder_ai_pm_fr.py
description: Generate the ATS-optimized, French-language, AI PM GENERIC variant of the
    Senior-Product-Manager PDF CV for Debanjan Mazumdar — AI-first framing for Senior AI PM /
    agentic-automation roles. 60/40 product-vs-build balance. Same teal reportlab template as
    cv_builder_pm_fr.py (imports shared primitives from cv_builder_core.py); only build_story()
    content and the header/subtitle differ.
inputs: --out (path; default .tmp/cv_ai_pm_debanjan_mazumdar_fr.pdf)
outputs: the PDF at --out (exactly 2 pages)

Numbers reconciled to personal_brand/metrics_canonical.md (Wiser = +45%/-55%; outbound =
1M$+/~200K$/an; marketplace = 85K$/3mo; 12+ produits IA livres; mediane <30 jours; 15 ans).

Font note: this container has no Windows Arial, so cv_builder_core._register_fonts() falls back
to base-14 Helvetica, whose bulletFontName default and un-embedded glyph table mangle bullets and
drop French accents on text extraction. This script stages DejaVu Sans under the arial.ttf /
arialbd.ttf names core's own font lookup expects (via a local WINDIR override) so core registers
real embedded TrueType glyphs under its usual 'CV' / 'CV-Bold' names, then also points each
bullet-style's bulletFontName at that same face — cv_builder_core.py itself is not modified.

Usage:
    python3 execution/personal_workflows/cv_builder_ai_pm_fr.py --out ".tmp/cv_ai_pm_fr.pdf"

Dependencies: pip install reportlab
"""

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from cv_builder_core import (
    A4, HexColor, cm,
    Paragraph, Spacer, KeepTogether, HRFlowable,
    TA_JUSTIFY,
    _register_fonts, make_style,
    accroche, exp_entry, skill_row, build_cv_doc,
    SectionHeader as _SectionHeaderBase,
)

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_LR = 1.8 * cm
MARGIN_TB = 1.5 * cm
TEXT_W = PAGE_W - 2 * MARGIN_LR

# ── Colours (same palette as cv_builder_pm_fr.py) ───────────────────────────────
NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')


# ── Fonts ──────────────────────────────────────────────────────────────────────
def _register_ai_pm_fonts():
    """Register (FONT, FONT_BOLD) via cv_builder_core._register_fonts(), staging a DejaVu
    Sans fallback under the arial.ttf / arialbd.ttf names when the real Windows fonts aren't
    present (any non-Windows box). This makes core embed real TrueType glyphs — fixing bullet
    (cid:127) mangling and dropped accented characters on pdfplumber extraction — without
    editing core.
    """
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    have_real_arial = (
        os.path.exists(os.path.join(win_fonts, 'arial.ttf'))
        and os.path.exists(os.path.join(win_fonts, 'arialbd.ttf'))
    )
    if not have_real_arial:
        dejavu_reg = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        dejavu_bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if os.path.exists(dejavu_reg) and os.path.exists(dejavu_bold):
            stage = Path(tempfile.gettempdir()) / 'cv_ai_pm_fake_winfonts' / 'Fonts'
            stage.mkdir(parents=True, exist_ok=True)
            for src, name in ((dejavu_reg, 'arial.ttf'), (dejavu_bold, 'arialbd.ttf')):
                dst = stage / name
                if not dst.exists():
                    shutil.copy(src, dst)
            os.environ['WINDIR'] = str(stage.parent)
    return _register_fonts()


FONT, FONT_BOLD = _register_ai_pm_fonts()


# ── Section header (same teal-accent style as pm_fr) ────────────────────────────
class SectionHeader(_SectionHeaderBase):
    HEIGHT = 19

    def __init__(self, text, width=TEXT_W):
        super().__init__(text, width)

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
    return make_style(FONT, **kw)


S = {
    'name':      _s(fontName=FONT_BOLD, fontSize=21, textColor=NAVY, leading=25, spaceAfter=2),
    'subtitle':  _s(fontSize=9.2, textColor=TEAL, leading=12.5, spaceAfter=3),
    'contact':   _s(fontSize=7.9, textColor=MDGRY, leading=11, spaceAfter=0),
    'accroche':  _s(fontSize=8.3, alignment=TA_JUSTIFY, leading=12.5),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.1, textColor=NAVY, leading=11.8, spaceAfter=1),
    'employer':  _s(fontSize=8.1, textColor=MDGRY, leading=10.8, spaceAfter=3),
    'bullet':    _s(fontSize=8.1, alignment=TA_JUSTIFY, leading=12,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
    'oneliner':  _s(fontSize=8.0, textColor=MDGRY, leading=10.8, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.2, textColor=NAVY, leading=10.8, spaceAfter=0),
    'skill_val': _s(fontSize=8.0, alignment=TA_JUSTIFY, leading=11.6, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=8.8, textColor=DKGRY, leading=11.8, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.0, textColor=MDGRY, leading=10.8, spaceAfter=5),
    'lang':      _s(fontSize=8.3, leading=11.6, spaceAfter=2),
    'project':   _s(fontSize=8.0, alignment=TA_JUSTIFY, leading=11.6,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
}


def _accroche(text, kpi_line):
    return accroche(text, kpi_line, style=S['accroche'], text_w=TEXT_W, bg_color=LTBLUE)


def _exp_entry(title, company_line, bullets):
    return exp_entry(title, company_line, bullets,
                     role_style=S['role'], employer_style=S['employer'],
                     bullet_style=S['bullet'], keep_first_bullet=False)


def _skill_row(cat, val):
    return skill_row(cat, val, cat_style=S['skill_cat'], val_style=S['skill_val'],
                     text_w=TEXT_W, cat_col_w=3.3, separator=' :')


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── En-tête ─────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'Senior Product Manager — IA &amp; Automatisation Agentique | LLM · RAG · Agents '
            'IA | 15 ans en SaaS B2B',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • +33 7 55 80 76 58 • Paris, France'
            ' • '
            '<a href="https://linkedin.com/in/dmazumdar/" color="#1B9AAA">linkedin.com/in/dmazumdar</a>'
            ' • '
            '<a href="https://github.com/dmazumdar186" color="#1B9AAA">github.com/dmazumdar186</a>'
            ' • '
            '<a href="https://prodcraft.fyi" color="#1B9AAA">prodcraft.fyi</a>',
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 6),
    ]

    # ── Accroche ────────────────────────────────────────────────────────────────
    st.append(_accroche(
        "Senior Product Manager, <b>15 ans</b> en SaaS B2B, spécialisé produits <b>IA, GenAI "
        "et automatisation agentique</b>. Je mène la product discovery avec les équipes "
        "métier, défends la priorisation au niveau <b>VP/C-level</b>, et reste hands-on — "
        "<b>LLM, RAG, orchestration d'agents</b>, low-code et Python — quand construire est "
        "le chemin le plus court vers l'impact. <b>12+ produits IA livrés</b>, médiane "
        "<b>&lt;30 jours</b>.",
        "<b>Impact :</b> <b>+45%</b> d'adoption • <b>−55%</b> latence p95 • <b>~200K$/an</b> "
        "de coûts automatisés • <b>1M$+</b> de pipeline qualifié",
    ))
    st.append(Spacer(1, 8))

    # ── Expérience professionnelle ──────────────────────────────────────────────
    st.append(SectionHeader('Expérience Professionnelle'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, IA &amp; Data Intelligence — Wiser Solutions',
        'B2B SaaS · Retail &amp; Digital-Commerce Intelligence · Paris | Nov. 2022 – Aujourd\u2019hui',
        [
            "Responsable de bout en bout de la ligne produit <b>IA/GenAI</b> (assistant RAG "
            "sur APIs OpenAI/Anthropic, recommandation, alerting intelligent) : discovery → "
            "PRD → <b>gates d'évaluation LLM</b> (jeu de test golden, LLM-as-judge) → "
            "rollout — <b>+45% d'adoption, −55% de latence p95</b>.",

            "Pilotage du <b>déploiement GenAI global</b> : roadmap, OKR, <b>budget de "
            "150K$</b>, revues go/no-go avec le <b>CPO</b> — <b>+40% d'adoption BU, +20% de "
            "CSAT</b>.",

            "Alignement de <b>5 squads cross-fonctionnelles</b> (Paris, US, Inde) sur une "
            "roadmap priorisée unique — sans autorité hiérarchique.",

            "<b>Expérimentation</b> (A/B tests, feature flags, monitoring de drift) avec "
            "garde-fous <b>RGPD / privacy-by-design</b> — <b>−25% d'ambiguïté en sprint, "
            "+25–30% de précision de delivery</b>.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Fondateur &amp; Consultant Produit IA — '
        '<a href="https://prodcraft.fyi" color="#1B9AAA">ProdCraft</a> (AI Product Studio)',
        'Paris (indépendant, en parallèle de Wiser) | Janv. 2026 – Aujourd\u2019hui',
        [
            "<b>Moteur outbound autonome</b> (pipeline agentique : classification des "
            "réponses par <b>Claude</b>, orchestration Cloudflare Workers, 32 boîtes mail, "
            "leads chauds traités sous 3h) — <b>1M$+ de pipeline qualifié</b>, "
            "<b>~200K$/an de coût SDR remplacé</b>.",

            "Co-lancement d'une <b>marketplace Stripe Connect</b> (React + Node + Postgres) — "
            "<b>85K$ traités en 3 mois</b>.",

            "<b>12+ produits IA livrés</b>, médiane <b>&lt;30 jours</b> — SaaS d'optimisation "
            "de CV multilingue, app de coaching GenAI, CLI d'audit de code — discovery, PRD "
            "et release gates.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Produits Data &amp; Recommandation — InfoTnT',
        'B2B SaaS · Paris | Juin 2021 – Nov. 2022',
        [
            "Product discovery structurée (entretiens, <b>JTBD</b>, recherche utilisateur, "
            "analytics d'usage) → roadmap et backlog priorisés — <b>−35% de cycles "
            "d'itération, +25% d'adéquation produit-marché</b>.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2019 – 2021 :</b> MSc International Strategic Business — Toulouse Business '
        'School, Paris (temps plein).',
        S['oneliner']
    ))
    st.append(Spacer(1, 4))

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'Shipping &amp; Logistics SaaS · Pune | Avr. 2019 – Sept. 2019',
        [
            "<b>−20% de time-to-market</b> via cartographie des dépendances, cadence Scrum et "
            "revues RAID.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'Healthcare SaaS · Pune | Juin 2018 – Févr. 2019',
        [
            "<b>+30% de scalabilité de la plateforme</b> via frameworks SLA/SLO et "
            "gouvernance QA.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner, Plateforme Communications — Avaya India',
        'Enterprise software · Pune | Juil. 2015 – Mars 2018',
        [
            "<b>+30% de vélocité, −25% d'instabilité des exigences</b> sur <b>3 squads</b> via "
            "discipline Scrum et alignement OKR–roadmap.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2010 – 2015 :</b> Ingénieur logiciel (Tata Consultancy Services) → QA / Release '
        'Coordinator (IDrive) — <i>fondations en systèmes distribués</i>',
        S['oneliner']
    ))
    st.append(Spacer(1, 7))

    # ── Compétences ─────────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Compétences'),
        Spacer(1, 5),
        _skill_row(
            'IA &amp; Agentique',
            'LLM (OpenAI, Anthropic, Google) • RAG • Agents IA &amp; orchestration • Prompt '
            'engineering • Évaluation LLM &amp; garde-fous • MCP • Gouvernance des coûts LLM',
        ),
        _skill_row(
            'Automatisation',
            'n8n • Make • Python • SQL • Cloudflare Workers • Modal • Intégrations API • CI/CD '
            '• Claude Code (développement agentique)',
        ),
        _skill_row(
            'Product Management',
            'Product discovery (recherche utilisateur, entretiens, JTBD) • Stratégie produit • '
            'Roadmap &amp; OKR • PRD &amp; user stories • Priorisation backlog • A/B testing '
            '&amp; expérimentation • Analytics (Mixpanel, Amplitude) • UX • '
            'Go-to-market • Agile (Scrum, Kanban) • Cycle de vie produit',
        ),
        _skill_row(
            'Leadership',
            'Management des parties prenantes VP/C-level • Collaboration cross-fonctionnelle • '
            'Conduite du changement &amp; adoption IA • Décisions data-driven • Exécution dans '
            'l\u2019ambiguïté',
        ),
        _skill_row(
            'Gouvernance',
            'RGPD / Privacy-by-design • AI Act • IA responsable • Pistes d\u2019audit',
        ),
        Spacer(1, 7),
    ]
    st.append(KeepTogether(competences))

    # ── Formation ────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Formation'))
    st.append(Spacer(1, 5))
    st.append(Paragraph('MSc International Strategic Business', S['edu_title']))
    st.append(Paragraph('Toulouse Business School, Paris | 2019–2021', S['edu_sub']))
    st.append(Paragraph('BE Information Technology Engineering', S['edu_title']))
    st.append(Paragraph('CMR Institute of Technology, Bengaluru | 2006–2010', S['edu_sub']))

    # ── Langues ──────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Langues'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>Anglais</b> : Bilingue (C2) • <b>Français</b> : Bilingue (C2) • '
        '<b>Hindi / Bengali</b> : Natif',
        S['lang']
    ))
    st.append(Spacer(1, 7))

    # ── Projets sélectionnés ────────────────────────────────────────────────────
    st.append(SectionHeader('Projets Sélectionnés'))
    st.append(Spacer(1, 5))
    for p in [
        '<a href="https://cv-optimizer.pages.dev" color="#1B9AAA"><b>CV Optimizer</b></a> '
        '(SaaS live — cv-optimizer.pages.dev) : scoring ATS multilingue + réécriture de CV ; '
        'build eval-first.',

        '<b>AgentUp</b> (live) : coaching par roleplay GenAI — LLM en streaming avec fallback, '
        'redaction PII côté client.',

        '<b>Job Search Engine</b> : agrégation multi-sources + ranking LLM (API France '
        'Travail, ingestion Gmail) — infra à 0$.',
    ]:
        st.append(Paragraph('<bullet>•</bullet>' + p, S['project']))

    return st


# ── Build PDF ────────────────────────────────────────────────────────────────────
def build_cv(output: Path):
    build_cv_doc(output, build_story(), margin_lr=MARGIN_LR, margin_tb=MARGIN_TB)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    tmp = root / '.tmp'
    tmp.mkdir(exist_ok=True)
    out = args.out or (tmp / 'cv_ai_pm_debanjan_mazumdar_fr.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)

    print("Generating AI PM GENERIC French CV")
    build_cv(out)
    size_kb = out.stat().st_size / 1024
    print(f"Done: {out}  ({size_kb:.0f} KB)")
    print("Vérifier : exactement 2 pages.")


if __name__ == '__main__':
    main()
