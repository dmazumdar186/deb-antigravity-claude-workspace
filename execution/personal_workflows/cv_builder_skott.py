#!/usr/bin/env python3
"""
cv_builder_skott.py
description: Generate the French 2-page CV "CV MAZUMDAR Debanjan.pdf" targeted at the
             SKOTT Group roles (PO Data & IA Toulouse / Chef de projet automation pharma /
             Data Business Analyst automation), mirroring SKOTT's anonymized CV template
             (PROFIL -> COMPETENCES CLES -> EXPERIENCES -> FORMATION, corporate navy).
inputs: --output (optional path; default "<workspace root>/CV MAZUMDAR Debanjan.pdf")
outputs: the PDF at the output path; prints page count sanity hint
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
        Paragraph, Spacer, Flowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
except ImportError:
    print("ERROR: pip install reportlab")
    sys.exit(1)

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_LR = 1.7 * cm
MARGIN_TB = 1.4 * cm
TEXT_W = PAGE_W - 2 * MARGIN_LR

# ── Colours (SKOTT-style corporate navy) ───────────────────────────────────────
NAVY  = HexColor('#1F4E79')
BLUE  = HexColor('#2E75B6')
DKGRY = HexColor('#2C2C2C')
MDGRY = HexColor('#5A5A5A')


def _register_fonts():
    """Use Arial (Windows) for full Unicode; fall back to Helvetica."""
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    regular = os.path.join(win_fonts, 'arial.ttf')
    bold    = os.path.join(win_fonts, 'arialbd.ttf')
    italic  = os.path.join(win_fonts, 'ariali.ttf')
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont('CV',      regular))
        pdfmetrics.registerFont(TTFont('CV-Bold', bold))
        pdfmetrics.registerFont(TTFont('CV-Ital', italic if os.path.exists(italic) else regular))
        registerFontFamily('CV', normal='CV', bold='CV-Bold',
                           italic='CV-Ital', boldItalic='CV-Bold')
        return 'CV', 'CV-Bold'
    registerFontFamily('Helvetica', normal='Helvetica', bold='Helvetica-Bold',
                       italic='Helvetica-Oblique', boldItalic='Helvetica-BoldOblique')
    return 'Helvetica', 'Helvetica-Bold'


FONT, FONT_BOLD = _register_fonts()


class SectionHeader(Flowable):
    """SKOTT-style section header: navy uppercase title over a thin rule."""
    HEIGHT = 20

    def __init__(self, text, width=TEXT_W):
        super().__init__()
        self.text   = text
        self.width  = width
        self.height = self.HEIGHT

    def draw(self):
        c = self.canv
        c.setFillColor(NAVY)
        c.setFont(FONT_BOLD, 10.5)
        c.drawString(0, 6, self.text.upper())
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.8)
        c.line(0, 1.5, self.width, 1.5)


def _s(**kw):
    defaults = dict(fontName=FONT, fontSize=8.6, textColor=DKGRY,
                    leading=12.6, spaceAfter=0)
    defaults.update(kw)
    return ParagraphStyle('', **defaults)


S = {
    'name':     _s(fontName=FONT_BOLD, fontSize=21, textColor=NAVY,
                   leading=25, spaceAfter=2),
    'subtitle': _s(fontName=FONT_BOLD, fontSize=10.5, textColor=BLUE,
                   leading=14, spaceAfter=3),
    'meta':     _s(fontSize=8.4, textColor=MDGRY, leading=12, spaceAfter=1),
    'contact':  _s(fontSize=8.2, textColor=MDGRY, leading=11.5, spaceAfter=0),
    'profil':   _s(fontSize=8.7, alignment=TA_JUSTIFY, leading=13.2),
    'kpi':      _s(fontSize=8.7, leading=13, spaceAfter=0),
    'role':     _s(fontName=FONT_BOLD, fontSize=9.5, textColor=NAVY,
                   leading=12.5, spaceAfter=1),
    'employer': _s(fontSize=8.4, textColor=MDGRY, leading=11.5, spaceAfter=3),
    'bullet':   _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=12.6,
                   leftIndent=11, bulletIndent=0, spaceAfter=2.5),
    'oneliner': _s(fontSize=8.3, textColor=MDGRY, leading=11.5, spaceAfter=3),
    'skill':    _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=12.8, spaceAfter=3.5),
    'edu':      _s(fontSize=8.6, leading=12.8, spaceAfter=2.5),
    'lang':     _s(fontSize=8.6, leading=12.8, spaceAfter=2),
    'project':  _s(fontSize=8.4, alignment=TA_JUSTIFY, leading=12.4,
                   leftIndent=11, bulletIndent=0, spaceAfter=2.5),
}

SEP = ' • '   # " • "
DOT = ' · '   # " · "


def exp_entry(title, company_line, bullets):
    # Whole entry is atomic: an experience must never split across the page break.
    elems = [
        Paragraph(title, S['role']),
        Paragraph(company_line, S['employer']),
    ]
    for b in bullets:
        elems.append(Paragraph('<bullet>•</bullet>' + b, S['bullet']))
    return [KeepTogether(elems), Spacer(1, 6)]


def skill_line(cat, vals):
    return Paragraph(f'<font color="#1F4E79"><b>{cat} :</b></font> ' + vals, S['skill'])


def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan MAZUMDAR', S['name']),
        Paragraph('Chef de Projet Data &amp; IA | AI Product Manager / Product Owner',
                  S['subtitle']),
        Paragraph('Paris, France' + SEP + 'Mobilité France entière' + SEP
                  + 'Disponible immédiatement' + SEP + '15 ans d’expérience' + SEP
                  + 'Français (bilingue), Anglais (bilingue)', S['meta']),
        Paragraph(
            'debanjan186@gmail.com' + SEP + '07 55 80 76 58' + SEP
            + '<a href="https://linkedin.com/in/dmazumdar/" color="#2E75B6">linkedin.com/in/dmazumdar</a>'
            + SEP
            + '<a href="https://github.com/dmazumdar186" color="#2E75B6">github.com/dmazumdar186</a>'
            + SEP
            + '<a href="https://www.malt.fr/profile/debanjanmazumdar" color="#2E75B6">malt.fr/debanjanmazumdar</a>',
            S['contact']),
        Spacer(1, 7),
    ]

    # ── Profil ──────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Profil'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        "Chef de projet Data &amp; IA orienté livraison et gouvernance, fort de 15 ans "
        "d’expérience en environnements data-intensifs internationaux, dont 7 ans de "
        "pilotage de bout en bout de produits et projets Data &amp; IA (cadrage, étude "
        "d’opportunité, delivery, recette, mise en production) dans les secteurs SaaS, "
        "santé, retail et télécoms. Spécialiste du déploiement de solutions d’IA "
        "générative en production (LLM, RAG, systèmes multi-agents), à l’interface "
        "Métier / Data / IT / Sécurité. Maîtrise de la gouvernance projet (jalons, gestion "
        "des risques et dépendances, reporting sponsors), des méthodologies Agile / Scrum et "
        "de la conduite du changement pour sécuriser l’adoption et le passage à "
        "l’échelle. Pratique builder hands-on : Python, SQL, pipelines de données, "
        "automatisation de workflows.",
        S['profil']))
    st.append(Spacer(1, 4))
    st.append(Paragraph(
        '<b>Résultats :</b> +40 % adoption BU' + SEP + '+20 % CSAT'
        + SEP + '−40 % latence' + SEP + '−35 % cycles d’itération'
        + SEP + '−20 % time-to-market', S['kpi']))
    st.append(Spacer(1, 9))

    # ── Compétences clés ────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Compétences clés'),
        Spacer(1, 5),
        skill_line('Pilotage &amp; gouvernance de projet',
                   'Gestion de projet de bout en bout' + DOT + 'Gouvernance &amp; comitologie'
                   + DOT + 'Gestion des risques &amp; dépendances' + DOT
                   + 'Planification &amp; jalons' + DOT + 'Reporting sponsors &amp; direction'
                   + DOT + 'Agile' + DOT + 'Scrum' + DOT + 'Kanban' + DOT
                   + 'Animation de cérémonies'),
        skill_line('Cadrage &amp; delivery',
                   'Étude d’opportunité' + DOT + 'Business case &amp; ROI' + DOT
                   + 'Discovery (entretiens utilisateurs, JTBD)' + DOT + 'Roadmap' + DOT
                   + 'Backlog &amp; user stories' + DOT + 'Priorisation (RICE, MoSCoW)' + DOT
                   + 'Spécifications fonctionnelles' + DOT + 'Recette / UAT' + DOT + 'MVP'
                   + DOT + 'Mise en production' + DOT + 'Passage à l’échelle'),
        skill_line('Data &amp; IA',
                   'IA générative (LLM, RAG, agents &amp; multi-agents)' + DOT
                   + 'Pipelines de données (ETL/ELT)' + DOT
                   + 'Contrats &amp; qualité de données' + DOT
                   + 'Modélisation de workflows &amp; flux de données end-to-end' + DOT
                   + 'Tableaux de bord &amp; KPI' + DOT + 'Automatisation' + DOT
                   + 'Frameworks d’évaluation IA' + DOT
                   + 'Monitoring opérationnel (drift, incidents)'),
        skill_line('Conduite du changement',
                   'Formation &amp; enablement' + DOT + 'Animation d’ateliers' + DOT
                   + 'Communication stakeholders' + DOT + 'Animation de communauté' + DOT
                   + 'Mesure d’impact (adoption, KPI, CSAT)'),
        skill_line('Conformité &amp; gouvernance des données',
                   'RGPD / privacy-by-design' + DOT + 'Pistes d’audit' + DOT
                   + 'Contrôle d’accès' + DOT + 'Éthique IA' + DOT
                   + 'Environnements réglementés (santé, retail international)'),
        skill_line('Outils',
                   'Jira' + DOT + 'Confluence' + DOT + 'Miro' + DOT + 'Figma' + DOT
                   + 'Mixpanel' + DOT + 'SQL' + DOT + 'Python' + DOT + 'n8n / Make' + DOT
                   + 'APIs GenAI (OpenAI, Anthropic, Google)' + DOT + 'Git / CI-CD'),
        Spacer(1, 8),
    ]
    st.append(KeepTogether(competences))

    # ── Expériences ─────────────────────────────────────────────────────────────
    st.append(SectionHeader('Expériences professionnelles'))
    st.append(Spacer(1, 6))

    st += exp_entry(
        'Chef de Projet / Product Manager IA — Transformation Digitale',
        'Wiser Solutions (SaaS retail intelligence), Paris | Nov. 2022 – Aujourd’hui',
        [
            "Pilotage de bout en bout (cadrage, étude d’opportunité, delivery, mise en "
            "production) des capacités d’IA générative : triage, recommandation, "
            "support client RAG, alertes intelligentes — avec OpenAI Assistants, Claude et "
            "systèmes multi-agents → <b>−40 % latence, +25 % précision, "
            "+25 % adoption</b>",

            "Gouvernance projet : roadmap avec hypothèses de valeur, critères go/no-go et "
            "plans de rollback ; alignement de <b>5 équipes cross-BU</b> (Data/AI, MLOps, "
            "architecture, sécurité, métier) ; reporting régulier auprès de la direction",

            "Rédaction des spécifications fonctionnelles et PRDs orientés IA (contrats "
            "API/données, seuils d’évaluation, gestion du non-déterminisme, "
            "RGPD/privacy-by-design) ; revues de faisabilité technique avec les équipes Data/AI",

            "Animation des rituels Agile / Scrum et d’ateliers de cadrage ; interface "
            "entre les équipes techniques et les utilisateurs métiers",

            "Conduite du changement : déploiement GTM mondial, plans d’enablement et "
            "playbooks terrain → <b>+40 % adoption BU, +30 % adoption utilisateur, "
            "+20 % CSAT</b>",

            "Tableaux de bord de pilotage (usage, couverture, qualité) et signaux opérationnels "
            "(drift, incidents) → <b>+25–30 % précision de livraison, "
            "−25 % ambiguïté</b> en sprint via DoR/DoD et recette pré-production",
        ])

    st += exp_entry(
        'AI Product Engineer — Missions freelance (en parallèle du poste salarié)',
        'Indépendant, Paris / remote | Janv. 2025 – Aujourd’hui — '
        'mission principale : Accessory Masters (Elite Broker Group), Déc. 2025 – Mars 2026',
        [
            "Conçu et livré un pipeline cold email autonome à grande échelle (<b>24 000 "
            "emails/mois, ~800/jour sur 32 inboxes</b>) avec personnalisation IA, classification "
            "de réponses et auto-reply contextuel → <b>4 % de réponse</b>, SLA "
            "hot-lead 3 h",

            "Architecturé une stack serverless event-driven (Cloudflare Workers, webhooks, CRM, "
            "jobs planifiés) avec clés d’idempotence, déduplication et garde-fous LLM "
            "(limites, voix, fallbacks)",

            "Industrialisé monitoring &amp; gouvernance : dashboard opérateur, endpoint "
            "/api/health, modes --dry-run sur chaque chemin payant, canary synthétique → "
            "dérive silencieuse détectée avant impact sur les crédits API",
        ])

    st += exp_entry(
        'Data Product Manager',
        'InfoTnT (conseil SaaS B2B), Paris | Juin 2021 – Nov. 2022',
        [
            "Piloté la discovery produit d’un moteur de recommandation data-driven "
            "(entretiens utilisateurs, JTBD) → <b>−35 % cycles d’itération, "
            "+25 % adéquation post-lancement</b>",

            "Traduit les enjeux métiers en capacités backend, épics et contrats de données avec "
            "critères d’acceptation, métriques de succès et contraintes d’intégration",

            "Standardisé prompts, templates et procédures de versioning des composants IA ; "
            "coordonné les releases via PRDs/RFCs et recette fonctionnelle (QA)",
        ])

    st += exp_entry(
        'Senior Data Product Owner',
        'Pitney Bowes Inc (logistique), Pune, Inde | Avr. – Sept. 2019',
        [
            "Réduit le time-to-market de <b>−20 %</b> via cartographie des dépendances "
            "cross-équipes, cadence de release renforcée, checklists pré-production et revues de "
            "risques structurées (RAID)",
        ])

    st += exp_entry(
        'Senior Data Product Owner',
        'Evolent International (secteur santé), Pune, Inde | Juin 2018 – Fév. 2019',
        [
            "Plateforme data santé (environnement réglementé, données de santé US) : amélioré "
            "scalabilité et performance de <b>+30 %</b> via SLA/SLO pour arbitrer les "
            "priorités run/change ; intégré des checkpoints gouvernance et QA dans le flux "
            "de livraison",
        ])

    st += exp_entry(
        'Senior Product Owner',
        'Avaya India Pvt Ltd (télécoms), Pune, Inde | Juil. 2015 – Mars 2018',
        [
            "Accéléré la vélocité de livraison (<b>+30 %</b>) via discipline Scrum renforcée "
            "et alignement OKR ↔ roadmap ; réduit l’instabilité des exigences "
            "(<b>−25 %</b>) pour fiabiliser la préparation des releases",
        ])

    st.append(Paragraph(
        'QA Engineer / Release Coordinator — IDrive India Pvt Ltd, Bengaluru'
        ' | Avr. 2013 – Juil. 2015', S['oneliner']))
    st.append(Paragraph(
        'Software Engineer — Tata Consultancy Services, Bengaluru'
        ' | Nov. 2010 – Mars 2013', S['oneliner']))
    st.append(Spacer(1, 8))

    # ── Formation ───────────────────────────────────────────────────────────────
    formation = [
        SectionHeader('Formation'),
        Spacer(1, 5),
        Paragraph('<b>MSc International Strategic Business</b> — '
                  'Toulouse Business School | 2019–2021', S['edu']),
        Paragraph('<b>BE Information Technology Engineering</b> — '
                  'CMR Institute of Technology, Bengaluru | 2006–2010', S['edu']),
        Paragraph('<b>AI Masterclass</b> — Outskill | 2025 '
                  '(agents IA, LLM, prompt engineering, automatisation)', S['edu']),
        Spacer(1, 8),
    ]
    st.append(KeepTogether(formation))

    # ── Langues ─────────────────────────────────────────────────────────────────
    langues = [
        SectionHeader('Langues'),
        Spacer(1, 5),
        Paragraph('<b>Français</b> : bilingue' + SEP + '<b>Anglais</b> : bilingue'
                  + SEP + '<b>Hindi / Bengali</b> : natifs', S['lang']),
        Spacer(1, 8),
    ]
    st.append(KeepTogether(langues))

    # ── Projets personnels ──────────────────────────────────────────────────────
    projets = [
        SectionHeader('Projets personnels (sélection)'),
        Spacer(1, 5),
        Paragraph('<bullet>•</bullet><b>Anneal</b> — boucle d’audit adversarial '
                  'pour code généré par LLM (multi-provider, convergence sur 2 rondes sans '
                  'défaut) : discipline qualité &amp; tests appliquée à l’IA générative',
                  S['project']),
        Paragraph('<bullet>•</bullet><b>Job Tracker PM France</b> — pipeline ETL '
                  'quotidien : 5 sources scrapées, filtrage, enrichissement via API INSEE '
                  'SIRENE, digest email automatisé (Python, SQLite, cron serverless)',
                  S['project']),
        Paragraph('<bullet>•</bullet><a href="https://www.youtube.com/@ProdCraft" '
                  'color="#2E75B6"><b>ProdCraft</b></a> (YouTube) — chaîne ed-tech product '
                  'management : vulgarisation, pédagogie et animation de communauté',
                  S['project']),
    ]
    st.append(KeepTogether(projets))

    return st


def build_cv(output: Path):
    doc = BaseDocTemplate(
        str(output), pagesize=A4,
        leftMargin=MARGIN_LR, rightMargin=MARGIN_LR,
        topMargin=MARGIN_TB, bottomMargin=MARGIN_TB,
        title='CV MAZUMDAR Debanjan', author='Debanjan Mazumdar',
    )
    frame = Frame(MARGIN_LR, MARGIN_TB, TEXT_W, PAGE_H - 2 * MARGIN_TB,
                  id='main', showBoundary=0)
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
    doc.build(build_story())


def main():
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent.parent
    parser.add_argument('--output', default=str(root / 'CV MAZUMDAR Debanjan.pdf'))
    args = parser.parse_args()

    out = Path(args.output)
    build_cv(out)
    print(f"Done: {out}  ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == '__main__':
    main()
