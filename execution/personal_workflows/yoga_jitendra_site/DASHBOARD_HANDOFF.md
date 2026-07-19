# Dashboard V0.01 → V1.0 — Handoff for the Next Context Window

**Created:** 2026-07-11 evening (Paris)
**Author:** Debanjan (via prior Claude Code context, ~90% context spent on SEO Phase 1 shipping + Ahrefs cleanup)
**Next context to pick this up:** fresh session, target same-day delivery of V0.01 to Jitendra
**Related plan file:** `~/.claude/plans/you-are-picking-up-tender-rain.md` (SEO v2.0 — parent project)
**Related tracking log:** `SEO_TRACKING.md` in this same directory

---

## 1. Why this exists

Debanjan is doing this SEO project for Jitendra unpaid, as a personal favour / portfolio piece. The site (`yogaavecjitendra.fr`) is live, indexed, and starting to accrue signal. Over the next 4 weeks → 3 months → 6 months → 12 months → 2 years, the value delivered will grow but be almost entirely invisible to Jitendra unless it's shown to him.

The dashboard is the artifact that makes the value visible — not a raw analytics dump, but a **narrative surface** that says:

- "Here's how many people are finding you on Google right now."
- "Here's how they're converting into WhatsApp conversations."
- "Here's how the story has moved since we started."

It also doubles as a portfolio piece Debanjan can point future clients at ("this is what agency-level rigor looks like for a solo teacher").

---

## 2. The ask (Debanjan's own words, verbatim)

> I want to build a dashboard for this entire system. The dashboard definitely will be internal and it will just be seen by me and Jitendra. It should only track all the key metrics and it should be safe to be presented as something to the customer. It should be very interactive, very cool-looking, using the best tools available. It should not cost him anything extra. We build it today, deliver it to him, and 4/12/24 months later he can see the cumulative value.

Reformulated as a specification:

- **Users:** 2 (Debanjan + Jitendra)
- **Access model:** internal only, auth required
- **Location:** on the existing domain (subpath preferred: `yogaavecjitendra.fr/dashboard/`)
- **Budget:** €0/mo forever
- **Aesthetic:** matches the yoga site's cream / terracotta / sage palette + Fraunces serif + Inter sans
- **Density:** not overwhelming — ~8-10 primary metrics at most on the main view
- **Interactivity:** subtle (animated counters, hover states, smooth range toggle) — NOT 24-widget-drag-and-drop
- **Longevity:** must show a 2-year narrative arc, not just today's numbers
- **Portfolio-grade:** presentable to a paying client, not a scrappy internal tool

---

## 3. Non-negotiables (already decided — don't re-litigate)

| Constraint | Decision | Reason |
|---|---|---|
| Cost | €0/mo hard cap | Debanjan unpaid on this project |
| Auth | Required | Prevents scraping of query data / competitor intelligence |
| Data safety for customer view | No raw competitor names, no "cost per lead" style internal metrics, no negative framing | It's Jitendra's dashboard, not Debanjan's ops console |
| Design system | Reuse the yoga site's: `--cream`, `--sand`, `--terracotta`, `--sage`, `--ink` + Fraunces + Inter (see `src/styles/global.css`) | Feels like the same product; zero design churn |
| Hosting | Same domain, subpath `/dashboard/` | One DNS record, one build pipeline, one acceptance gate |
| Rollback | One-line removal (`git revert` + `wrangler pages deploy`) | Standard for this repo |

---

## 4. Two-stage build plan

### V0.01 — TODAY (~4-6 hours in the next context)

**Goal:** something Jitendra can open on his phone tonight and immediately understand what he's looking at, even if the numbers are mostly placeholder / mocked from the little live data we already have (GSC = 0 impressions until propagation; Ahrefs Health Score = 86 is real; site is verified in GSC + Ahrefs + Bing).

**Scope:**

