# Study: AI-role coverage gap + Upwork / RemoteOK / Crossover feasibility

**Date:** 2026-06-24
**Trigger:** Operator question — "is it true that there are no AI Automation or
Process Automation jobs posted anywhere? noone needs an AI Automation Engineer
using Claude Code? Can we add Upwork to this list or RemoteJobs and Crossover
platforms? I want a study report on this as well from a feasibility and a
quantitative value add."
**Status:** Research only. No code changes outside what was already shipped to
extend `linkedin_guest_api` + `wttj_algolia` keyword sets to include AI-role
queries. New-platform integration is gated on operator approval per this report.

---

## TL;DR

1. **The AI Automation gap was on our side, not the market's.** Prior to today's
   keyword extension, `linkedin_guest_api` and `wttj_algolia` ONLY searched for
   16 PM-flavored terms. Zero of those terms hit AI Automation / AI Mobile /
   AI Process / AI Consultant titles. The "AI Automation" / "AI Process" tabs
   were empty because we never asked the upstream APIs for those roles, not
   because the roles don't exist. Keyword expansion landed this morning; first
   run with the new keywords is in progress.
2. **Upwork is wrong-shape for the operator's profile.** It's freelance gig
   marketplace (mostly short-engagement, $25–$80/hr contracts). Useful as a
   side-channel for AI Consultant / AI Automation builds, but does NOT yield
   full-time permanent senior PM roles. Public API exists but requires
   approved OAuth app. Recommend: low-priority Phase 2.
3. **RemoteOK is high-value, near-zero-cost.** Public JSON API at
   `remoteok.com/api`, no auth, no rate limit beyond reasonable use. Returns
   ~50–80 AI/PM/automation roles per day across the full global remote market.
   Strong fit for the operator's "remote-EU" branch. Recommend: ship in Phase 1
   alongside the keyword expansion already done today.
4. **Crossover is medium-value.** No public API; jobs listed at
   `crossover.com/perm-jobs` behind their own search UI. JavaScript-heavy SPA
   — would need either Playwright (banned by workspace history with WTTJ) or a
   reverse-engineered XHR endpoint. Targets $50–100k+ FTE remote roles. Volume
   is low (~5–10 PM/AI per week globally). Recommend: defer.

---

## Part 1 — The AI Automation question

### Operator question

> "Is it true that there are no AI Automation or Process Automation jobs posted
> anywhere? noone needs an AI Automation Engineer using Claude Code?"

### The answer: no, the market is rich; we just weren't asking

`linkedin_guest_api` and `wttj_algolia` are the two LIVE-VERIFIED sources
contributing daily data. Before today's edit, their `DEFAULT_KEYWORDS` sets
contained only PM-flavored queries:

| Source | Old keyword count | Old keyword coverage | AI Automation matches expected |
|---|---|---|---|
| `linkedin_guest_api` | 16 | "product manager", "produktmanager", "chef de produit", "AI product manager", ... | 0 (none of these match "AI Automation Engineer", "AI Consultant", "Process Automation") |
| `wttj_algolia` | 13 | same pattern | 0 |

`config/job_search_v2.json` correctly defines tab routing for AI Automation /
AI Mobile / AI Process / AI Consultant — but routing only fires once a job
reaches the normalizer, and no jobs reach the normalizer if the upstream
search never returns them.

### The fix (shipped 2026-06-24)

- `linkedin_guest_api.DEFAULT_KEYWORDS` extended by 11 entries covering AI
  Automation Engineer / AI Engineer / AI Mobile / Mobile AI / AI Process
  Automation / Process Intelligence / AI Consultant variants (English-first;
  the global English market is rich enough that translations add little for
  these specific titles).
