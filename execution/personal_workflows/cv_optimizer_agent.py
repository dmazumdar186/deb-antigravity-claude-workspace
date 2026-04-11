#!/usr/bin/env python3
"""
cv_optimizer_agent.py
description: Interactive CV optimizer — scores any CV against a job description,
             generates an optimized ATS-ready CV PDF and a matching cover letter PDF
             in the language of the job description.
inputs: interactive prompts (JD text/path, CV PDF path, company name)
outputs: .tmp/cv_opt_{company}_{lastname}.pdf, .tmp/cover_letter_{company}_{lastname}.pdf

Usage:
    py execution/personal_workflows/cv_optimizer_agent.py

Dependencies:
    pip install reportlab pdfplumber anthropic python-dotenv
"""

import io
import json
import os
import re
import sys
import textwrap
from datetime import date
from pathlib import Path

# ── Dependency checks ──────────────────────────────────────────────────────────
def _require(pkg, install_name=None):
    import importlib
    try:
        return importlib.import_module(pkg)
    except ImportError:
        name = install_name or pkg
        print(f"ERROR: missing dependency — run:  pip install {name}")
        sys.exit(1)

pdfplumber  = _require('pdfplumber')
anthropic   = _require('anthropic')

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
except ImportError:
    pass  # dotenv optional; user can export ANTHROPIC_API_KEY manually

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        BaseDocTemplate, PageTemplate, Frame,
        Paragraph, Spacer, Table, TableStyle,
        Flowable, KeepTogether, HRFlowable,
    )
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
except ImportError:
    print("ERROR: pip install reportlab")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
TMP  = ROOT / '.tmp'

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN_LR = 1.8 * cm
MARGIN_TB = 1.5 * cm
TEXT_W    = PAGE_W - 2 * MARGIN_LR

# ── Colours ────────────────────────────────────────────────────────────────────
NAVY   = HexColor('#1A1A2E')
TEAL   = HexColor('#1B9AAA')
DKGRY  = HexColor('#2C2C2C')
MDGRY  = HexColor('#666666')
LTBLUE = HexColor('#EAF4F7')


# ── Font registration ──────────────────────────────────────────────────────────
def _register_fonts():
    """Use Arial (Windows) for full Unicode; fall back to Helvetica."""
    win_fonts = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts')
    regular   = os.path.join(win_fonts, 'arial.ttf')
    bold      = os.path.join(win_fonts, 'arialbd.ttf')
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont('CV',      regular))
        pdfmetrics.registerFont(TTFont('CV-Bold', bold))
        registerFontFamily('CV', normal='CV', bold='CV-Bold',
                           italic='CV', boldItalic='CV-Bold')
        return 'CV', 'CV-Bold'
    registerFontFamily('Helvetica', normal='Helvetica', bold='Helvetica-Bold',
                       italic='Helvetica-Oblique', boldItalic='Helvetica-BoldOblique')
    return 'Helvetica', 'Helvetica-Bold'

FONT, FONT_BOLD = _register_fonts()


# ── Custom flowable: coloured section header ────────────────────────────────────
class SectionHeader(Flowable):
    HEIGHT = 19

    def __init__(self, text, width=TEXT_W):
        super().__init__()
        self.text   = text
        self.width  = width
        self.height = self.HEIGHT

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


