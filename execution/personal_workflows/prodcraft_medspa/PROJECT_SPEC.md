# ProdCraft — "0.5 Website" Lead-Gen Pipeline (Med Spas, US Midwest)

Project spec for Claude Code. Manual-outreach variant: no sequencer, no Instantly, one real inbox.

---

## 0. One-paragraph brief

Find every independent med spa in one Midwest metro via Google Places API, audit each website, score it 0–100 for "outdated / can't convert bookings", auto-generate a private templated preview site ("the 0.5") for the worst-scoring ones, and hand-send personalized emails offering to finish the site end-to-end ("0.5 → 1"). Source of truth is Supabase. Outreach is manual from an aged Google Workspace inbox at 10–20 emails/day. Validate with 5 hand-built previews before automating anything.

---

## 1. Decisions already made (do not re-litigate)

| Decision | Value | Why |
|---|---|---|
| Niche | Medical spas / aesthetic clinics (incl. laser hair removal) | Scored 86/100 vs cosmetic dentistry 80. $536 avg visit, $8,700 3-yr LTV, only ~22% of bookings online, 81–94% single-location owner-operated. |
| First geo | Chicago North Shore suburbs (Winnetka, Glencoe, Highland Park, Lake Forest, Northbrook, Evanston) | Highest density (1,103 med spas Chicago metro), affluent cash-pay clientele. |
| Next metros (in order) | Minneapolis–St. Paul (Edina/Wayzata) → Columbus (Dublin/New Albany) → Detroit (Birmingham/Bloomfield) → Indianapolis (Carmel) → KC → St. Louis → Cleveland → Cincinnati → Milwaukee | Tiered by independent med spa count + metro affluence. |
| Outreach mode | Manual, one aged Workspace inbox, 10–20/day, 4 touches | Personalization is the throttle; asset quality drives reply rate. |
| Preview link in email 1 | Allowed (one link, own domain) | Manual sends from an aged inbox don't carry sequencer-scale link penalties. |
| Source of truth | Supabase (Postgres) | Relational: business ↔ audit ↔ preview ↔ outreach ↔ deal. Sheets is a read-only mirror. |
| Preview stack | Next.js + Tailwind template repo, JSON per business, Cloudflare Pages, `{slug}.preview.prodcraft.fyi`, 30-day auto-expiry, noindex | Zero marginal cost, deterministic, you own the code. |
| Brand assets in unsolicited previews | Stock imagery + their public business text + watermark. Real logo/photos only after they reply. | Copyright/trademark/Google ToS exposure. |
| Offer | Growth tier: $4,500 setup (50% to start, 50% at go-live) + $199/mo care plan. 60-day booking-rate guarantee on the second 50%. | Hormozi: collapses risk and time-to-value. |
| Qualify-to-build threshold | Audit score ≥ 45 | Below that the site is fine; don't waste a build or insult them. |

---

## 2. Target numbers (manual mode)

Manual volume: ~200–400 sends/month. Funnel needed for 5 closes/month:

| Stage | Rate | Count |
|---|---|---|
| Sends (all touches) | — | ~300 |
| Unique prospects touched | ~4 touches each | ~75–100 |
| Replies | 15–20% of prospects | 12–20 |
| Calls booked | 50% of replies | 6–10 |
| Closes | 50% of calls | 3–5 |

Implication: every prospect must be score ≥45, owner-named, email-verified, with a real preview. No spray.

Expected reply-rate benchmarks for reference: platform average 3.4% (Instantly 2026); web-audit outreach 4–6% (Puzzle Inbox); "concrete gap named" 15–20% top-decile (B2BLeadFinder). Follow-ups produce 42% of all replies (Instantly 2026) — manual senders skip them; the pipeline must not let you.

---

## 3. Phases

### Phase 0 — Validation (manual, no pipeline code beyond discovery)
1. Run discovery for North Shore Chicago only.
2. Audit by hand (or with the minimal audit script) → pick top 5 by score with findable owner name.
3. Hand-build 5 previews from the template.
4. Send 5 emails, follow up 3× each over 12 days.
5. Gate: ≥1 call booked from 5 → proceed to Phase 1. 0 calls → rewrite email/offer, retry with 5 new prospects before writing more code.

### Phase 1 — Automate discovery → audit → enrich → preview
Everything in §4–§7. Human reviews each preview before it's linked.

### Phase 2 — Daily manual outreach loop
`outreach` table drives a daily queue. See §8.

