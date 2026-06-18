# Job Search Sheet v2 (directive)

**Paired script:** [execution/personal_workflows/job_search_v2/](../../execution/personal_workflows/job_search_v2/)
**Replaces:** `execution/personal_workflows/job_search_sheet.py` (v1) — see [JOB_SEARCH_SHEET_AUDIT.md](../../JOB_SEARCH_SHEET_AUDIT.md) for the v1 audit and rationale for the rebuild.

---

## Prior art pass (2026-06-18, per `~/.claude/rules/prior-art-first.md`)

- **Public API exists?** YES for LinkedIn (jobs-guest, unauthenticated). YES for WTTJ (public Algolia backend, referer-restricted public key). YES for France Travail (official OAuth2 REST). NO known public for Indeed / Hellowork / Jobgether (those remain Gmail-alert-based).
- **Best existing OSS approach:** [sivad259-alt/job-scanner](https://github.com/sivad259-alt/job-scanner) (MIT). Two-source scanner (LinkedIn jobs-guest + WTTJ Algolia) using plain `requests.get` / POST — no browser, no login, no paid scraping API. Volume per the live smoke (2026-06-18): ~30 hits/keyword/page from WTTJ, ~10 from LinkedIn.
- **Why crib:** the friend's approach solves the WTTJ Didomi-consent-gate problem and the LinkedIn auth-wall problem that our v2.0 Playwright + Gmail-IMAP approach failed at. Adapted to our SourceJob contract, PM-Paris keywords, IDF geoId. MIT attribution in module headers.
- **Recommended architecture:** replace `sources/linkedin_gmail.py` and `sources/wttj.py` (Playwright) with `sources/linkedin_guest_api.py` and `sources/wttj_algolia.py`. Keep `linkedin_gmail` as opt-in belt-and-suspenders. Demote `wttj` / `apec` / `*_gmail` (probationary) from the default `--sources` list.

This pass is the post-hoc record. The lesson cost ~12 hours of build that the 10-minute pass at the top would have eliminated; the rule now exists so future "fetch from $service" tasks open with it.

---

## Why v2 exists

v1 has three compounding defects:

1. Only Adzuna is live; the user (senior FR PM) has never heard of Adzuna and it has zero brand recognition in Paris.
2. Dedup is in-memory per-run; tomorrow's run re-discovers the same Adzuna jobs and presents them as "new."
3. The daily count is locked at ~124–126 because of (1) + (2) producing a deterministic fingerprint.

v2 fixes all three by switching to a free FR-native source stack with persistent cross-day dedup and typed contracts at every layer boundary.

---

## Goals

- Source mix matches what a Paris senior PM actually checks: **France Travail + Welcome to the Jungle + APEC + LinkedIn (via Gmail-MCP alert ingestion)**.
- Persistent seen-set across days. A job reported yesterday must not be reported as "new" today.
- Typed contracts at every layer boundary (Pydantic v2). No untyped dicts crossing layers.
- Front-door synthetic gates the "working" claim per [`~/.claude/rules/front-door-synthetic.md`](../../.claude/rules/front-door-synthetic.md).
- $0/month operating budget (free APIs and self-hosted Playwright).

---

## 5-layer architecture

| Layer | Purpose | Files |
|---|---|---|
| 1. Sources | One adapter per origin. Each returns `list[SourceJob]`. | LIVE-VERIFIED (default cron): `sources/france_travail.py`, `sources/linkedin_guest_api.py`, `sources/wttj_algolia.py`, `sources/linkedin_gmail.py`. DARK or opt-in only: `sources/wttj.py` (Playwright, broken), `sources/apec.py` (Playwright, consent-gate), `sources/indeed_gmail.py`, `sources/hellowork_gmail.py`, `sources/jobgether_gmail.py` (probationary, no fixture). |
| 2. Normalizer | `SourceJob -> NormalizedJob` (clean, typed). + cross-day dedup via SQLite. | `normalizer/normalize.py`, `normalizer/dedup.py` |
| 3. Ranker | LLM-judge that tiers each job A/B/C/SKIP against a cached rubric. | `ranker/score.py`, `ranker/rubric.md` (v2.1 — not built yet) |
| 4. Notifier | Drafts the morning Gmail digest + updates the Google Sheet. | `notifier/email.py`, `notifier/sheet.py` (v2.0 — not built yet) |
| 5. Eval | Weekly precision@5 / recall against a `golden_set.csv` the user labels. | `eval/score_pipeline.py` (v2.1 — not built yet) |

**v2.0 ship target** = Layers 1 + 2 + 4 (notifier wires the existing sheet writer to NormalizedJob).
**v2.1 ship target** = Layers 3 + 5.

Reasoning: ship the source-mix and dedup fix first because that addresses both user complaints. Ranking and eval are quality polish that come after the front door is green.

---

## Source: France Travail (live in v2.0)

- **API:** Official [`Offres d'emploi v2`](https://francetravail.io/data/api/offres-emploi) REST API.
- **Auth:** OAuth2 client_credentials. Register at `https://francetravail.io` → create app → subscribe to "Offres d'emploi v2" → copy `client_id` + `client_secret` into `.env` (`FRANCE_TRAVAIL_CLIENT_ID`, `FRANCE_TRAVAIL_CLIENT_SECRET`). Free.
- **Endpoint module:** [`sources/france_travail.py`](../../execution/personal_workflows/job_search_v2/sources/france_travail.py).
- **Rate limit:** generous on the free tier; we self-throttle to 1 req/sec.
- **Fixture path for tests:** [`tests/fixtures/france_travail_sample.json`](../../tests/fixtures/france_travail_sample.json).

CLI:

```bash
# live
py execution/personal_workflows/job_search_v2/sources/france_travail.py --query "product manager" --location Paris --max-pages 3 --posted-within-days 1

# offline (fixture, for the front-door synthetic)
py execution/personal_workflows/job_search_v2/sources/france_travail.py --fixture tests/fixtures/france_travail_sample.json --out .tmp/job_search_v2/ft.jsonl
```

## Source: WTTJ — superseded by `wttj_algolia` (2026-06-18)

The `sources/wttj.py` Playwright module is **DARK and superseded.** It remains in the codebase for fixture-only parser tests, but the production cron no longer invokes it. The replacement `sources/wttj_algolia.py` hits WTTJ's public Algolia search backend directly:

- Endpoint: POST `https://csekhvms53-dsn.algolia.net/1/indexes/wk_cms_jobs_production_published_at_desc/query` with referer-gated public credentials (NOT secrets — same credentials WTTJ ships to every anonymous browser).
- No browser, no consent gate, no `__NEXT_DATA__` parsing. The Algolia backend doesn't care about Didomi modals because it's the API the modal-gated SPA itself calls.
- Live smoke (2026-06-18): 224 hits across the PM keyword set, 48h window, FR-wide. After in-batch dedup (Algolia returns multi-language clones with different `objectID`s for the same job): ~30 unique/keyword/page.
- If WTTJ rotates the Algolia key, re-harvest from a live page load (DevTools → Network → request to `*-dsn.algolia.net` → copy `x-algolia-api-key` header). The module raises `WttjAlgoliaBlockedError` on 403 so silent failure isn't possible.

## Source: WTTJ (Playwright) — DARK, kept for fixture parser only

Original status notes preserved for context:
- httpx + `__NEXT_DATA__` extraction path: WTTJ moved their hydration off of `__NEXT_DATA__`; the blob is no longer in the response.
- Playwright fallback: page renders, but job cards require interactive search submission (the bare URL with query params shows marketing copy, not results). Headless `goto + networkidle` is insufficient.

Module is left in place for the fixture-only parser test. Not invoked by the production cron.

## Source: APEC (fixture-only as of 2026-06-15)

Built but **not live-functional.** Status:
- httpx + BeautifulSoup path: APEC's search page is server-shelled then hydrated via Angular XHR calls. Raw httpx response has 0 offer URLs.
- Playwright direct goto: page renders the Didomi cookie-consent modal + "Vous avez déjà un compte?" gate before any job results. Headless render doesn't get past the consent layer.

Same recommendation as WTTJ: Firecrawl when restored, or extend Playwright to accept-cookies + wait for `/cms/webservices/rechercheOffre` XHR response, or self-throttled Apify actor as paid fallback.

## Source: LinkedIn jobs-guest API (LIVE-VERIFIED as of 2026-06-18) — preferred LinkedIn source

`sources/linkedin_guest_api.py` hits LinkedIn's public unauthenticated `jobs-guest` API:

- Search: `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=...&geoId=...&f_TPR=r172800&start=0`
- No auth, no Gmail middleman, no alert subscription. The endpoint is what LinkedIn serves to logged-out browsers.
- Default geoId = `104246759` (Île-de-France). Paris-only = `104196728`. France-wide = `105015875`. Configurable via `--geo-id`.
- Default keyword set: `product manager`, `senior product manager`, `lead product manager`, `principal product manager`, `head of product`, `chef de produit`, `AI product manager`, `product owner`. One search request per keyword; results merged by jobId; ~10 unique/keyword/page on a typical day.
- Live smoke (2026-06-18): 94 SourceJobs across the full PM keyword set, 48h window, IDF.
- Anti-bot: module raises `LinkedInBlockedError` on a captcha/checkpoint/verify marker, with a hard-stop on suspicious page-1 sizes. Won't hammer a rotated/blocked state.
- Search cards carry title/company/location/canonical_url/posted_at but NOT description text. The ranker works on title+company. If we want richer scoring, add a detail-fetch pass against `/jobs/view/{job_id}` later — out of MVP scope.

This source replaces `linkedin_gmail` as the primary LinkedIn signal. `linkedin_gmail` is retained as opt-in belt-and-suspenders (already-configured Gmail label survives the migration).

## Source: LinkedIn via Gmail (LIVE as of 2026-06-15)

**Working live via IMAP.** No OAuth bootstrap required.

Mechanism:
- User creates Gmail label `JobAlerts/LinkedIn` and a filter routing `from:jobs-noreply@linkedin.com` to it. ✅ Done.
- User configures 1–3 LinkedIn Job Alert subscriptions (PM Paris, Head of Product Paris, AI PM Paris). ⚠️ Current alerts are not Paris-locked — they return Germany-based PM roles. User-side LinkedIn settings tweak needed.
- Pipeline opens IMAP to `imap.gmail.com:993` with `GMAIL_SMTP_USER` + `GMAIL_SMTP_APP_PASSWORD` (same App Password used by v1's SMTP outbound), selects the label, fetches messages from the last N days, parses HTML.

Parser specifics (LinkedIn email layout observed June 2026):
- Each job card is wrapped in `<a href="https://www.linkedin.com/comm/jobs/view/{id}/?...">`.
- Title is in `<div class="font-bold ...">` inside the anchor.
- Company + location are in a `<p>` sibling of the title div, separated by U+00B7 `·`.
- Company logo's `<img alt="...">` is a stable backup signal for company.
- LinkedIn re-skins these every ~6 months. The parser emits a WARNING `"parsed 0 jobs from email id=… — LinkedIn template may have shifted"` so the operator sees template drift before silent breakage.

CLI:
```bash
# IMAP (default if GMAIL_SMTP_APP_PASSWORD is set)
py execution/personal_workflows/job_search_v2/sources/linkedin_gmail.py --days 7 --max-emails 20

# Force IMAP / OAuth
py execution/.../linkedin_gmail.py --auth imap --label JobAlerts/LinkedIn
py execution/.../linkedin_gmail.py --auth oauth  # uses GMAIL_TOKEN_PATH
```

## Source: Indeed via Gmail (LIVE as of 2026-06-15)

Same IMAP pattern as LinkedIn. Reuses `GMAIL_SMTP_USER` + `GMAIL_SMTP_APP_PASSWORD`. Module: [`sources/indeed_gmail.py`](../../execution/personal_workflows/job_search_v2/sources/indeed_gmail.py). User setup: Gmail label `JobAlerts/Indeed` + filter `from:(noreply@match.indeed.com OR jobsalerts@indeed.com OR alerts@indeed.com)`, plus a saved-search alert at fr.indeed.com.

## Source: Hellowork via Gmail (PROBATIONARY as of 2026-06-16)

**Pattern:** identical to `indeed_gmail` / `linkedin_gmail` — IMAP read, parse alert HTML, emit `SourceJob`. Module: [`sources/hellowork_gmail.py`](../../execution/personal_workflows/job_search_v2/sources/hellowork_gmail.py). Reuses `GMAIL_SMTP_USER` + `GMAIL_SMTP_APP_PASSWORD`. **Status: parser uses heuristic regex until a real alert email is captured to `tests/fixtures/hellowork_email_sample.html` and the parser is locked.**

User setup (once):
1. Create Gmail label `JobAlerts/Hellowork`.
2. Create a Gmail filter — pin the actual sender after the first alert arrives; placeholder:
   ```
   from:(noreply@hellowork.com OR alertes@hellowork.com OR no-reply@hellowork.com)
   ```
   Apply label `JobAlerts/Hellowork`, Skip the Inbox.
3. Sign up at hellowork.com → create a saved search (`Product Manager` / `Chef de produit`, Île-de-France) → enable daily email alert.
4. After the first alert, save its raw HTML to `tests/fixtures/hellowork_email_sample.html` and re-run the front-door synthetic.

## Source: Jobgether via Gmail (PROBATIONARY as of 2026-06-16)

**Pattern:** identical to `hellowork_gmail`. Module: [`sources/jobgether_gmail.py`](../../execution/personal_workflows/job_search_v2/sources/jobgether_gmail.py). Adds remote-first European PM coverage that France Travail / Hellowork / APEC under-index. **Status: parser uses heuristic regex until a real alert email is captured to `tests/fixtures/jobgether_email_sample.html` and the parser is locked.**

User setup (once):
1. Create Gmail label `JobAlerts/Jobgether`.
2. Create a Gmail filter — pin the actual sender after the first alert arrives; placeholder:
   ```
   from:(noreply@jobgether.com OR alerts@jobgether.com OR no-reply@jobgether.com)
   ```
   Apply label `JobAlerts/Jobgether`, Skip the Inbox.
3. Sign up at jobgether.com → create a saved search (`Product Manager`, remote-first, Europe) → enable daily email alert.
4. After the first alert, save its raw HTML to `tests/fixtures/jobgether_email_sample.html` and re-run the front-door synthetic.

### Parser drift detection (applies to all *_gmail sources)

Each `*_gmail` parser emits a WARNING `"parsed 0 jobs from email id=… — {site} may have shifted template"` when it processes a non-empty email but extracts zero jobs. That warning is the canary for template drift — surface it in the daily digest summary, not silently in logs.

---

## Cross-day dedup

[`normalizer/dedup.py`](../../execution/personal_workflows/job_search_v2/normalizer/dedup.py) maintains an SQLite seen-set at `.tmp/job_search_v2/seen.db`:

- Schema: `seen(content_hash PK, canonical_url, title, company, source, first_seen_at, last_seen_at)`.
- `content_hash = sha256(title|company|canonical_url)`. Canonical URL strips utm_* + tracking params and lowercases host.
- TTL = 60 days. A job not seen for 60 days expires and will be re-surfaced if it reappears (likely repost — surfacing is correct).
- The expiry sweep runs opportunistically on every `filter_new()` call; no separate cron needed.

This is the load-bearing fix for the v1 "AI Consultant: 7 every day" symptom.

---

## Contracts (single source of truth)

All inter-layer data passes through Pydantic v2 models defined in [`contracts.py`](../../execution/personal_workflows/job_search_v2/contracts.py):

- `SourceJob` — what each source adapter returns. Frozen.
- `NormalizedJob` — post-normalize. Includes `content_hash`, `canonical_url`, `also_seen_on`. Frozen.
- `RankedJob` — LLM-judge output. Joins back to `NormalizedJob.content_hash`. Frozen.
- Enums: `JobSource`, `ContractType`, `RemoteMode`, `JobTier`.

Helpers: `compute_content_hash(title, company, canonical_url)`, `canonicalize_url(url)`.

The whole point of the typed contracts is that an LLM-judge layer is only auditable if its inputs are stable. Untyped dicts crossing layer lines are the v1 anti-pattern this rule exists to kill.

---

## Front-door synthetic

[`tests/front_door_job_search_v2.sh`](../../tests/front_door_job_search_v2.sh) runs the full pipeline end-to-end against the fixture and asserts:

1. France Travail fixture produces ≥3 SourceJobs.
2. Normalize round-trips cleanly through `model_validate_json(model_dump_json(...))`.
3. First dedup run admits all jobs as new (cold DB).
4. Second dedup run with the same fixture admits zero new (persistent dedup proven).
5. Zero Adzuna URLs appear in v2 output.

Per [`~/.claude/rules/front-door-synthetic.md`](../../.claude/rules/front-door-synthetic.md), v2 is NOT "working" until this passes 5 consecutive runs.

---

## Cutover

- v2 is built alongside v1; v1 is untouched until cutover.
- Cutover trigger: front-door synthetic passes once, on real data (not just fixture).
- Cutover action: edit [`.github/workflows/job_search_daily.yml`](../../.github/workflows/job_search_daily.yml) to invoke the v2 orchestrator instead of `job_search_sheet.py`.
- v1 moves to `execution/personal_workflows/_archived/job_search_sheet_v1.py` for 30-day rollback.
- Until the synthetic passes 5 consecutive days, every status report leads with `PROBATIONARY FRONT-DOOR SYNTHETIC: day N of 5`.

---

## Edge cases / known constraints

- **France Travail empty days.** Government API has weak PM density; some days return <5 jobs. Mitigation: WTTJ + APEC sources fill the gap once wired.
- **Playwright fragility.** WTTJ/APEC selectors change. Mitigation: each source returns 0 cleanly on parse failure (not crash). Two consecutive 0-row days from one source raises red and emits a paged alert.
- **OneDrive sync.** `.tmp/job_search_v2/seen.db` lives under the OneDrive-synced workspace path. SQLite file locking + OneDrive sync can race. Mitigation: open with `isolation_level=None` (autocommit) and avoid long-held transactions. If lock contention shows up, move the DB to `~/.local/share/job_search_v2/seen.db` outside OneDrive.
- **Idempotency.** v2 inherits v1's GH-Actions dual-cron pattern (07:00 + 08:00 UTC for DST). The 23h idempotency guard moves into the v2 orchestrator (not yet built).

---

## Verification commands

```bash
# Front-door synthetic (must pass before any "ready" claim)
bash tests/front_door_job_search_v2.sh

# Inspect the persistent seen-set
py execution/personal_workflows/job_search_v2/normalizer/dedup.py

# Dry-run France Travail live (needs creds in .env)
py execution/personal_workflows/job_search_v2/sources/france_travail.py --query "product manager" --location Paris --max-pages 1
```

---

## Open follow-ups (post-v2.0)

- [ ] Wire `sources/wttj.py` (Playwright).
- [ ] Wire `sources/apec.py` (Playwright).
- [ ] Wire `sources/linkedin_gmail.py` (Gmail MCP ingestion).
- [ ] Build `ranker/score.py` with cached Anthropic rubric (Sonnet 4.6 + prompt cache + Message Batches API).
- [ ] Build `notifier/email.py` (Gmail MCP draft) and `notifier/sheet.py` (reuse existing sheets writer).
- [ ] Build `eval/` golden-set + weekly precision@5 / recall report.
- [ ] Cut the GH-Actions cron over to v2.
- [ ] Once `JobAlerts/Hellowork` and `JobAlerts/Jobgether` labels receive their first real alert: save raw HTML to `tests/fixtures/{site}_email_sample.html` and lock parser regexes against real layout.

## Exit Criteria

- `tests/front_door_job_search_v2.sh` passes 5 consecutive runs against the live system (per `~/.claude/rules/front-door-synthetic.md`).
- Every live source (`france_travail`, `linkedin_gmail`, `indeed_gmail`, `hellowork_gmail`, `jobgether_gmail`) emits at least 1 `SourceJob` in a 7-day window, or is explicitly logged as "no new postings in window" in the digest.
- Per-source jsonl files in `.tmp/job_search_v2/runs/run_<id>/` exist for every source listed in `--sources`.
- `seen.db` contains rows with `first_seen_at` < today, demonstrating cross-day dedup is active (not just an empty-DB cold start).
- The daily email digest output contains no Adzuna URLs (the v1 anti-pattern).
- Every `*_gmail` parser logs the "parsed 0 jobs from email" warning when an email contained no extractable job cards — silent zero from a known label is treated as template drift, not "no jobs today."