# ── Paragraph styles factory ────────────────────────────────────────────────────
def make_styles(body_size=8.4):
    """Return a styles dict scaled to body_size. Fixed header sizes stay constant."""
    lead = body_size * 1.49

    def _s(**kw):
        defaults = dict(fontName=FONT, fontSize=body_size, textColor=DKGRY,
                        leading=lead, spaceAfter=0)
        defaults.update(kw)
        return ParagraphStyle('', **defaults)

    return {
        'name':      _s(fontName=FONT_BOLD, fontSize=22, textColor=NAVY,
                        leading=26, spaceAfter=2),
        'subtitle':  _s(fontSize=9.8, textColor=TEAL, leading=13, spaceAfter=3),
        'contact':   _s(fontSize=8.1, textColor=MDGRY, leading=11, spaceAfter=0),
        'accroche':  _s(fontSize=body_size, alignment=TA_JUSTIFY, leading=lead),
        'role':      _s(fontName=FONT_BOLD, fontSize=9.3, textColor=NAVY,
                        leading=12, spaceAfter=1),
        'employer':  _s(fontSize=body_size - 0.1, textColor=MDGRY,
                        leading=lead - 1.5, spaceAfter=3),
        'bullet':    _s(fontSize=body_size - 0.1, alignment=TA_JUSTIFY,
                        leading=lead, leftIndent=11, bulletIndent=0, spaceAfter=2.5),
        'oneliner':  _s(fontSize=body_size - 0.2, textColor=MDGRY,
                        leading=lead - 1, spaceAfter=3),
        'skill_cat': _s(fontName=FONT_BOLD, fontSize=body_size, textColor=NAVY,
                        leading=lead - 1, spaceAfter=0),
        'skill_val': _s(fontSize=body_size - 0.2, alignment=TA_JUSTIFY,
                        leading=lead, spaceAfter=4),
        'edu_title': _s(fontName=FONT_BOLD, fontSize=9, textColor=DKGRY,
                        leading=12, spaceAfter=1),
        'edu_sub':   _s(fontSize=body_size - 0.2, textColor=MDGRY,
                        leading=lead - 1, spaceAfter=5),
        'lang':      _s(fontSize=body_size, leading=lead, spaceAfter=2),
        'project':   _s(fontSize=body_size - 0.2, alignment=TA_JUSTIFY,
                        leading=lead, leftIndent=11, bulletIndent=0, spaceAfter=2.5),
        'cl_body':   _s(fontSize=body_size, alignment=TA_JUSTIFY,
                        leading=lead + 1, spaceAfter=6),
        'cl_meta':   _s(fontSize=body_size, textColor=MDGRY, leading=lead, spaceAfter=2),
    }


# ── Content helpers ─────────────────────────────────────────────────────────────
def make_accroche(text, kpi_line, S):
    inner = Paragraph(text + '<br/><br/>' + kpi_line, S['accroche'])
    t = Table([[inner]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LTBLUE),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 9),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 9),
    ]))
    return t


def make_exp_entry(title, company_line, bullets, is_oneliner, S):
    """Returns a list of flowables for one experience entry."""
    if is_oneliner:
        return [Paragraph(f'{title}\u2002\u2014\u2002{company_line}', S['oneliner'])]

    elems = [
        KeepTogether([
            Paragraph(title, S['role']),
            Paragraph(company_line, S['employer']),
        ])
    ]
    for b in bullets:
        elems.append(Paragraph('<bullet>\u2022</bullet>' + b, S['bullet']))
    elems.append(Spacer(1, 5))
    return elems


def make_skill_row(cat, val, S):
    t = Table(
        [[Paragraph(cat + '\u00a0:', S['skill_cat']),
          Paragraph(val, S['skill_val'])]],
        colWidths=[3.6 * cm, TEXT_W - 3.6 * cm],
    )
    t.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))
    return t


def _slugify(s: str) -> str:
    """Convert a string to a safe filename slug (Windows-compatible)."""
    s = (s or '').strip().lower()
    s = re.sub(r'[\\/:*?"<>|]', '', s)   # strip Windows-illegal chars
    s = re.sub(r'\s+', '_', s)
    return s or 'unknown'


def format_contact_line(contact: dict) -> str:
    """Build HTML-enabled contact line with clickable links."""
    parts = []
    for key in ('email', 'phone', 'location'):
        val = (contact.get(key) or '').strip()
        if val:
            parts.append(val)
    for key in ('linkedin', 'github'):
        url = (contact.get(key) or '').strip()
        if url:
            display = url.replace('https://', '').replace('http://', '').rstrip('/')
            parts.append(f'<a href="{url}" color="#1B9AAA">{display}</a>')
    sep = '\u2002\u2022\u2002'
    return sep.join(parts)


