# Notes — youtube-video-analyzer (external repo)

External repo: `C:\Users\deban\dev\youtube-video-analyzer\`
Public repo: https://github.com/dmazumdar186/youtube-video-analyzer
Workspace wrapper: `execution/video/youtube_video_analyzer.py` (delegates to external repo)

---

## Status snapshot (as of 2026-06-12)

- [technical] 114 tests across 6 test files: `test_sanity.py`, `test_monkey.py`, `test_performance.py`, `test_e2e.py`, `test_unit.py`, `canary_check.py`. All mock-based (no API calls) except e2e and canary.
- [technical] Test coverage is broad: monkey/chaos tests, SSRF guards, path-traversal guards, performance thresholds, and a dry-run canary.

## SKILL.md path question (row 19 audit)

- [pattern] SKILL.md at `.claude/skills/youtube-video-analyzer/SKILL.md` references `py execution/video/youtube_video_analyzer.py`. The workspace wrapper EXISTS at `execution/video/youtube_video_analyzer.py` — this is correct. The wrapper delegates to the external repo. SKILL.md path is accurate; no change needed.
- [constraint] If the external repo path ever changes (e.g. renamed or moved), update both: (1) `execution/video/youtube_video_analyzer.py` wrapper, and (2) SKILL.md invocation examples.

## Obsidian vault lock pattern

- [technical] `--obsidian-vault <path>` flag writes the breakdown .md into the user's Obsidian vault under `Video Breakdowns/`. The script holds a `_VAULT_WRITE_LOCK` (threading.Lock) to prevent concurrent writes to the vault directory when running in `--parallel N` batch mode.
- [constraint] Never run `--parallel N` without verifying `_VAULT_WRITE_LOCK` is acquired before any vault write. This is already implemented but must be preserved in future refactors.

## Parallel mode

- [technical] `--parallel N` is opt-in. Default is sequential (N=1). The flag was deliberately NOT made the default — sequential is safer for rate-limited API paths and easier to debug.
- [technical] Parallel workers use `ThreadPoolExecutor(max_workers=N)`. Shared state (vault write lock, creator profile cache) is guarded per the lock pattern above.

## Creator profile cache

- [technical] Creator profiles build after 3+ videos from the same channel. Stored at `.tmp/creator_profiles/{channel_id}.json`. Profile updates every 5 additional videos (threshold: 3, 8, 13, …).
- [technical] Distillation pass uses Gemini free tier by default. Falls back to paid if `GEMINI_API_KEY` is absent.
- [pattern] Use `--refresh-creator-profile` to force re-distillation. Use `--no-creator-profile` to skip for a single run.

## Dry-run modes

- [technical] `--dry-run` (shallow): no network, no pipeline. Returns JSON immediately with `would_*` fields + estimated cost. Use for canary checks.
- [technical] `--deep-dry-run`: full pipeline (download + PySceneDetect + frame extraction + grid tiling) but skips the AI API call. Use for accurate token/cost forecasting before a paid run.
- [pattern] Always `--deep-dry-run` first on unfamiliar long videos. Always `--dry-run` for automated canary probes.

## Windows subprocess hardening (row 18 fix)

- [learned] All 6 test files had subprocess.run() calls missing `encoding="utf-8", errors="replace"`. Fixed 2026-06-12 (audit row 18). The compliant reference was already at `tests/test_batch.py:58-63`.
- [technical] `canary_check.py` had `encoding="utf-8"` on the dry-run smoke check but was missing `errors="replace"`. Both kwargs are required together — `errors` is only valid when `encoding` is set, and omitting it still leaves the default error handler (strict) in place.
- [pattern] When adding new subprocess.run() calls in this repo, always include both: `encoding="utf-8", errors="replace"`. The `_run()` helper in each test file is the right place to centralise this — add there, not per-call.

## Tier routing

- [technical] `--tier gemini` + `GEMINI_API_KEY` → Gemini reads the YouTube URL natively (no frame extraction, no download). Completely free on Gemini free quota.
- [technical] `--tier default` with no OR key falls back to Anthropic direct if `ANTHROPIC_API_KEY` is set. Priority: OpenRouter > Anthropic.
- [constraint] `--tier gemini --provider anthropic` is rejected at argparse (test_m12 in test_monkey.py covers this).

## Model registry cache

- [technical] Model registry cached at `.tmp/model_registry.json`. TTL: 7 days. Cache schema: `resolved_at` (ISO), `ttl_days`, per-provider model IDs.
- [technical] `--refresh-models` forces a re-fetch. Use when a new model version needs to be adopted.
- [pattern] If `.tmp/model_registry.json` is absent, the script populates it on first dry-run. The canary check warns if cache age exceeds 7 days.
