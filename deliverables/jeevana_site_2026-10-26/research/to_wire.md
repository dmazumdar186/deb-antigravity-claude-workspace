# To wire — Jeevana production site v2 (2026-10-26)
Every slot below ships empty or generic-true; nothing was invented.

| slot | where | what ships today |
|---|---|---|
| Biography paragraph | `js/i18n.js` `about.bio` (EN + FR) | generic-true: teaches yoga in Paris, group and private |
| Location | `js/i18n.js` `about.c3.p` | "Location shared on registration" |
| Timetable | `js/schedule.json` rows `{id, day 1-7, time, title}` | `[]` → "The timetable opens soon — register your interest" |
| Prices | `js/i18n.js` `price` | "Price on request" |
| Formats beyond group / private (workshops, outdoor) | `about.*`, Classes cards | Workshop card kept as a format description only |
| Facebook | `js/contact.json` `facebook` | empty → row hidden |
| Custom domain | canonical / og:url / JSON-LD / robots / sitemap; add as 2nd host on the Web Analytics site | `https://jeevana-yoga.pages.dev/` |
| Search Console | DNS TXT once the domain is bound | — |
| Export / stats login | Pages env `EXPORT_USER`, `EXPORT_PASS` | unset → `/api/export`, `/api/stats` return 401 |
| Notification email (Brevo) | `wrangler pages secret put BREVO_API_KEY` (+ optional `NOTIFY_TO`, `NOTIFY_FROM` = verified sender) | unset → registrations/subscriptions logged only; operator: create free Brevo account, verify sender, set the key; check with `wrangler pages secret list` |
| Newsletter sending + unsubscribe link | every newsletter must carry `https://<domain>/api/unsubscribe?t=<unsubscribe_token>` (token in each `news:` record, in the export) | KV list only |
| Visitor confirmation email | after the notification works | — |
| Kling film | `assets/film/hero.mp4` (+ `hero-m.mp4`), 3:4, 12 keyframes, 5 s legs; set `ready:true` in `assets/film/hero.json` | dormant; the figure crossfades run |
| Instagram bio link | `https://<domain>/?utm_source=instagram&utm_medium=bio` | — |
| Jeevana's written OK | photos, phone, copy (record in HANDOFF.md) before the domain goes live | pending |
| Content order (lens 5) | timetable → price → first-class terms → one consented testimonial → arrondissement + reply time | pending |

Wired: phone / WhatsApp +33 7 54 28 72 10 (Contact row + mobile bar only); KV `JEEVANA_KV` (id in wrangler.toml);
Cloudflare Web Analytics beacon token f7ff1290…bc05; first-party counters `/api/event` (allowlist) + `/api/stats`.
Runbook: `/api/export` pages KV lists; beyond ~1,000 rows per list, export per `?type=news|reg`.
