# prodcraft.fyi v2 — build report (2026-10-19)

**Files** (`site/`): index.html 35.9 KB · css/styles.css 28.5 KB · js/main.js 15.0 KB (bundle 79 KB ≤ 150) · js/backdrop.js 5.4 KB (GLM 5.3, hand-reviewed, alphas raised) · 404.html · _headers (CSP, HSTS, cache) · _redirects (/book 302 → cal.com, /call 301) · robots.txt · sitemap.xml · assets: favicon.svg, headshot.webp (720×900), plates/{gtm,greenjobs,misb,midas}.webp, hero.mp4/webm 204/147 KB, hero-m.mp4/webm, hero.jpg, hero.json ready:true, og.jpg 1200×630.

**Verify:** functional 32/32 (`research/functional.json`) · site_check exit 0, 0 failures · 0 console errors desktop/mobile · no horizontal overflow at 390 to 3840 · cover headline is 65% of viewport width at 3840 · screens in `screens/` (35, recipe list plus wide/tablet).

**Heights:** desktop 5,801 px vs live 6,508 · mobile 3,146 (iPhone 13) / 4,307 (Pixel 7) vs live 10,360. Largest deck panel: 822 px desktop, 1,710 px mobile.

**GLM cost:** $0.0111 (one call, 46 s; `research/glm_log.md`).

**Defaults I picked:** the mobile breakpoint is 768 rather than 800, so 768 gets the desktop deck in 2 columns. The ledger is a tri-fold over 2 sheets in the brief's order, turned with Prev/Next, dots or arrow keys. Small-caps text uses #8a6a2b rather than #B07A1C, because #B07A1C fails 4.5:1 on bone. Jitendra's quote has no verify link because no URL is known. The Video Studio "live ↗" goes to YouTube @prodcraft. The persona contact headlines are new copy.

**Not done:** no reviewer rounds on the PNGs yet (only my own look). The fonts were not checked because Google Fonts doesn't load in the sandbox. The Midas plate shows a broken logo, taken from that concept. Also no Kling footage, no deploy, no commit.
