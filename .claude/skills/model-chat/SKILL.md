---
name: model-chat
description: >
  Spawn 5+ Claude instances into a shared conversation room where they debate, disagree, and converge on solutions. Uses round-robin turns with parallel execution within each round. Triggers on "model chat", "multi-model debate", "agent debate", "spawn a chat room", or /model-chat. Pass a topic as the argument.
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Model Chat

Spawn 5 Claude Sonnet instances into a shared conversation room. They debate a problem across 5 rounds using round-robin turns (all agents respond in parallel each round, see full history). A synthesizer agent then merges the debate into a final answer.

**Why this works:** Same model, slight framing variations = systematically different failure modes. Surfacing disagreements between instances is more valuable than any single instance's confident answer. Consensus across independent runs filters hallucinations; divergences reveal genuine judgment calls.

## Execution

### 1. Parse the request

Extract from the user's message:
- **Topic/problem** to debate
- **Mode**: auto (default) or interactive (`--interactive` flag)
- **Agent count**: default 5, user can override
- **Round count**: default 5, user can override

### 2. Run the orchestration script

```bash
cd /path/to/your/workspace && .venv/bin/python .claude/skills/model-chat/model_chat.py "<topic>"
```

For interactive mode:
```bash
cd /path/to/your/workspace && .venv/bin/python .claude/skills/model-chat/model_chat.py "<topic>" --interactive
```

Optional flags:
- `--agents N` — number of agents (default 5)
- `--rounds N` — number of debate rounds (default 5)

### 3. Deliver results

The script outputs the full conversation to stdout in real-time and saves to a timestamped subdirectory:
- `active/model-chat/<YYYYMMDD-HHMMSS>/conversation.json` — full structured conversation log
- `active/model-chat/<YYYYMMDD-HHMMSS>/synthesis.md` — final synthesized answer
- `active/model-chat/latest` — symlink to the most recent run

Present to the user:
- Brief summary of key agreements and disagreements
- The synthesis (or link to it)
- Note any particularly interesting moments of debate

## How it works internally

1. **5 agents** with slight framing variations (systems thinker, pragmatist, edge-case finder, UX-focused, contrarian)
2. **Round-robin**: each round, all agents see full history and respond in parallel via async API calls
3. **5 rounds** of debate (25 total messages)
4. **Synthesizer**: a final agent reads the entire debate and produces a structured merged answer
5. **Interactive mode**: after each round, prompts user for optional input to steer the debate

## Output files

Each run saves to `active/model-chat/<YYYYMMDD-HHMMSS>/`:

| File | Description |
|------|-------------|
| `conversation.json` | Full structured conversation log |
| `synthesis.md` | Final synthesized answer |

A `latest` symlink always points to the most recent run. Previous runs are preserved.
