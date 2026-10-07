# Jev Use Case Finder (use case 19)

## Goal
Find where Jev helps this operator: rank a catalog of Jev use cases against a profile of the operator and
business, and scan past-work artefacts for steps a sub-second typed decision (classify / pick / score / gate)
could have replaced.

## Operator prompts
- "Which Jev use cases fit my business" → `rank`
- "Find Jev steps in my past sessions" → `sessions`

## Inputs
- Catalog: `--catalog file.json`, else live `https://shipwithjev.com` (+ `/use-cases`, `/sitemap.xml`), else
  the bundled `execution/infrastructure/jev_specs/jev_use_case_catalog.json` (47: RoboNuggets 19 + Hugging Face
  "18 practical JEV use cases" + 10 industry examples; keys id, title, category, description, inputs, effort 1-3).
- Profile: `--profile` (repeatable); default `.claude/notes/general.md`, `directives/README.md`, `HANDOFF.md`
  (first 6k chars each).
- Built flags: ✅ rows of the table in `directives/infrastructure/jev.md` (row N ↔ catalog id `rnNN_*`).
- Env `OPENROUTER_API_KEY` (cloud alias `OPENROUTER_API_TOEKN`).

## Tools
`execution/infrastructure/jev_use_case_finder.py`
```
python3 execution/infrastructure/jev_use_case_finder.py catalog [--catalog f.json] [--no-live]
python3 execution/infrastructure/jev_use_case_finder.py rank [--profile p.md ...] [--top 10] [--include-built] [--live]
python3 execution/infrastructure/jev_use_case_finder.py sessions [--dir path --glob "*.md"] [--min-prob 0.7] [--limit N]
```
- `rank`: one Jev call per use case; questions `fit` (score 0-3), `data_ready` (noul), `already_built` (noul;
  `built` passed in state), `impact` (choice). Rank = fit × (1 + data_ready); built ones excluded unless
  `--include-built`. Quick wins = fit ≥ 2, data_ready ≥ 0.6, effort 1. "Needs data first" = fit ≥ 2, data_ready < 0.6.
- `sessions`: default sources `HANDOFF*.md`, `.claude/handoffs/`, `.claude/notes/**`, `docs/audits/`; steps =
  bullets/paragraphs ≥ 8 words; batches of 20 steps → 40 questions (noul + primitive choice) per call.

## Outputs
- `.tmp/jev_use_cases_for_me.md`, `.tmp/jev_steps_found.md`, `.tmp/shipwithjev_raw.json`; ledger `caller=jev_use_case_finder`.

## Edge cases
- shipwithjev.com may block or change markup — the bundled catalog is the fallback. On 2026-10-07 the live
  fetch worked but the site is a community gallery (~620 builds, card description = author), so `rank` uses the
  bundled catalog by default; `--live` ranks the gallery (hundreds of calls, still cents).
- Jev fails open: errored rows score 0 and sink to the bottom; check the ledger `errors` count.
- Paths outside the repo are refused.

## Changelog
- 2026-10-07: Created (RoboNuggets use case 19). Live shipwithjev fetch works (gallery, author-only descriptions).
