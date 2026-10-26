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

## v2 build — 2026-10-26 (brief_v2 "Twelve breaths, drawn then real"; not deployed, not committed)
- Cover rewritten: paper stage, cut-out figure on a ground line (86 % desktop / 78 % phones), 13 scrubbed states
  (14·100vh desktop, 10·100svh phones), S0 contour self-draws at load, autoplay S1→S3, S9–S11 wipe to the photograph.
  Drawing layer per art direction (2026-10-26): traced contour + 18 % graphite wash; pencil renders only for the About portrait.
  Backdrop canvas, hero videos and the v1 `assets/img` set deleted; Kling slot dormant in `assets/film/hero.json`.
- Figures: `research/ingest_photos.py --cutouts _raw_assets/cutouts_v2 --pencil _raw_assets/pencil --out site/assets/fig`
  re-applies each cut-out mask to the full-resolution original (×2.4, native pixels, never upscaled), touch-up pass,
  webp q92 srcset + wash + contours.json + manifest.json.
- Ops/legal: fonts self-hosted, `_middleware.ts`, unsubscribe / event / stats endpoints, notify() via Brevo, privacy page,
  `research/stamp.mjs` + `research/deploy.sh` (deploy from inside `site/`).
- Owners: site, domain and export login = Debanjan (ProdCraft) until handover; data controller and data requests =
  Jeevana (jeevanagogula.gj22@gmail.com).
- Operator to record before the domain goes live: Jeevana's written OK on the photos, the phone number and the copy: ______
- Open slots: `research/to_wire.md`. KV id in `site/wrangler.toml` unchanged.
- Skill change: `.claude/skills/site-redesign/scripts/site_check.mjs` gained `--allow-hosts` (permitted third parties
  such as the Cloudflare beacon); run with `--allow-hosts cloudflareinsights.com`.
