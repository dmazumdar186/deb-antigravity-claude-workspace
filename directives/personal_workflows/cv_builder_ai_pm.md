# CV Builder — AI PM Generic (EN + FR)

## Goal
Generate the lean, ATS-optimised, generic **Senior AI Product Manager** CV (AI-first framing
for agentic-automation roles, e.g. Believe "Senior PM — Agentic & AI Automation") in English
and French. Submission-ready 2-page PDFs, no manual editing.

## Inputs
- `--out <path>` (optional): output PDF path; defaults below.

## Tools/Scripts

| Script | Purpose |
|--------|---------|
| `execution/personal_workflows/cv_builder_ai_pm_en.py` | EN variant. Content-only; rendering delegated to `cv_builder_core.py`. |
| `execution/personal_workflows/cv_builder_ai_pm_fr.py` | FR variant, mirrored layout. |
| `execution/personal_workflows/cv_builder_core.py` | Shared rendering primitives (do not modify without approval). |
| `tests/cv_ats_check_pm.py` | Hard-fail ATS gate — profiles `ai_pm_en` / `ai_pm_fr` (32-keyword pools incl. LLM/RAG/agentic/orchestration, ≥90% coverage, ≥18 metrics, forbidden-token scan). Free, pdfplumber-only. |
| `tests/cv_recruiter_panel.py` | 6-persona hiring-committee audit (paid Gemini API; needs `GEMINI_API_KEY`). |

## Outputs
- `.tmp/cv_ai_pm_debanjan_mazumdar_en.pdf` / `_fr.pdf`
- Committed deliverables: `deliverables/cv_ai_pm/CV MAZUMDAR Debanjan EN.pdf` / `FR.pdf`

## Steps
1. Edit `build_story()` in the relevant variant only if repositioning (keep the design spec below).
2. `python3 execution/personal_workflows/cv_builder_ai_pm_en.py` (and `_fr.py`).
3. Audit: `python3 tests/cv_ats_check_pm.py --lang ai_pm_en --pdf <pdf>` (and `ai_pm_fr`). Must report 0 findings.
4. Verify exactly 2 pages, selectable text, page 1 self-contained (accroche + impact line + all experience entries).
5. Copy passing PDFs to `deliverables/cv_ai_pm/`.

## Design Spec (2026 France research-backed)
| Element | Value |
|---|---|
| Pages | Exactly 2; page 1 must stand alone (90% of recruiters decide on page 1) |
| Word budget | ≤ 750 extracted words per language (Dior variant's 1,255 was the anti-pattern) |
| Bullets | 3–4 for current roles, 1 for roles older than ~5 years, each ≤ ~30 words with ≥1 bolded metric |
| Balance | 60% product ownership / 40% hands-on build (mirrors agentic-PM JDs) |
| Bold share | ~15–20% of words: all metrics + load-bearing keywords only |
| Conventions | No photo, `+33` phone, CEFR (C2) language labels, accroche ≤ 5 lines |

## Edge Cases
- **Linux/cloud fonts**: no Arial on Linux — `_register_ai_pm_fonts()` in each variant stages
  DejaVu Sans as `arial.ttf`/`arialbd.ttf` in a temp dir and points `WINDIR` there before core's
  `_register_fonts()` runs; also sets `bulletFontName` explicitly (core's default `Helvetica`
  bullet font extracts `•` as `(cid:127)`). Verify extraction shows no `(cid:` tokens.
- **FR metric density is at the 18/18 threshold** — removing any quantified marker from the FR
  content fails the gate; add before removing.
- **Recruiter panel in cloud sessions**: `GEMINI_API_KEY` is not configured in the cloud
  environment — the panel only runs locally (or add the key to the environment's variables).
- Forbidden tokens (client names `Accessory Masters` / `Elite Broker` / `Hedgestone`, API-key
  patterns) hard-fail the ATS gate.

## Exit Criteria
Both PDFs exist, exactly 2 pages, `cv_ats_check_pm.py` reports 0 findings for `ai_pm_en` and
`ai_pm_fr`, text selectable with clean glyphs, deliverables copied to `deliverables/cv_ai_pm/`.

## Changelog
- 2026-09-01: Initial creation. Lean rebuild targeting generic Senior AI PM roles in France
  (research: lean 2-page ≤750 words beats dense; Believe JD 60/40 split). EN 692 / FR 747 words,
  100% keyword coverage, 0 ATS findings on first render.
