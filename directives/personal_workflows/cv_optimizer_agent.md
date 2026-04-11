# CV Optimizer Agent

## Goal

Given any person's CV (as a PDF) and a job description, this agent:
1. Analyses the CV against the JD using the world's most critical ATS + human recruiter lens
2. Produces an ATS compatibility score (initial and projected after optimisation)
3. Shows a skill matrix and top recommendations to reach 9+/10
4. Generates an optimised CV PDF in the **language of the job description** (same page count as original)
5. Generates a matching cover letter PDF in the **language of the job description**

Both documents use the same design language (Navy/Teal, Arial/Helvetica, A4).

---

## Script

```
execution/personal_workflows/cv_optimizer_agent.py
```

## Usage

```bash
py execution/personal_workflows/cv_optimizer_agent.py
```

The script is fully interactive. It prompts for:
1. **Job description** — paste inline or provide a `.txt` file path
2. **CV PDF path** — any candidate's PDF CV
3. **Company name** — used in output filenames

---

## Inputs

| Input | Format | Notes |
|-------|--------|-------|
| Job description | Inline paste or `.txt` file path | Multi-line paste ends with double Enter |
| CV | PDF file (text-selectable) | Scanned/image PDFs are not supported |
| Company name | Free text | Slugified for filenames |

---

## Outputs

| File | Description |
|------|-------------|
| `.tmp/cv_opt_{company}_{lastname}.pdf` | Optimised ATS-ready CV, same page count as original |
| `.tmp/cover_letter_{company}_{lastname}.pdf` | Narrative cover letter, single page |

Both files are in the language of the job description.

---

## Dependencies

```bash
pip install reportlab pdfplumber anthropic python-dotenv
```

**API key:** Add `ANTHROPIC_API_KEY=<your-key>` to `.env`. If missing, the script will prompt at runtime.

---

## ATS Scoring Logic

The agent uses Claude (`claude-opus-4-6`) with a tool-use call to produce structured output:

- **Initial score:** How well the raw CV matches the JD's explicit keywords
- **Improved score:** Projected score after applying truthful, tactful recommendations
- **Skill matrix:** Each JD skill is scored for strategic relevance (1–10) and checked for presence or transferable equivalent in the CV
- **Target:** Always aims for ≥9/10 ATS score

---

## CV Generation Rules

- **Never omit content** — every role, education, certification, project, and skill from the original CV is retained
- **No fabrication** — all optimisations are truthful rewrites of existing experience
- **Language match** — full CV is in the JD's language (translated if needed)
- **Page count match** — if original was 2 pages, output is 2 pages (auto-scales font 8.4→8.0→7.6→7.2→6.8pt until it fits)
- **ATS-readable** — selectable text, no tables that break keyword extraction

---

## Cover Letter Rules

Based on a 15-step generation process:
- **Hook:** Never generic. Opens with a bold statement, question, or insight tied to company mission
- **Body:** Narrative-driven, weaves achievements into a story that answers "Why this candidate?"
- **Closing:** Confident and proactive — not "I look forward to hearing from you"
- **Length:** 250–400 words
- **No placeholders** — fully personalised, submission-ready

---

## Edge Cases

| Scenario | Behaviour |
|----------|-----------|
| Image-only/scanned PDF | Script exits with clear error message |
| CV > 2 pages | Font size reduced until content fits; warns if minimum size still overflows |
| JD in French, CV in English | Claude translates the full CV to French automatically |
| Missing Anthropic API key | Script prompts for key at runtime with a tip to add it to `.env` |
| No LinkedIn/GitHub in CV | Contact line omits those fields gracefully |

---

## Self-Annealing Notes

- If Claude returns malformed JSON / skips the tool call → check `ANALYSIS_TOOL` schema in script
- If ReportLab overflows pages at smallest font → increase `MARGIN_TB` or reduce section spacers
- If pdfplumber extracts garbled text → the source PDF may use embedded fonts without proper encoding; advise user to export from Word/Docs to PDF
