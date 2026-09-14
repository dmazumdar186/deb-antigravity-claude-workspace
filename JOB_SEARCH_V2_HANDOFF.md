# Job Search v2 — Operational Runbook

**Last verified live:** 2026-06-15 (3 consecutive wet runs, full idempotency proven).
**Owner:** Debanjan (debanjan186@gmail.com).
**Code:** `execution/personal_workflows/job_search_v2/`
**Spec / directive:** `directives/personal_workflows/job_search_sheet_v2.md`
**Audit (why v1 was retired):** `JOB_SEARCH_SHEET_AUDIT.md`

---

## What this is

One daily aggregator that consolidates jobs from multiple sources into one Google Sheet + one email digest, so you stop reading individual alert emails from LinkedIn / Indeed / WTTJ / APEC / etc.

```
Sources → Normalizer → Persistent Dedup → Location Filter → Gemini Ranker → Sheet + Email
```

## What's live as of 2026-06-15

| Source | Status | Mechanism | Cost |
|---|---|---|---|
| **France Travail** | ✅ LIVE | Official `Offres d'emploi v2` REST API + OAuth2 | Free |
| **LinkedIn (via Gmail)** | ✅ LIVE | IMAP reads `JobAlerts/LinkedIn` Gmail label | Free |
| **Indeed (via Gmail)** | ⚠️ READY (label not yet populated) | IMAP reads `JobAlerts/Indeed` Gmail label | Free |
| **WTTJ (direct scrape)** | ⚠️ FIXTURE ONLY | Anti-bot + interactive search gate blocks headless | n/a |
| **APEC (direct scrape)** | ⚠️ FIXTURE ONLY | Same — Didomi consent + Angular SPA | n/a |

**Tab routing:** jobs land in `PM` / `AI PM` / `AI Automation` / `AI Mobile` / `AI Process` / `AI Consultant` based on title synonyms in `config/job_search_v2.json`. Fallback = `PM`. Synonym matching uses longest-match-first so "ai product manager" wins over "product manager".

**Ranker:** Gemini 2.5 Flash (free tier) scores each job A/B/C/SKIP. On 503 / 429 (high demand or quota), retries with backoff, then falls back to `gemini-2.5-flash-lite`. If still failing, defaults to tier B so the job still ships.

---

## Setup — one-time tasks

### A. Required `.env` variables

Already provisioned and verified working:
- `FRANCE_TRAVAIL_CLIENT_ID`
- `FRANCE_TRAVAIL_CLIENT_SECRET`
- `GMAIL_SMTP_USER`
- `GMAIL_SMTP_APP_PASSWORD`
- `GMAIL_NOTIFY_TO`
- `SHEETS_SPREADSHEET_ID`
- `GEMINI_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_PATH=credentials/service_account.json`

### B. Required GitHub Actions secrets

Same set as `.env` above, plus:
- `GOOGLE_SERVICE_ACCOUNT_JSON_B64` = `base64 < credentials/service_account.json`

Set at: https://github.com/dmazumdar186/deb-antigravity-claude-workspace/settings/secrets/actions

### C. Adding more Gmail-alert sources (Indeed, WTTJ-email, APEC-email)

For each source you want to ingest from Gmail alerts:

1. **Subscribe to that source's job alerts** with your search criteria (Paris, Île-de-France, France-wide, PM keywords).
2. **Create the Gmail label** matching the config: e.g. `JobAlerts/Indeed`.
3. **Create a Gmail filter** that routes the alert sender → label + Skip the Inbox + (optional) Mark as read.

Filter sender expressions:
- Indeed: `from:(noreply@match.indeed.com OR jobsalerts@indeed.com OR alerts@indeed.com)`
- LinkedIn: `from:(jobs-noreply@linkedin.com OR jobs-listings@linkedin.com)`
- Welcome to the Jungle: `from:(noreply@welcometothejungle.com OR alerts@welcometothejungle.com)`
- APEC: `from:(noreply@apec.fr OR alerte@apec.fr)`

The pipeline auto-reads these labels every cron tick. Your inbox stays clean; the digest aggregates everything.

---

## Daily ops

### What you do each morning

