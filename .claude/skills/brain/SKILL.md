---
name: brain
description: Workspace brain of lessons from past mistakes. /brain status|list|search|add|repeat|lint. Auto-loads via hooks; this skill is only for manual inspection or edits.
disable-model-invocation: true
allowed-tools: Bash, Read
---

# /brain

The brain runs on hooks (session start, every prompt, end of turn). You never need to invoke it. Use this skill to look inside it or change it by hand. Full design: `directives/infrastructure/brain.md`.

| Ask | Run |
|---|---|
| `/brain` or `/brain status` | `python3 execution/infrastructure/brain.py status` then `core` |
| `/brain list` | `python3 execution/infrastructure/brain.py list` (`--all` includes archived) |
| `/brain search <text>` | `python3 execution/infrastructure/brain.py search "<text>"` |
| `/brain add <lesson>` | turn the operator's words into one imperative rule ≤240 chars, a dated `--why` and 4-8 specific `--triggers`, then `add` |
| `/brain forget <id>` | `archive <id>` |
| `/brain check` | `lint --deep --apply`; resolve conflicts with `supersede <old> <new>` |

After any change, commit `.claude/brain/` and push per CLAUDE.md principle 3.
