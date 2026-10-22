#!/usr/bin/env python3
"""
cv_builder_senior_pm_en.py
description: Generate the English GENERIC Senior Product Manager / Senior AI Product Manager PDF CV
    for Debanjan Mazumdar, built from a keyword model of 10 real EN postings (research in
    .tmp/jd_research/en, 2026-10-22: Brevo, Pigment, Pennylane, Datadog, Doctolib, Front, Photoroom,
    Mistral, Intercom x2). Core terms carried: end-to-end ownership, outcome metrics, strategy and
    roadmap, problem framing, prioritisation and trade-offs, discovery, experiments, launch, AI
    fluency, technical fluency with engineers, design partnership, platform/API, cross-functional
    collaboration, autonomy. French-style brevity; key figures in bold; no first person. Same teal
    reportlab template as cv_builder_ai_pm_en.py (shared cv_builder_core primitives); nothing
    invented — every figure already exists in cv_builder_ai_pm_en.py / metrics_canonical.md.
inputs: --out (path; default .tmp/cv_senior_pm_debanjan_mazumdar_en.pdf)
outputs: the PDF at --out (exactly 2 pages)

Usage:
    python3 execution/personal_workflows/cv_builder_senior_pm_en.py --out ".tmp/cv_en.pdf"

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
    """Stage DejaVu Sans under the Arial names core expects when Windows fonts are absent."""
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
            'Senior Product Manager — AI, Data &amp; Growth Products | B2B SaaS | '
            '<b>15 years</b> in software, <b>11</b> in product',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • +33 7 55 80 76 58 • Paris, France'
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
        "Senior Product Manager, <b>15 years</b> in B2B software, <b>11</b> owning products end to "
        "end: Product Owner on enterprise platforms, then Senior PM for AI, data and growth "
        "products. Four years on GenAI at Wiser Solutions: launched a RAG assistant "
        "(<b>+45%</b> adoption), priced the AI tier (<b>+18%</b> ARPU), ran a <b>$150K</b> "
        "company-wide rollout. Engineering degree; prototypes in Claude Code before writing the "
        "spec. Targeting Senior PM, Senior AI PM or Growth PM roles in B2B SaaS, Paris or remote.",
        "<b>Selected impact:</b> +45% adoption • +18% ARPU • +32% trial-to-paid • −55% p95 "
        "latency • $1M+ pipeline • ~$200K/yr cost removed",
    ))
    st.append(Spacer(1, 8))

    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, AI &amp; Data Intelligence — Wiser Solutions',
        'B2B SaaS · Retail &amp; Digital-Commerce Intelligence · Paris | Nov 2022 – Present',
        [
            "Launched a RAG assistant on OpenAI and Anthropic APIs, from JTBD interviews and "
            "Figma flows to release, lifting feature adoption <b>45%</b> and cutting p95 "
            "latency <b>55%</b>.",

            "Priced and packaged the AI tier (product-led upsell, Mixpanel funnel), raising "
            "ARPU <b>18%</b>.",

            "Led the company-wide GenAI rollout on a <b>$150K</b> budget: build-vs-buy across "
            "OpenAI, Anthropic and Google, go/no-go with the CPO and BU heads, onboarding per "
            "unit. BU adoption <b>+40%</b>, CSAT <b>+20%</b>.",

            "Aligned <b>5</b> squads (engineering, design, data) across Paris, the US and India "
            "on one prioritised roadmap without line authority, cutting in-sprint ambiguity "
            "<b>25%</b> and raising delivery predictability <b>25–30%</b>.",

            "Set LLM evaluation gates (golden set, LLM-as-judge), guardrails and cost per call "
            "as release criteria; ran A/B tests and feature-flagged launches with drift "
            "monitoring in production, GDPR by design.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Founder &amp; AI Product Consultant — ' + _link('https://prodcraft.fyi', 'ProdCraft'),
        'Independent AI product studio, Paris (evenings and weekends, alongside Wiser) | '
        'Jan 2026 – Present',
        [
            "Shipped <b>12+</b> AI products for clients at a <b>&lt;30-day</b> median from brief "
            "to production, owning discovery, PRD, MVP and release gate.",

            "Built an agentic outbound pipeline (Claude classification, Cloudflare Workers, "
            "<b>32</b> inboxes, <b>3-hour</b> SLA) that sourced a <b>$1M+</b> qualified "
            "pipeline and replaced ~<b>$200K/yr</b> of manual work.",

            "Turned rapid prototyping into a sales tool: rebuilt <b>6</b> prospects' websites "
            "as live concept redesigns with pitch decks in <b>4 weeks</b> (research, Figma-grade "
            "design, Cloudflare Pages), each opening a client conversation.",

            "Designed a candidate sourcing system for a recruitment client (multi-source "
            "harvest, evidence checks, Recruit CRM sync): <b>≥90%</b> grade precision on a "
            "labelled set.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Data &amp; Recommendation Products — InfoTnT',
        'B2B SaaS · Paris | Jun 2021 – Nov 2022',
        [
            "Introduced product-led growth (self-serve trial, pricing tests, Mixpanel funnel), "
            "raising trial-to-paid conversion <b>32%</b>.",

            "Set up continuous discovery (customer interviews, JTBD / Outcome-Driven "
            "Innovation, usage analytics) and a prioritised roadmap, cutting iteration cycles "
            "<b>35%</b> and lifting the product-market-fit score <b>25%</b>.",

            "Wrote the PRDs and Figma flows for the recommendation engine; ran the backlog in "
            "Jira and Confluence.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2019 – 2021:</b> MSc International Strategic Business, Toulouse Business School, '
        'Paris (full-time, career break for study).',
        S['oneliner']
    ))
    st.append(Spacer(1, 4))

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'Shipping &amp; Logistics SaaS · Pune | Apr 2019 – Sep 2019',
        [
            "Cut time-to-market <b>20%</b> on a data platform release by mapping dependencies, "
            "fixing the Scrum cadence and running RAID risk reviews.",

            "Owned backlog and sprint goals in Jira for a distributed data team.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'Healthcare SaaS (regulated, US payers and providers) · Pune | Jun 2018 – Feb 2019',
        [
            "Improved platform scalability <b>30%</b> by introducing an SLA/SLO framework and QA "
            "governance for the data products.",

            "Adopted JTBD / Outcome-Driven Innovation for discovery under healthcare "
            "compliance and privacy constraints.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner, Communications Platform — Avaya India',
        'Enterprise software · Pune | Jul 2015 – Mar 2018',
        [
            "Raised delivery velocity <b>30%</b> and cut requirement instability <b>25%</b> "
            "across <b>3</b> Scrum squads through Scrum discipline and OKR-to-roadmap "
            "alignment.",

            "Owned backlog and acceptance criteria for the platform APIs (Confluence).",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'QA / Release Coordinator — IDrive · Software Engineer — Tata Consultancy Services',
        'Cloud backup · IT services · Bengaluru | 2010 – 2015',
        [
            "Coordinated release trains and QA sign-off for a cloud backup product (Jira, "
            "Confluence); built distributed-systems components at TCS.",
        ]
    ):
        st.append(item)

    st.append(Spacer(1, 4))

    competences = [
        SectionHeader('Skills'),
        Spacer(1, 5),
        _skill_row(
            'Product',
            'Product strategy &amp; roadmap • Continuous discovery, JTBD / ODI • Product-led '
            'growth, pricing &amp; packaging • Prioritisation (RICE) • PRDs &amp; user stories • '
            'A/B testing • OKRs • Go-to-market',
        ),
        _skill_row(
            'AI &amp; data',
            'LLM products (OpenAI, Anthropic, Google) • RAG, agents • LLM evals &amp; '
            'guardrails • Cost per call, model routing • Build vs. buy • ML fundamentals • '
            'Data pipelines • Responsible AI (GDPR, EU AI Act)',
        ),
        _skill_row(
            'Tools',
            'Figma • Mixpanel, Amplitude • Jira, Confluence • SQL, Python • Claude Code • '
            'Cloudflare Workers, Modal • n8n, Make',
        ),
        _skill_row(
            'Leadership',
            'Cross-functional squads (eng, design, data) • Exec and customer stakeholders • '
            'Influence without authority • Change management &amp; AI adoption • Agile (Scrum, '
            'Kanban)',
        ),
        Spacer(1, 6),
    ]
    st.append(KeepTogether(competences[:3]))
    st.extend(competences[3:])

    st.append(SectionHeader('Education'))
    st.append(Spacer(1, 5))
    st.append(Paragraph('MSc International Strategic Business', S['edu_title']))
    st.append(Paragraph('Toulouse Business School, Paris | 2019–2021', S['edu_sub']))
    st.append(Paragraph('BE Information Technology (engineering degree)', S['edu_title']))
    st.append(Paragraph('CMR Institute of Technology, Bengaluru | 2006–2010', S['edu_sub']))

    st.append(SectionHeader('Languages'))
    st.append(Spacer(1, 5))
    st.append(Paragraph(
        '<b>English</b>: bilingual (C2) • <b>French</b>: bilingual (C2) • '
        '<b>Hindi / Bengali</b>: native',
        S['lang']
    ))
    st.append(Spacer(1, 6))

    st.append(SectionHeader('Open-source projects'))
    st.append(Spacer(1, 5))
    for p in [
        _link('https://github.com/dmazumdar186/anneal', '<b>Anneal</b>') +
        ': release gate that audits AI-generated code through LLM audit-fix and red-vs-blue '
        'loops.',
        _link('https://github.com/dmazumdar186/cv-optimizer-agent', '<b>CV Optimizer</b>') +
        ' (live SaaS): scores a CV against a job description and rewrites it; eval-first build.',
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
    out = args.out or (tmp / 'cv_senior_pm_debanjan_mazumdar_en.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)
    print("Generating generic Senior PM / Senior AI PM English CV")
    build_cv(out)
    print(f"Done: {out}  ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == '__main__':
    main()
