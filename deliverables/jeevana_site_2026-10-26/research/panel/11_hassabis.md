# Panel lens 11 — Hassabis (systems & long horizon)

**Verdict: PASS for v1, but the loop does not compound yet.** The bottom of the funnel is captured (KV records); the top and middle are not, so no measurement can feed a decision.

## Findings
1. Bottom is solid: `/api/register` stores `reg:*` (name, email, phone, class, level, lang, source_url, ts); `/api/subscribe` stores `news:<sha256>` with `source` + `source_url`. `/api/export` gives CSV. Counts by lang/class/source come for free.
2. Top is blind: no GSC verification tag, no analytics beacon. CSP is `script-src 'self'; connect-src 'self'`, so nothing third-party loads.
3. Mid is blind: `js/main.js` sends only form POSTs; no event beacon for cover completion, deck opens, register starts or WhatsApp/Instagram taps.
4. Instagram is the main acquisition channel, but the bio link has no UTM, so IG traffic looks the same as direct. `source_url` would carry `?utm_source=ig` once the bio link includes it.
5. SEO groundwork is in place: JSON-LD `ExerciseGym` with `sameAs` Instagram, OG tags, sitemap. hreflang en/fr both point to the same URL, which is fine for a single-URL i18n site but weak for FR SEO later.
6. Jitendra precedent (`/dashboard`, GSC+GBP cron, WhatsApp beacon, reviews KV): copy the shape at smaller scale.

## Minimal metric set
| Metric | Source | Built today? | Next step |
|---|---|---|---|
| Impressions / clicks / queries | Search Console | No | Domain or HTML-tag verification; submit sitemap |
| Visits, referrers (IG) | CF Web Analytics | No | Add it (cookieless, served by CF; CSP needs `static.cloudflareinsights.com` + `cloudflareinsights.com` connect) |
| IG-attributed visits | UTM in `source_url` | Partial | Bio link `?utm_source=instagram&utm_medium=bio` |
| Cover completion, deck opens | first-party `/api/e` → KV counters | No | 20-line beacon, counters only, no PII |
| Register starts | same beacon | No | Fire on first focus |
| Registrations | KV `reg:*` | Yes | Show on dashboard |
| Newsletter opt-ins | KV `news:*` | Yes | Show on dashboard |
| WhatsApp / IG taps | same beacon | No | `sendBeacon` on click |
| Reviews count / rating | GBP | No (no GBP) | Create a GBP listing once there is a studio address |

## 12-month shape
- Month 1: custom domain, GSC verification, CF analytics, beacon, UTM bio link, then a password-protected `/dashboard` reading KV.
- Months 2-4: timetable slot gets real data; workshop pages each with an `Event` JSON-LD; monthly newsletter, with opt-in → registration conversion tracked.
- Months 4-12: reviews block fed by GBP sync (Jitendra cron pattern); FR URLs (`/fr/`) with proper hreflang; FR keyword pages ("cours de yoga Paris 11e"). Loop: queries with impressions but no clicks → rewrite copy; workshops that fill → run more.

## Honest gaps
- I did not run the build or confirm that KV `source_url` keeps query strings end to end.
- I have not checked whether CF Web Analytics would be acceptable under the CSP the operator approved.
