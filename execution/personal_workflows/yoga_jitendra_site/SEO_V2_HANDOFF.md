# Yoga avec Jitendra — v2.0 SEO Handoff

**Created:** 2026-07-11 · **For:** the next context window that will plan + implement SEO.
**Project:** `execution/personal_workflows/yoga_jitendra_site/` · **Live:** https://yogaavecjitendra.fr (apex + www), alias `yoga-jitendra.pages.dev`.

---

## THE HANDOFF PROMPT (paste this into a fresh context window)

> You are picking up **v2.0 of the `yoga_jitendra_site` project — the SEO phase.**
> The site is already built, live, and stable at **https://yogaavecjitendra.fr** (Astro + Tailwind, static, deployed to Cloudflare Pages under account `1bd372ca60ff5733565863799237e83b`, project `yoga-jitendra`). Source lives in `execution/personal_workflows/yoga_jitendra_site/`. It is a **bilingual FR/EN** single-page marketing site for Jitendra Kumar, a Hatha Yoga teacher in Paris 16 (Passy) offering studio, at-home, corporate, and outdoor sessions. Read `SEO_V2_HANDOFF.md` in the project root in full before doing anything — it has the current SEO-state audit, the known issues, and the constraints.
>
> **Goal:** when someone in France searches "yoga Paris", "cours de yoga Paris 16", "hatha yoga Passy", "yoga à domicile Paris", "yoga en entreprise Paris", "yoga cours particulier Paris", and the long tail around them, Jitendra's site should rank as high as realistically possible. Local + organic. Budget is **€0/month** (per workspace `model-tier.md` cost-constraint — no paid SEO tools, no paid backlinks; free tiers only: Google Search Console, Google Business Profile, Bing Webmaster, free keyword sources).
>
> **Do NOT start editing yet. Enter plan mode first.** In plan mode:
> 1. **Keyword research** — build the real French + English query set (head + long-tail + local-intent). Use free sources: Google autocomplete, "People also ask", Google Trends, `answerthepublic`-style manual expansion, the competitors' page titles. Score each by rough intent (transactional vs informational) and local specificity. Document the target keyword → target page map.
> 2. **Competitor research** — pull the top 5–10 sites currently ranking for the head terms above (Paris yoga teachers/studios: e.g. Tapovan, Qee, individual Superprof/Malt yoga teachers, studios in the 15e/16e/7e). For each: note their title/H1 patterns, page structure, word count, schema, Google Business Profile presence, review count, backlink sources. Identify the gap Jitendra can win (hyper-local Passy/16e + bilingual + traditional-lineage angle + corporate).
> 3. **Technical SEO audit** — verify/expand the state documented in this file (sitemap, robots, hreflang, canonical, schema, Core Web Vitals via the `web-perf` skill / PageSpeed, mobile, indexability). The bilingual-on-one-URL problem is the headline issue — decide the fix (recommended: split to `/` = FR and `/en/` prerendered routes with correct reciprocal hreflang, OR subdomain; evaluate the Astro i18n routing tradeoff vs. the current JS-toggle).
> 4. **Content plan** — a single-page site ranks poorly for a spread of intents. Plan the dedicated pages/sections Jitendra needs (per-offering pages, an FAQ page with FAQPage schema, possibly a light blog/journal for informational long-tail). Map each to its target keyword cluster.
> 5. **Off-site / local plan** — Google Business Profile (the single highest-leverage free lever for a local service), NAP consistency, citations/directories (Superprof, MeetUp, Malt, Yoga Alliance, Pages Jaunes, Yelp, local Paris directories), review-generation flow. Flag every item that needs **Jitendra's own action** (GBP address verification, review requests) vs. what we can do.
>
> Then present the plan via **ExitPlanMode** as a **phased** rollout (see "Phasing & timeline" in `SEO_V2_HANDOFF.md`), with realistic timelines and a clear "what needs Jitendra / what needs Debanjan / what I can do autonomously" split. Run the **plan-skeptic** skill before ExitPlanMode (this is a multi-file, multi-week, architectural change → COMPLEX → hard block, loop to CONVINCED or 3 rounds). Follow all always-active workspace rules (front-door-synthetic, output-acceptance-gate, panel-pass, currency-eur, mandatory-audit-stack). Measurement is mandatory: nothing is "done" until Google Search Console is capturing impressions/clicks and we can point at the numbers. SEO is a months-long game — set expectations honestly (see timeline). Ask me (Debanjan) any blocking questions with AskUserQuestion before finalizing the plan.

