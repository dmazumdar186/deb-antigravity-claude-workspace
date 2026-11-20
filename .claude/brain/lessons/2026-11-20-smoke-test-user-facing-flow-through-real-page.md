---
id: 2026-11-20-smoke-test-user-facing-flow-through-real-page
triggers: smoke test, form, apply, e2e, browser, staging, api
scope: all
strength: 2
status: active
created: 2026-11-20
confirmed: 2026-11-20
source:
supersedes:
---
Smoke-test every user-facing flow through the real page in a real browser (fill and submit the form), not only by calling the API directly.

Why: GreenJobs 2026-11-20: API-level smoke passed apply, but the on-page form posted to the wrong origin and every email application failed.
