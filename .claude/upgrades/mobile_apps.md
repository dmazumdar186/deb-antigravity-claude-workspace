# Upgrade Report Card — mobile_apps

Audit date: 2026-06-11
Phase: B (per `clever-crunching-blanket.md`)
Surface: `execution/mobile_apps/` (6 scripts + registry.json) + `directives/mobile_apps/` (17 directives)
Constraint: read-only except this file; AM api-proxy excluded.

---

## Score Summary

| Script / Directive | D1 DynWF | D2 Exit Crit | D3 --mode | D4 Sub-agent | D5 Hardening | D6 Notes | D7 AgentTeam | D8 Canary |
|---|---|---|---|---|---|---|---|---|
| `bootstrap_mobile_app.py` | N/A | N/A | MAYBE | N/A | OK | MAYBE | N/A | N/A |
| `app_store_research.py` | HIT | N/A | MAYBE | N/A | MAYBE | MAYBE | N/A | N/A |
| `eas_build_helper.py` | N/A | N/A | N/A | N/A | OK | MAYBE | N/A | N/A |
| `mobile_app_canary.py` | N/A | N/A | N/A | N/A | OK | MAYBE | N/A | OK |
| `play_console_tester_gate.py` | N/A | N/A | N/A | N/A | OK | MAYBE | N/A | N/A |
| `testflight_invite.py` | N/A | N/A | N/A | N/A | MAYBE | MAYBE | N/A | N/A |
| `directives/mobile_apps/preflight.md` | N/A | HIT | N/A | N/A | N/A | MAYBE | N/A | N/A |
| `directives/mobile_apps/bootstrap_app_repo.md` | N/A | HIT | N/A | N/A | N/A | MAYBE | N/A | N/A |
| `directives/mobile_apps/app_design.md` | N/A | HIT | N/A | N/A | N/A | N/A | MAYBE | N/A |
| `directives/mobile_apps/phase1_local_standalone.md` | N/A | HIT | N/A | MAYBE | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/phase2_network_layer.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/phase4a_cf_worker.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | OK |
| `directives/mobile_apps/phase4b_modal_cron.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | OK |
| `directives/mobile_apps/phase5a_openrouter_routing.md` | N/A | HIT | HIT | N/A | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/canary.md` | N/A | OK | N/A | N/A | N/A | N/A | N/A | OK |
| `directives/mobile_apps/security_audit.md` | N/A | HIT | N/A | N/A | N/A | N/A | MAYBE | N/A |
| `directives/mobile_apps/android_deploy.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/ios_deploy.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/phase3_local_db.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/phase4c_supabase_setup.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/phase4d_supabase_auth.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | N/A |
| `directives/mobile_apps/phase5b_supabase_ai.md` | N/A | HIT | N/A | N/A | N/A | N/A | N/A | N/A |

HIT count: 15 | MAYBE count: 12 | OK count: 12 | N/A: remainder

---

## Dimension 1 — Dynamic Workflow candidate

### `app_store_research.py` — HIT

**Finding:** The script is a single-threaded serial scraper: one query → one Firecrawl call → parse results. The natural use pattern is "research 5–10 competitor apps across both stores before building." That fan-out (10+ parallel Firecrawl scrape calls, one per app/store) is the exact Dynamic Workflow shape:

- Each competitor URL is an independent `firecrawl_scrape` call.
- No cross-talk between tasks.
- Results merge into one competitive matrix.
- Current script hits one URL at a time — 10 competitors × 2 stores = 20 serial HTTP calls, probably 2+ minutes.

**Upgrade:** `ultracode:` prompt + orchestration script that fans out `app_store_research.py --query <competitor> --store <store>` calls in parallel (up to 16 concurrent), collects JSON blobs, merges into a `{query, competitor_matrix: [...]}` shape, and saves to `.tmp/aso_matrix_<slug>.json`.

**Save as** `.claude/workflows/aso-research.md` reusable command.

All other scripts: N/A — none fan out to >5 parallel tasks.

---

## Dimension 2 — Declarative exit criteria in directive

### All phase directives (phase1 through phase5b, ios_deploy, android_deploy, preflight, bootstrap_app_repo, security_audit) — HIT (11 directives)

**Finding:** Every phase directive uses imperative "steps" format (`1. Run X, then 2. Do Y`). None has an `## Exit Criteria` block with verifiable predicates. The `_TEMPLATE.md` standard now requires declarative exit criteria that define DONE as a testable state, not a sequence of commands. Imperative sequences rot fast — if a tool changes (EAS flags, wrangler v4 differences), the step silently mis-fires and the agent doesn't know it's done.

