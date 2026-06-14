# Workspace Status

> Live status page reads this file. Edit anytime; mobile reload picks it up immediately.
> Last updated: 2026-06-14

## Current focus

**CV Optimizer v2.1** — reliability + profile enrichment shipped (commit `3fca347`). Deep-eval rebuild in progress.

## Blocker

**Anthropic credit balance = -$0.14** (negative — past balance owed).
Top up at: https://console.anthropic.com/settings/billing
Minimum suggested: $10 (allows ~150 Sonnet 4.6 calls — enough for several iteration loops).

## What was done today

- Phase A-F shipped (two-phase orchestration, prompt SST, Firecrawl retry, 26 unit tests, prompt cleanup, profile enrichment from GitHub).
- Deep eval harness built: `py .tmp/cv_test/visual_matrix.py` — runs 8 (CV, JD) combos, per-field langdetect on every bullet/skill/recommendation, renders PNG via headless Chromium, recruiter 2-second proxy checks.
- First deep-eval run: **2/8** with Haiku 4.5 (was hiding behind shallow 9/9 PASS).
- Upgraded to Sonnet 4.6 (Haiku banned per new model-tier policy). Mid-iteration when credits ran out.
- Six guardrail files installed globally (`~/.claude/rules/eval-first.md`, `~/.claude/rules/model-tier.md`, three DoD templates, pre-deploy hook).

## What's next (when credits topped up)

1. Raise langdetect threshold to 25 chars in `visual_matrix.py` — kills false positives on short skill categories.
2. Re-tighten prompt cap rule for `summary` (T2 hit 56 words / 50 cap).
3. Re-run `visual_matrix.py` — expect 6-8/8 pass.
4. Iterate until 8/8.
5. Update global `~/.claude/CLAUDE.md` with new model policy (no Haiku ever).
6. Commit + push.

## Live endpoints

- App: https://cv-optimizer.pages.dev
- Worker health: https://cv-optimizer-api.debanjan186.workers.dev/api/health
- Mobile status (this page rendered): https://cv-optimizer.pages.dev/status.html

## Recent commits

- `3fca347` feat(cv_optimizer_v2): v2.1 — reliability rebuild + profile enrichment
- `8ab397b` chore(cv_optimizer_v2): record live KV namespace IDs after deploy
- `48a442d` feat(anthropic_watch): v1 daily watcher routine + seeded ledger
