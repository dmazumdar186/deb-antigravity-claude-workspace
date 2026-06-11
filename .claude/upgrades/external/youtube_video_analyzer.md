# YouTube Video Analyzer — Upgrade Audit
**Date**: 2026-06-11
**Repo**: `C:\Users\deban\dev\youtube-video-analyzer\`
**Public**: github.com/dmazumdar186/youtube-video-analyzer
**Version audited**: v4.1 (batch + creator-profile + content-first breakdown)
**Test count at audit**: 114 tests across 9 files (README claims; prior memory says 41 new in v4)

---

## D1 — Dynamic Workflow candidate (batch fan-out)

**Finding: SERIAL-SEQUENTIAL by default; opt-in `--parallel N` exists but is shallow.**

The `_run_batch()` function (line ~1767) uses `ThreadPoolExecutor(max_workers=N)` when `--parallel N > 1`.
The vault write is protected by `_VAULT_WRITE_LOCK` (line 83 / 1473). The `results` list is
collected via `concurrent.futures.as_completed()` — each future returns a complete result dict,
no shared mutable accumulator. Threading safety is correct for the vault path.

However, `--parallel` is documented as "opt-in to avoid YouTube IP-blocks" — the skill defaults
to sequential (N=1). For a true Dynamic Workflow (fan-out via agent SDK), the value would be
launching one sub-agent per URL with its own context window. Not done; not needed for a CLI tool.
No action required.

**Grade: ADEQUATE** — threading safety is clean; parallel is opt-in and well-justified.

---

## D2 — Declarative exit criteria in README/docs

**Finding: GOOD — machine-readable dry-run JSON + documented cost table.**

README describes two dry-run modes: `--dry-run` (shallow, instant JSON) and `--deep-dry-run`
(full pipeline sans AI call, accurate token/cost estimate). The `would_*` field contract is
documented in both README and SKILL.md. Cost table present with per-tier estimates.

One gap: no explicit "done criteria" for the batch run — the summary file
(`.tmp/video/_batch_{run_id}/summary.md`) is written but its schema is not documented
in README. Minor.

**Grade: GOOD** — exit criteria clear for single URL; batch summary schema undocumented.

---

## D3 — `--mode`/tier flag coverage (cheap / balanced / premium)

**Finding: FULLY COVERED — maps to `--tier {default,premium,gemini}`.**

| CLAUDE.md tier | `--tier` flag | Model (at audit) | Cost |
|---|---|---|---|
| cheap | `gemini` | Gemini 2.5 Flash | $0.00 |
| balanced | `default` | Claude Sonnet 4.6 | ~$0.032 |
| premium | `premium` | Claude Opus 4.7 | ~$0.16 |

The `model_registry.py` resolves model IDs at runtime with a 7-day cache and
`LAST_KNOWN_GOOD` fallback. ALLOWED_FAMILIES allowlist prevents rogue model selection.

Note: SKILL.md uses `--tier` (correct) not `--mode`. Naming inconsistency
vs. the audit axis label is cosmetic — the functionality is complete.

**Grade: PASS**

---

## D4 — Sub-agent opportunities missed

**Finding: LOW PRIORITY — not a multi-step agent workflow.**

The tool is a CLI script, not an agent pipeline. The creator-profile distillation
(triggered after video #3 from a channel) calls the LLM inline in `creator_profiles.py`,
not as a sub-agent. For a CLI tool this is correct — the LLM call is a single synchronous
step, not a branching decision tree that benefits from delegation.

Potential future upgrade: if the tool grows to "research a creator across 50+ videos",
the distillation step could be a parallel sub-agent per channel. Not warranted at current scale.

**Grade: N/A (CLI tool — no sub-agent model applies)**

---

## D5 — Python-on-Windows hardening (subprocess + encoding)

**Finding: MAIN SCRIPT CLEAN; 3 test files have bare `text=True` without `encoding=`.**

**Main script (`youtube_video_analyzer.py`):**
- Line 66-68: `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at module load.
- Line 663: The only `subprocess.run()` call in the main script includes `encoding="utf-8", errors="replace"`. PASS.
- All file I/O (`write_text`, `read_text`) explicitly specifies `encoding="utf-8"`. PASS.
- `threading.Lock()` (`_VAULT_WRITE_LOCK`) guards the only shared filesystem write in
  parallel mode (vault). PASS.
- No bare `except Exception: pass` — the one at line 68 wraps `reconfigure()` and is
  a legitimate platform-guard (Python < 3.7 fallback). PASS.
