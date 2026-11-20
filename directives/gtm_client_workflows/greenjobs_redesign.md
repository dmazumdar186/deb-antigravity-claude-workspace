# GreenJobs (greenjobs.ie + greenjobs.co.uk) redesign demo

## Purpose

A public static demo of both job boards owned by Keith Molony (Gaia Talent Ltd), built on their live
data, to back the €1,875 redesign proposal and to open the "move off the current vendor" conversation.
Companion to `gaia_redesign.md` (same pipeline pattern, different visual lane). Spec, critique and
panel pass: `deliverables/greenjobs_redesign_2026-09-22/research/`.

Live: https://greenjobs-redesign.pages.dev/ (Cloudflare Pages, the only host; github.io is retired and
redirects here). Evidence page: `<base>/ie/for-keith/`
(not linked from the public nav).

## Inputs

- `deliverables/greenjobs_redesign_2026-09-22/src/` — templates, `css/`, `js/`, `assets/` (fonts,
  maps, logos), `data/` (`ie.json`, `uk.json`, `brief.md`, `regions_*.json`, `perf_*.json`).
- Facts on public pages come only from `data/*.json` and `data/brief.md`.

## Process

1. Refresh data (optional, ~14 min): `python3 execution/gtm_client_workflows/greenjobs_redesign/scrape_greenjobs.py --site both`
   (polite: 4 workers, 0.3 s sleep; Mozilla UA; no keys).
2. Maps only when geometry changes: `python3 .../make_maps.py` (Natural Earth admin-1 → `assets/maps/{ie,uk}.svg`).
3. Build: `python3 .../build_site.py --src deliverables/greenjobs_redesign_2026-09-22/src --out deliverables/greenjobs_redesign_2026-09-22/site --edition both`
   (always `both`; a single edition leaves cross-edition links dangling). Runs node tests, validator,
   byte budgets (CSS ≤ 80 KB, JS ≤ 125 KB). `--out` allow-list and `.greenjobs-build` marker as in Gaia;
   `.greenjobs-build-ok` (sha256 of the tree) is written only after the validator passes and is the deploy gate.
4. Tests: `python3 tests/greenjobs_redesign/run_all.py` (python build/validate/scrape/gaps + `node --test` lib/dashboard +
   Playwright DOM and layout tiers; a skipped browser tier fails the run unless `--allow-skip`; prints the total
   check count and writes it to `tests/greenjobs_redesign/COVERAGE.md`); screenshots: `bash .../screenshot.sh`
   then look at every PNG in `.tmp/greenjobs_redesign_shots/`.
5. Audit stack + panel pass (roster in `.claude/memory/panel_roster.md`); fix; rebuild.
6. Publish: `bash .../deploy_cloudflare.sh` (project `greenjobs-redesign`; refuses without a fresh
   `.greenjobs-build-ok` and re-runs `validate_site.py <site>` first). `curl -sI` the base URL and
   one job page. `publish_gh_pages.sh` is retired (exits 2); github.io holds redirect stubs only.

## Hero footage (Higgsfield)

`python3 execution/gtm_client_workflows/greenjobs_redesign/generate_hero_footage.py --edition ie --env-file <path to .env> --duration 10`
prints the free estimate; add `--go` to spend (guarded by `--max-usd`, default 1.50). It polls, downloads, and cuts
`src/assets/hero/{ie,uk}.mp4`, `-m.mp4` (portrait) and `-poster.jpg` with ffmpeg; the next build picks them up.
Prompts live in the script (`PROMPTS`) and in `research/hero_footage_brief.md`. Model: Kling 3.0 Pro by
default since 2026-09-28 (1080p source; the 2026-09-24 Standard estimate was 10 s 16:9 = 13.44 credits / $0.84; 5 s = $0.42). The key is `HF_API_TOKEN=key_id:secret`
in the operator's `.env`; `api.higgsfield.ai` is behind Cloudflare and blocks non-browser user agents (error 1010),
the script sets one. `not_enough_credits` (HTTP 403) means the **API console** balance, separate from the app plan,
is below the estimate: top up at the Higgsfield API console, then re-run. On 2026-09-24 the balance was below
4.5 credits, so nothing was generated.

## Exit criteria

- Build exits 0; validator green; job pages == dataset length per edition; every apply link is the
  real listing URL; no "(0)" sector, no employer named as "hiring now" without a live role; public
  pages carry no "AI"/"Claude"/vendor names; `noindex` everywhere; 200 on `/`, `/ie/`, `/uk/`,
  `/ie/jobs/`, one job page, `/ie/for-keith/` on Cloudflare.

## Edge cases

- Both boards run the same hosted platform (jQuery 1.11, Bootstrap 3, `sjbimg.com`); the IE home page
  is 190 KB HTML / 1,090 links. The sites name "GreenJobs Ltd, Ennis" as owner, not Keith; the
  B Corp footer mark links to a B Lab explainer that never states GreenJobs' own certification —
  show the mark only, claim nothing.
- UK jobs carry no sector tags: sectors are keyword-derived (the evidence page says so).
- greenjobs.ie shows UK-located roles with sterling figures relabelled as €. Sterling rule: `sterling_correction()`
  restores the greenjobs.co.uk twin's GBP figures when the twin matches by id, slug or title + employer AND the
  (salary_min, salary_max) pair is numerically identical (the source relabels 1:1); several adverts share a slug,
  so the nearest posted date wins among figure-matching twins. Roles without a twin keep the scraped euros,
  are flagged `unverified_cur` (2 on the 22 Sept snapshot) and never enter a median, band, guide or dashboard
  figure; the salary guide says so. Displayed figures are never converted; the bracketed equivalent uses 1.17.
  Human-eye r1 #3 (2026-09-29): `salary_stats(jobs, ed)` is the single computation behind the home band, insights,
  salary guide, guides index, dashboard and film payload; `test_r1_pages_agree_and_job_ctx` builds both editions
  and asserts the four pages print the same count/share/bands. `sector_stat()` counts by the same rule.
