# Panel-pass consolidated fix brief (2026-10-26) — lenses 1,3,4,5,6,7,8,10,11 in (2 and 9 pending; fold them in when they land)
Decisions by the brain marked ►. Scope: backend, legal, ops, measurement. Visual items live in `review_round2.md`.

## A. Deploy correctness (lens 10)
1. Pages Functions must actually deploy: `wrangler pages deploy` is run **from `site/`** (`cd site && npx wrangler@4 pages
   deploy . --project-name jeevana-yoga --branch main --commit-dirty=true`). After deploy, probe `POST /api/register`
   with an invalid body → expect 400 JSON (not 405 HTML). Put this in the directive and in a `research/deploy.sh`.
2. Do not expose sources: add `site/functions/_middleware.ts` that returns 404 for `/wrangler.toml`, `/functions/*`,
   `/*.ts`, `/research/*`; verify with curl after deploy.
3. Cache busting: `css/styles.css?v=<short hash>` and `js/*.js?v=` written by a tiny `research/stamp.mjs` run before
   deploy (idempotent); `_headers` keeps 1 h on css/js, `no-cache` on html.

## B. Backend hardening (lenses 6, 10, 3)
4. `_lib.ts`: rate limiter in try/catch (KV failure → allow, `console.error`); body size cap 8 KB before parse
   (`content-length` + `text()` length); missing KV binding → 503 JSON `{error:"storage unavailable"}`.
5. `subscribe.ts`: phone stays as an **optional** field (► operator decision 2026-10-26, overrules the jury); the dialog shows email, phone (optional), consent; idempotent re-subscribe keeps the original `consent_ts`;
   store `unsubscribe_token` (random 24 bytes hex); record `{email, phone?, lang, source, consent_ts, consent_text}`.
6. New `GET /api/unsubscribe?t=<token>` → deletes the record, returns a tiny HTML page (EN/FR by `lang`). Copy on the
   site says "unsubscribe at any time" — now true; the link goes into every future newsletter (documented in to_wire).
7. `register.ts`: `expirationTtl` 24 months on `reg:` records (retention policy, stated in the privacy page); keep
   `consent_text` verbatim with the record.
8. `export.ts`: rate limit 10 / 10 min per IP; constant-time compare on equal-length padded strings; CSV with both
   lists; note the ~1,000-row KV read limit in the runbook.
9. Notification (lens 6, the launch blocker "nobody hears"): implement `notify()` in `_lib.ts`: if secret
   `BREVO_API_KEY` is set, POST a transactional email to `NOTIFY_TO` (default jeevanagogula.gj22@gmail.com) on every
   registration and subscription (subject "Nouvelle inscription — <name>"), failures logged and never block the
   visitor's success; if the secret is unset, `console.log` only. ► Operator action recorded in to_wire: create a free
   Brevo account, add the sender, set `BREVO_API_KEY` with `wrangler pages secret put`. Visitor confirmation email
   comes later, only after the notice works.
10. Error channel: `console.error` with `{service:"jeevana", route, error, count:1}` on every 5xx; on 429/5xx the
    front end shows the WhatsApp fallback line (main.js).

## C. Legal (lens 3, 7)
11. **Self-host fonts**: install `@fontsource/cormorant-garamond`, `@fontsource/inter`, `@fontsource/noto-serif-devanagari`
    (npm, in `research/`, not shipped), copy the needed woff2 (latin + latin-ext + devanagari subsets, weights used)
    into `site/assets/fonts/`, `@font-face` in styles.css with `font-display:swap`, remove the Google Fonts link and
    the Google origins from the CSP. Assert in site_check: no external request on load.
12. New page `site/privacy/index.html` (EN) with FR block toggled by the same i18n: Mentions légales (publisher:
    Jeevana Gogula, Paris; contact email; hosting: Cloudflare, Inc., 101 Townsend St, San Francisco) + Politique de
    confidentialité (purposes: class registration, newsletter; legal basis: consent; data: name, email, phone
    (optional), class, level, message; retention: registrations 24 months, newsletter until unsubscribe; processor:
    Cloudflare (KV, global replication); rights: access, rectification, deletion, withdrawal by email; no cookies,
    localStorage for language + dialog only). Footer link "Privacy · Mentions légales". Same CSS, paper body.
13. Copy accuracy: `about.c1/c3` "group classes, private sessions and workshops, in a studio and outdoors" → ►
    "Classes in Paris — group and private" (formats beyond that are to wire); "Studio address shared on registration"
    → "Location shared on registration" (EN/FR). JSON-LD: keep `email`, **drop `telephone`**; type `Person` with
    `jobTitle: Yoga teacher` + `sameAs: Instagram` (not an ExerciseGym — there is no verified studio).