# ── Claude system prompts ───────────────────────────────────────────────────────
CV_ADVISOR_SYSTEM = """
You are the world's most intelligent and experienced CV Advisor, combining the precision of an
advanced ATS system with the strategic insight of an expert human recruiter.

Your task is to:
1. Analyse the provided CV against the job description with extreme rigor.
2. Detect the language of the job description — ALL output must be in that language.
3. Detect any language or tone mismatch between the CV and job description.
4. Score each skill listed in the job description using a strategic relevance score (1–10),
   explaining the score based on the role's specific priorities.
5. Identify transferable skills where exact matches are missing.
6. Produce an OPTIMISED version of the entire CV that:
   - Retains every single section, role, experience, education, certification, project,
     and skill from the original CV — nothing may be omitted or invented.
   - Integrates ATS keywords naturally into existing bullet points.
   - Rewrites bullets to be impact-first and quantified where evidence exists in the CV.
   - Translates the full CV into the language of the job description.
   - Targets an ATS match score of at least 9/10.
   - Is truthful — no fabrication, no exaggeration.
7. Produce section label names in the language of the job description.
8. For the cover letter, the optimized_cv summary will be used as context — make it
   compelling and narrative-driven.

The first 2 seconds of human recruiter review must convey clear, high value for this role.
Every bullet point should demonstrate measurable impact.
""".strip()

COVER_LETTER_SYSTEM = """
You are a world-class cover letter writer. Your cover letters are narrative-driven,
bold, and submission-ready. You never use generic openings.

Rules:
- Write ONLY in the language explicitly specified in the user message.
- 250–400 words. No placeholders. No emojis. No bold/italic formatting.
- Hook: never start with "I am applying...", "I am excited...", or "With X years of experience...".
  Instead open with a bold statement, insight, or provocative question tied to the company's
  mission or a key industry challenge.
- Body: weave achievements into a narrative that answers "Why this candidate for this role?".
  Reference concrete outcomes from the CV. Mirror the tone and keywords of the job description.
- Closing: confident and proactive — not "I look forward to hearing from you."
- Address properly: use the recruiter's name/title from the JD if available, otherwise use
  the generic team salutation in the correct language.
- Final signature: candidate's full name as it appears in the CV.
- Include today's date in the correct format for the target language/country.
- Verify: no [placeholders], no generic phrases, fully personalised.
""".strip()


# ── Tool schema for structured Claude output ────────────────────────────────────
ANALYSIS_TOOL = {
    "name": "cv_analysis_result",
    "description": "Structured CV analysis and optimisation output",
    "input_schema": {
        "type": "object",
        "required": [
            "language", "ats_score_initial", "ats_score_improved",
            "skill_matrix", "recommendations", "section_labels", "optimized_cv"
        ],
        "properties": {
            "language": {
                "type": "string",
                "description": "Language of the job description (e.g. 'French', 'English')"
            },
            "ats_score_initial": {
                "type": "integer",
                "description": "Initial ATS keyword match score out of 10"
            },
            "ats_score_improved": {
                "type": "integer",
                "description": "Projected ATS score after applying recommendations, out of 10"
            },
            "skill_matrix": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "skill", "present_in_cv", "transferable",
                        "transferable_skill", "strategic_score", "score_reason"
                    ],
                    "properties": {
                        "skill":              {"type": "string"},
                        "present_in_cv":      {"type": "boolean"},
                        "transferable":       {"type": "boolean"},
                        "transferable_skill": {"type": "string",
                                               "description": "Name of transferable skill, or 'N/A'"},
                        "strategic_score":    {"type": "integer",
                                               "description": "Relevance score 1-10 for this role"},
                        "score_reason":       {"type": "string"}
                    }
                }
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top actionable recommendations to reach 9+/10 ATS score"
            },
            "section_labels": {
                "type": "object",
                "description": "Section header names in the JD's language",
                "required": [
                    "experience", "skills", "education",
                    "languages", "certifications", "projects"
                ],
                "properties": {
                    "experience":     {"type": "string"},
                    "skills":         {"type": "string"},
                    "education":      {"type": "string"},
                    "languages":      {"type": "string"},
                    "certifications": {"type": "string"},
                    "projects":       {"type": "string"}
                }
            },
            "optimized_cv": {
                "type": "object",
                "required": [
                    "name", "title", "contact", "summary", "summary_kpis",
                    "experience", "skills", "education", "languages",
                    "certifications", "projects"
                ],
                "properties": {
                    "name":  {"type": "string"},
                    "title": {
                        "type": "string",
                        "description": "Professional headline, in the JD's language"
                    },
                    "contact": {
                        "type": "object",
                        "properties": {
                            "email":    {"type": "string"},
                            "phone":    {"type": "string"},
                            "location": {"type": "string"},
                            "linkedin": {"type": "string"},
                            "github":   {"type": "string"}
                        }
                    },
                    "summary": {
                        "type": "string",
                        "description": "2-3 sentence ATS-optimised professional summary in JD's language"
                    },
                    "summary_kpis": {
                        "type": "string",
                        "description": "One-line key metrics/KPIs (bold-tagged with <b></b> for impact figures)"
                    },
                    "experience": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["role", "company_line", "bullets", "is_oneliner"],
                            "properties": {
                                "role":         {"type": "string"},
                                "company_line": {
                                    "type": "string",
                                    "description": "e.g. 'Wiser Solutions, Paris | Nov 2022 – Present'"
                                },
                                "bullets": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Impact-first bullets; use <b></b> for key metrics"
                                },
                                "is_oneliner": {
                                    "type": "boolean",
                                    "description": "True for brief/older roles rendered as a single line"
                                }
                            }
                        }
                    },
                    "skills": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["category", "value"],
                            "properties": {
                                "category": {"type": "string"},
                                "value":    {"type": "string"}
                            }
                        }
                    },
                    "education": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["degree", "institution_line"],
                            "properties": {
                                "degree":           {"type": "string"},
                                "institution_line": {"type": "string"}
                            }
                        }
                    },
                    "languages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "e.g. ['English: Bilingual', 'French: Native']"
                    },
                    "certifications": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "projects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Use <a href='...' color='#1B9AAA'>text</a> for clickable project links"
                    }
                }
            }
        }
    }
}