- Import normalisation (human-eye r1 #4/#19/#32): `sanitise_html` → `unwrap_bold_lines` (whole-line
  `<strong>`/`<b>` dropped, inline kept), `bullets_to_lists` ("* ", "- ", "• " lines across `<br>`/`<p>` join one
  `<ul>`), `collapse_blank_lines` (empty `<p>`, `<br>` runs); `tidy_text` fixes "UK/ Ireland" in title, summary and
  location. A job with no logo file borrows its employer's, else `logo_img` prints a monogram. Job page header ctx:
  `closed_chip` (hidden "Closed" chip) and `sal_caveat` (unverified-currency line under the chips); a location
  chip equal to the loc badge label ("UK") is dropped. Landing intros: ≤60 words, banned-phrase test in r2a.
- Snapshot data goes stale within a week: the hero carries a snapshot date; re-scrape before resending.
- wrangler ≥ 4.136 delegates `pages project create` to Workers and fails: `--force` is required.
- Sticky-footer layout stretches `main` inside a capture window taller than the page; screenshot.sh
  sets per-page heights so this is not mistaken for a layout bug.
- A screenshot "before/after" slider was dropped: greenjobs.ie serves no assets to a headless browser
  (Firecrawl token invalid in cloud), so a capture is unstyled and unfair; the comparison stays data-based.
- The "Ask GreenJobs" / "Your fit" panel is a local TF-IDF matcher. The Cloudflare Worker stub in `worker/` expects
  `OPENROUTER_API_KEY` (or an Anthropic key) as a Worker secret; nothing model-backed is live and no
  key exists in cloud sessions. Cloud sessions have no `.env`.

## Strategies data import (migration, 2026-11)

Moving both boards off Strategies (contract ends 6 Dec 2026). Mapping, gates and run order:
`deliverables/greenjobs_migration_2026-11-06/build/import/IMPORT_MAPPING.md`.

- Inputs: Strategies admin → "Download Reports" CSVs (recruiters, candidates, profiles, jobs, applications), per
  site, in date batches; alias map `execution/gtm_client_workflows/greenjobs_redesign/strategies_mapping.json`.
- Command: `python3 execution/gtm_client_workflows/greenjobs_redesign/strategies_import.py --site ie|uk --report TYPE
  --csv PATH [--csv PATH ...] [--as-of YYYY-MM-DD] [--retention-months 24]`. Dry run by default (JSON summary, no PII).
  `--emit-sql PATH` writes idempotent upserts (shapes of `build/d1/upserts.sql`) plus an `import_batches` row per
  file; the operator applies them with `npx wrangler@4 d1 execute greenjobs --file=PATH`. No network in the script.
- Outputs: stdout summary; `--report-out` (no PII; outside the repo or `<repo>/.tmp/`); `--emit-sql` (outside the repo only).
- Exit: 0 ok / no-op, 2 usage or a required header with no alias match, 3 gate (yield < 0.05, rejects > 0.20).
- CSVs hold candidate PII: never in git, never in `.tmp/`; the script refuses repo paths except
  `tests/**/fixtures/` (fake data). Real headers are unknown until the first export: add aliases to the JSON,
  never edit code. Profiles need `--candidates-csv` (or an email column); applications SQL needs `--jobs-csv` or
  `--known-job-ids`. Tests: `python3 -m pytest tests/greenjobs_redesign/test_strategies_import.py -q`.

## Platform Worker (migration, 2026-11)

Staff posting console + public apply endpoint for go-live Thu 3 Dec 2026 (floor scope). Code:
`execution/gtm_client_workflows/greenjobs_redesign/platform_worker/` (README has routes, config, deploy).
Schema `deliverables/greenjobs_migration_2026-11-06/build/d1/schema.sql`; build pack index `build/README.md`.

- Dry by default: mail sends only with `DRY_RUN="0"` AND `LIVE_CONFIRM="send-applications"`; `MAIL_DAILY_CAP`
  is the budget guard and `audit_log` `mail.send` rows are the ledger. Secrets only via `wrangler secret put`.
- Staff auth: Cloudflare Access plus in-Worker JWT verification and the `STAFF_EMAILS` allow-list.
- Tests (offline): `bash deliverables/greenjobs_migration_2026-11-06/build/run_tests.sh` (schema x2, pytest import,
  `node --no-warnings --test 'tests/greenjobs_redesign/platform/*.test.mjs'`, no-CSV check). Node 22 rejects a bare
  directory after `--test`; use the quoted glob.
- Keith's twelve answers map to config in `build/DECISION_TABLE.md`; audits run against the frozen
  `build/REDTEAM_CHECKLIST.md`, at most 2 rounds.

## Gaia feed sync (migration, 2026-11-20)

Ends Gaia Talent's double posting: it posts on gaiatalent.com (WordPress, public `/wp-json/wp/v2/jobs`, 83 jobs on
20 Nov) and retypes most of them on greenjobs.ie. Destination-agnostic: it writes files a destination pulls (Cavuno's
recurring XML import, or our D1 via the Worker). Nothing is posted anywhere.

- Command: `python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_sync.py [--offline SNAPSHOT]
  [--board-jobs ie.json --board-jobs uk.json] [--out .tmp/gaia_feed] [--no-jev] [--save-fixture PATH]`.
  Board jobs = `scrape_greenjobs.py` output (full advert text matters for dedupe) or a GreenJobs RSS `.xml` with
  `--board-site` (RSS has no employer, so every match lands in review).
- Fetch: paginates `per_page=100` to `X-WP-TotalPages`, fails (exit 3) if rows ≠ `X-WP-Total`; four taxonomies
  (`job_location`, `job_category`, `job_type`, `job_sector`) read from their own endpoints. Honest UA, 20 s timeout,
  3 tries with backoff on 429/5xx.
- Record: `source_id` = `gaia:<wp id>` (stable), sanitised html (allow-list; no scripts, attributes, `javascript:`),
  dates in UTC, apply = mailto in the advert, else the job page URL (the page carries a Formidable application form;
  Gaia shows no public recruiter email). Gaia has no salary or closing date on any job (all 83 blank on 20 Nov).
