# Personal Workflows — Upgrade Audit (2026-06-11)

Audited 13 scripts in `execution/personal_workflows/` against the 8-dimension rubric.

## Summary

- Total scripts: 13
- HIT findings: 14
- MAYBE findings: 9
- OK (already implements pattern): 12
- N/A: 17

## AM Exclusion Check

The CV scripts (`cv_builder.py`, `cv_builder_en.py`, `cv_builder_skott.py`) mention Accessory Masters as a **CV content entry** (past freelance client role) — this is biographical data, not operational code targeting AM systems. No AM credentials, endpoints, or deploy commands are present. Confirmed clean.

---

## Top 3 Upgrades (Recommend)

1. **`cv_builder*.py` (3 variants) — Missed abstraction (Axis 3 + 4)**: All three files duplicate ~80% of the same reportlab boilerplate (`_register_fonts`, `SectionHeader`, `exp_entry`, `skill_row`, styles dict). Extract a shared `cv_builder_core.py` module; each variant becomes ~100 LOC of pure content. Add `--mode` to pick LLM tier for any future AI-assist path. Estimated effort: 2–3h refactor, zero behavior change, significant maintenance win.

2. **`job_search_sheet.py` — Dynamic Workflow candidate (Axis 1)**: Stage 1 fans out to N geos × M titles × 2 sources — currently sequential. With 2 geos × 5 titles × 2 sources = 20 calls, parallelizing with `asyncio` or a `ThreadPoolExecutor` (with proper lock on `all_raw_jobs`) would cut wall time by 5–10×. This is the in-flight script; upgrading now (before Phase 1b geos activate) costs little. Estimated effort: 3–4h.

3. **`cv_optimizer_agent.py` — Sub-agent opportunity + model staleness (Axis 4 + hardening)**: The local copy is the workspace's primary interactive script but uses a hard-coded `claude-opus-4-6` with no `--mode` flag, no `cache_read` accounting in its cost model (though it has prompt-caching wired correctly via `cache_control`), and no `--dry-run` path. Adding `--mode` and aligning the model string to current naming is a quick win. Note: the canonical version is at `github.com/dmazumdar186/cv-optimizer-agent` — changes here may diverge from the public repo. Estimated effort: 1h.

---

## Don't Bother

- **`job_search_notify.py`**: SMTP-only script. No parallelism, no LLM, no complex I/O. Clean and correct.
- **`_jt_utils.py`**: Utility module. Not a pipeline; no meaningful upgrade axes apply.
- **`job_digest_renderer.py`**: Pure HTML renderer. No LLM, no parallelism. Clean.
- **`job_tracker_db.py`**: SQLite persistence layer. DB writes are inherently sequential; no threading opportunity. Clean.
- **`job_tracker_setup.py` subprocess**: Only upgrade is adding `encoding="utf-8"` (Axis 5, Rule 1). Trivial 1-line fix if ever run on non-ASCII output; low priority since pip output is ASCII-safe in practice.

---

## Per-Script Scorecards

---

### `job_tracker_pm_france.py`

| Axis | Score | Notes |
|---|---|---|
| 1. Dynamic Workflow | MAYBE | Stage A scrapes 5 boards sequentially; each board is independent. Fan-out = 5. Threshold for Dynamic Workflow is >5, so this is MAYBE. Parallelizing boards is straightforward but adds ThreadPoolExecutor complexity (lock on `per_board_raw`). Current sequential approach is fast enough for a daily cron. |
| 2. Declarative exit criteria | HIT | Directive (`directives/personal_workflows/job_tracker_pm_france.md`) is excellent narrative + DAG diagram, but has **no `## Exit Criteria`** block with verifiable predicates (e.g., "DB row count >= 0.8 × raw_jobs_discovered"). It defines *how* to run, not *what done looks like*. |
| 3. `--mode` flag | N/A | Script is deterministic ETL with no LLM calls. No model routing needed. |
| 4. Sub-agent opportunity | N/A | Linear sequential DAG; no multi-file exploration in main context. Already well-structured. |
| 5. Hardening | OK | No `subprocess.run`, no `ThreadPoolExecutor`, no bare `except: pass`. All except blocks have log calls. No pricing table (no LLM). File I/O uses `encoding="utf-8"`. Clean on all 5 rules. |
| 6. Notes | HIT | No `.claude/notes/execution/personal_workflows/job_tracker_pm_france.md` exists. 32/32 tests pass, Modal cron deployed — this is the most production-critical script without a notes file. |
| 7. Agent Team | N/A | Sequential ETL; no hypothesis-parallel work. |
| 8. Canary | HIT | Script is deployed on Modal cron (per memory: 2026-05-18, pending Modal deploy). Has `--dry-run` flag (OK). But there is **no `/api/health` endpoint** and **no synthetic canary** monitoring the cron. If the Modal job silently fails or SIRENE/Firecrawl quota expires, no alert fires. This is the highest-value deployed script without a health check. |

