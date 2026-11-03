# WordPress feasibility study — ASSET Voyages (2026-11-03)

Scope: WordPress build at a fixed price ≤ €3,000 excl. VAT; hosting/maintenance quoted separately; tool costs billed to the client.
**Verification key:** **V** = price seen on the vendor page on 2026-11-03 (scraped with curl). **U** = from model knowledge (cut-off mid-2026), NOT checked today. Re-check every U before quoting.

## 1. Plugin stack

| Need | Pick (free-first) | Cost | Licence holder | Alternative / premium | Status |
|---|---|---|---|---|---|
| Congress CPT + taxonomies (discipline, country, city, period) | Custom code in an mu-plugin (`register_post_type`, `register_taxonomy`) | €0 | Code handed to the client (GPL) | CPT UI (free): adds a dependency and does not version the config | design choice |
| Custom fields | Secure Custom Fields (WordPress.org fork of ACF, 100k+ installs, v3.x), https://wordpress.org/plugins/secure-custom-fields/ | €0 | GPL, none | ACF Pro ~$49–149/yr (U), https://www.advancedcustomfields.com/pro/ | V (installs); ACF price U |
| Recommended for fields | Native `register_post_meta` + a small custom metabox for the private GM&E fields | €0 | — | — | design |
| Filtering/search | Custom `WP_Query` + taxonomy query form (server-rendered, accessible) | €0 | — | FacetWP from $99/yr; higher tiers $249 / $349 / $499 (V), https://facetwp.com/pricing/ | V |
| CSV import of ~300 rows | Custom WP-CLI command + admin upload screen with dry run | €0 | — | WP All Import Pro: tiers seen from $99 up to $1,299 lifetime (V), https://www.wpallimport.com/pricing/ | V |
| Forms + entries | Fluent Forms free (entries stored in the DB, CSV export, conditional logic, Turnstile) (U), https://wordpress.org/plugins/fluentform/ | €0 | — | Gravity Forms $59 / $159 / $259 per year (V), https://www.gravityforms.com/pricing/. WPForms Lite does not store entries (U) | mixed |
| Enquiry back-office (status, owner, history, routing) | Custom "Enquiry" CPT that forms write into via a hook, plus a status taxonomy, an owner field and the revision log | €0 | — | Fluent Forms Pro (U) | design |
| Roles (5) | Defined in code (`add_role`, mapped capabilities); Members plugin (free) only to inspect | €0 | — | User Role Editor (free) | U |
| MFA for admins | Two-Factor (WordPress.org, free), https://wordpress.org/plugins/two-factor/ ; or WP 2FA free with role enforcement | €0 | — | WP 2FA Premium (U) | U |
| Access/activity log | WP Activity Log free, or Simple History (free) | €0 | — | WP Activity Log Premium ~$99+/yr (U) | U |
| Versions/restore | Core revisions; revisions enabled for the meta (`revisions_enabled` on `register_post_meta`, WP 6.4+) | €0 | — | — | U |
| Editorial draft → approval → publish | Core statuses + custom "pending approval" capability gate. PublishPress Statuses (free) as an option | €0 | — | PublishPress Pro (U) | U |
| Backups | Host backups plus UpdraftPlus free to off-site storage | €0 (plus storage) | — | UpdraftPlus Premium ~$70/yr (U) | U |
| Security | Wordfence free + security headers at server/Cloudflare level | €0 | — | Patchstack (U) | U |
| SEO + 301s | Rank Math free (or Yoast free) + Redirection (free) | €0 | — | Rank Math Pro (U) | U |
| Multilingual (EN later) | Polylang free (hreflang supported) | €0 | — | WPML €39 / €99 / €199 per year (V), https://wpml.org/purchase/ | V |
| Cookie consent (CNIL) | Complianz free (refusal on the same level as acceptance, Consent Mode) | €0 | — | CookieYes paid tiers (U) | U |
| Caching/performance | Host-level cache (LiteSpeed Cache on o2switch/Hostinger) | €0 | — | WP Rocket ~€59/yr (U) | U |
| Anti-spam | Cloudflare Turnstile (free), https://www.cloudflare.com/products/turnstile/ | €0 | client's Cloudflare account | — | U |

