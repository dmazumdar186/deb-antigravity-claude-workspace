# GreenJobs platform Worker

Cloudflare Worker for the go-live floor scope (Thu 3 Dec 2026): (a) boards on Keith's domains
with current jobs, (b) the staff posting console (post, edit, close), (c) applications routed to
an inbox. It sits beside the static Pages front end built by `../build_site.py` and uses
D1 (`DB`) + R2 (`CVS`). The D1 contract is
`deliverables/greenjobs_migration_2026-11-06/build/d1/schema.sql` + `upserts.sql`; the Worker
uses those exact statement shapes with bound parameters only.

**Dry by default.** No application email leaves unless `DRY_RUN="0"` **and**
`LIVE_CONFIRM="send-applications"` (and `MAIL_PROVIDER="resend"` with the `RESEND_API_KEY`
secret set). Otherwise the application is stored with `delivery_status='dry_run'` and the mail
transport is never called. Each live send writes one `audit_log` row `mail.send` (the cost
ledger); `MAIL_DAILY_CAP` is the budget guard.

## Layout

| File | Role |
|---|---|
| `src/index.js` | Router, `export default { fetch, scheduled }`, `createHandler(deps)` for tests |
| `src/auth.js` | Cloudflare Access JWT verification (RS256 / WebCrypto, aud, iss, exp, nbf) + `STAFF_EMAILS` |
| `src/validate.js` | Pure validation: lengths, control chars, email, header injection, `toCsvCell()`, prompt-injection flags, traversal-safe ids, https URLs, CV magic bytes |
| `src/ratelimit.js` | `APPLY_LIMITER` binding, else KV `RATE`, else in-isolate Map |
| `src/mail.js` | Mail adapter (dry-run gate, Resend transport, ledger row) |
| `src/site.js` | `HOST_SITE_MAP` host -> site, inbox per site, CORS |
| `src/routes/public.js` | `GET /api/jobs`, `GET /api/jobs/:id`, `GET /api/export/jobs?site=` |
| `src/routes/admin.js` | `GET/POST /api/admin/jobs`, `GET/PUT /api/admin/jobs/:id`, `POST /api/admin/jobs/:id/close` |
| `src/routes/apply.js` | `POST /api/apply` (multipart) + delivery used by the cron retry |
| `src/routes/console.js` | `GET /admin/` console HTML + `/admin/console.js`, `/admin/console.css` (strict CSP, no inline script) |
| `package.json` | `{"type":"module"}` only, so Node loads `src/*.js` as ES modules in tests. Nothing to install. |

## Routes

| Route | Auth | Notes |
|---|---|---|
| `GET /api/jobs` | public, site from Host | live and `closing_at >= today`; `{today, jobs:[{id,title,employer,location,type,sal_text,sectors,posted,closing,summary}]}` |
| `GET /api/jobs/:id` | public | 404 unless live on this site; `description_html` is escaped |
| `GET /api/export/jobs?site=ie\|uk` | `Authorization: Bearer $BUILD_TOKEN` (constant-time) | for the static rebuild |
| `POST /api/apply` | public, `ALLOWED_ORIGINS` CORS | multipart: `job_id, name, email, phone?, cover_note?, cv?, consent=yes, website=""` (honeypot), `ts` (render ms, >= 3 s, <= 24 h old) |
| `GET /admin/` | Access + JWT + allow-list | console |
| `GET /api/admin/jobs[?status=&limit=&offset=]` | staff | paginated (limit <= 200, `next_offset`) |
| `POST /api/admin/jobs` | staff, same-origin `Origin`, `application/json`, `Idempotency-Key: <uuid>` | id `{site}:gj:{uuid}` |
| `PUT /api/admin/jobs/:id` | as above, body carries `version` | stale version -> 409 |
| `POST /api/admin/jobs/:id/close` | as above | idempotent (`already_closed: true`) |
| `POST /api/alerts`, `/api/newsletter` | public | 404 unless `ALERTS_ENABLED` / `NEWSLETTER_ENABLED` = "1" (then a 501 stub) |

Unknown Host -> 404 `unknown_host`. Errors are always `{"error": code}`; no stack traces, no PII
in responses or `console.*`. Audit rows carry field NAMES only (plus prompt-injection `flags`,
also names).

## Config (wrangler.toml `[vars]`, secrets via `wrangler secret put`)