### Phase 3 — Fulfil, prove, retain
Contract → baseline booking rate → 0.5→1 build → go-live → 60-day proof → $199/mo.

### Phase 4 — Next metro
Re-run Phase 1 for the next suburb cluster only after ≥3 paid clients in the current one.

---

## 4. Discovery — Google Places API (New)

- Endpoint: Text Search (New). Query: `"med spa"`, `"medical spa"`, `"laser hair removal"`, `"aesthetic clinic"`, `"botox"` per tile. Dedupe on `place_id`.
- 60-result cap per query → tile each metro: ~3 km radius circles over the target suburbs (~10–30 tiles). Use `locationBias` circle per tile.
- Field mask (billed at highest SKU touched — keep it tight, Enterprise ~$35/1k):
  `places.id,places.displayName,places.formattedAddress,places.location,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.regularOpeningHours,places.businessStatus,places.primaryType`
- Exclusions: chains (Ideal Image, LaserAway, Milan Laser, European Wax, Skin Laundry, Sono Bello, Athenix, Elase, etc.) via name-match list; `businessStatus != OPERATIONAL`; `userRatingCount < 10` (too small to pay).
- Pricing (2026): 5,000 free Text Search Pro/mo; Enterprise fields $35–40/1k. One metro ≈ a few dollars.
- Fallback for bulk photos/emails only: Apify Google Maps scraper ($1.50–11/1k) or Outscraper ($3–14/1k). ToS risk — internal use only.

Output → `businesses`.

---

## 5. Website audit

### 5.1 Steps per URL
1. Fetch HTML (follow redirects, record final URL, SSL validity).
2. PageSpeed Insights API, mobile + desktop. Free, 25k/day, throttle to ≤100 req/100s.
3. Tech detection: Apify Wappalyzer actor (~$0.0002–0.0005/site) or local Wappalyzer fingerprints. Capture builder (Wix/Squarespace/GoDaddy/Webflow/WordPress + theme), jQuery, GA4/GTM/Meta Pixel.
4. Booking-widget detection: grep HTML + network requests for `vagaro`, `mindbody`, `boulevard`/`blvd.co`, `zenoti`, `acuityscheduling`, `calendly`, `squareup.com/appointments`, `aesthetic record`, `patientnow`, `moxie`.
5. Above-the-fold CTA check: any "Book", "Schedule", "Consult" link/button in first viewport (Playwright, 390×844 viewport).
6. Footer copyright year regex.
7. Playwright screenshots: mobile full-page + desktop hero → R2/Supabase Storage.
8. Claude vision pass on screenshots → `vision_dated_score` 0–10 with one-sentence rationale (prompt in `/prompts/vision_audit.md`).

### 5.2 Scoring rubric (0–100, higher = worse site = better prospect)

| Signal | Points | Fail condition |
|---|---|---|
| No online booking widget | 22 | none of §5.1 step 4 detected |
| Not mobile-friendly | 15 | no `<meta viewport>` or Lighthouse mobile-friendly audit fails |
| Poor performance | 15 (10 if 50–70) | PSI mobile performance < 50 |
| Dated design | 15 | vision score ≥ 7 |
| No above-fold CTA | 10 | §5.1 step 5 fails |
| No valid SSL | 8 | http only or cert invalid |
| Builder/theme age | 8 | Wix/GoDaddy builder OR WordPress theme released pre-2018 OR jQuery <3 |
| No analytics/pixel | 4 | no GA4/GTM/Meta Pixel |
| Stale footer year | 3 | year ≤ current − 2 |
| No website at all | 100 | `websiteUri` null or 4xx/5xx — top prospect |

Buckets: ≥45 qualified (build preview) · 25–44 borderline (email audit only, no build) · <25 skip.

### 5.3 Empirical prevalence
Before outreach in a new metro, run audit-only on a random 40–50 sample and record `% ≥45`. Report it in `metro_stats`. Replaces the 40% assumption.

Output → `audits`.

---

## 6. Enrichment — owner name + verified email

Order of operations (stop at first hit):
1. Site contact/about page scrape → owner/founder name, personal email.
2. Google Business Profile "owner" mentions in reviews/replies.
3. State business registry (IL SOS, MN SOS, OH SOS, MI LARA, IN INBiz) → registered agent / member name.
4. Apollo.io (already licensed) → person + email.
5. Findymail ($49/mo, pays only on verified finds) or Hunter ($49/mo) → email by name+domain.
6. Fallback: `info@` / `hello@` with owner first name in the body.

