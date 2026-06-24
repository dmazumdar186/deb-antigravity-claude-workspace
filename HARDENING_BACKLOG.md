# Hardening Backlog — 2026-06-15

## Update 2026-06-24 — Output-acceptance-gate rule backport triage

New always-active rule landed: `~/.claude/rules/output-acceptance-gate.md` (every user-facing artifact needs an unskippable, hard-failing, corpus-backed gate that asserts on the OUTPUT a user reads, not on mechanics). Born from job_search_v2 shipping cybersecurity/accounting/SEO rows into a PM sheet while "verified" checks (row counts, exit codes) passed. Per `rule-backport-cadence.md`, a read-only triage was run within the hour. Mechanical guardrail added: `workspace_sast.py` rule `acceptance-gate-missing` (registry-driven presence check).

**Triage scope:** the 5 artifact-producing projects in `_ACCEPTANCE_GATE_PROJECTS`. Each assessed for a hard-failing, unskippable, corpus-backed output-acceptance gate.

| Project | Has gate? | Hard-fail? | Unskippable (wired to run)? | Frozen corpus? | Grade |
|---|---|---|---|---|---|
| job_search_v2 | YES (`acceptance_job_search_v2.py`) | YES (exit 1/3) | YES (run.py Stage 5b) | YES (19 reject + 12 keep) | **DONE (1/5 days)** |
| cv_optimizer | NO | — | — | — | **OWED** |
| humanizer | NO (has lang-guard + e2e, not an output-acceptance gate) | — | — | — | **OWED** |
| youtube_video_analyzer | NO | — | — | — | **OWED** |
| job_tracker_pm_france | NO | — | — | — | **OWED** |

**Aggregate:** 1 of 5 compliant. SAST `acceptance-gate-missing` flags the other 4 (info-severity) on every scan until closed.

### Owed-work (priority by user-facing leverage; NO fixes applied without operator approval)

