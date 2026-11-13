---
id: 2026-11-13-replay-evaluation-through-exact-live-call
triggers: eval, benchmark, replay, metrics, recall, precision, evaluator
scope: all
strength: 2
status: active
created: 2026-11-13
confirmed: 2026-11-13
source:
supersedes:
---
Replay an evaluation through the exact live call path, with the same exclusions and session state, before trusting its numbers.

Why: 2026-11-13 brain eval let always-loaded core lessons compete for per-prompt slots the live hook excludes; 32 of 51 hits in a replay were core, hiding weak recall.