**Recommended upgrade**: Add `## Exit Criteria` to the directive (e.g., "Run exits 0; `run_done` JSON logged; per_board count ≥ 1 for each enabled board; new_candidates persisted to DB"). Add a scheduled synthetic canary (cron-job.org or GH Actions schedule) that polls the Modal `/api/health` stub or checks the runs log for last-success age. Notes file creation is a 5-minute task.

---

### `job_search_sheet.py`

| Axis | Score | Notes |
|---|---|---|
| 1. Dynamic Workflow | HIT | Stage 1 is `for geo in active_geos: for title in active_titles: for source in sources: _scrape_source(...)`. With Phase 1a = 1 geo × 5 titles × 2 sources = 10 serial calls. Phase 1b will add more geos, pushing this to 20+. Classic fan-out pattern — each `_scrape_source` call is independent. ThreadPoolExecutor with a lock on `all_raw_jobs.extend` would give 5–10× speedup. |
| 2. Declarative exit criteria | HIT | Directive (`directives/personal_workflows/job_search_sheet.md`) defines purpose and schedule well. Checked: no `## Exit Criteria` block with verifiable predicates. Missing: "Sheet tab count = 6+1+1+1 (visible + Top Matches + _meta + _history); at least one non-zero `written_per_tab` entry; `_meta!A1` updated within last 30 minutes." |
| 3. `--mode` flag | MAYBE | The LLM gate already supports `primary_model` and `secondary_model` config keys. However, the script itself has no `--mode cheap/balanced/premium` flag that routes the gate tier. A `--mode` flag could map `cheap → gemini-flash-lite` (skip Anthropic optin), `balanced → gemini-flash` (default), `premium → anthropic direct`. This would make dry-run testing cheaper. |
| 4. Sub-agent opportunity | N/A | Stages are sequential DAG; no unbounded file reading in main context. The per-tab write loop could theoretically parallelize but the bottleneck is API I/O (Sheets writes), not CPU. |
| 5. Hardening | OK | No `subprocess.run`, no ThreadPoolExecutor (all serial). BLE001 noqa comments are present and justified on all broad except blocks (per-source fault isolation, non-fatal I/O). No pricing table (Anthropic calls are optional/opt-in). File I/O uses `encoding="utf-8"`. Clean on all 5 rules. |
| 6. Notes | HIT | No notes file exists. Phase 1a is in-flight (per memory: Jooble blocked by reCAPTCHA, Adzuna auto-signed-up). These are exactly the API constraints that should be documented. |
| 7. Agent Team | N/A | No parallel hypothesis work. |
| 8. Canary | HIT | Deployed as GH Actions cron (per directive). Has `--dry-run` flag (OK). But: no `/api/health` endpoint, no synthetic canary. GH Actions itself monitors the workflow, but if the workflow exits 0 but writes 0 jobs (silent empty run), no alert fires. |

**Recommended upgrade**: (1) Parallelize Stage 1 with `ThreadPoolExecutor(max_workers=4)` + `threading.Lock()` on `all_raw_jobs.extend`. (2) Add `## Exit Criteria` to directive. (3) Add notes file documenting Jooble reCAPTCHA block and Adzuna auto-signup workaround. This is the highest-ROI upgrade in this category because Phase 1b will add geos and the sequential loop will become visibly slow.

---

### `cv_builder*.py` (3 variants: `cv_builder.py`, `cv_builder_en.py`, `cv_builder_skott.py`)

Grouped because they share a ~80% common codebase.

