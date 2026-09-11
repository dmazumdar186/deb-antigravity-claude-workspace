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

## [2026-09-06 16:00] technical job_digest LinkedIn geoIds verified live
FR, DE, AT, BE, NL, GB, CH, IN, SG, CA geoIds confirmed working via LinkedIn guest API; US instead uses a state-abbreviation regex since guest results return "City, ST" strings.
Source: directives/personal_workflows/job_digest.md, engine/job_digest/registry.py

## [2026-09-06 16:00] learned job_digest live preview run FR+DE Sales Manager
345 jobs fetched in ~5 min across LinkedIn FR/DE, WTTJ FR, Hellowork, RemoteOK (France Travail returned 0 without keys); 13 rows kept as relevant. Rate-limit preview to once/hour.
Source: engine/job_digest

## [2026-09-06 16:00] learned job_digest remote detector misclassified bare "Remote" location
Ported remote detector marked a bare "Remote" location string as HYBRID by matching description text first, silently dropping all RemoteOK/WeWorkRemotely jobs; fixed by checking location string before description text.
Source: engine/job_digest

## [2026-09-06 16:00] learned job_digest state marking moved after confirmed SMTP send
Marking jobs "seen" before a confirmed email send caused jobs to be burned on the second daily cron fire; state is now only marked for digest rows after a real send succeeds.
Source: engine/job_digest

## [2026-09-06 16:00] pattern job_digest acceptance gate needs an independent implementation
Acceptance gate must use its own tokenizer/alias match rather than reusing the filter pipeline's logic, otherwise it's a tautology and exit code 3 is dead code.
Source: engine/job_digest

## [2026-09-06 16:00] constraint job_digest repo layout and packaging
Friend's repo layout is engine/job_digest + engine/requirements.txt with PYTHONPATH=engine; shipped zip excludes tests/, so fixtures live in job_digest/fixtures/. scripts/package_job_digest.py refuses to build if any bundled file contains operator personal data (blocklist scan).
Source: scripts/package_job_digest.py

## [2026-09-06 16:00] constraint job_digest falls back to heuristic ranker without an API key
A Claude subscription does not provide an ANTHROPIC_API_KEY, so unattended job_digest runs default to the heuristic ranker rather than an LLM ranker.
Source: engine/job_digest

## [2026-09-11 10:00] learned gaia_sourcing residence gate false positives
Firm-office phrases ("joined the Cork office of") and project/market mentions ("experience in Ireland and the UK") are not residence evidence under require_direct_evidence and must not yield a place.
Source: execution/gtm_client_workflows/gaia_sourcing

## [2026-09-11 10:00] learned gaia_sourcing discipline exclude terms scoped to title/sector only
Exclude terms must fire only from the title or a sector claim, never from an employer/project sentence; a side "health and safety officer" duty wrongly excluded a structural Associate Director.
Source: execution/gtm_client_workflows/gaia_sourcing

## [2026-09-11 10:00] learned gaia_sourcing client-facing reasons must trace to the gate basis claim
Reasons shown to the client are rebuilt from the gate's basis claim with the quote on the same row; generic templates contradicted the evidence three times on one page.
Source: execution/gtm_client_workflows/gaia_sourcing

## [2026-09-11 10:00] learned gaia_sourcing rule text must render from live params, not spec description fields
Rendering rule text from spec description fields leaked an internal note ("PENDING KEITH MOLONY CALL") into client-facing output; must render from live params after overrides.
Source: execution/gtm_client_workflows/gaia_sourcing

## [2026-09-11 10:00] pattern gaia_sourcing passes-with-note surfaced, not silently counted
Near-miss passes are shown as "n with a note" rather than folded into plain pass counts.
Source: execution/gtm_client_workflows/gaia_sourcing

## [2026-09-11 10:00] process gaia_sourcing client feedback authority is the commit message, not a re-read transcript
Recorded feedback in commit messages (e.g. a626381 "too senior, some not in Ireland") takes precedence over re-deriving feedback from a call transcript; Fathom mis-transcribed a name (Steph for Maddie) and "over 60" was a match score, not an age.
Source: execution/gtm_client_workflows/gaia_sourcing

## [2026-09-11 10:00] pattern gaia_sourcing offline --check on cached persons is the zero-spend demo path
Spend asserted 0.00 before and after an offline --check run on cached persons confirms no live calls fired.
Source: execution/gtm_client_workflows/gaia_sourcing

## [2026-09-11 10:00] constraint gaia_sourcing run cache rescue branch must never merge
Branch gaia-run-cache-2026-09-14 holds the run cache tarball for rescue purposes only; never merge it into main.
Source: execution/gtm_client_workflows/gaia_sourcing