- Mapping order (never guessed): sector = title keywords from `build_site.TAXONOMY` when the title names exactly one
  sector and does not contradict the Gaia terms, else the term dictionary `gaia_feed_mapping.json` (edit the JSON, not
  code); region = location term → county (aliases + Gaia towns), unless the advert's own `Location:` line excludes it;
  job type = term, unless the text says fixed-term / contract / N months. Conflicts and unmatched values go to Jev
  (`jev.choice` with a `none` option; Gaia's region options are Irish counties only); below `--jev-cut 0.6` →
  `review_queue.json` for Rashieda.
- Dedupe: auto-duplicate only on a copied advert by Gaia Talent (5-word-shingle containment ≥ 0.5); a same-title
  rewrite is ambiguous (Gaia runs same-title roles for several clients) and goes to Jev noul (≥ 0.8 dup, ≤ 0.2 not,
  between → review). One advert is one vacancy: a board advert copied from one feed job is not a duplicate of another.
  Both directions are reported: feed jobs already on a board (`on_board`) and Gaia board adverts missing from the feed
  (`dedupe.json` `board_only`).
- Outputs in `--out`: `feed.json`, `feed.xml` (id, title, description, location, region, category, type, salary, url,
  apply, date, updated, expiry, boards, status), `sync_report.json` (fetched, mapped deterministically / by Jev, queued,
  duplicates, new / updated / removed vs the previous run), `review_queue.json`, `dedupe.json`, `jev_cache.json`.
  Files are rewritten only when their bytes change and carry no wall-clock time; a no-change re-run is byte-identical
  (the report converges after the run that records the change). Gates (exit 3): 0 jobs fetched, a count mismatch, or
  more than `--max-removed-share 0.5` of the previous feed removed.
- Evals: `python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_eval.py [--no-jev]` scores E1/E2 on the
  hand-labelled fixtures in `tests/greenjobs_redesign/fixtures/gaia_eval/` (labelling rules inside `e1_labels.json`,
  `e2_pairs.json`) and writes `deliverables/greenjobs_migration_2026-11-06/build/feed/eval_report.md`. Jev answers are
  cached in `jev_cache_eval.json`, so a re-run is offline. No key and no cache → the Jev tier reads NOT RUN.
- Tests: `python3 -m pytest tests/greenjobs_redesign/test_gaia_feed_sync.py -q` (in `build/run_tests.sh`).
- Edge cases learned 20 Nov: Gaia's location term can contradict the advert (term Meath, advert Mullingar,
  Co. Westmeath; term Ennis, advert Dublin or Dundalk); job-type term "Permanent" on fixed-term roles; job_type
  taxonomy holds stray terms ("Land Acquisition"); board copies are often rewritten, so title + location alone
  over-merges (two live "Senior Town Planner" roles for different clients); RSS descriptions are truncated.

## Ops: redirects, DNS watcher, probe + service levels, metrics, backups, acceptance, reports (migration, 2026-11-20)

Scripts in `execution/gtm_client_workflows/greenjobs_redesign/ops/`, tests in `tests/greenjobs_redesign/ops/` (in
`build/run_tests.sh`, tier 4). Everything is offline or dry-run by default and tested without network or `.env`.
Scratch state (state files, outbox, ledgers, probe log, status page) lives in `.tmp/greenjobs_ops/` (`--state-dir`).
Sold scope (engagement record 2026-11-20 §2): the two boards. **The 8 network domains are optional** ("quoted
separately", P11): their forwards are prepared config only, every check on them is labelled `optional`, and they
never enter the go/no-go gate, the overall status grade, SLA figures or incidents.

- **Redirects** `redirects.py build [--live-ids d1_export.json] [--routes routes.json]` → `ops/generated/`
  `bulk_redirects.json` (Cloudflare Bulk Redirects list; recorded spelling + lowercase of every old path; sector
  domains 301 to `/sectors/<slug>/` on www.greenjobs.co.uk with subpath matching), `worker_redirects.json` (table for
  `ops/worker/`, routes `*/jobboard/*` and `*/browse-jobs/*`: ASP query strings, case/slash variants, retired job ids)
  and `redirect_coverage.json`. Facets map with `build_site.py`'s own vocabulary (TAXONOMY keywords via
  `assign_sectors`, region aliases via `resolve_regions`, `contract_of`, client names); no keyword → `/jobs/`.
  Every target is checked against `common.Routes` (static pages from `PAGES_FOR_SITEMAP` + `LANDINGS` +
  `/sectors/<slug>/`, `/jobs/<id>/` for live ids, `/jobs/?sector=&region=&type=&employer=` with known values); an
  unserved target aborts (exit 2). When the site engineer publishes the real route list, pass it as `--routes`.
  Before loading: re-run with `--live-ids` from a D1 export (default ids are the Sept snapshot, marked ASSUMED).
  20 Nov: 1,206 old URLs, 100% to a served page, 58.8% to a specific page or filter, 497 to board/home/employers.
  `crawl --live` measures the graded M2 after the switch (read-only GETs). Apex records on wastejobsuk.com and
  waterjobsuk.com do not exist today: add proxied records for apex and www when (if) those zones move.
- **DNS watcher** `dns_watcher.py [--send]`, every 10 min: DoH NS/MX/TXT for the 10 domains vs
  `zone_inventory_2026-11-20.json`. Target = NS on `*.ns.cloudflare.com` and MX + SPF identical. First arrival drafts
  one "done, checked" email to Diana (`dns-done:<domain>`, never twice: state file + outbox key). MX/SPF drift → an
  operator alert per distinct drift and exit 2; 6 failed lookups in a row → alert. A failed lookup is never "moved".
  An approved mail change goes in `--baseline`, not by editing the inventory.
