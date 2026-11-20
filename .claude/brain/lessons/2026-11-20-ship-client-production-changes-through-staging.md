---
id: 2026-11-20-ship-client-production-changes-through-staging
triggers: deploy, production, staging, ci/cd, pipeline, go live, client site
scope: all
strength: 2
status: active
created: 2026-11-20
confirmed: 2026-11-20
source:
supersedes:
---
Ship client production changes only through staging plus CI/CD gates (tests, e2e on staging, approved promote, recorded rollback); never deploy unchecked.

Why: GreenJobs 2026-11-20: operator required staging and a CI/CD pipeline; nothing unchecked on a client's live production.
