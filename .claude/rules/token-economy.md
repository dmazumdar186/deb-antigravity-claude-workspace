# Token Economy (Always Active)

**Adopted 2026-09-01, rewritten 2026-09-21** after the operator kept hitting the 5-hour cap. Evidence and sources: `docs/reference/token_usage_research_2026-09-21.md` (read it before changing this rule). Two facts drive everything: the Max plan is one rolling 5-hour + weekly pool shared by every model, sub-agent, workflow and teammate; and every auto-loaded byte (CLAUDE.md, unscoped rules, skill descriptions, MCP schemas) is re-sent on **every model call in every context**, including each sub-agent's.

## 1. Fixed context is rent

- CLAUDE.md ≤ 7,000 chars. Unscoped rules ≤ ~12k chars total; anything reference-shaped goes to `directives/` or `docs/reference/`, or gets `paths:` frontmatter so it loads only for matching files.
- Skill `description:` ≤ ~250 chars. Operator-only skills carry `disable-model-invocation: true` so their descriptions leave the prefix entirely.
- Register only MCP servers in active use; prefer `curl`/`gh`. Tool search keeps schemas deferred; `MAX_MCP_OUTPUT_TOKENS` stays default.
- Keep the prefix byte-stable: cache reads are cheap only while nothing before them changes. Batch edits to CLAUDE.md, rules and settings; a model switch, MCP toggle or CLAUDE.md edit misses the cache for every open session.
- Hooks: only SessionStart / UserPromptSubmit stdout enters context. Keep `session-start.sh` small. PostToolUse stdout on exit 0 is discarded (free, but does nothing).

## 2. Model doctrine — Fable 5.1 only, effort low (2026-09-21)

- One model everywhere: `claude-fable-5-1` for the session, every sub-agent (`CLAUDE_CODE_SUBAGENT_MODEL`), workflows, audit lenses and both `model_registry` tiers. One effort everywhere: `low` (`effortLevel` + `modelSettings` in settings.json, `effort: low` on every agent, `llm_client.default_effort()` on API calls). No medium, no other model, unless the operator names one for a task.
- Why this is the cheap shape: one model means one cache namespace, cache reads at $0.25/MTok, and low effort means fewer tool calls and less preamble per turn. Fable cannot disable thinking; thinking bills as output, so never put it in a tight poll loop.

## 3. Work-splitting — small units, fresh contexts

- **Fable never grinds.** Exploration >2-3 files, implementation from an approved plan, bulk per-row work, and every audit lens go to a worker with a complete brief up front. Workers return a ≤300-word conclusion; large output goes to a file the brain reads narrowly.
- Cheapest to most expensive for the orchestrator's context: Dynamic Workflow (`ultracode:`; only the final value returns) < sub-agent (final text only) < Agent Team (every teammate message lands in the lead; ~proportional to team size). `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` stays `0`; enable per session only when teammates must talk to each other.
- Scale effort to the task (Anthropic's multi-agent guidance): one worker with 3-10 calls for a lookup, 2-4 workers for a comparison, a workflow for >5 independent units. Workers own disjoint files; brief them once, fully.
- `omitClaudeMd: true` on agents whose brief is self-contained. Use `isolation: worktree` for parallel implementers.

## 4. In-session hygiene

- `/clear` between unrelated tasks (free); `/compact <focus>` at milestones; `/rewind` beats compact; `/btw` for side questions. Don't resume a large session after >1h idle without compacting first (full-prefix cache miss).
- Read narrowly (`offset`/`limit`, `head_limit`); never cat a large file; never re-read what is in context; `bashOutputMaxChars` caps tool output.
- Batch independent tool calls (`always-parallelize.md`); long jobs `run_in_background: true`, never sleep-poll.
- `/usage` shows the session, cache line and per-skill/sub-agent attribution; check it when the cap pinches. `/insights` itself bills tokens.

## 5. Not levers (don't chase)

Account sharing or reselling is prohibited; multiple accounts are an AUP risk, not a strategy; proxies that strip `cache_control` cost more; nothing makes cached or sub-agent tokens free. The official overflow path is `/usage-credits`.

## 6. Measure

Weekly or when limits pinch: `python3 execution/infrastructure/token_usage_report.py` (`directives/infrastructure/token_usage_report.md`) plus `/usage`. Red flags: main session dominating volume (delegation failing), zero sub-agent spawns on multi-file work, cache-miss share ≥10%, skills unused for a month (archive to `docs/reference/skills-archive/`). Quarterly: re-measure `wc -c CLAUDE.md .claude/rules/*` and the skill-description total.
