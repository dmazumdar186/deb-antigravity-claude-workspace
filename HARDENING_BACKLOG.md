# Hardening Backlog — 2026-06-15

## Update 2026-06-15 (operator scope decisions)

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