Verification: MillionVerifier (~$39/10k, or EverClean $15/mo). Only `deliverable` status gets emailed. Target bounce < 2% — this is your primary domain, protect it.

Output → `businesses.owner_name, owner_email, email_status, email_source`.

---

## 7. Preview site generation

- Repo: `prodcraft-medspa-template` (Next.js 15 App Router, Tailwind, one route, static export).
- Input: `business.json` → `{ name, city, phone, address, hours, services[], rating, review_count, tagline, primary_color }`. Services inferred from site text + Google `primaryType` via Claude (prompt in `/prompts/extract_services.md`).
- Content rules (legal):
  - Stock/placeholder hero + service imagery (licensed set in repo). No scraped photos, no logo, no staff/patient images.
  - Business name in plain type only. No logo reproduction.
  - Reviews: show rating + count and link out to Google. Do not copy review text.
  - Watermark bar, every page: "Concept preview by ProdCraft — not affiliated with or endorsed by {name}. Remove: reply 'remove'."
  - `<meta name="robots" content="noindex,nofollow">`, `robots.txt` disallow all, unguessable slug suffix.
  - No medical claims. Service descriptions are generic ("Botox — schedule a consultation").
- Booking: embed a live demo booking widget (e.g., Calendly demo or a Boulevard-styled mock) so the "book at 11pm" pitch is visible.
- Deploy: Cloudflare Pages project per preview, `{slug}-{6char}.preview.prodcraft.fyi`. Store URL in `previews`.
- Expiry: cron Worker daily; `expires_at` = deploy + 30d → redirect to `/expired` ("Reply to reactivate"). Extend on reply.
- Takedown: `previews.takedown = true` → unpublish within 1 hour. Honor every request.
- Human gate: `previews.status = 'review'` until you approve in the dashboard; only `approved` previews get emailed.

---

## 8. Manual outreach loop

### 8.1 Daily queue
Query: `outreach` rows where `next_touch_at <= today AND status IN ('queued','sent')`, ordered by audit score desc, cap 20. Dashboard shows: business, owner, preview URL, screenshot of their current site, the specific gap(s), draft email. You edit and send from Gmail (Gmail connector can create drafts, never auto-send). On send, mark `sent_at`, set `next_touch_at`.

### 8.2 Touch plan (per prospect)

| Touch | Day | Content | Link |
|---|---|---|---|
| 1 | 0 | Specific gap + preview link + one question | 1 (preview) |
| 2 | 3 | 60–90s Loom walkthrough of the preview | 1 (Loom) |
| 3 | 7 | Proof line (once you have one) + "15 min this week?" | 0 |
| 4 | 12 | Breakup: "taking the concept down Friday" | 0 |

No touch 3/4 template until you have at least one real result to cite; use audit-stat proof instead ("78% of med spa bookings still come by phone").

### 8.3 Email 1 draft (generated per prospect, you edit)
Subject: `quick question about {name}'s booking`

> Hi {owner_first},
>
> I was looking at {name} and noticed clients can't book online without calling — {gap_2}. Most people won't call after hours, and about 78% of med spa bookings still come in by phone.
>
> I put together a book-online-first concept of your homepage to show what I mean: {preview_url}
>
> It's a starting point. If you like the direction, I finish it end to end with your branding and booking system, and you don't pay the balance until it's live. Worth a look?
>
> {signature, physical address, "reply 'no' and I won't follow up"}

Rules: never say their site is bad; talk about lost bookings. One link. CAN-SPAM: real From, honest subject, physical postal address, honor opt-out globally (`businesses.do_not_contact = true`).

### 8.4 Reply handling
Positive → book call (Calendly), status `call_booked`. "Remove" → takedown + DNC. No reply after touch 4 → `closed_lost`, preview expires.

---

## 9. Offer & sales call script

Tiers: Starter $2,500 + $99/mo · **Growth $4,500 + $199/mo (default)** · Premium $8,000 + $299/mo.

Call script core:
> "You've seen the preview. I'll finish it with your branding and hook up online booking so clients can book at 11pm. $2,250 to start, nothing more until it's live and you've signed off. If online bookings don't beat where you are today within 60 days, you don't owe the other $2,250. After that it's $199/month to keep it fast and converting."

Onboarding must capture: current booking tool, baseline online-booking count (last 30 days), services list, brand assets (now licensed to use), medical-director approval of copy.

---

## 10. Data model (Supabase)