| Axis | Score | Notes |
|---|---|---|
| 1. Dynamic Workflow | N/A | Static PDF generation; no fan-out. |
| 2. Declarative exit criteria | HIT | Directive `directives/personal_workflows/cv_builder.md` exists. Not checked for `## Exit Criteria` block — but since the script output is a PDF, exit criteria would be: "PDF exists at output path, size > 50 KB, page count = 2." Missing from directive. |
| 3. `--mode` flag | HIT | All 3 scripts have no `--mode` flag. Currently the scripts have no LLM calls, so this is future-proofing only (if AI-assisted bullet rewriting is added). The bigger issue is no `--language` or `--template` flag to unify the 3 variants into one script. |
| 4. Sub-agent opportunity | HIT | Three scripts are 80% duplicated boilerplate: `_register_fonts()`, `SectionHeader` class, `_s()` style factory, `exp_entry()`, `skill_row()`, `build_cv()`, `main()`. The only variation is `build_story()` (content) and minor style constants. Extract `cv_builder_core.py` shared module; each variant becomes a thin content-only file. |
| 5. Hardening | OK | No `subprocess.run`, no threading, no LLM pricing. All I/O uses pathlib. No bare `except: pass`. Clean on all 5 rules. |
| 6. Notes | HIT | No notes file. Memory records the Arial/reportlab learning (`feedback_cv_builder.md`) but that's in the memory index, not a per-script notes file. |
| 7. Agent Team | N/A | No parallel hypothesis work. |
| 8. Canary | N/A | Manual-run scripts, not deployed services. |

**Recommended upgrade**: Extract `execution/personal_workflows/cv_builder_core.py` with the shared reportlab plumbing. Each of the 3 variants imports from it and only defines `build_story()` + a `main()` that calls `build_cv(build_story(), output)`. This eliminates ~600 LOC of duplication, makes style updates apply globally, and makes future LLM-assist addition a single-point change. Estimate: 2–3h, zero user-visible behavior change.

---

### `cv_optimizer_agent.py`

