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
            'Senior Product Manager — AI &amp; Data Products | B2B SaaS | PM since 2021, PO 2015–19',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • +33 7 55 80 76 58 • Paris, France'
            ' • ' + _link('https://linkedin.com/in/dmazumdar/', 'linkedin.com/in/dmazumdar')
            + ' • ' + _link('https://github.com/dmazumdar186', 'github.com/dmazumdar186'),
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 6),
    ]

    st.append(_accroche(
        "Senior Product Manager on AI and data products. Continuous discovery and customer "
        "interviews first, then a roadmap with outcomes attached and a launch that gets "
        "measured. PM since 2021, on GenAI at Wiser Solutions since 2022; before that four "
        "years as a Product Owner and five as a software engineer. Prototypes with Claude Code "
        "before writing the spec; works through trade-offs with engineers and roadmap with "
        "the CPO.",
        "Paris-based, bilingual English and French, remote-friendly.",
    ))
    st.append(Spacer(1, 8))

    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, AI &amp; Data Intelligence — Wiser Solutions',
        'B2B SaaS · Retail &amp; Digital-Commerce Intelligence · Paris | Nov 2022 – Present',
        [
            "Own the AI product area end to end: a RAG assistant on OpenAI and Anthropic APIs, "
            "recommendations and smart alerting on a platform used by retail and brand "
            "customers. Problem framing and JTBD interviews with customers, roadmap with the "
            "CPO, PRDs and Figma flows, pricing and packaging of the AI tier, product-led "
            "launch, adoption tracked in Mixpanel. Feature adoption up <b>45%</b> after the "
            "assistant's second release; p95 latency down <b>55%</b>.",

            "Ran the company-wide GenAI rollout with a <b>$150K</b> budget: build-vs-buy "
            "across OpenAI, Anthropic and Google, go/no-go reviews with the CPO and "
            "business-unit heads, onboarding of each unit. Adoption up <b>40%</b> across BUs, "
            "CSAT up <b>20%</b>.",

            "Coordinate <b>5</b> squads (engineering, design, data) across Paris, the US and "
            "India on one prioritised roadmap, with no reporting line into any of them.",

            "A/B tests and feature flags, usage and funnel analytics (Mixpanel, Amplitude), LLM "
            "evaluation sets and guardrails, GDPR by design.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Founder &amp; AI Product Consultant — ' + _link('https://prodcraft.fyi', 'ProdCraft'),
        'Independent AI product studio, Paris (alongside Wiser) | Jan 2026 – Present',
        [
            "Side practice, evenings and weekends: <b>12</b> small AI products for clients, "
            "including an agentic outbound pipeline on Cloudflare Workers that replaced about "
            "<b>$200K/yr</b> of manual work, and a Stripe Connect marketplace.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Data &amp; Recommendation Products — InfoTnT',
        'B2B SaaS · Paris | Jun 2021 – Nov 2022',
        [
            "Introduced continuous discovery (customer interviews, JTBD / Outcome-Driven "
            "Innovation, Mixpanel usage analytics), product-led growth and pricing work, and "
            "a prioritised roadmap to a team that had none of it. Shorter iteration cycles and "
            "a <b>25%</b> higher product-market-fit survey score.",
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
        'Senior Product Owner — Avaya (2015–18) · Evolent (2018–19) · Pitney Bowes (2019)',
        'Enterprise communications · Healthcare SaaS (regulated) · Logistics SaaS · Pune | '
        '2015 – 2019',
        [
            "Four years as Product Owner on platform and data products, up to <b>3</b> Scrum "
            "squads at a time: backlog, sprint goals, SLA/SLO framework, RAID risk reviews, "
            "OKR-to-roadmap alignment in Jira and Confluence. At Avaya, delivery velocity rose "
            "<b>30%</b>; at Evolent, first use of JTBD / Outcome-Driven Innovation, under "
            "healthcare compliance and privacy rules.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2010 – 2015:</b> Software Engineer, Tata Consultancy Services, then QA / Release '
        'Coordinator, IDrive. Distributed systems and release management.',
        S['oneliner']
    ))
    st.append(Spacer(1, 7))

    competences = [
        SectionHeader('Skills'),
        Spacer(1, 5),
        _skill_row(
            'Product',
            'Continuous discovery and user research, JTBD / Outcome-Driven Innovation • OKRs and outcome metrics • '
            'Strategy &amp; roadmap • Product-led growth, pricing and packaging • Prioritisation '
            'and trade-offs • PRDs • A/B tests • Analytics (SQL, Mixpanel, Amplitude) • '
            'Go-to-market',
        ),
        _skill_row(
            'AI &amp; data',
            'LLM products (OpenAI, Anthropic, Google) • RAG and agents • Build vs. buy • ML '
            'fundamentals • Data pipelines • Responsible AI (GDPR, EU AI Act)',
        ),
        _skill_row(
            'Technical',
            'Python, SQL • APIs and platform products • Figma • Jira, Confluence • Cloudflare '
            'Workers • CI/CD • Prototyping with Claude Code',
        ),
        _skill_row(
            'Ways of working',
            'Engineering and design partnership • Exec and customer stakeholders • Influence '
            'without authority • Change management • Agile (Scrum, Kanban)',
        ),
        Spacer(1, 7),
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
    st.append(Spacer(1, 7))

    st.append(Paragraph(
        'Open source: ' + _link('https://github.com/dmazumdar186/anneal', 'Anneal') +
        ', a release gate that audits AI-generated code (' +
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
    out = args.out or (tmp / 'cv_senior_pm_debanjan_mazumdar_en.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)
    print("Generating generic Senior PM / Senior AI PM English CV")
    build_cv(out)
    print(f"Done: {out}  ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == '__main__':
    main()
