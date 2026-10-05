---
name: site-redesign
description: Redesign an existing website or build one from scratch as a zero-dependency static concept, test it on desktop + mobile, deploy to Cloudflare Pages and hand over a pitch page. Triggers on "redesign <site>", "rebuild their website", "build a site for", /site-redesign.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, WebSearch, WebFetch
user_invocable: true
---

# Site redesign — research → build → test → deploy → pitch

Consolidated 2026-10-05 from GAIA Talent, GreenJobs, h2 Recruit and Midas France. One invocation
takes a URL (or a brief for a from-scratch build) to a live `*.pages.dev` link plus a pitch page the
operator can forward. The operator never runs a command; the brain routes, workers build.

## Inputs
- `$ARGUMENTS`: target URL or brand name, optional language (`fr`, `en-GB`…), optional prospect name
  for the pitch page (`for-<name>/` or `pour-<name>/`), optional theme hints from the operator.
- Env: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` (present in the cloud env). Chromium at
  `/opt/pw-browsers` for Playwright.

## Outputs
- `deliverables/<slug>_redesign_<YYYY-MM-DD>/site/` — `index.html`, `css/styles.css`, `js/main.js`,
  `assets/` (real logo, favicon), `<pitch>/index.html`. Plus `screens/` and `HANDOFF.md`.
- Live: `https://<slug>-redesign.pages.dev/` (noindex). Never github.io, never an artifact link.
- A 4–5 line outreach message in the prospect's language, signed
  "Debanjan, Founder, ProdCraft, debanjan@prodcraft.fyi".

## Process (brain does steps 1, 4-gate, 7; workers do 2, 3, 5)

### 1. Research (brain, one batched message, ≤ 10 calls)
- Try the site directly (`curl -A "Mozilla/5.0"`, WebFetch). Big chains 403 bots — fall back to
  `WebSearch` with `site:<domain>` queries, Wikipedia (facts + logo file), franchise/trade press,
  review platforms (Trustpilot, Custplace, Google). Firecrawl/Tavily MCP keys are often invalid in
  cloud (401); don't retry them more than once.
- Collect ONLY verifiable facts: services, live offers with exact wording and end dates, promises
  (guarantees, SLAs), network size, founding year, parent group, slogan, booking flow, phone/hours
  model, review score. Write them into the worker brief. Invent nothing; placeholders are labelled.
- **Logo:** fetch the real asset (Wikimedia Commons file page → `upload.wikimedia.org` URL with an
  identifying User-Agent; or the site's own `/favicon`, `og:image`). Never a text wordmark.
- Sector best practice: one `WebSearch` "<sector> website best practices conversion <year>". Fold the
  top 5 into the brief (e.g. garages: phone + booking + hours above the fold, starting prices,
  warranty as trust, per-service pages, one-handed mobile).
- Read `reference/build_rules.md` before briefing.

### 2. Build (one `general-purpose` worker, foreground, complete brief)
Use `reference/worker_brief_template.md`. The brief must contain: palette (stay in the brand's own
register — Midas is yellow+light, not yellow+black), the fact list, the section list in order, the
engineering rules, the verification commands, and the report format. The worker verifies with
Playwright before reporting (section 4). Budget: index+css+js ≤ 120 KB, zero third-party JS.

### 3. Pitch page (same worker)
`for-<name>/` (EN) or `pour-<name>/` (FR): what it is (concept on our domain, nothing touches
their site, facts from public sources), a "Today / Concept" table (6 rows), "what doesn't exist on
your site yet" (2–3 items), "next if you want it", signature. Mirror
`deliverables/h2recruit_redesign_2026-09-30/site/for-ian/index.html` and
`deliverables/midas_redesign_2026-10-05/site/pour-midas/index.html`.

### 4. Test gate (worker runs, brain reads the summary; nothing deploys red)
```bash
node .claude/skills/site-redesign/scripts/site_check.mjs --site <site-dir> [--mobile-only-reveal]
```
Serves the folder, runs desktop 1440×900, Pixel 7 and iPhone 13 emulation (touch), and a
reduced-motion context. Fails on: any page error, horizontal overflow, any `.reveal` element still
`opacity:0` in the viewport 150 ms after a 2600 px fling (the Pixel 8 Pro bug), tap targets < 44 px
on phones, inputs < 16 px font on phones, fixed bottom bar overlapping the last CTA, fonts/scripts
from more than one third-party host. Writes `screens/check-*.png`. Then the brain **looks at** the
mobile full-page PNG and the hero PNG (Read tool) — a DOM pass is not a visual pass. For a client
release, also run `/human-eye-test`.

### 5. Deploy (brain, one command)
```bash
bash .claude/skills/site-redesign/scripts/deploy.sh <site-dir> <slug>-redesign
```
Creates the Pages project if missing (`--force` once, wrangler 4.136+), deploys, curls the live URL
and the pitch page for 200, compares live CSS/JS md5 to local. Cloudflare's CDN can serve the old
stylesheet for ~1 min; the script polls. Note: the sandbox Chromium cannot reach `*.pages.dev`
through the proxy — verification is on identical local files, say so in the handoff.

### 6. Handoff + commit (brain)
Write `HANDOFF.md` (live URLs, target, research facts with sources, what it is, verified, redeploy
line, not done, next steps). `git add deliverables/<dir>`, commit, push the branch, fast-forward
`main`, push `main` (operator order 2026-10-01). Never commit `.tmp/` or screenshots over 2 MB.

### 7. Reply to the operator
Both links first. Then: what changed, what was verified and how, caveats, the outreach message in
the prospect's language. Offer the next shop as the same loop.

## Feedback loop
Operator feedback on a live concept → reproduce under emulation **before** changing anything
(Pixel 7 for Android reports, iPhone 13 for iOS), name the root cause, fix, re-run step 4, redeploy,
append a `vN` block to `HANDOFF.md`. Record any new rule in `reference/build_rules.md`.

## Related
- `/human-eye-test` — release gate with reviewer agents reading every PNG.
- `/impeccable` — design critique/polish on an existing surface.
- `design-website` (legacy) — Sheet-driven buildinamsterdam template generator; superseded by this
  skill for prospect concepts.