1. **cv_optimizer** (~1.5h, high leverage — career artifact). Output-acceptance gate: given a CV+JD, assert the generated CV/cover-letter is (a) in the JD's language, (b) ATS-score ≥ baseline+10, (c) no placeholder/`[INSÉRER]`/TODO tokens, (d) no language-switched bullets. Frozen corpus: 1 known-good + 1 known-bad CV/JD pair. Aligns with `eval-first.md` Exhibit A (the 9/9-PASS-but-2/8-real incident).
2. **humanizer** (~1h). Gate: given AI text + voice profile, assert output (a) passes the AI-tell detectors it claims to strip, (b) stays in the source language, (c) preserves meaning (length within band). Corpus: 1 robotic input that MUST be de-tell'd, 1 already-human input that MUST pass through ~unchanged.
3. **youtube_video_analyzer** (~1h). Gate: given a known fixture video, assert the breakdown has non-empty hook/scenes/transcript-highlights and N≥threshold real scene cuts (not 1 giant scene). Corpus: 1 known multi-cut video.
4. **job_tracker_pm_france** (~45m). Overlaps job_search_v2; may be retired in favour of v2. Confirm status before building a gate (don't gate a deprecated pipeline).

---

## Update 2026-06-16 — Panel-pass rule backport triage

New always-active rule landed: `~/.claude/rules/panel-pass.md` (4-lens "would Karpathy / Cherny / Amodei / Anthropic research team leave satisfied?" rigor floor before declaring work done). Per `rule-backport-cadence.md`, a read-only backport triage was run within 24 hours of the rule landing.

**Triage scope:** 5 active project wrap-ups assessed against the 4 lenses (Karpathy=empirical, Cherny=dogfood, Amodei=deployment, Honest-gaps).

| Project | Karpathy | Cherny | Amodei | Honest gaps | Overall |
|---|---|---|---|---|---|
| anneal v0.1 | WARN | PASS | PASS | FAIL | FAIL |
| cv_optimizer_v2 | WARN | WARN | WARN | FAIL | FAIL |
| job_search_v2 | FAIL | WARN | WARN | FAIL | FAIL |
| mobile_apps (preflight) | PASS | PASS | INSUFFICIENT | INSUFFICIENT | WARN |
| anthropic_watch | PASS | INSUFFICIENT | INSUFFICIENT | WARN | WARN |

**Aggregate:** 0 of 5 projects fully pass the 4-lens panel-pass. Most common failing lens: **Honest gaps** (4/5 projects declare features done without explicitly surfacing what remains). Second most common: **Karpathy / measurement** (3/5 lack real empirical validation).

### Top 3 owed-work items (priority by leverage)

1. **`job_search_v2` live cutover gate** (~2h, daily-driver impact). Run front-door synthetic 5 consecutive days on live sources; measure per-source counts + dedup accuracy; cut GitHub Actions cron to v2. Currently "PROBATIONARY" in directive but the probation has not started.
2. **`anneal` real-LLM loop-with-memory benchmark** (~1.5h, validates this turn's anneal shipping). Execute against planted-bug + SWE-Bench Lite; record rounds-to-convergence delta, oscillation rates, cost per round. Update anneal `CHANGELOG.md` with results. Recipe in `C:/Users/deban/dev/anneal/HANDOFF.md` §5.
3. **`cv_optimizer_v2` end-to-end dogfood** (~1h, blocks user adoption confidence). Verify `WORKER_SECRET` provisioning; run full CVSpec synthetic on a real WTTJ URL; print output to PDF and inspect. Add a rubric (e.g., "ATS score ≥10pt increase") to satisfy Karpathy lens.

### Per-project owed-work detail

**anneal** — (a) full-pipeline canary with `--audit-samples 3 --vote-threshold 2`, (b) loop-with-memory benchmark execution per HANDOFF §5, (c) loop_adversarial determinism patch if reproducible replays needed.

**cv_optimizer_v2** — (a) `WORKER_SECRET` in `.env` + full CVSpec synthetic, (b) curl pages-url + inspect PDF on real WTTJ URL, (c) quality rubric + sample-of-3 ATS-score comparison.

**job_search_v2** — (a) 5-consecutive-day live front-door synthetic, (b) cron cutover to v2 in `.github/workflows/job_search_daily.yml`, (c) 7-day dedup accuracy verification from `seen.db`.

**mobile_apps preflight** — (a) run `py execution/mobile_apps/preflight.py --json` and include current-state snapshot in directive or new `STATUS.md`.

**anthropic_watch** — (a) live run (not `--dry-run`) verifying Fable 5 oracle entry appears in digest, (b) cron wiring via `/schedule` command.

### Mechanical guardrail (per rule-backport-cadence)

Panel-pass is meta and hard to grep for. Primary enforcement is at model-write-time (the discipline of running the 4 lenses before saying "done"). Partial guardrail: the forbidden-framings list in `panel-pass.md` (`"we're done"`, `"all set"`, `"100% complete"`, etc.) is regex-anchorable. A future workspace-SAST extension could scan session transcripts at finalize time and flag forbidden-framing matches that lack a preceding "Honest gaps" block. **Not implemented this turn — logged as low-priority workspace-tooling item.**

---

## Update 2026-06-15 evening (session 3 — landings)

Three parallel hardenings landed today + one mobile skeleton. Pytest gate after the work: **1018 passed, 53 skipped, 0 failed** (up from 992).

- **Row 4 (cv_optimizer_v2 Worker)** — Keep + harden chosen. Two pieces:
  - POST `/api/optimize` front-door synthetic at `tests/test_cv_optimizer_v2_front_door_optimize.py` (4 tests, gated by `CV_OPTIMIZE_LIVE=1`; bad-secret rejection live-verified; authenticated tests skip until `WORKER_SECRET` lands in workspace `.env`).
  - Per-field language validator at `worker/src/lang_validator.ts` covering `summary`/`summary_kpis`/`experience.role`/`bullets[]`/`projects[]`/`recommendations[]`. Stopword-frequency heuristic, no extra dep. Retry-once on mismatch. 36/36 Worker unit tests passing. **NOT yet deployed** — operator approves separately.
- **Row 28 (mobile_apps)** — first registered app: `demo-app-001`. Skeleton scaffolded at `C:\Users\deban\dev\mobile-apps\demo-app-001\` via `bootstrap_mobile_app.py`. Per-app front-door stub at `tests/front_door.py` reports PARTIAL (3 PASS — source integrity, tsc, registry entry; 1 SKIP — deployed health, phase-4 gated). Preflight RED — operator-owned blockers: `eas login`, `pip install modal`, 7 mobile env keys, `APPLE_ENROLLMENT_STATUS`.
- **Row 30 (remotion_bootstrap)** — render wrapper at `execution/video/remotion_render.py` (CLI + auto-composition-detect from Root.tsx). 26 unit tests + 1 E2E (gated by `REMOTION_LIVE=1`). Directive `directives/video/remotion_render.md` updated. The "render wrapper deferred to v1.1" item from `project_remotion.md` is closed.
- **Row 31 (remotion_template_overlay)** — `tsc --noEmit` gate already landed in prior session (per memory). No-op this session.

---

## Update 2026-06-15 evening (session 3 — verified state)

- **Haiku-4.5 rows (1, 2, 3) are STALE.** Verified all three:
  - `execution/personalization/ai_opener_generator.py:43-52` — `cheap` already maps to `claude-sonnet-4.6`. Haiku entry remains only in the pricing dict (lines 60-65) with an explicit comment that it's kept for legacy AM cost-lookups on frozen records — does not violate the ban.
  - `execution/personalization/variant_generator.py:41-47` — `cheap` already maps to `claude-sonnet-4.6`.
  - `directives/personal_workflows/job_search_sheet.md:195` — already "Claude Sonnet 4.6 (user's Anthropic Max plan)".
  - Banner from morning was authored against an older tree.
- **Row 4 (cv_optimizer_v2 fate)** — operator decision: **Keep + harden.** Worker stays the canonical CV path. Live at `https://cv-optimizer.pages.dev` / `https://cv-optimizer-api.debanjan186.workers.dev`. Provider is Gemini 2.5 Flash (free tier, ~50 calls/year). Session-3 work: POST `/api/optimize` synthetic + per-field langdetect on CVSpec output.
- **Row 5 (cv_optimizer_agent.py)** — already deleted in prior session per morning banner. Row is moot.

## Update 2026-06-15 (morning, operator scope decisions)

- **Sundowned (deleted from tree, history preserved in git)**:
  - `execution/personal_workflows/cv_optimizer_agent.py` (Streamlit + Gemini prototype). The Cloudflare Worker at `execution/personal_workflows/cv_optimizer_v2/` is the canonical CV path going forward. The local CLI at `execution/personal_workflows/cv_optimizer_local/` is operator-personal and remains as a fallback but is not the focus of future CV work.
  - `execution/content/wedding_card_generator.py` (one-time artifact; event date 2026-05-07 is past).
  - `execution/infrastructure/setup_telegram_webhook.py` (AM-coupled; AM is frozen, this script will never be re-run from this workspace).
- **In active hardening focus** (operator-stated near-term priorities): video projects (`youtube_video_analyzer`, `remotion_*`) and the mobile apps scaffolder (`mobile_apps/`).
- **Hardened this session** (per-project commits already on `origin/main`): `workspace_sast`, `anthropic_watch`, `gmail_send_digest`, `google_sheets_writer`, `job_tracker_db` (country-aware key + migration), `humanizer` (langdetect guard), `cv_builder` (3 variants render + skott `make_style` kwarg fix), `custom_scrapers` (8 files + adzuna `_parse_posted_at` fix).

---


Workspace-wide triage of every active project against the four always-active rules: **eval-first**, **front-door-synthetic**, **model-tier** (Haiku 4.5 banned; free-tier-as-production flagged), and the matching **DoD template** (`~/.claude/templates/dod-{llm-ui,cold-email,cron-pipeline}.md`).

Source: 11 read-only Explore agents fanned out across `execution/{category}/` on 2026-06-15. Per-category raw reports are summarized below; this file is the decision deliverable.

**Operator: read this before approving any fixes.** Nothing in this file has been changed yet. Items are sorted by leverage (worst grade × lowest effort first). Cells use `Y` / `N` / `P` (partial) / `?` (UNKNOWN) / `—` (N/A).

---

## TL;DR — what to fix first

1. **Three Haiku-4.5 violations** (banned per `model-tier.md`). All trivial: change one model id. Fix today.
   - `execution/personal_workflows/job_search_sheet.py` (directive line 195: "Primary: Claude Haiku 4.5")
   - `execution/personalization/ai_opener_generator.py:42,47` (`MODE_TO_MODEL_OPENROUTER["cheap"] = anthropic/claude-haiku-4.5`)
   - `execution/personalization/variant_generator.py:40` (same pattern)
2. **CV Optimizer v2 (Worker)** — deprecated to demo-only per yesterday's pivot. Decision needed: retire / banner / rebuild. (See gap #4 in handoff.)
3. **Custom scrapers** (7 of 8) — no eval, no front-door synthetic, brittle regex. ~17h to harden the whole category; do as one batch.
4. **Cold-email enrichment** (anymailfinder, million_verifier) — no output schema validator; 5h fix unblocks a class of silent-corruption bugs.

Estimated total effort for everything below: **~95–125 hours**. AM-frozen items account for ~25 grade rows and are skipped (`lock-as-frozen`).

---

## Master backlog (sorted by leverage)

Leverage rank = (severity of worst gap) × (1 / effort). Top of list = biggest win per hour.

| Rank | Project | Grade (E/F/M/DoD) | Top gap | Action | Effort (h) |
|---:|---|---|---|---|---:|
| 1 | `personalization/ai_opener_generator.py` | N / N / **FAIL** / cold-email | Haiku 4.5 (banned) line 42,47 | small-fix: swap → Sonnet 4.6; add `--mode` flag | 4–6 |
| 2 | `personalization/variant_generator.py` | P / — / **FAIL** / cron-pipeline | Haiku 4.5 (banned) line 40 | small-fix: swap → Sonnet 4.6; add HANDOFF note (internal tooling, front-door waived) | 3–4 |
| 3 | `personal_workflows/job_search_sheet.py` | N / N / **FAIL** / cron-pipeline | Haiku 4.5 (banned) directive line 195; silent fallback on parse error | small-fix: swap → Sonnet 4.6; add JSON-output validator + langdetect | 8–24 |
| 4 | `personal_workflows/cv_optimizer_v2/` | N / Y / **FAIL** / llm-ui | No per-field validators; free-tier-as-production with no quota gate; URL still public | **operator-decide**: retire (delete project) / banner ("demo only") / rebuild | 0 (retire) – 24 (rebuild) |
| 5 | `personal_workflows/cv_optimizer_agent.py` | Y / N / FAIL / llm-ui | No front-door synthetic; older Streamlit + Gemini path; CL has no langdetect | **operator-decide**: superseded by `cv_optimizer_local/`, candidate for retire | 0 (retire) – 8 (revive) |
| 6 | `enrichment/anymailfinder_lookup.py` | N / N / PASS / cold-email | No output schema validator; null `owner_email` can pass through | small-fix: post-enrich schema assert + `tests/test_anymailfinder_lookup_e2e.py` | 2–3 |
| 7 | `enrichment/million_verifier.py` | N / N / PASS / cold-email | Same: no schema enum check on `email_verification_result` | small-fix: assert enum + score range + E2E with mock | 2–2.5 |
| 8 | `personal_workflows/anthropic_watch/` | N / N / PASS / cron-pipeline | Tagging-heuristic untested; Firecrawl single-429 kills the source | small-fix: heuristic unit tests + 3× retry+jitter on fetch | 2–8 |
| 9 | `content/humanizer` | N / Y | PASS / llm-ui | Front-door uses `--dry-run` mock; never tests live multi-provider path; no per-field langdetect on humanized text | small-fix: rotate-providers test + langdetect post-LLM | 6–8 |
| 10 | `infrastructure/setup_instantly_webhook.py` | N / N / — / none | No tests; secret + webhook flow tested manually only | small-fix: mocked unit tests + idempotency reverify | 2–3 |
| 11 | `infrastructure/setup_telegram_webhook.py` | N / N / — / none | Same | small-fix: mocked tests + post-setup `getWebhookInfo` assert | 2–3 |
| 12 | `infrastructure/workspace_sast.py` | Y / — / PASS / none | No regression tests on `--rules` modes; AM-skip path untested | small-fix: fixture-driven `--rules` unit tests | 3–4 |
| 13 | `custom_scrapers/apec_jobs.py` | N / N / PASS / none | No field-validation pytest; brittle regex | small-fix: schema + fixture front-door | 2 |
| 14 | `custom_scrapers/france_travail_jobs.py` | N / N / PASS / none | Date parsing + thread-safety on `_token_cache` (rule #2 violation) | small-fix: lock + ISO test + mock front-door | 3 |
| 15 | `custom_scrapers/indeed_jobs.py` | N / N / PASS / none | `_is_blocked()` boundary untested; stealth fallback never executed | small-fix: boundary tests + stealth mock | 2.5 |
| 16 | `custom_scrapers/google_jobs_serper.py` | N / N / PASS / none | French date variants unhandled silently; wall-clock flakiness | small-fix: param tests + `freezegun` | 3 |
| 17 | `custom_scrapers/wttj_jobs.py` | N / N / PASS / none | Company-name heuristic brittle (may pick contract type) | small-fix: fixture for contract-line-before-company | 2 |
| 18 | `custom_scrapers/adzuna_jobs.py` | N / N / PASS / none | FR contract-type fallback + 429 path untested | small-fix: tests for both | 2.5 |
| 19 | `custom_scrapers/jooble_jobs.py` | N / N / PASS / none | 401 path + contract mapping untested | small-fix: tests for both | 2.5 |
| 20 | `custom_scrapers/job_filter.py` | Y / P / PASS / none | Eval-first met; edge cases on langdetect (empty/1-word) | verify-only: optional edge tests | 1 |
| 21 | `personal_workflows/cv_builder.py` + 3 variants | — / N / PASS / none | No CLI front-door; no per-locale golden render | small-fix: render-once+grep fixture | 2–8 |
| 22 | `lead_sourcing/serper_maps_scraper.py` | N / N / ? / none | No schema validation; no CLI fixture test | small-fix: mock + schema | 3–4 |
| 23 | `lead_sourcing/prospeo_leads.py` | N / N / ? / none | No email-format validation; no front-door | small-fix: mock + schema | 3–4 |
| 24 | `lead_sourcing/sirene_company_lookup.py` | P / N / — / none | NAF classification untested; OAuth2 fallback silent | small-fix: param tests + OAuth2 mock | 4–5 |
| 25 | `google/gmail_send_digest.py` | Y / Y / PASS / none | Plain-text fallback regex naive; single retry only | small-fix: HTML2Text + tenacity | 3–4 |
| 26 | `google/google_sheets_writer.py` | Y / P / PASS / cron-pipeline | No CI synthetic against real test sheet; clear+update race | small-fix: CI smoke + batched update | 6–8 |
| 27 | `enrichment/firecrawl_linkedin_dork.py` | Y / Y / PASS / llm-ui | API-key-absent silently returns `[]`; title parsing regression-untested | verify-only: mock E2E + raise on missing key in non-mock mode | 2 |
| 28 | `mobile_apps/<skill + 7 scripts>` | mixed | Preflight has no machine-readable exit; security audit prompt-only; no per-app front-door | small-fix per script (`preflight.py`, structured findings JSON, app-level e2e) | 8–12 |
| 29 | `video/youtube_video_analyzer.py` | Y / Y / ? / none | Distillation cost untracked; transcript 429 no backoff | small-fix: backoff + cost log | 2–3 |
| 30 | `video/remotion_bootstrap.py` | Y / P / — / none | No E2E render test; partial-failure rollback missing | small-fix: rollback try/finally + smoke-test in CI | 3–4 |
| 31 | `video/remotion_template_overlay/` | Y / N / — / none | No tsc check post-overlay | small-fix: `tsc --noEmit` gate | 2–3 |
| 32 | `content/rosy_origami/` | N / P (mocked) / PASS / cold-email | No langdetect per section (fr/en mix in GIO); no golden HTML diff; Tavily 429 silently drops section | small-fix while still in Phase 0 — cheaper now than later | 8–10 |
| 33 | `personal_workflows/cv_optimizer_local/` | Y / Y / PASS / llm-ui | Synthetic ran 5× this morning but no golden-baseline visual diff yet; Playwright no retry | verify-only: pin baseline + retry wrapper | 0–2 |
| 34 | `personal_workflows/job_tracker_pm_france.py` | Y / Y / — / cron-pipeline | Fixture files in `tests/fixtures/raw_*` not confirmed-present per board; cache-key collides on cross-country same-name | verify-only: assert fixtures exist + cache-key includes country | 0–2 |
| 35 | `personal_workflows/remote_control_mobile/` | — / N / — / none | Layer 3 (`launch.ps1` → real `claude --remote-control` → phone) never end-to-end tested | **operator-action**: manually double-click shortcut, confirm URL + phone connect | 0–2 |
| 36 | `content/wedding_card_generator.py` | N / N / — / none | One-off; hardcoded names; event date 2026-05-07 is in the past | **retire-or-archive** (move out of active execution/) | 0–2 |
| 37 | `personal_workflows/cv_optimizer_v2/` Worker (revisited at retire-time) | — | demo URL still alive after retire decision: ensure no synthetic claims it's "ready" | follow-up of row 4 | included above |

### FROZEN — locked by `CLAUDE.local.md` (action: `lock-as-frozen`, effort: 0)

These were inspected for path-membership only. **No grading performed, no edits, no API calls.** Listed for completeness so the backlog matches the workspace inventory.

- `execution/gtm_client_workflows/` — all three scripts (`accessory_masters_pipeline.py`, `generate_qa_test_plan.py`, `import_leads.py`) are AM-coupled. Plus the directive `_baseline_worker_checklist.md` and `import_leads.md` (default config → AM).
- `execution/infrastructure/api-proxy/` — explicitly locked.
- `directives/personalization/cold_email_sequences.md` — AM-coupled.
- `directives/personal_workflows/self_outbound_system.md` — external repo (`github.com/dmazumdar186/outbound-engine`), AM-style infrastructure.

### Out of workspace (skipped here; need their own pass elsewhere)

- `github.com/dmazumdar186/cv-optimizer-agent` (Streamlit + Gemini)
- `github.com/dmazumdar186/humanizer`
- `github.com/dmazumdar186/youtube-video-analyzer`
- `C:\Users\deban\dev\anneal\`
- `C:\Users\deban\dev\mobile-apps\{slug}\` — each app (registry currently empty)

---

## Cross-cutting patterns surfaced by the triage

Three recurring failure modes across the workspace. These are bigger than any single project and inform how to spend the next few hardening sessions.

### Pattern A — "tested layers ≠ system works"

Half the projects have unit tests with mocked LLM/API providers and call themselves tested. Per `front-door-synthetic.md`, mocked tests don't count. The category-wide fix isn't more tests; it's a `tests/front_door.{sh,py}` per project that enters through the same door a user would, and a workspace-wide expectation that no project is `ready` until its `front_door` passes 5/5.

### Pattern B — "Haiku 4.5 keeps re-appearing"

Three independent files reference Haiku 4.5 today (rows 1–3 above). The ban was added on 2026-06-14 and hasn't been backported. Until the SAST grep is updated, more will sneak in.

**Proposed workspace guardrail**: add a `claude-haiku` grep rule to `execution/infrastructure/workspace_sast.py` so the workspace gates on Haiku presence going forward. ~30 min. Listed below in "Lessons & guardrails."

### Pattern C — free-tier API treated as production

`cv_optimizer_v2` (Gemini), `anthropic_watch` (Firecrawl), `rosy_origami` (Tavily), `job_tracker_pm_france` (multiple) all depend on free-tier APIs without an explicit quota-gate visible in the code. When the quota exhausts, behavior is "degrade silently" or "throw 502" — neither acceptable.

**Proposed workspace guardrail**: every directive that names a free-tier upstream must include an `## Upstream quotas` section with the quota limit + the gate behavior (queue / abort / fail-open). Audit task post-triage. Listed below.

---

## Recommended sequencing (if operator green-lights all)

**Day 1 (~1 hour)**: Rows 1–3 (the three Haiku bans). All small, all the same change, all critical. Land in one commit.

**Day 2 (~6 hours)**: Rows 6, 7, 10, 11, 13–19 (cold-email enrichment + custom scrapers). One commit per scraper to keep agent budgets safe per `~/.claude/CLAUDE.md` sub-agent rules.

**Day 3 (~6 hours)**: Row 4 decision + execution (retire cv_optimizer_v2 / banner / rebuild). Operator picks.

**Day 4+**: Everything else, prioritized by operator.

---

## What this backlog does NOT cover

Per the front-door-synthetic rule, none of the rows above are marked "passing" — they're marked as graded. The "PASS" cells in the model-tier column are about **the rule** (no Haiku, no free-tier-as-prod-without-gate), not about whether the project itself works. A project can pass model-tier and still be broken (see row 4).

Also not covered:
- Anything outside `execution/` (e.g. `.claude/skills/*`, `modules/`, scripts that are imports-only).
- The 5 empty execution categories (`crm_and_pm`, `gtm_icp_filters`, `image_generation`, `n8n_workflows`, `rag`) — confirmed empty in directives too, except `subagent/` which has 2 internal-workspace directives (note_taker, documenter) that don't need this kind of grading.

---

## Next action — operator decision

Before any of the above gets touched, I need three answers:

1. **Worker retirement (row 4)**: retire / banner / rebuild? (Recommendation: retire, since the local CLI is now the production path.)
2. **`cv_optimizer_agent.py` (row 5)**: retire or keep? It was an earlier Streamlit/Gemini prototype superseded by `cv_optimizer_local/`.
3. **Sequencing**: green-light Day 1 (the three Haiku swaps) now? It's <1 hour total and unblocks the model-tier rule across the workspace.

---

## Update 2026-06-18 — Prior-art-first backport triage

New always-active rule landed earlier today: `~/.claude/rules/prior-art-first.md`. Before writing any code that fetches data from / scrapes / integrates with an external service, do a 10-minute prior-art pass (DevTools Network tab + GitHub search for "$service python") and report a synthesis paragraph to the operator before touching a directive or a script.

Per `~/.claude/rules/rule-backport-cadence.md`, a read-only triage of every existing source/scraper/enricher module was run within 24 hours of the rule landing. Findings below.

### Scope

- `execution/personal_workflows/job_search_v2/sources/` — 9 source adapters
- `execution/modules/scrapers/` — empty (.gitkeep only)
- `execution/modules/sources/` — empty (.gitkeep only)
- `execution/modules/enrichers/` — empty (.gitkeep only)

The modules/ folders being empty is itself a signal: the workspace's reusable scraper/source/enricher tier is unbuilt. Out-of-scope for this triage.

### Findings (source adapters)

| File | Service | Mechanism | Risk | Why |
|---|---|---|---|---|
| linkedin_gmail.py | LinkedIn | gmail_alert_imap | HIGH (already deprecated) | Replaced by linkedin_guest_api.py 2026-06-18. Kept as opt-in belt-and-suspenders. |
| wttj.py | WTTJ | playwright_browser | HIGH (already deprecated) | Replaced by wttj_algolia.py 2026-06-18. Kept for fixture-only parser test. |
| indeed_gmail.py | Indeed | gmail_alert_imap | **HIGH (rewrite candidate)** | Indeed has RSS feeds + a public job API. Same Gmail-IMAP anti-pattern as the deprecated linkedin_gmail. |
| hellowork_gmail.py | Hellowork | gmail_alert_imap | **HIGH (rewrite candidate)** | Hellowork likely has a GraphQL endpoint (~2-3h reverse-engineering on GitHub). |
| jobgether_gmail.py | Jobgether | gmail_alert_imap | **MEDIUM (audit first)** | Small service; public API existence unknown. Needs a 10-min GitHub audit before deciding rewrite vs deprecate. |
| apec.py | APEC | playwright_browser + css_html_scrape | MEDIUM (Playwright fragile) | Didomi consent gate blocks headless. APEC may have a partner/Pole-Emploi-style API. Investigate. |
| france_travail.py | France Travail | oauth_api | LOW | Official government REST API. Best practice already. |
| linkedin_guest_api.py | LinkedIn | public_api | LOW | Unauthenticated jobs-guest API. Best practice (and the textbook exhibit for this rule). |
| wttj_algolia.py | WTTJ | public_api | LOW | Public Algolia backend (referer-gated public credentials). Best practice. |

### Top rewrite candidates by leverage

1. **indeed_gmail.py → indeed_rss.py** (HIGH impact, MEDIUM effort). Indeed offers an RSS feed per saved search and an XML job-detail surface. ~3h work, eliminates a Gmail label + filter + brittle email parser. Adds a 5th LIVE-VERIFIED source.

2. **linkedin_gmail.py → fully deprecate** (HIGH impact, LOW effort). Replacement (`linkedin_guest_api.py`) already exists + is now the primary LinkedIn signal. Confirm no orchestrator path still depends on Gmail, then remove from `_DISPATCH`. ~15 min.

3. **apec.py → apec_api.py** (MEDIUM impact, MEDIUM-HIGH effort). APEC is a major FR PM source. The Didomi gate is a known anti-pattern that a backend-API path solves. Worth a 30-min DevTools audit before committing time.

4. **hellowork_gmail.py → hellowork_graphql.py** (MEDIUM impact, MEDIUM effort). Hellowork's SPA likely has a discoverable GraphQL endpoint.

5. **jobgether_gmail.py → ?** (LOW-MEDIUM impact). Small service; do the prior-art-first audit first, then decide: rewrite if public API exists, deprecate if not.

### Mechanical guardrails (SAST grep) — owed

Per `~/.claude/rules/rule-backport-cadence.md`, a mechanical guardrail is required:

- [ ] Workspace SAST scanner (`execution/infrastructure/workspace_sast.py` or equivalent) gets a `re.compile(r"copy\.(copy|deepcopy)\(\s*os\.environ\s*\)")` check (for the 2026-06-15 environ-not-copy-copy rule).
- [ ] Same scanner gets a presence check: every directive that adds a new source/scraper module (`execution/{category}/sources/*.py` or `execution/modules/scrapers/*.py`) must have a `## Prior art pass` section in its paired directive. Flag missing ones at directive-creation time.

These are added in the same commit as this HARDENING_BACKLOG update.

### Why the rule was needed

The 5 HIGH RISK files represent ~12 hours of engineering lost to building workarounds for problems that didn't exist:
- linkedin_gmail.py (~6h Gmail IMAP + alert subscription + filter + parser drift detection): LinkedIn has had a public unauthenticated jobs-guest API for years. 30 seconds of GitHub search would have found it.
- wttj.py (~4h Playwright + Didomi consent + __NEXT_DATA__ debugging): WTTJ's search box has always been a client-side Algolia call. 30 seconds of DevTools Network tab would have shown the request.
- 3 still-HIGH files (indeed/hellowork/jobgether Gmail-IMAP, ~6h combined): same anti-pattern, not yet rewritten.

Going forward, the prior-art-first rule and its 10-minute pass are the floor. The rewrites above are the backport — they make the workspace's existing code consistent with the new rule, not just new code.


---

## Update 2026-06-19 — Two operator-reported bugs + fixes

Operator-reported on 2026-06-19: "it is sending me around 200 jobs, and then it is sending emails twice daily, why is such a simple tool not working correctly?"

### Bug 1: Ranker silently disabled in production CI — 200+ jobs per email

**Root cause:** `GEMINI_API_KEY` IS present in GitHub Secrets (set 2026-06-09) but the `.github/workflows/job_search_daily.yml` env block does NOT pass it through to the orchestrator step. The ranker code reads `os.environ.get("GEMINI_API_KEY", "")`, finds empty, emits B-tier placeholders for every job, no filtering happens, all ~200 jobs end up in the digest.

**Autonomous code-level fix (this commit):**
- Add `--max-digest-jobs N` (default 25) to `run.py`. After dedup + location filter, sort by `(-ranker_score, -posted_at)` and slice top N for sheet append + email digest. Excess jobs STILL get recorded in seen.db so they don't re-surface tomorrow. UX-grade output cap; reverts via `--max-digest-jobs 999`.
- Sort key uses ranker score IF the ranker ran. Until the YAML is fixed, all scores are 0.5 (placeholder) so sort falls through to `-posted_at` (most-recent-first).

**Workflow YAML owed-fix (blocked on PAT scope):**
```yaml
      - name: Run job_search_v2 orchestrator
        env:
          # ...existing entries...
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}  # <- ADD THIS LINE
```
After this YAML edit, the ranker activates, jobs get real A/B/C/SKIP tiers, the cap drops the bottom-tier noise. To apply: operator runs `gh auth refresh -s workflow` (one-time interactive browser flow), then pushes a 1-line YAML diff. Owed-by: ASAP.

### Bug 2: Dual-cron at 07:00 + 08:00 UTC sends two emails per day

**Root cause:** `.github/workflows/job_search_daily.yml` has two cron triggers (`"0 7 * * *"` and `"0 8 * * *"`) — a DST workaround so the cron lands at 09:00 Paris year-round. `send_digest` has no idempotency check, so it sends every time.

**Autonomous code-level fix (this commit):**
- Add `--min-hours-between-emails N` (default 22.0) to `run.py`. Before send, check the lock state. If last send was within N hours, skip + log "email lock: last send was Xh ago — skipping to prevent dual-cron spam." `--dry-run` bypasses the lock and doesn't stamp it, so manual workflow_dispatch tests don't clobber production state.
- Lock state lives in `seen.db` meta KV table (NEW `meta` table added by `dedup.py`). This piggy-backs on the existing seen.db cache step in the workflow YAML — survives between cron invocations without needing a new cache path. Autonomous because the YAML doesn't need to change.

**Edge cases handled:**
- Disabled when threshold ≤ 0 (escape hatch).
- Corrupt state value → treat as no prior send (better to send than silently skip — visible failure).
- Missing seen.db → treat as no prior send.

### Bug 3 owed-work (operator decision)

Even with the cap + ranker, "150 jobs filtered down to 25" assumes the ranker correctly tiers PM-Paris-fit. The rubric at `execution/personal_workflows/job_search_v2/ranker/rubric.md` was tuned for the operator's profile. If it under-filters (still too many B's), tightening options:
- Drop cap to 15 by default
- Increase `--min-score-to-keep` threshold (default 0.0 today)
- Add a tier filter (e.g. `--digest-tiers A,B` to ship only A's)

This is a quality-calibration task that needs 1-week of dogfood data — not blocking the current shippability question.


---

## Update 2026-06-22 — GLM 5.2 integration sensitivity guardrail

New always-active addition to `~/.claude/rules/model-tier.md` (Exhibit C): GLM 5.2 is permitted for creative/non-sensitive content only — never PII, CV/recruiter content, cold-email leads, AM-scoped data, or client/customer data. The guardrail is policy-only today.

### Owed mechanical guardrail

Add a SAST grep in `execution/infrastructure/workspace_sast.py` (or wherever the workspace scanner lives) that flags Python files matching BOTH conditions in the same function:

- `chat_completion(...model="z-ai/...")` OR `chat_completion(...model=resolve_model("openrouter", "glm")...)`
- AND PII keyword tokens nearby: `email`, `recipient`, `lead`, `candidate`, `cv`, `resume`, `cover_letter`, `phone`, `address`, `client`, `customer`

Trigger: at least one match for the GLM call AND at least one PII keyword in the same function body. Output: list each callsite with file:line and the PII keyword that triggered.

### Owed read-only backport triage

Per `~/.claude/rules/rule-backport-cadence.md`, within 24 hours of the rule landing (2026-06-22): run the grep above against the workspace, write findings here. Likely audit-clean today since GLM 5.2 has just been added — but if any pre-existing module already passes user input to `model="z-ai/..."` without sanitization, surface it.

### Revert path

If GLM 5.2 needs to be backed out entirely:
1. `mv ~/.claude/rules/model-tier.md.bak-2026-06-20 ~/.claude/rules/model-tier.md`
2. Revert two edits in `execution/modules/model_registry.py` (drop `"z-ai/"` from `ALLOWED_FAMILIES`, drop `"glm"` key)
3. Revert `execution/modules/llm_client.py` to bare singleton (drops Z.AI-direct capability, keeps OR working)

Or partial: keep the code, revert only the rule.

### Status

- Code shipped: model_registry.py + llm_client.py edits committed (or pending — operator decides)
- Rule shipped: model-tier.md Exhibit C added
- Directive shipped: directives/infrastructure/glm_5_2_integration.md
- SAST grep: NOT shipped (owed)
- Backport triage: NOT run (owed within 24h of code commit)

### Block on GLM-calling work

OpenRouter balance is $0 as of 2026-06-22. No GLM 5.2 calls can be made until the operator approves one of:
- (a) Z.AI Lite $3/mo flat plan
- (b) OpenRouter top-up ($5 minimum)
- (c) Cancel GLM project work and keep the infrastructure dormant

Phase 2/3/4 of `~/.claude/plans/chapter-1-introduction-and-calm-sonnet.md` are paused pending this decision.

---

## Update 2026-06-22 — PowerShell ASCII-only rule

New always-active rule shipped: `~/.claude/rules/powershell-ascii-only.md`. PowerShell 5.1 reads UTF-8-no-BOM files as cp1252; multi-byte UTF-8 sequences (em dash, smart quotes, ellipsis) break parsing several lines downstream with misleading error messages.

### Owed mechanical guardrail

SAST scanner extension: for every `*.ps1` file not starting with the UTF-8 BOM `EF BB BF`, flag any byte > 0x7F with file:line and the offending character.

### Owed read-only backport triage

Within 24h of rule landing: grep workspace for all existing `.ps1` files and check ASCII-only OR BOM-flagged. Known clean (2026-06-22 cleanup): all 6 files in `execution/infrastructure/launchers/`. Other `.ps1` files in workspace: not yet audited.

### Universal model chooser shipped 2026-06-22 evening

- Dispatcher: `execution/modules/model_router.py` — `call_model(alias, ...)` for 8 aliases (opus / sonnet / gpt / gpt4o / o1 / gemini / gemini-pro / glm). CLI: `py execution/modules/model_router.py <alias> "<prompt>"`.
- Launchers: 5 PowerShell + 5 Bash + interactive picker in `execution/infrastructure/launchers/`.
- Directive: `directives/infrastructure/model_chooser.md`.

Live-tested 2026-06-22: only `gemini` (free) works today. Anthropic balance = 0, OpenAI restricted key missing `model.request` scope, OR balance = 0. Chooser correct; budget/scope gates upstream.

---

## Update 2026-06-22 (evening) - Universal model chooser + free-claude-code proxy

Major additions to the workspace cost-routing layer:

### What shipped
- `execution/modules/model_router.py` - added `mode` ('client' | 'personal') + `sensitivity` ('public' | 'sensitive') parameters to `call_model()`. Personal-mode remaps Opus/Sonnet/GPT to `glm` (latest GLM via OR). Sensitivity guardrail raises `RuntimeError` when sensitive payload targets a public-only alias (GLM).
- `execution/modules/model_registry.py` - added `_OR_GLM_RE` + `_best_glm_family` helper + a `glm` tier branch in `_resolve_openrouter`. Auto-picks the highest `z-ai/glm-X.Y` from OR's catalog (currently 5.2; will auto-pick 5.3 / 6.0 when listed).
- `execution/modules/llm_client.py` - already had `base_url` parameter and dict-keyed client cache from prior turn; `_call_openrouter` now passes `base_url` through for Z.AI-direct (deferred).
- `execution/infrastructure/launchers/claude-{client,personal,pick}.ps1` + `.sh` - mode-aware launchers. `claude-personal.ps1` reads port from `C:/Users/deban/dev/free-claude-code/.fcc-port`, auto-starts the proxy if down.
- `directives/infrastructure/free_cc_proxy.md` - trust boundary, install path, pinned SHA `d281d52`, revert procedure.
- `directives/infrastructure/model_chooser.md` - already exists from prior turn; covers the chooser surface.
- `~/.claude/rules/model-tier.md` - new "Client vs Personal mode" section + GLM-5.2 auto-latest note + NIM-vs-OR rationale clarification. Backup at `.bak-2026-06-22-2`.
- Local install: free-claude-code pinned to commit `d281d52` at `C:/Users/deban/dev/free-claude-code/`, installed via `uv tool install --force <local_path>` (NOT via the upstream's `irm | iex` PowerShell remote-exec, which the auto-mode classifier correctly blocked).
- Proxy is running; smoke-tested end-to-end (Anthropic-protocol → proxy → OR; routing chain verified, only blocker is the OR $0 balance which surfaces as a clean 402 in the response).

### Owed mechanical guardrails

1. **SAST grep for `mode='personal'` x PII keyword in same function body**. Extends the prior-turn grep (for `chat_completion(model='z-ai/...')` x PII). Flag any Python file where a function contains BOTH `call_model(...mode='personal'...)` AND any of: `email`, `recipient`, `lead`, `candidate`, `cv`, `resume`, `cover_letter`, `phone`, `address`, `client`, `customer`. Defense in depth on top of the runtime `RuntimeError` raised in `call_model`.

2. **SAST grep for non-ASCII bytes in `.ps1` files (no BOM)** - already noted in the powershell-ascii-only.md backport item.

### Owed empirical work (Karpathy lens)

Ship ONE ProdCraft video end-to-end using `claude-personal.ps1` (proxy -> GLM-5.2). Compare quality vs a Sonnet baseline. Gated on $5 OR top-up (operator action).

### Status today (2026-06-22 evening)

- Proxy: installed, running on `localhost:8082`, healthy.
- Routing chain: verified end-to-end via curl POST to /v1/messages (got expected 402 from OR with $0 balance).
- Working live routes today: `gemini` direct (free). All other routes return clean credit/scope errors. Top-up unblocks.
- Documentation: trust boundary directive shipped, model-tier rule updated, model_chooser cheat sheet still current.

### Revert path

See `directives/infrastructure/free_cc_proxy.md` § Revert procedure. One-line per component; partial revert valid.

---

## Update 2026-06-22 (late evening) - Personal-mode SAST grep + PS1 ASCII rule shipped

### What shipped (after operator topped up $5 OR)

- **Live verification**: `call_model('glm', ...)` and `call_model('sonnet', mode='personal', ...)` both return real GLM-5.2 output. Personal-mode remap (sonnet -> glm) verified end-to-end. Proxy chain (Anthropic protocol -> proxy -> OR -> GLM) verified via direct curl POST to /v1/messages.
- **Karpathy-lens empirical**: same "rainbow explainer" prompt run through GLM-5.2 and Sonnet 4.6, both via OR. Outputs at `.tmp/glm_baseline/rainbow_{glm5.2,sonnet}.html`. GLM-5.2: 11213 bytes, 7 interaction handlers, 34s wall-clock, ~$0.008. Sonnet: 12312 bytes, 4 handlers, 57s wall-clock, ~$0.045 (5.6x cost). Both structurally valid; operator's eyeball test on visual quality is the final word.
- **SAST `personal-mode-with-pii` rule**: implemented in `execution/infrastructure/workspace_sast.py`. AST-based: extracts each function body, checks if BOTH `call_model(...mode='personal'...)` AND any PII keyword (`email`, `recipient`, `lead`, `candidate`, `cv`, `resume`, `cover_letter`, `phone`, `address`, `customer`, `pii`) appear in the same span. Severity HIGH. Verified with synthetic offender.
- **SAST `ps1-non-ascii` rule**: implemented in same file. Scans `.ps1` files (skipping AM-locked + node_modules + .anneal); flags files without UTF-8 BOM that contain any byte > 0x7F. Severity MEDIUM. Defends against the PowerShell-em-dash bug class (rule `powershell-ascii-only.md`).

### Backport triage results (read-only audit)

- `personal-mode-with-pii`: **0 findings** on workspace. No existing code combines `mode='personal'` with PII keywords. Expected — mode shipped today.
- `ps1-non-ascii`: **1 finding** at `execution/personal_workflows/remote_control_mobile/install_shortcut.ps1` line 2. Em dash in comment. **FIXED in-place** with the ASCII substitution sweep; re-scan returns 0 findings.

### What remains owed (pre-existing, not regressions from today's work)

The full SAST run also surfaced pre-existing findings on other rules, NOT introduced by today's work:
- `environ-copy`: 1 hit in `tests/test_workspace_sast.py` line 213 (likely test fixture exercising the rule — verify intent before fixing).
- `prior-art-pass-missing`: 6 directives missing the `## Prior art pass` section (adzuna_jobs, jooble_jobs, firecrawl_linkedin_dork, google_sheets_writer, job_search_sheet, job_tracker_pm_france). All `info` severity. These pre-date the rule landing 2026-06-18 — backport-triage owed but not blocking.

### Status (2026-06-22 late evening)

- OR balance: ~$5.00 minus tonight's smoke tests (~$0.06 total spend)
- Personal mode: WORKING end-to-end
- Client mode: working through Anthropic native (when balance available), through OR (verified, $0.0001 per call for Opus)
- Sensitivity guardrail: enforced at runtime by `call_model()` + defense-in-depth by SAST rule
- ASCII PS1 rule: enforced by SAST
- Trust boundary: documented, pinned SHA d281d52, revert procedure one-line per component
- Nothing committed: operator has clean working tree to review
