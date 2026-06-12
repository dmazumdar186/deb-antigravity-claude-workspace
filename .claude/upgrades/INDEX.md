# Workspace Upgrade Index (2026-06-11)

Aggregated from 8 per-project audit cards under `.claude/upgrades/`. Use this index to decide which upgrades to actually execute. Each row links to the source card.

---

## Stats

- Audits run: 8 (personal_workflows, mobile_apps, other_categories, in_flight_projects, anneal, humanizer, youtube_video_analyzer, cv_optimizer_agent)
- Total HIT findings: 43
- Total MAYBE findings: 26
- Total OK (already implements pattern): 29

HIT breakdown by card:
- `personal_workflows.md` — 14 HITs
- `mobile_apps.md` — 15 HITs
- `other_categories.md` — 9 HITs
- `in_flight_projects.md` — 5 HITs (Rosy Origami 4 + Remotion 1)
- `external/anneal.md` — 3 HITs
- `external/humanizer.md` — 5 HITs (incl. D7 Agent Team + D9 CLAUDE.md as HITs)
- `external/youtube_video_analyzer.md` — counted as TEST MINOR / NO CI / SKILL PATH GAP (3 actionable items, not formally HIT-tagged; conservative count: 3)
- `external/cv_optimizer_agent.md` — DEFERRED

---

## Top 5 quick wins (≤ 1 hour each, near-zero risk)

Order: low effort + zero risk + high reuse value.

1. **Humanizer** — Add `## Exit Criteria` block to README — 15 min — [`external/humanizer.md`](.claude/upgrades/external/humanizer.md)
   Why: 15-minute docs addition that turns "did it exit 0?" into a verifiable 4-predicate success contract. Zero code change, zero risk. Pay-off in every future SKILL.md invocation.

2. **Humanizer** — Fix `canary_check.py` subprocess encoding (6 calls missing `encoding="utf-8", errors="replace"`) — 20 min — [`external/humanizer.md`](.claude/upgrades/external/humanizer.md)
   Why: 6 one-line fixes, identical pattern, copy from the compliant calls already in `test_batch.py:58-63`. Closes the only Windows crash path in the public tool's test suite.

3. **Humanizer** — Add `cache_read`/`cache_write` to `_TIER_COST_PER_M` — 10 min — [`external/humanizer.md`](.claude/upgrades/external/humanizer.md)
   Why: 2 extra dict entries per tier. Pricing model becomes correct (currently over-estimates ~5-10× under caching). Required by workspace hardening rule 4.

4. **job_search_llm_gate.py (personal_workflows)** — Create `.claude/notes/execution/personal_workflows/job_search_llm_gate.md` — 15 min — [`personal_workflows.md`](.claude/upgrades/personal_workflows.md)
   Why: Captures the Gemini 2.5 thinking-token truncation fix, `response_mime_type` workaround, and throttle_s=7 rationale — three gotchas that took real time to discover and will trip any future session working on this module.

5. **mobile_apps directives** — Add `## Exit Criteria` to 11 phase directives — 2h — [`mobile_apps.md`](.claude/upgrades/mobile_apps.md)
   Why: Pure text additions to `.md` files. Zero code risk. Makes every future `/mobile-app` skill sub-agent's "done" state verifiable rather than implicit. The highest-leverage 2 hours in the workspace — 11 directives become machine-auditable.

---

## Top 3 high-impact rewrites (1+ day, significant value)

1. **cv_builder*.py (personal_workflows)** — Extract shared `cv_builder_core.py` module — 2–3h — [`personal_workflows.md`](.claude/upgrades/personal_workflows.md)
   Why: All 3 CV builder variants duplicate ~80% of reportlab boilerplate (`_register_fonts`, `SectionHeader`, `exp_entry`, `skill_row`, styles dict). Extracting to a shared core eliminates ~600 LOC of duplication, makes style updates apply globally, and creates a single insertion point for any future AI-assist feature. Zero behavior change; the only risk is a broken import if the refactor is sloppy.

2. **job_search_sheet.py (personal_workflows)** — Parallelize Stage 1 fan-out with `ThreadPoolExecutor` — 3–4h — [`personal_workflows.md`](.claude/upgrades/personal_workflows.md)
   Why: Stage 1 is `for geo × title × source` — currently serial, will reach 20+ calls when Phase 1b geos activate. With `ThreadPoolExecutor(max_workers=4)` + `threading.Lock()` on `all_raw_jobs.extend`, wall-clock time drops 5–10×. The upgrade must be done BEFORE Phase 1b geos are activated — retrofitting after the fact on a live pipeline is riskier. This is the highest-ROI script upgrade because the cost of inaction grows with each new geo added.

