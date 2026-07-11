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

Post 1 — "What's new" — outdoor Hatha Yoga sessions at Champ-de-Mars / Bois de Boulogne, **ad-hoc dates announced on MeetUp** (corrected 2026-07-11 after Debanjan flagged "not daily/weekly"). FR body ready, photo = `champ-de-mars-eiffel.jpg`, CTA = "Learn more" → MeetUp group URL.

**Downstream plan impact:** the `/plein-air` page in Phase 2 was slated to include `Event` schema for a "recurring weekly slot." Since the sessions are actually ad-hoc, drop the `recurring` framing. Options for the schema:
- (a) Ship a single upcoming `Event` per Meetup announcement, refresh when a new one is announced.
- (b) Skip `Event` schema on `/plein-air`; instead frame the page as "outdoor sessions announced on MeetUp" with a link to the MeetUp group. Simpler, no staleness risk.
Recommend (b) — €0 maintenance, no risk of stale event data showing in SERP.

Post 2 — "Offer" — bilingual corporate + at-home (FR body ready, photo = `teaching-backbend.jpg`, CTA = "Book" → calendly.com/yogaavecjitendra/15min).

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