```sql
businesses(id, place_id unique, name, slug, address, city, suburb, metro, state, lat, lng,
  phone, website_url, final_url, rating, review_count, primary_type, is_chain bool,
  owner_name, owner_email, email_status, email_source, do_not_contact bool default false,
  created_at, updated_at)

audits(id, business_id, audited_at, psi_mobile int, psi_desktop int, has_ssl bool,
  is_mobile_friendly bool, builder text, theme text, theme_year int, has_jquery_legacy bool,
  booking_widget text, has_cta_above_fold bool, has_analytics bool, footer_year int,
  vision_dated_score int, vision_rationale text, total_score int, bucket text,
  screenshot_mobile_url, screenshot_desktop_url, raw jsonb)

previews(id, business_id, template_id, subdomain_url, status text, -- review|approved|live|expired|takedown
  deployed_at, expires_at, takedown bool default false, content jsonb)

outreach(id, business_id, touch int, status text, -- queued|sent|replied|call_booked|closed_won|closed_lost|dnc
  draft_subject, draft_body, sent_at, replied_at, reply_sentiment text,
  next_touch_at date, notes text)

deals(id, business_id, tier, setup_price, mrr, contract_signed_at, baseline_online_bookings_30d int,
  live_at, bookings_60d int, guarantee_met bool, care_plan_active bool)

metro_stats(metro, sampled int, pct_qualified numeric, measured_at)
```

Sheets mirror: read-only view `v_pipeline` synced daily.

---

## 11. Repo layout

```
prodcraft-medspa-pipeline/
  apps/
    dashboard/        # Next.js: daily queue, preview approval, screenshots, draft editor
    template/         # the 0.5 site template (static export)
  packages/
    discovery/        # Places API tiling + dedupe + chain filter
    audit/            # PSI, tech detect, booking grep, Playwright, vision scoring
    enrich/           # registry lookups, Apollo, Findymail/Hunter, MillionVerifier
    preview/          # business.json → build → CF Pages deploy → expiry cron
    outreach/         # queue, draft generation, Gmail draft creation, status updates
    db/               # Supabase schema, migrations, typed client
  prompts/
    vision_audit.md
    extract_services.md
    email_touch_1.md .. email_touch_4.md
  scripts/
    run_metro.ts      # discovery → audit → enrich for one metro
    sample_audit.ts   # 40–50 random sample → metro_stats
    daily_queue.ts
```

---

## 12. Monthly tool cost (manual mode, ~100 new prospects/month)

| Item | $/mo |
|---|---|
| Places API | ~5 |
| Apify tech-detect | ~1 |
| PSI | 0 |
| Claude (vision + drafts) | ~15 |
| MillionVerifier EverClean | 15 |
| Findymail or Hunter | 49 |
| Cloudflare Pages/Workers/R2 | ~5 |
| Supabase | 0–25 |
| Loom | 0–15 |
| **Total** | **~$90–130** |

Apollo already licensed. No Instantly, no extra domains, no warmup.

---

## 13. Build order for Claude Code

1. `db/` schema + migrations. Seed chain-exclusion list.
2. `discovery/` for one suburb cluster; verify counts against a manual Google Maps check.
3. `audit/` minimal: SSL, viewport, PSI, booking grep, footer year, screenshots. Add vision + tech-detect after.
4. `scripts/sample_audit.ts` → first `metro_stats` row.
5. `template/` with `business.json` contract; deploy one by hand.
6. `enrich/` with the 6-step waterfall + verification.
7. `preview/` deploy + expiry cron + takedown.
8. `dashboard/` daily queue + approval + Gmail draft creation.
9. `outreach/` drafts from prompts, status machine, follow-up scheduling.
10. `deals` + 60-day proof tracking.

Phase 0 (5 hand-built previews, 5 emails) runs after step 5. Do not build steps 6–10 until Phase 0 gate passes.

---

## 14. Known unknowns — measure, don't assume

- % of med spas with score ≥45 per metro → `sample_audit.ts`.
- Real reply rate of the built-asset email in manual mode → first 20 prospects.
- Owner-name find rate via registry vs Apollo → log `email_source`.
- Whether `info@` replies materially worse than named inboxes for single-location spas → tag and compare.
- Midwest agency density per capita vs coasts → count Clutch/UpCity per metro if it ever matters for pricing.
- Directory med spa counts disagree up to 4× (Orbital vs medicalspalocator); trust your own Places pull.

---

## 15. Later phases (stub)
Canada → UK → France (GDPR legitimate-interest + source disclosure) → Australia → UAE/KSA → Singapore/Korea/HK/Mexico. Each: re-check cold-email law, med spa ownership rules, currency-adjusted pricing, directory sources.
