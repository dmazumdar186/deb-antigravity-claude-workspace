---
description: Toggle or inspect the Jev router (on | off | status | test | pick <prompt>)
---

Run `python3 execution/infrastructure/jev_router.py $ARGUMENTS` (use `py` on Windows) and show the output verbatim.

- `on` — every prompt is routed by Jev (model tier + skill pick) via the UserPromptSubmit hook.
- `off` — pass-through; use for confidential prompts (prompt text is sent to OpenRouter/TypeSafe when on).
- `status` — on/off, key presence, routes, decisions logged, cost, latency, tier and skill counts.
- `test` — runs 10 fixed prompts through the classifier and prints tier/skill/confidence/latency.
- `pick <prompt>` — classify one prompt and print the context the hook would inject.
- `gate <file>` — score an audit report: `python3 execution/infrastructure/jev_audit_gate.py gate --report <file>` (exit 0 accept, 1 review, 3 reject).

No arguments = `status`. Reference: `directives/infrastructure/jev.md`.
