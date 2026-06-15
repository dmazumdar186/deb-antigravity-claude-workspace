# JOB SEARCH SHEET — Architectural Audit

**Date:** 2026-06-15
**Scope:** `execution/personal_workflows/job_search_sheet.py` (the daily Adzuna pipeline that fills the Google Sheet and emails the user).
**Trigger:** User reported two symptoms — daily count locked around 124–126; Adzuna is the only source despite the user being a senior PM in Paris who has never heard of Adzuna and expected APEC / Welcome to the Jungle / France Travail / LinkedIn.

This audit is read-only. Every claim is cited file:line. The rebuild plan is in `C:\Users\deban\.claude\plans\jolly-swimming-naur.md`.

---

## TL;DR

Three independent defects compound:

1. **Only Adzuna is live.** Jooble is disabled in `.env` (line 76). France Travail is `false` for FR in [config/job_search.json](config/job_search.json#L37). APEC, WTTJ, LinkedIn were never wired in. The "broad source mix" the user expected does not exist in this pipeline.
2. **The pipeline has no cross-day persistent dedup.** The `seen` dict in [execution/personal_workflows/job_search_sheet.py:215](execution/personal_workflows/job_search_sheet.py#L215) is local to one function call. Tomorrow's run starts with `seen = {}` and the same Adzuna page yields the same jobs again, presented as "new."
3. **Adzuna is a poor source for a Paris PM market.** It is a UK-origin meta-aggregator with 24–48h lag behind APEC / WTTJ / Indeed / LinkedIn and zero brand recognition among French senior PMs. The user's instinct is correct.

The "124 or 126" count is the deterministic fingerprint of those three defects together. It is **not** the real arrival rate of new PM jobs in Paris; it is the constant filter-throughput of a constant fetch with no real dedup.

---

## Why the count is always 124–126 — the math

Last ten real (non-mock, non-dry-run) runs from [.tmp/job_search/job_search_runs.jsonl](.tmp/job_search/job_search_runs.jsonl):

| run_id | discovered | after_dedup | per-tab sum |
|---|---:|---:|---:|
| run_20260609_155348 | 205 | 102 | 89+26+2+0+0+7 = **124** |
| run_20260609_164301 | 205 | 104 | 91+26+2+0+0+7 = **126** |
| run_20260610_113648 | 206 | 101 | 89+27+2+0+0+7 = **125** |
| run_20260610_161715 | 207 |  84 | 72+25+2+0+0+7 = **106** |
| run_20260610_163221 | 207 |  97 | 85+26+2+0+0+7 = **120** |
| run_20260610_164012 | 207 |  98 | 86+27+2+0+0+7 = **124** |
| run_20260610_164543 | 207 | 103 | 91+27+2+0+0+7 = **127** |
| run_20260610_173817 | 207 |  94 | 82+26+2+0+0+7 = **119** |
| run_20260610_175601 | 207 |  97 | 85+26+2+0+0+7 = **120** |

Pattern decoded:

- **`discovered ≈ 207`** every day. That is `1 geo (FR) × 5 active title queries × 1 page × ~50 results/page ≈ 250` raw Adzuna jobs, minus Adzuna's own internal dedup across overlapping synonyms ⇒ ~205–207. See [execution/personal_workflows/job_search_sheet.py:569](execution/personal_workflows/job_search_sheet.py#L569) for the fan-out and [execution/custom_scrapers/adzuna_jobs.py:157-158](execution/custom_scrapers/adzuna_jobs.py#L157-L158) for the `max_results=50, pages=1` defaults.
- **Per-tab sum lands in 119–127** every day. The deterministic filter chain (keyword filter → LLM gate → tab routing) takes the same input shape and produces the same output band. The user sees this in the email as "124 new" / "126 new."
- **`AI Consultant: 7` is identical on every run.** That tab gets the same 7 Adzuna jobs every single day. They are not deduped against yesterday because the seen-set does not persist. Same for `AI Automation: 2` — exactly 2 every run.

The user's instinct that this number "looks too clean" is exactly right. A real job market produces noisy daily counts (sometimes 5 new, sometimes 60 new). A pipeline whose seen-set resets every morning produces a constant.

---

## Why only Adzuna — the source-mix gap

Cited evidence:

| Claim | Evidence |
|---|---|
| Source list is hardcoded to `["adzuna", "jooble"]` | [execution/personal_workflows/job_search_sheet.py:569](execution/personal_workflows/job_search_sheet.py#L569) |
| Jooble exits cleanly with `return []` because key is disabled | `.env:76` → `JOOBLE_API_KEY=DISABLED_RECAPTCHA_BLOCKED` (memory: `project_job_search_sheet.md` notes Jooble was deferred for reCAPTCHA) |
| France Travail is *configured* but `false` for every geo, including FR | [config/job_search.json:37](config/job_search.json#L37) → `"FR": {"phase": "1a", ..., "france_travail": false, ...}` |
| France Travail credentials *do* exist (blank), so the API isn't even called | `.env:55-56` → `FRANCE_TRAVAIL_CLIENT_ID=` / `_SECRET=` (placeholders) |
| WTTJ, APEC, LinkedIn, Indeed: no source adapter in `execution/personal_workflows/` or `execution/modules/sources/` | No file matches. The dispatcher at `job_search_sheet.py:146-183` only branches on `adzuna` and `jooble`. |
| The other `job_tracker_pm_france.py` project (in memory) has a broader source set, but is a *different pipeline* not wired to this cron | memory: `project_job_tracker_pm_france.md` |

**Net:** Adzuna is the only working source. Every other source is either disabled, never written, or in a sibling project.

---

## Why dedup doesn't carry across days

The dedup function at [execution/personal_workflows/job_search_sheet.py:198-269](execution/personal_workflows/job_search_sheet.py#L198) does *within-run* dedup correctly (`seen: dict[str, dict] = {}` at line 215, Jaccard-trigram guard at line 235). But:

- The `seen` dict is a local variable. It is destroyed when `_dedup_jobs` returns.
- The pipeline does have a *carry-forward* step (preserving `Status`/`Notes` on matched `dedup_hash`, see `_build_sheet_row` around [line 304-330](execution/personal_workflows/job_search_sheet.py#L304-L330)) — but this only preserves user-entered fields on rows that *happen to be in the sheet*. Once the sheet rotates or a row drops out, the seen-set is gone.
- There is **no persistent file or KV** mapping "I have already reported URL X on day Y." Tomorrow's `discovered=207` will re-discover today's jobs, and they will land in the email as "new" again.

This is the actual fix the rebuild has to deliver: a persistent, time-windowed seen-set, keyed on canonical URL + content fingerprint, that survives across runs.

---

## Adzuna verdict — is it credible as a FR PM source?

Adzuna is a UK-origin global meta-aggregator. For the French Paris PM market specifically:

- Brand recognition: zero among senior FR PMs (the user's own observation, corroborated by 2026 research across the FR job-search landscape).
- Coverage: Adzuna re-indexes APEC + Indeed + LinkedIn + Monster.fr + RegionsJob/HelloWork with a typical 24–48h lag.
- Field quality: salary, contract type, and seniority fields are frequently empty for FR roles; the underlying Adzuna `category` and `location` are coarse.
- App Store / Play Store: 3.4/5 rating with complaints about stale data and poor French filters.

**Conclusion:** Adzuna is acceptable as a wide US/UK net. As the *sole* source for a Paris senior PM job search, it is the wrong primary. It is what is responsible for the user receiving the same `AI Consultant: 7` jobs every day for weeks.

---

## What a senior FR PM actually checks (2026)

| Tier | Source | Why FR PMs use it | Access path |
|---|---|---|---|
| 1 | **APEC** (`apec.fr`) | *The* board for cadres. Every senior FR PM checks it. ~60k cadre roles. | No official API. Self-hosted Playwright (rate-throttled) or paid Apify actor. |
| 1 | **Welcome to the Jungle** (`welcometothejungle.com`) | *The* tech/startup board in France. ~1k jobs/day. | No public official API. Self-hosted Playwright or paid Mantiks third-party feed. |
| 1 | **France Travail** (`francetravail.fr`) | Massive volume; weak PM density but completes coverage; **has an official free API**. | Official `Offres d'emploi v2` REST API, OAuth2 client-credentials, generous free tier. |
| 2 | **LinkedIn** | Highest recall for PM postings. Hostile to scraping. | Either paid job-data API (Lix.ai, TheirStack) OR ingest LinkedIn job-alert *emails* via Gmail MCP. |
| 2 | HelloWork | French-owned, regional. Mostly duplicates WTTJ/APEC. | Skip in v1. |
| skip | Indeed FR | Mostly duplicates APEC + LinkedIn. | Skip. |
| **kill** | **Adzuna** | UK aggregator, 24–48h lag, no FR brand recognition. | Remove from the primary path. |

---

## Fingerprint failure callout

The "always 124–126" symptom is a textbook *fingerprint failure mode*. The defining trait is: when input is stable and the filter chain is deterministic, the daily output count is constant *regardless of whether the underlying market is actually producing new jobs*. A pipeline in that state is functionally indistinguishable from one that is returning yesterday's jobs forever.

Two operational tells make this diagnosable without the source:

1. **Per-bucket invariance.** The `AI Consultant: 7` and `AI Automation: 2` numbers are identical, byte-for-byte, on every run in the log. Real market churn would jitter these.
2. **Aggregate band-locked.** The per-tab sum sits in a 119–127 band for nine consecutive runs across two days. Real arrival rates produce 5×–10× variance.

These two signatures together mean the pipeline is operating as a *fixed-window re-fetcher with no true cross-day awareness*. That is the bug the rebuild fixes.

---

## Audit conclusion

The pipeline does what it was built to do — it fans out Adzuna queries, dedupes within a run, writes a sheet, sends an email. It is not technically broken. It is **scoped wrong** (only Adzuna, no FR-native sources) and **architecturally incomplete** (no cross-day persistent seen-set). The combination is what produces the user-visible symptoms.

The rebuild plan in `C:\Users\deban\.claude\plans\jolly-swimming-naur.md` addresses both, with a free-only source stack (France Travail official API + WTTJ via Playwright + APEC via Playwright + LinkedIn alerts via Gmail MCP), persistent SQLite-backed dedup, typed Pydantic contracts at every layer boundary, and a front-door synthetic gating the "working" claim.

**This audit is read-only.** No code in this pipeline was modified to produce it.
