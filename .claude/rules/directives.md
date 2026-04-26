---
paths:
  - "directives/**/*.md"
---

# Directive Authoring Rules

- Every directive must have these sections: **Goal**, **Inputs**, **Tools/Scripts**, **Outputs**, **Steps**, **Edge Cases**
- Directives are living documents — update them when you discover API constraints, timing limits, or better approaches
- Never delete a directive without asking the user — they are the instruction set
- When a script is created or modified, the corresponding directive must be updated to reflect current behavior
- Directive names must match their corresponding execution script names (e.g., `cv_builder.md` ↔ `cv_builder.py`)
- After updating a directive, spawn the Documenter agent: `directives/subagent/documenter.md`
- Use the standard template from `/new-directive` command for new directives
- Keep steps numbered and atomic — one action per step
- Document known API limits and rate limits in the Edge Cases section
