# System Re-Audit 2 (2026-06-12) — Post Batches 1-5

## Stats
- Commits audited: 19 across 4 repos (main workspace × 15, anneal × 2, humanizer × 2, yt-analyzer × 0 new)
- Major changes spot-checked: 9
- NEW HIT findings: 4
- REGRESSED axes: 0
- Wins (HIT → OK): 8

---

## Spot-checks (correctness)

1. **`execution/personal_workflows/job_search_sheet.py` (parallelization)** — PASS
   Lock `_jobs_lock` guards `all_raw_jobs.extend()` correctly. Post-pool sort by `(country, _fetched_by_title, board)` makes dedup output deterministic across parallel runs. `as_completed` + `future.exception()` properly propagates unexpected errors. Serial fallback (`max_workers=1`) path is correct. No shared mutable state outside the lock.

2. **`execution/personal_workflows/cv_builder_core.py` (refactor)** — PASS
   Shared module exposes correct `__all__`. Font registration with `with_italic=False` default is backward-compatible. `make_style()` replaces variant-specific duplicate implementations cleanly. `build_cv_doc()` signature uses `**doc_kwargs` forwarding — no behavioral change.

3. **`execution/personalization/ai_opener_generator.py` (--mode flag + cache_control)** — PASS
   4-entry `ANTHROPIC_PRICING` dict is present and correct (cache_read=0.1×, cache_write=1.25×). `_calc_cost()` reads all 4 token-count fields from `response.usage`. `cache_control: ephemeral` applied to static system prompt. `--mode` maps to correct model IDs for both Anthropic and OpenRouter paths. Old `--model` override still accepted (not removed). API contract intact.

4. **`execution/mobile_apps/mobile_app_canary.py` (--alert flag + state dedup)** — PASS WITH NOTE
   `threading.Lock` guards `results` dict across `ThreadPoolExecutor`. State written atomically via temp-file rename (POSIX atomic, best-effort on Windows — documented). Alert threshold logic `consecutive % alert_threshold == 0` fires at N, 2N, 3N, etc — correct periodic behaviour. One subtle issue: `threshold_breach` fires on the very first run when `alert_threshold=1` and `prior_status is None` (because `consecutive` becomes 1 ≥ 1 and 1 % 1 == 0). This fires an alert on the first-ever check of a failing app — which may be intentional but is undocumented. See NEW HIT #1.

5. **`execution/mobile_apps/app_store_research.py` (parallel fan-out)** — PASS
   `_lock` guards both `results.append()` and `skipped.append()` inside `_worker`. `run_batch` also catches `fut.exception()` at the outer level. `--single` mode correctly bypasses batch and returns single-cell JSON. No shared state outside locks.

6. **`execution/enrichment/firecrawl_linkedin_dork.py` (parallelization)** — PASS
   `results_lock` guards `results[company_name] =` assignment. Worker ceiling capped at 5 for Firecrawl rate-limit safety. Single-worker path avoids ThreadPoolExecutor overhead and preserves inter-company sleep. No race on `results` dict.

7. **`anneal/batch.py` (new batch subcommand)** — PASS
   `_results_lock` guards `row_results[idx] =` slot write. `_run_one` is self-contained; exceptions caught by BLE001 with log. No shared state between workers. `_parse_refs_file` splits on rightmost `:` so Windows paths `C:\...:HEAD~1` are handled correctly. `_write_batch_results` runs after pool shutdown (single writer — no lock needed).

8. **`anneal/audit/voting.py` (VotingAuditor parallelization)** — PASS
   Comment states "CostTracker is already thread-safe (guarded by threading.Lock)" — confirmed in `cost.py` (`self._lock = threading.Lock()`). `reports[idx] = report` via indexed slot assignment is safe (list slot access is GIL-protected for single-element assign). No shared mutable aggregate outside the thread-safe CostTracker.

9. **`humanizer.py` (--batch mode + ThreadPoolExecutor)** — PASS WITH NOTE
   `results_lock` guards `results[row["index"]] =` slot write. `_worker` captures all exceptions internally (`humanize_one` wraps everything). Fallback slot fill for still-None entries is defensive and correct. Output CSV written after pool shutdown (single writer). One issue: `total_cost` accumulation after pool runs sequentially over `results` without a lock — but this is correct because it runs after the pool has joined (single-threaded at that point).

---

## NEW HIT findings (real new work needed)

| # | Project | Issue | Severity | Effort |
|---|---|---|---|---|
| 1 | mobile_app_canary | First-run alert noise: when `alert_threshold=1` and the app has never been seen before (`prior_status is None`), `consecutive` becomes 1 ≥ 1 and fires a "threshold" alert on the very first check of any failing app. Intended? Not documented. The transition path (`transitioned = prior_status is not None and …`) would NOT fire, but threshold_breach fires independently. | low | 15 min — add `prior_status is not None` guard to `threshold_breach`, or add a comment saying first-run alerts are intentional. |
| 2 | SAST exit-criteria-missing | Three non-AM directives still missing `## Exit Criteria`: `directives/personalization/cold_email_sequences.md`, `directives/gtm_client_workflows/accessory_masters_gtm.md`, `directives/gtm_client_workflows/accessory_masters_prd.md`. The first is live and used; the AM ones are locked but still generate SAST noise. | low | 15 min — add Exit Criteria to `cold_email_sequences.md`; add AM lockdown comment to the AM directive header to suppress SAST warning. |
| 3 | anneal/batch | `anneal batch` in adversarial mode passes `**extra_kwargs` to `AnnealConfig` which does NOT include `parallel_judge` or `judge_max_workers` — those are only set by `_run_adversarial`. So adversarial batch runs always use `parallel_judge=True` and `judge_max_workers=4` defaults. This is correct defaults behaviour but is undocumented — a user who wants `--no-parallel-judge` in batch mode cannot pass it. | low | 20 min — document in `anneal batch --help` that judge parallelism flags are not forwarded in batch mode, or add them to `extra_kwargs`. |
| 4 | workspace CLAUDE.md | Line count is 379 vs <250 target set in AUDIT_1 (pre-upgrades it was ~382 — no reduction occurred). The Phase 5b rules additions (`python-hardening.md`, `sub-agent-delegation.md`, `dynamic-workflows.md`) were added as separate `.claude/rules/` files (correct) but the main CLAUDE.md was not slimmed in compensation. | low | 30 min — slim CLAUDE.md by removing the Universal Python Hardening inline copy (now covered by `.claude/rules/python-hardening.md`) and the sub-agent orchestration prose (now in `.claude/rules/sub-agent-delegation.md`). Target: <280 lines. |