Directives with the highest drift risk:
- `phase4a_cf_worker.md` — steps reference wrangler v3 vs v4 logic inline (not a separate exit check).
- `android_deploy.md` — 20/14 gate already has per-step checks but no single end-state predicate.
- `ios_deploy.md` — ends with "confirm core flow works" (subjective, not automatable).
- `preflight.md` — outputs a table but lacks a machine-readable exit predicate (e.g., "all required items green").

**Example `## Exit Criteria` block for `android_deploy.md`:**
```markdown
## Exit Criteria
- `play_console_tester_gate.py --app <slug>` prints `gate_open: True`.
- `eas_build_helper.py` last run had exit code 0 and `last_build_sha` in registry is non-null.
- Play Console submission track shows `production` (not `alpha`/`beta`).
- `execution/mobile_apps/registry.json` entry for `<slug>` has non-null `last_build_sha`.
```

**Upgrade:** Add `## Exit Criteria` blocks to all 11 phase directives. Quick win — pure text, no code changes.

### `canary.md` — OK

Already contains clear output predicates (`/api/health` shape, dry-run counters, alert dedup), effectively declarative exit criteria even without the header. No change needed.

---

## Dimension 3 — `--mode` flag opportunity

### `phase5a_openrouter_routing.md` — HIT

**Finding:** The directive defines a `ROUTES` dict with hard-coded `simple` and `complex` tiers, both fixed to specific model IDs (`claude-haiku-4-5`, `claude-sonnet-4-7`). This is effectively a manual `--mode cheap/balanced/premium` pattern without the CLI-accessible switch. There is no way for the caller to say "I want a full Sonnet run on all tasks" or "run the whole thing on Gemini Flash for cost testing." The `anneal` precedent shows that exposing `--mode` (cheap/balanced/premium) at the CLI layer makes this trivially overridable per-session without editing code.

**Upgrade:** `backend/llm.py` should accept a `MODE` env var or `--mode` argument that overrides the `simple/complex` → model mapping. E.g.:
- `MODE=cheap` → both tiers use Haiku (or Gemini Flash fallback)
- `MODE=balanced` → current defaults (Haiku + Sonnet)
- `MODE=premium` → both tiers use Sonnet or Opus

### `bootstrap_mobile_app.py` — MAYBE

The script scaffolds the template and writes registry entries. No LLM calls, so `--mode` doesn't apply in the classic sense. MAYBE: if/when the bootstrap step eventually runs a design-assist LLM call (e.g., auto-generating placeholder screens from `APP_SPEC.md`), adding `--mode` at that point would be the right moment. Not worth doing now.

### `app_store_research.py` — MAYBE

Uses Firecrawl (fixed-cost API, not model-tiered), so `--mode` doesn't map cleanly. MAYBE applicable if competitor analysis is extended to include an LLM summarization step (classify apps, rate similarity). Defer.

---

## Dimension 4 — Sub-agent opportunity missed

### `phase1_local_standalone.md` — MAYBE

**Finding:** Phase 1 directs Claude to implement all screens, Context, state shape, and navigation in a single agentic run inside the main context. For apps with ≥5 screens or a complex state shape, this is a main-context memory hog. The pattern "one sub-agent per screen" or "sub-agent for Context + state, sub-agent per screen cluster" would fit the CLAUDE.md rule: delegate every file-read past the third one to an Explore or general-purpose agent.

