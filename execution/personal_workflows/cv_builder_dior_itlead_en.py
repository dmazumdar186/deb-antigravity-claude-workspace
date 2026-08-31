#!/usr/bin/env python3
"""
cv_builder_dior_itlead_en.py
description: Generate the English, ATS-optimized CV for Debanjan Mazumdar targeted at the
    Christian Dior Couture / D_NEXT "Senior IT Lead Consultant — GenAI-Assisted Development
    Deployment Program" role (JD: Downloads/IT lead job Desc.pdf). Same teal reportlab template
    and section order as cv_builder_pm_en.py; only build_story() content differs.

    Positioning: Senior product + IT program leader who has (a) led an enterprise GenAI rollout
    (Wiser) and (b) runs an agentic, specification-driven AI SDLC daily (this workspace).
    Bullets follow the "Result-first XYZ" contract (metric-first, then the method, carrying JD
    vocabulary: charter, roadmap, governance, steering, RAID, adoption KPIs, change management).

    Numbers are reconciled to personal_brand/metrics_canonical.md (Wiser = +45%/-55%/+40%/+20%;
    outbound = $1M+/~$200K; marketplace = $85K/3mo; 12+ systems; <30-day median; 15 years) and to
    counts taken from this workspace on 2026-08-28 (81 directives, 261 scripts, 1,136 tests,
    16 SAST rules, 24 rules, 447 commits since 2026-04-06); no agent count is rendered.
    Operator-supplied facts (chat, 2026-08-28): Wiser GenAI rollout was run as a program with the
    operator as lead; $150K program budget owned; steering / exec reporting to the CPO; the program
    consolidated fragmented team-by-team AI usage into one shared AI infrastructure; immediately
    available. Scale numbers (BUs / users) were NOT supplied -> none are claimed.
    Client "Accessory Masters" is NEVER named -> "high-velocity outbound consultancy".
    AgentUp links to its public live URL (agentup-iag.pages.dev, operator-owned); the
    hiring-exercise client is not named in the text.
    Review trail (2026-08-28): v1 -> v2 -> v3 iterated against four independent reviewers
    (Dior recruiter, D_NEXT hiring manager, enterprise-ATS engineer, adversarial fact-checker);
    see HANDOFF note in deliverables/cv_dior_itlead/REVIEW_LOG.md.

inputs: --out (path; default .tmp/cv_dior_itlead_debanjan_mazumdar_en.pdf)
outputs: the PDF at --out (exactly 2 pages)

Usage:
    py execution/personal_workflows/cv_builder_dior_itlead_en.py --out ".tmp/cv_dior.pdf"
    py tests/cv_ats_score_jd.py --cv ".tmp/cv_dior.pdf" --jd "C:/Users/deban/Downloads/IT lead job Desc.pdf"

Dependencies: pip install reportlab
"""

import argparse
import os
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
LINK   = '#1B9AAA'

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
    'name':      _s(fontName=FONT_BOLD, fontSize=22, textColor=NAVY, leading=26, spaceAfter=2),
    'subtitle':  _s(fontSize=9.6, textColor=TEAL, leading=13, spaceAfter=3),
    'contact':   _s(fontSize=8.1, textColor=MDGRY, leading=11, spaceAfter=0),
    'accroche':  _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=13),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.3, textColor=NAVY, leading=12, spaceAfter=1),
    'employer':  _s(fontSize=8.3, textColor=MDGRY, leading=11, spaceAfter=3),
    'bullet':    _s(fontSize=8.3, alignment=TA_JUSTIFY, leading=12.5,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.5,
                    bulletFontName=FONT),   # U+2022 in embedded Arial (ATS-parseable)
    'oneliner':  _s(fontSize=8.2, textColor=MDGRY, leading=11, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.4, textColor=NAVY, leading=11, spaceAfter=0),
    'skill_val': _s(fontSize=8.2, alignment=TA_JUSTIFY, leading=12, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=9, textColor=DKGRY, leading=12, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.2, textColor=MDGRY, leading=11, spaceAfter=5),
    'lang':      _s(fontSize=8.5, leading=12, spaceAfter=2),
    'project':   _s(fontSize=8.2, alignment=TA_JUSTIFY, leading=12,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.5,
                    bulletFontName=FONT),
}


def _link(url, label):
    return f'<a href="{url}" color="{LINK}">{label}</a>'


def _accroche(text, kpi_line):
    return accroche(text, kpi_line, style=S['accroche'], text_w=TEXT_W, bg_color=LTBLUE)


