# Build rules — every rule here was paid for once

## Identity
1. **Keep the brand's real logo** in header, footer and pitch page (operator order 2026-10-05).
2. Stay in the brand's own light/dark register unless the operator asks (Midas: yellow + cream, not
   yellow + black). "Make it feel like gold" = gradients + one shimmer, not a dark theme.
3. Use their current slogan, offer wording and guarantees verbatim, with end dates. No invented
   quotes, names, prices or review scores. Weak public review scores are never shown; build a
   per-location reviews block "à brancher" and sell review management in the pitch.
4. Any named third party on the page (employer logo, partner) needs a build-time assertion that
   the claim is true (GreenJobs 2026-09-22).

## Engineering
- Zero dependencies: hand-rolled motion, inline SVG, one Google Fonts link (or self-hosted), one
  IIFE, every `querySelector` guarded, no globals. `lang` set, skip link, `focus-visible`, aria on
  menus/dialogs, `<dialog>` for modals, `inert` on closed mobile menus.
- Budgets: index+css+js ≤ 120 KB; `.reveal` transitions ≤ .45 s; no layout-property animation.
- **Visibility is never JS-gated on phones.** `< 800px`: `.reveal` is always painted; motion is
  additive. On desktop: IntersectionObserver threshold `.01`, rootMargin `0 0 8%`, plus a 2.5 s
  failsafe that adds `is-in` to everything and a `window.error` handler that removes `html.has-js`.
- Mobile layout: every desktop grid gets a `< 800px` rule (rows → 2 columns with grid-areas; a
  4-column list row collapses otherwise). Inputs 16 px on phones (iOS zoom), tap targets ≥ 44 px,
  `inputmode`/`autocapitalize`/`enterkeyhint`, a fixed bottom bar with `scroll-padding-bottom` and
  extra padding on the last form so it never covers the confirm button.
- Hero: `min-height:100svh` (fallback `100vh`), `overflow:hidden`, `isolation:isolate`. SVG labels
  that stack (`lamp-ok` under `lamp-label`) are hidden under 800 px.
- Booking/search bar: one full-width row at ≥ 800 px (`grid-template-columns: 1.1fr 1.3fr 1.1fr auto`,
  `min-width:0` on fields, nowrap labels); below 800 px two columns then full-width button.
- Reduced motion: every animation has a `prefers-reduced-motion` static end state; rotating words
  stop on the first item; tickers wrap.
- Contrast: body ≥ 4.5:1 (gold on cream fails: `#A77B00`/`#FFF6DC` = 3.6:1; use `#8A6500` = 4.9:1).
- Fonts only load on the live URL (sandbox proxy TLS); screenshots render fallback fonts — judge
  layout, not type, in the sandbox.

## Conversion patterns (local service businesses)
- First screen: phone (tap-to-call), booking, hours, location. An emergency path ("Je suis en
  panne") first under the header on phones.
- Live offer with countdown; free diagnostics/consults as a ticker; services as filterable rows
  that pre-fill the booking form; promise strip (SLA, guarantee, clear quote).
- Trust: real network numbers, founding year, parent group; placeholders for photos and reviews.

## Research
- Direct fetch of big chains 403s (Akamai); Wayback also blocked. Use `WebSearch site:` queries,
  Wikipedia API (space calls ~20 s; rate-limited), trade press. Firecrawl/Tavily keys: try once.
- Wikimedia logo download needs an identifying `User-Agent` or it returns an HTML error page.

## Deploy
- Cloudflare Pages only; project `<slug>-redesign`; `wrangler pages project create --force` once
  (wrangler ≥ 4.136 otherwise delegates to Workers and fails). `--commit-dirty=true` on deploy.
- Poll the live CSS for a marker after deploy; the CDN lags ~30–60 s.
- `pkill` in a `&&` chain aborts the chain when nothing matches — run it on its own line.
