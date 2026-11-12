# Workspace brain: lessons from past mistakes, loaded automatically

**Goal.** Never repeat a mistake the operator already had to point out. Every lesson learned in any session (a client reply, a cold-email campaign, a site build) becomes a short rule that later sessions get automatically, at a small and bounded token cost. Nobody invokes it by hand.

## Tools/Scripts

`execution/infrastructure/brain.py` (engine + CLI) · `.claude/hooks/brain.sh` (hook wrapper, registered in `.claude/settings.json` for SessionStart / UserPromptSubmit / Stop) · `/brain` skill (operator-only) · tests `tests/test_brain.py`.

## Inputs

Hook JSON on stdin (`session_id`, `prompt`, `transcript_path`, `stop_hook_active`); lesson files `.claude/brain/lessons/*.md` (one lesson per file, so parallel branches never conflict); `OPENROUTER_API_KEY` (optional, only `add` and `lint --deep` use it).

## Outputs

Hook `additionalContext` (session start / prompt) or a one-time Stop `block`; lesson files in `lessons/` and `archive/`; `.claude/brain/state.json` (`last_deep`); `.tmp/brain_sessions/` (per-session dedupe, pruned after 14 days); `.tmp/jev_ledger.jsonl` rows (`caller=brain`).

## Steps (automatic, no operator action)

| Moment | Hook | What enters context | Cost bound |
|---|---|---|---|
| Session start | `SessionStart` → `brain.sh start` | the **core**: lessons with strength ≥ 3, plus the capture instruction and a one-line upkeep flag when due | ≤ 12 lessons / 2,200 chars, once per session |
| Every prompt | `UserPromptSubmit` → `brain.sh prompt` | up to 3 lessons from a **hybrid retriever**: keyword triggers (offline, whole words, plurals folded) plus one Jev relevance call over every lesson (p ≥ 0.6, 3.5 s timeout, daily cap $0.25, skipped under `/jev off`). Agreement ranks first. Each lesson appears at most once per session; a capture reminder is added when the prompt reads like a correction | ≤ 900 chars, usually 0; about $0.0002 per prompt. Notifications and agent reports are skipped |
| End of turn | `Stop` → `brain.sh stop` | blocks **once** if the assistant admitted a miss ("my mistake", "nice catch", "I overlooked"...) this turn and did not run `add`/`repeat` | ≤ 3 nudges per session |
| End of turn (evidence) | same Stop hook | nothing; it appends one text-free observation row for the weekly eval (`directives/infrastructure/brain_eval.md`) when the turn had an injection, a correction or an admission | one Jev call only on those turns |

Every hook fails open (exit 0, no output). Without Jev the per-prompt path is keyword-only and offline.

**Measured, not assumed:** `brain_eval.py` scores this weekly with an independent judge (Claude Sonnet). Baseline 2026-11-12: hybrid F1 0.55 against keyword-only 0.23. See `directives/infrastructure/brain_eval.md`.

## Learning loop

1. **Capture.** On a real correction or an admitted miss: `brain.py search "<topic>"` first. If a lesson already covered it, `repeat <id>` (it was missed, so it gets stronger). Otherwise `add --rule "<one imperative line ≤240>" --why "<incident, date>" --triggers "<4-8 words a future prompt would contain>" [--scope] [--source <sha|path>]`.
2. **Self-check at write time.** `add` finds the 3 nearest lessons and asks Jev, in one call, whether each is a duplicate, contradicts, refines or is unrelated. A **duplicate** strengthens the existing lesson instead of adding a file. A **contradiction**, or a restatement (refines ≥ 0.8), is **refused** (exit 3) with the old rule shown. Claude then either rephrases, runs `repeat <old>`, or re-runs with `--supersede <old>` when it holds evidence newer than the old lesson's source (`restore <id>` undoes). A new lesson never silently removes a proven one; this was tested 2026-11-12, when a planted bad rule would otherwise have archived a strength-2 operator lesson. Without a Jev key, a lexical overlap ≥ 0.6 counts as a duplicate and the near lessons are printed for Claude to judge.
3. **Reinforcement.** Strength 1–5. New lessons start at 2; each `repeat` or duplicate adds 1; at 3 a lesson joins the core and loads every session.
4. **Forgetting.** `lint --apply` archives lessons with strength 1 that have not been confirmed for 180 days, keeps at most 120 active lessons (weakest and oldest go first), and merges lexical duplicates (the stronger lesson keeps the union of triggers).
5. **Weekly self-review.** When `state.json:last_deep` is ≥ 7 days old (or missing), session start adds an upkeep line. Claude then runs `lint --deep --apply` in a background worker: Jev checks each lesson against its nearest neighbours for duplicates and contradictions, and Claude resolves each contradiction with `supersede <old> <new>`, then commits.

Commit `.claude/brain/` together with the work that taught the lesson.

## What belongs here (and what doesn't)

- **Brain:** behavioural rules that would have prevented a real miss: process, client perception, verification, recurring traps.
- **Not here:** anything CLAUDE.md already says (it loads every call anyway); one-off technical detail (`.claude/notes/`); session recall (claude-mem). Notes stay the raw log, and the brain holds the distilled rules.
- Every lesson cites a real `source` (sha or path) and a dated `Why`. Never invent either.

## Edge cases

- A bad lesson file is reported by `lint` and `status` but never breaks a hook.
- A cloud container has no `.tmp` history, so per-session dedupe starts fresh. That is harmless.
- Sub-agents get no hooks: the main session copies the relevant injected lessons into each brief.
- Triggers are whole-word matches (`les` does not match `less`), so choose specific words over generic ones.
- `/jev off` turns off every Jev call that carries prompt text (per-prompt recall and the live judge); keywords keep working.

## Output contract

Nothing in this system writes to an operator deliverable or channel. Upkeep runs silently in a worker and is reported only if it fails.