**"€0 recurring licence" stack:** core + custom mu-plugin (CPT, roles, GM&E meta, importer, enquiry CRM) + SCF + Fluent Forms free + Two-Factor + WP Activity Log/Simple History + Wordfence + Rank Math + Redirection + Polylang + Complianz + UpdraftPlus. **Total €0/yr.** This stack also keeps the plugin count low (about 10).
**Best-in-class stack:** ACF Pro (~$49, U) + FacetWP ($99, V) + WP All Import Pro (lowest tier $99, V; the import add-on may cost extra) + Gravity Forms Elite ($259, V) + WPML Multilingual CMS (€99, V) + WP Rocket (~€59, U) + WP Activity Log Premium (~$99, U) + UpdraftPlus Premium (~$70, U). **Total ≈ €800–850/yr** (U on FX and tiers). Licences can be bought in the client's name and paid by the client. Recommendation: €0 stack. Paid plugins save little build time here, because the fixed-price scope needs custom logic anyway (GM&E, dedup, routing).

## 2. Hosting (all U — vendor pages not parsed today; o2switch returned no price via curl)
| Host | €/month approx. | Backups/staging/SSL/CDN | EU data | Notes |
|---|---|---|---|---|
| o2switch (FR, Clermont) | ~€8–10 excl. VAT, single offer (U) | JetBackup daily (≈30 days), staging via Softaculous, Let's Encrypt; no CDN (use Cloudflare free) | France | No formal SLA (U); PHP 8.x, MariaDB |
| Hostinger WP | ~€3–12, with promo pricing that rises on renewal (U) | Daily/weekly backups by plan, staging on Business+, CDN on higher tiers | EU DC selectable (U) | Owned outside the EU (Lithuania/Cyprus entity) (U) |
| OVHcloud Perso/Pro | ~€3–10 (U) | Backups, SSL; staging limited | France | |
| Infomaniak WP | ~€6–15 (U) | Backups, SSL; staging via tools | Switzerland (adequacy decision) | Eco-friendly positioning |
| Kinsta | from ~$35/mo (U) | Daily backups, staging, CDN, 99.9% SLA | GCP Europe (Paris/Frankfurt) | Premium |
| WP Engine | from ~$30–40/mo (U) | Same as Kinsta | EU regions | Premium |
**Picks:** cheap and reliable = **o2switch (~€10/mo excl. VAT, U)** + Cloudflare free. Premium = **Kinsta (~€35/mo, U)** for the SLA and managed staging. Two-site staging on o2switch costs nothing extra (subdomain). RPO 24h: daily JetBackup + off-site UpdraftPlus. RTO 8h: a documented restore, tested in T13.

## 3. GM&E private-code protection
- Store the codes in post meta with a leading underscore (`_gme_code`). `register_post_meta(..., ['show_in_rest'=>false, 'single'=>true, 'auth_callback'=>fn()=>current_user_can('manage_gme')])`. Underscore keys are also hidden from the core Custom Fields box.
- Metabox rendered only `if current_user_can('manage_gme')`; save handler checks the capability + nonce.
- Never output in the theme (no generic "print all meta" templates). Exclude from search: core search does not search meta, and any search plugin must be configured to skip `_gme_*`.
- Exports: core WXR export includes ALL postmeta. Filter `wxr_export_skip_postmeta` to skip `_gme_*`, and restrict the export capability. CSV exports go through our code, so whitelist the columns.
- Also check: REST `?context=edit` exposure, oEmbed, RSS, sitemaps, the activity-log plugin (it may record meta values; configure it to mask them), and the backup files (they contain the DB, so encrypt them and limit access).
- **Leak test (automated, T05):** seed a canary code `GME-CANARY-7731`, then curl and grep for it across: public pages, `/wp-json/wp/v2/congress?context=view|edit` as anonymous and as a contributor/commercial-viewer user, `/?s=`, `/feed/`, sitemaps, the WXR export as a non-admin, and the HTML source. Expected result: 0 hits.
- **Residual risk:** any plugin with DB access (forms, logs, SEO, backup, page builders) can read or expose meta, and a compromised admin account sees everything. Mitigations: minimal plugin set, MFA, a canary test after each update. Strongest option: keep codes in a separate custom table, or encrypt them with a key in wp-config (adds about 4h).

## 4. CSV import + dedup
WP-CLI `wp congress import file.csv --dry-run` plus an admin upload screen that calls the same class. Normalise each row (trim, case-fold, strip accents, ISO country, ISO dates). **Dedup key** = `sha1(normalised_name + start_date(YYYY-MM) + city)`, stored as `_import_key`. Exact match → update or skip, chosen by flag. Fuzzy match (same city + month, name similarity > 0.85 via `similar_text`) → flagged in the report, not imported. All rows go in as **draft**. The report CSV lists created/updated/skipped/flagged/errors. Re-running is idempotent. Effort ~10–12h.