- LLM-supplied path validation: `slugify()` sanitizes titles; `WORKSPACE_ROOT`-relative
  paths used throughout. No `resolve().is_relative_to()` check on the Obsidian vault path
  — a user-supplied `--obsidian-vault` argument could theoretically point outside expected
  boundaries, but this is a user-controlled flag not LLM-derived input. LOW risk.

**Test files with missing `encoding=` on subprocess calls (non-fatal on Windows, but violates rule 1):**

| File | Line(s) | Issue |
|---|---|---|
| `tests/test_sanity.py` | ~76, ~91 | `capture_output=True, text=True` — no `encoding="utf-8"` |
| `tests/test_monkey.py` | ~24-26 | `capture_output=True, text=True` — no `encoding="utf-8"` |
| `tests/test_performance.py` | ~30-32, ~128-130 | Same |
| `tests/test_e2e.py` | ~30, ~146 | Same |
| `tests/canary_check.py` | ~154-156 | `git rev-parse` call — no `encoding=` |
| `tests/test_unit.py` | ~161-163, ~169-171 | Help/dry-run calls — no `encoding=` |

`tests/test_batch.py`, `tests/test_sanity.py` (S2 only), and `canary_check.py` dry-run
check DO include `encoding="utf-8"`. Inconsistent across the test suite.

**Risk level**: LOW in practice (tests call Python subprocesses, output is ASCII-safe),
but technically non-compliant with the hardening rule on this machine (Windows cp1252).
If a video title containing cp1252-unsafe chars appears in test stderr, the `_readerthread`
exception would surface.

**Grade: MAIN SCRIPT PASS / TEST SUITE MINOR VIOLATIONS (6 files)**

---

## D6 — Note capture / docs

**Finding: ADEQUATE — README is comprehensive; no `.claude/notes/` file for this external repo.**

README documents all CLI flags, tiers, cost, architecture, and test suite. SKILL.md is
detailed and up to date (references v4.1 batch summary + takeaways sections). No stale
doc detected.

No `.claude/notes/execution/video/youtube_video_analyzer.md` exists in the workspace
(the script lives at `execution/video/youtube_video_analyzer.py` per SKILL.md but the
source is in the external standalone repo). This is a structural gap — learnings from
running the tool don't have a capture location in the workspace's notes system.

**Action**: Create `.claude/notes/execution/video/youtube_video_analyzer.md` in the
workspace to capture future API quirks, rate-limit learnings, etc.

**Grade: ADEQUATE** — README excellent; workspace notes file missing.

---

## D7 — Agent Team candidate

**Finding: N/A — CLI tool; no agent team architecture applies.**

A "team" (Orchestrator + specialized sub-agents) would only add overhead here.
The creator-profile distillation is the closest analog, and it's correctly
handled as a single synchronous LLM call.

**Grade: N/A**

---

## D8 — Canary / health monitoring

**Finding: CLI TOOL — canary N/A; but `tests/canary_check.py` is a functional local canary.**

The tool is a CLI script with no deployed service, so the canary_monitoring.md pattern
(external HTTP probe on `/api/health`) does not apply.

However, `tests/canary_check.py` is a well-structured health check that verifies:
secrets presence, dependency importability, ffmpeg binary, OR endpoint reachability,
YouTube reachability, model registry cache age, and a `--dry-run` smoke test. It emits
structured JSON. This is the correct pattern for a CLI tool.

No external scheduler invokes it — it's run manually. For the public repo, a GitHub
Actions cron (e.g., weekly) running `canary_check.py` would catch dep version breakage
or YouTube API changes before users hit them. Not currently present (no `.github/`
directory detected).

**Grade: LOCAL CANARY GOOD / NO CI CRON**

---

## D9 — CLAUDE.md / workspace best practices

**Finding: 3 gaps vs. workspace standards.**

