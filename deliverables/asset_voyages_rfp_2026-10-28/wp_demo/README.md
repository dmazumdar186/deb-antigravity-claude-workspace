# ASSET Voyages: WordPress demonstration plugin (Option A)

`asset-congres-demo` is a WordPress plugin built to show ASSET Voyages the five things they asked to see. It runs in **WordPress Playground**, so it needs no hosting, account or API key. **All data is fictional:** congress titles end in « — exemple », every e-mail address is `@example.com`, and the GM&E codes are dummies in the format `DEMO-GME-XXXX`.

- Visitor demo: `https://playground.wordpress.net/?mode=seamless&login=no&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-visitor.json` (logged out, opens on the catalogue)
- Admin demo: `https://playground.wordpress.net/?mode=seamless&blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json` (logged in as `direction`, Direction ASSET, opens on « Demandes »)
- About the URL parameters: by default, playground.wordpress.net forces `login: true` on every blueprint unless the URL carries `login=no` (source: `resolve-blueprint-from-url.ts`, `if (query.get('login') !== 'no') blueprint.login = true`). The visitor blueprint therefore sets `"login": false`, the URL adds `login=no`, and the plugin adds a safety net: when the visitor blueprint's `ASSET_DEMO_VISITOR` constant is set, Playground's automatic login is cancelled on arrival. A normal login through `wp-login.php` still works. `mode=seamless` shows the site full width, without Playground's browser frame and toolbar (documented values: `browser-full-screen`, the default, or `seamless`).
- Demo accounts (throwaway sandbox password `demo-asset`): `direction` (Direction ASSET; also edits, publishes and deletes the site’s pages, its own and others’, with no user, plugin, theme or settings access and no unfiltered HTML), `equipe` (Équipe ASSET), `contributeur` (Contributeur ASSET). Playground's own `admin` / `password` is the administrator.
- Isolation: the demo links are public, but WordPress Playground runs the whole site (PHP + SQLite) **inside each visitor's own browser tab**. Visitors never share a database, so what one person types (enquiries, access requests, revealed dummy codes) is never seen by anyone else, and no cross-visitor isolation layer is needed. The only shared files are the static `asset-congres-demo.zip` and the two blueprints.
- One journey in one tab: the visitor link and the admin link are two separate sandboxes, so an enquiry sent on one never reaches the other. To show the whole flow in **one** Playground tab, use the discreet « Espace équipe » link in the site header or footer: it opens the login page, and after signing in (e.g. `equipe` / `demo-asset`) the dashboard shows « Dernière demande » with the enquiry just sent, also first in « Demandes ». The way back is « Retour au site » in the admin bar, then « Se déconnecter » in the site header.
- Reset: reload the Playground page. Every visit starts from the seed. **Outils → Démo ASSET** re-runs the seed, which is idempotent and creates no duplicates.

## What each feature does

