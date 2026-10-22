#!/usr/bin/env python3
"""
cv_builder_ai_po_isd_en.py
description: Generate the English, ATS-optimised AI PRODUCT OWNER / PRODUCT MANAGER (ISD, Lyon)
    variant of Debanjan Mazumdar's PDF CV. Target JD: "AI Product Owner / Product Manager —
    Information Systems Department, reports to Data/AI Manager, CDI, Lyon" (anonymised, 2026-10).
    Framing: French-style brevity (short factual bullets, no first person, no adjectives that
    do not carry a number), Product-Owner vocabulary (backlog, delivery cadence, risk
    escalation, business partnering, change management, responsible AI, KPIs, governance),
    key figures in bold. Same teal reportlab template as cv_builder_ai_pm_en.py; only
    build_story() content differs. Nothing is invented: every figure comes from
    cv_builder_ai_pm_en.py / metrics_canonical.md; projects come from github.com/dmazumdar186.
inputs: --out (path; default .tmp/cv_ai_po_isd_debanjan_mazumdar_en.pdf)
outputs: the PDF at --out (exactly 2 pages)

Usage:
    python3 execution/personal_workflows/cv_builder_ai_po_isd_en.py --out ".tmp/cv_isd.pdf"

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

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_LR = 1.8 * cm
MARGIN_TB = 1.5 * cm
TEXT_W = PAGE_W - 2 * MARGIN_LR

# ── Colours ─────────────────────────────────────────────────────────────────────
NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')
LINK   = '#1B9AAA'


# ── Fonts (DejaVu staged as Arial on non-Windows, see cv_builder_ai_pm_en.py) ──
def _register_isd_fonts():
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    have_real_arial = (
        os.path.exists(os.path.join(win_fonts, 'arial.ttf'))
        and os.path.exists(os.path.join(win_fonts, 'arialbd.ttf'))
    )
    if not have_real_arial:
        dejavu_reg = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        dejavu_bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if os.path.exists(dejavu_reg) and os.path.exists(dejavu_bold):
            stage = Path(tempfile.gettempdir()) / 'cv_ai_po_isd_fake_winfonts' / 'Fonts'
            stage.mkdir(parents=True, exist_ok=True)
            for src, name in ((dejavu_reg, 'arial.ttf'), (dejavu_bold, 'arialbd.ttf')):
                dst = stage / name
                if not dst.exists():
                    shutil.copy(src, dst)
            os.environ['WINDIR'] = str(stage.parent)
    return _register_fonts()


FONT, FONT_BOLD = _register_isd_fonts()


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
    'accroche':  _s(fontSize=8.7, alignment=TA_JUSTIFY, leading=13.2),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.1, textColor=NAVY, leading=11.8, spaceAfter=1),
    'employer':  _s(fontSize=8.5, textColor=MDGRY, leading=11.5, spaceAfter=3),
    'bullet':    _s(fontSize=8.5, alignment=TA_JUSTIFY, leading=12.7,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
    'oneliner':  _s(fontSize=8.4, textColor=MDGRY, leading=11.5, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.2, textColor=NAVY, leading=10.8, spaceAfter=0),
    'skill_val': _s(fontSize=8.4, alignment=TA_JUSTIFY, leading=12.3, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=8.8, textColor=DKGRY, leading=11.8, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.0, textColor=MDGRY, leading=10.8, spaceAfter=5),
    'lang':      _s(fontSize=8.3, leading=11.6, spaceAfter=2),
    'project':   _s(fontSize=8.4, alignment=TA_JUSTIFY, leading=12.3,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
}


def _accroche(text, kpi_line):
    return accroche(text, kpi_line, style=S['accroche'], text_w=TEXT_W, bg_color=LTBLUE)


def _exp_entry(title, company_line, bullets):
    return exp_entry(title, company_line, bullets,
                     role_style=S['role'], employer_style=S['employer'],
                     bullet_style=S['bullet'], keep_first_bullet=True)


def _skill_row(cat, val):
    return skill_row(cat, val, cat_style=S['skill_cat'], val_style=S['skill_val'],
                     text_w=TEXT_W, cat_col_w=3.8, separator=' :')


def _link(url, text):
    return f'<a href="{url}" color="{LINK}">{text}</a>'


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'AI Product Owner / Product Manager | GenAI · RAG · AI Agents | '
            '<b>11 yrs</b> PO/PM · <b>15 yrs</b> B2B software',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • +33 7 55 80 76 58 • Paris, France — available for Lyon'
            ' • ' + _link('https://linkedin.com/in/dmazumdar/', 'linkedin.com/in/dmazumdar')
            + ' • ' + _link('https://github.com/dmazumdar186', 'github.com/dmazumdar186')
            + ' • ' + _link('https://prodcraft.fyi', 'prodcraft.fyi'),
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 6),
    ]

    # ── Summary ─────────────────────────────────────────────────────────────────
    st.append(_accroche(
        "Product Owner / Product Manager, <b>11 years</b> on data and AI products, the last "
        "four on GenAI. Used to sitting between an IT department, business lines and a "
        "Data/AI lead: a vague business need becomes a backlog developers can work from, "
        "then gets followed through to adoption. Hands-on enough on <b>LLM, RAG and "
        "agents</b> to challenge a vendor or an estimate. <b>12+ AI products</b> delivered, "
        "median <b>under 30 days</b>. Healthcare and enterprise-software background.",
        "<b>Key figures:</b> <b>+45%</b> adoption • <b>+20%</b> CSAT • <b>−55%</b> p95 latency "
        "• <b>$150K</b> AI budget owned • <b>~$200K/yr</b> cost removed • <b>5</b> squads "
        "coordinated on 3 continents",
    ))
    st.append(Spacer(1, 8))

    # ── Professional Experience ─────────────────────────────────────────────────
    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, AI &amp; Data Intelligence — Wiser Solutions',
        'B2B SaaS · Retail &amp; Digital-Commerce Intelligence · Paris | Nov 2022 – Present',
        [
            "Owner of the <b>AI/GenAI product line</b> (RAG assistant on OpenAI / Anthropic, "
            "recommendations, smart alerting): vision and roadmap with the <b>CPO</b>, weekly "
            "backlog refinement with business and dev, release gated by LLM evaluation "
            "(golden set, LLM-as-judge). <b>+45%</b> feature adoption, <b>−55%</b> p95 latency.",

            "Ran the <b>company-wide GenAI rollout</b>: OKRs, <b>$150K</b> budget, vendor and "
            "model evaluation (build vs. buy), go/no-go reviews with the CPO and BU heads, "
            "change management and onboarding per BU. <b>+40%</b> BU adoption, <b>+20%</b> CSAT.",

            "Point of contact for business stakeholders: needs gathering, use case "
            "qualification by ROI, expectation management. <b>5</b> cross-functional squads "
            "(Paris, US, India) on one roadmap, without line authority.",

            "Delivery and risk: <b>A/B tests</b>, feature flags, drift monitoring, "
            "<b>GDPR / privacy-by-design</b> written into every AI story. <b>−25%</b> "
            "in-sprint ambiguity, <b>+25–30%</b> delivery predictability.",

        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Founder &amp; AI Product Consultant — ' + _link('https://prodcraft.fyi', 'ProdCraft'),
        'Independent AI product studio, Paris (alongside Wiser) | Jan 2026 – Present',
        [
            "<b>12+ AI products</b> shipped, <b>&lt;30-day</b> median, owning discovery, PRDs, "
            "backlog and release gates. One agentic outbound pipeline (Claude classification, "
            "Cloudflare Workers, <b>32</b> inboxes, <b>3-hour</b> SLA): <b>$1M+</b> qualified "
            "pipeline, <b>~$200K/yr</b> of manual work removed.",

            "Co-launched a Stripe Connect marketplace (React, Node, Postgres): <b>$85K</b> "
            "processed in the first 3 months.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Data &amp; Recommendation Products — InfoTnT',
        'B2B SaaS · Paris | Jun 2021 – Nov 2022',
        [
            "Set up product discovery (interviews, JTBD, usage analytics) and a prioritised "
            "backlog where there was none. <b>−35%</b> iteration cycles, <b>+25%</b> "
            "product-market-fit score.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2019 – 2021:</b> MSc International Strategic Business, Toulouse Business School, '
        'Paris (full-time).',
        S['oneliner']
    ))
    st.append(Spacer(1, 4))

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'Shipping &amp; Logistics SaaS · Pune | Apr 2019 – Sep 2019',
        [
            "Backlog, Scrum cadence, dependency mapping and RAID risk reviews for a data "
            "platform team. <b>−20%</b> time-to-market.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'Healthcare SaaS (US payers and providers) · Pune | Jun 2018 – Feb 2019',
        [
            "Data product backlog in a regulated healthcare context (compliance, privacy): "
            "SLA/SLO framework, QA governance, documentation standards. <b>+30%</b> platform "
            "scalability.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner, Communications Platform — Avaya India',
        'Enterprise software · Pune | Jul 2015 – Mar 2018',
        [
            "Product Owner for <b>3</b> Scrum squads: backlog, sprint goals, OKR-to-roadmap "
            "alignment. <b>+30%</b> delivery velocity, <b>−25%</b> requirement churn.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2010 – 2015:</b> Software Engineer, Tata Consultancy Services → QA / Release '
        'Coordinator, IDrive. <i>Distributed systems, release management.</i>',
        S['oneliner']
    ))
    st.append(Spacer(1, 7))

    # ── Skills ──────────────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Skills'),
        Spacer(1, 5),
        _skill_row(
            'Product owner',
            'Product vision &amp; roadmap • Backlog ownership &amp; refinement • User stories • '
            'Prioritisation (RICE, WSJF) • Delivery cadence &amp; risk escalation • KPIs &amp; '
            'adoption tracking • Agile (Scrum, Kanban)',
        ),
        _skill_row(
            'Partnering',
            'Needs gathering with non-technical teams • Use case qualification by ROI • '
            'Change management • Support materials • Reporting to senior stakeholders',
        ),
        _skill_row(
            'AI &amp; data',
            'LLM (OpenAI, Anthropic, Google) • RAG • AI agents • Prompt engineering • LLM '
            'evaluation &amp; guardrails • Data pipelines • Vendor / model evaluation • MCP • '
            'LLM cost governance',
        ),
        _skill_row(
            'Responsible AI',
            'GDPR / privacy-by-design • EU AI Act • Explainability &amp; fairness checks • '
            'PII redaction • Audit trails • AI governance documentation',
        ),
        _skill_row(
            'Build',
            'Python • SQL • n8n • Make • Cloudflare Workers • Modal • APIs • CI/CD • Claude Code',
        ),
        Spacer(1, 7),
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
        '<b>English</b>: bilingual (C2) • <b>French</b>: bilingual (C2) • '
        '<b>Hindi / Bengali</b>: native',
        S['lang']
    ))
    st.append(Spacer(1, 7))

    # ── Selected Projects (public, github.com/dmazumdar186) ─────────────────────
    st.append(SectionHeader('Selected Projects — open source'))
    st.append(Spacer(1, 5))
    for p in [
        _link('https://github.com/dmazumdar186/anneal', '<b>Anneal</b>') +
        ': LLM audit-fix and red-vs-blue loops that harden code changes. A release gate '
        'for AI-generated code.',

        _link('https://github.com/dmazumdar186/cv-optimizer-agent', '<b>CV Optimizer</b>') +
        ' (live SaaS): scores a CV against a job description and rewrites it; eval-first.',

        _link('https://github.com/dmazumdar186/youtube-video-analyzer',
              '<b>YouTube Video Analyzer</b>') +
        ': vision-model breakdowns; model routing and scene detection cut token spend.',

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
    out = args.out or (tmp / 'cv_ai_po_isd_debanjan_mazumdar_en.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)

    print("Generating AI Product Owner / PM (ISD, Lyon) English CV")
    build_cv(out)
    print(f"Done: {out}  ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == '__main__':
    main()
