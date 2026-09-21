# prodcraft_medspa_pipeline

ProdCraft "0.5 Website" lead-gen pipeline for independent med spas. Find every independent med spa
in a metro, audit its website, score it 0-100 for "outdated / can't convert bookings", build a
private preview site for the worst scorers, and hand-send personalized outreach from one aged
Google Workspace inbox. Manual outreach, automated everything upstream and the takedown/reply
path. Full spec: `execution/personal_workflows/prodcraft_medspa/PROJECT_SPEC.md`. Binding build
contracts: `execution/personal_workflows/prodcraft_medspa/CONTRACTS.md`. Panel-pass decisions this
directive assumes: `docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md`.

## Goal

Ship 5 hand-built previews and 5 hand-sent emails for Chicago North Shore (Phase 0), gate on
>= 1 call booked, then automate discovery -> audit -> enrich -> preview so the operator's only
daily manual work is sending 10-20 emails from the dashboard's drafts and taking the sales call.

## Inputs

- Env vars (see CONTRACTS.md "Secrets only via env" — every one is optional until the stage that
  needs it runs live; `doctor.py` lists exactly which stage needs which):
  `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GOOGLE_PLACES_API_KEY`, `PAGESPEED_API_KEY`,
  `ANTHROPIC_API_KEY`, `APOLLO_API_KEY`, `FINDYMAIL_API_KEY`, `HUNTER_API_KEY`,
  `MILLION_VERIFIER_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `R2_BUCKET`,
  `PREVIEW_BASE_DOMAIN`, `GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `GOOGLE_SHEETS_MIRROR_ID`, `DASHBOARD_USER`, `DASHBOARD_PASS`.
- `PRODCRAFT_STORE` (`local` | `supabase`, default `local`) and `PRODCRAFT_ENV` (free text, used in
  Telegram error lines).
- Discovery tiles: `execution/personal_workflows/prodcraft_medspa/discovery/tiles/{metro}.json`.
- Chain exclusion list: `db/seed_chains.json`. Seeded config (phase0 gate, proof lines, sender
  identity, touch-day plan): `db/seed_config.json`.

## Tools / Scripts

Every script supports `--mock` (fixtures, no network, no secrets) and `--store {local,supabase}`.

