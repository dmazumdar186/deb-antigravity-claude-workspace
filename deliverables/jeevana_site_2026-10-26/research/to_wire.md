# To wire — Jeevana production site (2026-10-26)
Every slot below ships empty or generic-true; nothing was invented.

| slot | where | what ships today |
|---|---|---|
| Biography paragraph | `js/i18n.js` keys `about.bio` (EN + FR) | generic-true: she teaches yoga in Paris (group, private, workshops, studio + outdoors) |
| Studio address | `js/i18n.js` `about.c3.p` | "address will be published here" |
| Timetable | `js/schedule.json` rows `{id, day 1-7, time, title}` | `[]` -> "Timetable coming — register your interest"; rows also fill the Register class select |
| Prices | `js/i18n.js` `price` | "Price on request" |
| Facebook | `js/contact.json` `facebook` (https URL) | empty -> button hidden, no dead link |
| Custom domain | `index.html` canonical / og:url / og:image / hreflang / JSON-LD, `robots.txt`, `sitemap.xml` | `https://jeevana-yoga.pages.dev/` (Pages project name) |
| KV namespace | `wrangler.toml` | wired: `JEEVANA_KV` = 33c31b00e6e946489c86f55aa63ba3cc (created 2026-10-26) |
| Export credentials | Pages env `EXPORT_USER`, `EXPORT_PASS` | unset -> `/api/export` returns 401 |
| Kling footage | `assets/hero.json` `kling` slot | self-rendered canvas footage (hero.mp4 / hero-m.mp4) |
| Newsletter sending (Brevo or similar, double opt-in) | `functions/api/subscribe.ts` | KV list only; no email is sent |
| More cover photos | `_raw_assets/` + `research/ingest_photos.py --sequence` | all 12 frames real; 05/08, 03/10, 02/11 reuse a photo (the sequence repeats) |

Wired since the brief (operator, 2026-10-26): phone / WhatsApp +33 7 54 28 72 10 (`js/contact.json`, Contact panel, footer, mobile bar).
