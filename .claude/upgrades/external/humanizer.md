# Humanizer — Upgrade Audit (Phase E.2)
_Audited: 2026-06-11 | Repo: C:\Users\deban\dev\humanizer\ | Read-only_

## Repo snapshot

- Pipeline: 4-stage — deterministic pre-pass (regex AI-tell stripping) → voice profile lookup
  → LLM rewrite via tool-use (structured output) → platform post-processing
- Entry point: `humanizer.py` (flat-repo, no src/ layout)
- Sibling module: `model_registry.py` (dynamic model ID resolution, 7-day local cache)
- CLI flags: `--text | --file | stdin`, `--voice`, `--platform`, `--max-length`, `--show-diff`,
  `--keep-em-dashes`, `--tier {default,premium,gemini}`, `--dry-run`
- Test count: 107 across 8 files (unit, integration, e2e, sanity, performance, monkey, resilience,
  canary_check.py)
- CI: NO GitHub Actions workflow found (`.github/` directory absent)
- Voice profiles: `voices/` directory; `_template.json` + at least `debanjan.json`
- Model path: OR → Anthropic-direct fallback → Gemini free (`GEMINI_API_KEY`)
- CLAUDE.md: NOT present in repo

---

## Dimension scores

| #  | Dimension                    | Score | Finding |
|----|------------------------------|-------|---------|
| 1  | Dynamic Workflow (batch)     | HIT   | No batch mode; single-text only; fan-out of N drafts is common use case |
| 2  | Declarative exit criteria    | HIT   | README is usage-only; no "done when X" / success definition anywhere |
| 3  | `--tier` flag                | OK    | `--tier default\|premium\|gemini` fully implemented; maps Sonnet/Opus/Gemini |
| 4  | Sub-agent opportunities      | MAYBE | Single-file monolith; no internal delegation. Acceptable for current size. |
| 5  | Python-on-Windows hardening  | MAYBE | Mostly good; 4 of 5 rules pass. See detail below. |
| 6  | Note capture / docs          | HIT   | No `.claude/notes/` in repo; no known-quirks section in README |
| 7  | Agent Team candidate         | HIT   | "Humanizer council" overlap with anneal v0.2 roadmap; multi-rewrite + judge pattern fits |
| 8  | Canary/health                | N/A   | CLI tool; `canary_check.py` already provides a local health probe |
| 9  | CLAUDE.md best practices     | HIT   | No CLAUDE.md in repo; should be seeded |
| 10 | Tests + CI                   | MAYBE | 107 tests strong; no CI pipeline; one bare `except Exception: pass` in test_monkey.py |

---

## HIT details

### D1 — Dynamic Workflow: no batch mode

The CLI accepts exactly one text input per invocation. The most common real-world use case (as
invoked by the workspace skill) is humanizing a single draft — but the workspace skill's own
trigger list mentions "batch of drafts" implicitly (the skill SYSTEM.md description says it
fires when a user pastes AI-generated text to "send to [person/platform]", implying repeated
calls per draft).

Adding `--batch` (accept a JSONL file of texts, fan out via `concurrent.futures.ThreadPoolExecutor`)
would allow `ultracode:` orchestration for multi-draft campaigns. Typical shape:

```bash
py humanizer.py --batch drafts.jsonl --tier gemini --platform linkedin
# outputs: humanized_drafts.jsonl (one JSON result per line)
```

Impact: HIGH for any campaign where 5–20 AI-drafted cold emails need humanizing before send.
Effort: LOW — the existing pipeline is stateless per call; just wrap in a thread pool with the
same safety patterns already in `test_performance.py::test_perf_concurrent_dry_runs`.

**Workspace skill impact**: if `--batch` is added, SKILL.md Step 2–5 would need a batch workflow
branch. Low coordination cost since batch is purely additive.

### D2 — Declarative exit criteria

README is organized as: Demo → Quick Start → Three Tiers → Key Features → CLI Reference →
Adding a Voice → Testing → Environment Setup. No section defines what "success" means for the
pipeline — e.g., "humanized text must differ from input by at least N chars AND score <X on
AI-detect". This matters for the workspace skill's Step 5 ("hand back the cleaned text") — there
is no machine-checkable threshold, only human judgment.

Quick win: add an `## Exit Criteria` block to README:

```markdown
## Exit Criteria
A run is successful when:
1. returncode == 0
2. stdout is non-empty and differs from the raw input
3. No AI-tell patterns from the pre-pass regex list appear in the output
4. Output length <= --max-length (or 280 for tweet)
```

Effort: 15 minutes, pure docs.

### D6 — Note capture / docs

No `.claude/notes/` directory in the repo. Known quirks worth capturing:
- `canary_check.py` runs outside pytest; must be invoked directly (`py tests/canary_check.py`)
- `--dry-run` gives cost estimate using static per-million rates, not live usage (over-estimates
  under prompt caching)
- `model_registry.py` caches to `.tmp/model_registry.json` — delete to force re-fetch on model
  changes
- Windows stdout must be reconfigured to UTF-8 before any output (already done at top of
  `humanizer.py` lines 33–37; if forked, preserve this block)

Seeding `.claude/notes/` is low-effort and prevents re-discovering these in future sessions.

### D7 — Agent Team candidate: humanizer council mode

