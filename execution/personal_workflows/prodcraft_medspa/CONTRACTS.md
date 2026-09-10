# ProdCraft med-spa pipeline — build contracts

Binding for every package in this directory. Read `PROJECT_SPEC.md` for the why and
`docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md` for the decisions D1–D11 that amend it.

## Layout

```
execution/personal_workflows/prodcraft_medspa/
  __init__.py
  common/            store.py (Store interface, LocalStore, SupabaseStore), models.py (dataclasses), llm.py,
                     notify.py (Telegram error channel), slug.py, http.py (retry session), config.py (env + paths)
  db/                schema.sql, migrations/, seed_chains.json, seed_config.json, apply_schema.py
  discovery/         places_search.py, tiles.py, tiles_chicago_north_shore.json, fixtures/
  audit/             audit_site.py, scoring.py, tech_detect.py, booking_detect.py, screenshots.py, vision.py,
                     psi.py, sample_audit.py, fixtures/ (html pages, psi json, vision_golden/)
  enrich/            waterfall.py, contact_page.py, gbp_reviews.py, state_registry.py, apollo.py, findymail.py,
                     hunter.py, verify.py (wraps execution/enrichment/million_verifier.py), fixtures/
  preview/           build_preview.py (business.json → template build → R2 upload), extract_services.py,
                     content_lint.py, takedown.py, worker/ (TypeScript CF Worker: wildcard host, expiry cron,
                     /remove endpoint, /expired page)
  template/          Next.js 15 App Router, Tailwind, static export, reads business.json at build time
  dashboard/         static HTML/JS + functions/ (Pages Functions, Basic Auth middleware, Supabase REST via service key)
  outreach/          daily_queue.py, draft_email.py, lint_draft.py, gmail_drafts.py, scan_replies.py,
                     state_machine.py, fixtures/
  deals/             deals.py (record, baseline, 60-day proof, guarantee computation)
  prompts/           vision_audit.md, extract_services.md, email_touch_1_a.md, _b.md, _c.md, email_touch_2.md,
                     email_touch_3.md, email_touch_4.md, classify_reply.md, fuzzy_variables.md
  scripts/           run_metro.py, doctor.py, fit_weights.py, sync_sheets.py
tests/prodcraft_medspa/   pytest; test_<package>.py; acceptance_template.py (Playwright, both viewports)
directives/personal_workflows/prodcraft_medspa_pipeline.md
```

Package import root: `execution/personal_workflows/prodcraft_medspa` is a package; every script is runnable as
`python3 -m execution.personal_workflows.prodcraft_medspa.<pkg>.<script>` from the repo root AND as
`python3 execution/personal_workflows/prodcraft_medspa/<pkg>/<script>.py` (add the repo root to `sys.path` at the
top of each script via `common.config.bootstrap()`).

## Python rules (non-negotiable)

- Python 3.11 syntax and stdlib only, plus: `requests`, `python-dotenv`, `pydantic>=2` (optional, prefer dataclasses),
  `anthropic`, `playwright` (audit + tests only; guard the import so scripts without Playwright still run `--help`).
- `.claude/rules/python-hardening.md` and `python-execution.md` apply: module docstring with `description:` /
  `inputs:` / `outputs:`; `load_dotenv()`; argparse; no bare `except: pass`; subprocess calls carry
  `encoding="utf-8", errors="replace"`; locks around shared state in thread pools; LLM- or API-derived paths are
  resolved and boundary-checked; no `#!/usr/bin/env python` shebang.
- Every script has `--mock` (uses `fixtures/`, no network, no secrets) and `--store {local,supabase}`
  (default from env `PRODCRAFT_STORE`, fallback `local`). `--mock` implies `--store local` unless overridden.
- Every dropped row is written with a `drop_reason`; nothing is silently skipped. Every script ends by printing a
  one-line JSON stat (`{"script": ..., "in": n, "out": n, "dropped": {...}}`) to stdout.
- Secrets only via env. Names (all optional unless the stage runs live):
  `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GOOGLE_PLACES_API_KEY`, `PAGESPEED_API_KEY`, `ANTHROPIC_API_KEY`,
  `APOLLO_API_KEY`, `FINDYMAIL_API_KEY`, `HUNTER_API_KEY`, `MILLION_VERIFIER_API_KEY`, `CLOUDFLARE_API_TOKEN`,
  `CLOUDFLARE_ACCOUNT_ID`, `R2_BUCKET` (default `prodcraft-previews`), `PREVIEW_BASE_DOMAIN`
  (default `preview.prodcraft.fyi`), `GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `GOOGLE_SHEETS_MIRROR_ID`, `DASHBOARD_USER`, `DASHBOARD_PASS`.
- LLM calls go through `common/llm.py`: model pinned to `claude-sonnet-5` for extraction/classification and
  `claude-fable-5-1` for vision scoring, `temperature=0`, records `model_id`, `prompt_sha256`, `usage` (all four
  token counts) in the returned envelope. `--mock` returns fixture responses keyed by prompt name.
- Error channel: any script's top-level failure calls `common.notify.error(service, error, count=1)`; shape
  `service / environment / error / count`; no-op without Telegram env (logs to stderr instead).

## Store interface (`common/store.py`)

```python
class Store(Protocol):
    def upsert_business(self, row: dict) -> dict            # keyed on place_id; returns row with id
    def get_business(self, business_id: str) -> dict | None
    def find_businesses(self, **filters) -> list[dict]        # metro=, bucket=, has_email=, do_not_contact=
    def insert_audit(self, row: dict) -> dict
    def latest_audit(self, business_id: str) -> dict | None
    def upsert_preview(self, row: dict) -> dict              # keyed on (business_id, content_hash)
    def update_preview(self, preview_id: str, patch: dict) -> dict
    def upsert_outreach(self, row: dict) -> dict             # keyed on (business_id, touch)
    def update_outreach(self, outreach_id: str, patch: dict) -> dict
    def queue(self, today: date, cap: int) -> list[dict]     # next_touch_at <= today, status in (queued, sent)
    def upsert_deal(self, row: dict) -> dict
    def insert_metro_stats(self, row: dict) -> dict
    def get_config(self, key: str, default=None)
    def set_config(self, key: str, value) -> None
    def log_event(self, entity: str, entity_id: str, event: str, payload: dict | None = None) -> None
    def chains(self) -> list[str]