## 5. Admin demo this week
(a) **WordPress Playground + blueprint** (https://wordpress.github.io/wordpress-playground/blueprints/ , U). Steps such as `installPlugin`, `runPHP`, `wp-cli`, `importWxr`, `login`, `defineWpConfigConsts` can preinstall wp.org plugins, register the CPT (via an mu-plugin zip), add roles and load sample data. Limits: the browser-only instance is lost on reload (no persistence), there is no outbound email, performance is slower, first load takes ~10–30s, it needs a modern Chromium/Firefox/Safari, and a blueprint hosted on Cloudflare Pages needs CORS headers (`_headers`). Not representative of hosting speed.
(b) o2switch staging: ~€10, live in ~1h plus the build. Persistent and shareable, and email works.
(c) Local + video: safe, but the client can't click through it.
**Recommend (a) for the demo, with (c) as a 5-minute recorded backup.** Hours: blueprint + mu-plugin + 20 sample congresses + roles = **6–8h**, recording 1h. Move to (b) once they sign.

## 6. SEO migration (WP → WP)
Same platform, so we can keep the permalink structure and slugs: run a WXR export → import (posts/pages/media), or migrate the full DB (Duplicator/WP-CLI `search-replace`) if the content is reused. Crawl the old site (Screaming Frog free ≤500 URLs, U), take the top URLs from GSC, build the 301 map in Redirection (CSV import), and check old URLs with `curl -I` (T10). Keep the GSC property, and resubmit the sitemap. ~6–8h.

## 7. Effort (one dev + Claude Code, honest)
| Module | h |
|---|---|
| Hosting, staging/prod, deploy (git or WP Migrate), backups | 4 |
| Block theme (theme.json, patterns) implementing the concept: ~8 templates | 20 |
| Business Travel, MICE, Congress, consulting, Savings Scan, SmartFees, Wondermiles pages (content entry) | 8 |
| Congress CPT, taxonomies, fields, past-event rule, listing/detail, filters | 14 |
| GM&E private fields, capabilities, approval workflow, roles, MFA, log | 10 |
| CSV importer + dedup | 11 |
| Forms (5), Turnstile, routing, acknowledgement email, enquiry CPT back-office, CSV export, no PII in URLs | 12 |
| SEO, 301 map, Polylang setup (hreflang ready) | 7 |
| Complianz/CNIL, analytics consent | 3 |
| A11y + CWV pass, T01–T15 acceptance tests | 10 |
| Handover docs + 2h training | 6 |
| Demo (Playground) | 7 |
| **Total** | **~112h** |
At €3,000 that is **≈ €27/h**, about 5x below the Paris freelance rate (~€520/day ≈ €65–75/h; see market_pricing_paris_2026.md). Viable only if scope is cut or the work is treated as a loss leader. A realistic market price is €7–9k.
Block theme over classic: native editing for Veena, no builder, best CWV/a11y. Use a classic/hybrid theme only if the concept's bespoke layouts fight theme.json.

## 8. Maintenance (TMA)
France WP maintenance offers commonly run €50–150/mo for basic updates+backups, and €200–500/mo with SLA/support hours (U; extend with the agency rows in market_pricing_paris_2026.md). "No mandatory contract" means the client owns patching. The contract must state this in writing: after the warranty period (propose 30 days of bug fixes), security updates, plugin vulnerabilities and backups checks are the client's responsibility, and an unpatched site voids the warranty.
Optional care plan: **Essentiel €69/mo** (monthly updates, uptime monitor, backup check, canary leak test) and **Pro €149/mo** (weekly updates, 1h of changes, 2 business-day response). Ad hoc rate €70/h excl. VAT, billed in 15-min increments; urgent work +50%.

## 9. Accessibility & CWV
Achievable: WCAG 2.2 AA on a custom block theme; LCP < 2.5s, INP < 200ms, CLS < 0.1 on o2switch + LiteSpeed + Cloudflare. Avoid: Elementor/Divi (DOM bloat, a11y debt), slider plugins, unthrottled third-party scripts, icon fonts. Tools: axe DevTools / pa11y-ci, WAVE, Lighthouse/PageSpeed Insights, CrUX, keyboard and NVDA/VoiceOver manual passes (T11).

## Red flags
1. €3,000 for ~112h is far below market; the risk is scope creep on the CRM, GM&E and importer.
2. The GM&E leak surface grows with every plugin, so the canary test is mandatory.
3. WXR export leaks meta by default; the filter must ship with the build.
4. Without a mandatory contract, the security of the plugin ecosystem falls on the client, and this must be in writing.
5. Most hosting/plugin prices are U, so re-verify before the quote.
