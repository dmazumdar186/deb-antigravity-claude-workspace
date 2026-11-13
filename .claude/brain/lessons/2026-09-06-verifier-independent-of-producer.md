---
id: 2026-09-06-verifier-independent-of-producer
triggers: acceptance gate, verifier, prospect list, evidence pack, validation, check, audit
scope: all
strength: 3
status: active
created: 2026-09-06
confirmed: 2026-11-11
source: 48fc82c
supersedes:
---
Build every acceptance check independently of what it checks: its own matcher, or a blind worker that never reads the finder's files.

Why: job_digest 2026-09-06: a gate reusing the filter logic was a tautology; agency referral 2026-11-11: a single-pass prospect list named a modern site.