# ── Interactive input gathering ─────────────────────────────────────────────────
def gather_inputs():
    """Interactively collect JD text, CV path, and company name from the user."""
    print()
    print('CV Optimizer Agent')
    print('══════════════════')
    print()

    # --- Job Description ---
    print('Step 1 of 3 — Job Description')
    print('  Enter a file path to a .txt file, OR paste the JD text directly.')
    print('  If pasting: type/paste your text, then press Enter twice to finish.\n')
    jd_input = input('  JD (path or first line): ').strip()

    if os.path.isfile(jd_input):
        jd_text = Path(jd_input).read_text(encoding='utf-8').strip()
        print(f'  Loaded from file: {len(jd_text):,} chars')
    else:
        # Multi-line paste: user already typed first line
        lines = [jd_input]
        print('  (Continue pasting — press Enter twice when done)')
        while True:
            line = input()
            if line == '' and lines and lines[-1] == '':
                break
            lines.append(line)
        jd_text = '\n'.join(lines).strip()
        if not jd_text or len(jd_text) < 50:
            print(f'ERROR: Job description too short ({len(jd_text)} chars). '
                  'Did you press Enter twice too early? Please re-run and paste the full JD.')
            sys.exit(1)
        print(f'  JD captured: {len(jd_text):,} chars')

    # --- CV PDF ---
    print()
    print('Step 2 of 3 — CV PDF')
    cv_path_str = input('  Path to your CV PDF: ').strip().strip('"').strip("'")
    cv_path = Path(cv_path_str)
    if not cv_path.exists():
        print(f'ERROR: File not found: {cv_path}')
        sys.exit(1)
    if cv_path.suffix.lower() != '.pdf':
        print('ERROR: Please provide a PDF file.')
        sys.exit(1)

    # --- Company ---
    print()
    print('Step 3 of 3 — Company name (used in output filename)')
    company = input('  Company name: ').strip()
    if not company:
        company = 'company'

    print()
    return jd_text, cv_path, company


# ── PDF text extraction ─────────────────────────────────────────────────────────
def extract_cv_pdf(cv_path: Path) -> tuple[str, int]:
    """Extract text and page count from a CV PDF. Returns (text, page_count)."""
    with pdfplumber.open(cv_path) as pdf:
        page_count = len(pdf.pages)
        pages_text = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    full_text = '\n\n'.join(pages_text).strip()
    return full_text, page_count