3. **Remotion + Rosy Origami** — Add visual quality validation to smoke-test pipeline — 1–2h across both — [`in_flight_projects.md`](.claude/upgrades/in_flight_projects.md)
   Why: The `/remotion` skill's smoke-test exports a PNG but never asserts it is non-blank (a silent transparent/black frame passes today). Rosy Origami generates HTML email but has no browser-preview step and no hallucination-flag surface to the editor. Per `feedback_product_quality_skeptic.md`, visual quality validation is non-negotiable for user-facing artifacts. The Remotion fix is a 3-line PIL assertion; the Rosy Origami fix is adding Steps 11–12 to the directive. Together: ~1–2h, zero code churn.

---

## Cross-cutting patterns (apply across multiple projects)

These upgrades appear in 3+ audit cards — fix the pattern workspace-wide rather than per-project:

- **No `.claude/notes/` for almost any project** — 0 notes files exist for personal_workflows, mobile_apps, enrichment, custom_scrapers, infrastructure, video, rosy_origami, remotion, anneal, or humanizer. The note-taker hook fires on directive/script edits but the actual note files have never been seeded. Workspace-level fix: a single "seed all high-value notes" session (~2h) to create stub files with the known gotchas for the 10 highest-priority locations listed across the 8 audit cards.

- **No `## Exit Criteria` blocks in directives** — This HIT appears in mobile_apps (11 directives), lead_sourcing (2), infrastructure (1), custom_scrapers (7 as MAYBE), google (1), rosy_origami (1), remotion (1), anneal (OK via AnnealResult.reason, but docs gap). Workspace-level fix: add an exit-criteria lint step to the `workspace_sast.py` runner — a Grep for `## Exit Criteria` in every directive file, flagging any that lack it. One SAST rule addition, catches the gap on every future session.

- **Subprocess encoding violations in test files** — Both `humanizer` and `youtube_video_analyzer` external repos have test files calling `subprocess.run(*, text=True, capture_output=True)` without `encoding="utf-8"`. Workspace-level fix: extend the Python hardening SAST rule in `workspace_sast.py` (or a dedicated Grep pattern) to flag `text=True` without `encoding=` in any `.py` file. The rule already exists in CLAUDE.md prose; it needs a machine enforcement path.

- **No CLAUDE.md in external repos** — HIT for both anneal and humanizer; likely true for youtube-video-analyzer and cv-optimizer-agent (not confirmed). Workspace-level fix: a one-off sweep of all `C:\Users\deban\dev\*` repos, seeding a minimal CLAUDE.md in any that lack one. ~30 min per repo × 4 repos = 2h total.

- **Directive/code sync gap (Documenter agent not being called)** — Both Rosy Origami and Remotion have directives that drift from the actual code (Tools/Scripts table out of sync, new bootstrap steps not reflected). The CLAUDE.md rule requiring a Documenter agent call after every code edit is being skipped under time pressure. Workspace-level fix: wire the Documenter agent call as a `post-edit` hook in `.claude/settings.json` rather than a voluntary step, as recommended in `in_flight_projects.md`.

- **Cache-aware Claude pricing missing** — HIT for `humanizer`, `ai_opener_generator.py`, and `variant_generator.py`. All use flat `input + output` pricing without `cache_read` (0.1×) and `cache_write` (1.25×) entries. Fix is 2 dict entries per model, but it must be applied to every script that has a cost log line.

---

## Full prioritized list

Sort by (impact × ease), descending.

