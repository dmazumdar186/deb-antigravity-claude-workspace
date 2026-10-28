# ASSET Voyages — concept mock-up (2026-10-28)

Live (noindex): https://asset-voyages-redesign.pages.dev/ · pitch https://asset-voyages-redesign.pages.dev/pour-asset/ · console https://asset-voyages-redesign.pages.dev/console/
Source: `site/` (index, css, js, `pour-asset/`, `console/`, `_headers` with CSP + X-Robots-Tag noindex, robots.txt). Screens: `screens/r-*.png` (review set), `screens/check-*.png` (site_check).

## Research (fetched 2026-10-28, curl with a browser user agent)
- The homepage, the MICE pages and `contactez-nous` were reachable. research/facts.md from the parallel worker was not there yet, so the facts below come from the direct fetch.
- Verbatim facts used:
  - "agence de voyages d'Affaires à taille humaine, membre du réseau Selectour Affaires"
  - "Avec plus de 122 agences et plateaux d'affaires en France, Selectour Affaires constitue le premier réseau dédié aux voyages d'affaires"
  - "disponible 24h/24, 7 jours/7"
  - "interlocuteur dédié"
  - "Votre projet de voyage de groupe devient accessible dès 10 personnes"
  - "Un chef de projet dédié : présent dès la prise de brief"
  - the PME-PMI/TPE line and the reporting line
  - the slogan "Optimisez vos voyages d'affaires"
- Assets taken from the live site: the real logo (dark and light versions), the favicon, the hero photo `slide_2_asset.jpg` (now `skyline.webp`) and the Selectour Affaires logo. Every other plate is a generated SVG labelled "Illustration".
- Contradictions (footnoted in the pitch):
  - The live domain is asset-voyagesdaffaires.com, but the RFP cites www.assetvoyages.com.
  - The client area is "Connexion Traveldoo" (plus IRES and the Smart app), but the RFP says Wondermiles.
  - The footer shows both ©2020 and © 2026.
  - The "122 agences" figure is undated.
- Measured heights, live site (`research/live_metrics.json`): 5,014 px desktop, 10,527 px mobile, 661 words.
- Measured heights, concept: 6,033 px desktop, which is taller because of the scrubbed cover and fold-out; 5,111 px mobile.
- Congresses: 12 generic sample listings ("— exemple", fictional dates), no real names. No prices, no GM&E codes, no fare claims.

## Gates
- Functional suite `research/functional.mjs`: 36/36. That is the 29 template assertions plus 7 for ASSET: catalogue, quote prefill with no-network confirmation, MICE brief, FR/EN stub, console, Selectour claim.
- site_check: PASSED on /, /pour-asset/ and /console/, at desktop, Pixel 7, iPhone 13 and reduced motion.
- Bundle: index 37 KB + css 33 KB + js 21 KB ≈ 91 KB. Backdrop 5.9 KB, generated with GLM 5.3 for $0.025 (`research/glm_log.md`). Zero third-party JS. Fonts are self-hosted.
- Hero video: self-rendered (`assets/hero*.mp4|webm`, `hero.json` ready:true). This is the Kling-ready slot.
- Deploy: CSS hash matches live; /, /pour-asset/ and /console/ return 200.

## Eye review
No Agent tool was available inside the build worker, so the worker read the PNGs itself instead of spawning an Opus reviewer.
- Round 1 defects:
  - fieldset border on the MICE brief
  - deck h2 wrapping to 3 lines
  - "7 / jours/7" line break
  - EN "bientôt" hidden on phones
  - tall mobile filter card
  - US date format in the screens
  - `<p>` margins on mobile rows
  - a clipped column in the console
- Round 2: all of the above fixed, plus nowrap on the phone number. Verdict: SHIP.
- An independent reviewer pass is still recommended.

## Not done
- Not committed.
- No independent reviewer sub-agent.
- The sandbox cannot screenshot *.pages.dev, so the live viewport trust gate was not run.
- The real Wondermiles client-area URL is unknown, so that link is a note.
