# Jeevana site — handoff (2026-10-26)

- Operator to overrule if wanted: the newsletter pop-up no longer asks for a phone number (design jury, review round 1, H33). Phone stays as an optional field on the Register form only; `/api/subscribe` still accepts an optional phone.
- Open slots: `research/to_wire.md`. KV id in `site/wrangler.toml` is real; keep it.

## Deploy 1 — 2026-10-26 (operator: "deploy it")
- Live: https://jeevana-yoga.pages.dev/ (Cloudflare Pages project `jeevana-yoga`, deployed from the committed
  round-1 build via `git archive HEAD:…/site` → `wrangler pages deploy .` run inside the site dir).
- Verified live: `/` 200, css/js/manifest 200, `/functions/api/*.ts` 404 (sources not served), `POST /api/register {}`
  → 400 JSON, `POST /api/subscribe {}` → 400 JSON, `/api/export` → 401 (secrets unset), probe subscription → 200.
  Headers live: HSTS, CSP, X-Frame-Options DENY. `/wrangler.toml` is served (200) — carries only the KV id; the ops
  round adds a middleware 404 for it.
- Pending on this deploy: visual round 3 (review_round2.md), ops/legal round (panel/00_fix_brief.md), round-3 eye
  review, then redeploy.
