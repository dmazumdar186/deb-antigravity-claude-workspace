# cv_builder.py Notes

Captured from .claude/upgrades/personal_workflows.md on 2026-06-12.

- [technical] Arial TTFont registration: Must call `pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))` before using Arial in any reportlab style. Plain string font names fail silently on Windows. This is also documented in general.md.
- [technical] Shared boilerplate: `cv_builder.py`, `cv_builder_en.py`, and `cv_builder_skott.py` share ~80% identical boilerplate (`_register_fonts`, `SectionHeader`, `exp_entry`, `skill_row`, styles dict). The only unique part per variant is `build_story()`. When editing style or layout, apply the same change to all 3 variants or extract a shared `cv_builder_core.py`.
- [constraint] No --mode or --language flag: None of the 3 variants expose a `--language` or `--template` flag to unify them. Do not refactor to a single unified script without first reading all 3 `build_story()` implementations to understand the variation.
- [pattern] Exit criteria: For script validation, expected output is a PDF at the target path with size > 50 KB and page count = 2. Any deviation (blank PDF, single-page output) indicates a reportlab table layout issue, usually caused by missing `colWidths`.
- [learned] AM reference in content: The CV scripts reference Accessory Masters as a past freelance client role (biographical data only). Not operational AM code — confirmed clean per 2026-06-11 audit.

## See also

- .claude/upgrades/personal_workflows.md
- .claude/notes/general.md (reportlab Arial/table-widths entries)
- C:\Users\deban\.claude\projects\c--Users-deban-OneDrive-Documents-AntiGravity-Project-Space\memory\feedback_cv_builder.md
