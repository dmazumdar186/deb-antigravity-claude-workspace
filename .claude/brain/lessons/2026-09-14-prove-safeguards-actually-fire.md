---
id: 2026-09-14-prove-safeguards-actually-fire
triggers: dedup, hook, safeguard, gate, guard, duplicates, formatter, check
scope: code
strength: 3
status: active
created: 2026-09-14
confirmed: 2026-11-12
source: 11b6652
supersedes:
---
Prove each safeguard (dedup, hook, gate) fires with a positive test on real input that it must catch; a silent no-op looks identical to a pass.

Why: job_search_v2 dedup lost its _id column and silently passed (2026-09-14); three hooks read an unset variable and were no-ops (2026-11-12).