1. Open Gmail → look for digest with subject `Job Search v2 — N new for YYYY-MM-DD (A:n B:n C:n)`.
2. Open the linked Google Sheet → switch to the relevant tab (PM / AI PM / etc.).
3. Apply to jobs you want; mark Status = `Applied` / `Saved` / `Skip` on each row.
   **Your edits are preserved across runs** — the dedup layer never overwrites status.

### What the pipeline does each morning (07:00 + 08:00 UTC, dual-cron for DST)

1. Parallel fan-out to all live sources.
2. Normalize via Pydantic v2 contracts, **in-batch cross-source dedup by content_hash OR fingerprint** (2026-09-10 — a fuzzy title+company key that survives gender markers, accents, legal suffixes, and recruiter "via X" wrapping, so the same posting from two boards collapses even when the exact hash differs).
3. Persistent SQLite dedup (60-day TTL), now matched on content_hash **OR fingerprint** too.
4. Title filter (PM/PO-only), location filter (FR/BE/DE/PL/AT/LU + remote; rejects US/APAC/India/Switzerland/UK/etc.), contract filter, EN/FR language filter.
5. **Domain filter (new 2026-09-10)** — rejects PM/PO roles for a non-digital product (hardware, electronics, instrumentation, semiconductors, embedded/firmware, systems software, mechanical, medical devices…). The CV is software-only; a role can be the right title and still be the wrong industry.
6. **Posting verification (new 2026-09-10)** — opens every surviving job's OWN page, reads the real posted date and whether it's still accepting applications; drops closed / stale (>7 days by default) / undatable postings instead of trusting the source's own timestamp.
7. Gemini ranker → tier A/B/C/SKIP; Sonnet reranks the shortlist if a credit is available.
8. Drop SKIP, route others to tabs by title synonym.
9. **Sheet hygiene (extended 2026-09-10)** — purges existing rows that now fail title/language/domain/location, cross-tab-dedups the whole sheet (union-find over `_id`/Link/fingerprint, keeping the row with a Status/earliest-seen/lowest-index), and re-verifies a bounded batch of historical unstamped rows (opens their Link, drops closed/stale/undatable, stamps survivors).
10. Append to sheet — **cross-tab dedup at append time** too (a job is checked against every role tab it could land in, not just the one it's routed to) + send SMTP digest.

---

## Stress-test evidence (2026-06-15)

Three consecutive live wet runs:

| Run | DB | Fetched | New | Sheet | Email |
|---|---|---|---|---|---|
| 1 (cold) | empty | 8 | 7 | PM: 5, AI PM: 2 | "7 new" |
| 2 (warm) | 8 rows | 8 | 0 | 0 | "0 new" |
| 3 (warm) | 8 rows | 8 | 0 | 0 | "0 new" |

Same input → same output across all 3. Persistent dedup proven.

---

## Failure modes & recovery

| Symptom | Likely cause | Fix |
|---|---|---|
| No email at 09:00 Paris | GH-Actions secrets missing OR cron didn't fire | https://github.com/dmazumdar186/deb-antigravity-claude-workspace/actions → re-run workflow manually |
| "0 new" several days in a row | Genuine — no new jobs match filters | Or Gmail alert template changed — check logs for `parsed 0 jobs from email id=… template may have shifted` |
| France Travail 401 | Token endpoint rejected credentials | Re-issue at https://francetravail.io and update `.env` + GH secrets |
| Ranker shows all tier-B placeholders | Quota exhausted (250 RPD free) or 503 high-demand | Pipeline degrades gracefully — placeholders are valid B-tier jobs |
| Sheet append fails | SA lost Editor access OR sheet renamed | Verify SA email still has Editor on the spreadsheet |
| All jobs deduped to 0 unexpectedly | GH cache picked up an old seen.db | GH-Actions → Caches → delete `job-search-v2-seen-db-*` |
| Duplicate rows still in the sheet | Same posting seen from two sources with different URLs/tracking params, OR routed to two different tabs on different days | Should now self-heal: in-batch fingerprint merge (Stage 2), cross-tab dedup at append, and the Stage 3.9 `dedup_rows` sweep all run automatically. Manual: `purge_irrelevant_rows.py --dry-run` (dedup runs by default; `--no-dedup` to isolate) |
| A hardware/electronics PM/PO role slipped into the sheet | Title has no hardware anchor but the description does, below the domain-filter's 2-distinct-anchor / core-requirement threshold | Check `pipeline_stats.domain_filter.rejected_sample` for near-misses; if the title itself carries a clear hardware word, add it to profile.json `hard_filters.skip_domain_anchors` rather than editing `domain_filter.py` directly |
| Row's Verified column says "unverified (source date)" | The job's page host is blocking automated fetches (WTTJ 202 challenge, weworkremotely 100% block observed 2026-09-10, etc.) | Expected degrade-gracefully behavior — the row is kept on the source's own posted date rather than dropped. Check `pipeline_stats.verification.warnings` for hosts blocking ≥80% of ≥5 attempts |
| Rows look stale (age_days growing) but aren't being purged | `reverify_max_fetches` (default 400/run) backlog hasn't drained yet on a large historical sheet | Check `stats.remaining_unstamped` in the reverify output; run `purge_irrelevant_rows.py --reverify-max-fetches 1000` manually to drain faster, or wait — it drains over subsequent cron runs |

### Manual replay commands

```bash
# Local dry-run (no email/sheet write):
py execution/personal_workflows/job_search_v2/run.py --mode live --dry-run

# Local wet run:
py execution/personal_workflows/job_search_v2/run.py --mode live

# Subset of sources:
py execution/personal_workflows/job_search_v2/run.py --mode live --sources france_travail,linkedin_gmail

# Skip ranker (if Gemini is down):
py execution/personal_workflows/job_search_v2/run.py --mode live --no-ranker

# Skip location filter (debug):
py execution/personal_workflows/job_search_v2/run.py --mode live --no-location-filter
```

### Inspect the dedup DB

```bash
py execution/personal_workflows/job_search_v2/normalizer/dedup.py
py execution/personal_workflows/job_search_v2/normalizer/dedup.py --reset  # nuke and start fresh
```

---

## Testing

```bash
bash tests/front_door_job_search_v2.sh
# Must print "== front_door_job_search_v2: PASS =="
```

The synthetic asserts:
- All 5 sources produce ≥3 jobs from fixtures
- Round-trip through Pydantic JSON
- Cold-DB admits all 15 as new
- Warm-DB admits 0 (persistent dedup)
- Tab routing distributes (not collapsed to one tab)
- No Adzuna URLs in output

Per `~/.claude/rules/front-door-synthetic.md`, v2 is PROBATIONARY until the synthetic passes 5 consecutive cron-day runs. Day 1 = 2026-06-15.

---

## What was retired

- `execution/personal_workflows/job_search_sheet.py` (v1, Adzuna-only) → `execution/personal_workflows/_archived/job_search_sheet_v1.py`. Slated for deletion 2026-07-15.
- `Adzuna *` and `Jooble *` env / GH secrets are unused (safe to delete).
- Old data in tabs (PM, AI PM, etc.) was wiped 2026-06-15 (kept headers).
- Scratch tab `v2_jobs` was deleted — v2 routes into the 6 destination tabs directly.

---

## Phase 2 — paid feed unlocks (deferred)

If WTTJ + APEC live ingest matters enough to spend money later:

| Source | Provider | Cost (est.) | Effort |
|---|---|---|---|
| WTTJ | Mantiks (`mantiks.io`) | ~€3/1k jobs ≈ €5–10/mo | 30 min |
| APEC | Apify actor `solidcode/apec-fr-scraper` | ~€0.90/1k ≈ €2–4/mo | 30 min |

Or restore Firecrawl MCP and use `firecrawl_scrape` for both at ~1 credit/page/day.

---

## Trust contract

What v2 commits to:

- The 6 tabs are your single source of truth.
- Your `Status` and `Notes` edits on existing rows are never overwritten.
- Same job never appears twice (cross-day, cross-source, cross-rename).
- US / APAC / India / non-EU jobs will not reach your digest.
- If a source breaks, the digest still ships with what works.
- Synthetic green = pipeline is honest about its state.
