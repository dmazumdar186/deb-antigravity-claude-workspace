# Token Economy (Always Active)

**Adopted 2026-09-01.** The operator was hitting the 5-hour usage cap constantly with Fable 5 as the everywhere-default. Usage limits are model-weighted (Fable ≈ 5x Sonnet, 2x Opus per token), and every auto-loaded file is re-sent on **every model call**. Two levers: fixed context and model weight. This rule governs both.

## Fixed context is rent

Everything that auto-loads (CLAUDE.md, always-active rules, skill descriptions, MCP tool schemas) is paid on every single turn, in every session, forever.

- CLAUDE.md stays ≤ 7,000 characters. Reference-shaped content (tables, histories, war stories, setup guides) goes to `directives/`, `docs/reference/`, or on-demand rule files — never inline in CLAUDE.md.
- Skill frontmatter `description:` fields stay ≤ ~300 characters — enough to trigger, nothing more. The skill body loads only on invocation and can be as long as it needs.
- New always-active rules require operator approval; prefer path-scoped auto-load (like `python-hardening.md`) or on-demand reads.
- MCP servers: every registered server's tool schemas load into context. Register only servers in active use; prefer CLI equivalents (`gh`, `curl`) where they exist. Adding to `.mcp.json` needs operator approval.
- Keep the auto-loaded prefix **stable**: prompt caching makes re-reads ~0.1x cost, but any edit to CLAUDE.md/rules invalidates the cache for every session. Batch such edits; don't churn them mid-week.

## Model ladder — Sonnet drives, Fable is an escalation

- Session default is `claude-sonnet-5`. Most driving, execution, and review work lives here.
- Escalate to `claude-fable-5` **deliberately** (`/model claude-fable-5`) for: architecture decisions, debugging that has resisted one Sonnet attempt, high-stakes/ambiguous judgement. Switch back to Sonnet when the judgement moment is over — don't run mundane follow-through on the premium tier.
- Sub-agents and fan-out workers: `claude-sonnet-5`. Adversarial verification (`pipeline-auditor`) is the one Opus-pinned agent. Haiku stays banned.

## In-session hygiene

- `/clear` between unrelated tasks; `/compact` at milestones. A long transcript is re-sent with every subsequent turn.
- Delegate >3-file exploration to an Explore sub-agent (fresh context, Sonnet); keep only the conclusion in main context.
- Read narrowly: `offset`/`limit` on Read, `head_limit` on Grep, never `cat` a large file into context, never re-read a file already in context.
- Batch independent tool calls (see `always-parallelize.md`) — fewer turns means the fixed context is re-sent fewer times.
- Don't paste large tool outputs into replies; summarize and cite file paths.
- Long-running jobs: `run_in_background: true`, never foreground sleep+poll loops (each poll turn re-sends the whole context).

## Review cadence

Quarterly (or when limits start pinching again): re-measure `wc -c CLAUDE.md .claude/rules/*` and the skill-description total, prune skills that haven't been invoked, and re-check `.mcp.json` against actual use.