| Client story | In the demo |
|---|---|
| S1 Create / edit a congress | **Congrès** menu (custom post type `asset_congres`, archive `/congres/`). The « Informations du congrès » box holds start/end dates, city, country, discipline, venue, official website, source and verification date. French labels, and required fields are marked « (obligatoire) ». Country and discipline are typed, with suggestions (taxonomies `asset_pays`, `asset_discipline`). Server-side checks: an end date before the start date, or an invalid URL, is rejected with a French message. A published congress missing required fields goes back to draft. HTML is stripped from titles. Workflow: draft → pending review → published. The **Contributeur ASSET** role can draft and submit for review but cannot publish. |
| S2 Public catalogue | The « Catalogue des congrès » page (shortcode `[asset_catalogue]`) is the home page. It is a server-rendered GET form, so it works without JavaScript. Search covers title, city and discipline, and ignores accents and case. Filters: discipline, country, month, and date sort. One-click discipline chips. Past events are hidden by default, with an opt-in checkbox. Shows 9 per page with pagination that keeps the filters. Also shows the result count, a no-results state and a reset link. Each congress page has a details card (dates, city, country, discipline, venue, official website, source + verification date; the fictional congresses have no website and show « Site officiel : fictif (démonstration) » as plain text, and a reserved example.com/.net/.org address is never a link) and the « Demander un devis vol » form, prefilled with that congress. |
| S3 Flight enquiry | Fields: nom, e-mail, téléphone, société (optional), ville de départ, date aller, date retour, nombre de passagers, message, RGPD consent. Server validation: passengers must be a whole number from 1 to 50; return date ≥ outbound date; no past dates; valid e-mail; length limits. Errors appear next to each field in French, and the visitor's input is kept. Spam protection: nonce, honeypot, a signed minimum fill time of 3 s, and a rate limit of 10 accepted enquiries per hour per hashed IP (stored as a transient; the IP itself is never stored). Each enquiry is stored as the private post type `asset_demande` (not public, not in REST, custom capability). The visitor sees a reference such as `DV-2026-0007` on the confirmation page. The form uses post/redirect/get with a single-use form token, so reloading the page or replaying the request creates nothing new. The team is notified by `wp_mail`, and every notification is also written to **Demandes → Journal des notifications**, since Playground has no SMTP. |
| S4 Team tracks enquiries | The **Demandes** screen lists reference, date, congress, contact, departure city, dates, passengers, status and owner. It has status views with counts (Nouvelle, Qualifiée, Devis envoyé, Gagnée, Perdue), search (name, e-mail, company, city, reference) and sorting. The detail screen lets staff change the status, assign an owner and add internal notes. The append-only history records who, when and from → to, and cannot be edited or deleted from the UI. CSV export (`;`, UTF-8 BOM) neutralises spreadsheet formulas: cells starting with `=`, `+`, `-`, `@`, tab or CR get a leading `'`. A dashboard widget shows counts by status and links straight to the newest enquiry. |
| S5 GM&E codes | Codes live **only** in the custom table `wp_asset_gme_codes`, never in post meta, options or REST. They are encrypted with libsodium XChaCha20-Poly1305, using a random nonce per value and the congress id as additional data; with no valid `ASSET_GME_KEY`, the plugin fails closed. The **Codes GM&E** menu (sub-items « Codes », « Demandes d’accès », « Journal d’accès GM&E ») shows codes masked; « Afficher le code » shows one, « Masquer le code » hides it again. **Équipe ASSET** clicks « Demander l'accès » and must give a reason. That button only appears on verified or approved codes: detected codes are not yet verifiable, and expired codes are closed to everyone, Direction included. **Direction ASSET** (and administrators, capability `asset_manage_gme`) approves or refuses from the dashboard widget or the « Demandes d'accès » screen. « Approuver pour 24 h » grants 24 h; « Retirer l’accès » ends it at once. A reveal is a nonce'd POST that is checked on the server and shown once in that response only. Every reveal, refused reveal, request and decision is logged (who, which congress, when) in « Journal d’accès GM&E », which only Direction can see. The log never contains a code. Code lifecycle: Détecté → Vérifié → Approuvé pour la vente → Expiré, with validity dates and an evidence note. The public site only says « Tarif congrès négocié disponible : appliqué à votre devis » when a code is approved and in date. |

### Encryption key (demo and production)

Codes are encrypted with libsodium XChaCha20-Poly1305 (AEAD). The congress id is bound as additional data, so a ciphertext copied onto another congress's row no longer decrypts. The key comes **only** from the constant `ASSET_GME_KEY`: 64 hex characters, or 32 bytes in base64. If the constant is missing or malformed, the plugin **fails closed**. It saves no code, reveals no code, and shows an admin notice on « Codes GM&E » and on the dashboard. There is no fallback to the WordPress salts, because they can live in `wp_options`, and then a database copy alone would decrypt every code.

- **Demo:** both blueprints set `ASSET_GME_KEY` with the `defineWpConfigConsts` step, next to `ASSET_GME_KEY_NOTICE` ("DEMO ONLY"). That key is public, because it sits in the blueprint, and it only protects fictional `DEMO-GME-` codes in a per-browser sandbox. It must never be reused.
- **Production:** generate the key once on a trusted machine (`php -r "echo sodium_bin2hex(sodium_crypto_aead_xchacha20poly1305_ietf_keygen());"`). Store it in the host's secret manager or as a server environment variable, and have `wp-config.php` read it, e.g. `define( 'ASSET_GME_KEY', getenv( 'ASSET_GME_KEY' ) );`. Never store it in the database, in the repository, or in database backups. Keep an offline escrow copy with Direction, because losing the key makes the codes unrecoverable. Rotation (a WP-CLI command that re-encrypts every row with the new key, then removes the old one) is written during the project.

## Files