def _exp_entry(title, company_line, bullets):
    return exp_entry(title, company_line, bullets,
                     role_style=S['role'], employer_style=S['employer'],
                     bullet_style=S['bullet'], keep_first_bullet=True)


def _skill_row(cat, val):
    return skill_row(cat, val, cat_style=S['skill_cat'], val_style=S['skill_val'],
                     text_w=TEXT_W, cat_col_w=3.9, separator=' :')


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'Senior Product Manager &amp; IT Program Lead — GenAI-assisted development | '
            '15 years in software delivery &amp; digital transformation | Hands-on with agentic, '
            'specification-driven AI tooling',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            _link('mailto:debanjan186@gmail.com', 'debanjan186@gmail.com')
            + ' • +33 7 55 80 76 58 • Paris, France • '
            + _link('https://linkedin.com/in/dmazumdar/', 'linkedin.com/in/dmazumdar')
            + ' • '
            + _link('https://github.com/dmazumdar186', 'github.com/dmazumdar186')
            + ' • '
            + _link('https://prodcraft.fyi', 'prodcraft.fyi'),
            S['contact']
        ),
        Paragraph('Immediately available for consulting missions — Paris area (hybrid)', S['contact']),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 7),
    ]

    # ── Summary ─────────────────────────────────────────────────────────────────
    st.append(_accroche(
        "Senior product and IT delivery leader with <b>15 years</b> across US-headquartered "
        "B2B SaaS (retail-tech / digital commerce, healthcare, logistics, communications) and "
        "distributed US–EU–India teams. At Wiser Solutions (since 2022), has led the <b>global "
        "Generative AI program</b> end-to-end: consolidated fragmented, team-by-team AI usage "
        "into one shared AI infrastructure, and owned the roadmap and OKRs, a <b>$150K program "
        "budget</b>, go/no-go steering reviews with the CPO and BU leads, release gates and "
        "adoption / value KPIs — delivering <b>+40 % BU adoption and +20 % CSAT</b>. "
        "Builds production software daily with <b>agentic, specification-driven AI development "
        "tooling</b> (Claude Code, AI SDLC), so can align architects and engineers on their "
        "terms and management on theirs.",
        "<b>Impact:</b> 5 multidisciplinary squads coordinated across Paris, US and India  •  "
        "+45 % feature adoption and −55 % p95 latency on GenAI capabilities  •  "
        "12+ AI products shipped, &lt;30-day median",
    ))
    st.append(Spacer(1, 9))

    # ── Professional Experience ─────────────────────────────────────────────────
    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, AI &amp; Data Intelligence — Wiser Solutions',
        'US-headquartered global enterprise SaaS · Retail &amp; Digital-Commerce Intelligence · '
        'Paris | Nov 2022 – Present',
        [
            "<b>+40 % BU adoption and +20 % CSAT</b> on the company\u2019s global Generative AI "
            "rollout — as program lead end-to-end: program scope and implementation roadmap, "
            "OKRs, a <b>$150K program budget</b>, go/no-go steering reviews with the CPO and BU "
            "leads, rollback plans, and a usage / quality / drift KPI dashboard used for "
            "executive reporting and decision support.",

            "<b>5 cross-functional squads</b> (Product Managers, Product Owners, architects, "
            "engineering, data and privacy) coordinated on one prioritized roadmap across Paris, "
            "US and offshore teams — through influence, without formal authority over any squad "
            "— as the escalation point for delivery risks, dependencies and business-vs-technical "
            "trade-offs.",

            "<b>+45 % feature adoption and −55 % p95 latency</b> on GenAI capabilities (triage, "
            "recommendation, RAG support, smart alerting) — delivered through PRDs with "
            "acceptance criteria, data-readiness checklists, API contracts and LLM evaluation "
            "thresholds; GDPR / privacy-by-design and vendor-API (OpenAI, Anthropic) spend "
            "tracking and cost controls built into the release gates.",

            "Consolidated fragmented, team-by-team AI usage into <b>one shared AI infrastructure "
            "and set of shared practices</b> across the BUs — the change-management core of the "
            "program: playbooks, sprint coaching and a continuous-improvement loop on adoption "
            "metrics; the new ways of working (DoR/DoD, pre-prod QA, phased rollouts with feature "
            "flags and A/B tests) cut <b>in-sprint ambiguity −25 %</b> and lifted <b>delivery "
            "precision +25–30 %</b>.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Founder &amp; Lead Consultant — ' + _link('https://prodcraft.fyi', 'ProdCraft')
        + ' (AI Product Studio)',
        'GenAI-assisted software engineering practice · Paris (independent, alongside Wiser) | '
        'Jan 2026 – Present',
        [
            "Operates a <b>specification-driven, agentic AI SDLC</b> on Claude Code — 80+ "
            "directive specifications, <b>1,100+ automated tests</b>, static-analysis, "
            "review-agent and git-hook quality gates — and has shipped <b>12+ AI products at a "
            "&lt;30-day median</b> (0 → live) with it, including a live multilingual "
            "CV-optimizer SaaS and a GenAI roleplay-coaching app; codebase public on GitHub.",

            "Packaged the practice as an <b>adoption &amp; enablement kit</b> for AI-assisted "
            "software engineering — engineering rules, reusable playbooks, an LLM cost-routing "
            "and estimation policy, and a multi-auditor release gate (front-door synthetic, "
            "output acceptance, LLM audit loop, test suite, adversarial review) — the operating "
            "model behind every current ProdCraft delivery, offered as a reference "
            "implementation for engineering-team rollout (single-operator scale to date).",

            "<b>$1M+ qualified pipeline</b> and <b>~$200K/yr</b> of SDR cost replaced for a "
            "high-velocity outbound consultancy — by taking an autonomous outbound product from "
            "discovery to launch, with dry-run modes, health endpoints and synthetic canaries on "
            "every paid path; all code and IP handed to the client.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Data &amp; Recommendation Products — InfoTnT',
        'B2B SaaS · Paris | Jun 2021 – Nov 2022',
        [
            "<b>−35 % iteration cycles and +25 % post-launch product-market fit</b> across "
            "3 enterprise clients — by leading structured discovery (interviews, usage analysis, "
            "JTBD workshops) and translating it into a prioritized roadmap, backlog and release plan.",

            "Standardized PRDs and user stories with acceptance criteria, data contracts, API "
            "constraints and experimentation playbooks — enabling predictable squad delivery "
            "and regression-free releases.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'US enterprise SaaS · Shipping &amp; Logistics · Pune | Apr 2019 – Sep 2019',
        [
            "<b>−20 % time-to-market</b> — by mapping cross-squad dependencies, clarifying exit "
            "criteria, tightening Scrum cadence, and running structured <b>RAID (risk, "
            "assumption, issue, dependency) reviews</b> and pre-prod checklists.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'US healthcare SaaS · Pune | Jun 2018 – Feb 2019',
        [
            "<b>+30 % platform scalability and performance</b> — by introducing SLA/SLO "
            "frameworks to arbitrate run-vs-change priorities and embedding governance and QA "
            "checkpoints into the delivery flow.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner, Communications Platform — Avaya India',
        'US enterprise software · Pune | Jul 2015 – Mar 2018',
        [
            "<b>+30 % delivery velocity and −25 % requirement instability across 3 squads</b> — "
            "by strengthening Scrum discipline, structured sprint reviews and OKR ↔ roadmap "
            "alignment with US and India stakeholders.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'QA Engineer &amp; Release Coordinator — IDrive India',
        'Cloud backup software · Bengaluru | Apr 2013 – Jul 2015 — '
        '<i>QA and release management for a distributed storage platform</i>',
        []
    ):
        st.append(item)

    for item in _exp_entry(
        'Software Engineer — Tata Consultancy Services',
        'IT services · Bengaluru | Nov 2010 – Mar 2013 — '
        '<i>foundations in distributed systems engineering</i>',
        []
    ):
        st.append(item)
    st.append(Spacer(1, 3))

    # ── Skills ──────────────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Skills'),
        Spacer(1, 5),
        _skill_row(
            'Program Leadership',
            'IT Program Management • Digital Transformation • Deployment Roadmap &amp; OKRs • '
            'Governance Framework (go/no-go steering reviews, release gates) • Risk &amp; '
            'Dependency Register (RAID), Risk Mitigation • Executive Reporting &amp; Decision '
            'Support • Program Budget Tracking (incl. vendor / LLM spend) • Change '
            'Management, GenAI Adoption Strategy &amp; Planning • KPI &amp; Value Measurement • Vendor &amp; '
            'Partner Coordination • Communication &amp; Facilitation (workshops, playbooks, sprint '
            'coaching) • Data-Driven Decision Making',
        ),
        _skill_row(
            'Agile &amp; Delivery',
            'Scrum • Kanban • Product-Oriented Delivery Models • OKRs • Roadmap &amp; Backlog '
            'Prioritization • PRDs &amp; Acceptance Criteria • DoR/DoD • Release Gates &amp; '
            'Rollback • Cross-Functional Coordination • Dependency Management • Pre-Prod QA • '
            'Continuous Improvement',
        ),
        _skill_row(
            'AI-Assisted Engineering',
            'AI-Assisted Software Engineering Tools (Claude Code — agentic development; '
            'GitHub Copilot-class assistants) • AI SDLC • Specification-Driven Development • '
            'Generative AI Deployment (global rollout) • LLM Evaluation Frameworks • RAG • Multi-Agent '
            'Systems • MCP • LLM Cost Governance',
        ),
        _skill_row(
            'Governance',
            'GDPR / Privacy-by-Design • Security &amp; Access Control • Audit Trails • '
            'Responsible AI • Regulatory Compliance',
        ),
        _skill_row(
            'Tools',
            'Jira • Confluence • Notion • Miro • Figma • Mixpanel • Amplitude • SQL • Python • '
            'Git / GitHub • Cloudflare Workers • Modal • n8n • GenAI APIs (OpenAI, Anthropic, Google)',
        ),
        Spacer(1, 8),
    ]
    st.append(KeepTogether(competences))

    # ── Education ────────────────────────────────────────────────────────────────
    st.append(SectionHeader('Education'))
    st.append(Spacer(1, 5))
    st.append(Paragraph('MSc International Strategic Business', S['edu_title']))
    st.append(Paragraph('Toulouse Business School, Paris | 2019–2021', S['edu_sub']))
    st.append(Paragraph('BE Information Technology Engineering', S['edu_title']))
    st.append(Paragraph('CMR Institute of Technology, Bengaluru | 2006–2010', S['edu_sub']))

    # ── Languages ───────────────────────────────────────────────────────────────
    st.append(SectionHeader('Languages'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>English</b> : Bilingual (C2) — daily working language • '
        '<b>French</b> : Bilingual (C2) • <b>Hindi</b> : Native • <b>Bengali</b> : Native',
        S['lang']
    ))
    st.append(Spacer(1, 8))

    # ── Selected Projects ───────────────────────────────────────────────────────
    st.append(SectionHeader('Selected Projects'))
    st.append(Spacer(1, 5))
    for p in [
        _link('https://agentup-iag.pages.dev', '<b>AgentUp</b>')
        + ' (live) — GenAI roleplay-coaching app for call-center agents, built '
        'specification-first: <b>75-requirement PRD with full traceability matrix</b>, '
        'streaming LLM with automatic provider fallback, client-side PII redaction, '
        '<b>95 automated tests</b>; Astro + Cloudflare Pages.',

        _link('https://cv-optimizer.pages.dev', '<b>CV Optimizer</b>')
        + ' (live SaaS) — multilingual app that scores a CV against a job description and '
        'generates an ATS-optimized CV &amp; cover letter; eval-first build with per-field '
        'language and format validators.',

        '<b>Two-sided marketplace</b> (with a partner agency, under NDA) — Stripe Connect '
        'payments platform processing <b>$85K in the first 3 months</b>; owned scope, roadmap '
        'and partner coordination; React + Node + Postgres.',
    ]:
        st.append(Paragraph('<bullet>•</bullet>' + p, S['project']))

    return st


# ── Build PDF ────────────────────────────────────────────────────────────────────
def build_cv(output: Path):
    """Render to <output>.part then atomically replace, so a chained gate never reads a
    half-written PDF (race observed 2026-08-28 when the scorer ran straight after the build)."""
    part = output.with_suffix(output.suffix + '.part')
    build_cv_doc(part, build_story(), margin_lr=MARGIN_LR, margin_tb=MARGIN_TB,
                 title='CV MAZUMDAR Debanjan — Senior IT Lead, GenAI-Assisted Development',
                 author='Debanjan Mazumdar')
    if part.stat().st_size < 10_000:
        raise RuntimeError(f"rendered PDF suspiciously small: {part.stat().st_size} bytes")
    os.replace(part, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    tmp = root / '.tmp'
    tmp.mkdir(exist_ok=True)
    out = args.out or (tmp / 'cv_dior_itlead_debanjan_mazumdar_en.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)

    print("Generating Dior / D_NEXT Senior IT Lead English CV")
    build_cv(out)
    size_kb = out.stat().st_size / 1024
    print(f"Done: {out}  ({size_kb:.0f} KB)")
    print("Verify it is exactly 2 pages.")


if __name__ == '__main__':
    main()