**Upgrade (MAYBE, not HIT):** Add a note to `phase1_local_standalone.md` recommending a sub-agent split for apps with >4 screens: one agent for state shape + Context, one per 2-3 screens. Small enough to not warrant a full rewrite of the directive; just a note.

All other scripts/directives: N/A — orchestration is already linear or already delegates via the `/mobile-app` skill.

---

## Dimension 5 — Python-on-Windows hardening violations

### `bootstrap_mobile_app.py` — OK

All 5 rules confirmed implemented:
1. `run_cmd()` has `encoding="utf-8", errors="replace"` on every subprocess call. ✓
2. `_REGISTRY_WRITE_LOCK = threading.Lock()` guards all registry writes. ✓
3. `resolve_app_dir()` does `.resolve().is_relative_to(base)` path-traversal guard. ✓
4. No LLM pricing table needed (no Anthropic calls). N/A. ✓
5. No bare `except Exception: pass` — the one bare OSError in the tmp-cleanup is commented explaining it's safe. ✓

### `eas_build_helper.py` — OK

1. `subprocess.run(..., encoding="utf-8", errors="replace")` present on all calls. ✓
2. `_REGISTRY_WRITE_LOCK` present. ✓
3. No path derived from LLM output — `repo_path` comes from `registry.json`, not LLM. N/A. ✓
4. No pricing table. N/A. ✓
5. No bare swallows. ✓

### `mobile_app_canary.py` — OK

1. No subprocess calls; uses httpx directly. N/A. ✓
2. `results_lock = threading.Lock()` guards shared `results` dict in `ThreadPoolExecutor`. ✓
3. No LLM path validation needed. N/A. ✓
4. No pricing table. N/A. ✓
5. No bare swallows. ✓

### `play_console_tester_gate.py` — OK

1. No subprocess calls (pure date math). N/A. ✓
2. `_REGISTRY_WRITE_LOCK` present on registry writes. ✓
3. No LLM paths. N/A. ✓
4. No pricing table. N/A. ✓
5. No bare swallows. ✓

### `testflight_invite.py` — MAYBE

**Finding:** The script calls the ASC API via `requests.post/get` (not subprocess), so Rule 1 (subprocess encoding) is N/A. However, one subtle issue:

- `asc_post()` returns `{"status": resp.status_code, "body": resp.text}` for ALL status codes — including 5xx. The caller in `main()` then does `result.get("status")` and manually checks `< 400`. But if `resp.text` contains bytes that are ambiguous on Windows (unlikely for ASC JSON, but possible if Apple returns malformed error pages), `resp.text` could produce a `UnicodeDecodeError` that is not caught. **Severity: LOW** — ASC is always JSON, so this is theoretical.
- More concretely: `key_path = Path(require_env("ASC_PRIVATE_KEY_PATH"))` — this path comes from an env var, not LLM output. Rule 3 (LLM path validation) is strictly N/A. However, there is no check that `key_path` is an `.is_file()` before `private_key_path.read_text()` — `generate_jwt()` handles this with an explicit check `if not private_key_path.exists(): raise SystemExit(...)`. ✓ OK as-is.

**Verdict:** MAYBE — one theoretical unicode edge case in `requests` text decoding on 5xx Apple error pages. Not a current blocker given ASC is well-behaved.

### `app_store_research.py` — MAYBE

**Finding:** Uses `requests.post()` — encoding rule (Rule 1) is N/A (not subprocess). However:

- `parse_listings()` does string manipulation on the Firecrawl markdown response with no encoding guard. If Firecrawl returns non-UTF-8 markdown (unlikely but possible with scraped App Store pages containing emoji or special chars), the `resp.text` could misbehave. **Severity: LOW**.
- No LLM calls → no pricing table needed. ✓
- No threading → no lock needed. ✓
- No bare swallows: all exceptions propagate or are caught with messages. ✓

**Verdict:** MAYBE — not a practical bug today (Firecrawl returns UTF-8), but note for hardening if this becomes a paid production path.

---

## Dimension 6 — Note capture gap

