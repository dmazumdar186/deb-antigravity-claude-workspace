# prodcraft.fyi v2 — "the build log" — handoff (2026-10-19)

**LIVE on the real domain:** https://prodcraft.fyi/ (Cloudflare Pages project `prodcraft`, deployment `7b948532`, replaces the June Astro site).
Staging copy of the same files: https://prodcraft-site.pages.dev/ (project `prodcraft-site`).
**Rollback (one command):** the previous production deployment is `c06736d0-9a6f-44b4-a68f-fc4935ff6bd3` (https://c06736d0.prodcraft.pages.dev, 2026-06-25). In the Cloudflare dashboard → Pages → prodcraft → Deployments → "Rollback to this deployment", or re-deploy any older build with wrangler. The v1 Astro source is not in this repo.

## What changed for visitors
- **Prospectus renderer, not a static page** (site-redesign standard since MISB v3): pinned, scroll-scrubbed cover with Kling footage and five "receipt" beats ($1M+ · +45% · <30 days · walk-away clause), a tri-fold **ledger** of shipped work (01), then a **command deck** (02–08) where one chapter is visible at a time with hash deep links, back/forward and arrow keys.
- **02 — Who you are**: a persona board (Founder / Sales leader / Recruiter-agency owner / Enterprise product leader). Picking one re-orders the proof in 03 and rewrites the contact headline, so each visitor type sees their own proof first.
- **New projects added** (verbatim numbers from the deliverable handoffs, `research/project_facts.md`): SaaS GTM recruiter concept (10.1× / 12.4× shorter page, 3→0 third-party scripts), GreenJobs (195 pages, 165 live roles, 2,797 checks), Paris business-school prospectus + 20-post social set, French auto-service franchise concept (33/33 iPhone assertions), the Jev decision stack (21 use cases, $0.00099 for 10 routed prompts), lead-list operations (2,501→977 relaunch after a bounce root-cause; 1,900-row 3-metro list; 229→195 studios), and an anonymised 500-member alumni-platform data audit (2→26→49 rows, 11-lens verdict). Prospects that never hired are named by sector only; links go to the public concept URLs.
- All six original systems, three offers, stack, three objections and three recommendations kept verbatim; stack gains Higgsfield/Kling, GLM, Kimi, Jev, Playwright, Astro.
- **Email** everywhere: `debanjan@prodcraft.fyi` (the Gmail address appears nowhere; asserted by functional test and on the live HTML).
- **Booking**: every CTA points to `https://prodcraft.fyi/book` (`_redirects`: `/book` → cal.com 302, `/call` → `/book`). The page never hard-codes cal.com, so moving to the ProdCraft calendar is a one-line edit in `site/_redirects` + redeploy. No Google Calendar for the prodcraft.fyi mailbox is connected to this session (only the three Gmail calendars), so the appointment-schedule URL could not be created here — see Next.
- Production hygiene: indexable, canonical `https://prodcraft.fyi/`, OG image, `robots.txt`, `sitemap.xml`, CSP + HSTS + frame-deny `_headers`, custom 404, zero third-party JS (one Google Fonts link).

## Measured
| | Live v1 (2026-10-19 morning) | v2 (live now) |
|---|---|---|
| Desktop 1440 scroll height | 6,508 px (7.2 screens) | 5,801 px (6.4) incl. pinned tracks |
| Mobile 390 scroll height | 10,360 px (12.3 screens) | 4,465 px (5.3); iPhone 13 emulation 3,212 px |
| Words in DOM | 918 | 595 in the first paint + every panel in DOM |
| index+css+js | Astro bundle | 79 KB; backdrop 5.4 KB |
| Tallest deck panel | — | 822 px desktop / 1,710 px mobile |
Sources: `research/live_metrics.json`, `research/live_metrics_after.json`, `research/functional.json`.

## Media
- **Hero footage**: Kling 3.0 std via Higgsfield, 10 s, $0.71 (`research/kling/prodcraft.json`, `research/gen_kling_hero.py`). Frame review flagged a desk surface in the lower 22 % → cropped and a lower-third gradient added (`hero-kling.*`), re-reviewed PASS. Landscape 1440×632, portrait 720×1280 (upscaled, slightly soft), WebM pairs, poster `hero.jpg`. Self-rendered canvas fallback stays in `js/backdrop.js` (GLM 5.3, one round, $0.011, `research/glm_log.md`).
- Plates: rendered from our own concept builds in this repo (`assets/plates/*.webp`); headshot and logo from the v1 site.

## Verified
- `research/functional.mjs` 32/32 (cover beats, video, fold hinge, deck tabs/hash/back/keys, counters, fade sequencing, heights, budgets, `/book` + no cal.com/gmail in HTML, persona switch, 404, mobile snap-scroll, bar timing, 0 console errors desktop + mobile).
- `site_check.mjs` exit 0 (desktop, Pixel 7, iPhone 13, reduced motion). No horizontal overflow 390–3840 px.
- **Eye review** (Opus reviewer reading 38 PNGs incl. 768 / 1920 / 2560 / 3840): round 1 FIX (3 P1, 4 P2, 2 P3, all fixed), round 2 SHIP + 3 small items (also fixed, re-shot). First-3-seconds test vs v1: desktop "clearly stronger" (brand, face, proof rail), mobile "stronger", 3840 "clearly stronger".
- Live after deploy: CSS md5 matches local, `/` 200, `/book` 302 → cal.com, `/nope` 404, CSP header present, OG + hero 200.
- Known limits: fonts do not load in the sandbox (layout verified, type verified only by the live URL); full-page screenshots of pinned tracks repeat the stage (`research/states.md`).

## Repo
`site/` (deployable as-is), `research/` (brief, facts, functional, GLM/Kling logs, states, build report), `screens/` (38 PNGs, gitignored). `.gitignore` now un-ignores this site's PNGs. Redeploy:
```
npx -y wrangler@4 pages deploy deliverables/prodcraft_site_2026-10-19/site --project-name prodcraft --branch main --commit-dirty=true
```

## Next (not done, by design)
1. Create the Google Workspace appointment schedule on debanjan@prodcraft.fyi and change the `/book` target line in `site/_redirects`; redeploy.
2. Optional: regenerate the portrait Kling clip natively in 9:16 (~$0.70) instead of the upscaled crop.
3. `www.prodcraft.fyi` already resolves to the same project; DNS lives outside this account, nothing to change.
4. Deck-who "SELECT" persona state is not persisted across visits (deliberate: no cookies, no storage).