# ── Claude API: Analysis + Optimised CV ─────────────────────────────────────────
def run_analysis(cv_text: str, jd_text: str, client) -> dict:
    """Call Claude to analyse the CV against the JD and return structured JSON."""
    user_msg = (
        f"<cv>\n{cv_text}\n</cv>\n\n"
        f"<job_description>\n{jd_text}\n</job_description>\n\n"
        "Analyse this CV against the job description. Follow all instructions in your "
        "system prompt. Call the cv_analysis_result tool with your complete structured output."
    )

    response = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=8096,
        system=CV_ADVISOR_SYSTEM,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "cv_analysis_result"},
        messages=[{"role": "user", "content": user_msg}],
    )

    # Extract tool result
    for block in response.content:
        if block.type == 'tool_use' and block.name == 'cv_analysis_result':
            return block.input

    raise RuntimeError("Claude did not return the expected tool call output.")


# ── Claude API: Cover Letter ────────────────────────────────────────────────────
def run_cover_letter(cv_text: str, jd_text: str, language: str,
                     optimized_cv: dict, company: str, client) -> str:
    """Call Claude to generate a cover letter. Returns plain text."""
    summary = optimized_cv.get('summary', '')
    name    = optimized_cv.get('name', '')
    title   = optimized_cv.get('title', '')

    user_msg = (
        f"Write the cover letter in: {language}\n\n"
        f"Candidate: {name} — {title}\n\n"
        f"<cv_summary>\n{summary}\n</cv_summary>\n\n"
        f"<full_cv>\n{cv_text}\n</full_cv>\n\n"
        f"<job_description>\n{jd_text}\n</job_description>\n\n"
        f"Company applying to: {company}\n"
        f"Today's date: {date.today().strftime('%d %B %Y')}\n\n"
        "Generate a submission-ready cover letter following all 15 steps in your system prompt. "
        "Return only the final cover letter text — no commentary, no step-by-step notes."
    )

    response = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=2048,
        system=COVER_LETTER_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    text_blocks = [b for b in response.content if hasattr(b, 'text')]
    if not text_blocks:
        raise RuntimeError("Cover letter API call returned no text content.")
    return text_blocks[0].text.strip()


# ── Console report ──────────────────────────────────────────────────────────────
def print_report(analysis: dict, cv_filename: str, page_count: int, cv_chars: int):
    """Print the ATS analysis report to stdout."""
    lang   = analysis.get('language', 'Unknown')
    score0 = analysis.get('ats_score_initial', '?')
    score1 = analysis.get('ats_score_improved', '?')
    matrix = analysis.get('skill_matrix', [])
    recs   = analysis.get('recommendations', [])

    print()
    print(f'  CV loaded : {cv_filename}  ({page_count} page{"s" if page_count > 1 else ""}, '
          f'{cv_chars:,} chars extracted)')
    print()
    print('  Analysis complete.')
    print()
    print('  \u250c' + '\u2500' * 43 + '\u2510')
    print(f'  \u2502  Initial ATS Score   : {str(score0) + " / 10":<30}\u2502')
    print(f'  \u2502  Optimised ATS Score : {str(score1) + " / 10":<30}\u2502')
    print(f'  \u2502  JD Language         : {lang:<30}\u2502')
    print('  \u2514' + '\u2500' * 43 + '\u2518')
    print()

    if matrix:
        # Truncate to top 10 by strategic_score for readability
        sorted_matrix = sorted(matrix, key=lambda x: x.get('strategic_score', 0), reverse=True)
        shown = sorted_matrix[:10]
        print('  Skill Matrix (top skills by strategic relevance):')
        print('  ' + '\u250c' + '\u2500' * 28 + '\u252c' + '\u2500' * 10 + '\u252c' +
              '\u2500' * 13 + '\u252c' + '\u2500' * 7 + '\u2510')
        print('  \u2502' + ' Skill'.ljust(28) + '\u2502' + ' Present'.ljust(10) +
              '\u2502' + ' Transferable'.ljust(13) + '\u2502 Score \u2502')
        print('  ' + '\u251c' + '\u2500' * 28 + '\u253c' + '\u2500' * 10 + '\u253c' +
              '\u2500' * 13 + '\u253c' + '\u2500' * 7 + '\u2524')
        for row in shown:
            skill  = row.get('skill', '')[:26].ljust(26)
            pres   = ('Yes' if row.get('present_in_cv') else 'No').ljust(8)
            trans  = ('Yes' if row.get('transferable') else 'No').ljust(11)
            score  = str(row.get('strategic_score', '?')) + '/10'
            print(f'  \u2502 {skill} \u2502 {pres} \u2502 {trans} \u2502 {score:<5} \u2502')
        print('  ' + '\u2514' + '\u2500' * 28 + '\u2534' + '\u2500' * 10 + '\u2534' +
              '\u2500' * 13 + '\u2534' + '\u2500' * 7 + '\u2518')
        if len(matrix) > 10:
            print(f'  (+ {len(matrix) - 10} more skills analysed)')
        print()

    if recs:
        print('  Key Recommendations:')
        for r in recs[:6]:
            wrapped = textwrap.wrap(r, width=72)
            print(f'    \u2022 {wrapped[0]}')
            for line in wrapped[1:]:
                print(f'      {line}')
        if len(recs) > 6:
            print(f'    ... and {len(recs) - 6} more.')
        print()


