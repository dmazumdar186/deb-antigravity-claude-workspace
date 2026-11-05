# ASSET Voyages: Option B demo (custom platform)

A small but real platform covering the five functions ASSET asked every candidate to show. The visitor side and the staff console both work. All data is fictional and the GM&E codes are dummies (`DEMO-GME-…`).

- Live: https://asset-voyages-demo.debanjan186.workers.dev (Cloudflare Workers free plan, D1, cron 03:00 UTC)
- Staff console: `/console`. Demo accounts `direction`, `equipe` and `contributeur` all use the sandbox password `demo-asset`, which is also shown on the login page.

## Architecture in plain words

One Cloudflare Worker answers every request. It builds each page on the server, so the site works with JavaScript turned off; a 1 KB script only adds comforts such as filters that apply as soon as you pick one. The data lives in one D1 database (SQLite). The fonts, the stylesheet and the script are served as static files. Every night at 03:00 UTC a scheduled trigger puts the sandbox back to its starting state.

**Private sandbox per browser.** On its first visit each browser receives an HttpOnly cookie that names its own sandbox. Until that browser changes something, it reads the shared seed. Its first change copies the seed into its own sandbox (copy-on-write), and from then on it only reads and writes there. Every write is tagged with the sandbox: congresses and edits to them, enquiries, statuses, notes, notifications, GM&E requests, approvals and journal rows. Other visitors never see another browser's changes, so publishing, defacing or approving with the shared demo logins only affects the browser that did it. « Réinitialiser la démo » deletes the caller's sandbox only. The nightly cron deletes sandboxes older than 24 h and rebuilds the seed. Sandbox creation is capped at 150 per IP hash per hour and 1,500 a day overall, which keeps the demo inside the D1 free write quota.

```
 visitor / staff browser
          |  HTTPS (security headers on every response)
          v
 +-------------------------------+        +-------------------------------+
 | Worker  asset-voyages-demo    |  SQL   | D1  asset-voyages-demo        |
 |  /            catalogue       | -----> |  congresses, congress_events  |
 |  /congres/:slug  fiche+form   |        |  enquiries, enquiry_events    |
 |  /demande     POST -> 303     |        |   (append-only trigger)       |
 |  /console/*   staff, roles    |        |  notifications                |
 |  cron 03:00 UTC -> reset      |        |  gme_codes (AES-GCM, own tbl) |
 +-------------------------------+        |  gme_requests, gme_access_log |
          |  static                       |  users (PBKDF2), sessions,    |
          v                               |  rate_limits                  |
 public/assets  (fonts, app.css, app.js)  +-------------------------------+
 Worker secret GME_KEY (32 bytes): AES-GCM key for codes, HKDF-derived HMAC key for form tokens and IP hashes
```

Source: `src/index.js` (routing, headers, cron), `src/public.js` (catalogue, congress page, enquiry), `src/console.js` (sessions, roles, every console screen), `src/data.js` (schema, seed, reset), `src/views.js` (page shells, form fields), `src/lib.js` (escaping, WebCrypto, dates, CSV). No framework, no runtime dependency.

### Security, as built

