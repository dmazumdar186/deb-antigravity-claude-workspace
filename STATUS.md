# Workspace Status

> Live status page reads this file. Edit anytime; mobile reload picks it up immediately.
> Last updated: 2026-06-14 evening

## Current focus

**CV Optimizer v2.1** — now on free-tier Gemini 2.5 Flash. Eval at 5/8 deep-pass.

## Pivot today (cost-zero architecture)

You can't load less than $20 on the Anthropic API. That's the wrong economics for a personal tool that runs ~50 calls/year. Pivoted: the Worker now calls Gemini 2.5 Flash (free tier, 250 req/day) instead of Anthropic Sonnet. Same prompt, same schema, same architecture — provider swap only.

## Active blocker

**Gemini free-tier daily quota exhausted** by today's deep-eval iterations (30+ Worker calls × 8 tests = ~240, plus retries). Resets ~9am Paris time (midnight Pacific). No payment required — quota comes back automatically.

## What was done today

- Phase A-F shipped (two-phase orchestration, prompt SST, Firecrawl retry, 26 unit tests, prompt cleanup, profile enrichment from GitHub).
- Deep-eval harness built: `py .tmp/cv_test/visual_matrix.py` runs 8 (CV, JD) combos with per-field langdetect, headless Chromium render to PNG, recruiter 2-second proxies, JD keyword density.
- Old test_matrix.py "9/9 PASS" was a hollow signal; deep eval revealed real gaps.
- Tried Sonnet 4.6 — improved but $20 minimum top-up blocked further iteration.
- Pivoted to Gemini 2.5 Flash — 5/8 deep-pass on the run that completed. Visual output is recruiter-scannable.
- Mobile dashboard live at https://cv-optimizer.pages.dev/status.
- Desktop shortcut "Claude Remote Control" installed for one-click remote-control launch.
- Six guardrail files installed globally (`~/.claude/rules/`, `~/.claude/templates/`).

## What's next (tomorrow when quota resets)

1. Re-run `visual_matrix.py` — confirm 5/8 baseline holds.
2. Look at the failing tests (T7 had a real content error, T5/T8 were 429s — re-test).
3. Iterate prompt for remaining failures.
4. Target: 8/8 deep-eval pass on Gemini free tier.
5. Update global `~/.claude/CLAUDE.md` with cost-aware model policy.
6. Commit + push.

## Mobile workflow

- Read-only status: this page (bookmark on phone home screen).
- Drive Claude from phone: claude.ai/code (uses your Claude Web subscription — no API spend).
- Phone → laptop file edits: double-click **"Claude Remote Control"** shortcut on Desktop, connect from phone via printed URL.

## Live endpoints

- App: https://cv-optimizer.pages.dev
- Worker health: https://cv-optimizer-api.debanjan186.workers.dev/api/health
- Mobile status: https://cv-optimizer.pages.dev/status

## Recent commits

- `80d52af` feat: mobile status page + Sonnet 4.6 upgrade + remote-control directive
- `3fca347` feat(cv_optimizer_v2): v2.1 — reliability rebuild + profile enrichment
- `8ab397b` chore(cv_optimizer_v2): record live KV namespace IDs after deploy
