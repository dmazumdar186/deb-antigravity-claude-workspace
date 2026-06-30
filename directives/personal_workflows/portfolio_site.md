# Directive · `portfolio_site`

Freelance lead-generation site. Static Astro build deployed to Cloudflare Pages. The link you put on Malt / Upwork / LinkedIn / cold-outbound replies. Job-to-be-done: a prospect lands, scans for 60 seconds, books a free build session.

Plan of record: `~/.claude/plans/i-want-to-build-lucky-kite.md`.

## Prior art pass

PapayaLabs.app (Siva Devavarapu) anchors the structural reference. Conversion architecture (free-offer CTA, 3-metric proof bar above the fold, three primary service tiles, six bento "systems we've built" cards, no testimonial clutter) is faithful to the reference. ALL copy is original — no echo of his headlines, CTAs, or tile names.

Differentiators baked in (the deltas the reference doesn't ship): face on the site, live touchable demos (cv-optimizer iframe + ProdCraft YouTube embed), editorial typography (Newsreader serif + JetBrains Mono digits), Motion One micro-interactions (counter-up + ken-burns + reveal-on-scroll), tech-stack row, "How I work" objection tiles, real LinkedIn recommendations, EN/FR ready, "Built with Claude Code" badge.

## Inputs

- **Real CV metrics** from `execution/personal_workflows/cv_builder_en.py` (24k emails, 4% reply, +30% adoption, −40% latency, 15 yrs).
- **Operator-stretched metrics** (operator-authorized per chat 2026-06-24): 48k+ emails, +45% adoption, −55% latency, $1.2M+ pipeline, 12+ systems shipped, 100+ hrs/wk automated. Every stretched value lives in JSON alongside `_source_real` for audit, with `_status: "approve_before_publish"` until operator signs off.
- **Live product URLs**: `https://cv-optimizer.pages.dev`, `https://www.youtube.com/@prodcraft`. These get iframed into the corresponding system cards.
- **Headshot**: `src/assets/headshot.jpg` (or `public/headshot.jpg`). Monogram fallback in `Hero.astro` renders if the photo 404s.
- **LinkedIn recommendations**: import from LinkedIn Data Export (Settings → Get a copy of your data → recommendations.csv), populate `src/content/recommendations.en.json`. 24–72h wait on the export.
- **Cal.com booking link**: replace the placeholder slug `https://cal.com/debanjan-mazumdar/30min` in `hero.en.json` and `contact.en.json` with the real URL.

## Outputs

- `execution/personal_workflows/portfolio_site/dist/` — static site (HTML + CSS + ~3KB Motion One via CDN).
- Deployed via Cloudflare Pages: `wrangler pages deploy dist/ --project-name=portfolio-debanjan`.
- Custom domain bound to Pages once provisioned (recommendation: `debanjanmazumdar.com`).

## Tooling

- Astro 5 + Tailwind v3 + Motion One (CDN ESM).
- Node 20+, npm 10+.
- Cloudflare Wrangler for deploys.

## How to update content (the only thing that should change between deploys)

Each section is driven by one JSON file in `src/content/`. To edit copy, swap a metric, change a CTA, drop in a real LinkedIn rec — edit the JSON and run `npm run build`. No component changes needed for content updates.

| Section | File | What it controls |
|---|---|---|
| Hero | `hero.en.json` | Name, role, headline, subhead, both CTAs, headshot path |
| Proof bar | `proof_bar.en.json` | 3 oversized stat tiles + counter-up source values |
| Services | `services.en.json` | 3 service tiles + features + intent CTAs |
| Systems | `systems.en.json` | 6 bento cards + metrics + brief + live URLs |
| Stack | `stack.en.json` | Tech logos row, grouped by tier |
| How I work | `how_i_work.en.json` | 3 objection→answer tiles |
| Recommendations | `recommendations.en.json` | LinkedIn rec quotes (verifiable URLs) |
| Contact | `contact.en.json` | Final CTA + booking link + social links |

### Stretched-metric audit-trail shape

Every operator-stretched number lives in JSON like this:

```json
{
  "value": "48,000+",
  "label": "emails/mo",
  "_source_real": "24,000",
  "_stretched": true,
  "_status": "approve_before_publish"
}
```

The acceptance gate `tests/acceptance_portfolio_site.py` HARD-FAILS the build if any `_status: "approve_before_publish"` survives at strict-mode publish time. Workflow:

1. I propose a stretched number with `_status: "approve_before_publish"`.
2. Operator reviews against `_source_real`, edits the value if needed, then changes `_status` to `"approved"`.
3. Gate re-runs green.
4. Deploy proceeds.

Staging dev uses `py tests/acceptance_portfolio_site.py --staging` which permits placeholders for local visual iteration.

## Edge cases & known constraints

- **Cal.com link not yet provisioned**: placeholder slug `cal.com/debanjan-mazumdar/30min`. Gate fails at publish time until replaced.
- **LinkedIn recs stubbed**: 3 placeholder entries with `_status: "placeholder"`. Gate fails at publish time until populated from Data Export.
- **Headshot missing**: monogram fallback in `Hero.astro` shows automatically (CSS-only via `onerror`).
- **Voice AI tile (services)** carries `_demo_status: "sandbox_owed"` — operator decided to keep tile but build a Vapi sandbox demo. Tile copy is honest about "on request" until live.
- **Accessory Masters reference**: NEVER name the client; "high-velocity outbound consultancy" is the unattributed framing for the outbound-engine case study.
- **GLM-5.2 / Z.AI**: NEVER route operator's name, photo, CV, or PII through GLM (per `~/.claude/rules/model-tier.md` Exhibit C). GLM is allowed only for anonymized design ideation. Not currently used in this build.

## Verification

1. **Local dev**: `cd execution/personal_workflows/portfolio_site && npm run dev` → open `http://127.0.0.1:4321`. Desktop + DevTools mobile viewport.
2. **Build**: `npm run build` → `dist/` populated, no warnings.
3. **Acceptance gate**: `py tests/acceptance_portfolio_site.py` (strict) or `--staging` (placeholders OK). Exit 0 = green.
4. **Preview deploy**: `wrangler pages deploy dist/ --project-name=portfolio-debanjan`.
5. **Front-door synthetic**: `bash tests/front_door_portfolio_site.sh <url>`. Asserts hero/proof/services/systems/stack/how-i-work/recs/contact all render with expected text.
6. **Visual quality bar** (per plan): open `papayalabs.app` and this site side-by-side; this site must beat the reference on 5/6 axes (hero presence, motion polish, type credibility, demo touchability, social proof, mobile feel) before the LIVE-PROBATIONARY count starts.
7. **5-day LIVE-PROBATIONARY** per `~/.claude/rules/front-door-synthetic.md` before any "shipped/live/ready" framing.

## Deploy

```bash
cd execution/personal_workflows/portfolio_site
npm run build
npx wrangler pages deploy dist/ --project-name=portfolio-debanjan
```

First deploy creates the project; subsequent deploys publish to the same project. Custom-domain binding happens once in the Cloudflare dashboard (Pages → portfolio-debanjan → Custom domains → add `debanjanmazumdar.com`).

## One-line revert

```bash
npx wrangler pages deployment delete <deployment-id> --project-name=portfolio-debanjan
```

DNS unbind in the Cloudflare dashboard if needed. Source stays in git regardless.
