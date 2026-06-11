---
name: <kebab-case-name>
description: <one-line: what input + what output>
inputs:
  - <name>: <type> — <one-line description>
outputs:
  - <name>: <type> — <one-line description>
---

# <Workflow Title>

## When to invoke

<Bullet list of trigger conditions.>

## Orchestration outline

1. <Fan-out step: e.g., "for each lead in CSV, spawn enrichment subagent">
2. <Map step: e.g., "subagent calls Apollo + Exa, returns dict">
3. <Reduce step: e.g., "merge into single Sheet">

## Prompt template

```
ultracode: <verb> <object> <constraints> <output destination>
```

## Notes

- Default model for workers: claude-haiku-4-5 (cost).
- Default concurrency: 8.
- Failure mode: <e.g., "skip + log row on subagent failure; don't halt batch">.