```
wp_demo/
  plugin/asset-congres-demo/      plugin source (PHP 8.1+, no dependencies)
    asset-congres-demo.php        bootstrap, activation (roles, tables, rewrite rules)
    includes/class-roles.php      roles and capabilities
    includes/class-congres.php    CPT, taxonomies, meta box, validation
    includes/class-catalogue.php  catalogue shortcode, single page details, assets
    includes/class-demandes.php   enquiry CPT, public form, validation, anti-spam
    includes/class-demandes-admin.php  list table, detail, history, CSV, dashboard widget
    includes/class-notifications.php   wp_mail + notification journal
    includes/class-gme.php        encrypted store, access grants, audit log
    includes/class-gme-admin.php  GM&E screens, approvals, reveal
    includes/class-seed.php       idempotent fictional seed (+ `wp asset-demo seed`, Outils → Démo ASSET)
    assets/css/public.css, admin.css   all colours and fonts as :root tokens
  blueprints/*.template.json      blueprint sources (plugin URL placeholder)
  blueprint-visitor.json, blueprint-admin.json   rendered, point at the hosted zip
  build_zip.sh                    reproducible zip + blueprint rendering (single URL constant)
  asset-congres-demo.zip          built plugin
  tests/                          Playwright suite + start/stop/run scripts
  screens/                        screenshots at 1440 and 390 px
```

## Run locally

```bash
cd wp_demo
./build_zip.sh --local                 # zip + .tmp/blueprint-*.local.json (zip served from http://127.0.0.1:9401)
tests/start_server.sh                  # fresh Playground on http://127.0.0.1:9400 (visitor blueprint, fresh DB mounted at .tmp/db-current)
# or, by hand:
npx @wp-playground/cli@3.1.62 server --blueprint=.tmp/blueprint-admin.local.json --port=9400
```

`build_zip.sh` holds the single swappable URL (`HOSTED_ZIP_URL`; `PLUGIN_ZIP_URL` overrides the local one). Builds are byte-identical on re-run: fixed mtimes and sorted entries.

The admin blueprint ends with Playground's `login` step (as `direction`). Playground then auto-logs-in every new browser on that server, so the test suite boots the **visitor** blueprint and logs in through `wp-login.php` for each role. A second, throwaway server (port 9410, visitor blueprint **without** the key, started with `--login`) is booted by `08-fixes.spec.js` to prove two things: the fail-closed behaviour, and that the forced auto-login is cancelled.

Theme: the zip includes a minimal child theme of Twenty Twenty-Five (`theme/asset-demo`: ASSET palette and system/Inter fonts). It has a header with « ASSET Voyages — démonstration » and « Catalogue des congrès », a footer with the fictional-data notice, and a congress template with no author, date, category or related-posts blocks. The seed copies the theme into `wp-content/themes`, and the blueprints activate it (`activateTheme`).

Dates and time zone: the blueprints and the seed set `timezone_string = Europe/Paris` and `d/m/Y`. The admin, the history, the journals and the CSV show `jj/mm/aaaa HH:MM` in Paris time. Public pages use long French dates (« 27 août 2027 »). The native date pickers follow the visitor's browser language; screenshots are taken with `fr-FR` (jj/mm/aaaa).

Hardening in the plugin: login throttle per IP + username (10 failures per 15 minutes, no global account lockout), one generic error that never confirms whether a username exists, `/wp/v2/users` and author archives hidden from visitors, front-end headers (`X-Content-Type-Options`, `X-Frame-Options: SAMEORIGIN`, `frame-ancestors 'self'`, `Referrer-Policy`), separate nonces for approve, refuse and revoke, translations loaded on `init`. On the congress editor, autosave is switched off (it locked « Publier » while its heartbeat round-trip was pending, which blocked keyboard publishing), the heartbeat is capped at 60 s, and TinyMCE is replaced by a labelled plain-text « Description du congrès ».

Site language: the `setSiteLanguage: fr_FR` step works with the local CLI (translations download through the proxy), and admin and login screens are in French. All plugin strings are French source strings wrapped in `__()` with the text domain `asset-congres-demo`, so they can be translated. Month names are plugin strings, so dates stay French even if the core translation download ever fails.

## Tests

Run the full suite with `tests/run_all.sh`. It starts a fresh server, runs every spec in order with one worker, then stops the server. Playwright and Chromium were preinstalled; `tests/node_modules/playwright` is a symlink to the global install. Each test name starts with the acceptance gate ID from `../21_Acceptance_Gates_5_Stories.md`.