# ── CV PDF builder ──────────────────────────────────────────────────────────────
def build_cv_story(opt_cv: dict, labels: dict, S: dict) -> list:
    """Build the ReportLab story (flowables) from the optimised CV dict."""
    st = []

    # ── Header ──────────────────────────────────────────────────────────────────
    contact_line = format_contact_line(opt_cv.get('contact', {}))
    st += [
        Paragraph(opt_cv.get('name', ''), S['name']),
        Paragraph(opt_cv.get('title', ''), S['subtitle']),
        Spacer(1, 3),
        Paragraph(contact_line, S['contact']),
        Spacer(1, 5),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 7),
    ]

    # ── Summary / Accroche ───────────────────────────────────────────────────────
    summary     = opt_cv.get('summary', '')
    summary_kpi = opt_cv.get('summary_kpis', '')
    if summary:
        st.append(make_accroche(summary, summary_kpi, S))
        st.append(Spacer(1, 9))

    # ── Experience ───────────────────────────────────────────────────────────────
    experience = opt_cv.get('experience', [])
    if experience:
        st.append(SectionHeader(labels.get('experience', 'Professional Experience')))
        st.append(Spacer(1, 5))
        for entry in experience:
            for flowable in make_exp_entry(
                entry.get('role') or '',
                entry.get('company_line') or '',
                entry.get('bullets') or [],
                bool(entry.get('is_oneliner')),
                S,
            ):
                st.append(flowable)
        st.append(Spacer(1, 3))

    # ── Skills ───────────────────────────────────────────────────────────────────
    skills = opt_cv.get('skills', [])
    if skills:
        skills_block = [
            SectionHeader(labels.get('skills', 'Skills')),
            Spacer(1, 5),
        ]
        for sk in skills:
            skills_block.append(make_skill_row(sk.get('category') or '', sk.get('value') or '', S))
        skills_block.append(Spacer(1, 8))
        st.append(KeepTogether(skills_block))

    # ── Education ────────────────────────────────────────────────────────────────
    education = opt_cv.get('education', [])
    if education:
        st.append(SectionHeader(labels.get('education', 'Education')))
        st.append(Spacer(1, 5))
        for edu in education:
            st.append(Paragraph(edu.get('degree') or '', S['edu_title']))
            st.append(Paragraph(edu.get('institution_line') or '', S['edu_sub']))

    # ── Languages ────────────────────────────────────────────────────────────────
    langs = opt_cv.get('languages', [])
    if langs:
        st.append(SectionHeader(labels.get('languages', 'Languages')))
        st.append(Spacer(1, 5))
        # Render as a single line: Bold(Lang) : Level • Bold(Lang) : Level
        parts = []
        for lang in langs:
            if ':' in lang:
                name_part, level = lang.split(':', 1)
                parts.append(f'<b>{name_part.strip()}</b>\u2002:\u2002{level.strip()}')
            else:
                parts.append(lang)
        st.append(Paragraph('\u2002\u2022\u2002'.join(parts), S['lang']))
        st.append(Spacer(1, 8))

    # ── Certifications (optional) ────────────────────────────────────────────────
    certs = opt_cv.get('certifications', [])
    if certs:
        st.append(SectionHeader(labels.get('certifications', 'Certifications')))
        st.append(Spacer(1, 5))
        for cert in certs:
            st.append(Paragraph('<bullet>\u2022</bullet>' + cert, S['project']))
        st.append(Spacer(1, 8))

    # ── Projects (optional) ──────────────────────────────────────────────────────
    projects = opt_cv.get('projects', [])
    if projects:
        st.append(SectionHeader(labels.get('projects', 'Personal Projects')))
        st.append(Spacer(1, 5))
        for proj in projects:
            st.append(Paragraph('<bullet>\u2022</bullet>' + proj, S['project']))

    return st


