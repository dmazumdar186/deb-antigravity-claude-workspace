#!/usr/bin/env python3
"""
cv_builder_ai_pm_en.py
description: Generate the ATS-optimized, English-language, AI PM GENERIC variant of the
    Senior-Product-Manager PDF CV for Debanjan Mazumdar — AI-first framing for Senior AI PM /
    agentic-automation roles. 60/40 product-vs-build balance. Same teal reportlab template as
    cv_builder_pm_en.py (imports shared primitives from cv_builder_core.py); only build_story()
    content and the header/subtitle differ.
inputs: --out (path; default .tmp/cv_ai_pm_debanjan_mazumdar_en.pdf)
outputs: the PDF at --out (exactly 2 pages)

Numbers reconciled to personal_brand/metrics_canonical.md (Wiser = +45%/-55%; outbound =
$1M+/~$200K/yr; marketplace = $85K/3mo; 12+ AI products shipped; <30-day median; 15 years).

Font note: this container has no Windows Arial, so cv_builder_core._register_fonts() falls back
to base-14 Helvetica, whose bulletFontName default and un-embedded glyph table mangle '*' bullets
and '-' minus signs on text extraction. This script stages DejaVu Sans under the arial.ttf /
arialbd.ttf names core's own font lookup expects (via a local WINDIR override) so core registers
real embedded TrueType glyphs under its usual 'CV' / 'CV-Bold' names, then also points each
bullet-style's bulletFontName at that same face — cv_builder_core.py itself is not modified.

Usage:
    python3 execution/personal_workflows/cv_builder_ai_pm_en.py --out ".tmp/cv_ai_pm_en.pdf"

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

# ── Colours (same palette as cv_builder_pm_en.py) ───────────────────────────────
NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')


# ── Fonts ──────────────────────────────────────────────────────────────────────
def _register_ai_pm_fonts():
    """Register (FONT, FONT_BOLD) via cv_builder_core._register_fonts(), staging a DejaVu
    Sans fallback under the arial.ttf / arialbd.ttf names when the real Windows fonts aren't
    present (any non-Windows box). This makes core embed real TrueType glyphs — fixing bullet
    (cid:127) mangling and dropped minus signs on pdfplumber extraction — without editing core.
    """
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    have_real_arial = (
        os.path.exists(os.path.join(win_fonts, 'arial.ttf'))
        and os.path.exists(os.path.join(win_fonts, 'arialbd.ttf'))
    )
    if not have_real_arial:
        dejavu_reg = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        dejavu_bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if os.path.exists(dejavu_reg) and os.path.exists(dejavu_bold):
            stage = Path(tempfile.gettempdir()) / 'cv_ai_pm_fake_winfonts' / 'Fonts'
            stage.mkdir(parents=True, exist_ok=True)
            for src, name in ((dejavu_reg, 'arial.ttf'), (dejavu_bold, 'arialbd.ttf')):
                dst = stage / name
                if not dst.exists():
                    shutil.copy(src, dst)
            os.environ['WINDIR'] = str(stage.parent)
    return _register_fonts()


FONT, FONT_BOLD = _register_ai_pm_fonts()


# ── Section header (same teal-accent style as pm_en) ────────────────────────────
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
    'name':      _s(fontName=FONT_BOLD, fontSize=21, textColor=NAVY, leading=25, spaceAfter=2),
    'subtitle':  _s(fontSize=9.2, textColor=TEAL, leading=12.5, spaceAfter=3),
    'contact':   _s(fontSize=7.9, textColor=MDGRY, leading=11, spaceAfter=0),
    'accroche':  _s(fontSize=8.3, alignment=TA_JUSTIFY, leading=12.5),
    'role':      _s(fontName=FONT_BOLD, fontSize=9.1, textColor=NAVY, leading=11.8, spaceAfter=1),
    'employer':  _s(fontSize=8.1, textColor=MDGRY, leading=10.8, spaceAfter=3),
    'bullet':    _s(fontSize=8.1, alignment=TA_JUSTIFY, leading=12,
                    leftIndent=11, bulletIndent=0, spaceAfter=2.2, bulletFontName=FONT),
    'oneliner':  _s(fontSize=8.0, textColor=MDGRY, leading=10.8, spaceAfter=3),
    'skill_cat': _s(fontName=FONT_BOLD, fontSize=8.2, textColor=NAVY, leading=10.8, spaceAfter=0),
    'skill_val': _s(fontSize=8.0, alignment=TA_JUSTIFY, leading=11.6, spaceAfter=4),
    'edu_title': _s(fontName=FONT_BOLD, fontSize=8.8, textColor=DKGRY, leading=11.8, spaceAfter=1),
    'edu_sub':   _s(fontSize=8.0, textColor=MDGRY, leading=10.8, spaceAfter=5),
    'lang':      _s(fontSize=8.3, leading=11.6, spaceAfter=2),
    'project':   _s(fontSize=8.0, alignment=TA_JUSTIFY, leading=11.6,
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
                     text_w=TEXT_W, cat_col_w=3.3, separator=' :')


# ── CV story ────────────────────────────────────────────────────────────────────
def build_story():
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    st += [
        Paragraph('Debanjan Mazumdar', S['name']),
        Paragraph(
            'Senior Product Manager — AI &amp; Agentic Automation | LLM · RAG · AI Agents | '
            '15 years B2B SaaS',
            S['subtitle']
        ),
        Spacer(1, 3),
        Paragraph(
            'debanjan186@gmail.com • +33 7 55 80 76 58 • Paris, France'
            ' • '
            '<a href="https://linkedin.com/in/dmazumdar/" color="#1B9AAA">linkedin.com/in/dmazumdar</a>'
            ' • '
            '<a href="https://github.com/dmazumdar186" color="#1B9AAA">github.com/dmazumdar186</a>'
            ' • '
            '<a href="https://prodcraft.fyi" color="#1B9AAA">prodcraft.fyi</a>',
            S['contact']
        ),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 6),
    ]

    # ── Accroche / Summary ──────────────────────────────────────────────────────
    st.append(_accroche(
        "Senior Product Manager with <b>15 years</b> in B2B SaaS, specialized in <b>AI, GenAI "
        "and agentic automation</b> products. I run product discovery with business teams, "
        "defend prioritization at <b>VP/C-level</b>, and stay hands-on — <b>LLM, RAG, agent "
        "orchestration</b>, low-code and Python — when building is the fastest path to impact. "
        "<b>12+ AI products shipped</b> at a <b>&lt;30-day median</b>.",
        "<b>Impact:</b> <b>+45%</b> adoption • <b>−55%</b> p95 latency • <b>~$200K/yr</b> costs "
        "automated • <b>$1M+</b> qualified pipeline",
    ))
    st.append(Spacer(1, 8))

    # ── Professional Experience ─────────────────────────────────────────────────
    st.append(SectionHeader('Professional Experience'))
    st.append(Spacer(1, 5))

    for item in _exp_entry(
        'Senior Product Manager, AI &amp; Data Intelligence — Wiser Solutions',
        'B2B SaaS · Retail &amp; Digital-Commerce Intelligence · Paris | Nov 2022 – Present',
        [
            "Own the <b>AI/GenAI product line</b> end-to-end (RAG assistant on OpenAI/Anthropic "
            "APIs, recommendations, smart alerting): discovery → PRDs → <b>LLM evaluation "
            "gates</b> (golden test set, LLM-as-judge) → rollout — <b>+45% feature adoption, "
            "−55% p95 latency</b>.",

            "Led the <b>global GenAI rollout</b>: roadmap, OKRs, <b>$150K budget</b>, go/no-go "
            "reviews with the <b>CPO</b> and BU leads — <b>+40% BU adoption, +20% CSAT</b>.",

            "Aligned <b>5 cross-functional squads</b> (Paris, US, India) on one prioritized "
            "roadmap — through influence, without formal authority.",

            "Ran <b>A/B tests, feature flags and drift monitoring</b> with <b>GDPR / "
            "privacy-by-design</b> guardrails — <b>−25% in-sprint ambiguity, +25–30% delivery "
            "precision</b>.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Founder &amp; AI Product Consultant — '
        '<a href="https://prodcraft.fyi" color="#1B9AAA">ProdCraft</a> (AI Product Studio)',
        'Paris (independent, alongside Wiser) | Jan 2026 – Present',
        [
            "Shipped an <b>autonomous outbound engine</b> (agentic pipeline: <b>Claude-based "
            "reply classification</b>, Cloudflare Workers orchestration, 32 inboxes, 3-hour "
            "hot-lead SLA) — <b>$1M+ qualified pipeline</b>, <b>~$200K/yr SDR cost "
            "replaced</b>.",

            "Co-launched a <b>Stripe Connect marketplace</b> (React + Node + Postgres) — "
            "<b>$85K processed in the first 3 months</b>.",

            "<b>12+ AI products shipped</b> at a <b>&lt;30-day median</b> — multilingual "
            "CV-optimizer SaaS, GenAI coaching app, code-audit CLI — owning discovery, PRDs "
            "and release gates.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Product Manager, Data &amp; Recommendation Products — InfoTnT',
        'B2B SaaS · Paris | Jun 2021 – Nov 2022',
        [
            "Structured product discovery (interviews, <b>JTBD</b>, usage analytics) → "
            "prioritized roadmap and backlog — <b>−35% iteration cycles, +25% product-market "
            "fit</b>.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2019 – 2021:</b> MSc International Strategic Business — Toulouse Business School, '
        'Paris (full-time).',
        S['oneliner']
    ))
    st.append(Spacer(1, 4))

    for item in _exp_entry(
        'Senior Data Product Owner — Pitney Bowes',
        'Shipping &amp; Logistics SaaS · Pune | Apr 2019 – Sep 2019',
        [
            "<b>−20% time-to-market</b> via dependency mapping, Scrum cadence and RAID reviews.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Data Product Owner — Evolent International',
        'Healthcare SaaS · Pune | Jun 2018 – Feb 2019',
        [
            "<b>+30% platform scalability</b> via SLA/SLO frameworks and QA governance.",
        ]
    ):
        st.append(item)

    for item in _exp_entry(
        'Senior Product Owner, Communications Platform — Avaya India',
        'Enterprise software · Pune | Jul 2015 – Mar 2018',
        [
            "<b>+30% delivery velocity, −25% requirement instability</b> across <b>3 squads</b> "
            "via Scrum discipline and OKR–roadmap alignment.",
        ]
    ):
        st.append(item)

    st.append(Paragraph(
        '<b>2010 – 2015:</b> Software Engineer (Tata Consultancy Services) → QA / Release '
        'Coordinator (IDrive) — <i>foundations in distributed systems and release management</i>',
        S['oneliner']
    ))
    st.append(Spacer(1, 7))

    # ── Skills ──────────────────────────────────────────────────────────────────
    competences = [
        SectionHeader('Skills'),
        Spacer(1, 5),
        _skill_row(
            'AI &amp; Agentic',
            'LLM (OpenAI, Anthropic, Google) • RAG • AI agents &amp; orchestration • Prompt '
            'engineering • LLM evals &amp; guardrails • MCP • LLM cost governance',
        ),
        _skill_row(
            'Automation &amp; Build',
            'n8n • Make • Python • SQL • Cloudflare Workers • Modal • API integrations • CI/CD '
            '• Claude Code (agentic development)',
        ),
        _skill_row(
            'Product Management',
            'Product discovery (user research, interviews, JTBD) • Product strategy • Roadmap '
            '&amp; OKR • PRD &amp; user stories • Backlog prioritization • A/B testing &amp; '
            'experimentation • Analytics (Mixpanel, Amplitude) • Customer experience (UX) • '
            'Go-to-market • Agile (Scrum, Kanban) • Product lifecycle',
        ),
        _skill_row(
            'Leadership',
            'VP/C-level stakeholder management • Cross-functional collaboration • Change '
            'management &amp; AI adoption • Data-driven decision making • Delivering through '
            'ambiguity',
        ),
        _skill_row(
            'Governance',
            'GDPR / Privacy-by-design • EU AI Act • Responsible AI • Audit trails',
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
        '<b>English</b>: Bilingual (C2) • <b>French</b>: Bilingual (C2) • '
        '<b>Hindi / Bengali</b>: Native',
        S['lang']
    ))
    st.append(Spacer(1, 7))

    # ── Selected Projects ───────────────────────────────────────────────────────
    st.append(SectionHeader('Selected Projects'))
    st.append(Spacer(1, 5))
    for p in [
        '<a href="https://cv-optimizer.pages.dev" color="#1B9AAA"><b>CV Optimizer</b></a> '
        '(live SaaS — cv-optimizer.pages.dev): multilingual ATS scoring + CV rewrite; '
        'eval-first build.',

        '<b>AgentUp</b> (live): GenAI roleplay-coaching app — streaming LLM with provider '
        'fallback, client-side PII redaction.',

        '<b>Job Search Engine</b>: multi-source job aggregation + LLM ranking (France Travail '
        'API, Gmail ingestion) — $0 infra.',
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
    out = args.out or (tmp / 'cv_ai_pm_debanjan_mazumdar_en.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)

    print("Generating AI PM GENERIC English CV")
    build_cv(out)
    size_kb = out.stat().st_size / 1024
    print(f"Done: {out}  ({size_kb:.0f} KB)")
    print("Verify it is exactly 2 pages.")


if __name__ == '__main__':
    main()
