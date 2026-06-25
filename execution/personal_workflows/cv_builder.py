#!/usr/bin/env python3
"""
cv_builder.py
description: Generate an ATS-optimized, French-language PDF CV for Debanjan Mazumdar
inputs: --company (str), --role (str) via CLI args
outputs: .tmp/cv_{company}_debanjan_mazumdar.pdf

Usage:
    py execution/personal_workflows/cv_builder.py --company sahar --role "AI Product Manager"

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


# ── Section header (FR/EN style: teal accent bar + navy text) ──────────────────
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


# ── Variant-local helper wrappers ───────────────────────────────────────────────
def _accroche(text, kpi_line):
    return accroche(text, kpi_line, style=S['accroche'], text_w=TEXT_W, bg_color=LTBLUE)


def _exp_entry(title, company_line, bullets):
    return exp_entry(
        title, company_line, bullets,
        role_style=S['role'],
        employer_style=S['employer'],
        bullet_style=S['bullet'],
        keep_first_bullet=False,
    )


def _skill_row(cat, val):
    # FR uses non-breaking space before colon
    return skill_row(
        cat, val,
        cat_style=S['skill_cat'],
        val_style=S['skill_val'],
        text_w=TEXT_W,
        separator=' :',
    )


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'AI Product Manager &amp; Builder | IA Générative • RAG • '
            'Agentic AI • LLM • Automatisation — livré en production',
            S['subtitle']
        ),
        Spacer(1, 3),
        # LinkedIn and GitHub as clickable hyperlinks
        Paragraph(
            'debanjan186@gmail.com • 0755807658 • Paris, France'
            ' • '
            '<a href="https://linkedin.com/in/dmazumdar/" color="#1B9AAA">linkedin.com/in/dmazumdar</a>'
            ' • '
            '<a href="https://github.com/dmazumdar186" color="#1B9AAA">github.com/dmazumdar186</a>',
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 7),
    ]

    # ── Accroche ────────────────────────────────────────────────────────────────
    st.append(_accroche(
        "AI Product Manager et builder hands-on — 15 ans en produit data-intensif. "
        "Je livre des systèmes IA en production de bout en bout : fonctionnalités GenAI/RAG, "
        "workflows multi-agents, moteurs de cold-email, voice AI et applications full-stack, "
        "construits avec Claude Code et déployés en quelques semaines, pas en trimestres. "
        "Une combinaison rare de jugement produit (discovery, PRDs IA, RGPD/gouvernance, "
        "alignement cross-BU) et de pratique builder (Python, Cloudflare Workers, Modal, "
        "orchestration LLM, frameworks d’évaluation) qui dé-risque la livraison.",
        "<b>Impact :</b> $1M+ de pipeline • 48 000+ emails/mois à 4 %+ de réponse "
        "• +45 % adoption GenAI • −55 % latence p95 • livraison médiane &lt;30 jours "
        "• 12+ systèmes IA livrés",
    ))
    st.append(Spacer(1, 9))

    # ── Expériences professionnelles ────────────────────────────────────────────
    st.append(SectionHeader('Expériences Professionnelles'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'AI Product Manager',
        'Wiser Solutions, Paris | Nov. 2022 – Présent',
        [
            "Livré des capacités GenAI en production (triage, recommandation, support RAG, "
            "alertes intelligentes) atteignant <b>+45 % d’adoption et −55 % de latence p95</b>, "
            "en orchestrant des systèmes multi-agents OpenAI/Claude (MCP, A2A) avec seuils "
            "d’évaluation et maîtrise des coûts (prompt caching)",

            "Généré <b>+40 % d’adoption BU et +20 % CSAT</b> sur le déploiement GenAI mondial "
            "en rédigeant des PRDs IA (contrats API/données, RGPD/privacy-by-design), pilotant "
            "les revues de faisabilité et alignant <b>5 équipes cross-BU</b> sur une roadmap "
            "commune avec gates go/no-go et plans de rollback",

            "Amélioré la précision de livraison de <b>+25–30 %</b> et réduit l’ambiguïté en "
            "sprint de <b>~25 %</b> via dashboards usage/qualité/drift et DoR/DoD + QA pré-prod",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'AI Product Engineer (Freelance)',
        'Cabinet outbound à haute vélocité (confidentiel), remote | Déc. 2025 – Mars 2026',
        [
            "Conçu et livré un moteur de cold-email autonome à grande échelle — "
            "<b>48 000+ emails/mois à 4 %+ de réponse</b>, générant <b>$1M+ de pipeline "
            "qualifié</b> et remplaçant <b>~200K$/an de coût SDR</b>, avec personnalisation "
            "Claude, classification de réponses et auto-reply contextuel "
            "(SLA hot-lead 3 h via Telegram)",

            "Architecturé une stack serverless event-driven (Cloudflare Workers + KV cron, "
            "webhooks Instantly, CRM GoHighLevel, jobs Modal planifiés) avec idempotency keys, "
            "dedup TTL 60 j et garde-fous LLM",

            "Productisé monitoring & gouvernance : dashboard opérateur, endpoint "
            "<b>/api/health</b>, modes <b>--dry-run</b> sur chaque chemin payant, canary "
            "synthétique → dérive silencieuse détectée avant tout impact crédits",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Data Product Manager',
        'InfoTnT, Paris | Juin 2021 – Nov. 2022',
        [
            "Piloté la discovery produit pour un moteur de recommandation data-driven "
            "(quant/qual, JTBD) → "
            "<b>−35 % cycles d’itération, +25 % adéquation post-lancement</b>",

            "Traduit les enjeux métiers en capacités backend, épics et contrats de "
            "données avec métriques de succès et contraintes d’intégration",

            "Standardisé les prompts, templates et procédures de versioning pour les "
            "composants IA → comportements prédictibles et déploiements fiables ; "
            "coordonné les releases via PRDs/RFCs et QA fonctionnelle",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner',
        'Pitney Bowes Inc, Pune | Avr. – Sept. 2019',
        [
            "Réduit le time-to-market de <b>−20 %</b> via cartographie des "
            "dépendances cross-squads, cadence de release renforcée, checklists pré-prod "
            "et revues RAID structurées",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner',
        'Evolent International, Pune | Juin 2018 – Fév. 2019',
        [
            "Amélioré la scalabilité et la performance de la plateforme "
            "(<b>+30 %</b>) par l’introduction de SLA/SLO pour arbitrer les priorités "
            "run/change ; intégré des checkpoints gouvernance et QA dans le flux de livraison",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner',
        'Avaya India Pvt Ltd, Pune | Juil. 2015 – Mars 2018',
        [
            "Accéléré la vélocité de livraison (<b>+30 %</b>) via discipline "
            "Scrum renforcée et alignement OKR ↔ roadmap ; réduit l’instabilité "
            "des exigences (<b>−25 %</b>) pour améliorer la préparation aux releases",
        ]
    ):
        st.append(item)

    # Condensed early-career line: TCS + IDrive collapsed into one row under Avaya.
    st.append(Paragraph(
        '<b>2010 – 2015 :</b> Software Engineer '
        '(Tata Consultancy Services, Bengaluru | Nov. 2010 – Mars 2013) → '
        'QA Engineer / Release Coordinator '
        '(IDrive India, Bengaluru | Avr. 2013 – Juil. 2015) — '
        '<i>fondations techniques en systèmes distribués et release management</i>',
        S['oneliner']
    ))
    st.append(Spacer(1, 8))

    # ── Compétences ─────────────────────────────────────────────────────────────
    # KeepTogether forces the entire section (header + all rows) onto the same page,
    # preventing the header from being stranded at the bottom of page 1.
    competences = [
        SectionHeader('Compétences'),
        Spacer(1, 5),
        _skill_row(
            'IA & GenAI',
            'LLM, RAG, Agentic AI, Systèmes Multi-Agents, OpenAI Assistants, Claude, MCP, A2A, '
            'ML supervisé/non supervisé, Frameworks d’évaluation IA '
            '(précision, cohérence, robustesse), gestion du non-déterminisme, '
            'prompt caching, garde-fous LLM, audit-loops self-itérants (anneal), '
            'model routing (OpenRouter), Cloudflare Workers, Modal cron, Firecrawl',
        ),
        _skill_row(
            'Product Mgt',
            'Vision & Roadmap, Discovery (quant/qual, JTBD), PRD, Contrats API/données, '
            'Backlog, KPI/OKR, A/B tests, DoR/DoD, Enablement & GTM',
        ),
        _skill_row(
            'Gouvernance',
            'RGPD/privacy-by-design, contrôle d’accès, pistes d’audit, '
            'souveraineté technologique, éthique IA',
        ),
        _skill_row(
            'Collaboration',
            'Cross-fonctionnel (Data/AI, Dév, CSM, Sales, MLOps, Sécurité), '
            'animation d’ateliers, stakeholder management',
        ),
        _skill_row(
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
        'Toulouse Business School, Paris | 2019–2021', S['edu_sub']))
    st.append(Paragraph('BE Information Technology Engineering', S['edu_title']))
    st.append(Paragraph(
        'CMR Institute of Technology, Bengaluru | 2006–2010', S['edu_sub']))

    # ── Langues ──────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Langues'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>Anglais</b> : Bilingue (C2) • '
        '<b>Français</b> : Bilingue (C2) • '
        '<b>Hindi</b> : Natif • '
        '<b>Bengali</b> : Natif',
        S['lang']
    ))
    st.append(Spacer(1, 8))

    # ── Réalisations sélectionnées ──────────────────────────────────────────────
    # Le différenciateur qu'aucun CV de PM pur n'a : des systèmes livrés en production.
    st.append(SectionHeader('Réalisations Sélectionnées'))
    st.append(Spacer(1, 5))

    for p in [
        '<a href="https://cv-optimizer.pages.dev" color="#1B9AAA"><b>CV Optimizer</b></a> '
        '(SaaS en ligne) — application IA multilingue qui score un CV face à une offre et '
        'génère un CV &amp; une lettre de motivation optimisés ATS ; Streamlit + Gemini, '
        'déployé sur Cloudflare Pages/Workers',

        '<b>Marketplace à deux faces</b> (avec une agence partenaire, sous NDA) — plateforme '
        'de paiement Stripe Connect traitant <b>85K$ les 3 premiers mois</b> ; '
        'React + Node + Postgres',

        '<b>anneal</b> (CLI Python) — audit-loop de code auto-itératif sur <i>git diff</i> '
        '(classique + adversarial Red-vs-Blue), dual-adapter LLM (Anthropic + OpenRouter), '
        'termine sur 2 rondes consécutives sans bug',

        '<a href="https://github.com/dmazumdar186/youtube-video-analyzer" color="#1B9AAA">'
        '<b>YouTube Video Analyzer</b></a> — décomposition frame-by-frame de vidéos : '
        'PySceneDetect + dedup perceptuel + tiling 3×3 (<b>−85 % tokens vision</b>) + '
        'routing multi-modèle ; 73 tests, 8 rondes d’audit clean',

        '<b>job_search_v2</b> — agrégateur d’offres multi-sources quotidien (3 sources live), '
        'pipeline typé Pydantic v2 avec dedup SQLite persistant et ranker Gemini A/B/C ; '
        'tourne en CI à <b>0 €/mois</b>',
    ]:
        st.append(Paragraph('<bullet>•</bullet>' + p, S['project']))
    return st


# ── Build PDF ────────────────────────────────────────────────────────────────────
def build_cv(output: Path):
    build_cv_doc(output, build_story(), margin_lr=MARGIN_LR, margin_tb=MARGIN_TB)


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
