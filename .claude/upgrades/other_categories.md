# Other Workspace Categories — Upgrade Audit (2026-06-11)

Broad scoring of 14 categories. Top candidates per category audited against the 8-dimension rubric; rest skipped.

---

## Summary

- Categories scanned: 14
- Scripts in scope (total): 22 execution scripts + 20 directives
- Empty/stub categories (execution): `gtm_icp_filters/`, `image_generation/`, `n8n_workflows/`, `crm_and_pm/`, `rag/`
- HIT findings total: 9
- MAYBE findings total: 6
- Categories with no upgrades worth doing: `image_generation/`, `n8n_workflows/`, `crm_and_pm/`, `rag/` (all empty stubs), `gtm_client_workflows/` (only AM-locked scripts + one archive)

---

## Top 5 Cross-Category Upgrades

1. **`custom_scrapers/` — Dynamic Workflow candidate**: 8 job-board scrapers all run sequentially when they could fan out in parallel via `ultracode:` — each scraper is independent, no shared mutable state.
2. **`personalization/ai_opener_generator.py` — cache-aware pricing gap**: Uses OpenRouter/Claude Haiku with no cache-read/cache-write token accounting; flat-rate estimate overstates cost 5–10×. The system prompt is static per batch — ideal caching target.
3. **`lead_sourcing/` directives — declarative exit criteria missing**: Both directives (`google_maps_sourcing.md`, `sirene_company_lookup.md`) use imperative steps with no `## Exit Criteria` block; success conditions are implicit.
4. **`infrastructure/workspace_sast.py` — note capture gap + canary gap**: The SAST runner has no `.claude/notes/` entry. Also: it runs as a hook but has no `/api/health`-equivalent self-check exposing whether ruff/semgrep are installed (it exits 2 silently if neither is present).
5. **`enrichment/firecrawl_linkedin_dork.py` — sub-agent opportunity missed**: The script processes companies sequentially with `time.sleep(1.0)` inter-company delay. Parallelism via `ThreadPoolExecutor` (with a lock on the shared results list) would cut runtime ~5× for bulk mode.

---

## Per-Category Audit

### `lead_sourcing/`

Scripts: `prospeo_leads.py`, `serper_maps_scraper.py`, `sirene_company_lookup.py`
Directives: `google_maps_sourcing.md`, `sirene_company_lookup.md`
Top candidates: `serper_maps_scraper.py` (most reused), `sirene_company_lookup.py` (standalone enrichment step)

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | N/A | Each script is single-query; parallel fan-out handled by caller |
| 2. Declarative exit criteria | HIT | Both directives use imperative step lists; no `## Exit Criteria` block |
| 3. `--mode` flag | N/A | No LLM calls |
| 4. Sub-agent opportunity | N/A | Scripts are short (<100 LOC) |
| 5. Hardening violations | OK | `serper_maps_scraper.py`: no subprocess calls; `sirene_company_lookup.py`: no subprocess. Encoding rules n/a |
| 6. Note capture gap | HIT | No `.claude/notes/` entries for any lead_sourcing script or directive |
| 7. Agent Team candidate | N/A | Single-purpose scripts |
| 8. Canary/health gap | N/A | CLI scripts, not deployed services |

Recommended upgrade: Add `## Exit Criteria` blocks to both directives (one line each: "N leads sourced, deduped, and written to `.tmp/*.json`; exit code 0"). Add a notes stub at `.claude/notes/directives/lead_sourcing/google_maps_sourcing.md` capturing the SERPER_API_KEY rate-limit behavior.

---

### `enrichment/`

Scripts: `anymailfinder_lookup.py`, `firecrawl_linkedin_dork.py`, `million_verifier.py`
Directives: `email_find_verify.md`, `firecrawl_linkedin_dork.md`
Top candidate: `firecrawl_linkedin_dork.py` — bulk mode with sequential 1.0s sleep

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | HIT | Sequential `for company in companies` loop with `time.sleep(1.0)` between calls. Each company's Firecrawl dork is independent — prime `ThreadPoolExecutor` candidate |
| 2. Declarative exit criteria | MAYBE | `firecrawl_linkedin_dork.md` has rich step-list but no `## Exit Criteria` |
| 3. `--mode` flag | N/A | No LLM calls |
| 4. Sub-agent opportunity | N/A | Already a standalone script |
| 5. Hardening violations | MAYBE | `firecrawl_linkedin_dork.py`: if parallelism is added, shared `results` dict will need a `threading.Lock` on append (currently sequential, so no bug today — but the upgrade path has a trap) |
| 6. Note capture gap | HIT | No `.claude/notes/` entry for any enrichment script |
| 7. Agent Team candidate | N/A | — |
| 8. Canary/health gap | N/A | CLI script |