`DRY_RUN`, `LIVE_CONFIRM`, `HOST_SITE_MAP`, `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD`, `STAFF_EMAILS`,
`APPLY_ROUTING` (`inbox|consultant|advertiser`), `APPLY_INBOX_IE`, `APPLY_INBOX_UK`,
`MAIL_PROVIDER` (`resend|none`), `MAIL_FROM`, `MAIL_DAILY_CAP`, `RATE_APPLY_PER_10MIN`,
`RATE_ADMIN_PER_MIN`, `MAX_CV_BYTES`, `ALERTS_ENABLED`, `NEWSLETTER_ENABLED`, `ALLOWED_ORIGINS`.
Secrets: `RESEND_API_KEY`, `BUILD_TOKEN`. Bindings: `DB` (D1), `CVS` (R2), optional `RATE` (KV),
optional `APPLY_LIMITER` (Rate Limiting).

Routing: `inbox` -> the site inbox. `consultant`/`advertiser` -> `jobs.apply_email` if set and
valid, else the site inbox plus an `application.route_fallback` audit row. A missing site inbox
is a loud 503 (`routing_not_configured`), never a silent drop. `apply_mode='url'` jobs answer
409 `apply_externally` with the external URL.

## Tests (offline, no installs)

```bash
node --no-warnings --test 'tests/greenjobs_redesign/platform/*.test.mjs'
```

(Node 22's `--test` does not take a bare directory; pass the glob, quoted so Node expands it.
`--no-warnings` hides the `node:sqlite` ExperimentalWarning.) The D1 fake runs the real
`schema.sql` on `node:sqlite`; R2 is a Map; the mail transport and the Access JWKS are injected
(`createHandler({ jwksFetcher, mailTransport, now })`). BDD features live in
`deliverables/greenjobs_migration_2026-11-06/build/features/` and run through
`tests/greenjobs_redesign/platform/bdd_runner.test.mjs`; an undefined step fails the run.

## Deploy (all dry by default)

```bash
cd execution/gtm_client_workflows/greenjobs_redesign/platform_worker
npx wrangler@4 d1 create greenjobs                       # paste database_id into wrangler.toml
npx wrangler@4 d1 execute greenjobs --remote \
  --file=../../../../deliverables/greenjobs_migration_2026-11-06/build/d1/schema.sql   # idempotent
npx wrangler@4 r2 bucket create greenjobs-cvs            # private bucket, no public access
npx wrangler@4 secret put BUILD_TOKEN                    # long random string; also set in the Pages build
npx wrangler@4 secret put RESEND_API_KEY                 # only when going live; never in wrangler.toml
npx wrangler@4 deploy                                    # DRY_RUN="1": applications stored, nothing sent
```

Cloudflare Access (Zero Trust -> Access -> Applications -> Self-hosted):
1. One application covering `greenjobs.ie/admin*`, `greenjobs.ie/api/admin/*`,
   `greenjobs.co.uk/admin*`, `greenjobs.co.uk/api/admin/*` (plus the staging hosts).
2. Policy: allow the staff emails (same list as `STAFF_EMAILS`).
3. Copy the application's **AUD tag** to `ACCESS_AUD` and the team domain
   (`<team>.cloudflareaccess.com`) to `ACCESS_TEAM_DOMAIN`. The Worker re-verifies the
   `Cf-Access-Jwt-Assertion` JWT against `https://<team>/cdn-cgi/access/certs`; with either var
   empty it fails closed (503).
4. Add the Worker routes (commented in `wrangler.toml`) for `/api/*` and `/admin*` on both zones.

Going live with email (operator decision, not part of a default deploy): verify the sending
domain in Resend, set `MAIL_FROM`, `MAIL_PROVIDER="resend"`, `APPLY_INBOX_IE/UK`, then
`DRY_RUN="0"` and `LIVE_CONFIRM="send-applications"`. The cron (`*/10 * * * *`) retries
`pending`/`failed` deliveries from the last 48 h with the application id as the provider
Idempotency-Key, so a retry cannot double-send.

## Known limits

- The `ts` render timestamp is unsigned: a speed bump for naive bots, not a proof.
- The Rate Limiting binding's period is 10 or 60 s, so it is a burst guard; the 10-minute window
  is enforced by KV `RATE` (eventually consistent) or the per-isolate Map (best effort).
- Console edits cover the canonical edit statement's fields (title, location, description,
  closing, apply mode/email/url, salary, status); employer is fixed after creation. A job with
  `source='strategies'` edited in the console is overwritten by the next import upsert.
- Applications do not create `candidates` rows (no extra PII copy); `candidate_id` stays NULL.
