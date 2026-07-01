# Always Parallelize — Never Serialize (Always Active)

**Effective 2026-07-01.** Governs how work is dispatched within any single
session in this workspace. Overrides any per-file "wait for X before doing Y"
instinct when X and Y are independent.

---

## The rule

If two units of work do not depend on each other's output, they run
**concurrently in the same tool-call batch**. Serial execution of independent
work is a defect, not a style choice.

Concretely, in any single assistant turn:

- Read A + Read B + Read C + Grep D + git status → **one message, four tool
  calls**, not four messages of one each.
- Long-running verification (CI dispatch, live probe, `sleep`+poll) → runs in
  the background via `run_in_background: true`, and the next independent piece
  of work starts immediately in the SAME message.
- Multiple Agent/Explore delegations for independent research → single message,
  N tool_use blocks.
- Local unit-test verify + push to remote + external scheduler scaffolding →
  parallel where they don't touch the same file / same remote.

Serial is correct **only** when the output of A is a genuine input to B:
- Read the file BEFORE editing it (tool-required contract).
- Verify the fix BEFORE committing (if verification's failure would change the
  commit message).
- Push BEFORE dispatching a workflow that needs the pushed code.

Any other "let me wait and see" is a serialization defect.

---

## Why this exists

The 2026-07-01 war-room session on job_search_v2 spent >20 minutes of wall
clock idling in "waiting on CI" polls while the CF Worker scaffold, the L3
alarm push, and the source-list pruning could all have run in parallel. The
operator's wall clock is the scarce resource; when the assistant serializes
independent work, that clock burns for no reason.

The promise this rule makes to the operator: **the wall clock never idles on
independent work. If N pieces of work don't need each other, N tool calls fire
in the same message.**

---

## Practical patterns

**Pattern 1 — Fan-out reads.** When investigating a bug, read every plausibly
relevant file + run every plausibly relevant probe in one batch. Then reason
over the collected evidence.

```
[one message]
  Read(run.py) + Read(ranker/score.py) + Read(acceptance.py)
  + Grep("chunk_failures", type="py")
  + Bash("gh run view <id> --log")
  + Bash("cat .tmp/.../run_log.jsonl | tail -1")
```

**Pattern 2 — Verify in background, keep working.** When a probe takes minutes
(CI run, live scrape, `sleep` poll), fire it with `run_in_background: true`
and immediately start the next independent unit of work.

```
[one message]
  Bash(dispatch verification run, run_in_background=true)
  Write(next fix file)
  Edit(other unrelated file)
```

The background task will notify on completion. The turn does not idle.

**Pattern 3 — Push while dispatching.** If a commit is ready and the
verification is a live-CI probe, push in the same message as the dispatch —
don't wait to see the run's outcome before pushing an unrelated fix batch.
Panel-pass verifies each commit independently.

**Pattern 4 — Delegate independent research to sub-agents in parallel.** For
research questions that span >3 files or would blow main-context tokens,
launch multiple Explore / Agent calls in one message.

```
[one message]
  Agent(subagent_type="Explore", "audit all cron entries workspace-wide")
  Agent(subagent_type="Explore", "list all Anthropic-API callsites")
  Agent(subagent_type="Explore", "grep for silent-swallow patterns")
```

---

## Anti-patterns (forbidden)

- Reading files one at a time when investigating something. If you need
  files A, B, C to reason about a bug, they go in one message.
- Sleeping in the foreground to wait for CI. Use `run_in_background: true`.
- "Let me push first, then verify" when the push and verify don't depend
  on each other (they usually don't; verification is against pushed code
  OR against staged code — pick and stop debating).
- Ordering N independent Edit calls across N messages. One message, N
  Edit blocks.

---

## Exhibit A — 2026-07-01, job_search_v2 war-room

Fixes 1-4 landed, committed, pushed as a batch — parallel edits, sequential
where the commit needed all four files present. Verification run dispatched.
Then a serialization defect: while the verification ran (~20 min), the
assistant sat idle polling instead of concurrently:
  - Scaffolding the CF Worker external cron trigger.
  - Pushing the L3 alarm + watchdog batch (independent of ranker fix).
  - Pruning the 4 dead gmail-based sources from the default `--sources`.

Operator flagged the idle. This rule is the fix so future-me doesn't repeat it.

---

## How this rule is enforced

**Model-level:** the assistant must scan its planned tool calls before every
message and ask "do any of these depend on the OUTPUT of another one in this
message?" If no → all in one batch. If yes → only the truly-dependent ones
serialize.

**Mechanical guardrail (owed per rule-backport-cadence):** SAST-style scan
of session transcripts for the anti-pattern shape:
  message N: [one bash: sleep / poll]
  message N+1: [independent work]
Flag as `serialization-defect` for review. Prototype-level; not immediately
in scope for automation.

---

## Related rules

- `~/.claude/rules/panel-pass.md` — the 4-lens quality gate. Panel-pass and
  parallelize compose: run all four lenses concurrently where they're
  independent (Karpathy check + Cherny dogfood + Amodei deploy status +
  Ilya honest-gaps enumeration).
- `~/.claude/rules/learnings-loop.md` — the loop that produced this rule.
- `~/.claude/rules/front-door-synthetic.md` — the synthetic can run in
  parallel with dev work; do not idle waiting for it.