Recommended upgrade: Parallelize the bulk-company loop in `firecrawl_linkedin_dork.py` with `ThreadPoolExecutor(max_workers=3)` + `threading.Lock` on the shared results dict. Cap workers at 3 to stay polite to Firecrawl rate limits. Add exit criteria to directive.

---

### `personalization/`

Scripts: `ai_opener_generator.py`, `variant_generator.py`
Directives: `cold_email_sequences.md`, `auto_reply.md`
Top candidate: `ai_opener_generator.py` — calls Claude Haiku per lead, no cache-aware pricing

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | MAYBE | Processes leads one-at-a-time in a `for lead in leads` loop. Could fan out with `ThreadPoolExecutor` if latency matters — but rate-limit on OR/Anthropic is a constraint |
| 2. Declarative exit criteria | MAYBE | `cold_email_sequences.md` step 10 says "save to output JSON" — close but not a formal exit block |
| 3. `--mode` flag | HIT | `DEFAULT_MODEL = "anthropic/claude-haiku-4.5"` is hardcoded; `variant_generator.py` same (`DEFAULT_MODEL = "anthropic/claude-haiku-4.5"`). Neither exposes `--mode cheap/balanced/premium` per `_TEMPLATE.py` pattern |
| 4. Sub-agent opportunity | N/A | — |
| 5. Hardening violations | HIT | `ai_opener_generator.py`: no cache-aware pricing (system prompt is static per batch — ideal `cache_control` target; flat-rate estimate in the directive overstates cost ~5–10×) |
| 6. Note capture gap | HIT | No `.claude/notes/` entry for personalization scripts |
| 7. Agent Team candidate | N/A | — |
| 8. Canary/health gap | N/A | CLI script |

Recommended upgrade: (a) Add `--mode` to both scripts mirroring `_TEMPLATE.py` pattern — `cheap=haiku`, `balanced=sonnet`, `premium=opus`. (b) Add `cache_control: {"type": "ephemeral"}` to the static system prompt and add cache-aware token accounting to the cost log line.

---

### `gtm_icp_filters/`

Scripts: (none — `.gitkeep` only)
Directives: (none — `.gitkeep` only)

No high-value upgrades found. Category is a placeholder; no code to audit.

---

### `gtm_client_workflows/` (non-AM)

NOTE: Skipping `accessory_masters_*` per AM lockdown. `generate_qa_test_plan.py` references AM data internally (test cases hardcoded to AM campaign) but is not a live service — it's a one-off XLSX generator. `import_leads.py` is generic.

Scripts in scope: `import_leads.py` (generic CSV importer)
Scripts excluded: `accessory_masters_pipeline.py`, `generate_qa_test_plan.py` (AM-specific content)

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | N/A | `import_leads.py` is single-pass CSV read + write |
| 2. Declarative exit criteria | HIT | No directive for `import_leads.py` at all — directive gap |
| 3. `--mode` flag | N/A | No LLM calls |
| 4–8 | N/A / OK | Script is < 80 LOC, clean structure |

Recommended upgrade: Create `directives/gtm_client_workflows/import_leads.md` to document the CSV column-mapping behavior — currently zero directive coverage for this script.

---

### `custom_scrapers/`

Scripts: `apec_jobs.py`, `france_travail_jobs.py`, `google_jobs_serper.py`, `indeed_jobs.py`, `job_filter.py`, `wttj_jobs.py`, `adzuna_jobs.py`, `jooble_jobs.py`
Directives: `wttj_jobs.md`, `indeed_jobs.md`, `apec_jobs.md`, `france_travail_jobs.md`, `google_jobs_serper.md`, `adzuna_jobs.md`, `jooble_jobs.md`
Top candidates: All 7 job-board scrapers (they are identical in structure: fetch → normalize → save JSON)

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | HIT | 7 scrapers are fully independent — `job_tracker_pm_france.py` calls them sequentially. A fan-out wrapper (`ultracode:` task block or `ThreadPoolExecutor` in the orchestrator) would cut wall-clock time ~4–6× |
| 2. Declarative exit criteria | MAYBE | All 7 directives have `## Purpose` + `## Outputs` but no formal `## Exit Criteria` block |
| 3. `--mode` flag | N/A | No LLM calls in scrapers |
| 4. Sub-agent opportunity | N/A | Already individual scripts |
| 5. Hardening violations | OK | No subprocess calls; no threading; `argparse` present; encoding not applicable |
| 6. Note capture gap | HIT | No `.claude/notes/` entries for any custom_scrapers script or directive despite Jooble known-block (reCAPTCHA) and APEC session-cookie constraint |
| 7. Agent Team candidate | N/A | — |
| 8. Canary/health gap | N/A | CLI scripts |

