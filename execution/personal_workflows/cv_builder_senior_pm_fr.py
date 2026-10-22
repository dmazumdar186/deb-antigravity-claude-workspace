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
    'accroche':  _s(fontSize=9.2, alignment=TA_JUSTIFY, leading=14.1),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.1, textColor=NAVY, leading=11.8, spaceAfter=1),
    'employer':  _s(fontSize=9, textColor=MDGRY, leading=12.4, spaceAfter=3),
    'bullet':    _s(fontSize=9, alignment=TA_JUSTIFY, leading=13.6,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
    'oneliner':  _s(fontSize=8.9, textColor=MDGRY, leading=12.4, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.2, textColor=NAVY, leading=10.8, spaceAfter=0),
    'skill_val': _s(fontSize=8.9, alignment=TA_JUSTIFY, leading=13.2, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=8.8, textColor=DKGRY, leading=11.8, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.0, textColor=MDGRY, leading=10.8, spaceAfter=5),
    'lang':      _s(fontSize=8.3, leading=11.6, spaceAfter=2),
    'project':   _s(fontSize=8.9, alignment=TA_JUSTIFY, leading=13.2,
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
            'Senior Product Manager — Produits IA &amp; Data | SaaS B2B | PM depuis 2021, PO 2015–19',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • +33 7 55 80 76 58 • Paris'
            ' • ' + _link('https://linkedin.com/in/dmazumdar/', 'linkedin.com/in/dmazumdar')
            + ' • ' + _link('https://github.com/dmazumdar186', 'github.com/dmazumdar186'),
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 6),
    ]

    st.append(_accroche(
        "Senior Product Manager produits IA et data. Discovery continue et entretiens clients "
        "d'abord, puis une roadmap avec des objectifs mesurables et un lancement suivi. PM "
        "depuis 2021, sur la GenAI chez Wiser Solutions depuis 2022 ; avant cela quatre ans de "
        "Product Owner et cinq ans d'ingénieur logiciel, en scale-up, grand groupe (Avaya, "
        "TCS) et conseil. Prototype avec Claude Code avant d'écrire la spec ; travaille les "
        "arbitrages avec les développeurs et la roadmap avec le CPO.",
        "Basé à Paris, bilingue français-anglais, ouvert au télétravail.",
    ))
    st.append(Spacer(1, 8))

    st.append(SectionHeader('Expérience professionnelle'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, IA &amp; Data Intelligence — Wiser Solutions',
        'SaaS B2B · Retail &amp; Digital-Commerce Intelligence · Paris | Nov. 2022 – Aujourd’hui',
        [
            "Responsable du périmètre IA de bout en bout : assistant RAG sur APIs OpenAI et "
            "Anthropic, recommandation, alerting, sur une plateforme utilisée par des "
            "distributeurs et des marques. Cadrage et recherche utilisateur avec les clients, "
            "roadmap avec le CPO, PRD, lancement, suivi de l'adoption. Adoption en hausse de "
            "<b>45 %</b> après la deuxième version ; latence p95 en baisse de <b>55 %</b>.",

            "Pilotage du déploiement GenAI de l'entreprise avec un budget de <b>150 K$</b> : "
            "build vs. buy entre OpenAI, Anthropic et Google, go/no-go avec le CPO et les "
            "directions métier, acculturation de chaque BU. Adoption en hausse de <b>40 %</b> "
            "dans les BU, CSAT en hausse de <b>20 %</b>.",

            "Coordination de <b>5</b> squads (tech, design, data) entre Paris, les États-Unis "
            "et l'Inde sur une seule roadmap priorisée, sans lien hiérarchique.",

            "A/B tests et feature flags, analytics d'usage et de conversion (Mixpanel, "
            "Amplitude), jeux d'évaluation LLM et garde-fous, RGPD dès la conception.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Fondateur &amp; Consultant Produit IA — ' + _link('https://prodcraft.fyi', 'ProdCraft'),
        'Studio produit IA indépendant, Paris (en parallèle de Wiser) | Janv. 2026 – Aujourd’hui',
        [
            "Activité annexe, soirs et week-ends : <b>12</b> petits produits IA pour des "
            "clients, dont un pipeline outbound agentique sur Cloudflare Workers qui a remplacé "
            "environ <b>200 K$/an</b> de travail manuel, et une marketplace Stripe Connect.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Produits Data &amp; Recommandation — InfoTnT',
        'SaaS B2B · Paris | Juin 2021 – Nov. 2022',
        [
            "Mise en place d'une discovery continue (entretiens clients, JTBD, analytics "
            "d'usage) et d'une roadmap priorisée dans une équipe qui n'avait ni l'une ni "
            "l'autre. Cycles d'itération plus courts et score d'adéquation produit-marché en "
            "hausse de <b>25 %</b>.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2019 – 2021 :</b> MSc International Strategic Business (Bac+5), Toulouse Business '
        'School, Paris (temps plein).',
        S['oneliner']
    ))
    st.append(Spacer(1, 4))

    for item in _exp_entry(
        'Senior Product Owner — Avaya (2015–18) · Evolent (2018–19) · Pitney Bowes (2019)',
        'Communications d’entreprise · SaaS santé (secteur réglementé) · SaaS logistique · Pune | '
        '2015 – 2019',
        [
            "Quatre ans de Product Owner sur des produits plateforme et data, jusqu'à "
            "<b>3</b> squads Scrum en parallèle : backlog, objectifs de sprint, cadre SLA/SLO, "
            "revues de risques RAID, alignement OKR–roadmap. Chez Avaya, vélocité en hausse de "
            "<b>30 %</b> ; chez Evolent, travail sous contraintes de conformité santé.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2010 – 2015 :</b> Ingénieur logiciel, Tata Consultancy Services, puis QA / Release '
        'Coordinator, IDrive. Systèmes distribués et gestion des releases.',
        S['oneliner']
    ))
    st.append(Spacer(1, 7))

    competences = [
        SectionHeader('Compétences'),
        Spacer(1, 5),
        _skill_row(
            'Produit',
            'Discovery continue et recherche utilisateur • OKR, KPI et mesure d’impact • Vision '
            '&amp; roadmap • Cadrage du problème • Priorisation et arbitrages • PRD • A/B tests • '
            'Analytics (SQL, Mixpanel, Amplitude) • Go-to-market • Delivery et run',
        ),
        _skill_row(
            'IA &amp; data',
            'Produits LLM (OpenAI, Anthropic, Google) • RAG et agents • Build vs. buy • '
            'Principes ML • Pipelines data • IA responsable (RGPD, AI Act)',
        ),
        _skill_row(
            'Technique',
            'Python, SQL • APIs et produits plateforme • Cloudflare Workers • CI/CD • '
            'Prototypage avec Claude Code',
        ),
        _skill_row(
            'Collaboration',
            'Binôme tech et design • Direction et clients • Influence sans autorité '
            'hiérarchique • Conduite du changement • Agile (Scrum, Kanban)',
        ),
        Spacer(1, 7),
    ]
    st.append(KeepTogether(competences[:3]))
    st.extend(competences[3:])

    st.append(SectionHeader('Formation'))
    st.append(Spacer(1, 5))
    st.append(Paragraph('Diplôme d’ingénieur en informatique (BE Information Technology)',
                        S['edu_title']))
    st.append(Paragraph('CMR Institute of Technology, Bengaluru | 2006–2010', S['edu_sub']))
    st.append(Paragraph('MSc International Strategic Business (Bac+5)', S['edu_title']))
    st.append(Paragraph('Toulouse Business School, Paris | 2019–2021', S['edu_sub']))

    st.append(SectionHeader('Langues'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>Français</b> : bilingue (C2) • <b>Anglais</b> : bilingue (C2) • '
        '<b>Hindi / Bengali</b> : langues maternelles',
        S['lang']
    ))
    st.append(Spacer(1, 7))

    st.append(Paragraph(
        'Open source : ' + _link('https://github.com/dmazumdar186/anneal', 'Anneal') +
        ', une release gate qui audite le code généré par IA (' +
        _link('https://github.com/dmazumdar186', 'github.com/dmazumdar186') + ').',
        S['oneliner']
    ))

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
