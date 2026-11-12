---
id: 2026-09-13-recount-after-gate-change
triggers: gates.py, gate change, near-miss, counts, sourcing, gaia, threshold
scope: code
strength: 2
status: active
created: 2026-09-13
confirmed: 2026-09-13
source: .claude/notes/log.md
supersedes:
---
After any gate or threshold change, re-run the full pipeline and recount every client-facing number before reusing earlier figures.

Why: Gaia 2026-09-13: an 'over 7 years' floor bug changed the near-miss count shown to the client.
