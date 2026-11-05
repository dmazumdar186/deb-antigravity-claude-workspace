# ASSET Voyages: WordPress demonstration plugin (Option A)

`asset-congres-demo` is a WordPress plugin built to show ASSET Voyages the five things they asked to see. It runs in **WordPress Playground**, so it needs no hosting, account or API key. **All data is fictional:** congress titles end in « — exemple », every e-mail address is `@example.com`, and the GM&E codes are dummies in the format `DEMO-GME-XXXX`.

- Visitor demo: `https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-visitor.json` (logged out, opens on the catalogue)
- Admin demo: `https://playground.wordpress.net/?blueprint-url=https://asset-voyages-redesign.pages.dev/demo-wordpress/blueprint-admin.json` (logged in as `admin`, opens on « Demandes »)
- Demo accounts (throwaway sandbox password `demo-asset`): `direction` (Direction ASSET), `equipe` (Équipe ASSET), `contributeur` (Contributeur ASSET). Playground's own `admin` / `password` is the administrator.
- Reset: reload the Playground page. Every visit starts from the seed. **Outils → Démo ASSET** re-runs the seed, which is idempotent and creates no duplicates.

## What each feature does

| Client story | In the demo |
|---|---|
| S1 Create / edit a congress | **Congrès** menu (custom post type `asset_congres`, archive `/congres/`). The « Informations du congrès » box holds start/end dates, city, country, discipline, venue, official website, source and verification date. French labels, and required fields are marked « (obligatoire) ». Country and discipline are typed, with suggestions (taxonomies `asset_pays`, `asset_discipline`). Server-side checks: an end date before the start date, or an invalid URL, is rejected with a French message. A published congress missing required fields goes back to draft. HTML is stripped from titles. Workflow: draft → pending review → published. The **Contributeur ASSET** role can draft and submit for review but cannot publish. |
| S2 Public catalogue | The « Catalogue des congrès » page (shortcode `[asset_catalogue]`) is the home page. It is a server-rendered GET form, so it works without JavaScript. Search covers title, city and discipline, and ignores accents and case. Filters: discipline, country, month, and date sort. One-click discipline chips. Past events are hidden by default, with an opt-in checkbox. Shows 9 per page with pagination that keeps the filters. Also shows the result count, a no-results state and a reset link. Each congress page has a details card (dates, city, country, discipline, venue, website, source + verification date) and the « Demander un devis vol » form, prefilled with that congress. |
| S3 Flight enquiry | Fields: nom, e-mail, téléphone, société (optional), ville de départ, date aller, date retour, nombre de passagers, message, RGPD consent. Server validation: passengers must be a whole number from 1 to 50; return date ≥ outbound date; no past dates; valid e-mail; length limits. Errors appear next to each field in French, and the visitor's input is kept. Spam protection: nonce, honeypot, a signed minimum fill time of 3 s, and a rate limit of 10 accepted enquiries per hour per hashed IP (stored as a transient; the IP itself is never stored). Each enquiry is stored as the private post type `asset_demande` (not public, not in REST, custom capability). The visitor sees a reference such as `DV-2026-0007` on the confirmation page. The form uses post/redirect/get with a single-use form token, so reloading the page or replaying the request creates nothing new. The team is notified by `wp_mail`, and every notification is also written to **Demandes → Journal des notifications**, since Playground has no SMTP. |
| S4 Team tracks enquiries | The **Demandes** screen lists reference, date, congress, contact, departure city, dates, passengers, status and owner. It has status views with counts (Nouvelle, Qualifiée, Devis envoyé, Gagnée, Perdue), search (name, e-mail, company, city, reference) and sorting. The detail screen lets staff change the status, assign an owner and add internal notes. The append-only history records who, when and from → to, and cannot be edited or deleted from the UI. CSV export (`;`, UTF-8 BOM) neutralises spreadsheet formulas: cells starting with `=`, `+`, `-`, `@`, tab or CR get a leading `'`. A dashboard widget shows counts by status and links straight to the newest enquiry. |
| S5 GM&E codes | Codes live **only** in the custom table `wp_asset_gme_codes`, never in post meta, options or REST. They are encrypted with libsodium `secretbox` (random nonce per value). The **Accès GM&E** menu shows codes masked. **Équipe ASSET** clicks « Demander l'accès » and must give a reason. **Direction ASSET** (and administrators, capability `asset_manage_gme`) approves or refuses from the dashboard widget or the « Demandes d'accès » screen. An approval lasts 24 h and can be revoked at once. A reveal is a nonce'd POST that is checked on the server and shown once in that response only. Every reveal, refused reveal, request and decision is logged (who, which congress, when) in « Journal GM&E », which only Direction can see. The log never contains a code. Code lifecycle: Détecté → Vérifié → Approuvé pour la vente → Expiré, with validity dates and an evidence note. The public site only says « Tarif congrès négocié disponible : appliqué à votre devis » when a code is approved and in date. |

### Encryption key in production

The plugin uses the constant `ASSET_GME_KEY` when it is defined: 64 hex characters, or 32 bytes in base64. Generate it once (`php -r "echo sodium_bin2hex(sodium_crypto_secretbox_keygen());"`). Put it in `wp-config.php` or, better, in a server environment variable read by `wp-config.php`. Keep it out of the database and out of backups of the database, and keep an offline escrow copy, because losing the key makes the codes unrecoverable. Without the constant, the demo derives a key from the site's `wp_salt('auth')`. That is acceptable for a sandbox only, because rotating the salts would make the codes unreadable. Key rotation (re-encrypt all rows with a new key) would be a small WP-CLI command, written during the project.

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

The admin blueprint ends with Playground's `login` step. Playground then auto-logs-in every new browser on that server, so the test suite boots the **visitor** blueprint and logs in through `wp-login.php` for each role.

Site language: the `setSiteLanguage: fr_FR` step works with the local CLI (translations download through the proxy), and admin and login screens are in French. All plugin strings are French source strings wrapped in `__()` with the text domain `asset-congres-demo`, so they can be translated. Month names are plugin strings, so dates stay French even if the core translation download ever fails.

## Tests

Run the full suite with `tests/run_all.sh`. It starts a fresh server, runs every spec in order with one worker, then stops the server. Playwright and Chromium were preinstalled; `tests/node_modules/playwright` is a symlink to the global install. Each test name starts with the acceptance gate ID from `../21_Acceptance_Gates_5_Stories.md`.

RESULTS_PLACEHOLDER

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
- The dummy codes are visible in the plugin source (`class-seed.php`) because the seed has to create them. They are fictional and never appear in any page, feed, API response or database row in clear.
- The rate limit counts accepted enquiries per hashed IP. Behind a proxy or CDN, the real client IP header must be configured.
