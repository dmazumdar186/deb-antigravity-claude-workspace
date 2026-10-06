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

## v3 — "Brief it" (2026-10-06, after operator rejected v1 "dense" and v2 "long / copy-paste"; brainstorm in BRAINSTORM.md)
Live: https://gtm-people-redesign.pages.dev/ (v3). Comparison cuts: /deck/ (v1 tabs), /story/ (v2 scroll-story, eye-test P1/P2 fixed). Pitch: /for-ian/ ("three cuts, one recommendation").

What it is: an intent-first answer board. Headline + one large brief input (placeholder cycles example briefs); one control row (Hiring | Looking · Stage pill · scrolling example chips); a one-line answer summary; three equal hero-number tiles (Roles in play · Market rate · Your fee) and four one-line strips (How we'd run your search · Why this works at your stage · 2 FAQs for your stage · Next step / contact form). Every tile opens in place to the verbatim live content; an "Everything" index at the bottom holds the rest (specialisms, 28 partners, insights, founder, legal) in drawers. Share link `/#b=<brief>&m=hiring|looking` restores a board; `#pricing` `#roles` `#contact` deep-link. "Agency view" toggle prints the live source sentence under each tile. Client-side intent engine (`parseBrief` → stage, role family, location, seniority, volume) over a knowledge base built from the live copy + 25 live roles; `data-ask-url` on `<html>` switches to the Worker in `worker/` (Anthropic Messages, claude-fable-5-1) once `ANTHROPIC_API_KEY` exists — not deployed (no key in the cloud env).

Measured (research/metrics_v3.json, functional_v3.json; live from baseline_metrics.txt; eye-test friction from qa_2026-10-06/human_eye_verdict.md):
| | Live site | v1 deck | v2 story | v3 Brief it |
|---|---|---|---|---|
| Scroll to first matching role ("Series A London AE") | 3,896 px+ (then filter) | 0 (tab) | 18,729 px (20.8 screens) | 0 px (row at y≈582) |
| Interactions to pricing | scroll 8,682 px | 1 tab | 42,791 px (47.5 screens) | 0 (fee tile first viewport) |
| Default page height desktop / mobile | 17,828 / 36,490 | 1,773 / 2,941 | 52,167 / 27,515 | 2,350 / 3,646 |
| Visible words per viewport, desktop median | 190 | 224 | 35 | 227 (one answer screen; mobile 92) |
| Reviewer density / wow (1–5) | — | 2 / — | 4 / — | 4 / 4 |
| Third-party scripts | 3 | 0 | 0 | 0 |
| Content probe (live lines ≥ 6 words missing) | — | — | 0 | 0 |

Verified: site_check PASSED (/, /for-ian/; /deck/ and /story/ 0 console errors); functional_v3 44/45 (the miss is the 150-word density gate; structural floor explained above); content probe 0 missing; visual review round 1 → 9 defects → density pass → round 2: 4/5 density, 4/5 wow, all earlier defects fixed or polished; polish round applied (chip fades, one-line US note, collapsed role descriptions, Stage prefix, supporting facts, mobile summary truncation). Live CSS md5 matches local; real fonts load on the live URL (probed from Playwright).

Human-eye test on v2 (live at the time): FAIL 3 P1 / 12 P2 / 8 P3 — verdict in research/qa_2026-10-06/. P1 D-01 numeral overlap, D-02 reduced motion, D-04/06/07/08/09 fixed in /story/; D-03 friction is inherent to the pinned design and is why v3 exists. A full human-eye run on v3 is the next gate before a client release.

Redeploy: `bash .claude/skills/site-redesign/scripts/deploy.sh deliverables/gtm_people_redesign_2026-10-06/site gtm-people-redesign for-ian/`
Worker: `cd deliverables/gtm_people_redesign_2026-10-06/worker && npx -y wrangler@4 secret put ANTHROPIC_API_KEY && npx -y wrangler@4 deploy`, then set `data-ask-url` on `<html>` in index.html and redeploy.

Not done: Worker not deployed (no key); full human-eye run on v3; roles are a 2026-10-06 snapshot; form/newsletter not wired; partner audience split inferred; insights titles not public (3 "to wire" slots).

### v3.1 (2026-10-06)
Operator: quick-brief chip strip had no visible way to scroll. Added 44 px prev/next arrows (disabled at the ends), mouse-wheel → horizontal scroll, scroll-snap on chips; verified by Playwright on desktop and Pixel 7 (arrows move the strip, wheel moves it, 0 errors); site_check PASSED; redeployed.

## v4 — brand opening (2026-10-06)

**Live:** https://gtm-people-redesign.pages.dev/ (board unchanged below; pitch page `for-ian/`).

**What it is.** A cinematic four-beat opening above the untouched "Brief it" board, answering the brief "show why the company is great before the tool". No video dependency; all canvas + CSS, zero third-party scripts.

| Beat | Headline idea | Stage |
|---|---|---|
| 1 | GTM hiring, done in days | 800-particle pipeline (300 mobile) funnelling into five mint role cards (AE / SDR / CS / RevOps / VP); one lifts with "Placed · day 5" |
| 2 | Founder track record | Dimmed stage, 64 px counters on white pills |
| 3 | The process | Horizontal 6-node timeline colouring in, "Day 5" tag |
| 4 | Seed to Series C. Based in London, placing globally. | Hand-authored equirectangular coastlines, true lon/lat pins (London, Manchester, Paris, NY, SF), dashed "Remote UK/EU/US" ring |

Sequential beat transitions (260 ms out, 120 ms gap, in). Bottom rail: beat pills + "Start a brief ↓" + "Open roles". Reduced-motion: static beat 1 frame. Mobile: stage directly under copy, rail under cards.

**Verified.** site_check 0 failures · functional_v3 44/45 (density sampler, structural floor, unchanged) · content probe 135 live sentences / 0 missing · board identity diff identical to v3.1 · functional_opening 35/35 (frame delta, no two headlines visible, mobile gap ≤80 px) · visual review cool 4/5, clarity 4/5, composition 4/5, no blockers · index+css+js 145,603 B (cap 150 KB).

**Kling / Higgsfield footage (optional).** The opening is footage-ready: drop `hero.mp4` (desktop) and `hero-m.mp4` (mobile) into `site/assets/`, set `"ready": true` in `site/assets/hero.json`, redeploy. Prompts per beat: `research/hero_footage_prompts.md`; generator: `research/generate_hero_footage.py --beat 1..4` (needs `HF_API_TOKEN`, local only, not run).

**Not done.** Ask-Worker still undeployed (needs `ANTHROPIC_API_KEY` in the environment). Full human-eye run on v4 before client release.
