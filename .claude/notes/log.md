# Workspace Activity Log (append-only)

Chronological one-line entries appended after every directive/execution edit by the
`note-taker` sub-agent (defined at `.claude/agents/note-taker.md`). Newer entries at
the bottom. Never edit historical entries — they're a frozen record of what was
known at that point in time.

Format:
`## [YYYY-MM-DD HH:MM] {tag} {subject}`

Tags (single, lowercase): `learned`, `pattern`, `constraint`, `preference`, `technical`, `incident`.

The companion `.claude/notes/general.md` (and topic files under `.claude/notes/`)
hold the durable distilled knowledge. `log.md` is the raw chronological feed.

---

## [2026-06-11 00:00] pattern Workspace upgrade Phase 4 seeded the log file (Karpathy llm-wiki append-only pattern). Future entries appended by note-taker sub-agent.

## [2026-09-01 15:00] technical cv_builder_ai_pm font fallback on Linux
Base-14 Helvetica fallback in cv_builder_core._register_fonts() breaks bullet glyph rendering; ai_pm variants stage DejaVuSans as arial.ttf/arialbd.ttf and set bulletFontName explicitly.
Source: execution/personal_workflows/cv_builder_ai_pm_en.py, cv_builder_ai_pm_fr.py

## [2026-09-01 15:00] constraint cv_recruiter_panel.py unusable in cloud sessions
No GEMINI_API_KEY in cloud env; panel audits must run locally or via a Claude sub-agent substitute.
Source: tests/cv_recruiter_panel.py

## [2026-09-01 15:00] learned ai_pm CV variants verbosity calibration
Target ≤750 words, page-1 self-contained, ~15-20% bold share; FR variant sits exactly at the 18-metric ATS threshold so quantified markers must not be removed without replacement.
Source: execution/personal_workflows/cv_builder_ai_pm_fr.py

## [2026-09-01 15:00] pattern New ATS profiles added additively for ai_pm variants
ai_pm_en/ai_pm_fr profiles added to tests/cv_ats_check_pm.py without touching existing pm_en/pm_fr; both new PDFs passed 0 findings / 100% keyword coverage on first render.
Source: tests/cv_ats_check_pm.py