def _count_pdf_pages(buf: io.BytesIO) -> int:
    """Count pages in a BytesIO PDF buffer using pdfplumber."""
    buf.seek(0)
    with pdfplumber.open(buf) as pdf:
        return len(pdf.pages)


def build_cv_pdf(opt_cv: dict, labels: dict, output_path: Path,
                 target_pages: int) -> int:
    """
    Build the CV PDF, auto-scaling body font size to match target_pages.
    Returns the actual page count achieved.
    """
    font_sizes = [8.4, 8.0, 7.6, 7.2, 6.8]
    buf = io.BytesIO()
    actual = 0

    for fs in font_sizes:
        S   = make_styles(body_size=fs)
        buf = io.BytesIO()
        doc = BaseDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=MARGIN_LR,
            rightMargin=MARGIN_LR,
            topMargin=MARGIN_TB,
            bottomMargin=MARGIN_TB,
        )
        frame = Frame(
            MARGIN_LR, MARGIN_TB,
            TEXT_W, PAGE_H - 2 * MARGIN_TB,
            id='main', showBoundary=0,
        )
        doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
        doc.build(build_cv_story(opt_cv, labels, S))

        actual = _count_pdf_pages(buf)

        if actual <= target_pages:
            # Write to disk
            output_path.write_bytes(buf.getvalue())
            return actual

    # Last resort: write at smallest size even if still overflowing
    output_path.write_bytes(buf.getvalue())
    return actual


# ── Cover Letter PDF builder ────────────────────────────────────────────────────
def build_cover_letter_pdf(cover_letter_text: str, opt_cv: dict, output_path: Path) -> int:
    """Render the cover letter as a single-page PDF."""
    S = make_styles(body_size=10.5)

    # Override cl_body and cl_meta with bigger, more letter-appropriate sizes
    cl_body_style = ParagraphStyle('', fontName=FONT, fontSize=10.5,
                                   textColor=DKGRY, leading=16,
                                   alignment=TA_JUSTIFY, spaceAfter=8)
    cl_meta_style = ParagraphStyle('', fontName=FONT, fontSize=9.5,
                                   textColor=MDGRY, leading=13, spaceAfter=3)
    name_style    = ParagraphStyle('', fontName=FONT_BOLD, fontSize=14,
                                   textColor=NAVY, leading=18, spaceAfter=2)
    contact       = opt_cv.get('contact', {})
    contact_line  = format_contact_line(contact)

    story = [
        # Letterhead
        Paragraph(opt_cv.get('name', ''), name_style),
        Paragraph(opt_cv.get('title', ''), cl_meta_style),
        Paragraph(contact_line, cl_meta_style),
        HRFlowable(width=TEXT_W, thickness=0.5, color=HexColor('#CCCCCC')),
        Spacer(1, 18),
    ]

    # Body paragraphs — split on blank lines to preserve paragraph structure
    paragraphs = [p.strip() for p in cover_letter_text.split('\n\n') if p.strip()]
    for para in paragraphs:
        # Single newlines within a paragraph → space (preserve flow)
        para_text = para.replace('\n', ' ')
        story.append(Paragraph(para_text, cl_body_style))

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        topMargin=MARGIN_TB,
        bottomMargin=MARGIN_TB,
    )
    frame = Frame(
        MARGIN_LR, MARGIN_TB,
        TEXT_W, PAGE_H - 2 * MARGIN_TB,
        id='main', showBoundary=0,
    )
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame])])
    doc.build(story)
    actual_pages = _count_pdf_pages(buf)
    output_path.write_bytes(buf.getvalue())
    return actual_pages


