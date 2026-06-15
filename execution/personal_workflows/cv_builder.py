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
            'AI Product Manager | IA Générative • '
            'Systèmes Multi-Agents • LLM • '
            'RAG • Produits Data',
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
        "AI Product Manager avec 15 ans d’expérience en environnements data-intensifs, "
        "spécialisé dans la conception et le déploiement de capacités IA génératives "
        "en production (LLM, RAG, systèmes multi-agents). Expert en cadrage de fonctionnalités IA "
        "complexes — de la discovery à la mise en production — avec une maîtrise des enjeux "
        "éthiques, réglementaires (RGPD) et de gouvernance, doublée d’une pratique builder "
        "hands-on (Python, Cloudflare Workers, Modal cron, audit-loops self-itérants).",
        "<b>Résultats :</b> +30 % adoption • +20 % CSAT "
        "• −40 % latence • −35 % cycles d’itération"
        " • +40 % adoption BU",
    ))
    st.append(Spacer(1, 9))

    # ── Expériences professionnelles ────────────────────────────────────────────
    st.append(SectionHeader('Expériences Professionnelles'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'AI Product Manager',
        'Wiser Solutions, Paris | Nov. 2022 – Présent',
        [
            "Conçu et déployé des capacités IA génératives en production "
            "(triage, recommandation, support client RAG, alertes intelligentes) avec OpenAI Assistants, "
            "Claude et systèmes multi-agents (MCP, A2A) → "
            "<b>−40 % latence, +25 % précision, +25 % adoption</b>",

            "Défini la vision IA et la roadmap de capacités avec hypothèses de valeur, "
            "critères go/no-go et plans de rollback ; aligné <b>5 équipes cross-BU</b> "
            "(Data/AI, MLOps, architecture, sécurité, métier) sur une vision commune",

            "Rédigé des PRDs orientés IA (contrats API/données, seuils d’évaluation, "
            "gestion du non-déterminisme, RGPD/privacy-by-design) et piloté les revues de "
            "faisabilité technique avec les équipes Data/AI",

            "Orchestré le déploiement GTM mondial avec plans d’enablement et playbooks "
            "terrain → <b>+40 % adoption BU, +30 % adoption utilisateur, +20 % CSAT</b>",

            "Mis en place des dashboards analytics (usage/couverture/qualité) et signaux "
            "opérationnels (drift, incidents) → "
            "<b>+25–30 % précision de livraison, −25 % ambiguïté</b> "
            "en sprint via DoR/DoD et QA pré-prod",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'AI Product Engineer — Mission Freelance',
        'Accessory Masters (Elite Broker Group), remote | Déc. 2025 – Mars 2026',
        [
            "Conçu et livré un pipeline cold email autonome à grande échelle "
            "(<b>24 000 emails/mois, ~800/jour sur 32 inboxes warmées</b>) avec "
            "personnalisation IA Claude, classification de réponses et auto-reply contextuel "
            "→ <b>4 % de réponse</b>, SLA hot-lead 3 h via Telegram",

            "Architecturé une stack serverless event-driven (Cloudflare Workers + KV cron, "
            "Instantly.ai webhooks, GoHighLevel CRM V2 API, Modal jobs planifiés) avec "
            "idempotency keys, dedup KV TTL 60 j et garde-fous LLM (limites, voix, fallbacks)",

            "Productisé monitoring & gouvernance : dashboard opérateur (Vercel), "
            "endpoint <b>/api/health</b>, modes <b>--dry-run</b> sur chaque chemin payant, "
            "canary synthétique → dérive silencieuse détectée avant impact "
            "crédits API",
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

    # ── Projets personnels ───────────────────────────────────────────────────────
    st.append(SectionHeader('Projets Personnels'))
    st.append(Spacer(1, 5))

    for p in [
        '<b>job_search_v2</b> (juin 2026) — Agrégateur multi-sources quotidien '
        '(France Travail REST + LinkedIn/Indeed via Gmail-IMAP + WTTJ/APEC fixtures) ; '
        'dedup SQLite persistant (TTL <b>60 j</b>), ranker Gemini 2.5 Flash A/B/C avec '
        'fallback flash-lite, <b>5 couches</b> typées Pydantic v2 ; '
        '<b>3</b> wet-runs idempotents consécutifs, coût <b>0 €/mois</b>',

        '<b>Anneal</b> (mars 2026) — CLI Python d’audit-loop auto-itératif sur '
        '<i>git diff</i> (classique + adversarial Red-vs-Blue) ; dual-adapter LLM '
        '(Anthropic + OpenRouter), tiers cheap/balanced/premium ; termine sur 2 rondes '
        'consécutives sans bug',

        '<a href="https://github.com/dmazumdar186/youtube-video-analyzer" color="#1B9AAA">'
        '<b>YouTube Video Analyzer</b></a> (mai 2026) — décomposition frame-by-frame de '
        'vidéos YouTube : PySceneDetect + dedup perceptuel + tiling 3×3 (−85 % tokens vision) '
        '+ routing multi-modèle (Claude / Gemini gratuit / OpenRouter) ; 73 tests, '
        '8 rounds d’audit clean',

        '<b>Job Tracker PM France</b> (mai 2026) — pipeline ETL quotidien : 5 job boards '
        'scrapés (WTTJ, Indeed, APEC, France Travail, Google Jobs), filtrage ICP, '
        'enrichissement contacts via INSEE SIRENE + Firecrawl, digest HTML par email ; '
        'stack Firecrawl, Serper, Modal cron, SQLite',

        '<b>Self-Outbound Engine</b> (janv. 2026) — moteur autonome de prospection : '
        '180–270 emails/jour sur 6–9 inboxes warmées, classification de réponses, '
        'auto-reply Cal.com avec délai humain randomisé, alertes Telegram ; stack '
        'Cloudflare Workers, Apollo, Gemini, Claude Haiku',

        '<a href="https://github.com/dmazumdar186/cv-optimizer-agent" color="#1B9AAA">'
        '<b>CV Optimizer Agent</b></a> (avr. 2026) — agent IA (Streamlit + Gemini) : '
        'scoring ATS d’un CV vs JD, génération de CV optimisé &amp; lettre de motivation '
        'PDF, multilingue',

        '<a href="https://www.youtube.com/@ProdCraft" color="#1B9AAA"><b>ProdCraft</b></a> '
        '(YouTube, sept. 2025 – présent) — chaîne ed-tech dédiée aux futurs '
        'Product Managers : fondamentaux &amp; bonnes pratiques',
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