- `wttj_algolia.DEFAULT_KEYWORDS` extended by 5 broader terms ("AI
  automation" / "AI engineer" / "AI mobile" / "AI process" / "AI consultant").
  WTTJ's Algolia index is fuzzy and broader queries pull more relevant hits
  than tight phrase matches.

### Why each keyword

Each addition was checked against LinkedIn's public job search to confirm
non-zero results in the EU region:

| Keyword | LinkedIn EU last-7-days estimate | Notes |
|---|---|---|
| "AI automation engineer" | ~40 | Hot market; many DACH startups |
| "AI engineer" | ~250 | Broad but fits AI Automation tab via routing |
| "AI mobile developer" | ~12 | Niche; will produce 0–2 jobs/day |
| "mobile AI engineer" | ~18 | Same niche |
| "AI process automation" | ~25 | Strong in DE/BE consultancy market |
| "process automation engineer" | ~60 | Adjacent — RPA / Camunda heavy |
| "AI consultant" | ~80 | Strong in CH / DE Big-Four pipeline |
| "AI strategy consultant" | ~30 | Same |
| "AI transformation consultant" | ~25 | Same |

Estimated incremental yield: **+30–60 jobs/day across the 4 AI tabs once
seen.db re-warms** (i.e. day-3 onward). Day 1–2 will be inflated as everything
looks new.

### Risk

LinkedIn's 4 geoIds × 30+ keywords × 1–4 pages each = potentially 480+ HTTP
requests per run. With 1–2s self-throttle per request, this approaches the
GitHub Actions 30-minute job timeout (currently `timeout-minutes: 30` in the
workflow YAML). The existing `MAX_EMPTY_STREAK = 2` early-termination logic
mitigates most of this — low-volume keywords stop fast — but if the pipeline
starts timing out, drop `max_pages_per_keyword` from 4 to 2 for the AI
keywords (route via a separate function call with a tighter cap).

---

## Part 2 — Platform evaluations

### Method

For each platform: (a) public API check via DevTools Network tab on the
respective jobs page; (b) `requests.get` smoke test from a Windows shell;
(c) reading 1–2 community Python wrappers on GitHub (mostly to confirm
auth requirements + rate limits, not to fork). Per workspace's
`prior-art-first.md` rule.

### 2.1 — RemoteOK (`remoteok.com`)

**Public API:** YES. `GET https://remoteok.com/api` returns a JSON array of
~500 active remote jobs across all categories. The first element is metadata;
elements 1–N are jobs with `position`, `company`, `location`, `tags`,
`description`, `apply_url`, `date`.

**Auth:** None. They request a User-Agent header containing contact info
(can be `"job_search_v2 bot — debanjan186@gmail.com"`).

**Rate limit:** Implicit. Calling once per day is way under any threshold; the
endpoint is designed for aggregator polling.

**Coverage:** ~500 active listings at any time. Filtering by tag for
`product` + `ai` + `remote` typically yields 30–80 hits/day across PM / AI
Engineer / AI Automation. The operator's profile (Paris PM, French speaker,
remote-OK) maps cleanly.

**Quality:** High signal — RemoteOK is curated for actually-remote roles
(no "hybrid 5 days/week from our HQ" trickery).

**Implementation cost:** ~1 hour. A new `sources/remoteok.py` adapter calling
`httpx.get`, parsing the JSON, mapping to `SourceJob`. No browser, no OAuth,
no captcha. Tag-based filtering is trivial.

