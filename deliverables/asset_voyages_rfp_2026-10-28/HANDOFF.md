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
- Assets taken from the live site: the real logo (dark and light versions), the favicon, and the Selectour Affaires logo. `skyline.webp` is no longer from their site: it is a Paris panorama, https://commons.wikimedia.org/wiki/File:Paris-pano-wladyslaw.jpg, by Wladyslaw Sojka, CC BY 3.0 (credit shown in the figcaption), cropped to 1600x607. Every other plate is a generated SVG labelled "Illustration".
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

---

# v2 — concept-first redesign « Du brief au retour » (2026-10-28)

The operator rejected v1 because the fold-out and tabs read as a copy of an earlier concept. v2 was rebuilt from a concept paper (`04_Concept_Paper.md`), not patched.

**Live (noindex), same URLs:**
- https://asset-voyages-redesign.pages.dev/
- pitch: https://asset-voyages-redesign.pages.dev/pour-asset/
- console: https://asset-voyages-redesign.pages.dev/console/

Git keeps v1.

## Concept
ASSET packs the trip into one travel wallet, ships it and unpacks it on site. The hero is a 30-second scroll-scrubbed film in seven stages, with a step rail: Brief → Politique voyage → Itinéraire → Réservation (the documents pack into the « pochette ») → Départ (split-flap board, plane on the route) → Sur place (a congress hall assembles, the wallet unpacks badge and programme, assistance 24h/24 · 7j/7) → Retour & reporting.

**How it was chosen:**
- `openai/gpt-6.1-sol` proposed « Le Dossier qui voyage » and two others.
- `z-ai/glm-5.3` proposed « De la Demande au Tarmac » and two others; we rejected its invented figures.
- The synthesis and the reasons are in the paper.
- Logs and costs: `research/glm_log.md`, $0.107 in total. Raw input and output: `research/v2_models/`.

## Sections
1. **Floating pill header** with a progress bar, « Espace client » note (Traveldoo vs Wondermiles) and an FR / EN « bientôt » switch.
2. **Film.**
3. **Statement band.**
4. **Pinned card stack: « Ce que contient la pochette ».** Three document-styled offer cards:
   - boarding pass: Voyages d'affaires
   - seminar programme: Meetings & Events
   - congress badge: Congrès internationaux
5. **Congress catalogue.** The v1 logic, restyled. It covers search, filters, sort, pagination, no-results, the listing dialog and the F03 quote prefilled with fr-FR dates in a text field.
6. **Drum « La méthode ASSET ».** Five steps, each held for 60 % of its scroll unit.
7. **Hover list.** The 13 services that are actually on their site.
8. **L'agence.** Selectour, and a Paris panorama (Wikimedia Commons, CC BY 3.0, credited).
9. **Contact.** Three journeys (F01, F02 with a live summary, congrès).
10. **Footer.**

## Facts
- All quotes are verbatim from the live pages, fetched again on 2026-10-28:
  - home
  - service-evenementiel-seminaire-entreprise
  - voyages-de-groupes-entreprise
  - diagnostic
  - politique-de-voyages
  - notes-de-frais
  - dematerialisation-des-factures
  - assurance-voyages-affaires
  - expertise-tarifaires
  - voyage-daffaire-pme-tpe
- No figures beyond « 122 » (footnoted as undated). No prices, %, clients, testimonials or GM&E codes.
- The 15 % and 70 % claims on the politique-de-voyages page were deliberately left out.

## Film
- `js/film.js` is a pure function of time. The first draft was GLM's; it was re-choreographed by hand.
- Rendered by `research/render_film.mjs` (Chromium + ffmpeg, 24 fps, GOP 6):

| File | Size |
|---|---|
| `hero.mp4` (1920×1080) | 3.2 MB |
| `hero.webm` (1920×1080) | 3.4 MB |
| `hero-m.mp4` (1080×1350) | 3.0 MB |
| `hero-m.webm` (1080×1350) | 3.7 MB |
| posters `hero.jpg` / `hero-m.jpg` | |

- The video is fetched as a blob for scrubbing, with webm preferred.
- Fallback: the live canvas draws the same module.
- Reduced motion: the poster plus a static list of the six other stages.
- `hero.json` (`ready: true`) keeps the slot ready for produced footage.

## Fonts
- EB Garamond (variable, self-hosted) for display. Cormorant was removed.
- Inter for text.
- Zoomed accent check: `screens/accents-zoom-*.png`. The À, é and è glyphs are precomposed and correctly attached.

## Gates (local, served with the real `_headers` CSP via `research/serve_csp.mjs`)

**Functional suite** (`research/functional.mjs`): 46/46. It covers:
- the film: states 0–6, rail fill, blob source, and currentTime scrubbing 15 s → 5 s
- the card stack and the drum
- the catalogue: search, filters, combined filter, no-results, reset, pagination
- the listing and the F03 prefill and validation
- F01 and F02 journeys
- EN and the client note
- fonts, zero console errors, zero third-party requests
- budget and confidentiality
- the Selectour claim
- Pixel 7: header overlap, flattening, anchors, phone on one line, overflow, 16 px inputs
- iPhone 13
- reduced motion
- pitch and console

