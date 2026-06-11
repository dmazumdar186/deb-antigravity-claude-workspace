---
paths:
  - ".claude/agents/**"
  - ".claude/workflows/**"
  - "directives/subagent/**"
---

# Sub-Agent Delegation — Tier Selection

Three orchestration tiers are available. Pick by parallelism and context-sharing needs.

## Tier 1 — Sub-agent (`Agent(...)`)

**Use when**: 1–3 independent tasks, tight result loop, total runtime under 5 minutes.
- Fresh context per spawn. Returns once.
- Best for: file exploration, focused review, single-file implementation.
- Spawn pattern: `Agent(subagent_type="general-purpose", model="sonnet", description="...", prompt="...")`.

## Tier 2 — Dynamic Workflow (`ultracode:` keyword)

**Use when**: 5–16+ independent fan-out tasks, long-running jobs, runs in background.
- Up to 16 concurrent sub-agents, 1000 total per run.
- Resumable within the session. Saveable as `/command` in `.claude/workflows/`.
- Best for: lead enrichment (100+ rows), competitive matrices, multi-source research, large codebase sweeps.
- Default worker model: `claude-haiku-4-5`.
- See `.claude/workflows/README.md` for full triggers + examples.

## Tier 3 — Agent Team (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)

**Use when**: long-running parallel sessions with shared task list and peer-to-peer messaging.
- N full Claude sessions. Each has its own context. Shared mailbox + task list.
- Teammates can claim tasks, challenge each other's findings, and self-coordinate.
- Best for: multi-hypothesis research, parallel module development, "two teams racing on the same problem."
- Coordinated by a "team lead" agent. Display modes: `in-process` (Shift+Down to cycle) or `tmux` split-pane.
- Enabled via `.claude/settings.json` env block (see `.claude/SETTINGS_NOTES.md`).

## Cost-benefit decision

| Tier | Latency | $ cost | Context cost |
|---|---|---|---|
| Sub-agent | low | low | low |
| Dynamic Workflow | low (background) | low-med | very low (runs out-of-process) |
| Agent Team | medium | medium-high | low (each teammate has own context) |

Pick the smallest tier that satisfies parallelism + context-share needs. Don't over-engineer.

## What NOT to do

- Don't spawn a Dynamic Workflow for <5 parallel tasks. Sub-agents are cheaper and simpler.
- Don't spawn Agent Teams for one-shot work. Use a sub-agent.
- Don't create `.claude/agents/plan-skeptic.md` — the global plan-skeptic skill at `~/.claude/skills/plan-skeptic/SKILL.md` is the source of truth.
- Don't spawn multiple sub-agents for the same files in parallel (conflicting edits).
