#!/usr/bin/env python3
"""
cv_builder_pm_fr.py
description: Generate the ATS-optimized, French-language, GENERIC Senior-Product-Manager PDF CV
    for Debanjan Mazumdar (PM-first positioning; AI kept as one strength). Same teal reportlab
    template as cv_builder.py; only build_story() content differs. Bullets follow the
    "Result-first XYZ" contract (metric-first, then method carrying JD keywords).
inputs: --out (path; default .tmp/cv_pm_master_debanjan_mazumdar.pdf)
outputs: the PDF at --out (exactly 2 pages)

Numbers reconciled to personal_brand/metrics_canonical.md. Client "Accessory Masters" is NEVER
named -> "cabinet outbound a haute velocite".

Usage:
    py execution/personal_workflows/cv_builder_pm_fr.py --out ".tmp/cv_pm_fr.pdf"

Dependencies: pip install reportlab
"""

import argparse
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

# ── Colours ────────────────────────────────────────────────────────────────────
NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT, FONT_BOLD = _register_fonts()


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


def _s(**kw):
    return make_style(FONT, **kw)


S = {
    'name':      _s(fontName=FONT_BOLD, fontSize=22, textColor=NAVY, leading=26, spaceAfter=2),
    'subtitle':  _s(fontSize=9.6, textColor=TEAL, leading=13, spaceAfter=3),
    'contact':   _s(fontSize=8.1, textColor=MDGRY, leading=11, spaceAfter=0),
    'accroche':  _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=13),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.3, textColor=NAVY, leading=12, spaceAfter=1),
    'employer':  _s(fontSize=8.3, textColor=MDGRY, leading=11, spaceAfter=3),
    'bullet':    _s(fontSize=8.3, alignment=TA_JUSTIFY, leading=12.5,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.5),
    'oneliner':  _s(fontSize=8.2, textColor=MDGRY, leading=11, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.4, textColor=NAVY, leading=11, spaceAfter=0),
    'skill_val': _s(fontSize=8.2, alignment=TA_JUSTIFY, leading=12, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=9, textColor=DKGRY, leading=12, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.2, textColor=MDGRY, leading=11, spaceAfter=5),
    'lang':      _s(fontSize=8.5, leading=12, spaceAfter=2),
    'project':   _s(fontSize=8.2, alignment=TA_JUSTIFY, leading=12,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.5),
}


def _accroche(text, kpi_line):
    return accroche(text, kpi_line, style=S['accroche'], text_w=TEXT_W, bg_color=LTBLUE)


def _exp_entry(title, company_line, bullets):
    return exp_entry(title, company_line, bullets,
                     role_style=S['role'], employer_style=S['employer'],
                     bullet_style=S['bullet'], keep_first_bullet=False)


def _skill_row(cat, val):
    return skill_row(cat, val, cat_style=S['skill_cat'], val_style=S['skill_val'],
                     text_w=TEXT_W, separator=' :')


