# CV Builder

## Goal
Generate a tailored, ATS-optimised, submission-ready PDF CV in French (or target language)
for a specific job role. Output is a PDF ready to send — no manual editing required.

## Inputs
- `--company`: Company name (used in filename, e.g. `sahar`)
- `--role`: Target role (used in console output only)

## Tools/Scripts
`execution/personal_workflows/cv_builder.py`

## Output
`.tmp/cv_{company}_debanjan_mazumdar.pdf`

## Steps

1. **Check the JD** — identify target language, key technical keywords, role title
2. **Update the CV content** in `cv_builder.py` `build_story()` function if needed for a new role
3. **Run the script:**
   ```
   py execution/personal_workflows/cv_builder.py --company <name> --role "<role>"
   ```
4. **Verify:** PDF opens, is exactly 2 pages, text is selectable (ATS-readable)
5. **Submit** `.tmp/cv_{company}_debanjan_mazumdar.pdf` directly

## Customising for a New Role

To tailor the CV for a different company/role:
1. Open `cv_builder.py` and find the `build_story()` function
2. Update the `accroche()` call — adjust the summary paragraph and KPI line
3. Update `exp_entry()` bullet text for Wiser Solutions to match JD keywords
4. Update `skill_row()` values to lead with the most relevant skills first
5. The header subtitle can be changed to match the exact role title
6. Re-run the script

## CV Design Spec

| Element | Value |
|---|---|
| Language | French (to match JD language) |
| Pages | Exactly 2 |
| Font | Arial (Windows) or Helvetica fallback |
| Accent colour | Teal `#1B9AAA` |
| Primary colour | Navy `#1A1A2E` |
| Margins | 1.8cm left/right, 1.5cm top/bottom |
| ATS target | ≥95% keyword match vs JD |

## Edge Cases

- **Font missing**: Script auto-falls back from Arial to Helvetica — Unicode characters still render
- **Content overflow to 3 pages**: Reduce `spaceAfter` values in `S` dict or shorten bullet text
- **Content too short (< 2 pages)**: Increase `Spacer(1, N)` values between sections
- **Special characters not rendering**: Ensure the `CV` TTFont registered successfully (check console)

## Dependencies
```
pip install reportlab
```

## Exit Criteria

A CV build is considered successful when ALL of the following are true:

1. **PDF generated** — the output file `.tmp/cv_{company}_debanjan_mazumdar.pdf` exists and has a file size > 30 KB (a blank/empty PDF is typically < 5 KB).
2. **Exactly 2 pages** — `py tests/cv_ats_check.py` (or `pdfplumber` page count) reports exactly 2 pages; any overflow to 3 pages requires reducing `spaceAfter` or shortening bullet text.
3. **Font registration succeeded** — console output does NOT contain `"Arial not found"` or `"Falling back to Helvetica"` on a Windows machine with standard fonts installed; TTFont `CV` / `CV-Bold` registered successfully.
4. **All sections present** — the PDF contains all required sections: Summary/Accroche, Expérience Professionnelle, Compétences, Formation, Langues, Certifications, Projets Personnels. Verified visually or via `py tests/cv_ats_check.py --lang fr`.
5. **ATS keyword score ≥ 95%** — `py tests/cv_ats_check.py` reports ≥ 19/20 keywords matched for the target JD (or the equivalent threshold for the role's keyword list).
6. **Text is selectable** — opening the PDF in any reader and selecting text confirms it is not a raster/image-only render (ATS-readable).

## Changelog
- 2026-04-08: Initial creation. Sahar AI Product Manager role (French). Exactly 2 pages, ATS ≥95%.
- 2026-05-19: Master CV upgrade for FR AI PM job applications. Bumped 14→15 ans. Added Mission Freelance entry (Accessory Masters, Déc. 2025 – Mars 2026). Trimmed Pitney Bowes 2→1 bullet. Expanded IA & GenAI skills (anneal, OpenRouter, Cloudflare Workers, Modal, Firecrawl, prompt caching, garde-fous LLM). Rewrote PROJETS PERSONNELS 2→6 items (Anneal, YouTube Video Analyzer, Job Tracker PM France, Self-Outbound Engine, CV Optimizer Agent, ProdCraft) with clickable GitHub/YouTube links. Self-iterating audit: 3 consecutive clean rounds (`tests/cv_ats_check.py`: 2 pages, 20/20 keywords; visual + French syntax; independent code-reviewer agent). Output: `.tmp/cv_master_debanjan_mazumdar.pdf`.
- 2026-05-19: English sibling `cv_builder_en.py` created — same content, translated, same layout. `exp_entry()` helper bundles title+employer+first bullet in `KeepTogether` (fixes orphan title at page break). `tests/cv_ats_check.py` extended with `--lang {fr,en}` flag and a per-language checklist dict (sections, entries, keywords, dates, default PDF). EN audit: 4-round loop — Round 1 ATS 20/20 clean, Round 2 visual found orphan title (Avaya), fixed via the KeepTogether tweak, Round 3 re-audit clean, Round 4 independent code-reviewer PASS 0 critical issues. Output: `.tmp/cv_master_debanjan_mazumdar_en.pdf`. Run: `py execution/personal_workflows/cv_builder_en.py --company <name> --role "<role>"` and audit with `py tests/cv_ats_check.py --lang en`.