- **Roles checked on the server for every route and every POST.** `direction` does everything, including GM&E codes and access decisions. `equipe` handles congresses and enquiries; GM&E codes stay masked until Direction grants access. `contributeur` drafts congresses and submits them for review but cannot publish, and has no access to enquiries or codes.
- **Passwords** are stored as PBKDF2-SHA256 hashes (WebCrypto, per-user salt). **Sessions** use a random token whose SHA-256 is stored server-side, in a cookie `__Host-av_session` marked HttpOnly, Secure, SameSite=Strict, 8 h. Logging out deletes the session on the server.
- **CSRF**: every console POST needs the session's token and a same-origin `Origin`. The anonymous forms (enquiry, login) carry a signed token (HMAC) that also enforces the minimum fill time and blocks replay.
- **Login throttling** (atomic): each attempt on an account increments a counter in one `INSERT … ON CONFLICT … RETURNING` before the password is checked, with 10 per account per connection; there is also a limit of 50 failures per connection, and both windows last 15 minutes. A successful login clears the account counter.
- **Enquiry form**: all validation happens on the server (dates, past dates, return on or after outbound, e-mail, passengers 1 to 50, lengths, consent). It also has a honeypot, a 3-second minimum fill time and a limit of 10 accepted enquiries per 10 minutes per browser and IP hash, and 60 per IP hash for a whole office (stored in D1). A refused submission always shows a French message saying the enquiry was not sent. It uses POST-redirect-GET. The confirmation link is signed, so references cannot be enumerated.
- **GM&E codes** sit in their own table, encrypted with AES-GCM (random IV, key from the `GME_KEY` Worker secret, never in code or in the repo). A code is only shown in response to a server-checked POST. Each display and each refused attempt is written to the « Journal d'accès », which only Direction can read. Access is granted for 24 h and can be revoked at once. Public pages only ever say « Tarif congrès négocié disponible : appliqué à votre devis » for an approved, in-date code. No route returns a code.
- **Headers**: CSP `default-src 'self'` with no third-party source, `frame-ancestors 'none'`, `X-Robots-Tag: noindex, nofollow`, `robots.txt` set to disallow everything, nosniff, `Referrer-Policy: same-origin`, HSTS. Every interpolated value is HTML-escaped by default. The CSV export is UTF-8 with a BOM and `;` separators; a cell starting with `= + - @` or a tab is prefixed with `'`.

## Run, deploy, reset

```bash
npm install                 # wrangler only
printf 'GME_KEY=%s\n' "$(python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())')" > .dev.vars
npm run dev                 # wrangler dev --local --port 8787 --test-scheduled; seeds itself on the first request
BASE_URL=http://localhost:8787 node node_modules/playwright/cli.js test     # node_modules/playwright -> the preinstalled global package

# deploy (free plan only: Workers, D1 and cron triggers are all on the free tier)
npx wrangler@4 deploy
python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())' | npx wrangler@4 secret put GME_KEY
BASE_URL=https://asset-voyages-demo.debanjan186.workers.dev node node_modules/playwright/cli.js test
```

There are three ways to reset, and all three converge on the same seed with the same ids, so a second reset creates no duplicates: the « Réinitialiser la démo » button on Direction's dashboard, the 03:00 UTC cron, and, locally, `curl "http://localhost:8787/cdn-cgi/handler/scheduled?cron=0+3+*+*+*"`. The seed holds 13 congresses (12 published with the briefed dates and cities, plus one draft, CG-0113), 6 enquiries across all statuses, 5 dummy codes with mixed statuses, and one pending access request from `equipe`.

## Tests (Playwright, `tests/`)

Every test name starts with the gate ID it proves from `../21_Acceptance_Gates_5_Stories.md`. An automatic fixture fails any test that hits a console error, a sub-resource answered with 4xx/5xx, a network failure or a third-party request (X1, X2). The fixture ignores `ERR_ABORTED`, which is Chromium cancelling a load because the test clicked on to the next page. A separate test, « X1 strict », loads every visitor and console page without clicking and counts every failed request, aborted ones included. E gates count the clicks.

| File | Gates | Local | Live |
|---|---|---|---|
| `s1_congress.spec.mjs` | S1-F1, S1-E1, S1-F2, S1-E2, S1-F3, S1-H1, S1-H2 | 5/5 pass | 5/5 pass |
| `s2_catalogue.spec.mjs` | S2-F1 to S2-F6, S2-E1, S2-E2, S2-H1 | 9/9 pass | 9/9 pass |
| `s3_enquiry.spec.mjs` | S3-F1, S3-F2, S3-F3, S3-F4, S3-E1, S3-H1, S3-H2, S3-H3 | 7/7 pass | 7/7 pass |
| `s4_team.spec.mjs` | S4-F1 to S4-F6, S4-E1, S4-H1 | 7/7 pass | 7/7 pass |
| `s5_gme.spec.mjs` | S5-F1 to S5-F5, S5-E1, S5-H1, S5-L1 (crawl), S5-L2 | 11/11 pass | 11/11 pass |
| `fix_round1.spec.mjs` | FIX-1 to FIX-26 (eye review, adversarial and blind-QA findings, see below) | 24/24 pass | pending redeploy |
| `x_cross.spec.mjs` | X1, X1 strict, X2, X3, X4, X5, security headers, cookie and logout replay, console at 390 px, hostile console input | 9/9 pass | 9/9 pass |
| `z_screens.spec.mjs` | screenshots for X6 | 2/2 pass | 2/2 pass |
| **Total** | | **74/74 pass** | 50/50 before the fix round; re-run pending |

