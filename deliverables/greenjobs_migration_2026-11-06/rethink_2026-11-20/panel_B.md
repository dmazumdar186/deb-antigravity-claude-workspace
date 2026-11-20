# GreenJobs rethink: panel B (system design)

Written 2026-11-20. Internal. Three blind lenses, assume wrong until proven. Paths are relative to the workspace root:
`FACTS` = `deliverables/greenjobs_migration_2026-11-06/rethink_2026-11-20/FACTS.md`, `ARCH` = `.../build/ARCHITECTURE.md`,
`SCHEMA` = `.../build/d1/schema.sql`, `RUNBOOK` = `.../build/CUTOVER_RUNBOOK.md`, `FWD` = `.../build/dns/NETWORK_FORWARDS.md`,
`W` = `execution/gtm_client_workflows/greenjobs_redesign/platform_worker/`, `BS` = `.../greenjobs_redesign/build_site.py`.

## Headline defect (found by all three lenses)

**The job-to-board loop is not built.** ARCH:66-72 says a console write sets a "publish pending" flag, a 5-minute cron
calls `DEPLOY_HOOK_URL`, and the Pages build runs `build_site.py` against `GET /api/export/jobs`. In the code:
- `scheduled()` only retries application mail (W `src/index.js:106-130`). Nothing in `src/` or `wrangler.toml`
  mentions `DEPLOY_HOOK`, and no publish flag exists (not in `src/routes/admin.js` or SCHEMA).
- The cron runs every 10 minutes, not 5 (W `wrangler.toml:18`; ARCH:68 says 5; RUNBOOK:241 says "≤ 5 min").
- `build_site.py` reads `data/{ie,uk}.json` from disk (BS:12, 2748). Nothing in the repo calls `/api/export/jobs`;
  its only reference is the Worker itself.

So a job Rashieda posts on 3 Dec is stored in D1 and never shown on the board. Go/no-go item 4 (RUNBOOK:256) cannot
pass as built. "159 offline tests pass" (FACTS:41) tests the parts, not the loop.

## Lens 1: Boris Cherny, tooling craft

1. **Two systems glued by a missing seam.** A 2,890-line static generator (BS) built for a scraped snapshot, plus a
   Worker API, joined by a deploy hook that does not exist. With ~220 jobs and ~15 new jobs a month (FACTS:16-17),
   static generation buys nothing: the Worker can render list and job pages straight from D1 and cache them. That
   removes the deploy hook, `BUILD_TOKEN`, the Python build on Pages, publish lag and the "stale page shows a
   closed job" failure mode (ARCH:207).
2. **Config drift is already present.** ARCH:51-55 lists vars that do not match the code (`OPS_ALERT_EMAIL`,
   `MAIL_DAILY_CAP` are in W `wrangler.toml:33` and `src/mail.js:8` but not in ARCH). The cron interval also differs (above).
3. **The Worker is good.** JWT verification, CSRF plus Idempotency-Key on writes (W `src/index.js:50-55`), host-to-site
   map (W `src/site.js:5-16`), dry-run double key. Keep it.
4. **Over-built:** stubs for alerts and newsletter (W `src/index.js:85-92`) and a `feed` source reserved for Broadbean
   and others, when Diana says no live jobs come through a feed tool (FACTS:14).
5. **Missing:** an end-to-end test (post, then see the job on the board, apply, then mail).

## Lens 2: Greg Brockman, execution and reliability

1. **13 days, nothing deployed** (FACTS:41), with the core loop unbuilt. Close the loop by Tue 24 Nov or cut scope.
2. **Circular login dependency.** Registrar and host logins send codes to the info@ inboxes (FACTS:29). Those
   mailboxes are hosted on the domains being moved (FACTS:26). If a nameserver move breaks MX, the codes needed to
   roll it back stop arriving. Use Path B for greenjobs.ie (change web records only, RUNBOOK:165-172), or put a
   second recovery address on each login before T-3.
3. **Three DNS parties** (Hosting Ireland, LetsHost, 123-Reg with GoDaddy nameservers; FACTS:26-28) plus 8 network
   zones (FWD:32-33) is 10 nameserver changes in one week. The network domains carry live MX (FWD:33).
4. **Nobody is paged.** `OPS_ALERT_EMAIL` is empty by default (W `wrangler.toml:33`). The alert goes out through
   the same Resend account whose failure it reports, and counts against the same daily cap (W `src/mail.js:8, 93-99`).
   There is no uptime check. In practice the person paged is the solo founder, when Keith phones.
