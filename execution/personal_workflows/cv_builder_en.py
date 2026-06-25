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
            'AI Product Manager &amp; Builder | GenAI • RAG • '
            'Agentic AI • LLM • Automation — shipped to production',
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
        "AI Product Manager and hands-on builder — 15 years in data-intensive product. "
        "I ship production AI systems end-to-end: GenAI/RAG features, multi-agent workflows, "
        "cold-email engines, voice AI and full-stack apps, built with Claude Code and live in "
        "weeks, not quarters. A rare pairing of product judgment (discovery, AI PRDs, "
        "GDPR/governance, cross-BU alignment) and a builder practice (Python, Cloudflare Workers, "
        "Modal, LLM orchestration, eval harnesses) that de-risks delivery.",
        "<b>Impact:</b> $1M+ pipeline generated • 48,000+ emails/mo at 4 %+ reply "
        "• +45 % GenAI adoption • −55 % p95 latency • &lt;30-day median ship "
        "• 12+ AI systems shipped",
    ))
    st.append(Spacer(1, 9))

    # ── Professional Experience ─────────────────────────────────────────────────
    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'AI Product Manager',
        'Wiser Solutions, Paris | Nov. 2022 – Present',
        [
            "Shipped production GenAI capabilities (triage, recommendation, RAG support, "
            "smart alerts) achieving <b>+45 % feature adoption and −55 % p95 latency</b>, by "
            "orchestrating OpenAI/Claude multi-agent systems (MCP, A2A) with eval thresholds "
            "and prompt-cache-aware cost control",

            "Drove <b>+40 % BU adoption and +20 % CSAT</b> on the global GenAI rollout by "
            "authoring AI PRDs (API/data contracts, GDPR/privacy-by-design), running technical "
            "feasibility reviews, and aligning <b>5 cross-BU teams</b> on a shared roadmap with "
            "go/no-go gates and rollback plans",

            "Lifted delivery precision <b>+25–30 %</b> and cut sprint ambiguity <b>~25 %</b> by "
            "standing up usage/quality/drift dashboards and DoR/DoD + pre-prod QA",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'AI Product Engineer (Freelance)',
        'High-velocity outbound consultancy (confidential), remote | Dec. 2025 – Mar. 2026',
        [
            "Designed and shipped an autonomous cold-email engine at scale — "
            "<b>48,000+ emails/month at 4 %+ reply rate</b>, generating <b>$1M+ qualified "
            "pipeline</b> and replacing <b>~$200K/yr of SDR headcount</b>, with Claude-powered "
            "personalization, reply classification and contextual auto-reply "
            "(3-hour hot-lead SLA via Telegram)",

            "Architected a serverless event-driven stack (Cloudflare Workers + KV cron, "
            "Instantly webhooks, GoHighLevel CRM, scheduled Modal jobs) with idempotency keys, "
            "60-day dedup TTL and LLM guardrails",

            "Productized monitoring & governance: operator dashboard, <b>/api/health</b> "
            "endpoint, <b>--dry-run</b> on every paid path, synthetic canary "
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

    # Condensed early-career line: TCS + IDrive collapsed into one row under Avaya.
    st.append(Paragraph(
        '<b>2010 – 2015 :</b> Software Engineer '
        '(Tata Consultancy Services, Bengaluru | Nov. 2010 – Mar. 2013) → '
        'QA Engineer / Release Coordinator '
        '(IDrive India, Bengaluru | Apr. 2013 – Jul. 2015) — '
        '<i>technical foundations in distributed systems and release management</i>',
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
        '<b>English</b> : Bilingual (C2) • '
        '<b>French</b> : Bilingual (C2) • '
        '<b>Hindi</b> : Native • '
        '<b>Bengali</b> : Native',
        S['lang']
    ))
    st.append(Spacer(1, 8))

    # ── Selected Builds ─────────────────────────────────────────────────────────
    # The differentiator no pure-PM CV has: production systems shipped hands-on.
    st.append(SectionHeader('Selected Builds'))
    st.append(Spacer(1, 5))

    for p in [
        '<a href="https://cv-optimizer.pages.dev" color="#1B9AAA"><b>CV Optimizer</b></a> '
        '(live SaaS) — multilingual AI app that scores a CV against a job description and '
        'generates an ATS-optimized CV &amp; cover letter; Streamlit + Gemini, deployed on '
        'Cloudflare Pages/Workers',

        '<b>Two-sided marketplace</b> (with a partner agency, under NDA) — Stripe Connect '
        'payments platform processing <b>$85K in the first 3 months</b>; React + Node + Postgres',

        '<b>anneal</b> (Python CLI) — self-iterating code-audit loop over <i>git diff</i> '
        '(classic + adversarial Red-vs-Blue), dual-adapter LLM (Anthropic + OpenRouter), '
        'terminates on 2 consecutive zero-bug rounds',

        '<a href="https://github.com/dmazumdar186/youtube-video-analyzer" color="#1B9AAA">'
        '<b>YouTube Video Analyzer</b></a> — frame-by-frame video breakdown: PySceneDetect + '
        'perceptual dedup + 3×3 tiling (<b>−85 % vision tokens</b>) + multi-model routing; '
        '73 tests, 8 clean audit rounds',

        '<b>job_search_v2</b> — daily multi-source job aggregator (3 live sources), typed '
        'Pydantic v2 pipeline with persistent SQLite dedup and a Gemini A/B/C ranker; '
        'runs in CI at <b>€0/month</b>',
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
