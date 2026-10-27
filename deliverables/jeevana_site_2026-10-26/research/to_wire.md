# To wire — Jeevana production site v3 (2026-10-26)
Every slot below ships empty or generic-true; nothing was invented.

| slot | where | what ships today |
|---|---|---|
| Biography paragraph | not shown in v3 (chapter 01 describes the practice); add a `ch1.bio` key + `<p data-i18n>` when supplied | — |
| Location | `js/i18n.js` (add to `contact.lead`) | not shown; "Classes in Paris, group and private" |
| Timetable | `js/schedule.json` rows `{id, day 1-7, time, title}` | `[]` → "The timetable opens soon — register your interest" |
| Prices | `js/i18n.js` `price` | "Price on request" |
| Formats beyond group / private (workshops, outdoor) | `class.workshop*` in chapter 02 | Workshop card kept as a format description only |
| Facebook | `js/contact.json` `facebook` | empty → row hidden |
| Custom domain | canonical / og:url / JSON-LD / robots / sitemap; add as 2nd host on the Web Analytics site | `https://jeevana-yoga.pages.dev/` |
| Search Console | DNS TXT once the domain is bound | — |
| Export / stats login | Pages env `EXPORT_USER`, `EXPORT_PASS` | unset → `/api/export`, `/api/stats` return 401 |
| Notification email (Brevo) | `wrangler pages secret put BREVO_API_KEY` (+ optional `NOTIFY_TO`, `NOTIFY_FROM` = verified sender) | unset → registrations/subscriptions logged only; operator: create free Brevo account, verify sender, set the key; check with `wrangler pages secret list` |
| Newsletter sending + unsubscribe link | every newsletter must carry `https://<domain>/api/unsubscribe?t=<unsubscribe_token>` (token in each `news:` record, in the export) | KV list only |
| Visitor confirmation email | after the notification works | — |
| Kling film (final, 11 legs) | `research/film/hero.*` → `node research/stamp.mjs` copies to `site/assets/film/`; re-run figure_boxes.py, prep_assets.py, functional, screens | 5 s stand-in (`standin:true`), scaled to 12 states |
| Instagram bio link | `https://<domain>/?utm_source=instagram&utm_medium=bio` | — |
| Jeevana's written OK | photos, phone, copy (record in HANDOFF.md) before the domain goes live | pending |
| Tapovan training details (years, course) | lineage line in About names the school only (operator 2026-10-27); add years/course once Jeevana confirms | pending |
| Content order (lens 5) | timetable → price → first-class terms → one consented testimonial → arrondissement + reply time | pending |

Wired: contact email Jeevana.yogawellness@gmail.com (operator 2026-10-26; old address removed from site/, asserted); phone / WhatsApp +33 7 54 28 72 10 (Contact row + mobile bar only); KV `JEEVANA_KV` (id in wrangler.toml);
Cloudflare Web Analytics beacon token f7ff1290…bc05; first-party counters `/api/event` (allowlist) + `/api/stats`.
Runbook: `/api/export` pages KV lists; beyond ~1,000 rows per list, export per `?type=news|reg`.

**Email (operator, 2026-10-26, supersedes the brief):** Jeevana.yogawellness@gmail.com — use everywhere (mailto, JSON-LD, privacy page controller contact, NOTIFY_TO default). The earlier Gmail address is retired.

| Superprof price / rating / review count | Contact + About link only | link `https://www.superprof.fr/professeure-yoga-propose-cours-accessibles-niveaux.html`; no figures taken (page not readable from the build session) |
| Individual classes: price, where exactly (home 19e / student's home / online) | Classes card | "Individual classes in Paris · price on request" |
