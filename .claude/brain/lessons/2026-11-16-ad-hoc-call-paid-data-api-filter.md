---
id: 2026-11-16-ad-hoc-call-paid-data-api-filter
triggers: leadocean lookup email credits search person
scope: all
strength: 2
status: active
created: 2026-11-16
confirmed: 2026-11-16
source:
supersedes:
---
Before an ad-hoc call to a paid data API, use only filter keys the workspace script already sends and probe with count=true or limit=1; an unrecognised filter can be silently dropped and billed per row.

Why: 2026-11-16: a guessed domain= filter on the people-search endpoint was ignored, returned 10 unrelated rows and billed 10 credits while looking up one CEO email.
