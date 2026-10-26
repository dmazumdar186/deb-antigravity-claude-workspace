# jeevana_site

Production website for Jeevana Gogula, Paris-based yoga teacher (operator's friend). Built 2026-10-26 with
the `/site-redesign` prospectus renderer adapted to a **production** site (indexable, no pitch page), per the
operator's brief: a dynamic cover where she moves through the 12 positions of Sūrya Namaskāra before any
scroll, everything a visitor needs within three scrolls, voluntary newsletter opt-in, class registration.

## Goal
Top-of-funnel marketing + registrations for her classes. Traditional yoga register (Yoga Sūtras 1.2 and 2.46,
the twelve Sūrya Namaskāra mantras with plain glosses) **without religious symbolism** (she lives in Paris; no
deities, no Om logo, no temple motifs). Footer signature "Designed by Debanjan Mazumdar · ProdCraft" → prodcraft.fyi.

## Inputs
- `deliverables/jeevana_site_2026-10-26/_raw_assets/` — 22 photos from the operator's Drive folder (gitignored,
  third-party faces stay out of git). Map and roles: `research/photos.md`.
- Facts: name, email jeevanagogula.gj22@gmail.com, Instagram jeevana.gogula, phone/WhatsApp +33 7 54 28 72 10.
  Everything else is a slot (`research/to_wire.md`): bio, address, timetable, prices, Facebook, domain.
- Env: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `OPENROUTER_API_KEY` (backdrop regen only).

## Tools / scripts
- `research/ingest_photos.py --src _raw_assets --out site/assets/img --sequence sn-01=… ` — EXIF-transposed
  webp ≤ 1600 px + `-m` variants + `manifest.json` with per-frame `focus`. Swapping a frame = re-run, no HTML edit.
- `.claude/skills/site-redesign/scripts/{gen_backdrop.py,render_hero_video.mjs,site_check.mjs,deploy.sh}`.
- `research/functional.mjs` (40 assertions incl. autoplay, scrub takeover, i18n, newsletter dialog, register
  mock, dead-link guard), `research/serve_csp.mjs` (serves with real `_headers`), `research/screens.mjs`
  (18-viewport cover matrix × 0/50/100 + named states).
- Backend: Cloudflare Pages Functions `site/functions/api/{subscribe,register,export}.ts`, KV `JEEVANA_KV`
  (id in `site/wrangler.toml`). `/api/export` is Basic-auth CSV (`EXPORT_USER`/`EXPORT_PASS` Pages secrets).

## Outputs
- Live: https://jeevana-yoga.pages.dev (Cloudflare Pages project `jeevana-yoga`); custom domain to bind when the
  operator gives it (CF dashboard → Pages → Custom domains, then update canonical/og/sitemap).
- `deliverables/jeevana_site_2026-10-26/HANDOFF.md` — review rounds, jury verdicts, measurements, to-wire list.

## Steps
1. Edit content: `site/js/i18n.js` (all strings EN/FR), `site/js/schedule.json` (timetable rows),
   `site/js/contact.json` (phone, whatsapp, facebook; empty = hidden, never a dead link).
2. `node research/functional.mjs` → N/N; `node .claude/skills/site-redesign/scripts/site_check.mjs --site site --pages /`.
3. `node research/screens.mjs` → reviewer agents read `screens/` (≤ 40 PNGs each); ship only on SHIP.
4. `bash .claude/skills/site-redesign/scripts/deploy.sh deliverables/jeevana_site_2026-10-26/site jeevana-yoga`.
5. Secrets once: `npx wrangler@4 pages secret put EXPORT_USER --project-name jeevana-yoga` (and `EXPORT_PASS`).

## Edge cases / learnings
- The operator's local folder (Windows OneDrive) is unreachable from cloud sessions; a Drive folder shared
  "anyone with the link" is readable via `https://drive.google.com/embeddedfolderview?id=<id>#list` +
  `uc?export=download&id=<file>` even when the Drive connector cannot see it.
- No plank was photographed: step 05 uses Parvatāsana (12-step Bihar form); 05/08, 03/10, 02/11 reuse files
  because the sequence repeats. Document any reuse in `photos.md`.
- Design jury (2026-10-26): the stadium series (low sun, long shadows) is the house look; monument snapshots
  (Eiffel) read as souvenirs — keep them to one supporting appearance, never the hero.
- Newsletter sending is not built: KV list only. Wire Brevo or similar with double opt-in before the first send.