- **Notifier** `notify.py`: outbox first. Live only with `--send` + `RESEND_API_KEY` + `OPS_MAIL_FROM` + the
  recipient var (`DIANA_EMAIL`, `OPS_ALERT_EMAIL`); client-facing templates also need their sha256 in
  `approved_templates.json`, added only after `/redteam` passes (empty today, so no client email can go live). Cap 12
  sends a run; each send writes a cost-ledger row. A dry-run draft does not consume the live send.
- **Probe + service levels** `uptime_probe.py --live [--send]`, every 5 min: 20 hostnames must end on 200 at the
  canonical host (sector domains on their sector page), MX/SPF vs inventory, and per board the sev-1 posting checks
  (`/admin/` not 5xx/404, `GET /api/jobs` 200, `OPTIONS /api/apply` 2xx). `incidents.py` opens one incident per
  failing core check and alerts at once: sev-1 (posting outage) respond within 4 h, sev-2 within 1 business day
  (Proposal :92/:137); `incidents.py ack <id>` records the response. SLA1 = 99.9% monthly uptime, SLA2 = responses
  on time; both on the status page and in the overall grade.
- **Metrics** `metrics.py [--inputs DIR] [--send]`, daily: SLA1-2, M1-M11 (SYNTHESIS §4 thresholds), B1 backup age
  (≤26 h PASS, ≤48 h WARN), B2 restore drill (passed within 92 days), NET1 (optional domains, INFO), CPO1-4 and
  CDO1-4 (INFO: no §4 threshold). A missing input is UNMEASURED with value null; `metric()` forces that, so nothing
  unmeasured can show PASS or a number. M3/M4/SLA1 are graded only after 24 h of probes; M4 needs the test mail too.
  Writes `status.json` + `status.html` (operator only, `noindex`, phone-width) and one red alert per metric per day.
  Inputs (all optional) in `--inputs`: `d1_export.json` `{"tables": {table: [rows with D1 column names]}}`;
  `reconciliation.json` `{exported:{type:n}, imported:{type:n}, sample_field_diffs, fields_exported, fields_migrated}`;
  `mail_test.json {sent, arrived}`; `visibility_probe.jsonl {job_id, created_at, visible_at}`;
  `staff_checkin.json {month, minutes}`; `link_check.json` / `jsonld_check.json {checked, valid}`;
  `alert_sends.jsonl {site, sent_at, consent_marketing, opened_at}` (unknown consent counts as a breach);
  `search_console.json {baseline:{indexed, clicks}, current:{...}, weeks_since_switch}`;
  `gdpr.json {erasure_requests:[{received_at, closed_at}], archive_access_entries, unsubscribes_exported, unsubscribes_carried}`.
- **Client measures (dashboard contract)**: `metrics.py` also writes `measures_ie.json` / `measures_uk.json`, shape
  fixed by `ops/measures.schema.json` (schema_version 1): `{schema_version, site, as_of, measures: {live_jobs,
  jobs_posted_30d, applications_7d, applications_30d, applications_per_job_30d, alerts_sent_7d, alerts_opened_7d,
  live_duplicates, expired_still_showing, staff_minutes_month}}`. `GET /api/stats?site=ie|uk` serves the object
  unchanged (another engineer adds the endpoint); the board dashboard's "Measures to come" tiles read it and render
  null as "coming". Adding a key bumps schema_version and the schema file in the same commit.
- **Backups (P8)** `d1_backup.py --live`, daily outside 09:00-17:00 UTC: counts every schema table, `wrangler d1
  export --remote`, uploads `d1/<date>.sql` to GreenJobs' R2 bucket (`GJ_BACKUP_BUCKET`, default
  `greenjobs-backups`); once per day (skip if done). `d1_restore_drill.py --live`, quarterly: restores the newest
  backup into a fresh `greenjobs-drill-<date>` database, checks restored counts ≥ recorded, deletes only that
  scratch database. `--sqlite DUMP` runs the same check offline. Needs `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`.
- **Acceptance (P17)** `acceptance_check.py [--date]`, daily after `metrics.py` for the 10 working days from Thu 3 Dec
  (to Wed 16 Dec): grades every item of `ops/acceptance_list.json` from the day's status, probes, measures and the
  operator's dated `acceptance_evidence.json` (`{"A3": {"2026-12-03": {"ok": true, "note": "..."}}}`); no
  evidence = UNMEASURED. History in `acceptance_history.json`, one entry per date. The list is derived from the
  9 Nov plan and the 30 Sep proposal: reconcile it with the contract's acceptance list before 3 Dec.
- **Reports (renderers only, never send; outward text goes through /redteam)**: `keith_weekly.py --next-step TEXT`
  (5 lines: red items, applications, alerts sent, staff hours, next step) and `monthly_report.py --month YYYY-MM
  --changes FILE` (uptime, traffic from `traffic_<month>.json`, applications, posting routes, needs attention, what
  changed). Both read the same measures and status; a missing figure prints "not measured yet".
- Edge cases: `renewablejobsuk.com` is NXDOMAIN, the real domain is `renewableenergyjobsuk.com`; Cloudflare Bulk
  Redirects cannot match query strings (the Worker takes them); a probe row with a lookup error is `ok: null` (never a
  pass); the redteam hook blocks shell commands that mention the mail API host, so run the committed scripts directly.

## Changelog

- 2026-11-20 (ops): redirects (bulk list + Worker table + M2 coverage), DNS watcher, uptime/posting probe with incidents and service levels, metrics runner + status page + client measures object, daily D1 backup + restore drill, 10-day acceptance checks, weekly and monthly report renderers; network domains marked optional.
## Classifier, D1 import, review queue, employer posting (migration, 2026-11-20)

Scope per the engagement record (`deliverables/engagement_record_2026-11-20/RECORD.md` §2): candidate import only of
the records Keith chooses; employer self-posting is phase 2; the Gaia feed was never promised. So all three are built,
tested, and OFF by default. Migration `build/d1/migrations/0003_classifier_feed_review_employers.sql` (additive, new
tables only) must run before any of them; statements live in `build/d1/upserts_0003.sql` = `platform_worker/src/sql_0003.js`.

