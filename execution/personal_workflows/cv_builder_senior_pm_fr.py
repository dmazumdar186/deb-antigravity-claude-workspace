#!/usr/bin/env python3
"""
cv_builder_senior_pm_fr.py
description: Generate the French GENERIC Senior Product Manager / Senior Product Manager IA PDF CV
    for Debanjan Mazumdar, built from a keyword model of 10 real FR postings (research in
    .tmp/jd_research/fr, 2026-10-22: Theodo x2, Yespark, Converteo, Evaneos, Thiga, Saint-Gobain,
    EDF, Hubvisory, TEKsystems). Core terms carried: priorisation, KPI / mesure d'impact, vision
    produit, roadmap, discovery, ROI / valeur business, parties prenantes, autonomie, rigueur,
    animation d'équipe, delivery et run, IA et data, IA dans le quotidien du PM. Style CV français :
    court, factuel, pas de première personne, chiffres clés en gras. Même template teal reportlab
    que cv_builder_ai_pm_fr.py (primitives cv_builder_core) ; aucun chiffre inventé.
inputs: --out (path; default .tmp/cv_senior_pm_debanjan_mazumdar_fr.pdf)
outputs: the PDF at --out (exactly 2 pages)

Usage:
    python3 execution/personal_workflows/cv_builder_senior_pm_fr.py --out ".tmp/cv_fr.pdf"

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

PAGE_W, PAGE_H = A4
MARGIN_LR = 1.8 * cm
MARGIN_TB = 1.5 * cm
TEXT_W = PAGE_W - 2 * MARGIN_LR

NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')
LINK   = '#1B9AAA'


def _register_fonts_with_fallback():
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    have_real_arial = (os.path.exists(os.path.join(win_fonts, 'arial.ttf'))
                       and os.path.exists(os.path.join(win_fonts, 'arialbd.ttf')))
    if not have_real_arial:
        reg = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if os.path.exists(reg) and os.path.exists(bold):
            stage = Path(tempfile.gettempdir()) / 'cv_senior_pm_fake_winfonts' / 'Fonts'
            stage.mkdir(parents=True, exist_ok=True)
            for src, name in ((reg, 'arial.ttf'), (bold, 'arialbd.ttf')):
                if not (stage / name).exists():
                    shutil.copy(src, stage / name)
            os.environ['WINDIR'] = str(stage.parent)
    return _register_fonts()


FONT, FONT_BOLD = _register_fonts_with_fallback()


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
    'name':      _s(fontName=FONT_BOLD, fontSize=21, textColor=NAVY, leading=25, spaceAfter=2),
    'subtitle':  _s(fontSize=9.2, textColor=TEAL, leading=12.5, spaceAfter=3),
    'contact':   _s(fontSize=7.9, textColor=MDGRY, leading=11, spaceAfter=0),
    'accroche':  _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=12.6),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.1, textColor=NAVY, leading=11.8, spaceAfter=1),
    'employer':  _s(fontSize=8.5, textColor=MDGRY, leading=12.6, spaceAfter=3),
    'bullet':    _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=12.6,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
    'oneliner':  _s(fontSize=8.5, textColor=MDGRY, leading=12.6, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.2, textColor=NAVY, leading=10.8, spaceAfter=0),
    'skill_val': _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=12.6, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=8.8, textColor=DKGRY, leading=11.8, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.0, textColor=MDGRY, leading=10.8, spaceAfter=5),
    'lang':      _s(fontSize=8.3, leading=11.6, spaceAfter=2),
    'project':   _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=12.6,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
}


def _accroche(text, kpi_line):
    return accroche(text, kpi_line, style=S['accroche'], text_w=TEXT_W, bg_color=LTBLUE)


def _exp_entry(title, company_line, bullets):
    return exp_entry(title, company_line, bullets, role_style=S['role'],
                     employer_style=S['employer'], bullet_style=S['bullet'], keep_first_bullet=True)


def _skill_row(cat, val):
    return skill_row(cat, val, cat_style=S['skill_cat'], val_style=S['skill_val'],
                     text_w=TEXT_W, cat_col_w=3.3, separator=' :')


def _link(url, text):
    return f'<a href="{url}" color="{LINK}">{text}</a>'


def build_story():
    st = []

    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'Senior Product Manager — Produits IA, Data &amp; Growth | SaaS B2B | '
            '<b>15 ans</b> de logiciel, <b>11</b> en produit',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • +33 7 55 80 76 58 • Paris'
            ' • ' + _link('https://linkedin.com/in/dmazumdar/', 'linkedin.com/in/dmazumdar')
            + ' • ' + _link('https://github.com/dmazumdar186', 'github.com/dmazumdar186')
            + ' • ' + _link('https://prodcraft.fyi', 'prodcraft.fyi'),
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 6),
    ]

    st.append(_accroche(
        "Senior Product Manager, <b>15 ans</b> dans le logiciel B2B dont <b>11</b> à porter des "
        "produits de bout en bout : Product Owner sur des plateformes d'entreprise, puis Senior "
        "PM produits IA, data et growth. Quatre ans de GenAI chez Wiser Solutions : assistant "
        "RAG lancé (<b>+45 %</b> d'adoption), offre IA pricée (<b>+18 %</b> d'ARPU), déploiement "
        "groupe de <b>150 K$</b> piloté. Diplôme d'ingénieur ; prototype dans Claude Code avant "
        "d'écrire la spec. Vise un poste de Senior PM, Senior PM IA ou Growth PM en SaaS B2B, "
        "Paris ou télétravail.",
        "<b>Résultats clés :</b> +45 % d'adoption • +18 % d'ARPU • +32 % de conversion "
        "essai-payant • −55 % de latence p95 • 1 M$+ de pipeline • ~200 K$/an de coûts "
        "supprimés",
    ))
    st.append(Spacer(1, 8))

    st.append(SectionHeader('Expérience professionnelle'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, IA &amp; Data Intelligence — Wiser Solutions',
        'SaaS B2B · Retail &amp; Digital-Commerce Intelligence · Paris | Nov. 2022 – Aujourd’hui',
        [
            "Lancé un assistant RAG sur APIs OpenAI et Anthropic, des entretiens JTBD et "
            "parcours Figma jusqu'à la mise en production : <b>+45 %</b> d'adoption, "
            "<b>−55 %</b> de latence p95.",

            "Défini le pricing et le packaging de l'offre IA (upsell product-led, tunnel "
            "Mixpanel) : <b>+18 %</b> d'ARPU.",

            "Piloté le déploiement GenAI du groupe (budget <b>150 K$</b>) : build vs. buy, "
            "go/no-go avec le CPO et les directions métier, acculturation des BU. Adoption BU "
            "<b>+40 %</b>, CSAT <b>+20 %</b>.",

            "Aligné <b>5</b> squads (tech, design, data) entre Paris, les États-Unis et l'Inde "
            "sur une seule roadmap priorisée, sans lien hiérarchique : ambiguïté en sprint "
            "<b>−25 %</b>, prévisibilité du delivery <b>+25 à 30 %</b>.",

            "Instauré des gates d'évaluation LLM, garde-fous et coût par appel comme critères "
            "de release ; mené A/B tests et lancements sous feature flags, RGPD dès la "
            "conception.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Fondateur &amp; Consultant Produit IA — ' + _link('https://prodcraft.fyi', 'ProdCraft'),
        'Studio produit IA indépendant, Paris (soirs et week-ends, en parallèle de Wiser) | '
        'Janv. 2026 – Aujourd’hui',
        [
            "Livré <b>12+</b> produits IA pour des clients, médiane <b>&lt;30 jours</b> du brief "
            "à la production, en portant discovery, PRD, MVP et release gate.",

            "Construit un pipeline outbound agentique (classification Claude, Cloudflare "
            "Workers, <b>32</b> boîtes mail, SLA <b>3 h</b>) : <b>1 M$+</b> de pipeline "
            "qualifié, ~<b>200 K$/an</b> de travail manuel remplacé.",

            "Fait du prototypage rapide un outil commercial : <b>6</b> sites de prospects "
            "reconstruits en concepts live avec deck de pitch, chacun de l'URL au site en ligne "
            "en <b>48 heures</b> (design niveau Figma, Cloudflare Pages).",

            "Conçu un système de sourcing de candidats pour un client recrutement (collecte "
            "multi-sources, vérification des preuves, sync Recruit CRM) : <b>≥90 %</b> de "
            "précision sur jeu étiqueté.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Produits Data &amp; Recommandation — InfoTnT',
        'SaaS B2B · Paris | Juin 2021 – Nov. 2022',
        [
            "Mis en place le product-led growth (essai self-serve, tests de pricing, tunnel "
            "Mixpanel) : <b>+32 %</b> de conversion essai-payant.",

            "Structuré la discovery continue (entretiens clients, JTBD / Outcome-Driven "
            "Innovation, analytics d'usage) et une roadmap priorisée : cycles d'itération "
            "<b>−35 %</b>, score d'adéquation produit-marché <b>+25 %</b>.",

            "Rédigé les PRD et parcours Figma du moteur de recommandation ; tenu le backlog "
            "dans Jira et Confluence.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2019 – 2021 :</b> MSc International Strategic Business (Bac+5), Toulouse Business '
        'School, Paris (temps plein, pause carrière pour études).',
        S['oneliner']
    ))
    st.append(Spacer(1, 4))

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'SaaS Shipping &amp; Logistics · Pune | Avr. 2019 – Sept. 2019',
        [
            "Réduit le time-to-market de <b>20 %</b> sur une release de plateforme data via "
            "cartographie des dépendances, cadence Scrum et revues de risques RAID.",

            "Tenu backlog et objectifs de sprint dans Jira pour une équipe data distribuée.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'SaaS Santé (secteur réglementé, payeurs et soignants US) · Pune | Juin 2018 – Févr. 2019',
        [
            "Amélioré la scalabilité de la plateforme de <b>30 %</b> en instaurant un cadre "
            "SLA/SLO et une gouvernance QA sur les produits data.",

            "Adopté JTBD / Outcome-Driven Innovation pour la discovery, sous contraintes de "
            "conformité et de confidentialité santé.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner, Plateforme Communications — Avaya India',
        'Logiciel d’entreprise · Pune | Juil. 2015 – Mars 2018',
        [
            "Augmenté la vélocité de <b>30 %</b> et réduit l'instabilité des exigences de "
            "<b>25 %</b> sur <b>3</b> squads Scrum par la discipline Scrum et l'alignement "
            "OKR–roadmap.",

            "Tenu backlog et critères d'acceptation des APIs de la plateforme (Confluence).",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'QA / Release Coordinator — IDrive · Ingénieur logiciel — Tata Consultancy Services',
        'Sauvegarde cloud · Services IT · Bengaluru | 2010 – 2015',
        [
            "Coordonné trains de release et validation QA d'un produit de sauvegarde cloud "
            "(Jira, Confluence) ; développé des composants de systèmes distribués chez TCS.",
        ]
    ):
        st.append(item)

    st.append(Spacer(1, 4))

    competences = [
        SectionHeader('Compétences'),
        Spacer(1, 5),
        _skill_row(
            'Produit',
            'Stratégie &amp; roadmap • Discovery continue, JTBD / ODI • Product-led growth, '
            'pricing &amp; packaging • Priorisation (RICE) • PRD &amp; user stories • A/B tests • '
            'OKR • Go-to-market • Delivery et run',
        ),
        _skill_row(
            'IA &amp; data',
            'Produits LLM (OpenAI, Anthropic, Google) • RAG, agents • Évaluation LLM &amp; '
            'garde-fous • Coût par appel, routage de modèles • Build vs. buy • Principes ML • '
            'Pipelines data • IA responsable (RGPD, AI Act)',
        ),
        _skill_row(
            'Outils',
            'Figma • Mixpanel, Amplitude • Jira, Confluence • SQL, Python • Claude Code • '
            'Cloudflare Workers, Modal • n8n, Make',
        ),
        _skill_row(
            'Leadership',
            'Squads pluridisciplinaires (tech, design, data) • Direction et clients • Influence '
            'sans autorité hiérarchique • Conduite du changement &amp; adoption IA • Agile '
            '(Scrum, Kanban)',
        ),
        Spacer(1, 6),
    ]
    st.append(KeepTogether(competences[:3]))
    st.extend(competences[3:])

    st.append(SectionHeader('Formation'))
    st.append(Spacer(1, 5))
    st.append(Paragraph('MSc International Strategic Business (Bac+5)', S['edu_title']))
    st.append(Paragraph('Toulouse Business School, Paris | 2019–2021', S['edu_sub']))
    st.append(Paragraph('Diplôme d’ingénieur en informatique (BE Information Technology)',
                        S['edu_title']))
    st.append(Paragraph('CMR Institute of Technology, Bengaluru | 2006–2010', S['edu_sub']))

    st.append(SectionHeader('Langues'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>Français</b> : bilingue (C2) • <b>Anglais</b> : bilingue (C2) • '
        '<b>Hindi / Bengali</b> : langues maternelles',
        S['lang']
    ))
    st.append(Spacer(1, 6))

    st.append(SectionHeader('Projets open source'))
    st.append(Spacer(1, 5))
    for p in [
        _link('https://github.com/dmazumdar186/anneal', '<b>Anneal</b>') +
        ' : release gate qui audite le code généré par IA via des boucles audit-fix et '
        'red-vs-blue.',
        _link('https://github.com/dmazumdar186/cv-optimizer-agent', '<b>CV Optimizer</b>') +
        ' (SaaS en ligne) : score un CV face à une offre et le réécrit ; construit eval-first.',
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
    out = args.out or (tmp / 'cv_senior_pm_debanjan_mazumdar_fr.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)
    print("Génération du CV générique Senior PM / Senior PM IA (FR)")
    build_cv(out)
    print(f"Terminé : {out}  ({out.stat().st_size / 1024:.0f} Ko)")


if __name__ == '__main__':
    main()
