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
| `audit/audit_site.py` | Full per-site audit: SSL, viewport, PSI, tech detect, booking-widget grep, CTA check, footer year, screenshots, vision score, scoring. |
| `audit/sample_audit.py` | Random N-business audit-only sample -> `metro_stats` row with a Wilson 95% interval. |
| `enrich/waterfall.py` | 6-step owner-name/email waterfall + MillionVerifier verification, gated on `--min-score`. |
| `preview/build_preview.py` | `business.json` -> template static build -> R2 upload -> Worker `/api/publish`. |
| `preview/takedown.py` | Immediate unpublish (deletes the R2 prefix, flips `previews.takedown`) for one business id. |
| `outreach/daily_queue.py` | Today's queue (score desc, cap per phase0 gate), optional Gmail draft creation. |
| `outreach/scan_replies.py` | Classifies inbox replies; flags remove/opt-out language for takedown + DNC. |
| `outreach/advance.py` | Runs due state-machine transitions (e.g. `sent` -> next touch, `sent` -> `closed_lost`). |
| `deals/deals.py` | `record`/`golive`/`proof`/`list` — contract, baseline booking count, 60-day guarantee math. |
| `scripts/run_metro.py` | Chains discovery -> audit -> enrich -> preview for one metro; prints the funnel table. |
| `scripts/daily.py` | The operator's morning command: advance -> scan_replies -> takedowns -> daily_queue --create-drafts. |
| `scripts/doctor.py` | Env-presence + (with `--live`) one cheap authenticated call per service, Node/Chromium/node_modules checks. |
| `scripts/fit_weights.py` | Per-signal reply rate + point-biserial correlation from real outreach outcomes (never changes weights). |
| `scripts/sync_sheets.py` | Mirrors `v_pipeline` to a Google Sheet tab `pipeline` (or CSV under `--mock`). |
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
3. Deploy the dashboard: `dashboard/README.md`'s "Deploy" — `npx wrangler pages project create
   prodcraft-medspa-dashboard`, then `pages secret put` for `DASHBOARD_USER`, `DASHBOARD_PASS`,
   `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, then `npm run deploy`.
4. Gmail OAuth: run the standard Google OAuth installed-app flow for the aged Workspace inbox;
   save the resulting token as `GMAIL_TOKEN_JSON`, the client secret as `GMAIL_CREDENTIALS_JSON`.
5. Create the Telegram error channel, set `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, then verify:
   `python3 -m execution.personal_workflows.prodcraft_medspa.common.notify --sample`.
6. `python3 execution/personal_workflows/prodcraft_medspa/scripts/doctor.py --live` — every
   selected-stage row must show `OK`, every configured service's `live ok` column `yes`.

### Phase 0 (manual smoke test — do this before any cron is armed)

7. `python3 execution/personal_workflows/prodcraft_medspa/scripts/run_metro.py --metro
   chicago_north_shore --sample-n 40` — discovery + a 40-site audit sample, no enrich/preview yet.
   Review the printed funnel and `metro_stats` row; this replaces the spec's 40% qualification
   guess with a measured one for this metro (PROJECT_SPEC.md §5.3, §14).
8. Re-run `run_metro.py --metro chicago_north_shore` with default stages (no `--sample-n`) to
   audit/enrich/preview the full pull, or hand-pick the top 5 by score with a findable owner name
   per PROJECT_SPEC.md §3 Phase 0 step 2 and build previews for just those 5 by hand.
9. Review each preview in the dashboard's Previews tab; flip `review` -> `approved` only for the
   ones you'd actually send.
10. `python3 execution/personal_workflows/prodcraft_medspa/scripts/daily.py` — prints the queue
    (capped at 5 by the phase0 gate); hand-edit and send each draft from Gmail.
11. Follow up per PROJECT_SPEC.md §8.2 (day 3 Loom, day 7 proof line, day 12 breakup). Run
    `daily.py` each morning; it advances due touches and drafts the next one.
12. Gate: `python3 scripts/daily.py --phase0-status`. `calls_booked >= 1` -> `config.phase0.passed`
    flips true (set via the dashboard's Config tab or `deals.py`), and the queue cap lifts 5 -> 20.
    `calls_booked == 0` after all 5 close out -> rewrite the email/offer per PROJECT_SPEC.md §3 step
    5 and retry with 5 new prospects before automating anything further.

### Phase 1+ (after the gate passes)

13. Arm the reply-scan cron: set the `PRODCRAFT_CRON_ENABLED` repo variable to `true` (GitHub repo
    Settings -> Secrets and variables -> Variables) and add every secret named in
    `.github/workflows/prodcraft_medspa_replies.yml` to GitHub Secrets. The workflow is inert
    (`if: vars.PRODCRAFT_CRON_ENABLED == 'true'`) until this is done.
14. Run `run_metro.py --metro chicago_north_shore` daily or on a schedule of your choosing (not yet
    cron'd — discovery/audit/enrich/preview are cheap but not zero-cost; PROJECT_SPEC.md §12).
15. Run `daily.py` every morning; send from the dashboard's drafts.
16. Weekly: `scripts/sync_sheets.py` to refresh the read-only Sheets mirror; after >= 50 touch-1
    sends, `scripts/fit_weights.py` to see which audit signals actually predict replies.

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