14. Phone appears exactly twice on the page: the Contact row and the mobile bar (not footer, not JSON-LD).
    Footer: email + Instagram + Privacy; ProdCraft credit keeps the prodcraft.fyi link with `rel="noopener"` and
    **drops the mailto** (►).
15. HANDOFF.md names owners: site + domain + export login = Debanjan (ProdCraft) until handover; data controller and
    data requests = Jeevana (her email); and a line for the operator to record Jeevana's written OK on photos, phone
    and copy before the domain goes live.

## D. Rigor (lenses 1, 4, 8)
16. Fixture test `research/content_fixture.json`: the 12 triples (Devanagari, IAST, mantra, gloss EN, gloss FR) +
    the 2 sūtras; functional.mjs asserts i18n.js matches it exactly (both languages) and that the rail/mobile use it.
    Unify IAST: "Aśva Sañcālanāsana" everywhere (photos.md and i18n.js).
17. Named constants at the top of main.js for every timing/threshold (autoplay 900 ms, one cycle then hold,
    cover-end .8, fold-open .9, cover-out .2, mobile-bar .5, reveal failsafe 2500 ms, dialog delay 1200 ms / 35 s);
    read fps/seconds from hero.json; test names match probes (beats at the real boundaries); add a Pixel 7 console
    check; record Playwright and Pillow versions in functional.json.
18. Rail label `#B07A1C` on `#2A211A` = 4.24 → use `#C8923A` (≥ 4.5 on both cover inks); rail over photo always on
    the .72 scrim (round-2 §7). `#C4731A`/`#B07A1C` never as text on paper (keep `#9A5A12`).
19. glm_log.md: add sha256 of the shipped backdrop.js and the diff summary of hand edits.

## E. Measurement (lens 11; operator: "identify the necessary metrics")
20. First-party events, counts only, no PII: `POST /api/event {name}` with an allowlist
    (`cover_complete, deck_open, register_start, register_done, newsletter_open, newsletter_done, wa_tap, ig_tap,
    call_tap, lang_fr`) → KV `ev:<YYYY-MM-DD>:<name>` increment (non-atomic is fine); `GET /api/stats` behind the
    export auth returns the last 30 days as JSON. main.js sends them with `navigator.sendBeacon`.
21. Cloudflare Web Analytics: add the beacon only if the brain supplies a token at deploy (CSP needs
    `static.cloudflareinsights.com` script + `cloudflareinsights.com` connect); leave a `data-cf-beacon` slot.
22. hreflang: EN and FR point at the same URL → drop hreflang until `/fr/` exists; keep `lang` switching.
23. to_wire additions: Search Console verification (DNS TXT once the domain is bound), UTM on the Instagram bio link
    (`?utm_source=instagram&utm_medium=bio`), Brevo key, Jeevana's sign-off, timetable/price/trial terms (lens 5
    order: timetable → price → first-class terms → one consented testimonial → arrondissement + reply time).

## Verify
functional N/N (new: fonts self-hosted / no external request; privacy page 0 console errors; unsubscribe flow with a
mocked KV; event beacon allowlist; content fixture), site_check on `/` and `/privacy/`, 0 console errors.

## F. Lenses 2 and 9 (landed after the first cut)
24. Newsletter dialog never opens while focus is inside any form or while the Register panel is active; re-arm when
    the visitor leaves the form (assert in functional.mjs: focus a register input, wait > delay, dialog stays closed).
25. Autoplay prefetch: on frame n, `new Image().src` = frame n+1 (and n+2) so slow 4G never skips a frame; the first
    frame stays preloaded.
26. Inline error text under invalid fields (EN/FR), not only a mark; after a failed submit the mailto fallback carries
    the typed fields in the body; 404 page honours the saved language.
27. Directive and docs: full ingest command incl. `--zoom` for sn-03/sn-10 in `photos.md`; serve + URL before
    functional/screens; one working directory (repo root); `wrangler pages secret list` as the check; "43" not "40".

## Supplied by the brain (2026-10-26)
- Cloudflare Web Analytics site created for `jeevana-yoga.pages.dev`: beacon token `f7ff129092344aca8fd504fcca79bc05`
  (public, ships in HTML). Item 21 is therefore ON: add
  `<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token":"f7ff129092344aca8fd504fcca79bc05"}'></script>`
  and extend the CSP (`script-src` + `connect-src`) accordingly. This is the one permitted external script (cookieless,
  first-party vendor = the host). When the custom domain is bound, add it as a second host on the same site.
