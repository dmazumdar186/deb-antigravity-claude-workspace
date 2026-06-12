#!/usr/bin/env python3
"""
cv_builder_en.py
description: Generate an ATS-optimized, English-language PDF CV for Debanjan Mazumdar
inputs: --company (str), --role (str) via CLI args
outputs: .tmp/cv_{company}_debanjan_mazumdar_en.pdf

Usage:
    py execution/personal_workflows/cv_builder_en.py --company master --role "AI Product Manager"

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


# ── Section header (same FR/EN teal-accent style) ──────────────────────────────
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
    # EN variant keeps first bullet inside KeepTogether to prevent orphan title
    return exp_entry(
        title, company_line, bullets,
        role_style=S['role'],
        employer_style=S['employer'],
        bullet_style=S['bullet'],
        keep_first_bullet=True,
    )


def _skill_row(cat, val):
    return skill_row(
        cat, val,
        cat_style=S['skill_cat'],
        val_style=S['skill_val'],
        text_w=TEXT_W,
        separator=' :',
    )


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'AI Product Manager | GenAI • '
            'Multi-Agent Systems • LLM • '
            'RAG • Data Products',
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

    # ── Accroche / Summary ──────────────────────────────────────────────────────
    st.append(_accroche(
        "AI Product Manager with 15 years of experience in data-intensive environments, "
        "specialized in the design and deployment of production-grade Generative AI capabilities "
        "(LLM, RAG, Multi-Agent Systems). Expert at scoping complex AI features — from discovery "
        "to production — with a strong grasp of ethical, regulatory (GDPR) and governance "
        "constraints, paired with a hands-on builder practice (Python, Cloudflare Workers, "
        "Modal cron, self-iterating audit loops).",
        "<b>Results:</b> +30 % adoption • +20 % CSAT "
        "• −40 % latency • −35 % iteration cycles"
        " • +40 % BU adoption",
    ))
    st.append(Spacer(1, 9))

    # ── Professional Experience ─────────────────────────────────────────────────
    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'AI Product Manager',
        'Wiser Solutions, Paris | Nov. 2022 – Present',
        [
            "Designed and shipped production-grade GenAI capabilities (triage, recommendation, "
            "RAG customer support, smart alerts) using OpenAI Assistants, Claude and "
            "multi-agent systems (MCP, A2A) → "
            "<b>−40 % latency, +25 % precision, +25 % adoption</b>",

            "Defined the AI vision and capability roadmap with value hypotheses, go/no-go "
            "criteria and rollback plans; aligned <b>5 cross-BU teams</b> (Data/AI, MLOps, "
            "architecture, security, business) on a shared vision",

            "Authored AI-oriented PRDs (API/data contracts, evaluation thresholds, "
            "non-determinism handling, GDPR/privacy-by-design) and led technical feasibility "
            "reviews with Data/AI teams",

            "Orchestrated the global GTM rollout with enablement plans and field playbooks "
            "→ <b>+40 % BU adoption, +30 % user adoption, +20 % CSAT</b>",

            "Built analytics dashboards (usage / coverage / quality) and operational signals "
            "(drift, incidents) → <b>+25–30 % delivery precision, "
            "−25 % sprint ambiguity</b> via DoR/DoD and pre-prod QA",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'AI Product Engineer — Freelance Engagement',
        'Accessory Masters (Elite Broker Group), remote | Dec. 2025 – Mar. 2026',
        [
            "Designed and shipped an autonomous cold-email pipeline at scale "
            "(<b>24,000 emails/month, ~800/day across 32 warmed inboxes</b>) with Claude-powered "
            "personalization, reply classification and contextual auto-reply "
            "→ <b>4 % reply rate</b>, 3-hour hot-lead SLA via Telegram",

            "Architected a serverless event-driven stack (Cloudflare Workers + KV cron, "
            "Instantly.ai webhooks, GoHighLevel CRM V2 API, scheduled Modal jobs) with "
            "idempotency keys, 60-day KV dedup TTL, and LLM guardrails (limits, voice, fallbacks)",

            "Productized monitoring & governance: operator dashboard (Vercel), <b>/api/health</b> "
            "endpoint, <b>--dry-run</b> modes on every paid path, synthetic canary "
            "→ silent drift caught before any API-credit impact",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Data Product Manager',
        'InfoTnT, Paris | Jun. 2021 – Nov. 2022',
        [
            "Led product discovery for a data-driven recommendation engine (quant/qual, "
            "JTBD) → <b>−35 % iteration cycles, +25 % post-launch fit</b>",

            "Translated business needs into backend capabilities, epics and data contracts "
            "with success metrics and integration constraints",

            "Standardized prompts, templates and versioning procedures for AI components "
            "→ predictable behaviors and reliable releases; coordinated releases via "
            "PRDs/RFCs and functional QA",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner',
        'Pitney Bowes Inc, Pune | Apr. – Sep. 2019',
        [
            "Reduced time-to-market by <b>−20 %</b> via cross-squad dependency "
            "mapping, tightened release cadence, pre-prod checklists and structured RAID reviews",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner',
        'Evolent International, Pune | Jun. 2018 – Feb. 2019',
        [
            "Improved platform scalability and performance (<b>+30 %</b>) by introducing "
            "SLA/SLO to arbitrate run/change priorities; embedded governance and QA checkpoints "
            "into the delivery flow",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner',
        'Avaya India Pvt Ltd, Pune | Jul. 2015 – Mar. 2018',
        [
            "Accelerated delivery velocity (<b>+30 %</b>) through stronger Scrum "
            "discipline and OKR ↔ roadmap alignment; reduced requirement instability "
            "(<b>−25 %</b>) to improve release readiness",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        'QA Engineer / Release Coordinator — '
        'IDrive India Pvt Ltd, Bengaluru | Apr. 2013 – Jul. 2015',
        S['oneliner']
    ))
    st.append(Paragraph(
        'Software Engineer — '
        'Tata Consultancy Services, Bengaluru | Nov. 2010 – Mar. 2013',
        S['oneliner']
    ))
    st.append(Spacer(1, 8))

    # ── Skills ──────────────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Skills'),
        Spacer(1, 5),
        _skill_row(
            'AI & GenAI',
            'LLM, RAG, Agentic AI, Multi-Agent Systems, OpenAI Assistants, Claude, MCP, A2A, '
            'supervised / unsupervised ML, AI evaluation frameworks '
            '(precision, coherence, robustness), non-determinism handling, '
            'prompt caching, LLM guardrails, self-iterating audit loops (anneal), '
            'model routing (OpenRouter), Cloudflare Workers, Modal cron, Firecrawl',
        ),
        _skill_row(
            'Product Mgmt',
            'Vision &amp; Roadmap, Discovery (quant/qual, JTBD), PRD, API/data contracts, '
            'Backlog, KPI/OKR, A/B testing, DoR/DoD, Enablement &amp; GTM',
        ),
        _skill_row(
            'Governance',
            'GDPR / privacy-by-design, access control, audit trails, '
            'tech sovereignty, AI ethics',
        ),
        _skill_row(
            'Collaboration',
            'Cross-functional (Data/AI, Dev, CSM, Sales, MLOps, Security), '
            'workshop facilitation, stakeholder management',
        ),
        _skill_row(
            'Tools',
            'Jira, Confluence, Google AntiGravity, N8N, Make, Figma, Miro, Mixpanel, SQL, '
            'GenAI APIs (OpenAI, Google, Anthropic)',
        ),
        Spacer(1, 8),
    ]
    st.append(KeepTogether(competences))

    # ── Education ────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Education'))
    st.append(Spacer(1, 5))
    st.append(Paragraph('MSc International Strategic Business', S['edu_title']))
    st.append(Paragraph(
        'Toulouse Business School, Paris | 2019–2021', S['edu_sub']))
    st.append(Paragraph('BE Information Technology Engineering', S['edu_title']))
    st.append(Paragraph(
        'CMR Institute of Technology, Bengaluru | 2006–2010', S['edu_sub']))

    # ── Languages ───────────────────────────────────────────────────────────────
    st.append(SectionHeader('Languages'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>English</b> : Bilingual • '
        '<b>French</b> : Bilingual • '
        '<b>Hindi</b> : Native • '
        '<b>Bengali</b> : Native',
        S['lang']
    ))
    st.append(Spacer(1, 8))

    # ── Personal Projects ───────────────────────────────────────────────────────
    st.append(SectionHeader('Personal Projects'))
    st.append(Spacer(1, 5))

    for p in [
        '<b>Anneal</b> (Mar. 2026) — Python CLI for self-iterating audit loops over '
        '<i>git diff</i> (classic + adversarial Red-vs-Blue); dual-adapter LLM '
        '(Anthropic + OpenRouter), cheap / balanced / premium tiers; terminates on '
        '2 consecutive zero-bug rounds',

        '<a href="https://github.com/dmazumdar186/youtube-video-analyzer" color="#1B9AAA">'
        '<b>YouTube Video Analyzer</b></a> (May 2026) — frame-by-frame breakdown of '
        'YouTube videos: PySceneDetect + perceptual dedup + 3×3 tiling '
        '(−85 % vision tokens) + multi-model routing '
        '(Claude / Gemini free / OpenRouter); 73 tests, 8 clean audit rounds',

        '<b>Job Tracker PM France</b> (May 2026) — daily ETL pipeline: 5 job boards '
        'scraped (WTTJ, Indeed, APEC, France Travail, Google Jobs), ICP filtering, '
        'contact enrichment via INSEE SIRENE + Firecrawl, HTML digest by email; '
        'stack Firecrawl, Serper, Modal cron, SQLite',

        '<b>Self-Outbound Engine</b> (Jan. 2026) — autonomous prospecting engine: '
        '180–270 emails/day across 6–9 warmed inboxes, reply classification, '
        'Cal.com auto-reply with human-randomized delay, Telegram alerts; stack '
        'Cloudflare Workers, Apollo, Gemini, Claude Haiku',

        '<a href="https://github.com/dmazumdar186/cv-optimizer-agent" color="#1B9AAA">'
        '<b>CV Optimizer Agent</b></a> (Apr. 2026) — AI agent (Streamlit + Gemini): '
        'ATS scoring of CV vs JD, generation of optimized CV &amp; cover letter PDFs, '
        'multilingual',

        '<a href="https://www.youtube.com/@ProdCraft" color="#1B9AAA"><b>ProdCraft</b></a> '
        '(YouTube, Sep. 2025 – Present) — ed-tech channel for aspiring Product '
        'Managers: fundamentals &amp; best practices',
    ]:
        st.append(Paragraph('<bullet>•</bullet>' + p, S['project']))

    return st


# ── Build PDF ────────────────────────────────────────────────────────────────────
def build_cv(output: Path):
    build_cv_doc(output, build_story(), margin_lr=MARGIN_LR, margin_tb=MARGIN_TB)


# ── CLI ──────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--company', default='master')
    parser.add_argument('--role',    default='AI Product Manager')
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    tmp  = root / '.tmp'
    tmp.mkdir(exist_ok=True)

    company = args.company.lower().replace(' ', '_')
    out = tmp / f'cv_{company}_debanjan_mazumdar_en.pdf'

    print(f"Generating English CV for: {args.role} @ {args.company}")
    build_cv(out)

    size_kb = out.stat().st_size / 1024
    print(f"Done: {out}  ({size_kb:.0f} KB)")
    print("Open the PDF and verify it is exactly 2 pages.")


if __name__ == '__main__':
    main()