| Rank | Project | Upgrade | Effort | Risk | Source |
|---|---|---|---|---|---|
| 1 | humanizer | Add `## Exit Criteria` to README | 15 min | zero | external/humanizer.md |
| 2 | humanizer | Fix 6 `canary_check.py` + test subprocess calls: add `encoding="utf-8", errors="replace"` | 20 min | zero | external/humanizer.md |
| 3 | humanizer | Add `cache_read`/`cache_write` to `_TIER_COST_PER_M` pricing table | 10 min | zero | external/humanizer.md |
| 4 | humanizer | Fix bare `except Exception: pass` in `test_monkey.py:64` — add log line or comment | 5 min | zero | external/humanizer.md |
| 5 | humanizer | Seed `CLAUDE.md` (architecture + test structure + Windows quirks + skill ref) | 30 min | zero | external/humanizer.md |
| 6 | personal_workflows | Create `.claude/notes/execution/personal_workflows/job_search_llm_gate.md` | 15 min | zero | personal_workflows.md |
| 7 | personal_workflows | Create 4 notes files for job_tracker_pm_france, cv_builder, job_search_sheet, job_search_notify | 30 min | zero | personal_workflows.md |
| 8 | mobile_apps | Add `## Exit Criteria` to 11 phase directives (preflight, bootstrap, phase1–5b, ios_deploy, android_deploy, security_audit) | 2h | zero | mobile_apps.md |
| 9 | remotion | Add PIL brightness assertion to `remotion_bootstrap.md` Step 6 smoke-test | 15 min | zero | in_flight_projects.md |
| 10 | remotion | Create `.claude/notes/directives/video/remotion_three.md` with 4 R3F headless-render gotchas | 20 min | zero | in_flight_projects.md |
| 11 | rosy_origami | Add `## Exit Criteria` block to `directives/content/rosy_origami_composer.md` | 15 min | zero | in_flight_projects.md |
| 12 | rosy_origami | Rename `--tier` to `--mode` in `generate_demo.py` and update directive flag table | 30 min | low | in_flight_projects.md |
| 13 | rosy_origami | Create `.claude/notes/execution/content/rosy_origami/composer.md` + `generate_demo.md` | 30 min | zero | in_flight_projects.md |
| 14 | rosy_origami | Add `## Product Considerations` section to directive (UX / Trust / Edge behavior) | 20 min | zero | in_flight_projects.md |
| 15 | rosy_origami | Add Steps 11–12 to directive: surface `.meta.json` flagged_dates + browser preview step | 20 min | zero | in_flight_projects.md |
| 16 | anneal | Seed `CLAUDE.md` in anneal repo (key files + test command + tier explanation) | 30 min | zero | external/anneal.md |
| 17 | anneal | Create `.claude/notes/` for anneal repo (or capture known gotchas in workspace notes) | 20 min | zero | external/anneal.md |
| 18 | youtube_video_analyzer | Add `encoding="utf-8", errors="replace"` to 6 test helper `subprocess.run()` calls | 20 min | zero | external/youtube_video_analyzer.md |
| 19 | youtube_video_analyzer | Verify SKILL.md invocation path resolves from workspace; update if needed | 15 min | low | external/youtube_video_analyzer.md |
| 20 | youtube_video_analyzer | Create `.claude/notes/execution/video/youtube_video_analyzer.md` in workspace | 10 min | zero | external/youtube_video_analyzer.md |
| 21 | cv_optimizer_agent (workspace copy) | Add `--mode` flag (cheap=Sonnet, premium=Opus); update model string to `claude-opus-4-7` | 1h | low | personal_workflows.md |
| 22 | cv_optimizer_agent (workspace copy) | Add `resolve().is_relative_to(TMP)` boundary check on LLM-derived output path in `_slugify()` | 30 min | low | personal_workflows.md |
| 23 | cv_optimizer_agent (workspace copy) | Add notes file clarifying whether local copy or public repo is canonical | 10 min | zero | personal_workflows.md |
| 24 | personal_workflows | Add `## Exit Criteria` to `directives/personal_workflows/job_tracker_pm_france.md` | 15 min | zero | personal_workflows.md |
| 25 | personal_workflows | Add `## Exit Criteria` to `directives/personal_workflows/job_search_sheet.md` | 15 min | zero | personal_workflows.md |
| 26 | personal_workflows | Add `## Exit Criteria` to `directives/personal_workflows/cv_builder.md` | 10 min | zero | personal_workflows.md |
| 27 | lead_sourcing | Add `## Exit Criteria` to `google_maps_sourcing.md` and `sirene_company_lookup.md` | 20 min | zero | other_categories.md |
| 28 | enrichment | Add `## Exit Criteria` to `firecrawl_linkedin_dork.md` | 10 min | zero | other_categories.md |
| 29 | infrastructure | Add `## Exit Criteria` to `workspace_sast.md` (exit 0/1/2 semantics) | 10 min | zero | other_categories.md |
| 30 | google | Add `## Steps` + `## Exit Criteria` to `google_sheets_writer.md` | 20 min | zero | other_categories.md |
| 31 | infrastructure | Create `.claude/notes/execution/infrastructure/workspace_sast.md` (HOME env workaround, semgrep Windows incompat) | 15 min | zero | other_categories.md |
| 32 | video (workspace) | Create `.claude/notes/execution/video/youtube_video_analyzer.md` (yt-dlp rate-limit, PySceneDetect Windows install, creator-profile TTL) | 20 min | zero | other_categories.md |
| 33 | personalization | Add `--mode` flag to `ai_opener_generator.py` and `variant_generator.py` (cheap/balanced/premium) | 2h | low | other_categories.md |
| 34 | personalization | Add `cache_control` to static system prompt in `ai_opener_generator.py` + cache-aware token accounting | 1h | low | other_categories.md |
| 35 | personalization | Create notes file for `ai_opener_generator.py` (OR empty-credits fallback, cache opportunity) | 15 min | zero | other_categories.md |
| 36 | custom_scrapers | Create `.claude/notes/directives/custom_scrapers/` stub capturing Jooble=reCAPTCHA, APEC=session cookie, Indeed=rate-limited | 20 min | zero | other_categories.md |
| 37 | custom_scrapers | Add parallel fan-out wrapper in `job_tracker_pm_france.py` for scraper calls (`ThreadPoolExecutor`) | 2–3h | medium | other_categories.md |
| 38 | enrichment | Parallelize `firecrawl_linkedin_dork.py` bulk loop with `ThreadPoolExecutor(max_workers=3)` + lock | 2h | medium | other_categories.md |
| 39 | personal_workflows | Parallelize `job_search_sheet.py` Stage 1 with `ThreadPoolExecutor(max_workers=4)` + lock | 3–4h | medium | personal_workflows.md |
| 40 | personal_workflows | Extract `cv_builder_core.py` shared module from 3 CV builder variants | 2–3h | low | personal_workflows.md |
| 41 | mobile_apps | Seed `.claude/notes/execution/mobile_apps/` and `.claude/notes/directives/mobile_apps/` (6 key notes files) | 30 min | zero | mobile_apps.md |
| 42 | mobile_apps | Add `--alert` flag + `.tmp/canary_state.json` dedup to `mobile_app_canary.py` | 2h | low | mobile_apps.md |
| 43 | mobile_apps | Add `app_store_research.py` parallel fan-out orchestration wrapper (`.claude/workflows/aso-research.md`) | 3–4h | medium | mobile_apps.md |
| 44 | anneal | Add `anneal batch <refs-file>` subcommand (parallel multi-repo runs) | 4–6h | medium | external/anneal.md |
| 45 | anneal | Parallelize `VotingAuditor` sampling with `ThreadPoolExecutor` (already in `loop_adversarial.py`) | 2h | low | external/anneal.md |
| 46 | gtm_client_workflows | Create `directives/gtm_client_workflows/import_leads.md` directive (zero coverage today) | 30 min | zero | other_categories.md |
| 47 | remotion | Add `## Exit Criteria` to `remotion_render.md` (file size + ffprobe duration assertion) | 20 min | zero | in_flight_projects.md |
| 48 | personal_workflows | Add synthetic canary for `job_tracker_pm_france.py` Modal cron (cron-job.org or GH Actions schedule) | 2–3h | medium | personal_workflows.md |
| 49 | personal_workflows | Add `job_tracker_setup.py` subprocess encoding fix (1 line: add `encoding="utf-8", errors="replace"`) | 5 min | zero | personal_workflows.md |
| 50 | youtube_video_analyzer | Add GitHub Actions CI workflow + weekly `canary_check.py` cron | 2h | low | external/youtube_video_analyzer.md |
| 51 | humanizer | Add `--batch` flag with `ThreadPoolExecutor` fan-out + coordinated SKILL.md update | 3–4h | medium | external/humanizer.md |
| 52 | mobile_apps | Add note to `phase5a_openrouter_routing.md` directive: expose `MODE` env var in `backend/llm.py` | 1h | low | mobile_apps.md (defer until Phase 5a) |
| 53 | rosy_origami | Add `/api/health` to CF Worker on Day 1 of Phase 3 scaffolding | 1h | low | in_flight_projects.md (flag in Phase 3 plan) |