- **Classifier** `execution/gtm_client_workflows/greenjobs_redesign/job_classifier.py`: imports `build_site.py`
  (`assign_sectors`, `loc_class`, `resolve_regions`, `workplace_of`, `contract_of`, `canon_type`), adds a sector
  confidence (0 on assign_sectors' fallback; 0.45 + 0.30 title hit + 0.25 x margin), takes an upstream hint (Gaia
  dictionary/Jev, Strategies labels mapped through the taxonomy). Below the cut 0.6, a hint conflict, an unmappable
  sector or (feed only) an unfrozen taxonomy -> `needs_review`, suggestions kept, never a guess. Vocabulary: the frozen
  `platform_worker/src/taxonomy.json` when present (tolerant shape: names or `{name, aliases}`; malformed = exit 2),
  else `build_site.TAXONOMY` marked not frozen. Optional Jev (`--jev`), cached; any failure stays queued.
- **Gaia feed -> D1** `gaia_d1_sync.py --feed feed.json | --once [--offline SNAPSHOT]` -> `--emit-sql` / `--emit-json` /
  `--post URL` (bearer `BUILD_TOKEN`). Ids `{site}:gaia:<wp id>` (`source='feed'`, `source_id='gaia:<wp id>'`); review
  jobs are `draft` with a `job_review` row (`hold=1`); E2 duplicates become `job_links`, not jobs; E2 `queue` pairs are
  reviewed as possible duplicates; jobs gone from the feed are closed (never deleted, never reopened); a staff review
  decision is never overwritten. Gates (exit 3): empty feed, every job rejected, API non-200. Live: `--post --live` needs
  `GAIA_FEED_ENABLED=1` here AND `FEED_IMPORT_ENABLED="1"` on the Worker; the Worker also refuses a batch that would
  close more than `IMPORT_MAX_CLOSE_SHARE` (0.5) of open feed jobs. Cron later: `--once` every 10 min.
- **Review queue** `/admin/review` (staff): Approve = suggested sectors, Change & approve = 1..3 active `taxonomy_terms`.
  A held job goes live; a closed job never does; a decided review is final.
- **Strategies import** (`strategies_import.py`): jobs are classified (`sectors_json`, `job_type`, plus `job_facets` and,
  when unsure, a `job_review` row with `hold=0` — the job stays live) and only LIVE jobs are emitted (`--include-closed`
  to override). Recruiters -> employers as before. Candidates / profiles / applications: `--emit-sql` refuses without
  `--candidate-config` (Keith's choice: `reports`, `active_since`, `registered_from/to`, `categories` (needs
  `--profiles-csv`), `fields` (default names, headline, sectors, preferred region; phone / home location / cover note
  only if listed)). Only consented rows: no explicit 0 in Consent or Marketing and at least one 1. Jobs By Email ->
  `alert_subscriptions` `pending` under the same rule (join on CandidatePK via `--candidates-csv`). Sniff mode unchanged.
- **Employer self-posting** (phase 2, `EMPLOYER_POSTING_ENABLED="0"` = 404): Access JWT + `employer_accounts`
  (email -> employer row of that site, `expires_at` = contract end). Own jobs only (another employer's: 403), only on
  boards with a mapping; staff see all. Staff post for CHM Recruit and Mattinson in `/admin/` on 3 Dec.
- Tests: `tests/greenjobs_redesign/test_d1_classifier_import.py` and `platform/feed_review_employer.test.mjs` (both in
  `build/run_tests.sh`; the node test also proves the Python SQL and the API write identical rows).
- Learned: JSON written to D1 must be compact (`strategies_import.cjson`, = `JSON.stringify`) or the Python and Worker
  writers disagree byte-wise and the change-guarded upserts bump versions on every run.

## Changelog

- 2026-11-20 (classifier / D1 import): `job_classifier.py`, `gaia_d1_sync.py`, migration 0003, `/api/admin/import`, `/admin/review`, `/api/employer/*`; Strategies import live-only jobs, classified; personal data and Gaia feed and employer posting off by default (engagement record §2).
## Release pipeline (2026-11-20)

Nothing reaches GreenJobs' production unchecked: CI -> staging (deploy + smoke) -> gated promote -> auto rollback.
Code `execution/gtm_client_workflows/greenjobs_redesign/deploy/` (`release.py`, `smoke.py`, `environments.json`,
`stage.sh` / `promote.sh` / `rollback.sh`); names, secrets, gates and known gaps in `deploy/ENVIRONMENTS.md`.

- Goal: every Worker / D1 / board change is tested, deployed to staging, smoke-tested there, and promoted only
  as that exact sha, with the previous production versions recorded and restorable in one command.
- Inputs: a commit on main; GitHub environments `staging` and `production` holding the secrets named in
  ENVIRONMENTS.md (never valued in the repo).
- Tools/Scripts: workflows `.github/workflows/greenjobs_ci.yml`, `greenjobs_cd_staging.yml`,
  `greenjobs_promote.yml`; `release.py` (stage / promote / rollback / record-smoke / verify-promotable /
  seed-sql / check-config / scan-secrets); `smoke.py`.
- Outputs: per run `deploy_record.json` + append-only `ledger.jsonl` + `summary.md` (sha, Worker version id,
  Pages deployment ids, D1 migration level, previous versions, D1 bookmark, backup object, smoke, rollback,
  times), uploaded as the `greenjobs-<env>-ledger-<sha>` artifact and written to the job summary.
- Steps:
  1. CI (`greenjobs-ci`): secret scan, workspace SAST, `node --check`, `check-config`, then `run_tests.sh`
     and `pytest tests/greenjobs_redesign/smoke`.
  2. CD (`greenjobs-cd-staging`, CI green on main): `release.py stage --execute`, `smoke.py --mode full`,
     `record-smoke`, artifact.
  3. Promote (`greenjobs-promote`, manual, required reviewer): input the sha; `verify-promotable` against the
     staging artifact; `release.py promote --execute` (previous versions, D1 export to the client's R2,
     migration gate, migrate, Worker, boards); `smoke.py --mode read_only` (canary off by default); on failure
     `release.py rollback --execute` and smoke again.
  4. Rollback by hand: `deploy/rollback.sh --record <deploy_record.json>` prints, `--execute` runs.
- Edge cases: `--execute` needs `GREENJOBS_RELEASE_TARGET=<env>`, no `REPLACE_` placeholders, HEAD = sha;
  destructive migrations (DROP / DELETE / RENAME / TRUNCATE; 0001 is one) need `--allow-destructive` and a
  verified backup first; the production D1 backup holds personal data, so it goes to `greenjobs-backups` R2
  only and is deleted from the runner, never a CI artifact; D1 is never auto-restored (Time Travel restore is
  printed for a human); a first production deploy has no previous version, so rollback fails loud;
  staging seeds public jobs only (`assert_seed_safe`); smoke write checks use per-run idempotency keys and
  always close the jobs they opened. The workspace redteam-gate hook blocks running `release.py` /
  `stage.sh` from a dirty tree in a Claude session: test through `pytest tests/greenjobs_redesign/smoke`.
- Exit criteria: CI green; staging record shows smoke `pass` (mode full) for the sha; production record shows
  smoke `pass` or `rolled_back` with the after-rollback smoke attached.

## Changelog

- 2026-11-20 (release pipeline): staging + production wrangler envs, CI / CD-to-staging / gated promote
  workflows, `deploy/release.py` (ledger, backup-before-migrate, rollback), `deploy/smoke.py`, 47 offline tests.

## Strategies export bot (migration, 2026-11-20)

Promise P16: every Strategies export is in GreenJobs-owned storage before the sites go off (Sun 6 Dec 2026). The bot
follows Strategies' own instructions (admin → Download Reports → report type → date fields → Download → CSV, per type,
per site, a few months at a time). Code: `execution/gtm_client_workflows/greenjobs_redesign/strategies_export_bot.py`;
page flow (URLs, field names, option labels): `strategies_export_config.json` next to it.