Fix round 1, local: 74/74. Before the fix round, both full runs (local `wrangler dev`, then live deploy b48a4877) passed 49/49. « X1 strict » was added afterwards and run on its own, passing locally and live, which brings the totals to 50.

Click budgets measured: S1-E1 3 (budget 4), S1-E2 3 (3), S2-E1 2 (2), S3-E1 1, S4-E1 2 (3), S5-E1 2, 2 and 2 (2 each).

The leak test (S5-L1) crawls more than 20 public URLs logged out and more than 30 URLs as `equipe` without a grant. Its probes include `/api/*`, `/sitemap.xml`, `/feed`, `/wp-json`, `/.env` and `/src/data.js`. It checks every body and every header for any of the five seeded codes or the pattern `DEMO-GME-\d{4}`. S5-F1 and S5-L2 dump the D1 tables through `wrangler d1 execute` and confirm that no plaintext code is stored anywhere.

Screenshots (`deviceScaleFactor` 1) go to `screens/NN-name-1440.png` and `screens/NN-name-390.png`: 22 screens × 2 widths, covering the catalogue, the filtered and empty catalogue, the congress page and its errors, the confirmation, login, both dashboards, enquiries, the enquiry history, notifications, the masked GM&E codes, the access request, pending and granted access, the congress list and editor, a revealed code, the access log and the contributor form. The workspace `.gitignore` drops `*.png`, so they need a `!` override if they are to be committed.

## Hallmark (sloplint)

`node .claude/skills/hallmark/scripts/sloplint.mjs` runs on 7 rendered visitor pages (`--genre editorial`) and 10 console pages (`--scope app`). The X5 test does this on every run and writes the output to `.lint/<local|live>/sloplint.txt`.

- **0 FAIL, 0 REFLEX, 0 WARN** on both sets.
- **Stamp** `copy: verbatim`: the seeded titles and venues end with « — exemple », which acceptance gate X3 requires, so the gate 19 dash shows as a NOTE on those data strings only. Our own copy contains no em or en dash: date ranges read « 27 au 30 août 2027 ».
- **Dismissed F7**: at phone width each console table row becomes a card, which is the same row restacked rather than a new container.
- **Dismissed 3**, on the record in the stamp: the orange left rule on notices, the sandbox line and the to-do links is the concept console's own banner device, kept so the real console matches what the client already saw.
- **No small-caps waiver needed**: labels, table heads and tags are Inter in sentence case, untracked (gates 54/67 are clean), unlike the concept site's mono capitals.
- The render tier did not run: it needs `puppeteer-core`, which is not installed here. Responsiveness, tap targets and input sizes are covered by the Playwright gates instead.

## Working in the demo vs needs development for production