The anneal v0.2 roadmap mentions "humanizer-council overlap." The current pipeline is
single-LLM: pre-pass → one LLM rewrite → post-process. A council mode would:

1. Fan out to 2–3 LLMs in parallel (e.g. Gemini Flash, Sonnet, Opus) — each produces a
   humanized variant.
2. A judge agent (lightweight; could be Haiku) scores variants on: AI-tell absence, voice match,
   platform fit, length compliance.
3. Best variant returned.

This maps cleanly to the Agent Teams pattern now available in CLI v2.1.173. The `.claude/agents/`
directory would hold `humanizer-drafter.md` and `humanizer-judge.md`. Worth building if the
workspace moves to v2.1.173 features and council mode is prioritized on the anneal roadmap.

**Workspace skill impact**: a council mode would require a new `--council` flag or a separate
`humanizer_council.py` script. SKILL.md would need a new "council mode" step. Coordinate
SKILL.md update at the same time as the repo change.

### D9 — CLAUDE.md: missing

No CLAUDE.md in the humanizer repo. Recommended seed content (under 50 lines):

- Architecture summary (4-stage pipeline, flat layout, model_registry sibling)
- Where to add voices (`voices/`)
- Test structure (8 test files, pytest for sanity/monkey/e2e; direct-run for unit/perf/resilience)
- Known Windows hardening blocks (stdout reconfigure, encoding on subprocess)
- Workspace skill reference (`AntiGravity Project Space/.claude/skills/humanizer/SKILL.md`)
- Exit criteria (from D2 above)

---

## D5 — Python-on-Windows hardening detail (MAYBE, not HIT)

Rule-by-rule assessment:

| Rule | Status | Evidence |
|------|--------|---------|
| 1. subprocess `encoding="utf-8", errors="replace"` | PARTIAL | `test_monkey.py`, `test_resilience.py`, `test_e2e.py`, `test_sanity.py`, `test_performance.py`, `test_integration.py` all pass. `test_unit.py` _run_cli uses `encoding="utf-8"` but omits `errors="replace"` (line 296). `canary_check.py` subprocess calls have no `encoding=` at all (lines 90, 111, 155, 174, 187, 210). |
| 2. Threading locks on shared state | OK | `ThreadPoolExecutor` used only in `test_performance.py::test_perf_concurrent_dry_runs` — threads call subprocess (each isolated process); no shared Python mutable state. No lock needed here. |
| 3. `except Exception: pass` | MINOR | `test_monkey.py` line 64: bare `except Exception: pass` with no log line. Test code only; runtime code is clean. |
| 4. Cache-aware Claude pricing (4 entries) | MISS | `_TIER_COST_PER_M` has only `input` + `output` per tier; missing `cache_read` (0.1×) and `cache_write` (1.25×). Cost estimates over-report under prompt caching (though humanizer prompts are short so impact is small). |
| 5. LLM-supplied path validation | OK | `load_voice()` implements `.resolve()` + `is_relative_to(VOICES_DIR)` guard at lines 156–158. |

Two minor issues: `canary_check.py` subprocess calls lack encoding params; pricing table missing
cache entries. Neither is a crash risk at current scale, but worth fixing before the repo is
shared more widely.

---

## Workspace skill impact summary

The SKILL.md at `.claude/skills/humanizer/SKILL.md` hardcodes the script path as
`execution/content/humanizer.py` (workspace copy reference). The repo at
`C:\Users\deban\dev\humanizer\humanizer.py` is the source of truth. Any CLI additions need to
be mirrored into the SKILL.md command examples:

| Proposed change | SKILL.md update needed |
|-----------------|----------------------|
| `--batch` flag | Yes — new Step 2b for batch workflow |
| `--council` flag / council mode | Yes — new step or separate skill branch |
| Declarative exit criteria docs | No — README only |
| Cache-aware pricing fix | No — internal cost calc only |
| CLAUDE.md seed | No — repo-internal |

---

## Quick wins (no-deps, <1h each)

1. **Declarative exit criteria in README** — add `## Exit Criteria` block. 15 min, docs only.
2. **Fix `canary_check.py` subprocess calls** — add `encoding="utf-8", errors="replace"` to all
   6 subprocess.run calls. 20 min, no logic change.
3. **Add `cache_read` / `cache_write` to `_TIER_COST_PER_M`** — even if humanizer prompts are
   short, the pricing model should be correct for when voice profiles grow. 10 min.
4. **Seed CLAUDE.md** — 30 min; paste architecture + test structure + Windows quirks + skill ref.
5. **Fix bare `except Exception: pass`** in `test_monkey.py:64** — add `log` line or comment
   explaining why swallowing is safe. 5 min.

## Deferred / low-value

- **`--batch` flag**: real value but requires coordinated SKILL.md update; defer to a dedicated
  feature plan when a batch-humanize use case is actively needed.
- **Agent Team / council mode**: high value long-term but depends on anneal v0.2 council mode
  roadmap progressing. Defer until anneal ships council primitives.
- **CI / GitHub Actions**: 107 tests + no CI is a gap, but tests require API keys for non-dry
  runs. A free GitHub Actions workflow running only `test_sanity.py` + `test_monkey.py` (no
  API keys needed) would be quick. Defer — not urgent unless others contribute to the repo.
- **Sub-agent refactor of pipeline**: monolith is small enough (~730 lines) that internal
  sub-agent delegation adds overhead without benefit. Skip.