**Finding:** No `.claude/notes/execution/mobile_apps/` directory exists. No `.claude/notes/directives/mobile_apps/` directory exists. Given this is the most complex multi-phase workflow in the workspace (6 scripts, 17 directives, 5 build phases, 2 app stores, a canary, a tester gate), the absence of notes is a meaningful gap.

What's missing:

| Script / Directive | Expected Notes File | Known gaps to capture |
|---|---|---|
| `bootstrap_mobile_app.py` | `.claude/notes/execution/mobile_apps/bootstrap_mobile_app.md` | `--force` semantics for OneDrive paths; `_rmtree_force` Windows read-only bit behavior |
| `eas_build_helper.py` | `.claude/notes/execution/mobile_apps/eas_build_helper.md` | EAS build minute accounting; `MOBILE_BUILD_WEBHOOK_URL` usage; registry SHA tracking |
| `mobile_app_canary.py` | `.claude/notes/execution/mobile_apps/mobile_app_canary.md` | httpx dependency vs. requests; dry-run semantics; Modal cron integration state |
| `testflight_invite.py` | `.claude/notes/execution/mobile_apps/testflight_invite.md` | ASC JWT TTL (1200s max); silent re-invite skip behavior; ES256 key format |
| `directives/mobile_apps/preflight.md` | `.claude/notes/directives/mobile_apps/preflight.md` | wrangler v4 session-scoping gotcha; `wrangler whoami` wrong-account detection |
| `directives/mobile_apps/phase4a_cf_worker.md` | `.claude/notes/directives/mobile_apps/phase4a_cf_worker.md` | wrangler v4 `--type javascript` ignore behavior; AM-lockdown cross-ref |

**Upgrade:** Seed `.claude/notes/execution/mobile_apps/` and `.claude/notes/directives/mobile_apps/` with the above high-value notes. Medium effort, high ROI for future sessions — the wrangler v4 / AM-lockdown notes in particular would prevent repeat friction.

---

## Dimension 7 — Agent Team candidate

### `app_design.md` — MAYBE

**Finding:** The design directive is a Claude-only reasoning pass (no scripts). The 5-principle framework involves competing hypotheses (what is the *real* core function? which features are truly accessory vs. core-adjacent?). This is exactly the Agent Teams "multi-hypothesis research" shape — run a Designer agent and a Skeptic agent in parallel on the same spec paragraph, then merge their outputs. The Designer maximizes feasibility; the Skeptic challenges over-scoping. This mirrors the `4-persona product thinking` feedback from memory (`feedback_multi_persona_thinking.md`).

**Upgrade (MAYBE):** Add a note to `app_design.md` recommending spawning a Skeptic agent for apps with >5 accessory features or where the core function is ambiguous. Not enough apps have been built yet to validate the ROI — revisit after app #2.

### `security_audit.md` — MAYBE

**Finding:** The directive already mandates two independent passes (with `/clear` between them), which is the manual version of Agent Teams "peer reviewing each other's findings." The optional pass 3 uses `anneal adversarial` (its own Red/Blue team). An actual Agent Team (two simultaneous Claude sessions, each reading the same codebase cold) would be faster than serial `/clear` passes and could do cross-referencing via peer messages. **But:** the serial-pass mandate comes directly from Nick's transcript (chapter 23) and the value of the `/clear` pattern is zero context bleed. Agent Teams technically share the same mailbox, not zero-context. Structural tension → leave as MAYBE, not HIT.

---

## Dimension 8 — Canary/health gap (deployed services only)

### `mobile_app_canary.py` + `directives/mobile_apps/canary.md` — OK