---

## Current SEO state (audited 2026-07-11 — facts, not assumptions)

| Primitive | State | Verdict |
|---|---|---|
| `<title>` | "Yoga avec Jitendra · Hatha Yoga · Paris" | OK, but generic. Should target a keyword ("Cours de Hatha Yoga à Paris 16 \| Jitendra Kumar"). |
| `<meta description>` | Present, French, mentions studio/domicile/entreprise/plein air/Tapovan | Good. EN variant missing (single-URL problem). |
| Canonical | `https://yogaavecjitendra.fr/` | OK. |
| hreflang | fr, en, x-default **all point to the same `/` URL** | **BROKEN.** Self-referential; gives Google no real alternate. #1 fix. |
| Bilingual delivery | Both FR + EN in one HTML blob, toggled by JS/CSS (`data-lang-content`) | **Core problem.** Google indexes a mixed-language page. Dilutes both languages. |
| `robots.txt` | Cloudflare default content-signals boilerplate only | No `Sitemap:` directive, no real rules. Replace. |
| `sitemap.xml` | **Does not exist** (returns SPA HTML shell) | **Missing.** Add via `@astrojs/sitemap`. |
| Schema.org | `HealthAndBeautyBusiness` LocalBusiness (name, image, url, tel, address, areaServed, founder, sameAs) | Good base. Extend: `Service` per offering, `Person` for Jitendra, `FAQPage`, `AggregateRating`/`Review` from the real testimonials, `priceRange` was removed (client wants no prices — leave removed). |
| OG / Twitter | og:type/title/description/image + twitter summary_large_image | OK. og:image now = meditation portrait. |
| Core Web Vitals | Not yet measured. Static + CF edge → expected strong, but LCP preloads `champ-de-mars-eiffel.jpg` which is **no longer the hero** (hero is now `meditation-portrait.jpg`) — **preload is pointing at the wrong image**, minor perf bug to fix. | Measure with `web-perf` skill + PageSpeed Insights. |
| Google Search Console | **Not set up** (assumed) | Mandatory — can't measure without it. Needs a DNS TXT or the CF-native verification (we control the zone, so this is easy + I can do the DNS part). |
| Google Business Profile | **Unknown / likely not set up** | Highest-leverage free local lever. Needs Jitendra (address verification by postcard/phone). |
| Backlinks / citations | Superprof, MeetUp, TrainMe, GIO France mentioned on-site (sameAs) | Thin. Plan a citation-building pass. |

### Known quick wins already visible (for the next window to confirm + schedule)
1. Fix hreflang + split FR/EN into real routes.
2. Add `@astrojs/sitemap` → real `sitemap.xml` + a proper `robots.txt` with the `Sitemap:` line.
3. Fix the LCP `<link rel="preload">` — it still preloads the old hero image.
4. Keyword-optimize the `<title>` and per-page meta.
5. Set up Google Search Console (DNS verification — I control the CF zone).
6. Extend schema (Service, Person, FAQPage, Review/AggregateRating).

---

## Phasing & realistic timeline

**SEO is a compounding, months-long game. Anyone promising page-1 in weeks is lying.** Here's the honest shape:

### Phase 1 — Technical foundation (my work; ~1–2 build sessions / 2–4 days elapsed)
- Split FR/EN into real prerendered routes (`/` FR, `/en/` EN) with correct reciprocal hreflang.
- `@astrojs/sitemap` + real `robots.txt`.
- Keyword-optimized titles/descriptions per page.
- Extended schema (Service, Person, FAQPage, Review/AggregateRating).
- Fix the LCP preload bug; measure Core Web Vitals.
- Set up Google Search Console + Bing Webmaster (DNS verification — I do the DNS, needs no Jitendra).
- **Deliverable:** clean technical base, submitted sitemap, GSC capturing data.
- **Effort:** mostly autonomous. Deploy + front-door + acceptance gates as usual.

### Phase 2 — Content depth (my work + Jitendra's input; ~1–2 weeks elapsed)
- Dedicated pages per offering (studio / domicile / entreprise / plein air), each a keyword cluster.
- FAQ page (real questions people ask about yoga in Paris) with FAQPage schema.
- Optional light "journal"/blog for informational long-tail ("qu'est-ce que le Hatha Yoga", "bienfaits du yoga", "yoga pour débutants Paris").
- Needs Jitendra to review/approve French copy for authenticity (native-French recruiter-tone matters; per workspace `eval-first` the copy is the product).
- **Deliverable:** 5–10 indexable, intent-targeted pages.

