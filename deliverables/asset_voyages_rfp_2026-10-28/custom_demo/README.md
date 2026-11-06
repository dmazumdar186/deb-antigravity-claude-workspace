# ASSET Voyages: Option B demo (custom platform)

A small but real platform covering the five functions ASSET asked every candidate to show. The visitor side and the staff console both work. All data is fictional and the GM&E codes are dummies (`DEMO-GME-…`).

- Live: https://asset-voyages-demo.debanjan186.workers.dev (Cloudflare Workers free plan, D1, cron 03:00 UTC)
- Staff console: `/console`. Demo accounts `direction`, `equipe` and `contributeur` all use the sandbox password `demo-asset`, which is also shown on the login page.

## Architecture in plain words

One Cloudflare Worker answers every request. It builds each page on the server, so the site works with JavaScript turned off; a 1 KB script only adds comforts such as filters that apply as soon as you pick one. The data lives in one D1 database (SQLite). The fonts, the stylesheet and the script are served as static files. Every night at 03:00 UTC a scheduled trigger puts the sandbox back to its starting state.

**Private sandbox per browser, row-level copy-on-write.** On its first visit each browser receives an HttpOnly cookie that names its own sandbox. Browsing writes nothing. At the browser's first write the sandbox is registered (one row), and from then on only the rows it touches are written under its id: a new congress or enquiry, or the new version of an edited one. Reads lay those rows over the shared seed: for congresses, enquiries, codes and requests, a sandbox row hides the seed row with the same key, and history and logs are a union. Other visitors never see another browser's changes, so publishing, defacing or approving with the shared demo logins only affects the browser that did it. « Réinitialiser la démo » deletes the caller's rows only. Once a cap is reached, the visitor keeps browsing the read-only seed under a calm banner (« Démo très demandée : vous pouvez parcourir, les essais reprennent dans quelques minutes. »), never a bare 429.

**Sandbox budget, D1 free plan: 100,000 rows written a day; index entries and deletes count as written rows.** The typical session is the full S1–S5 journey: 4 logins and 3 logouts, a new published congress, an edited seeded one, an enquiry, a status change, an owner, a note, a GM&E request, its approval and a reveal. FIX3-1 measures it on every run through a per-request meter (`x-d1-rows-written`, test key only) at **29 rows**: logins 4 × 2 (two throttle counters, no session row because sessions are signed cookies), logouts 3 × 1 (revocation), new congress 5 (sandbox row, two sandbox counters, the congress, its publication event), edited congress 1 (one upsert), enquiry 4 (the row, the replay-guard index, two throttle counters), status 2, owner 2, note 1, request 1, approval 1, reveal 1. We budget 30 rows. **RESERVED_ROWS = 10,000** a day covers the bounded nightly work: purging 300 expired sandboxes (about 4,500 rows), orphans, 1,000 expired logouts and 3,000 expired throttle rows, plus the reseed (about 150 rows). Capacity is (100,000 − 10,000) / 30 = **3,000 full sessions a day overall**, and **20 new sandboxes per IP a day**. A visitor who only browses costs 0 rows; one who only sends an enquiry costs about 7. Expired sandboxes beyond 300 a night stay until a quieter night: they cost storage only, never visibility. To make writes cheap, the tables keyed by sandbox are `WITHOUT ROWID` and clustered on `sbx`, and team notifications and « création » history lines are derived on read. Per-browser limits (enquiries, logins) reset when someone drops the cookie, so the per-IP caps are the backstop: 20 sandboxes a day, 60 enquiries per 10 minutes, and 50 login attempts per 15 minutes.

**Write guards (ADV-B-207).** No browser can use up the day's writes for everyone.
- **Per browser:** each sandbox gets 60 write requests per 10 minutes. They are counted in memory; the count is persisted with one upsert only once a browser passes 20 writes in a window. The full S1–S5 journey makes 9 write requests (logins and logouts excluded; FIX4-4), so it stays far below the limit and never spends a row on the count. Past 60, the browser keeps reading and sees « Beaucoup d’essais en peu de temps : vos modifications reprennent dans quelques minutes. »
- **Global:** every request's written rows are metered. The tally is flushed to a single daily counter at most every 5 minutes or every 200 rows, one write per flush. At 85,000 rows (15,000 below the D1 quota, a margin that absorbs unflushed tallies, logins and the nightly job), every write path degrades to the read-only seed with « Démo très demandée… ». Never a 500.
- **No sandbox for a refused request:** a sandbox is created only by a write that passed its role, CSRF and validation checks (FIX4-3).