Client-eye fixes (6 Nov 2026, plugin 0.2.1), on fresh Playgrounds (WordPress 7.1.4, PHP 8.3): `tests/run_all.sh` ran **twice in a row with 78 passed, 0 failed and 0 skipped each time** (68 earlier tests + 10 client-eye regression tests in `09-client-eye.spec.js`). The screenshot run (`tests/run_screens.sh`, fresh seed, fr-FR, Europe/Paris) passed 3 of 3. Earlier fix round A: 68 of 68, twice. QA's monkey (`../qa/A/monkey_A.mjs`, seed 20261105, 300 actions × 4 roles, fresh server) found **0 failures**. Semgrep `p/php` and `p/default` find 0 issues; the one exemption states its reason inline. The scripts accept `WP_PORT` / `ALT_PORT` / `ZIP_PORT` (default 9400 / 9410 / 9401), so two suites (or two checkouts) can share a machine without stopping each other's servers or serving each other's zip.

Suites: functional (S1-S5), leak (`06-leak`: a logged-out crawl of 330+ URLs, and a second crawl as `equipe` without a grant, plus a raw scan of the SQLite file), hostile input (H gates), cross-cutting X1-X4, the fix-round tests FIX-A-1 to FIX-A-24 (`08-fixes.spec.js`; FIX-A-18 is in `screens.spec.js`), the client-eye regression tests (`09-client-eye.spec.js`, one per REAL finding for A in `../qa/register/CLIENT_EYE.md`: page editing for Direction, « Votre session a expiré. Reconnectez-vous. », unbreakable « — exemple », glossary labels, fictional seed names and phones, « Site officiel : fictif (démonstration) », Paris date in the CSV name, no compression-test errors, no layout shift from notices), and the rate limit (`99`). Click counts for the E gates are recorded as test annotations.


| Gate | Result | Evidence |
|---|---|---|
| S1-F1 | PASS | 1 test(s); clicks=3 |
| S1-F2 | PASS | 1 test(s); clicks=3 |
| S1-F3 | PASS | 1 test(s) |
| S1-E1 | PASS | 1 test(s); clicks=3 |
| S1-E2 | PASS | 1 test(s); clicks=3 |
| S1-H1 | PASS | 1 test(s) |
| S1-H2 | PASS | 1 test(s) |
| S2-F1 | PASS | 1 test(s) |
| S2-F2 | PASS | 1 test(s) |
| S2-F3 | PASS | 1 test(s) |
| S2-F4 | PASS | 1 test(s) |
| S2-F5 | PASS | 1 test(s) |
| S2-F6 | PASS | 1 test(s) |
| S2-E1 | PASS | 1 test(s); clicks=2 |
| S2-E2 | PASS | 1 test(s) |
| S2-H1 | PASS | 1 test(s) |
| S3-F1 | PASS | 1 test(s) |
| S3-F2 | PASS | 1 test(s) |
| S3-F3 | PASS | 1 test(s) |
| S3-F4 | PASS | 1 test(s) |
| S3-E1 | PASS | 1 test(s) |
| S3-H1 | PASS | 1 test(s) |
| S3-H2 | PASS | 2 test(s); accepted-before-block=4 |
| S3-H3 | PASS | 1 test(s) |
| S4-F1 | PASS | 1 test(s) |
| S4-F2 | PASS | 1 test(s) |
| S4-F3 | PASS | 1 test(s) |
| S4-F4 | PASS | 1 test(s) |
| S4-F5 | PASS | 1 test(s) |
| S4-F6 | PASS | 1 test(s); urls=330 |
| S4-E1 | PASS | 1 test(s); clicks=3 |
| S4-H1 | PASS | 1 test(s) |
| S5-F1 | PASS | 2 test(s) |
| S5-F2 | PASS | 1 test(s); clicks=2 |
| S5-F3 | PASS | 2 test(s); clicks=1 |
| S5-F4 | PASS | 1 test(s); clicks=2 |
| S5-F5 | PASS | 1 test(s) |
| S5-E1 | PASS | 3 test(s); clicks=2; clicks=1; clicks=2 |
| S5-H1 | PASS | 1 test(s) |
| S5-L1 | PASS | 2 test(s); urls=330; urls=404 |
| S5-L2 | PASS | 1 test(s) |
| X1 | PASS | 2 test(s) |
| X2 | PASS | 1 test(s) |
| X3 | PASS | 1 test(s) |
| X4 | PASS | 1 test(s) |
| FIX-A-1 | PASS | 2 test(s) |
| FIX-A-2 | PASS | 1 test(s) |
| FIX-A-3 | PASS | 1 test(s) |
| FIX-A-4 | PASS | 1 test(s) |
| FIX-A-5 | PASS | 1 test(s) |
| FIX-A-6 | PASS | 1 test(s) |
| FIX-A-7 | PASS | 1 test(s) |
| FIX-A-8 | PASS | 1 test(s) |
| FIX-A-9 | PASS | 1 test(s) |
| FIX-A-10 | PASS | 1 test(s) |
| FIX-A-11 | PASS | 1 test(s) |
| FIX-A-12 | PASS | 1 test(s) |
| FIX-A-13 | PASS | 1 test(s) |
| FIX-A-14 | PASS | 1 test(s) |
| FIX-A-15 | PASS | 1 test(s) |
| FIX-A-16 | PASS | 1 test(s) |
| FIX-A-17 | PASS | 1 test(s) |
| FIX-A-18 | PASS | screens.spec.js on a fresh seed (3/3 passed: 12 congresses, clean data, 32 PNGs) |
| FIX-A-19 | PASS | 1 test(s) |
| FIX-A-20 | PASS | 1 test(s) |
| FIX-A-21 | PASS | 1 test(s) |
| FIX-A-22 | PASS | 1 test(s) |
| FIX-A-23 | PASS | 1 test(s) |
| FIX-A-24 | PASS | 1 test(s) |
| CE-A4-002 | PASS | 1 test(s) |
| CE-B2-001 | PASS | 1 test(s) |
| CE-B4-004 | PASS | 1 test(s) |
| CE-B4-005 | PASS | 1 test(s) |
| CE-B6-001…008 | PASS | 1 test(s) |
| CE-C1-001 | PASS | 1 test(s) |
| CE-C4-001 | PASS | 1 test(s) |
| CE-C7-003 | PASS | 1 test(s) |
| CE-D1-001 | PASS | 1 test(s) |
| CE-D2-002 | PASS | 1 test(s) |

