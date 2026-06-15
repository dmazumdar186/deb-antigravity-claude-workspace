# Job Search Sheet v2 (directive)

**Paired script:** [execution/personal_workflows/job_search_v2/](../../execution/personal_workflows/job_search_v2/)
**Replaces:** `execution/personal_workflows/job_search_sheet.py` (v1) — see [JOB_SEARCH_SHEET_AUDIT.md](../../JOB_SEARCH_SHEET_AUDIT.md) for the v1 audit and rationale for the rebuild.

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
| 1. Sources | One adapter per origin. Each returns `list[SourceJob]`. | `sources/france_travail.py`, later `sources/wttj.py`, `sources/apec.py`, `sources/linkedin_gmail.py` |
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

## Source: WTTJ (fixture-only as of 2026-06-15)

Built but **not live-functional.** Status:
- httpx + `__NEXT_DATA__` extraction path: WTTJ moved their hydration off of `__NEXT_DATA__`; the blob is no longer in the response.
- Playwright fallback: page renders, but job cards require interactive search submission (the bare URL with query params shows marketing copy, not results). Headless `goto + networkidle` is insufficient.

To make WTTJ live: either (a) extend the Playwright path to dismiss cookies + submit the search form + wait for cards (brittle, ~2h work), or (b) route through Firecrawl (`firecrawl_scrape` with JSON extraction) which handles consent + render — ~1 credit/run, robust to template churn. **Recommended**: Firecrawl when its token is restored.

Module is left in place with fixture support so the synthetic still passes layer integration.

## Source: APEC (fixture-only as of 2026-06-15)

Built but **not live-functional.** Status:
- httpx + BeautifulSoup path: APEC's search page is server-shelled then hydrated via Angular XHR calls. Raw httpx response has 0 offer URLs.
- Playwright direct goto: page renders the Didomi cookie-consent modal + "Vous avez déjà un compte?" gate before any job results. Headless render doesn't get past the consent layer.

Same recommendation as WTTJ: Firecrawl when restored, or extend Playwright to accept-cookies + wait for `/cms/webservices/rechercheOffre` XHR response, or self-throttled Apify actor as paid fallback.

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
