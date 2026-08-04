# HANDOFF.md — <PROJECT_NAME>

*Living document. Update after every milestone.*

**IMPORTANT**: Do NOT write "shipped", "live", "ready", "done", "complete",
"good to go", or any synonym in this file until:

1. The mandatory-audit-stack (`~/.claude/rules/mandatory-audit-stack.md`)
   has been invoked and its verdict table appears below.
2. The front-door synthetic has passed **5 consecutive days** against the
   live production URL (`~/.claude/rules/front-door-synthetic.md`).

Until then, the correct status wording is: `LIVE-PROBATIONARY day N of 5`.

---

## Current status

**Status**: LIVE-PROBATIONARY day 0 of 5
**Deploy URL**: (fill in after first `wrangler pages deploy`)
**Health endpoint**: <SITE_URL>/api/health
**Last front-door-green day**: (none yet)

## Architecture (one paragraph)

Astro 5.x static site + Cloudflare Pages Functions for API. Basic-Auth
middleware protects `/dashboard/*` and `/api/*` (except `/api/health`).
KV binding `APP_KV` for rate limits + telemetry. LLM calls default to
Gemini free tier per model-tier rule; Anthropic Sonnet 4.6 if
`ANTHROPIC_API_KEY` set.

## What's verified live

*(fill after each mandatory-audit-stack run)*

| Auditor | Verdict | Evidence |
|---|---|---|
| Front-door synthetic | ??? | |
| Customer-POV / acceptance | ??? | |
| Anneal | ??? | |
| Panel: Karpathy | ??? | |
| Panel: Cherny | ??? | |
| Panel: Amodei | ??? | |
| Panel: Research | ??? | |
| Test suite (unit + e2e) | ??? | |
| Adversarial loop | ??? | |

## Honest gaps

*(list every skipped item, deferred design decision, or external dep)*

- [ ] Set `site` in `astro.config.mjs` to the production domain.
- [ ] Provision `DASHBOARD_PASS` secret on the Pages project.
- [ ] Add real content to `src/pages/index.astro`.
- [ ] Remove `Disallow: /` from `public/robots.txt` before public launch.
- [ ] Wire GitHub Actions secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

## One-line revert

```bash
git revert HEAD && git push
# then wrangler pages deployment rollback --project-name=<PROJECT_NAME>
```

## Change log

- YYYY-MM-DD — Scaffolded from `execution/templates/web_app_astro_cf/`.
