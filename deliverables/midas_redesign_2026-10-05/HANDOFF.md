# Midas France concept redesign — handoff (2026-10-05)

Live: https://midas-redesign.pages.dev/  (Cloudflare Pages project `midas-redesign`, noindex)
Pitch read-me for the prospect: https://midas-redesign.pages.dev/pour-midas/
Target: https://www.midas.fr/ — auto-repair franchise chain, 375 centres in France, 712 in 10 countries, Mobivia group since 2004. Prospect: the local franchisee near the operator's flat (send via the midas.fr contact form, or walk in).

## Research (midas.fr blocks scrapers with a 403; facts came from search snippets, Wikipedia, franchise press, Auto Infos / Journal Auto)
- 2025 signature « Avec Midas, vous pourrez toujours avancer » (Dentsu Creative, March 2025). Two hero offers in 2025 comms: RDV garanti en 24 h, plaquettes à 0 €.
- Live offer on midas.fr: -30 % on LA Révision constructeur, forfaits entretien and pièces, until 10/10/2026, participating centres only. Used verbatim in the gold band with a countdown.
- LA Révision garantie constructeur préservée since 2009; Midas France quotes ~35 % average price gap vs dealer. e-Révision for EV/hybrid since 2022. Midas Glass (vitrage) launched autumn 2025.
- 14 prestation families and 7 free diagnostics taken from midas.fr/entretien-auto search results.
- Trustpilot for centre.midas.fr is 1.7/5 (354 reviews, not solicited). Deliberately NOT shown; the concept has a per-centre reviews block ready to wire and the pitch page frames review management as the opportunity.
- Sector best practice (auto-repair sites): phone + booking + hours above the fold, starting prices, warranty as a primary trust element, per-service pages for local SEO, mobile one-handed use. The booking widget on the first screen follows the real midas.fr flow (plaque → prestation → centre → créneau).

## What it is
One page, zero dependencies, gold-on-black "touche Midas" theme, Sora font. Hero with scroll/time-driven dashboard warning lights, rotating word, working booking widget (FR plate mask, créneaux computed for the next 24 h, confirm → modal linking to midas.fr/devis). Offer band with live countdown, free-diagnostics ticker, 14 filterable prestation rows that pre-select the widget, La Révision checklist + counters, e-Révision battery bar, Midas Glass crack-to-clean SVG, France dot-field (illustration), centre search (links to midas.fr/centres-auto-midas), placeholder per-centre reviews, Pourquoi Midas strip, mobile sticky call/RDV bar. 59.6 KB HTML+CSS+JS.

## Verified
Playwright at 1440×900 and 390×844 plus reduced-motion: 0 console errors, plate mask, slots, modal, filters, menu a11y, reveals, no horizontal overflow. Screenshots in `screens/`. Google Fonts only load on the live URL (sandbox TLS).

## Redeploy
`npx -y wrangler@4 pages deploy deliverables/midas_redesign_2026-10-05/site --project-name midas-redesign --branch main --commit-dirty=true`

## Not done (by design)
No real booking backend, no real phone numbers/hours (per-centre), no photos, no audit stack / human-eye-test. Firecrawl and Tavily MCP keys were invalid in this cloud session (401).

## Repeatable process for the next local shop
1. Research: Wikipedia + franchise press + `site:` searches (direct scrape often 403s). 2. Brief a worker with verified facts only, same engineering rules. 3. Playwright check. 4. `wrangler pages project create <slug>-redesign --force`, deploy. 5. HANDOFF + `pour-<brand>/` pitch page. 6. Operator sends the two links via the chain's contact form.
