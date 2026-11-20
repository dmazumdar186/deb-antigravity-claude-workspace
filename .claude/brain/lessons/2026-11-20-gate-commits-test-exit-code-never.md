---
id: 2026-11-20-gate-commits-test-exit-code-never
triggers: commit, test runner, tail, exit code, all green, red
scope: all
strength: 2
status: active
created: 2026-11-20
confirmed: 2026-11-20
source:
supersedes:
---
Gate commits on the test runner's exit code, never on piped output (tail hides failure); commit only when the suite exits 0.

Why: GreenJobs 2026-11-20: run_tests.sh | tail -1 && git commit committed a RED suite.
