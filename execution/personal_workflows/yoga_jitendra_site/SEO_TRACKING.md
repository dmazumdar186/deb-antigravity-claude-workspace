# SEO_TRACKING — yogaavecjitendra.fr

Baseline log for the v2.0 SEO project. Weekly snapshots + dropped-term log + Rich Results Test results all land here.

---

## Jitendra's WhatsApp answers (2026-07-11)

| Q | Answer | Plan impact |
|---|---|---|
| 1. Address privacy | **Option A** — keep `22 rue Eugène Manuel 75016 Paris` public everywhere | No schema redaction. Base.astro schema stays with full `streetAddress`. Simplest path. |
| 2. RYT / Yoga Alliance | In-process; has yoga insurance | **Skip Yoga Alliance** for now. Revisit when RYT lands. |
| 3. Review distribution | No Google reviews yet; has reviews on Meetup + Instagram + TrainMe + email; willing to distribute cards | **YES — Track 3a review-generation infra worth building.** QR cards + WhatsApp templates all in. |
| 4. Old website / properties | Yes — see below. | Two additional assets discovered. |

## Existing web assets discovered

1. **Google Sites page:** https://sites.google.com/view/yogaavecjitendra/home
   - Content: FR positioning ("Hatha Yoga privé & petit groupe · Respiration • Mouvement • Relaxation"), 500h Tapovan, home/studio/corporate offerings.
   - Contact: same phone/email/address as main site.
   - Outbound links present: Calendly (`calendly.com/yogaavecjitendra/15min`), Instagram, YouTube, LinkedIn, Facebook, L'Hebdo du Vendredi press article.
   - Media: logo, press-preview image, workshop image. No embedded videos.
   - **Action Phase 1:** Add `<link rel="canonical">` from the Google Sites page pointing at `yogaavecjitendra.fr` if editable (Debanjan-side) — else consider 301 via a Google Sites redirect setting. Include the Google Sites URL as `sameAs` in Base.astro schema alongside existing socials so Google graphs them.
   - **Action Phase 3:** Add the L'Hebdo du Vendredi press link to the on-site `Press.astro` component if not already there.