| Script | Purpose |
|---|---|
| `discovery/places_search.py` | Google Places Text Search (New) per tile, dedupe on `place_id`, chain/closed/too-small filtering. |
| `discovery/import_csv.py` | Ingest an operator-curated list (`--csv PATH --metro X`; columns name, website, phone, address, city, state, email, review_count, owner_name, place_id). Same chain/no-name/too-small filters as Places; CSV emails land as `email_status=unverified`. `run_metro.py --import-csv PATH` runs it as the first stage. |
| `audit/audit_site.py` | Full per-site audit: SSL, viewport, PSI, tech detect, booking-widget grep, CTA check, footer year, screenshots, vision score, scoring. |
| `audit/sample_audit.py` | Random N-business audit-only sample -> `metro_stats` row with a Wilson 95% interval. |
| `enrich/waterfall.py` | 6-step owner-name/email waterfall + MillionVerifier verification, gated on `--min-score`. |
| `preview/build_preview.py` | `business.json` -> template static build -> R2 upload -> Worker `/api/publish`. |
| `preview/takedown.py` | Immediate unpublish (deletes the R2 prefix, flips `previews.takedown`) for one business id. `take_down_preview(..., dnc=True)` (the default, used by both the remove and the negative-reply paths) also flags the business do-not-contact and closes its open outreach rows; `dnc=False` is an unpublish-only variant no in-tree caller uses. |
| `preview/approve.py` | CLI twin of the dashboard approve button: `review` -> `approved` for `--preview-id ID` or `--metro X --all-review`; logs an `events` row. `run_metro.py --auto-approve` (implied by `--mock`) runs it after the preview stage. |
| `preview/publish.py` | Worker API client (`/api/publish`, `/api/extend`, `/api/meta`) used by build_preview/takedown. Its CLI is the only way to extend a preview: `python3 -m execution.personal_workflows.prodcraft_medspa.preview.publish extend --preview-id ID --days 30 [--mock]`. There is no `preview/extend.py` module. |
| `outreach/daily_queue.py` | Today's queue: picks `config.queue_pick` (`random`, seeded by date+metro, or `score`) up to the phase0 cap, renders + lints drafts, re-renders rows whose last lint failed; `--create-drafts` also files Gmail drafts. |
| `outreach/send.py` | `--stats` prints the trailing-7-day sends-vs-cap JSON line and exits (sends nothing). Otherwise sends every lint-clean `drafted` row via Gmail (`gmail.send` scope) and transitions it to `sent`; enforces the daily cap across touches, the bounce halt, DNC, approved/live preview, and never mails a business that already replied. `--recipient-override EMAIL` (or env `PRODCRAFT_RECIPIENT_OVERRIDE`) redirects every message to the operator with a `[TEST to <owner_email>]` subject. |
| `outreach/scan_replies.py` | Classifies inbox replies; `remove` -> takedown + DNC; `negative` -> closed_lost + takedown + DNC (an opt-out: the watermark promises the preview comes down on a "no"; negative and remove differ only in Telegram routing/classification); bounce -> `email_status` patched by id; `positive`/`neutral` -> Telegram message to the operator (`notify.reply`), row marked replied, no further touches. The operator answers those threads by hand. A bare "no" (`No.`, `Nope`, `No thanks`) is `negative` or `remove`, never `neutral` (gold set: `fixtures/replies_gold.jsonl`, `tests/prodcraft_medspa/test_reply_gold.py`). Under `--mock`, `PRODCRAFT_MOCK_INBOX_DIR` points the scan at a test-owned folder of inbox `*.json` replies. |
| `outreach/advance.py` | Runs due state-machine transitions (e.g. `sent` -> next touch, `sent` -> `closed_lost`). |
| `deals/deals.py` | `record`/`golive`/`proof`/`list` — contract, baseline booking count, 60-day guarantee math. |
| `scripts/run_metro.py` | Chains discovery -> audit -> enrich -> preview for one metro; prints the funnel table. |
| `scripts/daily.py` | The unattended daily loop: advance -> scan_replies -> takedowns -> daily_queue -> send. `--no-send` keeps drafts only; `--recipient-override EMAIL`, `--limit N` pass through to send. |
| `scripts/doctor.py` | Env-presence + (with `--live`) one cheap authenticated call per service, Node/Chromium/node_modules checks. |
| `scripts/fit_weights.py` | Per-signal reply rate + point-biserial correlation from real outreach outcomes (never changes weights). `--report-telegram` posts the weekly summary; its last line is `sends vs cap (7d): S/C, per day s/c ...` (from `outreach/send.py`'s `sends_vs_cap`, warmup-ramped cap per day), also on the not-enough-data path. |
| `scripts/set_loom.py` | Touch-2 operator path: `--prospect-id <outreach id or business id> --url https://www.loom.com/share/...` records `notes.loom_url` (https + loom.com only, one validation path, exit 2 when invalid), redrafts a `drafted` row via `state_machine.redraft` only when the URL changed, prints the row state as one JSON line. `--touch N` (default 2) selects which touch's open row a business id resolves to. Idempotent: an unchanged URL neither patches nor redrafts. |
| `scripts/sync_sheets.py` | Mirrors two tabs, `pipeline` (v_pipeline + outreach/reply columns) and `daily_log` (one row per send), to the Google Sheet `GOOGLE_SHEETS_MIRROR_ID`; `--mock` writes CSVs; `--xlsx PATH` also writes a workbook. |
| `db/apply_schema.py` | Applies `db/schema.sql` and seeds chains/config into the target store. |

## Outputs

- `businesses`, `audits`, `previews`, `outreach`, `deals`, `metro_stats`, `config`, `events`,
  `chains` tables (Supabase in production; `LocalStore` JSON files under `.tmp/prodcraft_medspa/store/`
  for `--mock`/local runs).
- Live previews at `https://{slug}-{suffix}.preview.prodcraft.fyi`.
- Operator dashboard (Cloudflare Pages) — daily queue, preview approval, funnel stats, config editor.
- `.tmp/prodcraft_medspa/runs/{metro}_{timestamp}.json` — one record per `run_metro.py` run.
- `.tmp/prodcraft_medspa/fit_weights.json` — per-signal reply-rate/correlation table.
- Google Sheet tab `pipeline` (read-only mirror of `v_pipeline`) or `.tmp/prodcraft_medspa/v_pipeline.csv`
  under `--mock`.

## Steps

### One-time setup (operator's machine, real secrets)

1. Create the Supabase project; set `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and (optional, enables
   `apply_schema.py` to apply directly instead of printing for manual paste) `SUPABASE_DB_URL` in
   `.env`. Run `python3 db/apply_schema.py --store supabase`.
2. Create the R2 bucket and Worker: `preview/worker/README.md`'s "One-time setup" — `npm install`,
   `npx wrangler r2 bucket create prodcraft-previews`, `npx wrangler kv namespace create META` (paste
   the id into `wrangler.toml`), `npx wrangler secret put SUPABASE_URL` /
   `SUPABASE_SERVICE_KEY` / `REMOVE_WEBHOOK_SECRET`, `npm run deploy`. Add the wildcard CNAME
   `*.preview` on the `prodcraft.fyi` zone per that README's "DNS" section.
2b. Create the R2 S3 API token (Cloudflare dashboard > R2 > Manage R2 API Tokens > Object Read and Write on
   the bucket) and set `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`; `build_preview.py` uploads with them and
   `doctor.py --stages preview` reports them missing by name.
3. Deploy the dashboard: `dashboard/README.md`'s "Deploy" — `npx wrangler pages project create
   prodcraft-medspa-dashboard`, then `pages secret put` for `DASHBOARD_USER`, `DASHBOARD_PASS`,
   `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, then `npm run deploy`.
4. Gmail OAuth: run the standard Google OAuth installed-app flow for the aged Workspace inbox;
   save the resulting token as `GMAIL_TOKEN_JSON`, the client secret as `GMAIL_CREDENTIALS_JSON`.
5. Create the Telegram error channel, set `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, then verify:
   `python3 -m execution.personal_workflows.prodcraft_medspa.common.notify --sample`.
6a. Set the sender identity once (CAN-SPAM rules 1 and 3; every draft fails `lint_draft` until this is
   set, and `doctor.py --stages outreach` reports it): from the dashboard Config tab, or
   `python3 -c "from execution.personal_workflows.prodcraft_medspa.common.store import get_store; get_store().set_config('sender', {'name': 'Your Name, ProdCraft', 'physical_address': 'Street, City, ST ZIP', 'signature': ''})"`.
   Under `--mock` only, `draft_email.py` substitutes a clearly synthetic `MOCK_SENDER` so the mock chain
   reaches `drafted`.

6b. `python3 execution/personal_workflows/prodcraft_medspa/scripts/doctor.py --live` — every
   selected-stage row must show `OK`, every configured service's `live ok` column `yes`.

### The automated loop (operator standing order 2026-09-16: no human until a positive or neutral reply)

**Secrets set -> first live 5 sent, verbatim** (run from the repo root; `P=execution/personal_workflows/prodcraft_medspa`):

```bash
python3 $P/db/apply_schema.py --store supabase
python3 $P/scripts/doctor.py --live                      # every row OK before spending API budget
python3 $P/scripts/run_metro.py --metro chicago_north_shore --store supabase
# approve previews: manual gate (default) ...
python3 $P/preview/approve.py --metro chicago_north_shore --store supabase --all-review --yes-i-reviewed-them
# ... or the automated gate (opt in once: set_config('auto_approve_previews', True)); the cron runs this step daily
python3 $P/scripts/preview_gate.py --metro chicago_north_shore --store supabase
python3 $P/scripts/daily.py --store supabase --recipient-override you@example.com   # dry run to your inbox
# read every email and preview on a phone, then:
#   set_config('live_send_confirmed', True); clear PRODCRAFT_RECIPIENT_OVERRIDE; set PRODCRAFT_CRON_ENABLED=true
```

The first live day sends `phase0.warmup_start_cap` (2) and ramps to `phase0.cap` (5) over `phase0.warmup_days`
(14); dry-run rows do not start the ramp. Reconciling this with `.claude/rules/automation-boundaries.md`: the outbound
email is first-draft copy from a human-authored template pool with a lint gate and a mandatory dry run, so per-send
auto-ship is judged compliant; the human stays in the loop for every reply and for preview approval unless the
operator opts into `auto_approve_previews`.

7. **Measure the metro first** (cheap): `python3 execution/personal_workflows/prodcraft_medspa/scripts/run_metro.py
   --metro chicago_north_shore --stages discovery,audit --sample-n 40 --sample-only`. Review the funnel and the
   `metro_stats` row (PROJECT_SPEC.md §5.3, §14). Without a Places key, feed a curated list instead:
   `run_metro.py --metro X --import-csv path/to/spas.csv --stages discovery,audit` (the import stage runs first).
8. **Config keys that shape the loop** (set once via the dashboard Config tab or `store.set_config`):
   `sender` (name + postal address; CAN-SPAM, drafts fail lint until set), `queue_pick` (`random` default, 5 random
   qualified businesses a day; `score` for highest-score-first), `email_policy` (`deliverable_only` default;
   `allow_unverified` only for a metro without a verifier key or a dry run), `min_score` (default 45 = qualified;
   lower it only when PSI/vision keys are missing and 40 of 100 points are unmeasurable; the value is recorded on
   every preview row), `preview_publish_mode` (`r2` default; `local` keeps exports under `.tmp/prodcraft_medspa/r2/`
   for hand hosting), `proof_lines`, `phase0`.
9. **Dry run to your own inbox first.** Set the repo variable `PRODCRAFT_RECIPIENT_OVERRIDE=<your address>` (or pass
   `--recipient-override`) so every send goes to you with a `[TEST to <owner_email>]` subject; the store still
   records the real owner email and `test_recipient`. Run `run_metro.py --metro X --auto-approve` (local store; on
   Supabase, approve previews in the dashboard or with `preview/approve.py --metro X --all-review --yes-i-reviewed-them`
   after looking at them) then `daily.py --recipient-override you@example.com`. Read every email and preview on a
   phone. Clear the variable only when the copy, the previews and the sender block are what you would send yourself.
10. **Arm the crons.** Set `PRODCRAFT_CRON_ENABLED=true` and every secret named in
    `.github/workflows/prodcraft_medspa_daily.yml` (daily 9am Chicago: run_metro -> daily.py -> sync_sheets) and
    `prodcraft_medspa_replies.yml` (every 30 minutes: advance -> scan_replies -> takedowns). They share one
    concurrency group and post to Telegram on failure. Also set the repo variable `PRODCRAFT_LIVE_RECIPIENTS=true`
    once you're ready for real sends — without it `send.py` refuses to send in `github-actions` even with
    `PRODCRAFT_RECIPIENT_OVERRIDE` unset (round-3 audit item 8; see CONTRACTS.md "Live-recipients gate"). From here
    the loop is unattended: discover, audit, build, approve (dashboard, or the operator's `approve.py`), pick 5,
    send, scan.
11. **What the operator does:** read Telegram. A positive or neutral reply arrives as one message (business, owner,
    summary, suggested next step, preview link, Gmail thread link); answer that thread yourself. Negative replies and
    remove requests both close the row, take the preview down within the 30-minute scan and mark the business
    do-not-contact (they differ only in how the Telegram alert is labelled); bounces feed the 2% halt.
    Weekly, open the Google Sheet (`pipeline` and `daily_log` tabs).
11b. **Touch 2 parks until you record a Loom.** Record the walkthrough, then run
    `python3 execution/personal_workflows/prodcraft_medspa/scripts/set_loom.py --store supabase --prospect-id <outreach id or business id> --url https://www.loom.com/share/... [--touch N]`
    (`--store local --store-root $R` for a mock store; `--touch N` defaults to 2 and only matters when you pass a
    business id, picking that touch's newest open row). It validates the URL, writes `notes.loom_url`, redrafts the
    parked row (only if the URL changed; re-running with the same URL is a no-op) and prints its state; the next
    `daily.py` re-renders and sends it. `send.py` posts one Telegram line
    per day with the parked count so you know when this is due.
12. If a prospect replies interested but cannot meet before the preview expires, extend it:
    `python3 -m execution.personal_workflows.prodcraft_medspa.preview.publish extend --preview-id ID --days 30`
    (renews `expires_at` on the Worker and the store, logs an `extended` event, warns if touch 4 already stated the
    old deadline). Follow up per PROJECT_SPEC.md §8.2; `daily.py` advances touches and sends the next one.
13. Gate: `python3 scripts/daily.py --phase0-status`. `calls_booked >= 1` -> flip `config.phase0.passed` (dashboard
    Config tab) and the daily cap lifts 5 -> 20. `calls_booked == 0` after the first 5 close out -> rewrite the
    email/offer per PROJECT_SPEC.md §3 step 5 before widening.
14. Weekly: `scripts/sync_sheets.py`; after >= 50 touch-1 sends, `scripts/fit_weights.py` (rows with
    `test_recipient` set are your own dry runs and must be excluded from any reply-rate statistic). The Monday
    Telegram report (`prodcraft_medspa_weekly.yml`) ends with `sends vs cap (7d): S/C, per day s/c ...`; the same
    number on demand: `python3 execution/personal_workflows/prodcraft_medspa/outreach/send.py --store supabase --stats`.

### Next metro

17. Per PROJECT_SPEC.md §3 Phase 4: only re-run this directive for the next metro (Minneapolis-St.
    Paul, per PROJECT_SPEC.md §1's ordered list) after >= 3 paid clients in the current one. Add a
    new `discovery/tiles/{metro}.json` first (mirror `chicago_north_shore.json`'s tile shape).

## Edge Cases

- **Places API 60-result cap per query.** Discovery tiles the metro into ~3km circles so no single
  tile query needs more than 60 results; if a suburb is denser than that, split its tile further
  (PROJECT_SPEC.md §4).
- **PSI throttle.** Keyless PageSpeed Insights is rate-limited; `audit_site.py` should back off on
  429s. Get a `PAGESPEED_API_KEY` (free, 25k/day) before running a full metro, not just a sample.
- **Chain list maintenance.** `db/seed_chains.json` is a name-substring list, not exhaustive —
  new regional chains will slip through discovery's filter. When you spot one in the funnel's
  "operational" stage, add its pattern and re-run `db/apply_schema.py` to reseed.
- **State-registry scrapers rot.** IL SOS / MN SOS / OH SOS / MI LARA / INBiz have no public APIs;
  `enrich/`'s registry step scrapes search pages. This is the most likely step to break silently —
  see the self-healing change log below.
- **Bounce halt.** `outreach.daily_queue`'s cap logic halts the queue (returns `[]` with a printed
  reason) when the rolling 30-day bounce rate exceeds 2% (CONTRACTS.md's state-machine section).
  Do not override this by hand without first fixing the email source that's bouncing.
- **Takedown SLA.** `outreach/scan_replies.py` on the 30-minute cron flips takedown/DNC automatically
  for remove/opt-out language; `daily.py --replies-only` (what the cron runs) does the same path
  manually if the cron isn't armed yet. Either way, honor every request — see
  `docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md` Amodei #1-2.
- **Phase 0 gate semantics.** `config.phase0` starts `{"passed": false, "queue_cap_locked": 5,
  "queue_cap_open": 20}`; nothing in this pipeline widens the queue past 5/day until a human
  flips `passed` to `true` after a real call books. `run_metro.py` and `daily.py` never do this
  automatically — it is a judgment call, not a metric threshold (Karpathy #3, Saraev #1).
- **`--mock` shortcuts two human steps, on purpose.** `run_metro.py --mock` appends the `approve`
  stage (every review preview -> approved) and `draft_email.py --mock` uses `MOCK_SENDER` when
  `config.sender` is empty, so the chain `apply_schema -> run_metro --mock -> daily.py --mock` ends
  with a non-empty, fully drafted queue. Neither happens on a live run: previews wait for a human
  approve (dashboard or `preview/approve.py`) and an empty sender fails the lint.
- **Operator-authored personalization.** A business row may carry `llm_overrides: {"extract_services": {...},
  "fuzzy_variables": {...}}`; the pipeline uses it instead of calling the model (model_id `manual:operator`,
  recorded on the row). Overrides still pass the services allowlist, content lint and the CAN-SPAM lint.
- **Degraded-mode audit.** Without `PAGESPEED_API_KEY` and `ANTHROPIC_API_KEY`, `psi_mobile`, `is_mobile_friendly`
  (when a viewport meta exists) and `vision_dated_score` are None and score 0: at most 60 of 100 points are
  measurable and the 45 threshold is rarely reached. Set the keys before judging a metro; a lowered `min_score`
  is a dry-run setting, not a scoring decision.
- **What `--mock` proves and doesn't.** Every stage's `--mock` path runs against fixtures with no
  network and no secrets — it proves the code paths, JSON shapes, and store writes are correct. It
  does *not* prove a live API contract still matches (field names, rate limits, auth flow); that's
  what `doctor.py --live` and the first live `run_metro.py --sample-n 40` are for. Never report a
  metro as "audited" or a preview as "shipped" from a `--mock` run alone.
- **Missing packages in a fresh checkout.** `run_metro.py` and `daily.py` run every stage as a
  subprocess and treat `ModuleNotFoundError` as a normal stage failure with a clear message (not a
  crash) — several packages (`discovery/`, `audit/`, `enrich/`, `preview/*.py`, `outreach/`,
  `deals/`) were being built by other agents concurrently with this orchestrator and may not exist
  yet in a given checkout.

## Self-healing change log

Standing instruction (per `.claude/rules/automation-boundaries.md`): if the same error recurs more
than 3 times across `run_metro.py` / `daily.py` / the 30-minute reply-scan cron, assume something
material changed in the external system (a scraped registry page's HTML, an API's field names, a
rate limit). Investigate with full autonomy, fix the *implementation* (the affected script), then
append an entry here: `{date, problem, solution, what was changed}`. Never rewrite this directive's
Steps/Edge Cases sections without operator approval per CLAUDE.md's operating principles — only this
change log grows on its own. State-registry scrapers (see Edge Cases above) are the most likely
source of entries.

*(no entries yet)*

## Honest gaps

Copied from `docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md`; keep this section current as
gaps close.

- No secrets exist in the cloud environment, so every live integration (Places, PSI, Claude vision,
  Apollo, Findymail, MillionVerifier, Supabase, Cloudflare, Gmail) is exercised only through
  fixtures and `--mock`. First live run happens on the operator's machine after `doctor.py` is green.
- The `preview.prodcraft.fyi` DNS zone, the R2 bucket, the Supabase project, and the Telegram error
  channel must be created by the operator once — see "One-time setup" above for the exact commands.
- State-registry lookups (IL SOS, MN SOS, OH SOS, MI LARA, IN INBiz) have no public APIs. The
  enrichment step implements search-page scrapers with fixtures; they are the most likely step to
  rot and carry the self-healing change-log instruction above.
- Vision golden set (`audit/fixtures/vision_golden/`) is synthetic until the operator labels 20 real
  screenshots.
- Phase 0 (five hand-sent emails, a human on the sales call) is a human act by definition; the
  pipeline prepares it but cannot pass it for you.
- `run_metro.py`'s "total estimated cost" is a floor, not a real total: it only sums a `cost_usd`
  field when a stage's stat line reports one, and not every stage is guaranteed to report cost.
  Cross-check against PROJECT_SPEC.md §12's ~$90-130/mo reference figure, don't trust the number
  alone.
- `fit_weights.py`'s point-biserial correlations are only as good as the audit signal definitions
  it mirrors from CONTRACTS.md — if `audit/scoring.py`'s exact fail conditions drift from that
  table, the two will silently disagree. Re-sync the `SIGNALS` dict in `fit_weights.py` whenever
  `audit/scoring.py` changes.