5. The runbook itself is strong: rollback window, split NS and web risk, go/no-go list (RUNBOOK:174-175, 249-280).

## Lens 3: Demis Hassabis, systems and the long horizon

1. **Tenancy is hard-coded.** `site CHECK (site IN ('ie','uk'))` appears on 6 tables (SCHEMA:17, 36, 70, 92, 114, 144).
   A 3rd tenant (a sector board sold as its own site) means rebuilding every table, because SQLite cannot alter
   a CHECK. Use a `boards` table with a foreign key instead, and model a sector domain as a board row with a
   sector filter.
2. **The 8 sector domains are a product, not a redirect.** Employers pay for "displayed on all relevant network
   websites" (FACTS:21). FWD:24 sends 6 of the 8 to a board filter or the nearest page, which quietly removes what
   was sold. With host-to-(board, filter) resolution these become views at near-zero cost. The Worker already
   resolves the board from the host (W `src/site.js:5`).
3. **No model for the 2-year path.** There are no employer accounts, no users or roles, and no products or orders,
   though alerts and the newsletter are sold to advertisers (FACTS:20). Employers are stored once per site
   (SCHEMA:15-31), so the same company on both boards is two unrelated rows.
4. **Bus factor of 1.** Custom JavaScript plus about 5,000 lines of Python (BS, scraper, importer), and only one
   person knows them. If the founder is unavailable, Keith has no fallback. Building logins, alerts and payments in
   custom code adds to this cost without limit. Buy those features instead.

## Options judged

| Option | Verdict |
|---|---|
| (a) Current custom Cloudflare stack | Floor is close; core loop missing; 2 build systems; bus factor 1. Amend, do not extend into phase 2. |
| (b) Hosted job-board SaaS | Lowest bus factor and gives logins, alerts and paid listings out of the box. Unverified on 13 days: CSV import, multi-domain pricing, 301 map. Best phase-2 home. |
| (c) WordPress + WP Job Manager | Gaia already runs WP (FACTS:22), so it is familiar and widely supported. Patching, plugin sprawl and multi-domain need a managed host. Viable phase-2 target; too much to stand up and migrate in 13 days. |
| (d) One multi-tenant board, domains as filtered views | Right shape whatever the platform: one codebase, one DB, host decides board plus filter. Adopt now inside (a). |
| (e) Simpler | Worker renders HTML from D1 directly; drop the static rebuild. This is the simplification that matters. |
| Apache Ant | A Java build tool from 2000. There is no Java here and the build is one command, so it has no role. |
| Microservices | Wrong at 2 staff and 220 jobs. One Worker is already the correct unit; splitting it adds network failure modes and deploys for no gain. |

## Who maintains it in a year

As built: only Debanjan. Diana and Rashieda can post through the console, and that is all they can do. Without the
amendments below, every phase-2 ask (logins, alerts, payments) becomes custom code that only one person can change.

## VERDICT: AMEND

Ship the custom floor on 3 Dec, collapsed to one multi-tenant Worker. Make phase 2 a buy-vs-build gate, not a build.

### Recommended target architecture
1. One Worker serves every host. It renders job list, job pages, sector views and sitemap from D1, with edge cache
   purged on write. Pages keeps only static assets and guides. Retire the deploy hook and `BUILD_TOKEN`.
2. A `boards` table (`greenjobs-ie`, `greenjobs-uk`, plus the 8 sector domains as `parent board + sector filter`).
   It replaces the `site` CHECK; the host map is data, not a var.
3. Employers are global, with a board link table. Jobs carry `board_id` and a list of boards they are shown on.
4. Keep the existing console, apply path, D1, R2, Access and the dry-run guard as they are.
5. Greenjobs.ie: Path B (web records only, mail untouched). Network domains: move NS only after their MX is copied
   (or after Diana confirms they are unused).
6. Ops: an external uptime check on both boards plus an ops alert through a second channel (not Resend). Name a
   person on Keith's side who receives it.
7. One end-to-end test (post → visible → apply → mail row) gates deploy.
8. Q1 2027 gate: before building any login, alert or payment, price a hosted SaaS or WP Job Manager against
   custom code. Default is to buy. D1 then becomes the export source for that migration.

### Claim → Objection → Resolution
- Claim: replace with SaaS or WP now, for the bus factor. Objection: 13 days, unverified imports and 301 maps, and 10
  domains, is the riskier migration. Resolution: **amend**: ship custom collapsed to one Worker on 3 Dec, gate phase 2 on buy.
