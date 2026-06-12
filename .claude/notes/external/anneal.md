# Notes — anneal (external repo)

External repo: `C:\Users\deban\dev\anneal\`
Public repo: https://github.com/dmazumdar186/anneal

---

## Status snapshot (as of 2026-06-12)

- [technical] 136 unit tests (73 before v0.1 session), all mock-based. 20 commits unpushed to remote as of 2026-05-25.
- [technical] `anneal` CLI entrypoint defined in `pyproject.toml` as `anneal = "anneal.cli:main"`. Always run via `py -m anneal.cli` or the `anneal` script — not `python src/anneal/cli.py`.

## Tier routing gotchas

- [technical] `cheap-gemini` tier uses `gemini-2.0-flash` via Gemini direct (`google-genai` SDK). Requires only `GEMINI_API_KEY` — no OpenRouter balance needed. Use this when `OPENROUTER_API_KEY` is present but has $0 credits.
- [technical] T1.1 (tier-1 classic, round 1) is unblockable via `cheap-gemini` — Gemini direct has free quota, so a $0 OpenRouter balance does NOT block a full audit run.
- [technical] `balanced` (default) uses Anthropic direct for Auditor/Fixer and OpenRouter for Judge (`google/gemini-2.5-flash`). Requires both `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY`. If OR is empty, use `cheap-gemini` or `premium`.

## Adversarial mode — Judge model selection

- [technical] Judge model in adversarial mode is tier-dependent: `cheap`/`cheap-gemini` use Gemini Flash; `balanced` uses Gemini Flash (OpenRouter); `premium` uses `claude-haiku-4-5-20251001`; `ultra` uses `claude-sonnet-4-6`.
- [technical] VotingJudge (`--judge-samples N`) runs N parallel Judge calls. Each call goes through the same provider as the single Judge. Parallel calls share a `threading.Lock` for the result accumulator — safe under ThreadPoolExecutor.
- [technical] Judge declares convergence when Red comes up empty two consecutive rounds (not one). Premature convergence is the main false-negative risk in adversarial mode.

## Suppressions DB

- [technical] Suppressions stored in `<repo-root>/.anneal/suppressions.json` (SQLite-backed via `peewee`). Schema: `fingerprint` (16-hex SHA), `reason` (str), `created_at` (ISO), `last_seen_at` (ISO).
- [technical] `SuppressionStore` uses `threading.Lock` around all read-modify-write ops. Safe for parallel audit rounds.
- [pattern] Suppressions survive across runs; they are per-repo (not global). Copy `.anneal/suppressions.json` when moving a project to a new path.

## Windows hardening — this repo is the reference

- [pattern] `sast/ruff_runner.py` and `sast/semgrep_runner.py` are the canonical reference for `subprocess.run(..., encoding="utf-8", errors="replace")`. Crib from these before writing any new subprocess code.
- [pattern] `runner/sandbox.py` is the reference for env-stripped subprocess invocation and LLM-path traversal guard (`resolved.is_relative_to(boundary)`).
- [pattern] `suppressions/store.py` is the reference for `threading.Lock` around concurrent writes.
- [pattern] `cost.py` is the reference for 4-entry-per-model cache-aware pricing (input / cache_read / cache_write / output).

## Cost model

- [technical] `cost.py` pricing last updated 2026-05-25. Check before running `ultra` tier on large diffs — `claude-opus-4-7` input is $15/M tokens.
- [technical] Claude models via Anthropic direct: `cache_read` = 0.1× input; `cache_write` = 1.25× input. Flat-rate estimate over-counts 5–10× on repeated prompts.
- [technical] OpenRouter does NOT uniformly support caching — `cost.py` uses flat blended rates for OR slugs. These are rough proxies for budget-gate enforcement only.

## SAST pre-pass

- [technical] Ruff and Semgrep run before the LLM loop. Findings are injected as a `## Pre-pass findings` section in the auditor prompt. The LLM auditor is instructed NOT to re-report SAST findings — it focuses on what SAST cannot catch (logic, contracts, cross-file breakage).
- [technical] Repo-graph context (Python symbol extractor + caller index) is also injected as `## Repo-graph context`. Use this section to spot cross-file parameter renames or removed methods.

## Canary suite

- [technical] `anneal canary --subset all` runs planted-bug regression fixtures in `src/anneal/canary/fixtures/planted_bugs/`. Each fixture has `before.py` and `after.py`. The canary verifies anneal finds the bug in `before.py` and the fix is present in `after.py`.
- [technical] `.canary/` at repo root stores canary run artifacts. The 2026-05-25 run at `.canary/20260525T161750Z/` shows all 12 planted-bug classes detected.

## Skill

- [technical] Workspace-level skill at `.claude/skills/anneal/SKILL.md` — body is TBD (Phase 6). The skill name is `anneal`; triggers on "anneal this", "audit-fix loop", "harden this diff", "red blue this", or `/anneal`.
- [constraint] Repo-level `CLAUDE.md` created 2026-06-12 (row 16). It documents architecture, entry points, test command, tiers, key files, Windows quirks, and contribution guide.