2. **Google Maps listing:** https://maps.app.goo.gl/LFy4eJncWWdt69Lo9?g_st=ic
   - CID: `0xc39304b7fc72d34b` (embedded in the URL — Google's internal business ID).
   - **State: CLAIMED BY JITENDRA ALREADY** (confirmed by Debanjan 2026-07-11).
   - **Plan impact: HUGE.** Track 3b collapses from ~22 min Jitendra work (create profile + 30-sec video + add manager) → ~2 min (accept Manager invite email). No video verification needed — Google already verified Jitendra.
   - **Revised Track 3b flow:** Debanjan → GBP dashboard → "Add Manager" → sends invite email to Jitendra → Jitendra clicks accept → Debanjan then enriches the existing profile with:
     - Correct name / spelling
     - Categories: `Yoga instructor` (primary) + `Yoga studio` (secondary)
     - FR + EN long descriptions (Debanjan drafts, matches site voice)
     - Service areas: Paris 1-20 + Boulogne / Neuilly / Levallois / Issy / Saint-Cloud
     - Hours (from `schedule.fr.json`)
     - Website URL = yogaavecjitendra.fr (currently maybe pointing to Google Sites?)
     - Photos: already-on-site meditation-portrait + portrait-namaste + hero backdrop + Champ-de-Mars + studio interior
     - `sameAs` / linked profiles: Instagram, Meetup, Superprof, GIO France, L'Hebdo du Vendredi press link
   - **Total revised Jitendra ask across whole SEO project: ~7 min** (Touch 1 batched Qs already delivered ~5 min + accept Manager invite ~2 min) + optional ~30 min Phase-2 review if he wants.

## Touch 2 — GBP Manager access (2026-07-11)

- Jitendra sent Manager invite → Debanjan (`debolshop@gmail.com`) accepted. **DONE.**
- Enrichment cheat-sheet drafted at `GBP_ENRICHMENT_CHEATSHEET.md` (13 sections).
- **GBP enrichment DONE by Debanjan same-day (sections 1–11, 13).**

### Findings during enrichment

- **Q&A section not available** on this listing (Google rolled it back for many SAB categories in 2026). Section 12 skipped by design. Substitute: 2 seeded GBP Posts (see below).
- **Site is already indexed** — Google search for `yoga avec jitendra Paris 16` returned `yogaavecjitendra.fr` as #1 organic result with "2 days ago" crawl date. GSC verification not yet run but Google is crawling.
- **Superprof profile surfaces in the SERP** with `40€/h · 5.0 ★ (2 avis)` — this is the **concrete data source for `Review` + `AggregateRating` schema deferred to Phase 3**. Two verified 5.0-star reviews at a real market price. When Debanjan builds the schema block, source from this URL: `https://www.superprof.fr/hatha-yoga-paris-experience-personnalisee-studio-prive-passy-domicile.html`.
- **MeetUp event indexed:** Sunday 2026-07-26 19:00, Paris 16, "Première séance offerte. Tarifs 20 €/pers." Used as content for seeded GBP Post #1.
- **Instagram @jitendrakuma:** 1.1K+ followers, 405 posts — worth adding as `sameAs` in Base.astro schema if not already, and considering as a backlink target during Phase 4.
- **Knowledge panel absent** from that specific SERP — normal when the domain result dominates; try re-checking after Post #1 goes live and the profile matures.

### Seeded GBP Posts (Debanjan drafted 2026-07-11)

### Corporate client logos (2026-07-11, Jitendra authorized)

3 SVG logos sourced + wired into Hero.astro:
- `totalenergies.svg` (3.7 KB) — from Wikimedia Commons (`TotalEnergies_wordmark_(2021-present).svg`)
- `semmaris-rungis.svg` (5.9 KB) — from Wikimedia Commons (`Logo_Marché_International_de_Rungis.svg`)
- `emmaus-solidarite.svg` (68 KB) — from Emmaüs Solidarité's own live site (`emmaus-solidarite.org/themes/custom/emmaus/logo.svg`); no Commons SVG existed for this specific chapter, so used their real production logo

Styling: monochrome + desaturated (grayscale + 0.6 opacity), 32 px height, subtle hover restore. Fits cream/terracotta/sage palette; doesn't hijack visual hierarchy. Redeployed to preview: https://0f24b90b.yoga-jitendra.pages.dev/

Post 1 — "What's new" — outdoor Hatha Yoga sessions at Champ-de-Mars / Bois de Boulogne, **ad-hoc dates announced on MeetUp** (corrected 2026-07-11 after Debanjan flagged "not daily/weekly"). FR body ready, photo = `champ-de-mars-eiffel.jpg`, CTA = "Learn more" → MeetUp group URL.

**Downstream plan impact:** the `/plein-air` page in Phase 2 was slated to include `Event` schema for a "recurring weekly slot." Since the sessions are actually ad-hoc, drop the `recurring` framing. Options for the schema:
- (a) Ship a single upcoming `Event` per Meetup announcement, refresh when a new one is announced.
- (b) Skip `Event` schema on `/plein-air`; instead frame the page as "outdoor sessions announced on MeetUp" with a link to the MeetUp group. Simpler, no staleness risk.
Recommend (b) — €0 maintenance, no risk of stale event data showing in SERP.

Post 2 — "Offer" — bilingual corporate + at-home (FR body ready, photo = `teaching-backbend.jpg`, CTA = "Book" → calendly.com/yogaavecjitendra/15min).

## GSC state (2026-07-11)

- Property TYPE: **Domain** (`sc-domain:yogaavecjitendra.fr`) — covers apex + www + all subdomains + both protocols
- Verified: **YES** (pre-existing; Debanjan didn't need to run verification manually)
- Sitemap submission: **DONE 2026-07-11** — `https://yogaavecjitendra.fr/sitemap-index.xml` accepted after production deploy
- Data population: expect 1-3 days for index coverage report; 2-4 weeks for meaningful query/impression data

## Production deploy (2026-07-11)

- Merged `seo-v2-i18n-restructure` → `main` (commit `5470adc`)
- Deployed via `wrangler pages deploy dist --project-name=yoga-jitendra --branch=main`
- Direct URL of the prod deployment: `https://589b76f2.yoga-jitendra.pages.dev`
- Live at `yogaavecjitendra.fr` — verified: new i18n build, `<title>` = "Hatha Yoga traditionnel indien à Paris — Yoga avec Jitendra", `/en/` route serves EN content with `lang="en"`, zero `data-lang-content` leftover, zero cross-language leak, corporate logo strip rendered, sitemap serves valid XML
- Rollback path: `git revert 5470adc && git push` + one CF Pages redeploy (~2 min) returns to old single-URL state

## Ahrefs Site Audit (2026-07-11) — first crawl

**Health Score 86 / Good** — 42 URLs crawled, 8 errors, 8 warnings, 8 notices.

Site Audit set up via Free (Webmaster Tools) tier. Weekly re-crawl scheduled. GSC Insights integration deferred until GSC has populated data (~3-5 days).

### Fixes applied same-day (commit follows)

| Issue | Count | Fix | File(s) |
|---|---|---|---|
| 404 page / 4XX page | 2 each | Removed `mailto:` from Contact — CF Scrape Shield was rewriting to `/cdn-cgi/l/email-protection` which 404'd to crawlers. Email now rendered as plain copyable text via `<span>`. | `Contact.astro`, `contact.{fr,en}.json` |
| Page has links to broken page | 2 | Auto-clears once mailto: removed | (same) |
| Meta description too short | 2 | Extended `/merci` (52→156 chars) + `/en/thanks` (52→143 chars) | `merci.astro`, `en/thanks.astro` |
| Low word count | 2 | Added `noindex` prop to Base.astro + applied to `/merci` + `/en/thanks` — these are post-conversion pages, no SEO value, shouldn't appear in SERP anyway | `Base.astro`, `merci.astro`, `en/thanks.astro` |
| Image file size too large | 2 | `studio-passy.jpg` 2.27 MB → 132 KB (single-pass PIL: 3840×5120 → 600×800, JPEG q80). Same file counted twice (www + non-www variants). | `public/assets/images/studio-passy.jpg` |

**Expected next-crawl improvement:** Errors 8 → 4, Warnings 8 → 4, Health Score 86 → ~92-95.

### Deferred / not touching

- **www vs apex duplication** (Ahrefs sees both `https://www.yogaavecjitendra.fr/*` and `https://yogaavecjitendra.fr/*` as separate pages, hence every issue count is doubled). Fix requires a Cloudflare Redirect Rule (`www` → apex, 301). Owed but non-urgent — canonical tags already point at apex, so Google won't index the www duplicates even if Ahrefs counts them.
- **Pages to submit to IndexNow (4)** — Free-tier feature nag. Skip.
- **Page has only one dofollow incoming internal link (2)** — Applies to `/merci` + `/en/thanks`. By design; now noindexed so moot.

## Phase 1 step 0 — Demand-verification pass (2026-07-11)

_In progress — dropped terms logged below as they're checked._

## Weekly GSC snapshots

_Populated weekly starting once GSC verification lands. Format:_
```
### YYYY-MM-DD (week N)
- Impressions: N (Δ from last week)
- Clicks: N (CTR: %)
- Avg position: N
- Top 5 queries by impressions:
- Top 5 queries by clicks:
- Winnable-wedge query status: N of 10 impressing
- Conversion (WhatsApp UTM clicks / /merci pageviews): N
```

## Rich Results Test log

_Populated at Phase 1 step 12._

## Citation-platform address-field check log (Phase 3 Track 3a)

_Populated at Phase 3 kickoff._

---

## Dashboard delivery log

### 2026-07-19 (day 8 since launch): V0.01+ delivered AND DEPLOYED

Naming note: called V0.01 in the DASHBOARD_HANDOFF sequence, but the monthly self-report form (originally scoped for V0.5) was pulled forward into this drop per the 2026-07-19 war-room plan. Effective scope is V0.01 + self-report.

**Live URL:** https://yogaavecjitendra.fr/dashboard/ (also `https://yoga-jitendra.pages.dev/dashboard/`)
**Preview URL of first deploy:** https://464bf385.yoga-jitendra.pages.dev/
**Auth:** HTTP Basic (interim stopgap for Cloudflare Access). User: `debanjan`. Password lives in the operator's local scratchpad file and as a `DASHBOARD_PASS` secret on the Pages project.

**Front-door synthetic — LIVE-PROBATIONARY day 1 of 5**

| Probe | Result | Timestamp (Paris) |
|---|---|---|
| `GET /` (homepage, public) | HTTP 200 | 2026-07-19 15:52 |
| `GET /dashboard/` unauth | HTTP 401 + `WWW-Authenticate: Basic realm="Yoga avec Jitendra Dashboard"` | 2026-07-19 15:52 |
| `GET /dashboard/` with correct auth | HTTP 200, 18 278 bytes, all 7 body markers present | 2026-07-19 15:52 |
| `GET /api/self-report` unauth | HTTP 401 | 2026-07-19 15:52 |
| `GET /api/self-report` with auth | HTTP 200 `{"history":[]}` (KV binding LIVE, empty namespace) | 2026-07-19 15:52 |

Day 2/5 through day 5/5: re-run this probe stack daily; log below.

- Day 2 / 5: —
- Day 3 / 5: —
- Day 4 / 5: —
- Day 5 / 5: — dashboard is then LIVE per workspace front-door rule.

**Owed for V0.02:**
- Cloudflare Web Analytics site token → `PUBLIC_CF_WA_TOKEN` env var on Pages project (unblocks "Conversation" hero tile + funnel WhatsApp-taps row).
- Replace HTTP Basic Auth with Cloudflare Access when a token with Zero Trust scope is available.
- POST-then-refresh dogfood test (submit one self-report, verify tile rehydrates) — Cherny lens verdict from the audit stack.

Internal dashboard live at `/dashboard/` (English-only, behind Cloudflare Access).

- Preconditions shipped: Cloudflare Web Analytics installed in `Base.astro` (gated behind `PUBLIC_CF_WA_TOKEN` env var); missing UTM tag on `Contact.astro:9` fixed to `utm_content=contact_${lang}`.
- Six components: HeroTile, FunnelStrip, MilestoneStrip, NextMoveCard, SelfReportTile, ProvenanceFooter.
- Single source of truth: `src/content/dashboard-data.json` (hand-edited weekly until V0.1 automation).
- Monthly self-report form at `/dashboard/self-report/` with a Cloudflare Pages Function (`functions/api/self-report.ts`) persisting to a KV namespace named `DASHBOARD_KV`.
- Manual owner steps to activate: enable CF Access on the Pages project scoped to `/dashboard/*` and `/api/*`, allowlist debolshop@gmail.com + jitendranitrr13@gmail.com; bind the `DASHBOARD_KV` namespace; set `PUBLIC_CF_WA_TOKEN` env var.
- Rollback: `git revert <sha> && wrangler pages deploy dist` then disable the Access application in the CF dashboard.