def build_story():
    st = []

    # ── En-tête ─────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'Senior Product Manager | Discovery produit • Roadmap &amp; OKR • '
            'Delivery Agile • Data-driven • B2B &amp; B2C SaaS',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • 0755807658 • Paris, France'
            ' • '
            '<a href="https://linkedin.com/in/dmazumdar/" color="#1B9AAA">linkedin.com/in/dmazumdar</a>'
            ' • '
            '<a href="https://github.com/dmazumdar186" color="#1B9AAA">github.com/dmazumdar186</a>',
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 7),
    ]

    # ── Accroche ────────────────────────────────────────────────────────────────
    st.append(_accroche(
        "Senior Product Manager avec <b>15 ans</b> d’expérience à livrer des produits B2B et B2C "
        "à forte composante data (SaaS, e-commerce, plateformes IA). Je pilote le cycle de vie "
        "produit complet — discovery continue (recherche utilisateur, JTBD, quant/qual) → roadmap "
        "et OKR → delivery Agile → mesure post-lancement — en transformant des besoins métier "
        "ambigus en résultats livrés et mesurables. À l’aise avec les équipes techniques comme "
        "avec le COMEX ; je fiabilise la livraison parce que je sais poser le business case et "
        "cadrer le build.",
        "<b>Impact :</b> +45 % d’adoption  •  +20 % CSAT  •  $1M+ de pipeline qualifié",
    ))
    st.append(Spacer(1, 9))

    # ── Expériences professionnelles ────────────────────────────────────────────
    st.append(SectionHeader('Expériences Professionnelles'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager — IA &amp; Data Intelligence — Wiser Solutions',
        'B2B SaaS · Market Intelligence, Paris | Nov. 2022 – Présent',
        [
            "<b>+45 % d’adoption et −55 % de latence p95</b> — en pilotant le cycle de vie complet "
            "de capacités data &amp; IA (triage, recommandation, support RAG, alertes "
            "intelligentes) : PRDs avec critères d’acceptation, data readiness et contrats API.",

            "Mené une discovery continue (entretiens utilisateurs, JTBD, quant/qual), défini les "
            "OKR et aligné 5 squads cross-fonctionnels sur une roadmap priorisée (gates go/no-go, "
            "plans de rollback) — générant <b>+40 % d’adoption BU et +20 % CSAT</b> sur un "
            "déploiement mondial.",

            "<b>−25 % d’ambiguïté en sprint et +25–30 % de précision de livraison</b> — via "
            "expérimentation (A/B tests, feature flags, déploiements progressifs) sur dashboards "
            "Mixpanel usage/qualité/drift, avec DoR/DoD, QA pré-prod et RGPD/privacy-by-design.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Consultant Produit Indépendant — '
        '<a href="https://prodcraft.fyi" color="#1B9AAA">ProdCraft</a> (Studio Produit IA)',
        'Paris (Freelance, en parallèle de Wiser) | Janv. 2026 – Présent',
        [
            "<b>$1M+ de pipeline qualifié</b> et <b>~200K$/an de coût SDR</b> remplacés — en "
            "amenant un produit outbound autonome de la discovery au lancement pour un cabinet "
            "outbound à haute vélocité, avec automatisation des réponses et SLA hot-lead de 3 h.",

            "<b>85K$ traités les 3 premiers mois</b>, après avoir co-construit et lancé une "
            "marketplace Stripe Connect à deux faces (React + Node + Postgres) avec une agence "
            "partenaire — cadrage, roadmap et go-to-market.",

            "<b>12+ produits livrés de bout en bout</b> — missions indépendantes et clients — à "
            "une <b>médiane &lt;30 jours</b>, dont un SaaS CV-optimizer multilingue et un CLI "
            "d’audit de code ; discovery, PRDs et release gates.",

            "Un seul opérateur senior sur chaque mission, de la discovery utilisateur au "
            "lancement — roadmap, contrats de données et alignement des parties prenantes ; "
            "tout le code et l’IP remis au client.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager — Produits Data &amp; Recommandation — InfoTnT',
        'B2B SaaS, Paris | Juin 2021 – Nov. 2022',
        [
            "<b>−35 % de cycles d’itération et +25 % d’adéquation produit-marché post-lancement</b> "
            "— en menant une discovery structurée (entretiens utilisateurs, analyse d’usage, "
            "ateliers JTBD) et en traduisant les insights en roadmap et backlog priorisés.",

            "Rédigé des PRDs détaillés et user stories avec critères d’acceptation, contrats de "
            "données et contraintes API, et standardisé les playbooks d’expérimentation — pour un "
            "delivery fiable et la prévention des régressions.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'Enterprise SaaS, Pune | Avr. – Sept. 2019',
        [
            "<b>−20 % de time-to-market</b> — en cartographiant les dépendances cross-squads, en "
            "clarifiant les critères de sortie, en renforçant la cadence Scrum et via checklists "
            "pré-prod et revues RAID structurées.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'Healthcare SaaS, Pune | Juin 2018 – Fév. 2019',
        [
            "<b>+30 % de scalabilité et de performance plateforme</b> — en introduisant des "
            "SLA/SLO pour arbitrer les priorités run/change et en intégrant gouvernance et "
            "checkpoints QA dans le flux de livraison.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner — Plateforme Communications — Avaya India',
        'Enterprise Software, Pune | Juil. 2015 – Mars 2018',
        [
            "<b>+30 % de vélocité de livraison et −25 % d’instabilité des exigences</b> — en "
            "renforçant la discipline Scrum, les revues de sprint structurées et l’alignement "
            "OKR ↔ roadmap sur 3 squads.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2010 – 2015 :</b> Software Engineer '
        '(Tata Consultancy Services, Bengaluru | Nov. 2010 – Mars 2013) → '
        'QA Engineer / Release Coordinator (IDrive India, Bengaluru | Avr. 2013 – Juil. 2015) — '
        '<i>fondations en systèmes distribués, QA et release management</i>',
        S['oneliner']
    ))
    st.append(Spacer(1, 8))

    # ── Compétences ─────────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Compétences'),
        Spacer(1, 5),
        _skill_row(
            'Product Mgt',
            'Discovery produit (recherche utilisateur, entretiens, JTBD, quant/qual) • Stratégie '
            '&amp; Vision produit • Roadmap &amp; OKR • PRD &amp; user stories • Critères '
            'd’acceptation • Priorisation backlog (valeur/risque/effort) • A/B testing &amp; '
            'expérimentation • Cycle de vie produit • Expérience client (UX) • GTM &amp; '
            'enablement • Conception KPI/métriques • Gestion des parties prenantes • '
            'Ownership &amp; leadership produit',
        ),
        _skill_row(
            'Agile &amp; Delivery',
            'Scrum • Kanban • Sprint planning &amp; rétrospectives • DoR/DoD • Release gates '
            '&amp; rollback • Collaboration &amp; leadership cross-fonctionnels • Gestion des '
            'dépendances • QA pré-prod',
        ),
        _skill_row(
            'Data &amp; IA',
            'Contrats de données &amp; API readiness • Analytics (Mixpanel) • SQL • Monitoring '
            'drift/qualité • Conception produit IA/GenAI (LLM, RAG, Agentic AI) • Frameworks '
            'd’évaluation ML',
        ),
        _skill_row(
            'Gouvernance',
            'RGPD/privacy-by-design • Contrôle d’accès • Pistes d’audit • Éthique IA • '
            'Conformité réglementaire',
        ),
        _skill_row(
            'Outils',
            'Jira • Confluence • Figma • Miro • Mixpanel • Amplitude • Notion • SQL • N8N • Make • '
            'GenAI APIs (OpenAI, Anthropic, Google)',
        ),
        Spacer(1, 8),
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
        '<b>Hindi</b> : Natif • <b>Bengali</b> : Natif',
        S['lang']
    ))
    st.append(Spacer(1, 8))

    # ── Projets sélectionnés ────────────────────────────────────────────────────
    st.append(SectionHeader('Projets Sélectionnés'))
    st.append(Spacer(1, 5))
    for p in [
        '<a href="https://cv-optimizer.pages.dev" color="#1B9AAA"><b>CV Optimizer</b></a> '
        '(SaaS en ligne) — application multilingue qui score un CV face à une offre et génère un '
        'CV &amp; une lettre de motivation optimisés ATS ; produit piloté de bout en bout '
        '(discovery → delivery).',

        '<b>Marketplace à deux faces</b> (avec une agence partenaire, sous NDA) — plateforme de '
        'paiement Stripe Connect traitant <b>85K$ les 3 premiers mois</b> ; React + Node + Postgres.',

        '<a href="https://prodcraft.fyi" color="#1B9AAA"><b>ProdCraft</b></a> '
        '(studio produit IA, prodcraft.fyi) — studio indépendant livrant des produits IA en '
        'production pour fondateurs et équipes à une <b>médiane &lt;30 jours</b>, de la discovery '
        'au lancement.',
    ]:
        st.append(Paragraph('<bullet>•</bullet>' + p, S['project']))

    return st


def build_cv(output: Path):
    build_cv_doc(output, build_story(), margin_lr=MARGIN_LR, margin_tb=MARGIN_TB)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    tmp = root / '.tmp'
    tmp.mkdir(exist_ok=True)
    out = args.out or (tmp / 'cv_pm_master_debanjan_mazumdar.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)

    print("Generating GENERIC Senior-PM French CV")
    build_cv(out)
    size_kb = out.stat().st_size / 1024
    print(f"Done: {out}  ({size_kb:.0f} KB)")
    print("Verifier: exactement 2 pages.")


if __name__ == '__main__':
    main()
