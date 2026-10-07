# Jev skill picker (use case 9 — let Jev pick the right skill)

## Goal
Given a prompt, pick the workspace skill to load (or `none`) in one sub-second Jev `choice` call,
instead of letting the main model deliberate over dozens of skill descriptions. Benchmark it
against a labelled set and, optionally, against `anthropic/claude-sonnet-5.5`.

## Relation to the router
Same menu, same call. `execution/infrastructure/jev_router.py` already asks this question inside
the UserPromptSubmit hook when `/jev on` (`skills_menu()` + the `skill` question in `classify()`).
This CLI reuses `skills_menu()` and exists for **manual picks and benchmarking**; it adds an optional
two-stage pass the hook does not run (hook latency budget).

## Inputs
- Env `OPENROUTER_API_KEY` (aliases `OPENROUTER_API_TOKEN`, `OPENROUTER_API_TOEKN`).
- Menu: every `.claude/skills/*/SKILL.md` without `disable-model-invocation: true`.
- Bench spec: `execution/infrastructure/jev_specs/skill_bench.json` (20 cases, 3 expect `none`).

## Tools
`execution/infrastructure/jev_skill_pick.py`
- `pick "<prompt>" [--json] [--top-k 3] [--min-confidence 0.5]` — skill, confidence, top-5
  probabilities, `.claude/skills/<name>/SKILL.md` path. If top confidence < min, stage 2 asks Jev
  again over the top-k shortlist (+`none`) using the first 800 chars of each SKILL.md body.
- `bench [--compare-llm] [--json] [--spec PATH]` — accuracy, stage-1 accuracy, top-3 accuracy,
  mean latency, wall time, cost, stage-2 runs/changes, mismatch table. `--compare-llm` runs
  Sonnet 5.5 via `llm_client.chat_completion` on the same menu (≤20 calls, skipped on failure).
- Ledger: `.tmp/jev_ledger.jsonl`, `caller=jev_skill_pick`.

## Making a skill pickable
Frontmatter `name:` + `description:` (≤ 250 chars; the router truncates at 220, so put the
trigger phrases first). `disable-model-invocation: true` hides it from the menu. The menu cache
(`.tmp/jev_skills_menu.json`) refreshes on SKILL.md mtime. Add a bench case for every new skill.

## Operator prompt
"Which skill should handle: <task>" → run `pick "<task>"`.

## Edge cases
- No key → exit 2. Jev error → `skill=none`, error surfaced, no stage 2.
- Skills whose description is empty (e.g. `test-suite` uses a YAML block scalar `|`) show as
  their name only and are pick-weak; fix the frontmatter to a single line.
- Stage 2 only fires below `--min-confidence`; on the bench Jev is usually confident, so it rarely runs.

## Changelog
- 2026-10-07: created (CLI, bench spec, tests).