- Command: `python3 execution/gtm_client_workflows/greenjobs_redesign/strategies_export_bot.py --out DIR [--r2]
  [--live] [--sites ie,uk] [--reports recruiters,candidates,profiles,jobs,applications,alerts] [--months 3]
  [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--pace 3] [--admin-totals FILE] [--code-file PATH]`. Without `--live`
  it is an offline plan (window count, env names set or missing, manifest state); nothing is contacted. No paid API.
- Credentials: env `STRATEGIES_USER_IE` / `STRATEGIES_PASS_IE`, `STRATEGIES_USER_UK` / `STRATEGIES_PASS_UK`, held in
  memory only and redacted from every line printed. Emailed login code: env `STRATEGIES_CODE_IE` / `_UK`, else
  `--code-file PATH` (the operator writes the code into it; polled up to `--code-wait 600` s, read once, deleted),
  else a hidden stdin prompt on a terminal, else exit 2 naming the env var.
- Destination: `--out DIR` refuses any path inside this repo, inside any git working tree, or under a `.tmp` dir; and/or
  `--r2` (env `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` or `CLOUDFLARE_ACCOUNT_ID`;
  keys under `--r2-prefix strategies_export/`, SigV4 from `prodcraft_medspa/preview/r2.py`). R2-only runs stage in a
  system temp dir that is deleted. Layout: `<site>/<report>/<start>_<end>.csv` (`all.csv` for Jobs By Email, which has
  no date filter), `manifest.json`, `reconciliation.{json,md}`, `discover_<site>.json`.
- Per window: submit the report form with the parsed hidden fields, stream to `.part`, refuse HTML (re-login once,
  then exit 3), retry transport errors and short bodies 3x with backoff, check the header row equals
  `build/import/REAL_HEADERS_2026-11-19.json` exactly (names and order; exit 3 naming only expected columns), count
  rows (multi-line cells handled), then record `site, report, window_start, window_end, rows, sha256, bytes,
  downloaded_at, file`. The manifest is rewritten atomically after every window.
- Idempotent: a window whose stored file (local hash, or R2 `x-amz-meta-sha256`) matches the manifest is skipped; a
  tampered or missing file is fetched again; a leftover `.part` is discarded. The last window ends today, so a run on a
  later day re-fetches it and marks the earlier one `superseded_by` (never double counted).
- "Members profile data": refused from 08:45 to 17:00 UTC (`--profile-margin-min 15`); alone → exit 2; in a mixed run
  the other reports finish and the run ends exit 4 "deferred, run again after 17:00 UTC".