---

## Don't bother (low-value upgrades to explicitly skip)

- **`anneal` — `--mode` alias for subcommands** — The subcommand UX (`anneal classic HEAD`) is more ergonomic than `--mode classic HEAD`. Only matters if workspace shell scripts hard-code `--mode`. Skip unless programmatic calling at scale becomes real.
- **`humanizer` — Agent Team / council mode** — High conceptual value but depends on anneal v0.2 council primitives. Skip until anneal ships council mode.
- **`humanizer` — Sub-agent pipeline refactor** — Monolith is ~730 lines; internal sub-agent delegation adds overhead without benefit at this size. Skip.
- **`mobile_apps` — `testflight_invite.py` unicode edge case** — Theoretical Apple 5xx error page unicode issue. ASC is well-behaved in practice. Not worth hardening unless it bites.
- **`mobile_apps` — `app_store_research.py` encoding on Firecrawl markdown** — UTF-8 in practice; theoretical only. Skip.
- **`job_tracker_pm_france.py` — full Dynamic Workflow** — Stage A fan-out is 5 boards; threshold is >5. Sequential is fast enough for a daily cron. Borderline MAYBE, not worth the ThreadPoolExecutor complexity.
- **`job_search_llm_gate.py` — `--mode` flag alignment** — The `--primary-model` / `--secondary-model` shape is functionally equivalent to `--mode`. Cosmetic alignment only; skip.
- **`youtube_video_analyzer` — `--obsidian-vault` path traversal guard** — User-controlled flag, not LLM-derived input. Risk is theoretical. Skip.
- **`wedding_card_generator.py`** — Single-use script with hardcoded event details. No meaningful upgrade axes apply. Skip entirely.
- **`_jt_utils.py`** — Utility module. No upgrade needed.
- **All stub/empty categories** (`gtm_icp_filters/`, `image_generation/`, `n8n_workflows/`, `crm_and_pm/`, `rag/`) — Nothing to audit or upgrade yet.

