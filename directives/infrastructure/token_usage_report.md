# Token Usage Report

## Goal
Measure actual Claude Code token consumption by model, day, skill, and sub-agent from local session transcripts, so the token-economy doctrine (`.claude/rules/token-economy.md`) is managed from data instead of guesses. Primary questions it answers: is the 5-hour cap burn dropping, is Fable being reserved for judgement, which skills are never invoked (archive candidates), and is delegation actually happening.

## Inputs
- `--days N` — lookback window (default 7).
- `--json` — machine-readable output.
- Reads transcripts from `~/.claude/projects/**/*.jsonl` (or `$CLAUDE_CONFIG_DIR/projects`). Must run on the machine where Claude Code runs — cloud sessions only see their own container's transcripts.

## Tools / Scripts
- `execution/infrastructure/token_usage_report.py`

## Outputs
- Table (or JSON): per-model calls, input/cache_read/cache_write/output tokens, cache-aware estimated cost; per-day cost; skill invocation counts; sub-agent spawn counts.
- The dollar figure is an API-price **proxy** for subscription cap burn — the cap's weighting is unpublished but tracks model cost, so relative comparisons (week over week, model vs model) are sound; absolute dollars are not a bill.

## Steps
1. Run `python3 execution/infrastructure/token_usage_report.py` (on Windows: `py`).
2. Read the model split: Fable's share should be mostly judgement turns; if Fable dominates raw volume, delegation is failing — re-read the token-economy rule.
3. Read skill invocations: any skill at zero across a month is an archive candidate (`git mv` to `docs/reference/skills-archive/`).
4. Read sub-agent spawns: healthy sessions show Explore/general-purpose spawns; zero spawns on multi-file work means the main thread is grinding.
5. Weekly cadence (or when limits pinch): compare against the prior week's numbers.

## Edge Cases
- Missing transcript dir → exits 1 with a message (wrong machine, or fresh install).
- Malformed JSONL lines and `<synthetic>` model entries are skipped silently; unreadable files warn to stderr and are skipped.
- Unknown model ids fall back to Opus-level pricing (conservative overestimate) — add new models to `PRICING` (4 entries each: input, cache_read 0.1x, cache_write 1.25x, output).
- Pricing drifts: verify against platform.claude.com before trusting absolute dollars.

## Changelog
- 2026-09-01: Created as part of the token-economy sweep (measurement loop — manage from data, not guesses).