**Recommendation:** **SHIP next.** Lowest cost, highest yield. Adds genuine
new jobs the LinkedIn jobs-guest search misses (Lever / Greenhouse / Ashby
listings that don't post to LinkedIn).

### 2.2 — We Work Remotely (`weworkremotely.com`)

**Public API:** YES, via RSS. Each job category has an RSS feed:
- `weworkremotely.com/categories/remote-programming-jobs.rss`
- `weworkremotely.com/categories/remote-product-jobs.rss`
- `weworkremotely.com/categories/remote-customer-support-jobs.rss`

**Auth:** None. Standard RSS, `feedparser` library on PyPI parses it cleanly.

**Coverage:** ~10–30 new jobs/day across product + programming combined.
Smaller pipeline than RemoteOK but partially non-overlapping (WeWorkRemotely
gets some posts that aren't on RemoteOK).

**Implementation cost:** ~45 minutes. RSS is the friendliest possible
upstream — no auth, no rate limit drama, deterministic schema.

**Recommendation:** **SHIP alongside RemoteOK in Phase 1.** Bundled they
double the remote-friendly EU job coverage.

### 2.3 — Upwork (`upwork.com`)

**Public API:** YES but gated. Upwork Developer API requires:
1. Create an Upwork account (paid? technically the API account is free but
   the platform itself charges 10–20% fees on freelance earnings).
2. Submit a Developer API application describing the use case (1–2 week
   review).
3. OAuth2 dance per user to fetch jobs.
4. Rate limit: 60 req/min on the free tier; jobs endpoint capped at 100
   results per query.

**Public job search URL:** YES — `upwork.com/nx/search/jobs/?q=<query>` is
unauthenticated but returns HTML wrapped around a React app. Parsing requires
either Playwright (page is hydrated client-side) or scraping the
`__NEXT_DATA__` JSON blob from the initial HTML. The `__NEXT_DATA__` approach
has been historically reliable for Upwork (last verified in
sivad259-alt/job-scanner 2024-Q4 commits).

**Coverage:** Upwork is primarily SHORT-FORM freelance gigs:
- "Build me an n8n workflow for $200, 2 weeks"
- "AI consultant needed for 10h/week, $50–80/hr"
- Very few full-time permanent roles. Almost zero senior PM perm roles.

For the operator (looking for full-time permanent Senior / Principal PM roles
in Paris), Upwork's match rate is **<5% of listings**. For an "AI Consultant
side-gigs" pipeline it would be 60%+ match rate — but that's a different
product than what `job_search_v2` does today.

**Implementation cost:** ~3–4 hours either path (OAuth ~3h; Next.js scrape
~4h with the typical SPA flakiness).

**Recommendation:** **DEFER (Phase 2 at earliest).** Only worth doing if the
operator explicitly wants a separate side-gig pipeline. The current pipeline
is a "permanent role" finder; mixing in Upwork gigs dilutes the signal.

### 2.4 — Crossover (`crossover.com`)

**Public API:** NO documented API. The site is a React SPA at
`crossover.com/perm-jobs`. A 30-second DevTools Network inspection on
2026-06-24 confirmed:
- Jobs are loaded via XHR to `crossover.com/api/jobs/search` (returns JSON)
- BUT the request requires a CSRF-like token harvested from the initial page
  load AND a `Cookie: optimizely_*` session cookie.
- Token harvesting works in `httpx` with `follow_redirects=True` + a first
  GET to the homepage. Manageable but more fragile than RemoteOK's pure-GET
  endpoint.

**Auth:** Session-cookie only; no user account required for read access.

**Coverage:** Crossover targets $50–100k+ remote FTE roles. They claim ~250
roles active globally at any time. The PM segment is small — ~5–10 PM jobs
per week globally, of which 1–2 might match the operator's profile.

**Quality:** Very high per-listing (deeply vetted, full JD, salary band
visible).

**Implementation cost:** ~5 hours including the CSRF-token + session-cookie
dance + Playwright fallback if the API moves.

**Recommendation:** **DEFER (Phase 3 or skip).** Low volume × medium
fragility × medium implementation cost. The cost-benefit only flips if the
operator wants exposure to US-style high-comp remote roles that are otherwise
unreachable from the EU job market.

### 2.5 — Adjacent platforms worth a footnote

| Platform | Why skipped here |
|---|---|
| **Wellfound (ex AngelList Talent)** | Login-gated; their API was killed mid-2024. Would need Playwright. |
| **Otta** | UK-focused; small EU coverage. Has a public-ish GraphQL endpoint behind Cloudflare. Worth re-evaluating in Q3. |
| **Y Combinator Work-at-a-Startup** | Login-gated; would need OAuth. Has 200–400 active roles, ~10% remote-EU. |
| **Hacker News "Who is hiring"** | Monthly thread. RSS-able via algolia.com/howsearch — high signal but only 1× per month. Worth wiring as a "monthly burst" source. |
| **Indeed** | Already a configured-but-dark source in `sources/indeed_gmail.py` (needs Gmail alert subscription). Their official API requires partner approval. |
| **APEC** | Already in `sources/apec.py`; Playwright + Didomi consent gate blocks headless. Dark. |
| **Hellowork / Jobgether** | Already configured as Gmail-alert sources; require operator-side alert setup. |

---

## Part 3 — Quantitative value-add per platform

Using the operator's empirical baseline of ~25–30 PM jobs/day across all 6
role tabs (after dedup + filters):

| Add | Est. extra jobs/day (after dedup + filters) | Est. extra tier-A picks/week | Implementation cost | ROI tier |
|---|---|---|---|---|
| **RemoteOK** | +15–25 | +2–4 | 1h | **A** |
| **WeWorkRemotely RSS** | +5–10 | +1–2 | 45min | **A** |
| **AI-keyword expansion (shipped today)** | +30–60 | +3–6 | 0 (already shipped) | **A** |
| **Crossover** | +1–3 | +0–1 | 5h | C |
| **Upwork (perm-only filter)** | +0–2 (very few perm) | +0 | 4h | D |
| **Upwork (gig-side pipeline — different product)** | +20–40 gigs | n/a (different metric) | 4h | (out of scope) |

---

## Recommended Phase 1 ship order

1. **(Done today)** Keyword expansion for AI roles in existing sources.
2. **(Next)** Add `sources/remoteok.py` — 1h, highest ROI.
3. **(Next)** Add `sources/weworkremotely.py` — 45min, near-zero risk.
4. Wait 1 week, observe AI-tab population. If still thin, revisit Crossover.

This Phase 1 stays inside the **prior-art-first rule** and the **front-door
synthetic rule**: every recommended source has been confirmed to expose a
public, unauthenticated endpoint (RemoteOK JSON, WeWorkRemotely RSS) requiring
zero operator setup.

---

## Honest gaps (per panel-pass)

- **No live numbers**, only LinkedIn-search-result-count estimates. The
  +30–60 AI jobs/day claim is based on watching the LinkedIn jobs-guest UI
  return counts in the EU geographies, not a 7-day run of the new pipeline.
  Re-validate on 2026-07-01 after a week of the new keywords running.
- **Upwork coverage estimate is anecdotal.** A real measure would require
  running the Upwork search for "senior product manager" / "AI consultant" /
  etc. across a 30-day window and bucketing by contract length. I did not do
  this; the "≤5% perm" figure is my read of how Upwork's marketplace is shaped,
  not a counted statistic.
- **RemoteOK & WeWorkRemotely overlap with LinkedIn coverage is unknown.**
  Both surface listings that probably also live on LinkedIn — the dedup layer
  will handle exact-match dupes via content_hash, but the operator should
  expect 20–40% overlap, not full additive yield. The net-new number is what
  matters; I estimated conservatively above (15–25 net-new from RemoteOK
  rather than the full 50–80 raw).
- **No exhibits.** This study is forward-looking. Per
  `rules/learnings-loop.md`, if any of the Phase 1 ships under-deliver vs the
  estimates here, that needs to be captured as Exhibit B in this file.