---

## Deferred (requires more info or external setup)

- **CV Optimizer** — SUPERSEDED by v2 (2026-06-12) — see `directives/personal_workflows/cv_optimizer_v2.md`. The public repo clone + audit path is no longer the priority; v2 (Cloudflare Pages + Worker + Gemini Flash, 7-phase scaffold) is now the canonical personal tool. The old Streamlit/Anthropic agent (`cv_optimizer_agent.py`) remains as offline CLI fallback. Original audit card: [`external/cv_optimizer_agent.md`](.claude/upgrades/external/cv_optimizer_agent.md).
- **`humanizer` — CI / GitHub Actions** — Tests require API keys for non-dry runs. Deferred until repo has external contributors or the no-key subset (`test_sanity.py`, `test_monkey.py`) is confirmed to run cleanly without creds.
- **`youtube_video_analyzer` — `--deep-dry-run` test + `--obsidian-vault` test** — Good coverage gaps but not crashing anything now. Defer to next v4.x work session.
- **Rosy Origami — Dynamic Workflow (multi-tenant)** — Fan-out trigger (>5 parallel tasks) not yet met. Triggered at Phase 4 multi-tenant. Save `.claude/workflows/rosy-ingest.md` at that point.
- **Remotion — Lambda parallel render** — Requires Remotion company license (v2 scope). Not current.
- **`mobile_apps` — Agent Team for `app_design.md`** — Revisit after app #2 is built.

---

## Suggested execution sequence

If you want to ship upgrades NOW with minimal risk, do them in this order:

**Batch 1 — Quick wins (≤ 2h total, zero risk)**
1. Humanizer 4 quick fixes (exit criteria + 6 subprocess encoding lines + cache pricing + monkey bare-except): ~50 min
2. Seed `CLAUDE.md` in humanizer repo: 30 min
3. Remotion PIL assertion + notes file: 35 min
4. `job_search_llm_gate.md` notes file: 15 min

**Batch 2 — Single project: mobile_apps exit criteria**
Add `## Exit Criteria` to all 11 phase directives in one focused session. Pure text, zero code risk, high durable value. ~2h. Pick this because the mobile_apps category is the most complex in the workspace and has 11 directives without any verifiable done-state.

**Batch 3 — Cross-cutting notes sweep**
Seed notes files for: personal_workflows (4 files), mobile_apps (6 files), custom_scrapers (1 file), infrastructure/workspace_sast (1 file). Total: ~12 stub files × 10 min each = ~2h. All documentation, zero code risk.

Stop after Batch 3, commit, and observe. The remaining work (parallelization rewrites, canary additions, CLAUDE.md seeding for anneal/youtube) can be batched by project in subsequent sessions.

---

## Skipped scope

- Accessory Masters surface — lockdown per `CLAUDE.local.md`; no audit, no edits.
- Stub/empty categories: `gtm_icp_filters/`, `image_generation/`, `n8n_workflows/`, `crm_and_pm/`, `rag/` (confirmed empty per Phase C).
- `execution/infrastructure/api-proxy/` — AM-locked, excluded from all audit phases.
- `gtm_client_workflows/accessory_masters_*` and `generate_qa_test_plan.py` — AM-specific content, excluded.