**site_check:** PASSED on /, /pour-asset/ and /console/, at desktop, Pixel 7, iPhone 13 and reduced motion. Fixes it needed along the way:
- tap targets on the logo, EN, inline links and the phone number
- `site_check.mjs` reported blob: URLs as third-party hosts; it now ignores hosts that are empty

**Budget:** index 33 KB + css 29 KB + js 46 KB (film.js 22 KB) ≈ 108 KB. Zero third-party JS.

**Confidentiality:** a grep of `site/` for other clients and projects returns 0 matches; it is also asserted in the functional suite.

**Measured heights:**

| | Desktop 1440 | Mobile 390 |
|---|---|---|
| Live site | 5,014 px | 10,527 px |
| Concept | 21,364 px | 14,950 px |

The concept is longer because the film, the card stack and the drum are scroll tracks. The pitch table states this plainly.

## Eye review
One self round on the PNGs in `screens/`. Fixed:
- the copy column overlapping the film at 1440
- the board not settled at the t=20 keyframe
- a mobile subject that was too small; the portrait stage was enlarged
- portrait labels and the hall clipped
- the empty-state block showing under results (the `[hidden]` override)
- uneven card heights
- the « / » separators wrapping on mobile
- the contact column left empty on desktop (now sticky)
- the pitch cover misaligned with the body
- the video readiness deadlock that silently fell back to canvas

An independent reviewer is still to run (caller).

## Not done
- Not committed.
- No independent reviewer.
- The sandbox cannot open *.pages.dev, so the live-viewport trust gate was not run. Live verification was: HTTP 200 on /, /pour-asset/, /console/, the videos and film.js; CSS hash match on styles.css and doc.css; CSP with `blob:` confirmed in the live headers.
- GPT was not used for microcopy. The headlines were written in session, and every quoted claim is verbatim.

## v2.1: independent reviewer fixes (2026-10-28)

The reviewer verdict was NOT SHIP. Every item has been fixed, redeployed to the same URLs, and not committed.

1. **Film text.** Text layers now hard-swap: opacity and visibility switch 0/1 with no crossfade. The text state follows the frame on screen (`round(currentTime / 5)`), not the raw scroll position. Asserted by a fast-scroll test: exactly one layer visible, and it matches the frame.
2. **Pack / ship / unpack, re-choreographed and re-rendered** (desktop, mobile and both posters):
   - **04 Réservation:** the documents slide INTO a large open pochette.
   - **05 Départ:** the closed pochette travels the route, with the plane just ahead.
   - **06 Sur place:** the same pochette comes to the front of the hall and opens, and the programme, badge and boarding pass come OUT of it.
3. **iPhone 13 cropping.** The mobile frame height is now `min(125vw, 100svh − header − 330px)`. Asserted: the subject is never covered by the copy (states 01, 04, 06).
4. **Clipped « VILLE DU CONGRÈS ».** The label now sits under the pin and is hidden during the zoom.
5. **Stage 03 headline.** Now « Un itinéraire tracé avec vous. », with no price or outcome promise.
6. **The two flagged quotes, re-fetched and verified on 2026-10-28:**
   - « […] nous trouvons la meilleure combinaison tarifaire pour les billets complexes, comme les multi-segments ou les tours du monde. » is from https://asset-voyagesdaffaires.com/solutions-voyages-affaires-pme/expertise-tarifaires/. The original reads « Ensuite, nous trouvons… »; the cut is marked [ … ].
   - « La politique de voyage de votre société sera appliquée de manière systématique, quel que soit le canal de réservation utilisé. » is from https://asset-voyagesdaffaires.com/solutions-voyages-affaires-pme/politique-de-voyages/.
7. **Lingering offer cards.** Retired offer cards now fade fully and are then hidden.
8. **Reduced motion on phones.** It now uses the portrait poster.
9. **Coquilles.** « quelle que soit » and « voyages d'affaires » are corrected on the page, and the pitch says « deux coquilles corrigées ».
10. **Pitch table.** Reframed as « ce que l'on atteint sans changer de page »; the measured figures are kept.
11. **Smaller items:**
    - Mobile statement tags now have rule separators.
    - The console's mobile tab row wraps.
    - The congress field in the quote form is a 2-line read-only textarea.
    - Hover effects apply only on hover devices, and the review shots park the mouse.
    - Non-breaking spaces inside « ».

**Gates:**
- Functional: 48/48 (two new assertions).
- site_check: PASSED on 3 pages × 4 contexts.
- `screens/` re-shot; one self-review round.
- Paris skyline photo and its credit confirmed present before deploy (done by the other worker; not touched here).