- Static Astro route at `/dashboard/` and `/en/dashboard/` (bilingual just because the parent site is — even though this is internal, consistency is cheap)
- **Auth via Cloudflare Access free tier** (50 users, magic-link email, zero config on the frontend). Falls back to Basic Auth via a Worker if CF Access proves finicky.
- Hero + 6-8 KPI tiles + one small timeline strip + one "story" section with 3-5 milestone cards.
- Mocked-but-honest data: real Ahrefs Health Score (86), real "deployed 2026-07-11" milestones, placeholder impressions ("data lands ~24-48h"), real GSC verified status, real GBP live status. Where a number isn't yet available, show a small skeleton pill saying "data arrives Mon 15 Jul" — not a fake number.
- Deployed to prod, sent to Jitendra via WhatsApp with the magic link.

**Explicitly out of scope for V0.01:**

- Any real API polling. All values are read from a single `dashboard-data.json` file checked into the repo. Debanjan edits that JSON weekly by hand until V0.1 automates it.
- Charts with animated tweens. V0.01 uses static SVG sparklines — save the animated tweens for V0.5.
- Multi-timeframe toggle (7d/30d/90d). V0.01 just shows "since launch."

### V0.1 — Week 2 (once GSC has real impression data)

- Cloudflare Worker with a cron trigger (daily 06:00 Paris) that:
  - Calls GSC API → writes latest snapshot to CF KV
  - Calls Bing WMT API → same
  - Calls GBP Business Profile Performance API → same
  - Serves `/api/dashboard-data` from KV
- Frontend fetches `/api/dashboard-data` at page load, populates the tiles
- Timeframe toggle added: 7d / 30d / 90d / all-time
- Ahrefs still manual weekly (no API on free tier) — Debanjan pastes numbers into a CF KV admin route once a week

### V0.5 — Month 2

- Animated counters on tile load
- Sparkline hover tooltips (recharts or ApexCharts, ~40KB gzipped)
- Milestone timeline becomes interactive (click for context)
- Optional: Cloudflare Analytics integration (page views on the yoga site itself)

### V1.0 — Month 4

- **The "value" narrative section.** This is the eventual hero of the dashboard:
  - Cumulative WhatsApp clicks tracked (via UTM)
  - × estimated conversion rate (start at 15%, refine when Jitendra reports actuals)
  - × avg session value (Debanjan asks Jitendra for a rough number in month 3)
  - = "€X of student-lifetime-value attributable to organic traffic since launch"
- One line, big number, understated. This is what makes it a portfolio piece.

---

## 5. Open decisions — surface these at the start of the next context

Present each as an `AskUserQuestion` block at the top of the planning phase. Don't guess.

### Q1: Auth method

| Option | Pro | Con |
|---|---|---|
| **A. Cloudflare Access free tier (email magic link)** | Zero frontend code; professional feel; 50 user cap; used by Cloudflare's own customer dashboards | Requires CF Access enablement on the Pages project (one dashboard click, but a click) |
| B. HTTP Basic Auth via a Worker | Simplest possible; 2 hardcoded credentials in Worker env vars | Ugly browser popup; Jitendra likely to lose the password |
| C. Signed magic-link URLs (Debanjan sends via WhatsApp, 30-day expiry) | No login flow at all; feels like a "private link" | Rebuilding CF Access from scratch; +2h scope |

Recommended: **A**. Falls back to B only if CF Access can't be turned on for whatever reason.

### Q2: URL shape

| Option | Pro | Con |
|---|---|---|
| **A. Subpath `/dashboard/` on the existing Pages project** | One build, one deploy, one acceptance gate; already tested | Subpath is slightly less "private-feeling" than a subdomain |
| B. Subdomain `dashboard.yogaavecjitendra.fr` | Feels more separate; easier to point CF Access at | New DNS record + new Pages project; ~30 min extra work |
| C. Separate deploy at `yoga-jitendra-dashboard.pages.dev` (no custom domain) | Total isolation | Feels unprofessional |

Recommended: **A**. B is fine if CF Access requires a distinct hostname.

### Q3: How honest about placeholder data on V0.01

| Option | Description | Vibe |
|---|---|---|
| **A. Show skeleton pills labeled "data arrives Mon 15 Jul"** where the number isn't ready | Transparent | Feels like a real product in beta |
| B. Show real numbers where we have them, hide the tiles we don't | Cleaner today | Hides the fact that the story is unfolding |
| C. Show placeholder numbers with a small `demo` badge | Common in mockups | Feels like a mockup, not a product |