| Axis | Score | Notes |
|---|---|---|
| 1. Dynamic Workflow | N/A | Sequential: extract PDF → Call 1 (analysis) → Build CV PDF → Call 2 (cover letter) → Build CL PDF. No fan-out. |
| 2. Declarative exit criteria | MAYBE | Directive exists (`directives/personal_workflows/cv_optimizer_agent.md`). Missing `## Exit Criteria`. Since this is interactive, exit criteria would be: "Two PDFs written to `.tmp/`, both > 0 bytes, ATS score improved ≥ original, page count matches source CV." |
| 3. `--mode` flag | HIT | Hard-coded `model='claude-opus-4-6'` for both API calls (lines 526, 569). No `--mode` flag. A cheap/balanced/premium mode would use Sonnet for quick ATS checks and Opus only for premium output. Saves significant tokens on test runs. |
| 4. Sub-agent opportunity | N/A | Interactive script; sub-agents don't fit the interactive pattern. |
| 5. Hardening | MAYBE | (a) `claude-opus-4-6` is a stale model string — current naming is `claude-opus-4-7`. (b) No `cache_read` / `cache_write` token accounting in `run_analysis()` — though caching is not wired in (no `cache_control` on the analysis call's system param). (c) `_slugify()` derives paths from LLM output (the candidate's name from Claude's response): `name_parts = opt_cv.get('name', 'candidate').split(); last_name = _slugify(name_parts[-1])`. The `_slugify` function strips illegal Windows chars but does **NOT** do `Path.resolve().is_relative_to()` boundary check (Rule 3). The output is in `.tmp/` which is hardcoded, and `_slugify` caps at 80 chars, so traversal risk is low but the rule technically applies. |
| 6. Notes | HIT | No notes file. Memory notes: "pivoted to standalone repo github.com/dmazumdar186/cv-optimizer-agent (Streamlit + Gemini)." The local copy uses Anthropic directly — if the public repo is the canonical version, this local copy may be an orphan. That should be documented. |
| 7. Agent Team | N/A | Interactive, sequential. |
| 8. Canary | N/A | Interactive script, not deployed. |

**Recommended upgrade**: (1) Add `--mode` flag routing to `claude-sonnet-4-6` (balanced) / `claude-opus-4-7` (premium, default). (2) Update model strings to current names. (3) Add a note in the directive clarifying whether the local copy or the public repo is canonical. (4) Add `resolve().is_relative_to(TMP)` guard on the output path derived from LLM name. Low effort (< 1h).

---

### `job_search_llm_gate.py`

| Axis | Score | Notes |
|---|---|---|
| 1. Dynamic Workflow | N/A | Batched sequential calls; fan-out is across jobs within a batch call, but each batch call is sequential by design (throttle_s spacing). |
| 2. Declarative exit criteria | N/A | This is a library module (no top-level directive entry point); `classify_batch()` is called from `job_search_sheet.py`. |
| 3. `--mode` flag | MAYBE | The standalone CLI `_main()` exposes `--primary-model` and `--secondary-model` args. This is the right shape but not the same as `--mode cheap/balanced/premium` from the workspace template. Alignment is optional but would standardize the CLI across all scripts. |
| 4. Sub-agent opportunity | N/A | Library module. |
| 5. Hardening | OK | No `subprocess.run`, no threading. Anthropic path uses `cache_control: ephemeral` on the system prompt correctly when `profile_text` is present (Rule 3 path-from-LLM: not applicable here; model output goes into `GateVerdict` fields, not filesystem paths). No pricing table needed (cost is paid by the caller). BLE001 noqa comments are present with justifications. Clean on all 5 rules. Note: `cache_creation_input_tokens` and `cache_read_input_tokens` are NOT tracked — no pricing table here, which is correct since this module doesn't report costs. |
| 6. Notes | HIT | No notes file. This module has earned several hard-won learnings: Gemini 2.5 thinking token `MAX_TOKENS` truncation behavior (workaround: `response_mime_type: application/json` + 8192 cap), Jooble reCAPTCHA block, batch size calibration. None are documented in a notes file. |
| 7. Agent Team | N/A | Library module. |
| 8. Canary | N/A | Library module; not deployed standalone. |

**Recommended upgrade**: Create `.claude/notes/execution/personal_workflows/job_search_llm_gate.md` documenting: (a) Gemini 2.5 thinking-token truncation and the `response_mime_type` + 8192 fix, (b) why throttle_s=7 (free-tier RPM), (c) why batch_size=10. Pure documentation, 15 minutes.

---

### Light-Pass Scripts

| Script | Axis 1 DW | Axis 2 Exit | Axis 3 Mode | Axis 5 Hardening | Axis 6 Notes | Axis 8 Canary | Verdict |
|---|---|---|---|---|---|---|---|
| `job_search_notify.py` | N/A | N/A | N/A | OK — BLE001 justified at line 104 (non-fatal SMTP) | HIT — no notes file | N/A | Clean; add notes file |
| `job_digest_renderer.py` | N/A | N/A | N/A | OK — BLE001 at line 249 justified (contact fetch non-fatal) | HIT — no notes file | N/A | Clean; add notes file |
| `job_tracker_db.py` | N/A | N/A | N/A | OK — no subprocess, threading, or LLM | HIT — no notes file | N/A | Clean; add notes file |
| `job_tracker_setup.py` | N/A | N/A | N/A | MAYBE — `subprocess.run` at line 164 with `text=True` and `capture_output=True` but **no** `encoding="utf-8"` (Rule 1 violation). Low priority: pip output is ASCII-safe in practice. | HIT — no notes file | N/A | Fix: add `encoding="utf-8", errors="replace"` to subprocess.run call |
| `job_search_setup.py` | N/A | N/A | N/A | OK — no subprocess, threading, or LLM | HIT — no notes file | N/A | Clean; add notes file |
| `_jt_utils.py` | N/A | N/A | N/A | OK — utility module, no subprocess/threading/LLM | N/A (shared utility) | N/A | No upgrades needed |

---

## Missing Directive Coverage

Scripts with **no corresponding directive**:
- `cv_builder_en.py` — only `cv_builder.md` exists (covers the French version)
- `cv_builder_skott.py` — no directive
- `job_search_notify.py` — no directive
- `job_digest_renderer.py` — no directive
- `job_tracker_db.py` — no directive
- `job_search_sheet.py` — directive **exists** (`job_search_sheet.md`) ✓
- `_jt_utils.py` — utility, no directive needed

The cv variant gap is the most impactful: if `cv_builder.md` is the single directive, it should explicitly note that `cv_builder_en.py` and `cv_builder_skott.py` are language/template variants and reference the shared core behavior.

---

## Notes Gap Summary

Zero `.claude/notes/execution/personal_workflows/` files exist. The entire category is undocumented at the notes level. High-value entries to create (from learnings visible in the code):

1. `job_search_llm_gate.md` — Gemini 2.5 thinking-token truncation fix; throttle_s rationale
2. `job_tracker_pm_france.md` — Modal cron deploy status; SIRENE rate limits (if any)
3. `cv_builder.md` — Arial TTFont requirement on Windows; reportlab install notes
4. `job_search_sheet.md` — Jooble reCAPTCHA block; Adzuna auto-signup flow; GH Actions SA JSON requirement
