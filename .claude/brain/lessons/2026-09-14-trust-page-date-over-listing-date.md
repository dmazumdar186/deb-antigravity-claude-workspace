---
id: 2026-09-14-trust-page-date-over-listing-date
triggers: freshness, posted date, job search, wttj, linkedin jobs, stale
scope: code
strength: 2
status: active
created: 2026-09-14
confirmed: 2026-10-26
source: .claude/notes/log.md
supersedes:
---
Judge freshness from the item's own page date, not a listing or search API date, which is often a bump or repost date.

Why: job_search_v2 2026-09-14 dropped 13/148 stale jobs; WTTJ published_at proved a bump date again 2026-10-26.