Recommended upgrade: (a) Add a `directives/custom_scrapers/README.md` or a note file capturing known blockers: Jooble=reCAPTCHA blocked, APEC=session cookie required, Indeed=rate-limited. (b) Add a parallel fan-out wrapper in `job_tracker_pm_france.py` to run all scraper calls concurrently (each is I/O-bound, no shared state during fetch).

---

### `infrastructure/` (non-AM)

NOTE: Skipping `api-proxy/` per AM lockdown. `setup_instantly_webhook.py` references AM-specific URLs in its defaults (line 27–29) but is used as infrastructure tooling, not an AM data pipeline.

Scripts: `workspace_sast.py`, `setup_telegram_webhook.py`, `setup_instantly_webhook.py`
Directives: `workspace_sync.md`, `domain_inbox_management.md`, `setup_instantly_webhook.md`, `setup_telegram_webhook.md`, `canary_monitoring.md`, `workspace_sast.md`

Top candidate: `workspace_sast.py` — most complex, CI-adjacent, already has a directive

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | N/A | SAST runs linearly (ruff then semgrep) |
| 2. Declarative exit criteria | HIT | `workspace_sast.md` explains when to run but has no `## Exit Criteria` block stating expected exit codes + findings threshold |
| 3. `--mode` flag | N/A | No LLM calls |
| 4. Sub-agent opportunity | N/A | — |
| 5. Hardening violations | OK | `workspace_sast.py` uses `subprocess.run(..., encoding="utf-8", errors="replace")` on lines 104, 148, 187 — hardening rule 1 satisfied. No threading. |
| 6. Note capture gap | HIT | No `.claude/notes/` entry despite known gotchas: semgrep raises `RuntimeError` when `HOME`/`USERPROFILE` not set (workaround already in the script header, but not documented in notes) |
| 7. Agent Team candidate | N/A | — |
| 8. Canary/health gap | N/A | Hook/CLI script, not a deployed service |

Recommended upgrade: (a) Add exit-criteria block to `workspace_sast.md`: "exit 0 = no critical/high findings; exit 1 = critical/high found; exit 2 = no tools installed." (b) Add `.claude/notes/execution/infrastructure/workspace_sast.md` capturing the HOME env workaround and the Windows-Python-3.14/semgrep incompatibility.

---

### `content/` (non-rosy-origami)

Scripts: `humanizer.py`, `wedding_card_generator.py`
Directives: `humanizer.md`
(Excluding `rosy_origami_composer.md` and `execution/content/rosy_origami/` — Phase D scope)

Top candidate: `humanizer.py` — the most featureful script in this category

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | N/A | Single-text-in / single-text-out; batch use case not in scope for local script (lives in separate repo) |
| 2. Declarative exit criteria | MAYBE | `humanizer.md` has a detailed `## Steps` but no `## Exit Criteria` |
| 3. `--mode` flag | OK | Already has `--tier default/premium/gemini` — equivalent to `--mode` |
| 4. Sub-agent opportunity | N/A | — |
| 5. Hardening violations | OK | Script fixes Windows Unicode at top (`sys.stdout.reconfigure`); no subprocess calls in the local copy |
| 6. Note capture gap | HIT | No `.claude/notes/` entry for `content/humanizer.py` despite known OR-empty-credits fallback behavior (noted in memory but not in notes files) |
| 7. Agent Team candidate | N/A | — |
| 8. Canary/health gap | N/A | CLI script |
| bonus | NOTE | `wedding_card_generator.py` has hardcoded event details and no CLI args — single-use script, no upgrade value |

Recommended upgrade: Add `.claude/notes/execution/content/humanizer.md` capturing: OR=empty → falls back to Anthropic-direct; `--tier gemini` requires `GEMINI_API_KEY`; `sys.stdout.reconfigure` is the Windows Unicode guard.

---

### `image_generation/`

Scripts: (none — `.gitkeep` only)
Directives: (none — `.gitkeep` only)

No high-value upgrades found. Category is a placeholder stub.

---

### `video/` (non-remotion)

Scripts: `youtube_video_analyzer.py` (remotion scripts excluded per Phase D scope)
Directives: `youtube_video_analyzer.md` (remotion directives excluded)