- M1 reconciliation: per site and report, windows done/planned, rows, the admin's own total (scraped by the
  config's `total_regex` where the Download Reports page shows one, or typed by the operator into `--admin-totals
  {"ie": {"recruiters": 418}}`, which wins), delta and MATCH / MISMATCH / NO_ADMIN_TOTAL / INCOMPLETE. Any INCOMPLETE
  or MISMATCH → exit 4. `--reconcile` rebuilds it offline from the manifest. A MISMATCH with a negative delta usually
  means records dated before `--since` (config `earliest`, 2005-01-01) or an export row cap: halve `--months`.
- Exit: 0 ok / no-op, 2 usage or refusal, 3 data contract (header mismatch, HTML instead of CSV), 4 incomplete, 5 transport.
- First live use (nobody has seen the admin): `--live --discover --out DIR --sites ie` saves only forms, field
  names, option labels and nav link paths (no values, no hidden-token values, no page text; selects with more than 50
  options keep only a count). Fix `strategies_export_config.json` from it, set `"verified": true` (live downloads
  refuse until then), set each report's `total_regex` if the page shows totals, then run one site, one report, one
  window (`--reports jobs --since 2026-09-01`) before the full walk. `needs_browser_hint: true` means the form is
  driven by JavaScript and a Playwright driver is needed (not built).
- Tests: `python3 -m pytest -q tests/greenjobs_redesign/test_strategies_export_bot.py` (in `build/run_tests.sh`): a
  local mock admin (login, code, Download Reports form, fixture CSVs from the real headers) and a mock R2 that
  re-checks SigV4. Covers header mismatch, crash resume, skip done windows, tamper, supersede, re-login, short body,
  profile guard, in-repo `--out`, unverified config, discover, R2-only, M1, and no secret or cell value in any output.

## Changelog

- 2026-11-20 (export bot, P16): `strategies_export_bot.py` + config + 22 mock-site tests; selectors unverified until a `--discover` run on the real admin.
- 2026-11-07 (migration platform): `platform_worker/` skeleton (console post/edit/close, `/api/apply`, Access JWT, rate limits, dry-run default), D1 schema + idempotent upserts, BDD features + 121 offline node tests, frozen red-team checklist, SAST report, decision table for the twelve questions.
- 2026-09-28 (client wall): `scrape_greenjobs.py` gains `parse_client_logos()` / `download_client_logos()`
  and a `--clients-only` flag: fetches /for-employers.asp on both boards (112 logos, all served from
  greenjobs.co.uk/images/logos/advertise/), saves them to `src/assets/logos/clients/` (dedupe by file,
  atomic write, ≤ 200 KB — three 120×60 PNGs carry ~400 KB of ICC/XMP and are re-encoded via Pillow),
  records `client:<file>` in `logos.json` with source + fetched date, writes `data/clients_{ie,uk}.json`.
  `build_site.client_wall()` renders the grid (7/6/4/3 per row, white tiles, lazy after 16, hidden until
  loaded, "Hiring this week" badge by `norm_org` match) on the home employer section and the employers
  page of both editions; `employers_strip()` remains the fallback when no clients json exists.
  Validator: wall required when clients data exists, ≥ 24 tiles, img+alt+file per tile, badge only with a
  live role. Refresh: `python3 execution/gtm_client_workflows/greenjobs_redesign/scrape_greenjobs.py
  --clients-only --assets deliverables/greenjobs_redesign_2026-09-22/src/assets/logos`. Layout baselines
  re-recorded for home + employers only.

- 2026-09-22: built, audited (anneal PASS, pipeline PASS 10/10, code review fixed, 16 design items,
  11-lens panel), published on both hosts.
- 2026-09-22 (act two): pinned scroll film hero (canvas; wind → county map → salary bands → sector
  ring → search; map points sampled from the SVG at build time), "Your fit in ten seconds" panel
  (home + jobs, upgraded local matcher, salary position, mini map, shareable hash), "Where this role
  sits" salary strip on job pages, live ad builder on Employers, count-ups/spotlights/magnetic
  buttons/view-transition morphs, evidence page request comparison. Budgets now CSS ≤ 72 KB, JS ≤ 110 KB.
  `capture_states.mjs` scrolls the film for screenshots; `tests/greenjobs_redesign/verify_browser.mjs`
  checks state 4 focus and a fit query in headless Chromium. Still zero API calls, zero third-party requests.
- 2026-09-24 (third pass, client feedback): warm-earth palette (paper `#f6f0e6` / `#efe6d6`, ink
  `#2a2521`, honey `#d99a1c` actions with ink text, terracotta once per section, sage/sky/clay data
  only; warm dark theme), Fraunces headlines + Nunito text (Archivo / Public Sans removed), a
  procedurally drawn living-landscape hero on one canvas (`js/landscape.js`: hills, river, solar
  field, five turbines, hedgerow, clouds, birds, scroll-warmed sun, parallax; ≤ 4 ms/frame, paused
  off-screen, static under reduced motion, CSS gradient without canvas), the film moved onto the
  paper-2 band with 2.4–3 px ink/clay/sage/sky/honey particles, ink label pills and a radial vignette,
  cookie banner + settings dialog and a weekly-email subscribe dialog (`js/popups.js`, localStorage,
  `?popup=` hook for captures), and a no-code hero footage drop-in (`src/assets/hero/<ed>.mp4`,
  `-m.mp4`, `-poster.webp|jpg`; validator checks referenced files exist). Budgets raised to CSS ≤ 80 KB,
  JS ≤ 125 KB (measured 70 / 99). Learned: the validator's checkbox rule needs `<label for>` (a
  wrapping label only counts when `<label>` is immediately followed by `<input>`).
- 2026-09-28 (edition rule and sterling fix, per Keith's document): Keith wrote "UK-only roles also appear
  prominently on the Irish board with salaries converted into euros. I would: retain salaries in their
  original advertised currency; clearly label UK, Ireland, remote and cross-border positions; allow users
  to exclude UK opportunities." Final rule: `EDITION_INCLUDES["ie"]` keeps every class (UK-only roles carry
  a "UK" badge and the "Hide UK/abroad-only roles" toggle, checklist B4); `EDITION_INCLUDES["uk"]` excludes
  Ireland-only and international roles (B5). An interim symmetric rule (IE excluding UK-only roles) was
  built and reverted the same day; the document overrides it. The real defect was the currency: the IE
  scrape relabels Mattinson's sterling figures as euros ("Associate Civil Engineer", London, €70,000 to
  €75,000). `sterling_twins()` indexes `src/data/uk.json`; `sterling_correction()` gives an IE role classed
  `uk` and priced in EUR the greenjobs.co.uk twin's GBP figures when the twin matches by id or slug, or by
  title + employer with the same numbers (a looser title match may be a different advert), and stamps
  `currency_source: "greenjobs.co.uk listing"`; the existing label then reads "£70k–75k (paid in sterling,
  about €82k–88k)" and the job page adds a "Salary source" line. Roles without a twin keep the scraped
  euros. The build log counts "sterling salaries restored from greenjobs.co.uk" (21 of 23 on the 22 Sept
  snapshot). The for-keith evidence table states per edition: IE "0 roles excluded; 23 UK-only roles shown
  with a UK label and the hide toggle", UK "20 Ireland-only roles kept off greenjobs.co.uk, 1
  international". `validate_site.py` fails a page carrying a role card outside its edition's class set
  (only the UK board excludes anything).
