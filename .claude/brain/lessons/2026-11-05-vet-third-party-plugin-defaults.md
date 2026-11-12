---
id: 2026-11-05-vet-third-party-plugin-defaults
triggers: plugin, skill, marketplace, mcp, install, vendor, claude-mem
scope: infra
strength: 2
status: active
created: 2026-11-05
confirmed: 2026-11-12
source: .claude/notes/general.md
supersedes:
---
Before enabling a third-party plugin or skill, grep it for model defaults, spend that fires on key presence, hooks and installers; pin or strip them first.

Why: Hallmark's imagegen auto-fires on key presence (stripped 2026-11-05); claude-mem defaulted to banned Haiku with per-tool LLM calls (2026-11-12).