### Phase 3 — Local + off-site (mostly Jitendra's action; ~1–2 weeks to set up, then ongoing)
- **Google Business Profile** — Jitendra must claim + verify (postcard = ~1–2 weeks, or phone/video instant if offered). This is the biggest local lever; without it, "yoga Paris 16" map-pack ranking is impossible.
- NAP consistency across all citations.
- Citation building: Malt, Pages Jaunes, Yelp FR, Yoga directories, local 16e arrondissement directories.
- Review-generation flow (a WhatsApp/email template asking happy students for Google reviews — reviews are a top-3 local ranking factor).
- **Deliverable:** verified GBP, 10+ consistent citations, first Google reviews coming in.

### Phase 4 — Measure, iterate, compound (ongoing; months)
- GSC weekly: which queries impress/click, average position, CTR.
- Iterate titles/content on the pages that are impressing but not clicking (CTR fixes) or ranking p11–20 (near-miss content boosts).
- Build backlinks slowly (guest posts on French wellness blogs, the yoga schools he teaches at linking back, L'Hebdo du Vendredi article link).

### When to expect what (honest)
| Milestone | Realistic timing |
|---|---|
| Technical foundation live + indexed | **1–2 weeks** (Google recrawls in days) |
| Google Business Profile verified + showing in Maps | **2–3 weeks** (postcard delay) |
| First measurable impressions in GSC | **2–4 weeks** |
| Local map-pack presence for "yoga Paris 16 / Passy" | **1–3 months** (GBP + reviews driven) |
| Ranking movement on mid-competition organic terms | **3–6 months** |
| Meaningful organic traffic + head-term ("yoga Paris") contention | **6–12 months** — this is a competitive term dominated by studios with years of authority; hyper-local + niche (bilingual, traditional lineage, corporate) is the winnable wedge, not "yoga Paris" head-on. |

---

## Constraints & decisions the next window must surface to Debanjan

- **Budget: €0/month.** Free tools only (GSC, GBP, Bing, PageSpeed, Google Trends). No Ahrefs/Semrush/paid backlinks unless Debanjan explicitly authorizes.
- **Currency in EUR** if any cost is ever shown.
- **Decisions that need Jitendra (surface with AskUserQuestion in the plan):**
  1. Will he claim + verify Google Business Profile? (Blocking for local. Needs his physical address confirmation — the studio at 22 rue Eugène Manuel, and a decision on whether to show it publicly.)
  2. Is he willing to ask past students for Google reviews? (Top-3 local factor.)
  3. FR/EN URL structure preference — `/en/` subpath (recommended, simplest) vs `en.` subdomain.
  4. Does he want a blog/journal (more content = more ranking surface, but he'd need to feed topics/approve copy)?
- **Workspace rules that apply:** front-door-synthetic (the synthetic must assert the new routes + sitemap + schema render live), output-acceptance-gate (acceptance test must check every SEO primitive), panel-pass, mandatory-audit-stack, plan-skeptic before ExitPlanMode, always-parallelize.

## Success metrics (define "done" for each phase)
- **Phase 1 done:** GSC verified + sitemap submitted + 0 hreflang/canonical errors in GSC + Core Web Vitals "Good" on mobile + acceptance gate asserts every SEO primitive.
- **Phase 2 done:** N intent pages live + indexed (confirm in GSC coverage).
- **Phase 3 done:** GBP verified + live in Maps + ≥5 citations consistent + review flow shipped.
- **Ongoing:** monthly GSC snapshot showing impressions/position trend (up and to the right).

---

## Files the next window will most likely touch
- `astro.config.mjs` (add `@astrojs/sitemap`, i18n routing)
- `src/layouts/Base.astro` (hreflang per route, schema extensions, preload fix)
- `src/pages/` (new routes: `/en/`, per-offering pages, FAQ)
- `src/content/*.json` (per-page meta, FAQ content)
- `public/robots.txt` (new — with Sitemap directive)
- `tests/acceptance_yoga_jitendra.py` + `tests/front_door_yoga_jitendra.sh` (assert new SEO primitives)
- New: `SEO_TRACKING.md` (GSC baseline + monthly snapshots)