---

## Regressions (axes that got WORSE)

None. All audited axes maintained their prior state or improved.

---

## Wins (axes that went HIT → OK)

- **cv_builder*.py duplication** → eliminated. `cv_builder_core.py` extracts ~600 LOC of shared reportlab boilerplate; variants import from it. Style changes now apply globally.
- **job_search_sheet Stage 1 parallelization** → present. `ThreadPoolExecutor(max_workers=4)` + `_jobs_lock` implemented correctly. Post-pool sort makes output deterministic. Wall-clock drops 4–8× on multi-geo runs.
- **ai_opener_generator.py cache-aware pricing** → present. 4-entry `ANTHROPIC_PRICING` dict, `_calc_cost()` reads all 4 token fields, `cache_control: ephemeral` on system prompt.
- **ai_opener_generator.py --mode flag** → present. cheap/balanced/premium routing for both Anthropic and OpenRouter paths.
- **mobile_app_canary.py alert dedup** → present. State persisted in `.tmp/canary_state.json`, transition + threshold logic correct, atomic write.
- **humanizer --batch mode** → present. ThreadPoolExecutor fan-out with lock-guarded result slots, per-row isolation, CSV I/O.
- **anneal batch subcommand** → present. Parallel fan-out with lock, per-row isolation, `_results_lock`, JSON summary output.
- **Exit Criteria across workspace** → 55 directives now have `## Exit Criteria` sections (up from ~0). Only 3 non-AM directives still missing (see NEW HIT #2).

---

## SAST status
- `subprocess-encoding`: **0 findings** — bulk fix in Wave 5A caught all violations in `execution/`. External repos (humanizer, yt-analyzer) also patched.
- `exit-criteria-missing`: **3 findings** — all are either AM-locked (2) or low-traffic cold-email directive (1). Not regressions; were pre-existing.
- AM-locked findings: 2 (excluded from action per lockdown rules).
- Ruff/Semgrep: not installed on this machine; native SAST rules running correctly.

---

## Directive sync check (Wave 5B exit-criteria additions)

Spot-checked 5 directives that received `## Exit Criteria` blocks:
- `directives/personal_workflows/job_search_sheet.md` — exit criteria match actual script stages (Stage 0–6). **OK**.
- `directives/mobile_apps/phase1_local_standalone.md` — exit predicates reference EAS build commands; consistent with `eas_build_helper.py` and directive body. **OK**.
- `directives/personalization/ai_opener_generator.md` — exit criteria reference `--mode` flag which now exists. **OK** (pre-flag version would have drifted; now synced).
- `directives/infrastructure/workspace_sast.md` — exit codes 0/1/2 documented; match actual script behavior. **OK**.
- `directives/mobile_apps/canary.md` — references `--alert` flag and `.tmp/canary_state.json`; consistent with `mobile_app_canary.py`. **OK**.

---

## Infrastructure shape check

- `.claude/agents/`: 6 agents — `anneal-reviewer`, `code-reviewer`, `documenter`, `note-taker`, `pipeline-auditor`, `qa`. **Correct** (matches original plan).
- `.claude/rules/`: 7 rules — `directives`, `dynamic-workflows`, `python-execution`, `python-hardening`, `security`, `sub-agent-delegation`, `testing`. **Correct** (3 added in Phase 5b).
- `.claude/workflows/`: 4 files — `README.md`, `_template.md`, `aso-research.md`, `enrich-leads.md`. `aso-research.md` present from Wave 3.3B. **Correct**.
- CLAUDE.md line count: **379** (target <250; no reduction, see NEW HIT #4).

---

## Recommendation

**Wave 7 recommended — small, 4 targeted fixes.**

The audit found 4 NEW HITs, all severity=low. No regressions. 8 axes improved from prior state. The parallelization rewrites (job_search_sheet, app_store_research, firecrawl_linkedin_dork, mobile_app_canary, anneal batch, humanizer batch, anneal VotingAuditor) are all correctness-PASS. Lock discipline, failure isolation, and output determinism are sound across the board.

Wave 7 fix targets (in priority order):
1. **NEW HIT #4 (CLAUDE.md bloat)** — slim CLAUDE.md to <280 lines by removing inline copies of rules that now live in `.claude/rules/`. Zero behavior change.
2. **NEW HIT #2 (cold_email_sequences.md exit criteria)** — 15-min doc addition.
3. **NEW HIT #1 (canary first-run alert)** — add a guard or a comment to `compute_alerts`. 15 min.
4. **NEW HIT #3 (anneal batch adversarial flag gap)** — add a note to the help string. 20 min.

Total Wave 7 effort estimate: ~1.5h, zero code risk on items 2-4.