| Function | Working in the demo | Needs development for production |
|---|---|---|
| S1 congresses | Create and edit with every field; draft → à relire → publié → archivé; contributor cannot publish; status history | CSV import of the ~300 listings with duplicate detection (match on title + dates + city), bulk edit, image per congress |
| S2 catalogue | Search (accent-insensitive), discipline, country and month filters, date sort, past hidden, 9 per page, empty state, fiche page | Page and content editor for the rest of the site (home, offers, agency, legal pages), English version, SEO once indexing is allowed |
| S3 enquiry | Full form, server validation, honeypot, minimum fill time, rate limit, reference DV-2026-NNNN, no duplicates on reload | **Real e-mail sending** (team alert + visitor acknowledgement through a transactional mail provider, SPF/DKIM), consent text reviewed by ASSET's DPO, retention and erasure policy |
| S4 team follow-up | List, filters, search, statuses, owner, internal notes, append-only history, CSV export with formula escaping, notification log | Reminders and due dates, the e-mail itself (the log shows what would be sent), per-person dashboards |
| S5 GM&E | Encrypted codes in their own table, statuses Détecté → Vérifié → Approuvé pour la vente → Expiré, validity, evidence note, request with reason, 24 h approval, revoke, refuse, server-checked reveal, access log | Staff **2FA via Cloudflare Access** (or WebAuthn) in front of `/console`, key rotation procedure, real codes entered by ASSET only |
| Operations | Nightly sandbox reset, security headers, noindex | **Backups and a restore drill** (D1 Time Travel + scheduled export), **monitoring** and alerting (uptime, error rate, failed deliveries), a staging environment, named accounts instead of shared demo logins, higher PBKDF2 cost (100k) on a paid Workers plan |

## Known limits of the demo

- The three demo accounts and their password are public by design. Changes only ever reach the browser that made them.
- PBKDF2 uses 25,000 iterations so a login stays within the free plan's CPU budget; production would raise it.
- Each browser has its own private sandbox: a colleague on another computer will not see your test enquiry. To show the whole journey, play visitor and staff in the same browser.
- E-mail is simulated: the « Notifications » screen shows the exact message that would be sent to the team.

## Fix round 1 (eye review + adversarial pass)

| Test | Finding fixed |
|---|---|
| FIX-1, FIX-2, FIX-3 | Shared mutable sandbox replaced by a private sandbox per browser (copy-on-write); the reset and the nightly purge only touch the caller's or expired sandboxes |
| FIX-4 | Official website must be `https://` |
| FIX-5 | Codes can be shown or requested only when « Vérifié » or « Approuvé pour la vente »; « Détecté » and « Expiré » show a short explanation instead of a form |
| FIX-6 | Atomic login throttle keyed by IP hash and username |
| FIX-7 | CSRF is checked before any write: a forged reveal leaves no journal row |
| FIX-8 | Ink text in the dark enquiry panel; placeholders at 4.5:1 or better |
| FIX-9 | Dates as jj/mm/aaaa or « 28 au 30 janv. 2027 »; the notification e-mail uses jj/mm/aaaa and a full https link |
| FIX-10 | Skip link only on keyboard focus; focus moves to the message after a redirect or an error |
| FIX-11, FIX-12 | At 390 px the console menu wraps, and table rows become labelled cards |
| FIX-13 | Fictional named users (Hélène Martin, Karim Benali, Julie Roux) in history, approvals and the journal |
| FIX-14, FIX-15 | Prefilled congress shown as plain text; a non-breaking space before « — exemple » |
| FIX-16 to FIX-20 | Plural tile labels, the mobile date line, « Nous écrire » in the no-result state, « Masquer le code », padding on badges |
| FIX-21 (D1) | Discipline and Pays are chosen from managed lists; Direction adds values (accent- and case-insensitive duplicates refused); free text is refused on the server |
| FIX-22 (D2) | The sidebar groups « Codes GM&E »: Codes, Demandes d’accès, Journal |
| FIX-23, FIX-24 (D3, D4) | A banner at the top lists each error as « Champ : message », with a link to the field; focus moves to it, and it is visible on a phone. Failed submissions re-render with status 200 |
| FIX-25 (D5) | 10 enquiries per 10 minutes per browser and IP, 60 per IP. The 11th shows a visible French message and keeps what was typed. The honeypot field is renamed and hidden with `display:none`, so autofill cannot trip it: this was the likely cause of the silent "no reference" seen in QA |
| FIX-26 (D6) | The date line reads « 29 sept. au 2 oct. 2027 » at every width, including for screen readers |