**Keys (SEC-B-201).** AES-GCM for the codes uses `GME_KEY` itself. Each MAC has its own key, derived with HKDF from `GME_KEY`: `session-v1` (session cookies), `form-v1` (anonymous form tokens; the form kind is a signed field of the token), `confirm-v1` (confirmation links) and `iphash-v1` (IP hashes). Tokens must have exactly their expected parts: two for a session, three for a form token. An extra segment is refused (SEC-B-203).

**Test-run key (Worker secret `DEMO_TEST_KEY`).** It is 32 random bytes (base64url, 43 characters), held only as a Worker secret and in the gitignored `.dev.vars`, never in `wrangler.toml` or the code. Requests carrying it in `x-demo-test` are compared in constant time (SHA-256 digests through `safeEqual`). Such requests skip the per-IP caps only (sandboxes, enquiries, login attempts), never the per-browser, per-account or global caps, and they get the write meter header. A missing or short secret means no exemption and no meter. The orchestrator deletes the secret after the final live run (`npx wrangler@4 secret delete DEMO_TEST_KEY`), so the live demo carries no bypass. To set it: `python3 -c 'import secrets;print(secrets.token_urlsafe(32))' | npx wrangler@4 secret put DEMO_TEST_KEY`.

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
- **Passwords** are stored as PBKDF2-SHA256 hashes (WebCrypto, per-user salt). **Sessions** are signed cookies (HMAC over user, CSRF token, expiry and a nonce; nothing written at login); logging out writes the nonce to `revoked`, so a copied cookie is refused afterwards. Before this round, sessions used a random token whose SHA-256 is stored server-side, in a cookie `__Host-av_session` marked HttpOnly, Secure, SameSite=Strict, 8 h. Logging out deletes the session on the server.
- **CSRF**: every console POST needs the session's token and a same-origin `Origin`. The anonymous forms (enquiry, login) carry a signed token (HMAC) that also enforces the minimum fill time and blocks replay.
- **Login throttling** (atomic, `INSERT … ON CONFLICT … RETURNING` before the password check): 50 attempts per IP across all accounts (skipped by the test key); 10 per browser sandbox and account, so a flood from one browser stops there and never reaches the counters other visitors share; and 50 wrong passwords per IP and account. The `ACCOUNT_LOCKOUT` variable in `wrangler.toml` picks the mode. **Demo (`off`, deployed):** the shared demo accounts are never locked for other visitors. **Production (`on`):** 10 attempts per IP and account, plus 30 per account from any IP. In production, staff log in behind Cloudflare Access with 2FA, so account lockout is a second line of defence.
- **Enquiry form**: all validation happens on the server (dates, past dates, return on or after outbound, e-mail, passengers 1 to 50, lengths, consent). It also has a honeypot, a 3-second minimum fill time and a limit of 10 accepted enquiries per 10 minutes per browser (whatever its IP: found live, the proxy changes IP between requests) and 60 per IP hash for a whole office (stored in D1). A refused submission always shows a French message saying the enquiry was not sent. It uses POST-redirect-GET. The confirmation link is signed, so references cannot be enumerated.
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
| `fix_round1.spec.mjs` | FIX-1 to FIX-26 (eye review, adversarial and blind-QA findings, see below; FIX-6 split into 6a production mode and 6b demo mode) | 25/25 pass | pending redeploy |
| `fix_round2.spec.mjs` | FIX2-1 to FIX2-13 (independent battery: security, flakes, UX/a11y/eye, monkey gap) | 11/11 pass (FIX2-1, 2-3 and 2-4 local only) | pending deploy |
| `fix_round3.spec.mjs` | FIX3-1 to FIX3-4 (row-level copy-on-write, write budget per S1–S5 session, test-key secret, signed sessions) | 4/4 pass | pending deploy |
| `fix_round4.spec.mjs` | FIX4-1 to FIX4-6 (write guards per browser and global, refused POSTs create nothing, journey vs throttle, per-purpose MAC keys, exact token parts) | 6/6 pass (FIX4-2 local only) | pending deploy |
| `fix_round5.spec.mjs` | FIX5-1 to FIX5-4 (UX re-check P3: DV and CG references unbroken, e-mails wrap only at @ and dots, « Vérifié le » defaults to the Paris date) | 4/4 pass | pending deploy |
| `x_cross.spec.mjs` | X1, X1 strict, X2, X3, X4, X5, security headers, cookie and logout replay, console at 390 px, hostile console input | 9/9 pass | 9/9 pass |
| `z_screens.spec.mjs` | screenshots for X6 | 2/2 pass | 2/2 pass |
| **Total** | | **100/100 pass, twice in a row** | 73 pass, 2 skipped by design (version 19d443cb, before fix round 2) |

