# Always Parallelize — Never Serialize (Always Active)

**Effective 2026-07-01** (born from a war-room session that idled >20 min polling CI while independent work waited; the operator's wall clock is the scarce resource). Condensed 2026-09-01 per `token-economy.md`.

## The rule

If two units of work do not depend on each other's output, they run **concurrently in the same tool-call batch**. Serial execution of independent work is a defect, not a style choice.

- Investigating anything → fan out every plausibly relevant Read/Grep/probe in one message, then reason over the collected evidence.
- Long-running verification (CI dispatch, live probe) → `run_in_background: true`, and the next independent unit of work starts in the SAME message. Never foreground sleep+poll.
- Independent research → multiple Agent/Explore delegations in a single message.
- N independent edits → one message, N Edit blocks.

Serial is correct **only** when A's output is a genuine input to B: read before edit (tool contract), verify before commit (if failure would change the commit), push before dispatching a workflow that needs the pushed code. Any other "let me wait and see" is a serialization defect.

## Self-check before every message

Scan the planned tool calls: "do any of these depend on the OUTPUT of another one in this message?" No → all in one batch. Yes → only the truly-dependent ones serialize.

## Related rules

- `token-economy.md` — batching also cuts re-sent context per task.
- `~/.claude/rules/panel-pass.md` — run the four lenses concurrently where independent.
