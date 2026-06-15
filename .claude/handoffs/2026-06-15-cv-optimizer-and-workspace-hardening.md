# Workspace Handoff — 2026-06-15

Carry-forward prompt for the next working session. Read this first.

## Where we ended

CV Optimizer was rebuilt as a local CLI on top of the operator's Claude subscription (`claude --print`). The Cloudflare Worker version is deprecated to demo-URL status. Front-door synthetic passed 5 consecutive times. Mobile dashboard at https://cv-optimizer.pages.dev/status reflects current state.

Two always-active workspace rules were added globally:
- `~/.claude/rules/front-door-synthetic.md`
- `~/.claude/rules/learnings-loop.md`

Both referenced from the new `TOP-OF-MIND RULES` block at the top of `~/.claude/CLAUDE.md`.

Latest commit on `main`: `777f19e`, pushed to origin.

Note: `HANDOFF.md` at the workspace root is the Accessory Masters handover (frozen, no-touch per `CLAUDE.local.md`). This file at `.claude/handoffs/` is the workspace-level handoff for ongoing work — do not conflate the two.

## What was NOT done today — gap list

### 1. Workspace hardening triage (BIGGEST GAP, recommended next session start)

The new rules apply to every existing project, not just new builds. We never ran the triage.

Affected in-workspace projects (personal_workflows):

| Path | Type | Known state | Gap |
|---|---|---|---|
| `execution/personal_workflows/cv_builder*.py` | CV PDF builder | Pre-rules; uses some LLM | No eval, no front-door synthetic, model-tier unverified |
| `execution/personal_workflows/cv_optimizer_agent.py` | Streamlit + Gemini (older) | Public repo `github.com/dmazumdar186/cv-optimizer-agent` | Separate audit needed |
| `execution/personal_workflows/anthropic_watch/` | Daily watcher | Has directive | No front-door synthetic, no DoD-cron-pipeline grade |
| `execution/personal_workflows/job_tracker_pm_france.py` | Daily cron pipeline | Memory says "32/32 tests pass" | Same hollow-signal pattern we just got burned on; needs a real synthetic |
| `execution/personal_workflows/job_search_sheet.py` | Lead aggregation | Phase 1a in flight (per prior session) | Apply rules now, before more is built |
| `execution/personal_workflows/job_tracker_setup.py` | Setup script | Likely fine | Confirm no user surface |
| `execution/personal_workflows/self_outbound_system.md` (directive) | Outbound engine | Likely AM-locked — confirm against CLAUDE.local.md | Either honor lock or audit |
| `execution/personal_workflows/cv_optimizer_v2/` | Cloudflare Worker | Deprecated to demo URL | Decide: retire / keep with synthetic / keep with banner |
| `execution/personal_workflows/remote_control_mobile/` | Built today | Layer 3 untested end-to-end | Operator double-clicks shortcut, confirms phone connects |

Plus other categories not yet inventoried: `lead_sourcing/`, `enrichment/`, `personalization/`, `gtm_*`, `custom_scrapers/`, `infrastructure/`, `content/`, `n8n_workflows/`, `crm_and_pm/`, `google/`, `rag/`, `mobile_apps/`, `video/`, `image_generation/`, `subagent/`.

**Triage execution plan:**
1. Spawn one Explore agent per top-level category to inventory active scripts + their state (read-only, no edits).
2. For each active project, grade it against the four rules: eval-first, front-door-synthetic, model-tier, learnings-loop. Plus the relevant DoD template (`~/.claude/templates/dod-{llm-ui,cold-email,cron-pipeline}.md`).
3. Produce `HARDENING_BACKLOG.md` at workspace root — one row per project with: current grade, top 3 gaps, recommended fix (small fix vs rebuild vs retire vs lock-as-frozen), effort estimate.
4. Operator reviews the backlog and picks which projects to harden first.

### 2. Remote-control Layer 3 verification

Desktop shortcut "Claude Remote Control" exists with verified-correct properties (target = cmd.exe, args = `/k claude --remote-control AntiGravity-CV-Optimizer`). Never actually double-clicked + tested. Operator needs to:
- Double-click the shortcut
- Confirm a real console opens
- Confirm Claude prints a connection URL
- Open that URL on phone (signed into same Anthropic account)
- Confirm the phone session can drive the laptop (file edit, commit, etc.)

If anything fails, the directive `directives/personal_workflows/remote_control_mobile.md` documents the recovery path.

### 3. Public-repo hardening (out of this workspace's git scope)