The canary ecosystem is well-designed:
- `mobile_app_canary.py` iterates `registry.json`, pings each app's `health_url` in parallel with `threading.Lock`-guarded results dict. ✓
- `--dry-run` mode in the canary itself (prints what it would assert, no HTTP calls). ✓
- `canary.md` directive defines the required `/api/health` JSON shape (including `secrets_present`, `upstream_credit_balances`, `last_success_per_job`) and mandates `--dry-run` on every cost-incurring CF Worker + Modal path. ✓
- `phase4a_cf_worker.md` specifies `/api/health` implementation with `secrets_present` boolean guards (never secret values). ✓
- `phase4b_modal_cron.md` has `dry_run: bool = False` parameter pattern. ✓
- Modal cron scheduling approach (not CF Triggers) is documented with the rationale (monitor Workers, don't share their infra). ✓

**One gap in `mobile_app_canary.py`:** The directive (Step 6) specifies alert dedup via `.tmp/canary_state.json` (only alert on state change), but `mobile_app_canary.py` has no dedup logic — it exits with status and a JSON summary but does NOT write to `.tmp/canary_state.json` or send alerts. This is the "Phase 2" of the canary not yet built. The script is a solid base, but the alerting and dedup are missing.

**Upgrade:** Add `--alert` flag + `.tmp/canary_state.json` dedup to `mobile_app_canary.py`. Low effort, closes the last gap between the canary directive and the canary script.

### `directives/mobile_apps/phase4a_cf_worker.md` — OK

`/api/health` + idempotency + `WORKER_SECRET` all mandated in the directive. Canary directive is the complementary contract. No gap.

**Note (excluded):** `execution/infrastructure/api-proxy/` is AM-locked per `CLAUDE.local.md` and excluded from this audit per plan constraints.

---

## Top 3 Highest-Value Upgrades

### #1 — Add `## Exit Criteria` to all 11 phase directives (D2 HIT — 11 files)

**Why top priority:** Pure text additions to `.md` files, zero code changes, zero risk. The payoff is high: phase directives are the instruction set for the `/mobile-app` skill's sub-agents. Without exit predicates, a sub-agent has no verifiable "done" state — it relies on the last step completing. The wrangler v4 step-vs-step drift in `phase4a_cf_worker.md` (step 1 checks version, but exit state isn't verified) is the concrete risk. This is a 2-hour effort, one directive at a time, that makes every future mobile-app build more reliable.

### #2 — Seed mobile_apps notes (D6 MAYBE — 0 current notes files)

**Why second:** The mobile_apps category is the most complex in the workspace and has zero notes. The wrangler v4 / AM-lockdown cross-reference, ASC JWT TTL behavior, and EAS minute accounting are exactly the kinds of gotchas that bite in session 2 of a build and take 20 minutes to re-derive. Seeding 4-6 notes files is a 30-minute effort with durable cross-session payoff.

### #3 — `app_store_research.py` Dynamic Workflow wrap (D1 HIT)

**Why third:** When building a new app, competitive ASO research across 8-10 competitors × 2 stores = 16-20 serial Firecrawl calls. The current script is single-threaded and must be called once per competitor. An `ultracode:` orchestration wrapper fans this to 16 parallel calls, cutting wall-clock time from ~2 min to ~15s. Moderate effort (write the workflow `.md` + orchestration script), high payoff when the first real app enters Phase 0 design.

---

## Lower-Priority Findings

- **D3 `--mode` for `phase5a_openrouter_routing.md`** (HIT): Clean win once the first app reaches Phase 5a. Add `MODE` env var to `backend/llm.py`. Defer until Phase 5a is actually invoked.
- **D8 canary alert + dedup** (gap in `mobile_app_canary.py`): The base canary works for manual `--dry-run` checks. Alerting only matters once a real app is deployed (Phase 4a). Add at Phase 4a time.
- **D5 `testflight_invite.py` unicode** (MAYBE): Theoretical edge case on Apple error pages. Not worth hardening unless it bites.
- **D4 sub-agent split for Phase 1** (MAYBE): Relevant only for apps with >5 screens. Add as a note to the directive, not a structural change.

---

## What to skip

- `registry.json`: no upgrade needed — clean JSON, the right shape, currently empty (no apps yet).
- `play_console_tester_gate.py`: well-hardened, right abstraction (pure date math, zero API calls). No change needed.
- `directives/mobile_apps/canary.md`: already declarative, already has exit predicates. Best-written directive in the category.
- `directives/mobile_apps/app_design.md`: Agent Team note is a MAYBE for later; current design is the right single-pass approach until you've built 2+ apps.
