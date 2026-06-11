# Anneal Upgrade Audit (2026-06-11)

Local repo: `C:\Users\deban\dev\anneal\`
Memory snapshot: 2026-05-25 — v0.1 shipped, 136 tests, 20 commits unpushed.

## Summary

- HIT (clear upgrade opportunity): 3
- MAYBE (worth investigating): 2
- OK (already implements well): 5
- N/A: 1 (canary/health — CLI library, not a deployed service)

## Top 3 Upgrades

1. **Dynamic Workflow / batch mode** — No `--repos` or `--batch` flag exists. Can't run `anneal all 50 PRs` today without a shell loop. Adding `anneal batch <refs-file>` with `ThreadPoolExecutor` parallelism across repos is a single file change (cli.py + loop_classic call site). High leverage: removes the #1 friction when using anneal across a monorepo or multiple PRs.

2. **CLAUDE.md missing** — The anneal repo has no `CLAUDE.md`. Claude Code sessions on that repo start cold every time. A 100-line CLAUDE.md covering: key entry points (cli.py → loop_classic/loop_adversarial), test run command, tier explanation, Windows subprocess hardening rules, and the anneal-inside-anneal bootstrap warning would pay off on every future work session.

3. **`--mode` unification** — The CLI currently uses subcommands (`classic` / `adversarial`) rather than a `--mode` flag. The workspace `execution/_TEMPLATE.py` convention uses `--mode`. This is a cosmetic API inconsistency — `anneal --mode classic HEAD` vs `anneal classic HEAD` — that matters if you ever call anneal from workspace scripts. Fixing it is a 30-line argparse shim (preserve subcommand for backward compat, add `--mode` alias).

## Per-Axis Scorecard

| # | Dimension | Score | Evidence |
|---|-----------|-------|----------|
| 1 | Dynamic Workflow candidate (batch/parallel across diffs)? | **HIT** | No `--repos` / `--batch` flag in cli.py. VotingJudge already uses `ThreadPoolExecutor` for per-finding parallelism; extending to per-repo would reuse the same pattern. |
| 2 | Declarative exit criteria? | **OK** | README + CHANGELOG define convergence precisely: N consecutive PASS rounds, oscillation, patch_conflict, budget, max_rounds. Exit codes 0/1/2 documented. `AnnealResult.reason` is the machine-readable predicate. |
| 3 | `--mode` flag opportunity? | **MAYBE** | CLI uses subcommands (`classic`, `adversarial`) not `--mode`. Tiers (`--tier cheap/balanced/premium/ultra/cheap-gemini`) are already a `--mode`-style flag and match the pattern. Subcommand form is arguably cleaner for a standalone CLI; a shim alias is the compromise. |
| 4 | Sub-agent opportunities missed? | **MAYBE** | The classic loop is fully sequential — one auditor call, then one fixer call, per round. The VotingAuditor runs N audit samples sequentially (per `audit/voting.py` docstring: "calls are sequential"). A parallel audit path (ThreadPoolExecutor over N samples, same pattern as `loop_adversarial.py`'s parallel Judge) would cut wall-clock time on `--audit-samples 3` by ~2x. Low-risk addition. |
| 5 | Python-on-Windows hardening | **OK** | All 5 rules verified: (a) subprocess encoding — `worktree.py` and `patch.py` pass `encoding="utf-8", errors="replace"`; ruff/semgrep runners decode bytes manually with `errors="replace"`. (b) threading locks — `CostTracker._lock` guards all `+=` mutations; `SuppressionStore._lock` guards all writes. (c) except-pass — only 3 bare `except Exception` blocks found, all commented with safe-to-swallow rationale (`# noqa: BLE001`, BudgetExceeded comment, fingerprint fallback). (d) cache-aware pricing — 4-field `_ModelPricing` TypedDict with separate `input/cache_read/cache_write/output`; test suite covers all 3 cache paths. (e) LLM path validation — `_security_check_test_path()` in `python_test_runner.py` uses `.resolve()` + `relative_to()` check. |
| 6 | Note capture / docs gap? | **HIT** | No `.claude/notes/` in the anneal repo (only `.claude/skills/anneal/SKILL.md`). No session knowledge log. Learnings from the v0.1 build live only in CHANGELOG.md and the workspace memory. |
| 7 | Agent Team candidate (Red-vs-Blue)? | **OK** | Adversarial mode is already implemented with specialized Red agents (security-red, perf-red, logic-red + coordinator), Blue, and VotingJudge. `loop_adversarial.py` uses `ThreadPoolExecutor` for parallel Judge calls. The multi-agent architecture is in place. |
| 8 | Canary/health gap? | **N/A** | CLI library — not a deployed service. The `anneal canary` subcommand serves a similar self-validation purpose for the tool itself. |
| 9 | CLAUDE.md exists? | **HIT** | No CLAUDE.md found in `C:\Users\deban\dev\anneal\`. The repo has a skill file at `.claude/skills/anneal/SKILL.md` (skill invocation instructions) but no instructions for working *on* the anneal codebase. |
| 10 | Tests + CI | **OK** | 136 unit tests (all mock-based). Test patterns: `test_cost.py` covers cache-aware pricing with 4 token-type scenarios + thread-safety barrier test. `test_python_test_runner.py` exists (path-traversal guard). No CI config (no `.github/workflows/` found) — tests run manually. No subprocess-encoding or threading-lock *negative* test cases (e.g., test that cp1252 bytes don't crash), but the production code is hardened. |

## Cross-Cutting Opportunities

**Parallel VotingAuditor.** The classic loop supports `--audit-samples N` but runs samples sequentially inside `VotingAuditor`. The adversarial loop already has the right pattern: `ThreadPoolExecutor` with `cfg.judge_max_workers`. Mirroring that for audit sampling would reduce wall-clock time for voting rounds without touching the loop logic — just a `ThreadPoolExecutor` inside `audit/voting.py`. The `CostTracker` is already thread-safe (verified), so no extra locking needed.

**Batch entrypoint.** The workspace uses anneal as `py -m anneal.cli classic --diff-file <patch> --repo <path>` in mobile-app phase hooks. If multiple phases run concurrently, there's no way to fan out to N repos in a single `anneal` call today. A `anneal batch <file-of-refs>` subcommand that reads a newline-delimited list of `--repo <path> <ref>` pairs and runs them in parallel (reporting per-repo results + aggregate cost) would unblock "anneal all open PRs" as a single command. Estimated implementation: 80 LOC in cli.py + a trivial batch runner module.

## Don't Bother

- **`--mode` alias for subcommands** — The subcommand UX (`anneal classic HEAD`) is actually more ergonomic than `anneal --mode classic HEAD`; only matters if workspace shell scripts hard-code `--mode`. Low value unless you're specifically harmonizing with `execution/_TEMPLATE.py` conventions and calling anneal programmatically at scale.
- **SWE-Bench Lite** — Already explicitly PARKED in CHANGELOG (T2.9, ~$20 estimated cost). Not worth reopening.
- **`replay-am` / `show` stubs** — Marked Phase 5, correctly deferred. AM project is frozen anyway.
- **CLAUDE.md for the anneal repo proper formatting** — Seeding a 50-line CLAUDE.md is the upgrade (axis 9 HIT above), but it doesn't need to be elaborate — key files + test command + one-line tier explanation is sufficient.