The operator owns at least four code locations outside this workspace that need their own hardening pass:
- `github.com/dmazumdar186/cv-optimizer-agent` (Streamlit + Gemini)
- `github.com/dmazumdar186/humanizer`
- `github.com/dmazumdar186/youtube-video-analyzer`
- `C:\Users\deban\dev\anneal\` (local Python audit CLI)

Each needs: front-door synthetic, model-tier verification, eval suite check.

### 4. Worker retirement decision

`cv-optimizer.pages.dev` is alive but deprecated. Options:
- A. Retire entirely (delete project from Cloudflare; remove from registry).
- B. Keep as demo URL + add a front-door synthetic running on cron (currently breaks daily due to Gemini quota).
- C. Keep without synthetic + add a banner "Demo only — use the local CLI for real use."

Operator decision pending.

### 5. Synthetic external scheduler

The front-door rule says synthetic should run on a 1-hour cron. The local CLI synthetic requires the operator's authenticated `claude --print` session — won't run on remote cron without a relay back to the laptop.

Options:
- A. Windows scheduled task on the laptop. Auto-mode denied "persistent scheduled task" earlier today as unauthorized persistence — operator can grant approval if they want it.
- B. Worker version of synthetic on UptimeRobot / GitHub Actions cron — but the Worker's optimize path is also broken on free-tier quota.
- C. Manual + on-demand only. Document the deviation in the directive.

Recommendation: C for now (single-user personal tool; the rule's 1-hour cron is for multi-tenant systems).

### 6. CV Optimizer Local — small follow-ups

- YouTube + personal site sources in `worker/src/profile.ts PROFILE_SOURCES` are unset placeholders. Add URLs when available (the local CLI doesn't use them yet anyway, but the Worker would).
- `--cv-text` and `--jd-url` CLI input paths exist but aren't synthetic-covered (synthetic uses `--cv` PDF + `--jd-text-file`). Add fixture-based test runs for the alternate input shapes.
- French CV synthetic — current fixture only covers English (`fixtures/cv_en.pdf` + `fixtures/jd_en.txt`). Add `fixtures/jd_fr.txt` and a `--lang fr` mode to the synthetic to cover FR→FR.

### 7. Memory updates (apply before next session ends)

The `MEMORY.md` index already has `project_cv_optimizer_v2.md` pointing to today's state. Need to add:
- `project_cv_optimizer_local.md` — new memory file for the local CLI as the active CV product
- Update `MEMORY.md` index pointer

### 8. Other in-flight items from prior sessions (per memory)

- `anthropic_watch` v1.1 schedule — deferred per session notes
- `job_search_sheet` Phase 1b/1c — Jooble integration was deferred (reCAPTCHA blocked); only SA JSON left
- Mobile app workspace (`mobile_apps/`) — separate skill, separate ongoing work
- Rosy origami — Phase 0 per memory; status unclear

## Lessons captured today (do NOT repeat)

- "Tested layers" ≠ "system works" (the 42/42 audit incident) → `~/.claude/rules/front-door-synthetic.md` Exhibit A
- Free-tier API quotas are not a production backend → `~/.claude/rules/model-tier.md` Exhibit B
- Shallow validators give false confidence (9/9 PASS → 2/8 deep) → `~/.claude/rules/eval-first.md` Exhibit A
- Workspace upgrades are design-phase tooling; applied retroactively they expose problems but don't fix them. Audit existing work explicitly when rules change.
- Windows tty: `claude --remote-control` needs a real interactive console; subprocess redirection collapses to print-mode. Use desktop shortcut → cmd.exe /k.
- CRLF line endings break fingerprint-based drift detection. Normalize to LF before hashing.
- The right architecture for a single-user career tool is a local CLI calling `claude --print`, not a SaaS-shaped Worker calling a paid API.

## Live endpoints (for mobile spot-checks)

- Local CLI: `py execution/personal_workflows/cv_optimizer_local/cli.py --help`
- Worker health: https://cv-optimizer-api.debanjan186.workers.dev/api/health (demo only)
- Mobile status: https://cv-optimizer.pages.dev/status

## Recommended next-session opening

> Read `.claude/handoffs/2026-06-15-cv-optimizer-and-workspace-hardening.md`. Start with gap #1 — workspace hardening triage. Spawn Explore agents per category to inventory state (read-only). Synthesize into `HARDENING_BACKLOG.md` at workspace root with one row per project: current grade, top 3 gaps, recommended fix, effort. Bring the backlog to operator before any actual fixes.