X5-X7 (Hallmark gate on the hub page, eye review, hub-page traces) belong to the hub page and to the QA agent, not to this plugin suite.


## Working in the demo vs needs development for production

| Area | Working in the demo | Needs development for production |
|---|---|---|
| Congress management | CPT, meta box, taxonomies, validation, draft → review → publish, Contributeur role | CSV import of the ~300 existing listings with duplicate detection (name + dates + city), bulk edit, media/brochures, a field for the organiser and their contact |
| Catalogue | Search, filters, pagination, details page, no-JS, responsive at 390 px, under Twenty Twenty-Five | ASSET's real theme/branding and copy, SEO metadata and structured data (`Event` schema), bilingual FR/EN content (Polylang or WPML, or native multilingual), analytics with consent |
| Enquiry form | Validation, honeypot, minimum fill time, rate limit, PRG, reference numbers, consent timestamp | Real SMTP/transactional e-mail (with SPF/DKIM) and an acknowledgement e-mail to the traveller, CAPTCHA fallback if spam appears, retention/erasure policy (RGPD) wired to WordPress privacy tools |
| Enquiry tracking | List, filters, search, statuses, owner, notes, append-only history, CSV export, dashboard widget | Link to ASSET's booking/quote tools or CRM, SLA reminders, per-owner notifications, reporting |
| GM&E codes | Encrypted custom table, masked display, request → approve (24 h) → reveal → revoke, audit log, public « tarif négocié » notice only | Production key management (env/secret manager, rotation command), attendee-facing code delivery if wanted (for example a signed one-time link to the traveller), alerting on refused reveals, export of the audit log |
| Security & operations | Nonces + capability checks on every action, escaping, custom capabilities, no third-party scripts | 2FA for staff, strong passwords and login rate limiting, managed hosting with WAF, TLS, automatic updates, daily off-site backups with restore tests, uptime monitoring, staging environment |
| Data | Fictional seed, idempotent, reset by reload | Migration of real data, access by real staff accounts, a data-processing agreement |

## Known limitations of the demo

- Playground has no outgoing mail server, so notifications show as « Non distribué (pas de SMTP) » in the journal.
- Playground keeps everything in the browser tab: closing or reloading it resets the site. That is intended for a sandbox.
- The 24 h expiry of an approval is enforced on the server (`expires_at` is compared at each reveal). The test suite checks the expiry time (approval time + 24 h), not a real 24 h wait.
- The dummy codes are visible in the plugin source (`class-seed.php`) because the seed has to create them, and the demo key is visible in the blueprints. Both are fictional or sandbox-only and never appear in any page, feed, API response or database row in clear.
- Native date pickers show the browser's own order (mm/dd/yyyy in an English browser). The stored value and every date the plugin displays are jj/mm/aaaa.
- The rate limit counts accepted enquiries per hashed IP. Behind a proxy or CDN, the real client IP header must be configured.