```
`LocalStore(root=".tmp/prodcraft_medspa/store")` keeps one JSON file per table and is fully functional.
`SupabaseStore` uses PostgREST over `requests` with the service key (`Prefer: resolution=merge-duplicates` for
upserts). Both pass the same `tests/prodcraft_medspa/test_store.py` contract suite (Supabase tests skip without env).

## `business.json` (template input contract, produced by `preview/build_preview.py`)

```json
{
  "schema_version": "1.0",
  "name": "Glow Aesthetics", "slug": "glow-aesthetics", "slug_suffix": "k3x9qa",
  "city": "Winnetka", "state": "IL", "address": "123 Green Bay Rd, Winnetka, IL 60093",
  "phone": "(847) 555-0100", "phone_href": "tel:+18475550100",
  "hours": [{"day": "Mon", "open": "9:00 AM", "close": "6:00 PM"}, ...],   // 7 entries, closed = null open/close
  "services": [{"name": "Botox", "blurb": "Schedule a consultation.", "icon": "syringe"}, ...],  // 3–8, generic blurbs
  "rating": 4.8, "review_count": 132, "google_maps_url": "https://maps.google.com/?cid=...",
  "tagline": "Book your next treatment in under a minute.",
  "primary_color": "#7C5CFF", "accent_color": "#F4F1EA",
  "hero_image": "hero-01.jpg",          // from template/public/stock/ only
  "preview": {"expires_at": "2026-10-10", "remove_url": "https://.../remove", "watermark": "Concept preview by ProdCraft — not affiliated with or endorsed by Glow Aesthetics. Remove: reply 'remove'."},
  "booking_demo": true
}
```
The template must build with any JSON that validates against `template/business.schema.json`. The template never
fetches anything at runtime except its own static assets. `<meta name="robots" content="noindex,nofollow">` and
`robots.txt` disallow-all are unconditional.

## Scoring (`audit/scoring.py`, pure, `SCORE_VERSION = "1.0"`)

| Signal | Points | Fail condition (exact) |
|---|---|---|
| no_booking_widget | 22 | `booking_widget is None` |
| not_mobile_friendly | 15 | `is_mobile_friendly is False` (no viewport meta OR PSI mobile-friendly audit fails) |
| poor_performance | 15 / 10 | `psi_mobile < 50` → 15; `50 <= psi_mobile < 70` → 10; else 0; `None` → 0 |
| dated_design | 15 | `vision_dated_score >= 7` |
| no_cta_above_fold | 10 | `has_cta_above_fold is False` |
| no_ssl | 8 | `has_ssl is False` |
| old_builder | 8 | builder in {wix, godaddy} OR (builder == wordpress AND theme_year < 2018) OR has_jquery_legacy |
| no_analytics | 4 | `has_analytics is False` |
| stale_footer | 3 | `footer_year is not None and footer_year <= current_year - 2` |
| no_website | 100 | `has_website is False` (short-circuit; other signals null) |

Buckets: `>= 45` qualified · `25–44` borderline · `< 25` skip. `score()` returns
`{"total": int, "bucket": str, "gaps": [{"signal", "points", "human_phrase"}], "score_version"}` with gaps
ordered by points desc. `human_phrase` is the customer-safe wording used in emails (never "your site is bad";
always the lost-booking framing, e.g. "clients can't book without calling").

## Outreach state machine (`outreach/state_machine.py`)

States: `queued, drafted, sent, replied, call_booked, closed_won, closed_lost, dnc`. Touch days: 0, 3, 7, 12.
Transitions (anything not listed raises `IllegalTransition`):
`queued→drafted`, `drafted→sent`, `sent→replied`, `sent→queued(next touch)` (creates touch+1 row when touch<4),
`sent→closed_lost` (touch 4 and `next_touch_at + 5d` passed), `replied→call_booked`, `replied→closed_lost`,
`call_booked→closed_won`, `call_booked→closed_lost`, `*→dnc`. `dnc` also sets `businesses.do_not_contact`,
`previews.takedown`, and cancels all other touches. Every transition logs an `events` row.
Queue cap: `config.phase0.passed` false → 5/day, true → 20/day. Queue halts (returns `[]` with a printed reason)
when rolling 30-day bounce rate `> 2%`.

## Template (Next.js) acceptance (tests/prodcraft_medspa/acceptance_template.py)

Static export served locally; Playwright checks at 390×844 (mobile emulation) and 1440×900:
no horizontal overflow (`scrollWidth <= innerWidth + 1`), a booking CTA (`[data-cta="book"]`) fully inside the first
viewport, watermark bar visible, `noindex` meta present, no console errors, total transfer < 1.5 MB, every image
has `width`/`height`/`alt`, `/remove` link present, no forbidden medical-claim terms in rendered text.
The reference site the operator likes (`evolution-exhibits-v4.pages.dev`) breaks on phones; this test is the guard.

## Fixtures

Fixtures are synthetic. No real business names, emails, or phone numbers; use the `example-medspa-*.test`
domains and `(847) 555-01xx` numbers. Fixture directories are committed; `.tmp/` is not.
