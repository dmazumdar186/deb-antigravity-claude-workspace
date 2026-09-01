# Token Economy (Always Active)

**Adopted 2026-09-01.** The operator was hitting the 5-hour usage cap constantly with Fable 5 as the everywhere-default. Usage limits are model-weighted (Fable ≈ 5x Sonnet, 2x Opus per token), and every auto-loaded file is re-sent on **every model call**. Two levers: fixed context and model weight. This rule governs both.

## Fixed context is rent

Everything that auto-loads (CLAUDE.md, always-active rules, skill descriptions, MCP tool schemas) is paid on every single turn, in every session, forever.

- CLAUDE.md stays ≤ 7,000 characters. Reference-shaped content (tables, histories, war stories, setup guides) goes to `directives/`, `docs/reference/`, or on-demand rule files — never inline in CLAUDE.md.
- Skill frontmatter `description:` fields stay ≤ ~300 characters — enough to trigger, nothing more. The skill body loads only on invocation and can be as long as it needs.
- New always-active rules require operator approval; prefer path-scoped auto-load (like `python-hardening.md`) or on-demand reads.
- MCP servers: every registered server's tool schemas load into context. Register only servers in active use; prefer CLI equivalents (`gh`, `curl`) where they exist. Adding to `.mcp.json` needs operator approval.
- Keep the auto-loaded prefix **stable**: prompt caching makes re-reads ~0.1x cost, but any edit to CLAUDE.md/rules invalidates the cache for every session. Batch such edits; don't churn them mid-week.

## Model doctrine — Fable thinks, Sonnet works

The operator runs Max with `claude-fable-5` as the orchestrator (session default). Cost control comes from what the brain is *allowed to spend tokens on*, never from downgrading it:

- The main session keeps Fable for what only the top model does well: planning, architecture, root-cause reasoning, design review, high-stakes judgement.
- **Fable never grinds.** Exploration beyond ~2-3 files → Explore sub-agent (Sonnet). Implementation from an approved plan → general-purpose sub-agent (Sonnet). Bulk per-row work → Dynamic Workflow workers (Sonnet). Fable reviews the returned diff/conclusion, not the journey. Rule of thumb: if a mid-level engineer could do the step from written instructions, it goes to a Sonnet agent.
- This is why the fixed-context diet above matters 5x: every KB in the always-loaded prefix is re-billed at Fable weight on every orchestrator turn.
- Audit lenses: `pipeline-auditor` on Fable (adversarial verification), `code-reviewer` on Opus, `anneal-reviewer`/`qa`/`documenter`/`note-taker` on Sonnet. Fan-out workers always Sonnet. Haiku stays banned.

## In-session hygiene

- `/clear` between unrelated tasks; `/compact` at milestones. A long transcript is re-sent with every subsequent turn.
- Delegate >3-file exploration to an Explore sub-agent (fresh context, Sonnet); keep only the conclusion in main context.
- Read narrowly: `offset`/`limit` on Read, `head_limit` on Grep, never `cat` a large file into context, never re-read a file already in context.
- Batch independent tool calls (see `always-parallelize.md`) — fewer turns means the fixed context is re-sent fewer times.
- Don't paste large tool outputs into replies; summarize and cite file paths.
- Long-running jobs: `run_in_background: true`, never foreground sleep+poll loops (each poll turn re-sends the whole context).

## Measure — manage from data, not guesses

- Weekly (or when limits pinch): run `python3 execution/infrastructure/token_usage_report.py` on the machine where Claude Code runs (directive: `directives/infrastructure/token_usage_report.md`). It reports burn by model/day, skill invocation counts, and sub-agent spawn counts from local transcripts.
- Red flags in the report: Fable dominating raw token volume (delegation is failing), zero sub-agent spawns on multi-file work, skills at zero invocations for a month (archive candidates → `docs/reference/skills-archive/`).
- Quarterly: re-measure `wc -c CLAUDE.md .claude/rules/*` and the skill-description total; re-check `.mcp.json` and claude.ai connectors against actual use.