Fix round 1, local: 75/75. FIX-6a uses a second local server with `--var ACCOUNT_LOCKOUT:on --port 8788`; it is skipped live, as is FIX-3 (cron trigger). Before the fix round, both full runs (local `wrangler dev`, then live deploy b48a4877) passed 49/49. « X1 strict » was added afterwards and run on its own, passing locally and live, which brings the totals to 50.

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
| FIX-6a, FIX-6b | Atomic login throttle. Demo mode: per browser sandbox and per IP, with no account-wide lock. Production mode (`ACCOUNT_LOCKOUT=on`): adds an account-wide ceiling. Found live: the proxy spread parallel guesses over 7 IPs |
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
| FIX-25 (D5) | 10 enquiries per 10 minutes per browser (from any IP) and 60 per IP. The 11th shows a visible French message and keeps what was typed. The honeypot field is renamed and hidden with `display:none`, so autofill cannot trip it: this was the likely cause of the silent "no reference" seen in QA |
| FIX-26 (D6) | The date line reads « 29 sept. au 2 oct. 2027 » at every width, including for screen readers |

## Fix round 2 (independent battery)

| Test | Finding fixed |
|---|---|
| FIX2-1, FIX2-2 | ADV-B-009/010: sandbox caps of 20 per IP a day and 325 a day overall (budget arithmetic above); a calm banner instead of a 429; per-IP caps as the backstop |
| FIX2-3 | ADV-B-011: the per-IP login counter is incremented first and atomically |
| FIX2-4 | ADV-B-012: the nightly purge removes orphan rows; the seed copy uses INSERT OR IGNORE |
| FIX2-5 | X4 flake. Root cause: the live page body was « upstream request failed », the agent egress proxy's own error, which the Worker never sends. Reset is idempotent, and indexes on `sbx` keep it at a few milliseconds; five resets in a row each take under 3 s |
| FIX2-6 | S2-F2 flake. Root cause: the test read the rows before the results page had loaded. The test now waits for the results URL, and 30 parallel searches during 5 sandbox copies all return CG-0109 |
| FIX2-7 | USAB-B-011: the « Demandes » table fits at 1440 (Statut is column 2, Départ, Dates and Passagers are merged into « Voyage », Contact wraps); below 1320 px each row becomes a card |
| FIX2-8, FIX2-9 | A11Y-B-001/002: no aria-label on sidebar links (visible text plus hidden text); the masked code uses hidden text |
| FIX2-10 | EYE-B-011: plurals on the contributor home (« 12 Publiés ») |
| FIX2-11 | USAB-B-012: filters jump to `#resultats` |
| FIX2-12 | EYE-B-017 to 025, USAB-B-013: nothing breaks mid-word (password, references, phones, dates); URLs break only after « / »; the contact line stays in its card column; the badge stays in its column; even rhythm on the confirmation; « — exemple » kept on the title's line; one-line sidebar; « Voir le site public » on its own row; the user's name shown at 390; « Modifier le code GM&E » styled as a button; specific status messages |
| FIX2-13 | Monkey gap: input and textarea values are scanned for `DEMO-GME-` for every role |
