---
id: 2026-09-10-inspect-live-dry-run-samples
triggers: filter, classifier, gate, scoring, pipeline, leads, job search, sourcing
scope: code
strength: 3
status: active
created: 2026-09-10
confirmed: 2026-09-14
source: .claude/notes/general.md
supersedes:
---
After building a deterministic filter, run it on live data in dry-run and read every reject and keep sample by hand before trusting it.

Why: Domain filter 2026-09-10 had two false-positive classes no unit corpus caught; job_search_v2 2026-09-14 found more from live data.
