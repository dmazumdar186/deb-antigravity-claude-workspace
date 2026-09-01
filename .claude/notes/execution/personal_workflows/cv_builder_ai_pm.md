# cv_builder_ai_pm_en.py / cv_builder_ai_pm_fr.py Notes

New AI PM generic CV variant, created 2026-09-01. Builds on `cv_builder_core.py` (shared module) — core left untouched.

- [technical] Linux/cloud font fallback: `cv_builder_core._register_fonts()` finds no Arial on Linux and falls back to base-14 Helvetica, which makes the bullet glyph '•' extract as '(cid:127)' (un-embedded base-14 glyphs), and `ParagraphStyle.bulletFontName` defaults to 'Helvetica' regardless of the paragraph font. Fix used in the new variants (core untouched): stage DejaVuSans.ttf/DejaVuSans-Bold.ttf as arial.ttf/arialbd.ttf in a temp dir, point WINDIR at it before calling core's `_register_fonts()`, and set `bulletFontName` explicitly on bullet/project styles.
- [constraint] Cloud sessions have no GEMINI_API_KEY in env, so `tests/cv_recruiter_panel.py` cannot run there — panel audits run locally only, or via a Claude sub-agent substitute.
- [learned] Verbosity calibration from 2026 France research: the Dior variant's 1,255 extracted words was ~2x the effective norm; the ai_pm variants target ≤750 words, page 1 self-contained (accroche + impact + all experience), bold share ~15-20%. FR variant sits exactly at the 18-metric ATS threshold — don't remove quantified markers from FR content without adding first.
- [pattern] New ATS profiles ai_pm_en/ai_pm_fr added additively to `tests/cv_ats_check_pm.py` (existing pm_en/pm_fr profiles untouched); both new PDFs passed 0 findings / 100% keyword coverage on first render.

## See also

- .claude/notes/execution/personal_workflows/cv_builder.md (general cv_builder family notes, Arial TTFont registration on Windows)
