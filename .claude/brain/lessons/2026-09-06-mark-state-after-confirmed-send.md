---
id: 2026-09-06-mark-state-after-confirmed-send
triggers: cron, seen, state, ledger, email send, digest, notifier, scheduled
scope: code
strength: 2
status: active
created: 2026-09-06
confirmed: 2026-09-06
source: .claude/notes/log.md
supersedes:
---
Mark items seen or sent only after the delivery is confirmed; never before the send call returns success.

Why: job_digest 2026-09-06: marking seen before SMTP confirmed burned jobs on the second daily cron fire.
