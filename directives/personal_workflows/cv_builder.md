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

## Changelog
- 2026-04-08: Initial creation. Sahar AI Product Manager role (French). Exactly 2 pages, ATS ≥95%.