- 2026-09-28 (Keith's 28 September notes + panel pass): hero footage now defaults to Kling 3.0 Pro (1080p
  source, cut to 1280x720 loops); `FX_GBP_EUR = 1.17` fixed in `build_site.py` and mirrored in `lib.js`, used
  only for salary-range filters, medians, the "Where you sit on pay" strip and the bracketed "(paid in euros,
  about £…)" equivalent, never for the displayed figure; UK edition inclusion rule (a role appears on the UK
  board only if located in the UK incl. NI, fully remote, or explicitly IE+UK; the log line counts
  "excluded by the edition rule"; the IE board's handling of UK-only roles is in the entry above); roles whose closing date is before the build date are dropped at build
  time and the browser shows a "Closed" chip / "This role has closed" for anything that closes after the
  build (`data.today` in the dataset); `--today YYYY-MM-DD` pins the build date (default: the dataset's
  fetched date) so "ago" labels, closed-role drops and the footer year are deterministic; `/dashboard/`
  per edition (live tiles from stored fields + "Event spec for launch" with a consent-gated `track()`
  stub and `data-ev` attributes on apply, search, sign-up, request-rates, post-job and save controls);
  SEO landing pages (4 per edition, only when a role matches); `/guides/` with a data-generated salary
  guide; new facets (workplace, level, contract — the scraped job type and the text-derived tags are one merged
  Contract facet, `contract_facet()` — salary range, closing date, agency vs direct,
  "Hide UK/abroad-only roles"); the pinned film hero and `film.js` removed. Panel pass run 2026-09-28,
  fixes applied (cookie copy lists every stored key; quick-job-match text stays out of the URL until
  "Copy shareable link"; B Corp shown as mark + generic definition only; testimonial slots off the
  public page; launch notes shown before every demo form; employers page single CTA and "Ask us"
  membership cells; tags wrap at 390 px). Tests: `test_build.py` block `# --- panel fixes B ---`,
  `node --test src/js/dashboard.test.js`.
- 2026-09-28 (round 1, trace + QA): functional trace of every page at 1440/390 light/dark (`.tmp/trace3/acceptance.md`),
  numbers on public pages verified against `data/*.json` (88/77 roles, 14 sectors, 10 network sites, 29/47 disclosed
  salaries), 404 in the shell, hreflang pairs only for paths built in both editions (`paired_paths()`), Northern
  Ireland and East Midlands listed at 0 on the UK map so they stay a location option.
- 2026-09-28 (round 2, panel v1): secondary sector tags need `SECONDARY_MIN` and a third of the primary's score
  (R010/R087), Built environment as a secondary needs a title hit or three body keywords, unverified euro roles
  carry `currency_source` (R011), landing intros ≤ 80 words, employer strip lists live employers only (R041),
  contract facet merged, quick-job-match text kept out of the URL, cookie copy lists every stored key.
- 2026-09-28 (round 3, visual + layout suite): warm-earth visual fixes (visual 3–32), footer date rendered
  server-side, `tests/greenjobs_redesign/layout.test.mjs` added — Playwright layout regression (R1–R12: overflow,
  chip geometry, table bands, overlapping text, clipped controls, button rows, hero trust lines, rail scroll,
  console/network, contrast, screenshot baseline in `layout_baseline/`), `dashboard_dom.test.mjs` for the
  dashboard's browser half, `run_all.py` as the one test command, `test_scrape.py` against a recorded corpus,
  `test_gaps.py` branch tests (COVERAGE.md).
- 2026-09-28 (round 4, panel v2 + trace 3, data/build): sterling twin match requires figure equality on every
  path with nearest posted date as tie-break (IE 11495292 £55–60k from 11495291, not the £62–67k namesake);
  figure-fidelity test asserts all 21 restored pairs equal the IE source pairs; secondaries kept when the title,
  the site's own energy label or the energy family (wind/solar/renewable/networks) names them, "coastal" added
  to Water & flood, "enforcement officer" to Policy, golden `expect_secondaries` entries so drops are caught;
  `SITE_WORDS` no longer fire on bare "onsite"/"reserves"; the scraped type wins the permanent/contract axis
  (Bridge Engineer 11493521 → Contract only); `CROSS_RE` accepts ", - –" separators and reads only the title +
  first 300 summary chars; `date_long(None)` → ""; `lib.js dedupeJobs` trims; unverified-currency roles excluded
  from every median/band/guide/dashboard figure with the fx note saying so; `.greenjobs-build-ok` marker +
  `validate_site.py` CLI + deploy gate; scraper `--site both` exits 3 when either site is rejected, `logos.json`
  atomic; `run_all.py` SKIP semantics, total check count into COVERAGE.md; dashboard copy in the visitor voice
  (`DASHBOARD_COPY` / `DASHBOARD_REWRITES` in `build_site.py`); IE hero now reads 15 live sectors (Solar became
  live through the restored secondary). Tests: `test_build.py` block `# --- round 4 ---`.
- 2026-11-07 (Strategies import): `strategies_import.py` + `strategies_mapping.json` validate, map, dedupe and
  retention-filter Strategies CSV exports offline and emit idempotent D1 SQL; mapping doc
  `deliverables/greenjobs_migration_2026-11-06/build/import/IMPORT_MAPPING.md`; tests
  `tests/greenjobs_redesign/test_strategies_import.py` (synthetic fixtures). Header aliases are guesses until the
  first real export.
- 2026-11-20 (Gaia feed sync): `gaia_feed_sync.py` (wp-json → canonical feed.json + feed.xml, dictionary/title/Jev mapping with review queue, copied-advert dedupe + Jev noul, idempotent outputs, gates), `gaia_feed_mapping.json`, `gaia_feed_eval.py` + hand-labelled E1 (83 jobs) / E2 (1,183 pairs) fixtures, 25 offline tests in `build/run_tests.sh`.