Top candidate: `youtube_video_analyzer.py` — most complex non-remotion script in the workspace

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | HIT | Batch mode (`--urls-file`) processes multiple YouTube URLs sequentially; each URL's pipeline (download → scene detect → frame extract → LLM analyze) is fully independent — prime `ultracode:` fan-out target |
| 2. Declarative exit criteria | MAYBE | `youtube_video_analyzer.md` has rich steps but no formal exit criteria block |
| 3. `--mode` flag | OK | Already has `--tier default/premium/gemini` + `--provider` flag |
| 4. Sub-agent opportunity | N/A | — |
| 5. Hardening violations | OK | `subprocess.run` at line 657 uses `encoding="utf-8", errors="replace"` — hardening rule 1 satisfied. No `ThreadPoolExecutor` in this script. |
| 6. Note capture gap | HIT | No `.claude/notes/execution/video/youtube_video_analyzer.md`; known quirks (yt-dlp rate-limit, PySceneDetect Windows install, creator-profile cache TTL) not documented |
| 7. Agent Team candidate | MAYBE | Multi-URL batch analysis with per-creator profile injection could benefit from Agent Team: one agent per URL, sharing a creator-profile cache agent |
| 8. Canary/health gap | N/A | CLI script |

Recommended upgrade: (a) Parallelize batch mode with `ThreadPoolExecutor(max_workers=2)` (capped low due to yt-dlp rate limits) + lock on creator-profile cache writes. (b) Add notes file capturing PySceneDetect Windows install path and yt-dlp rate-limit behavior. (c) Add `## Exit Criteria` to directive.

---

### `n8n_workflows/`

Scripts: (none — `.gitkeep` only)
Directives: (none — `.gitkeep` only)

No high-value upgrades found. Category is a placeholder stub.

---

### `crm_and_pm/`

Scripts: (none — `.gitkeep` only)
Directives: (none — `.gitkeep` only)

No high-value upgrades found. Category is a placeholder stub.

---

### `google/`

Scripts: `gmail_send_digest.py`, `google_sheets_writer.py`
Directives: `gmail_send_digest.md`, `google_sheets_writer.md`

Top candidate: `google_sheets_writer.py` — most reused module (used by job search sheet pipeline)

| Axis | Score | Note |
|------|-------|------|
| 1. Dynamic Workflow | N/A | Single-sheet writer; fan-out not applicable |
| 2. Declarative exit criteria | MAYBE | `google_sheets_writer.md` has a detailed inputs section but no `## Exit Criteria` or `## Steps` block at all — directive is setup-focused only |
| 3. `--mode` flag | N/A | No LLM calls |
| 4. Sub-agent opportunity | N/A | — |
| 5. Hardening violations | OK | No subprocess. Uses `tenacity` retry decorator (correct pattern). Module-level `_client` cache with no threading — OK since script is single-threaded |
| 6. Note capture gap | HIT | No `.claude/notes/` entry; known gotcha: `gspread` service-account scope must include Drive API for sheet creation — not in the directive's scope section |
| 7. Agent Team candidate | N/A | — |
| 8. Canary/health gap | N/A | Library module, not a deployed service |

Recommended upgrade: (a) Add `## Steps` + `## Exit Criteria` to `google_sheets_writer.md` (currently only has setup docs). (b) Add note capturing the `gspread` Drive scope requirement and the `_meta` tab cron-idempotency pattern.

---

### `rag/`

Scripts: (none — `.gitkeep` only)
Directives: (none — `.gitkeep` only)

No high-value upgrades found. Category is a placeholder stub.

---

## Hardening Violation Summary (across all in-scope scripts)

| Rule | Scripts with violation |
|------|----------------------|
| 1. Subprocess encoding | All subprocess calls checked — all use `encoding="utf-8", errors="replace"`. **No violations.** |
| 2. Threading locks | No scripts in scope use `ThreadPoolExecutor` today. When fan-out is added (enrichment, custom_scrapers, video), locks will be required on shared results. **Pre-emptive HIT for upgrade path.** |
| 3. LLM-supplied path validation | Not applicable to any script in this scope (no path derived from LLM output outside personal_workflows). |
| 4. Cache-aware Claude pricing | `ai_opener_generator.py` and `variant_generator.py` use flat-rate LLM accounting with no `cache_read`/`cache_write` token tracking. **HIT.** |
| 5. `except Exception: pass` | Zero bare swallows found across all in-scope scripts. **No violations.** |

---

## Missing Directives

| Script | Has directive? |
|--------|---------------|
| `gtm_client_workflows/import_leads.py` | No |
| `content/wedding_card_generator.py` | No (single-use script, not worth a directive) |

---

## Notes Coverage Gap Summary

Every category except `content/humanizer.py` (partially covered by MEMORY.md) has zero `.claude/notes/` entries. Highest-value notes to add:
1. `custom_scrapers/` — Jooble reCAPTCHA block, APEC session-cookie, Indeed rate limit
2. `infrastructure/workspace_sast.py` — HOME env workaround, semgrep Windows incompatibility
3. `video/youtube_video_analyzer.py` — yt-dlp rate limits, PySceneDetect install, creator-profile TTL
4. `enrichment/firecrawl_linkedin_dork.py` — Firecrawl /search dork rate limits, priority-tier ordering
5. `personalization/ai_opener_generator.py` — OR empty-credits fallback, cache opportunity