1. **No `execution/video/youtube_video_analyzer.py` symlink or proxy in workspace.**
   SKILL.md calls `py execution/video/youtube_video_analyzer.py` but the actual script
   lives in the external repo at `C:\Users\deban\dev\youtube-video-analyzer\`. If the
   skill is invoked from the workspace, it will fail unless the workspace path resolves
   (likely via a copy or PATH-level alias). This is a latent breakage risk.
   Confirm the skill actually calls the external repo path; update SKILL.md if the command
   needs an absolute path.

2. **No workspace notes file** (see D6 above).

3. **`model_registry.py` `LAST_KNOWN_GOOD` has a model ID inconsistency**:
   OpenRouter IDs use dot-notation (`claude-sonnet-4.6`, `claude-opus-4.7`) while the
   Anthropic direct IDs use dash-notation (`claude-sonnet-4-6`, `claude-opus-4-7`).
   This is intentional (OpenRouter uses `.` in its slugs), but worth noting as a
   maintenance trap when updating model IDs — easy to mix the two conventions.

**Grade: MINOR GAPS**

---

## D10 — Tests + CI

**Finding: TEST SUITE STRONG; NO CI; ENCODING GAPS IN TESTS.**

**Strengths:**
- 114 tests across 9 tiers (unit, integration, e2e, sanity, performance, monkey/chaos,
  canary, batch, creator-profile). Coverage is broad.
- Monkey tests cover SSRF, XSS params, path traversal, tampered cache, empty API key.
- Performance tests assert wall-clock threshold for dry-run (fast startup).
- Batch tests cover `--urls-file`, fail-fast validation, exit codes, summary file creation.
- Creator-profile tests mock the LLM distillation call — no API spend in CI.

**Gaps:**
- No `.github/workflows/` — zero CI automation. All tests are manual. For a public repo
  this means regressions land in the published version.
- Encoding compliance on subprocess calls in tests: 6 test helpers call subprocess with
  `text=True` but no `encoding="utf-8"` (see D5). These should be harmonized with the
  compliant calls in `test_batch.py` and `test_sanity.py` S2.
- No test for the `--deep-dry-run` path (full pipeline without AI call). The integration
  test covers `--dry-run` but not `--deep-dry-run`.
- No test for `--obsidian-vault` path (vault write with `_VAULT_WRITE_LOCK`).

**Grade: GOOD COVERAGE / NO CI / 3 TEST GAPS**

---

## Summary Card

| # | Dimension | Grade | Action |
|---|---|---|---|
| D1 | Dynamic Workflow / fan-out | ADEQUATE | None — opt-in `--parallel` is correct |
| D2 | Exit criteria in docs | GOOD | Document batch summary JSON schema in README |
| D3 | Tier flag (`--tier`) | PASS | None |
| D4 | Sub-agent opportunities | N/A | None |
| D5 | Python-on-Windows hardening | MAIN PASS / TEST MINOR | Add `encoding="utf-8"` to 6 test helper `subprocess.run()` calls |
| D6 | Note capture / docs | ADEQUATE | Create `.claude/notes/execution/video/youtube_video_analyzer.md` |
| D7 | Agent Team candidate | N/A | None |
| D8 | Canary / health | LOCAL GOOD | Add GitHub Actions weekly cron for `canary_check.py` (optional, public repo) |
| D9 | CLAUDE.md best practices | MINOR GAPS | Verify SKILL.md script path resolves in workspace; add notes file |
| D10 | Tests + CI | GOOD / NO CI | Add GitHub Actions CI; add `encoding=` to 6 test helpers; add `--deep-dry-run` and `--obsidian-vault` tests |

---

## Prioritized Actions

**P1 (1-line fixes, low risk):**
- Add `encoding="utf-8", errors="replace"` to 6 test helper `subprocess.run()` calls
  in `test_sanity.py`, `test_monkey.py`, `test_performance.py`, `test_e2e.py`,
  `canary_check.py`, `test_unit.py`. Pattern: copy from `test_batch.py:58-63`.

**P2 (workspace hygiene):**
- Verify SKILL.md invocation path `execution/video/youtube_video_analyzer.py` actually
  resolves from the workspace working dir. If not, update SKILL.md to use the absolute
  external repo path.
- Create `.claude/notes/execution/video/youtube_video_analyzer.md` in this workspace.

**P3 (test coverage):**
- Add `--deep-dry-run` test (calls the full frame pipeline mock).
- Add `--obsidian-vault` integration test to verify vault write + lock behavior.
- Document batch summary JSON schema in README.

**P4 (CI — optional for public repo):**
- Add `.github/workflows/tests.yml` running `py -m pytest tests/test_sanity.py tests/test_unit.py tests/test_monkey.py tests/test_batch.py tests/test_creator_profile.py -v` (no-download tests only).
- Add weekly `canary_check.py` cron job in the same workflow.

---

## Workspace Skill Coordination Note

Any CLI change to `youtube_video_analyzer.py` requires a coordinated update to
`.claude/skills/youtube-video-analyzer/SKILL.md`. Specifically:
- New flags must be added to both the CLI reference block and the Step 4 examples.
- New tiers/providers must update the cost table.
- The SKILL.md `--deep-dry-run` description (Step 3) should be kept in sync with
  any changes to what that flag does in the pipeline.
