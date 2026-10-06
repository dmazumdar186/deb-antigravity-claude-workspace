# GTM People concept redesign — handoff (2026-10-06)

Live: https://gtm-people-redesign.pages.dev/  (Cloudflare Pages project `gtm-people-redesign`, noindex)
Pitch page: https://gtm-people-redesign.pages.dev/for-ian/
Target: https://www.gtm-people.com/ — specialist SaaS GTM recruitment, Seed to Series C, London, placing globally. Trading name of H2 International Ltd (11968625). Founded 2026 by Ian Harwood (also founder of h2 Recruit; see `deliverables/h2recruit_redesign_2026-09-30/`).
Prospect: Ian Harwood. Reference design lens: the h2 Recruit concept, re-cut in GTM People's own light violet/mint register.

## The brief
"Needs a lot of scrolling; preserve all info; 10x more efficient, measurable." Answer: a one-page "command deck" — hero + sticky panel nav that switches one tabbed panel area (Specialisms · How it works · Roles · TaaS Pricing · Salary Guide · About · FAQ · Partners · Insights · Contact). Every panel is in the DOM (hidden when inactive), deep-linkable (`/#pricing`), keyboard-navigable, with back/forward support.

## Measured (Playwright, `research/measure.mjs`; baseline in `research/baseline_metrics.txt`, after in `research/metrics_after.json`)
| Metric | Live site | Concept | Factor |
|---|---|---|---|
| Desktop 1440×900 page height | 17,828 px (19.8 screens) | 1,773 px (2.0 screens) | 10.1× |
| Mobile 390×844 page height | 36,490 px (43.2 screens) | 2,941 px (3.5 screens) | 12.4× |
| Scroll to reach pricing | 8,682 px / 17,108 px | 0 px (tab) | — |
| Scroll to reach contact form | 16,522 px / 33,865 px | 0 px (tab) | — |
| Words in DOM | 4,373 | 5,003 (all live copy + 25 role descriptions) | nothing dropped |
| Third-party JS | Supabase client, Cloudflare email-decode, analytics | 0 (one Google Fonts link) | — |
| index+css+js | ~275 KB HTML alone | 100.1 KB | — |

Per-panel height at 1440: all ≤ 814 px (one viewport). Mobile: pricing panel ~2,100 px (4 stacked tiers) is the only panel over two viewports.

## Research facts (all from the live site 2026-10-06; `research/live_site_text.txt`, `research/public_jobs.json`)
Positioning, 9 specialisms, 6 client + 4 candidate steps, 30/60/90 check-ins, 3-month guarantee, Why-TaaS table, 4 TaaS tiers with Intelligence +50% toggle and fee notes, 2026 Salary Guide (6 rows), 8 FAQs, About (Ian Harwood, 20+ yrs, 4 pillars, stat chips), 26 partners + JobSearchBud, contact details, legal footer. Roles: 25 live roles pulled from the site's public Supabase `public_jobs` view (snapshot, inlined in `js/main.js`). Logo: the site's own apple-touch-icon mark; no text wordmark.

## What is new vs the live site
- TaaS fee calculator (base salary × tier → fee vs 30%-of-OTE traditional, annual cost incl. retainer).
- Roles as a filterable/sortable table with comp in local currency (location / role type / stage).
- Panel deep-links Ian can paste into DMs (`/#pricing`, `/#salary`, `/#roles`).
- Emoji icons replaced with inline SVG; animated hero "pipeline → shortlist → hire" diagram.

## Verified
`site_check.mjs` PASSED (desktop, Pixel 7, iPhone 13, reduced motion; 0 console errors, 0 overflow, tap targets ≥44, bottom bar clear of submit). Visual review by a reviewer agent: two blockers (panel headings under sticky header) fixed and re-reviewed PASS; two cosmetic notes fixed (opaque header, chip-row scroll-snap). Live CSS md5 matches local. Sandbox Chromium cannot reach `*.pages.dev`, so verification is on identical local files.

## Redeploy
`bash .claude/skills/site-redesign/scripts/deploy.sh deliverables/gtm_people_redesign_2026-10-06/site gtm-people-redesign for-ian/`

## Not done
- Insights article titles are loaded client-side on the live site and were not in the static HTML → three "to wire — live feed" slots; no invented titles.
- Partner for-clients/for-candidates classification is ours; partner links point to gtm-people.com/partners rather than affiliate URLs.
- Contact form and newsletter not wired (shows "Concept — not wired"). Roles are a snapshot, not the live Supabase feed.
- Hidden panels are not Ctrl-F searchable until active.
- No testimonials or client logos (none public; not invented).

## v2 — scroll-story cut (2026-10-06, after operator feedback "still too dense, more dynamic like h2recruit")
Live: https://gtm-people-redesign.pages.dev/ is now the scroll-story. The compact tabbed cut moved to https://gtm-people-redesign.pages.dev/deck/ (own css/js/assets, untouched).

What it is: the h2 Recruit engine (pinned scroll-scrubbed canvas hero with 6 copy states + progress rail, pinned card stacks, rotating drum, hover-accent lists) re-cut in GTM People's light violet/mint register, sentence-case headings, one idea per screen. Sections: film hero · proof counters · 9 specialisms card stack · 6-step drum + 30/60/90 + candidate strip · founder quote + about (dark violet) · 25 live roles card stack with filters · Why TaaS row-reveal · pricing (3 bullets + "Everything in the plan" details, fee calculator, "How our fees work" details) · salary bars · FAQ · JobSearchBud + 28 partners · insights · contact · footer.

Measured (research/metrics_v2.json, functional_v2.json):
| Metric | Live | Deck v1 | Scroll-story v2 |
|---|---|---|---|
| Median visible words per viewport, desktop (sampled every 400 px) | 190 | 224 | 35 |
| Max visible words per viewport, desktop | 392 | 267 | 295 |
| Median visible words per viewport, mobile | — | — | 62 |
| Tallest uninterrupted text block | 420 px | — | 348 px |
| Page weight / requests | 1,004 KB / 41 | — | ~152 KB / 7 |
| Third-party scripts | 3 | 0 | 0 |
| Scroll height desktop (pinned tracks count) | 17,828 px | 1,773 px | 52,167 px (hero 6×, specialisms 5×, roles 9×, drum 4×) |
Scroll height is no longer the metric for v2: pinned tracks consume scroll while the viewport stays put; density per viewport is. Content diff vs live: every live sentence present (checked by 7-word probe); only page title, cookie banner and a select hint omitted.

Verified: site_check PASSED on `/`, `/for-ian/`, `/deck/` (desktop, Pixel 7, iPhone 13, reduced motion), functional suite all green (hero states at 40/80 %, folio card 5/9, drum step 4, London → 11 roles, toggle, calculator £100k Unicorn → £15,000 vs £30,000, FAQ, form notice, reduced motion stacked), 0 console errors. Visual review: 4 minors fixed (hero crossfade residue, header opacity/scroll-margin, pricing card baselines, mobile bottom-bar padding); density rated 4/5 before the pricing trim.
Not done: fonts only render live; partner audience split inferred; roles are a snapshot; form not wired.