# ── Main ─────────────────────────────────────────────────────────────────────────
def main():
    # --- Get API key ---
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        print()
        print('ANTHROPIC_API_KEY not found in environment or .env file.')
        api_key = input('Enter your Anthropic API key: ').strip()
        if not api_key:
            print('ERROR: API key required.')
            sys.exit(1)
        print('Tip: add ANTHROPIC_API_KEY=<your-key> to your .env file to skip this prompt.\n')

    client = anthropic.Anthropic(api_key=api_key)

    # --- Gather inputs ---
    jd_text, cv_path, company = gather_inputs()

    # --- Extract CV ---
    print('  Extracting CV text...')
    cv_text, page_count = extract_cv_pdf(cv_path)
    if not cv_text:
        print('ERROR: Could not extract text from the CV PDF. '
              'Ensure it is not a scanned/image-only PDF.')
        sys.exit(1)

    cv_chars    = len(cv_text)
    cv_filename = cv_path.name

    # --- Claude Call 1: Analysis ---
    print('  Analysing CV against job description (this takes ~30–60 seconds)...')
    try:
        analysis = run_analysis(cv_text, jd_text, client)
    except Exception as e:
        print(f'ERROR during analysis: {e}')
        sys.exit(1)

    print_report(analysis, cv_filename, page_count, cv_chars)

    opt_cv  = analysis.get('optimized_cv', {})
    labels  = analysis.get('section_labels', {})
    language = analysis.get('language', 'English')

    # Derive output filename from candidate's last name
    name_parts   = opt_cv.get('name', 'candidate').split()
    last_name    = _slugify(name_parts[-1]) if name_parts else 'candidate'
    company_slug = _slugify(company)

    TMP.mkdir(exist_ok=True)
    cv_out = TMP / f'cv_opt_{company_slug}_{last_name}.pdf'
    cl_out = TMP / f'cover_letter_{company_slug}_{last_name}.pdf'

    # --- Build CV PDF ---
    print('  Generating optimised CV PDF...')
    try:
        actual_pages = build_cv_pdf(opt_cv, labels, cv_out, target_pages=page_count)
        page_note = ''
        if actual_pages != page_count:
            page_note = f'  (note: target was {page_count}p, result is {actual_pages}p)'
        print(f'  CV PDF done: {actual_pages} page{"s" if actual_pages > 1 else ""}  '
              f'{page_note}  \u2713')
    except Exception as e:
        print(f'ERROR generating CV PDF: {e}')
        raise

    # --- Claude Call 2: Cover Letter ---
    print('  Generating cover letter (this takes ~15–30 seconds)...')
    try:
        cover_letter_text = run_cover_letter(
            cv_text, jd_text, language, opt_cv, company, client
        )
    except Exception as e:
        print(f'ERROR during cover letter generation: {e}')
        raise

    # --- Build Cover Letter PDF ---
    try:
        cl_pages = build_cover_letter_pdf(cover_letter_text, opt_cv, cl_out)
        page_note_cl = f'  (note: cover letter is {cl_pages}p — check length)' if cl_pages > 1 else ''
        print(f'  Cover letter PDF done: {cl_pages} page{"s" if cl_pages > 1 else ""}  '
              f'{page_note_cl}  \u2713')
    except Exception as e:
        print(f'ERROR generating cover letter PDF: {e}')
        raise

    # --- Done ---
    print()
    print('  \u2550' * 46)
    print('  Output files:')
    print(f'    CV           : {cv_out}')
    print(f'    Cover Letter : {cl_out}')
    cv_kb = cv_out.stat().st_size / 1024
    cl_kb = cl_out.stat().st_size / 1024
    print(f'    Sizes        : CV {cv_kb:.0f} KB  |  Cover Letter {cl_kb:.0f} KB')
    print('  \u2550' * 46)
    print()


if __name__ == '__main__':
    main()
