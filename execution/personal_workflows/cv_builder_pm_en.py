#!/usr/bin/env python3
"""
cv_builder_pm_en.py
description: Generate the ATS-optimized, English-language, GENERIC Senior-Product-Manager PDF
    CV for Debanjan Mazumdar (PM-first positioning; AI kept as one strength). Same teal
    reportlab template as cv_builder_en.py; only build_story() content differs. Bullets follow
    the "Result-first XYZ" contract (metric-first, then method carrying JD keywords).
inputs: --out (path; default .tmp/cv_pm_master_debanjan_mazumdar_en.pdf)
outputs: the PDF at --out (exactly 2 pages)

Numbers are reconciled to personal_brand/metrics_canonical.md (Wiser = +45%/-55%; outbound =
$1M+/48k/4%/~$200K; marketplace = $85K/3mo; 12+ systems; <30-day median; 15 years). Client
"Accessory Masters" is NEVER named -> "high-velocity outbound consultancy".

Usage:
    py execution/personal_workflows/cv_builder_pm_en.py --out ".tmp/cv_pm_en.pdf"

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
                     bullet_style=S['bullet'], keep_first_bullet=True)


def _skill_row(cat, val):
    return skill_row(cat, val, cat_style=S['skill_cat'], val_style=S['skill_val'],
                     text_w=TEXT_W, separator=' :')


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'Senior Product Manager | Product Discovery • Roadmap &amp; OKR • '
            'Data-Driven Delivery • B2B &amp; B2C SaaS',
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
        "Senior Product Manager with <b>15 years</b> delivering data-intensive B2B and B2C "
        "products across SaaS, e-commerce and AI-powered platforms. I own the full product "
        "lifecycle — continuous discovery (user research, JTBD, quant/qual) → roadmap and OKRs "
        "→ agile delivery → post-launch measurement — turning ambiguous business needs into "
        "shipped, measurable outcomes. Fluent with both engineering and executive stakeholders; "
        "I de-risk delivery because I can frame the business case and read the build.",
        "<b>Impact:</b> +45 % feature adoption  •  +20 % CSAT  •  $1M+ qualified pipeline delivered",
    ))
    st.append(Spacer(1, 9))

    # ── Professional Experience ─────────────────────────────────────────────────
    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager — AI &amp; Data Intelligence — Wiser Solutions',
        'B2B SaaS · Market Intelligence, Paris | Nov. 2022 – Present',
        [
            "<b>+45 % feature adoption and −55 % p95 latency</b> — by owning the end-to-end "
            "lifecycle of data &amp; AI capabilities (triage, recommendation, RAG support, smart "
            "alerting): PRDs with acceptance criteria, data-readiness checklists and API contracts.",

            "Led continuous discovery (user interviews, JTBD, quant/qual), defined OKRs and "
            "aligned 5 cross-functional squads on a prioritized roadmap with go/no-go gates and "
            "rollback plans — driving <b>+40 % BU adoption and +20 % CSAT</b> on a global rollout.",

            "<b>−25 % in-sprint ambiguity and +25–30 % delivery precision</b> — by running "
            "experimentation (A/B tests, feature flags, phased rollouts) on Mixpanel "
            "usage/quality/drift dashboards, with DoR/DoD, pre-prod QA and GDPR/privacy-by-design.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Independent Product Consultant — '
        '<a href="https://prodcraft.fyi" color="#1B9AAA">ProdCraft</a> (AI Product Studio)',
        'Paris (Freelance, alongside Wiser) | Jan. 2026 – Present',
        [
            "<b>$1M+ qualified pipeline</b> and <b>~$200K/yr of SDR cost</b> replaced — by "
            "taking an autonomous outbound product from discovery to launch for a high-velocity "
            "outbound consultancy, with reply automation and a 3-hour hot-lead SLA.",

            "<b>$85K processed in the first 3 months</b>, after co-building and launching a "
            "two-sided Stripe Connect marketplace (React + Node + Postgres) with a partner "
            "agency — owning scoping, roadmap and go-to-market.",

            "<b>12+ products shipped end-to-end</b> across independent and client work, at a "
            "<b>&lt;30-day median</b> — including a multilingual CV-optimizer SaaS and a "
            "code-audit CLI — owning discovery, PRDs and release gates.",

            "One senior operator on every engagement, from user discovery to launch — owning "
            "the roadmap, data contracts and stakeholder alignment; all code and IP handed to "
            "the client.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager — Data &amp; Recommendation Products — InfoTnT',
        'B2B SaaS, Paris | Jun. 2021 – Nov. 2022',
        [
            "<b>−35 % iteration cycles and +25 % post-launch product-market fit</b> — by leading "
            "structured discovery (user interviews, usage analysis, JTBD workshops) and "
            "translating insights into a prioritized roadmap and backlog.",

            "Authored detailed PRDs and user stories with acceptance criteria, data contracts and "
            "API constraints, and standardized experimentation playbooks — enabling reliable squad "
            "delivery and preventing regressions.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'Enterprise SaaS, Pune | Apr. – Sep. 2019',
        [
            "<b>−20 % time-to-market</b> — by mapping cross-squad dependencies, clarifying exit "
            "criteria, tightening Scrum cadence, and adding pre-prod checklists and structured "
            "RAID reviews.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'Healthcare SaaS, Pune | Jun. 2018 – Feb. 2019',
        [
            "<b>+30 % platform scalability and performance</b> — by introducing SLA/SLO "
            "frameworks to arbitrate run/change priorities and embedding governance and QA "
            "checkpoints into the delivery flow.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner — Communications Platform — Avaya India',
        'Enterprise Software, Pune | Jul. 2015 – Mar. 2018',
        [
            "<b>+30 % delivery velocity and −25 % requirement instability</b> — by strengthening "
            "Scrum discipline, structured sprint reviews and tight OKR ↔ roadmap alignment across "
            "3 squads.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2010 – 2015 :</b> Software Engineer '
        '(Tata Consultancy Services, Bengaluru | Nov. 2010 – Mar. 2013) → '
        'QA Engineer / Release Coordinator (IDrive India, Bengaluru | Apr. 2013 – Jul. 2015) — '
        '<i>foundations in distributed systems, QA and release management</i>',
        S['oneliner']
    ))
    st.append(Spacer(1, 8))

    # ── Skills ──────────────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Skills'),
        Spacer(1, 5),
        _skill_row(
            'Product Mgmt',
            'Product Discovery (User Research, Interviews, JTBD, Quant/Qual) • Product Strategy '
            '&amp; Vision • Roadmap &amp; OKR • PRD &amp; User Stories • Acceptance Criteria • '
            'Backlog Prioritization (Value/Risk/Effort) • A/B Testing &amp; Experimentation • '
            'Product Lifecycle • Customer Experience (UX) • GTM &amp; Launch Enablement • '
            'KPI/Metric Design • Stakeholder Management • Product Ownership &amp; Leadership',
        ),
        _skill_row(
            'Agile &amp; Delivery',
            'Scrum • Kanban • Sprint Planning &amp; Retrospectives • DoR/DoD • Release Gates &amp; '
            'Rollback • Cross-Functional Collaboration &amp; Leadership • Dependency Management • Pre-Prod QA',
        ),
        _skill_row(
            'Data &amp; AI',
            'Data Contracts &amp; API Readiness • Analytics (Mixpanel) • SQL • Drift &amp; Quality '
            'Monitoring • AI/GenAI Product Design (LLM, RAG, Agentic AI) • ML Evaluation Frameworks',
        ),
        _skill_row(
            'Governance',
            'GDPR / Privacy-by-Design • Access Control • Audit Trails • Ethical AI • '
            'Regulatory Compliance',
        ),
        _skill_row(
            'Tools',
            'Jira • Confluence • Figma • Miro • Mixpanel • Amplitude • Notion • SQL • N8N • Make • '
            'GenAI APIs (OpenAI, Anthropic, Google)',
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
        '<b>English</b> : Bilingual (C2) • <b>French</b> : Bilingual (C2) • '
        '<b>Hindi</b> : Native • <b>Bengali</b> : Native',
        S['lang']
    ))
    st.append(Spacer(1, 8))

    # ── Selected Projects ───────────────────────────────────────────────────────
    st.append(SectionHeader('Selected Projects'))
    st.append(Spacer(1, 5))
    for p in [
        '<a href="https://cv-optimizer.pages.dev" color="#1B9AAA"><b>CV Optimizer</b></a> '
        '(live SaaS) — multilingual app that scores a CV against a job description and generates '
        'an ATS-optimized CV &amp; cover letter; product-owned end-to-end (discovery → delivery).',

        '<b>Two-sided marketplace</b> (with a partner agency, under NDA) — Stripe Connect '
        'payments platform processing <b>$85K in the first 3 months</b>; React + Node + Postgres.',

        '<a href="https://prodcraft.fyi" color="#1B9AAA"><b>ProdCraft</b></a> '
        '(AI product studio, prodcraft.fyi) — independent studio shipping production AI products '
        'for founders and teams at a <b>&lt;30-day median</b>, from discovery to launch.',
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
    out = args.out or (tmp / 'cv_pm_master_debanjan_mazumdar_en.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)

    print("Generating GENERIC Senior-PM English CV")
    build_cv(out)
    size_kb = out.stat().st_size / 1024
    print(f"Done: {out}  ({size_kb:.0f} KB)")
    print("Verify it is exactly 2 pages.")


if __name__ == '__main__':
    main()
