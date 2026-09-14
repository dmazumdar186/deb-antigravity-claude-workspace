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

## [2026-09-14 12:00] learned job_search_v2 sheet duplicates root cause
STANDARD_HEADERS lost the `_id` column so in-sheet dedup was a silent no-op; fixed with a title+company fingerprint (contracts.compute_fingerprint) merged in-batch, in seen.db, and cross-tab at append (565 -> 424 jobs live 2026-09-10).
Source: execution/personal_workflows/job_search_v2/contracts.py, normalizer/dedup.py, notifier/sheet.py

## [2026-09-14 12:00] learned job_search_v2 posted-date freshness unreliable at source
WTTJ Algolia gives the update date and LinkedIn cards show the repost date; Stage 3.8 posting_verifier reads the job page and the page date wins (13/148 live jobs dropped as stale on first run).
Source: execution/personal_workflows/job_search_v2/normalizer/posting_verifier.py

## [2026-09-14 12:00] technical job_search_v2 board-specific fetch quirks
WTTJ anti-bot returns HTTP 202 + empty body (retry once after 3s); WTTJ soft-404 is HTTP 200 with "Error 404 Page not found"; LinkedIn expired jobs 200-redirect to a `trk=expired_jd_redirect` URL; LinkedIn 429s ~3% of fetches at concurrency 8; weworkremotely.com 403s every page fetch (kept on feed pubDate, stamped unverified).
Source: execution/personal_workflows/job_search_v2/normalizer/posting_verifier.py

## [2026-09-14 12:00] learned job_search_v2 domain filter false positives from live data
skip_domain_anchors overlapping built-in anchors double-counted one mention as two hits; software vocabulary words (instrumentation, optics, sensor, mechanical, battery, RF, kernel) are now title-only, excluded from description counting; ambiguous anchor + software-product word in the same title is rescued.
Source: execution/personal_workflows/job_search_v2/normalizer/domain_filter.py

## [2026-09-14 12:00] pattern job_search_v2 Verified stamp and acceptance gate
Every sheet row carries `Verified` = "open · posted YYYY-MM-DD · checked YYYY-MM-DD"; the acceptance gate fails stale (>7d), closed, undated or unstamped rows and any run with skipped verification; purge_irrelevant_rows.reverify_rows re-verifies historical unstamped rows at 400 fetches/run.
Source: execution/personal_workflows/job_search_v2/purge_irrelevant_rows.py

## [2026-09-14 12:00] technical job_search_v2 verify_jobs worker isolation
Each verify_jobs worker is wrapped in try/except so one page-fetch exception doesn't kill the cron; future page dates (>now+1 day) are ignored in favour of the source date.
Source: execution/personal_workflows/job_search_v2/normalizer/posting_verifier.py

## [2026-09-14 12:00] constraint job_search_v2 cloud sandbox limitations
gspread (_cffi_backend/cryptography) and pdfplumber cannot import in this sandbox (tests stub gspread in sys.modules); langdetect has no wheel for Python 3.11 here so the language filter defaults to accept locally, though CI installs it fine.
Source: execution/personal_workflows/job_search_v2/

## [2026-09-14 13:15] learned job_search_v2 strict verification mode closes three unverified-link leaks
Panel audit found blocked-host, dated-but-unconfirmed, and never-rechecked rows leaking past the verifier; strict mode (config verification.strict, default true) drops unverifiable_blocked/unconfirmed_open and rechecks stamped rows every recheck_after_days (3).
Source: execution/personal_workflows/job_search_v2/normalizer/posting_verifier.py, purge_irrelevant_rows.py, commit 5d6f7b6