Recommended: **A**. Sets the honest expectation with Jitendra + reads as "we're waiting on Google to publish data" which is exactly true.

### Q4: How much to use GLM 5.2

Debanjan gave explicit override to the "no Chinese models for sensitive data" rule for this project. But the rule wasn't wrong — it applies to data payloads. The dashboard has two workstreams:

- **Visual layer (HTML/CSS/animation prompts):** GLM 5.2 is genuinely excellent at this per the model-tier.md exhibit; use it for the initial visual scaffold generation + micro-interaction ideation. **Approved.**
- **Data layer (real GSC queries, real conversion counts, real Jitendra data):** never touches GLM. Anthropic-direct or local logic only.

The next context should confirm this split with Debanjan before starting the GLM run.

---

## 6. Recommended stack (defensible; still ask before locking in)

**Frontend:**
- Astro (already the parent site's framework — reuse everything)
- Vanilla JS for interactivity — no React/Vue for V0.01
- Handwritten SVG sparklines for the tiles (no chart library in V0.01)
- Tailwind classes matching the parent site
- Add ApexCharts later at V0.5 when we need real interactive charts (~40KB gzipped, MIT license, free)

**Backend (V0.1+ only, not V0.01):**
- Cloudflare Worker with cron trigger
- CF KV for daily snapshot storage
- Both included in CF free tier

**Data sources (all free, all confirmed):**

| Source | Access | Cost | Latency | Notes |
|---|---|---|---|---|
| Google Search Console | GSC Search Analytics API (OAuth) | Free | ~24h | Debanjan already verified as domain property. Needs OAuth setup in Google Cloud Console for the Worker. |
| Google Business Profile | Business Profile Performance API v1 | Free | ~24h | Debanjan already has Manager access via debolshop@gmail.com. Needs OAuth setup + one manual approval. |
| Bing Webmaster Tools | Bing WMT API | Free | ~24h | Already added; needs API key (one dashboard click). |
| Ahrefs Webmaster Tools | Manual weekly (no API on free tier) | Free | Weekly | Debanjan copies numbers into CF KV via a signed admin route. |
| Cloudflare Analytics | CF Analytics Engine API | Free | Live | Native — no OAuth. Post-V0.5. |
| WhatsApp click tracking | Already in place via UTM tags on `wa.me/` links | Free | Live | We measure the click on the site (via a small Plausible-community or GA4-free ping); we can't see if the message actually landed in Jitendra's phone. |

**Auth:**
- Cloudflare Access free tier (50 users, magic email links)
- Fallback: Basic Auth via Worker

---

## 7. Data collection status — TODAY (2026-07-11 evening)

What's live and usable right now:

- ✅ GSC verified as Domain property (debolshop@gmail.com)
- ✅ GSC sitemap submitted; coverage data expected ~2026-07-13
- ✅ Ahrefs WMT verified; Site Audit ran; Health Score 86; weekly re-crawl scheduled
- ✅ Bing WMT added; sitemap submitted; data expected ~2026-07-13
- ✅ GBP Manager access on debolshop@gmail.com; profile enriched (13 sections)
- ✅ Corporate logos + SEO v2.0 live at yogaavecjitendra.fr
- ✅ UTM tracking on all WhatsApp CTAs
- ✅ `/merci` + `/en/thanks` conversion pages exist (and are now noindexed per Ahrefs cleanup)

What's NOT yet available:
- ❌ GSC impression data (needs ~24-48h)
- ❌ GBP performance data (needs ~7 days for first snapshot)
- ❌ Bing impression data (needs ~24-48h)
- ❌ First GBP review (Jitendra hasn't distributed cards yet)
- ❌ Any organic backlinks (project is 1 day old)

**Implication for V0.01 today:** the dashboard will be mostly-skeleton with a real Ahrefs Health Score (86) + real milestone log + real deployed-status booleans + everything else honestly labeled "waiting on data source."

That's fine. That's the point. A honest empty dashboard on day 1 that fills in over the next 4 weeks is more impressive to Jitendra than a fake-full dashboard on day 1.

---

## 8. Layout sketch (V0.01)

Left-to-right, top-to-bottom, mobile-first:

```
┌─────────────────────────────────────────────┐
│ [logo] yogaavecjitendra.fr / dashboard      │  ← minimal top nav; logout link
│                                             │
│         Depuis le lancement                 │  ← eyebrow, in Fraunces
│         5 jours de vol                      │  ← the H1: something warm, not "STATS"
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Google   │ │ Ahrefs   │ │ WhatsApp │    │  ← 3 hero tiles: the story
│  │ 0 imp    │ │ 86 / 100 │ │ 0 clics  │    │
│  │ ⏳ 2j    │ │ Good     │ │ ⏳ live  │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│                                             │
│  Découverte                                 │  ← section eyebrow
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐              │
│  │page│ │pos │ │Bing│ │GBP │              │  ← 4 secondary tiles
│  └────┘ └────┘ └────┘ └────┘              │
│                                             │
│  Chemin parcouru                            │  ← milestone strip
│  ● 11 juil  Site v2 déployé                │
│  ● 11 juil  Ahrefs audit 86/100            │
│  ● 12 juil  Première indexation Google     │
│  ○ 15 juil  Premières impressions attendues│
│                                             │
│  Ce que nous mesurons                       │  ← honest "what/why" section
│  Google Search Console : ce que les gens   │
│    tapent avant de nous trouver             │
│  Google Business : ce qu'ils font sur      │
│    Maps                                     │
│  Ahrefs : la santé technique du site        │
│  WhatsApp UTM : combien deviennent une      │
│    vraie conversation                       │
│                                             │
│  Dernière mise à jour : il y a 3 heures    │
└─────────────────────────────────────────────┘
```

Not shown: language toggle (FR default matches Jitendra), the ambient breathing-dot from the parent site, the same footer.

Explicit design principles for this layout:

- Every tile has a **status badge**: `⏳ waiting`, `✓ live`, or a real number. Never fake.
- The "Chemin parcouru" strip is the emotional core. It grows over time. It's what turns "0 impressions this week" into "look how far we've come."
- Copy is warm, not spreadsheet-ish ("Depuis le lancement, 5 jours de vol" beats "Analytics — Last 5 Days").
- No red / no green. Palette stays cream + terracotta + sage. Even negative metrics don't get shamed with red — they get an ⏳.

---

## 9. Files to create / modify (V0.01)

New:
- `src/pages/dashboard.astro` (FR)
- `src/pages/en/dashboard.astro` (EN)
- `src/components/dashboard/HeroTile.astro`
- `src/components/dashboard/KpiTile.astro`
- `src/components/dashboard/MilestoneStrip.astro`
- `src/components/dashboard/WhatWeMeasure.astro`
- `src/content/dashboard-data.json` — single source of truth for V0.01, hand-edited
- `src/content/dashboard.fr.json` — copy strings (labels, section titles)
- `src/content/dashboard.en.json` — same
- `tests/acceptance_dashboard.py` — dashboard-specific acceptance gate

Modify:
- `src/layouts/Base.astro` — add optional `dashboard` mode that strips ambient audio + adjusts nav
- `astro.config.mjs` — no changes (both routes auto-included in sitemap)
- `SEO_TRACKING.md` — add "Dashboard V0.01 delivered on YYYY-MM-DD" milestone
- `robots.txt` — optionally add `Disallow: /dashboard/` (though CF Access blocks crawler auth anyway)

**Cloudflare-side (one-time, next context asks Debanjan to click):**
- Enable CF Access on the yoga-jitendra Pages project
- Create an Access application scoped to `/dashboard/*`
- Allowlist: `debolshop@gmail.com` + `jitendranitrr13@gmail.com`
- Policy: email magic link, 30-day session

---

## 10. What to invoke in the next context

At kickoff, in this order:

1. Read this file (`DASHBOARD_HANDOFF.md`) + `SEO_TRACKING.md` + `~/.claude/plans/you-are-picking-up-tender-rain.md` in parallel — one message, three Reads.
2. `AskUserQuestion` block with Q1, Q2, Q3, Q4 from section 5.
3. Enter Plan Mode. Draft a V0.01 plan.
4. Invoke `plan-skeptic` on the draft. Classification: **COMPLEX** (multi-file, new route, new auth surface, deployed) → hard block, up to 3 rounds.
5. Once skeptic returns CONVINCED or the hard cap fires, run `panel-pass` — actual 4-agent spawn (Karpathy / Cherny / Amodei / Research), not narration.
6. Invoke `impeccable` skill for the visual design pass on the layout sketch before coding.
7. `ExitPlanMode`.
8. Build. One commit per logical step.
9. Deploy to preview URL first. Debanjan eyeballs. Then production.
10. Run the mandatory audit stack (6 auditors, parallel batch) on the final architectural commit.
11. Send Jitendra the WhatsApp with the CF Access magic link URL.

---

## 11. HITL required (kept honest, per the parent project's ledger discipline)

**Debanjan (~15-20 min across the session):**
- Answer Q1-Q4 (~2 min)
- Click "Enable Access" on Cloudflare dashboard when prompted (~2 min)
- Approve preview URL visually (~3 min)
- Send Jitendra the WhatsApp with the magic link (~1 min)
- Eyeball prod after deploy (~2 min)
- Copy paste GSC/Bing/GBP API OAuth flow (V0.1 only, not V0.01) — ~15 min later this week

**Jitendra (~0 min for V0.01):**
- Click the magic link Debanjan sends. That's it.
- Future asks (V1.0): ~5 min WhatsApp answer on "what's your rough avg student lifetime value" so we can plug the number into the value calculation.

Total end-to-end for V0.01 delivery: **Debanjan ~20 min, Jitendra ~30 sec.**

---

## 12. GLM 5.2 usage boundary (explicit split)

Debanjan approved GLM override for this project. To keep the workspace rule integrity:

**Approved GLM 5.2 uses:**
- Generating the initial HTML/CSS layout scaffold for the dashboard route (visual work only)
- Ideating micro-interaction patterns (hover states, animated counters)
- Sketch-to-code translation for the layout sketch in section 8

**NOT approved for GLM 5.2:**
- Passing real GSC query strings (student search patterns are semi-PII)
- Passing GBP performance data (Jitendra's business intel)
- Passing Ahrefs data (some inputs are Jitendra's competitive positioning)
- Passing any Jitendra email / phone / address / student data

Practical implementation: use GLM to generate a **template with placeholder tokens** (`{{METRIC_1}}`, `{{METRIC_1_LABEL}}`, etc.). Debanjan/next-Claude fill the tokens locally with real data.

---

## 13. Success criteria for V0.01 (checklist for next context)

- [ ] `/dashboard/` route deployed to yogaavecjitendra.fr
- [ ] `/en/dashboard/` route deployed
- [ ] CF Access (or fallback auth) protects both routes; unauthenticated visit redirects to magic-link login
- [ ] Both Debanjan and Jitendra emails whitelisted
- [ ] All 3 hero tiles render with either a real number or an honest `⏳ waiting` badge
- [ ] All 4 secondary tiles same
- [ ] Milestone strip has ≥ 3 real past milestones + ≥ 2 upcoming expected ones
- [ ] "What we measure" section explains each source in one warm sentence
- [ ] Loads under 500ms on 4G (parent site's LCP budget)
- [ ] Palette matches parent site (cream / terracotta / sage) — visual continuity confirmed by Debanjan eyeball
- [ ] Acceptance gate `tests/acceptance_dashboard.py` passes
- [ ] Mandatory audit stack all 6 auditors PASS
- [ ] `SEO_TRACKING.md` updated with "Dashboard V0.01 delivered YYYY-MM-DD"
- [ ] WhatsApp sent to Jitendra with the magic link URL + one-line "here's the little tracker I built for us"

---

## 14. Anti-patterns to watch for in the next context

Learned from the parent project (SEO v2.0) and prior contexts:

- **Don't ship a fake-full dashboard.** Every placeholder must be honestly labeled. See section 5 Q3.
- **Don't launch without CF Access (or another real auth).** A public `/dashboard/` route with real GSC query data on it is a small data-exposure risk.
- **Don't skip the 4-lens panel-pass** in favour of narrating "the four lenses probably agreed." Spawn the 4 sub-agents per the mandatory-audit-stack rule. This is user-facing customer-presented work — high panel bar.
- **Don't build V0.1 features into V0.01.** No cron trigger today. No API polling today. `dashboard-data.json` static file only. V0.1 is next week.
- **Don't use red/green.** The palette is cream + terracotta + sage. Even "0 impressions" is not a failure — it's an ⏳.
- **Don't overwhelm.** 8-10 primary numbers max. If a tile isn't storyful, cut it.

---

## 15. Cost breakdown (must remain €0/mo forever)

| Component | Cost | Cap |
|---|---|---|
| Astro build | €0 | — |
| Cloudflare Pages | €0 | 500 builds/mo (we use ~20) |
| Cloudflare Access | €0 | 50 users (we use 2) |
| Cloudflare Worker (V0.1+) | €0 | 100k requests/day (we use ~10) |
| Cloudflare KV (V0.1+) | €0 | 100k reads/day, 1k writes/day (we use ~50 reads, ~5 writes) |
| GSC API | €0 | — |
| GBP Performance API | €0 | — |
| Bing WMT API | €0 | — |
| Ahrefs Webmaster free tier | €0 | Weekly crawl already active |
| GLM 5.2 (visual scaffold only, one-off) | ~€0.05 one-off | Paid from Debanjan's OpenRouter balance if any; if $0, use free Gemini for the scaffold instead |

**Total: €0/mo recurring.** One-off design generation cost is a rounding error.

---

## 16. Rollback / removal path

If Jitendra doesn't want the dashboard or thinks it's overkill:

```bash
git revert <dashboard-commit-sha>
git push
cd execution/personal_workflows/yoga_jitendra_site
npx astro build
npx wrangler pages deploy dist --project-name=yoga-jitendra --branch=main
```

Then in Cloudflare dashboard: disable the Access application (~2 clicks). Total takedown time: ~5 min. The URL 404s, no orphaned data anywhere.

---

## 17. What NOT to touch (locked scope)

- `src/pages/index.astro` and `src/pages/en/index.astro` — the parent site homepages. Don't add a dashboard link to the public nav. Dashboard is discoverable only via direct URL.
- Any of the `src/components/` files that render on the public site — the dashboard gets its OWN components subfolder (`src/components/dashboard/`).
- Any of the schema.org JSON-LD in `Base.astro`. Dashboard doesn't need schema; it's noindexed anyway.
- `SEO_TRACKING.md` structure — append a new section, don't restructure existing.
- Any GBP / Ahrefs / Bing settings — they're already live and configured; dashboard just READS them.

---

## 18. Deferred to future contexts (V0.5+)

- Real-time animated counters
- Sparkline hover tooltips
- ApexCharts integration
- Multi-timeframe toggle (7d / 30d / 90d / all)
- Cloudflare Analytics integration
- Value-in-EUR narrative section (V1.0)
- Jitendra-facing "help me interpret this" tooltips
- Email digest ("here's your weekly summary") — could be a nice V2

---

## 19. MCP servers currently unavailable (heads-up for next context)

Session notes flagged these Cloudflare MCP servers as unauthorized in the current setup:
- `plugin:cloudflare:cloudflare-api`
- `plugin:cloudflare:cloudflare-bindings`
- `plugin:cloudflare:cloudflare-builds`
- `plugin:cloudflare:cloudflare-observability`
- `claude.ai Vercel` (unrelated but flagged)

If the next context wants to auto-configure the CF Access app or CF Worker via MCP, Debanjan needs to authorize these first via `/mcp` in an interactive session or via `claude mcp add`. Otherwise the Worker + Access configuration is a manual dashboard-click flow (~5 min).

---

## 20. One-line kickoff message for the next context

> Read `execution/personal_workflows/yoga_jitendra_site/DASHBOARD_HANDOFF.md` in full, then present Q1-Q4 from section 5 as an `AskUserQuestion` block. Once answered, enter Plan Mode, run plan-skeptic (COMPLEX), then panel-pass, then impeccable. Ship V0.01 today.
