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
                     content_lint.py, publish.py (Worker API + `extend` CLI), approve.py (review → approved CLI),
                     takedown.py, worker/ (TypeScript CF Worker: wildcard host, expiry cron,
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
- Every script that reads or writes the Store has `--mock` (uses `fixtures/`, no network, no secrets)
  and `--store {local,supabase}` (default from env `PRODCRAFT_STORE`, fallback `local`). `--mock`
  implies `--store local` unless `--store` is given explicitly — and `--mock` combined with an
  explicit `--store supabase` is a hard `parser.error` (exit 2), never a silent override
  (code-reviewer C4/M1: `--mock` must never reach a live Supabase store). Centralised in
  `scripts/_stage_runner.py`'s `resolve_store_kind()` / `reject_mock_with_supabase()` — call the
  latter immediately after `parser.parse_args()`. Pure-function CLIs that touch no store
  (`preview/content_lint.py`, `outreach/lint_draft.py`, `preview/r2.py --selftest`,
  `common/notify.py --sample`, `scripts/doctor.py`, `outreach/gmail_drafts.py`,
  `preview/extract_services.py`'s standalone CLI) take neither flag. Known gap:
  `audit/scoring.py --recompute` DOES call `get_store()` (has `--store` already) but has no
  `--mock` yet — out of scope for this pass (owned by the audit/ package), flagged for its owner.
  "No network" under `--mock`
  means no external HTTP calls; `preview/build_preview.py --mock` is the one exception that still
  runs a real local process, `npm run build` (local Node, no network) — pass `--skip-build` to
  synthesize a minimal site instead and skip that too.
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
    def list_rows(self, table, *, order_by=None, descending=False, limit=None, **filters) -> list[dict]
                                                              # generic read; equality filters only,
                                                              # None value means "column is null";
                                                              # table validated against an allowlist
    def get_row(self, table: str, row_id: str) -> dict | None  # single row by id, or None
    def update_row(self, table: str, row_id: str, patch: dict) -> dict
                                                              # generic patch-by-id; stamps updated_at
                                                              # for tables that have the column
    def claim_row(self, table: str, row_id: str, from_status: str, to_status: str) -> bool
                                                              # (round-3 item 11) atomic compare-and-set:
                                                              # patches `status` to `to_status` ONLY IF the
                                                              # row's current status is still `from_status`
                                                              # at write time; returns whether the claim
                                                              # succeeded. Two concurrent callers racing the
                                                              # same row: exactly one gets True. The
                                                              # sanctioned way to guard against a double-send
                                                              # (send.py claims drafted->sent before mailing).
    def manual_patch(self, table: str, id: str, patch: dict, reason: str) -> dict
                                                              # update_row() + logs a "manual_patch" event
                                                              # {table, id, fields: list(patch), reason} —
                                                              # the sanctioned way for an operator/dashboard
                                                              # hand-correction to leave an audit trail
    def purge_pii(self, business_id: str, reason: str) -> dict
                                                              # blanks owner_name/owner_email/phone/email_source
                                                              # on the business row and Gmail ids + reply_* on
                                                              # its outreach rows, stamps pii_purged_at, logs
                                                              # "pii_purged". See "PII retention" below.
    def list_previews(self, business_id: str) -> list[dict]   # thin list_rows() wrapper, newest first
    def list_outreach(self, business_id: str) -> list[dict]   # thin list_rows() wrapper, newest first
    def load_chains(self, patterns: list[dict]) -> int        # seed helper: merge {"pattern","note"} rows by pattern
```

`upsert_preview` merge guard (both LocalStore and SupabaseStore): when a re-upsert hits the same
`(business_id, content_hash)` key, the merge never lets the incoming row downgrade `status` from
`approved`/`live` back to `review` (a re-build of already-approved/live content must not clobber
an operator's or dashboard's forward progress), and never lets it silently overwrite an already-set
`subdomain_url` with a different one. Both are enforced by stripping those two fields from the
incoming row before the merge when they'd regress it — every other field still updates normally.
The returned row's `id` is always the *existing* row's id in this case, never a fresh uuid, so
callers (e.g. `preview/build_preview.py`) must use the returned row's `id` for anything downstream
(publish calls, `log_event`) rather than an id generated before the upsert.

## PII retention

`Store.purge_pii(business_id, reason)` is the mechanism; `scripts/purge_pii.py` is the CLI. Policy:
a `dnc` (do-not-contact) business's PII is purged within **10 business days** of the dnc transition
— run manually by the operator today (`purge_pii.py --business-id ID --reason ...`); a scheduled
worker may automate this later. A `closed_lost` deal/prospect's PII is purged after **180 days**
with no further contact. Purge never deletes rows (ids/statuses/timestamps/`do_not_contact` and the
funnel/audit trail all survive) — it blanks the fields listed in `common/store.py`'s
`_BUSINESS_PII_FIELDS`/`_OUTREACH_PII_FIELDS` and stamps `pii_purged_at`.
`LocalStore(root=".tmp/prodcraft_medspa/store")` keeps one JSON file per table and is fully functional.
`SupabaseStore` uses PostgREST over `requests` with the service key (`Prefer: resolution=merge-duplicates` for
upserts). Both pass the same `tests/prodcraft_medspa/test_store.py` contract suite (Supabase tests skip without env).

`list_rows`/`get_row`/`update_row` are the only sanctioned way for callers outside `common/store.py` to reach
table data the narrow accessors above don't cover (e.g. "every row in a table", "a preview by id", "patch any
row by id"). Callers must never reach into `LocalStore._read`/`_write` or `SupabaseStore._request`/`_headers`
directly — `table` is checked against the `TABLES` allowlist (`businesses, audits, previews, outreach, deals,
metro_stats, config, events, chains`) so an LLM- or caller-derived table name can never reach an arbitrary
PostgREST path; `get_row`/`update_row` are further restricted to `ID_TABLES` (`TABLES` minus `config` and
`chains`, which have no `id` column) and raise `ValueError` otherwise. Every filter/order-by key (caller- or
LLM-derived) is validated against `[a-z_][a-z0-9_]*` before it can reach a PostgREST query string; filter and
id values are always sent via `requests` `params=` as `(key, value)` tuples, never f-string-interpolated into
the URL, so `+`/`#`/`&` in a value can't mangle or inject into the query, and booleans are normalised to
`true`/`false`. `SupabaseStore.list_rows` paginates internally (1000-row pages via `Range-Unit`/`Range`) so a
full-table read isn't silently truncated at PostgREST's server-side row cap; `limit` still caps the total.
`insert_audit`/`insert_metro_stats` generate a client-side uuid `id` and upsert
(`resolution=merge-duplicates`) so a retried POST after a lost 5xx response can't duplicate the row;
`log_event`'s POST is not retried on 5xx (only on 429/connection errors) since `events` has no natural key to
de-dupe on. `LocalStore.upsert_business` raises `ValueError` on a `slug` collision with a different
`place_id`, mirroring the unique constraint on `businesses.slug` in `db/schema.sql`.

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
  "preview": {"expires_at": "2026-10-10", "remove_url": "https://.../remove", "watermark": "Concept preview by ProdCraft , not affiliated with or endorsed by Glow Aesthetics. Not for you? Reply 'no' to the email and this preview comes down."},
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

## Audit legibility: `mode` and `max_measurable` (`audit/audit_site.py`, `audit/scoring.py`)

Every `audits` row stamps `mode text` (`full` or `degraded`): `full` only when PSI, the Claude
vision pass, and Playwright screenshots all actually ran and returned a value for that business;
anything skipped (`--skip-vision`/`--skip-screenshots`, `--mock`, a fetch/PSI failure, no
`website_url`) yields `degraded`. `scoring.score()` also returns `max_measurable` (int): the sum
of points for every signal whose underlying measurement was present (not `None`), independent of
whether that signal passed or failed. `no_booking_widget` (22 pts) is always measurable once a
site was fetched (grep-based, no external dependency); `no_website` short-circuits both `mode`
(`degraded`) and `max_measurable` (100) to full observability. Purpose: a `total_score` of 30 with
`max_measurable: 45` (mostly degraded) reads very differently from 30 with `max_measurable: 100`
(fully measured, genuinely low-risk) — CONTRACTS.md scoring table's raw points alone can't tell
those apart. `audits.llm_cost_usd numeric(8,4)` (migration 0004) persists the vision-call cost
`audit_site.py` was already computing but dropping. `audit_site.py`'s stdout stat line adds a
`modes: {full, degraded}` breakdown alongside `buckets`.

## `fit_weights.py` (`scripts/fit_weights.py`) — inputs and filters

Reads `outreach` touch-1 sends joined to each business's latest matching `audits` row (never
patches scoring weights; measurement only). Filters, all optional:
- `--metro NAME` (default: all metros) — matches `businesses.metro` exactly.
- `--mode {full,degraded,all}` (default `full`) — matches `audits.mode` exactly; an audit row
  predating the `mode` column (value absent/`None`) matches only `--mode all`, never `full` or
  `degraded`, since we don't know what it measured.
- `--min-sent N` (default 50) — refuses to fit (prints why, writes nothing) below this many
  touch-1 sends in the filtered population.

Output `.tmp/prodcraft_medspa/fit_weights.json` stamps `metro` (the filter value or `"all"`),
`mode`, and `queue_pick` (the live `config.queue_pick` value at run time) alongside the existing
per-signal reply-rate/point-biserial table, plus a new `template_variants` table: reply rate per
`outreach.template_variant` (`a`/`b`/`c`; sends predating variants group under `"unknown"`).

`--report-telegram` posts a 7-line-max compact summary (scope, touch-1 sent + reply rate, top-2
signals by `|point_biserial_r|`, best template variant, `queue_pick`) via the new
`common.notify.weekly_report(lines)` — same Telegram transport/env/no-op behavior as
`notify.error`/`notify.reply`. Below `--min-sent`, it instead posts `"not enough data yet:
N/50 sends"`. Under `--mock`, `--report-telegram` prints the lines instead of sending (per the
existing `--mock` = no-network rule).

## `outreach.score_at_send` (migration 0004; owned by `daily_queue.py`)

`outreach.score_at_send integer` = the `total_score` of the audit referenced by
`outreach.audit_id`, stamped by `daily_queue.enqueue_new_touch1()` when the row is **enqueued**
(touch 1, `next_touch_at = today`) — not, despite the column's name, at the later moment it's
actually sent. This is intentional: `fit_weights.py`'s `touch1_outcomes()` joins each outreach row
to that SAME `audit_id` (falling back to the business's latest audit only when `audit_id` is
unset), so the enqueue-time score is exactly the regressor fit_weights measures against. A
re-audit or manual score patch between enqueue and send is deliberately NOT reflected here —
reading `total_score` back off the latest audit later can disagree with `score_at_send`, and that
divergence is itself informative (the site changed, or was corrected, after this touch was queued
on the old number). A row predating migration 0004 has `score_at_send = null`; treat that as "not
backfilled," not "score was zero."

## `outreach.queue_pick_effective` (migration 0005; owned by `daily_queue.py`; round-3 item 16)

`outreach.queue_pick_effective text` (`"random"`/`"score"`) records what actually governed THIS
row's touch-1 enqueue — may differ from the raw `config.queue_pick` while `phase0.passed` is
still false (see `daily_queue._pick_mode()`). Previously stamped only on the `outreach_enqueued`
events row (unreadable by `fit_weights.py` without an events join); now also on the outreach row
itself, so `scripts/fit_weights.py`'s `queue_pick_effective_table()` can report reply rate grouped
by it directly. A row predating migration 0005 has `queue_pick_effective = null`, grouped under
`"unknown"` in that table.

## `audits.superseded` / `audits.superseded_reason` (migration 0005; round-3 item 21)

Two columns the live store already wrote before `db/schema.sql`/the migration set caught up to
them (a Supabase apply of a fresh schema would have 400'd the first write). `superseded boolean
default false` marks an audit row that a later audit for the same business has replaced as "the"
audit; `superseded_reason text` records why (e.g. `"re-audit"`, `"manual correction"`). No
Python caller in this checkout sets them yet — the columns exist so a write from elsewhere in the
pipeline (or a future one) doesn't fail against the schema.

## Guarantee evidence (`deals/deals.py`) — `evidence_ref`

`deals record --baseline N` requires `--evidence-ref` (a URL or file ref to the client's baseline
booking export/screenshot) whenever `--baseline` is given; stored as `deals.baseline_evidence_ref`.
`deals proof --bookings-60d N` requires `--evidence-ref` for the day-60 evidence unconditionally,
and also refuses if the deal's `baseline_evidence_ref` was never captured — both raise `ValueError`
with the missing-evidence explanation rather than silently proceeding. See PROJECT_SPEC.md §9.1 for
the self-reported-booking-counts rationale and the `ZERO_BASELINE_FLOOR` rule.

## Weekly measurement routine (`.github/workflows/prodcraft_medspa_weekly.yml`)

Monday 15:00 UTC (gated on the `PRODCRAFT_CRON_ENABLED` repo variable, same as
`prodcraft_medspa_replies.yml`; same `prodcraft-medspa` concurrency group so the two workflows
never race the store). Runs `fit_weights.py --store supabase --report-telegram` against the live
Supabase store; posts a Telegram error on workflow failure via `notify.error`. Dependency install
is scoped to `execution/personal_workflows/prodcraft_medspa/requirements.txt`, matching the
replies workflow.

### The "5 weekly numbers" (what the operator should see every Monday)

| Number | Source |
|---|---|
| Sends vs cap | `config.phase0.{queue_cap_locked,queue_cap_open}` vs actual `outreach` rows with `sent_at` in the trailing 7 days (not yet computed by `fit_weights.py`; read `outreach`/`config` directly until a dedicated stat lands) |
| Touch-1 reply rate | `fit_weights.py`'s `overall_reply_rate` (this file's `touch1_outcomes()` / `compute_signal_table()`) |
| Rolling bounce rate | The 30-day bounce-rate gate already enforced by `outreach/state_machine.py`'s queue halt (CONTRACTS.md "Outreach state machine") — not part of `fit_weights.json` today |
| `pct_qualified` per metro | `metro_stats.pct_qualified` (PROJECT_SPEC.md §5.3 `sample_audit`), one row per metro |
| Cost per business | `audits.llm_cost_usd` summed per business (or per metro) over `audits`; `audit_site.py`'s stdout stat line also reports a per-run `llm_cost_usd` total |

## Round-2 audit additions (`outreach/send.py`, `outreach/daily_queue.py`, `outreach/draft_email.py`, `outreach/scan_replies.py`, `scripts/daily.py`)

- **Preview-host guard (`send.py`)**: a live send (`--mock` not passed) WITHOUT
  `--recipient-override` refuses to send any row whose preview's `publish_mode != "r2"` or whose
  `subdomain_url` host doesn't end with `config.preview_host_suffix` (default
  `.preview.prodcraft.fyi`) — dropped as `preview_not_public`, logged as a `send_dropped` event,
  row left `drafted` (not transitioned). `--recipient-override` bypasses the guard entirely
  (prints an unmistakable `WARNING: --recipient-override bypasses the preview-host guard`
  banner) since an operator dry-run never reaches a real prospect. `--mock` is also exempt (it
  never reaches a real prospect either — it writes a `.eml` file).
- **`List-Unsubscribe` header (`send.py`)**: every sent message (mock and live) carries
  `List-Unsubscribe: <mailto:{authenticated_address}?subject=unsubscribe>` alongside the body's
  plain-text opt-out line `lint_draft.py` already requires.
- **Live-recipients gate (`send.py`, round-3 audit item 8)**: `PRODCRAFT_RECIPIENT_OVERRIDE` (or
  `--recipient-override`) resolves an unset/misnamed value to `""` -> `None`, which is
  indistinguishable from an operator who deliberately wants live sends — so under
  `PRODCRAFT_ENV == "github-actions"` with no override resolved, `send.py` additionally requires
  the repo variable `PRODCRAFT_LIVE_RECIPIENTS == "true"`; otherwise it refuses with
  `dropped.live_recipients_not_enabled` and a single `notify.error`. Wired into all three
  workflows' `env:` blocks (`prodcraft_medspa_daily.yml`, `_replies.yml`, `_weekly.yml`) even
  though only the daily workflow currently reaches `send.py`.
- **Phase-0 warmup ramp (`daily_queue.effective_cap`, used by both `daily_queue.py` and
  `send.py`)**: `config.phase0.warmup_days` (default 14) and `config.phase0.warmup_start_cap`
  (default 2) ramp the effective daily cap linearly: `min(phase0.cap, warmup_start_cap +
  floor(days_since_first_live_send * (phase0.cap - warmup_start_cap) / warmup_days))`. Before any
  live send exists, the effective cap is `warmup_start_cap`. "First live send" is the earliest
  `sent` outreach row with **no** `test_recipient` — an operator dry-run to their own inbox never
  starts the ramp clock. `--mock` runs (and any caller passing `mock=True`) are **never** ramped
  (`effective_cap` returns the plain `phase0.cap`, falling back to `_queue_cap()`'s locked/open
  value) so the mock chain's day-one DoD (4 sends) is unaffected. Both scripts print the resolved
  cap as `"cap"` in their stdout stat line.
- **Queue-pick phase gate (`daily_queue._pick_mode`)**: while `config.phase0.passed` is `false`,
  the effective pick mode is `config.phase0.queue_pick_until_passed` (default `"score"`)
  regardless of `config.queue_pick` — Phase 0 must validate against real replies, not a random
  sample, even if the operator's steady-state preference is `"random"`. Once `phase0.passed` is
  `true`, `config.queue_pick` governs as documented below. The `outreach_enqueued` event's payload
  carries both `queue_pick` (raw config value) and `queue_pick_effective` (what actually governed
  this enqueue).
- **`score_at_send` (`daily_queue.enqueue_new_touch1`)**: `outreach.score_at_send` is stamped from
  the business's `audits.total_score` at enqueue time (see the dedicated section below); a later
  re-audit never retroactively changes an already-enqueued row's value.
- **Stable per-business template variant (`draft_email.pick_variant`)**: `variant="auto"` is now a
  STABLE hash of `business_id` — `["a","b","c"][int(sha1(business_id).hexdigest(), 16) % 3]` — not
  a rotating counter. A re-render of an outreach row that already has `template_variant` set
  reuses that value rather than recomputing, so a redraft never flips a business's variant.
- **Negative reply takedown, without DNC (`scan_replies.py`)**: a `negative` reply still goes
  `sent -> replied -> closed_lost`, and ALSO takes down every non-takendown preview linked to that
  business via the same real unpublish path (`preview/takedown.py`'s `take_down_preview()` — R2
  prefix delete + Worker `/remove`) the `dnc`/`remove` flow uses — but this is explicitly **not**
  a do-not-contact request: `businesses.do_not_contact` is left/reverted to its prior value and no
  other outreach rows are cascaded. (This amends the "closed_lost... no forced takedown" line
  below, which still holds for every OTHER path into `closed_lost` — touch-4 grace expiry via
  `advance.py`, etc. — a negative reply is the one exception.)
- **Remove reply also notifies (`scan_replies.py`)**: a `remove` reply keeps its existing
  `dnc` + takedown behavior and now ALSO posts the same Telegram alert `common.notify.reply()`
  sends for a positive/neutral reply, with `sentiment` forced to `"remove"` regardless of what the
  classifier's own `sentiment` field said. The row's `notes.remove_source` records which
  classifier flagged it: `"keyword"` under `--mock`'s deterministic matcher (`_mock_classify`),
  `"llm"` on the live classifier path.
- **Config validation on `daily.py`**: `scripts/daily.py` calls
  `common.config_validate.assert_valid_config()` (same key subset as `run_metro.py`'s own check)
  immediately after opening the store, before running any stage — an invalid value exits 1 with a
  `common.notify.error("daily", ...)` call rather than letting a stage silently degrade on it.
  `daily.py`'s own post-scan takedown loop stays a harmless no-op for any business already taken
  down by `state_machine.py`'s dnc path or the new negative-reply path above (idempotent, per
  `preview/takedown.py`'s own status check).

## Round-3 audit additions (`outreach/send.py`, `outreach/daily_queue.py`, `outreach/scan_replies.py`, `outreach/state_machine.py`, `scripts/daily.py`, `common/notify.py`)

- **`needs_operator_input` send guard (`send.py`, CRITICAL item 18)**: a `drafted` row is refused
  — dropped as `needs_operator_input`, logged as a `send_skipped` event, left `drafted` — when
  EITHER `notes.needs_operator_input` is true (daily_queue.py's lint-failure escalation, or
  lint_draft's own `needs_operator_input` flag for an unresolved `[[LOOM URL]]` placeholder) OR
  its rendered subject/body still contains an unresolved `[[...]]`/`{{...}}` token. This closes
  the gap item 1's lint fix opened: once the `[[LOOM URL]]` placeholder legitimately passes lint
  (rule 6 no longer trips on it), nothing else was stopping it from being mailed to a real
  prospect. One `notify.once_per_day` per day, naming the held-back count, not one per row/run.
  `daily_queue._drafted_pending_count()` excludes these rows from the daily cap count (they will
  never leave `drafted` on their own, so counting them would starve fresh drafting every day
  after) — an operator fixes the missing value (e.g. sets `notes.loom_url`) and calls
  `state_machine.redraft()` to send it back through the pipeline.
- **Atomic send claim (`send.py`/`Store.claim_row`, CRITICAL item 11)**: before mailing, `send.py`
  claims `drafted -> sent` via `Store.claim_row` (see Store interface above); a failed claim
  (another process already claimed the row) is dropped as `already_claimed` and the send is
  skipped — the actual compare-and-set that prevents two concurrent `send.py` processes from
  double-mailing the same row. A pre-send failure (header injection, a Gmail error) releases the
  claim (`claim_row(..., "sent", "drafted")`) so a retry can pick the row back up.
- **Fresh cap re-read per send (`send.py`, item 6)**: the remaining daily cap is
  `max(0, cap - _sent_today_count(...))`, re-read immediately before EACH send inside the loop —
  not a counter decremented once in memory — so two concurrent processes sharing one Store can't
  each work off a stale copy and together exceed the day's cap.
- **Bounce-halt / zero-candidates / needs-operator-input notify (`send.py`, items 12/18)**: a
  bounce-rate halt, a day with 0 candidates, and a batch of `needs_operator_input` holds all now
  page the operator via `common.notify.once_per_day(store, dedupe_key, service, message, today)`
  — deduped per calendar day per `dedupe_key` via `config['notify_dedupe']`, so a re-run of the
  same day's cron doesn't spam the channel. `send.py`'s live-recipients gate (below) and daily.py's
  config-validation failure use a plain `notify.error()` instead (misconfiguration, not a
  recurring daily state).
- **CI-log redaction (`common/notify.py`, item 4)**: under `PRODCRAFT_ENV == "github-actions"`,
  `notify.error()`/`notify.reply()`'s stderr fallback (used when Telegram is unconfigured or the
  send itself fails) prints a redacted line instead of the full text — stderr there is a
  persisted CI log, and the full text can carry an owner name/email, business name, or reply
  quote. The Telegram message itself is never redacted either way.
- **PII purge widened (`common/store.py`, item 5)**: `_OUTREACH_PII_FIELDS` now also blanks
  `notes` (Gmail ids, `llm_classify` output which can quote the prospect's own words),
  `draft_subject`, `draft_body` (rendered with the owner's first name and the business name) —
  previously left behind after a purge.
- **Lint-failure escalation (`daily_queue.py`, CRITICAL item 2)**: a row that fails lint has
  `next_touch_at` pushed forward one day and `notes.lint_fail_count` incremented; at
  `LINT_FAIL_LIMIT` (3) consecutive failures, `notes.needs_operator_input` is set and it's
  excluded from the selectable `queued` set (see `_needs_operator_input()` in both
  `daily_queue.py` and `send.py`) and dropped from `_drafted_pending_count()`'s cap accounting —
  a permanently-broken draft no longer eats the whole day's warmup cap forever. A single
  `notify.error()` fires on the transition into flagged (not on every subsequent failure).
- **One reply, one business (`scan_replies.py`, CRITICAL item 3)**: replies are now fetched and
  processed per BUSINESS, not per outreach row — a business can have multiple `sent` rows at once
  (touch 1 stays `sent` forever unless replied; `advance.py` creates touch 2+ as a separate row),
  and `gmail_reader.search_replies(owner_email)` matched the SAME inbound message for every
  sibling row. A message is classified/notified once per business per pass; every sibling row
  gets `notes.seen_reply_ids` updated so a later scan never reprocesses it.
- **Malformed classifier response (`scan_replies.py`, item 13)**: the live LLM call + `json.loads`
  around one reply's classification is wrapped in try/except — one bad response logs
  `classify_error`, calls `notify.error()`, and marks the message seen (skipped, not retried into
  a notify loop) without aborting the rest of the scan pass.
- **Negative-reply Telegram alert (`scan_replies.py`, item 15)**: a `negative` classification
  (which now, per item 1, can also come from a touch-2/3/4 draft the same way remove/positive do)
  posts the same `notify.reply()` alert as positive/neutral/remove, with the classification's
  provenance (`"llm"` live, `"keyword"` under `--mock`) folded into the summary — a
  misclassification that silently kills a live preview link is no longer silent.
- **Takedown reconciliation (`state_machine.reconcile_takedowns`, CRITICAL item 10)**: called from
  `scripts/daily.py` after every scan pass (normal and `--replies-only`) — finds every business
  that is `do_not_contact` OR has an outreach row `closed_lost` whose preview(s) are not
  `status == "takedown"`, and retries the real unpublish path for each, logging a
  `takedown_retry` event per attempt. A failed retry pages the operator once per preview per day
  (item 14, via `_notify_takedown_failure`/`notify.once_per_day`) and never aborts the rest of the
  reconcile pass or `daily.py` itself.
- **`phase0.calls_to_pass` (`state_machine.py`, item 17)**: `phase0.passed` no longer flips on the
  FIRST `call_booked` transition — it requires `config.phase0.calls_to_pass` (default 3,
  validated 1..20 in `common/config_validate.py`) `call_booked` transitions. Each one still
  increments `phase0.calls_booked`; the threshold check moved off a bare `set_passed_at=1`. A
  `phase0_passed` event logs the field/value/threshold the moment it flips.
- **`redraft()` never writes a `reason` column (`state_machine.py`, item 19)**: `outreach` has no
  `reason` column in `db/schema.sql` — `transition()` now strips `reason` out of the generic
  `patch` it sends to `Store.update_outreach()` for every non-`sent`/non-`dnc` transition
  (previously `redraft(store, id, reason)` → `transition(..., reason=reason)` would 400 against
  Supabase). `reason` still lands in the transition's logged `events` row (`{"fields": {...}}`)
  — the audit trail this existed for.
- **`daily.py` prints send.py's full stdout, not just its stat line (item 20)**: `send.py`'s
  RECIPIENT OVERRIDE banner, its preview-host-guard-bypass WARNING, and any `SEND BLOCKED: ...`
  line are printed to stdout, not carried in the final JSON stat line — `daily.py`'s "--- send
  output ---" block now prints the captured stdout in full (matching how the daily_queue step
  above it already does), so none of those reach the cron log silently dropped.

## Outreach state machine (`outreach/state_machine.py`)

States: `queued, drafted, sent, replied, call_booked, closed_won, closed_lost, dnc`. Touch days: 0, 3, 7, 12.
Transitions (anything not listed raises `IllegalTransition`):
`queued→drafted`, `drafted→sent`, `drafted→queued` ("redraft" — a lint/QA rejection or an operator
restart; use the `redraft(store, outreach_id, reason)` helper, which logs the transition's
`events` row with `reason` in the payload rather than calling `transition()` directly),
`sent→replied`, `sent→queued(next touch)` (creates touch+1 row when touch<4),
`sent→closed_lost` (touch 4 and `next_touch_at + 5d` passed), `replied→call_booked`, `replied→closed_lost`,
`call_booked→closed_won`, `call_booked→closed_lost`, `*→dnc`. `dnc` sets `businesses.do_not_contact`,
cancels all other touches, and calls the real takedown path — `preview/takedown.py`'s
`take_down_preview()` (R2 prefix delete + Worker `/remove`), not just a status flip — for every
non-takendown preview on the business; this is idempotent (a preview already marked `takedown` is
skipped, logging `takedown_requested` with `outcome: already_takendown` instead of re-running it),
so a later `scripts/daily.py` takedown pass over the same row is a safe no-op. Tests inject
`transition(..., takedown_fn=...)` to stub the real R2/Worker call. Every transition logs an
`events` row.
Queue cap: `config.phase0.passed` false → 5/day, true → 20/day. Queue halts (returns `[]` with a printed reason)
when rolling 30-day bounce rate `> 2%`. `config.phase0.queue_pick_until_passed` (default `"score"`):
`daily_queue.py` (owned by fixsend) uses this queue-pick strategy while `phase0.passed` is `false`,
and falls back to `config.queue_pick` once phase0 has passed — validated by
`common/config_validate.py` alongside `queue_pick` itself.

`config.auto_approve_previews` (bool, default `false` in `db/seed_config.json`): manual review in
the dashboard stays the default gate on every preview before it's linked to a prospect; setting
this `true` is an explicit operator opt-in for `preview/approve.py` to bulk-approve without a human
look at each one (that script's own behavior change is owned by whoever implements it — this repo's
contract is just the config key + `common/config_validate.py`'s bool check).

## Template (Next.js) acceptance (tests/prodcraft_medspa/acceptance_template.py)

Static export served locally; Playwright checks at 390×844 (mobile emulation) and 1440×900:
no horizontal overflow (`scrollWidth <= innerWidth + 1`), a booking CTA (`[data-cta="book"]`) fully inside the first
viewport, watermark bar visible, `noindex` meta present, no console errors, total transfer < 1.5 MB, every image
has `width`/`height`/`alt`, `/remove` link present, no forbidden medical-claim terms in rendered text.
The reference site the operator likes (`evolution-exhibits-v4.pages.dev`) breaks on phones; this test is the guard.

## Fixtures

Fixtures are synthetic. No real business names, emails, or phone numbers; use the `example-medspa-*.test`
domains and `(847) 555-01xx` numbers. Fixture directories are committed; `.tmp/` is not.
