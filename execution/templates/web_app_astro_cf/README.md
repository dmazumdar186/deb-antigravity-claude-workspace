# web_app_astro_cf — reference template

Astro 5.x + Cloudflare Pages web-app template with the workspace's audit
stack baked in. Every new web app in this workspace should scaffold from
here.

## What it gives you

- **Astro 5.x + Tailwind 3** — SSG by default, Pages Functions for API.
- **Cloudflare Pages** — `wrangler.toml` with observability enabled,
  `_headers` file with sane CSP/HSTS/nosniff/frame-deny defaults.
- **i18n scaffold** — FR default, EN mirror under `/en/`.
- **A11y baseline** — skip-link, `role="main"`, focus-visible outline.
- **Global middleware** — Basic-Auth gate for `/dashboard/*` + `/api/*`,
  KV-backed per-IP rate limit.
- **Health endpoint** — `functions/api/health.ts` returns JSON with
  upstream status + secret-presence + build SHA.
- **LLM scaffold** — `functions/api/llm.ts` with Gemini-default /
  Anthropic-fallback per `~/.claude/rules/model-tier.md`, cost logging
  in **EUR** per `~/.claude/rules/currency-eur.md`.
- **Test tiers** — unit (Vitest), e2e (Playwright), acceptance gate
  (Python), front-door synthetic (bash). All wired into CI.
- **Pre-commit hook** — blocks commits that leave untracked
  `functions/*.ts` (kills the yoga_jitendra 2026-08-03 disaster class).
- **CI** — GitHub Actions runs SAST -> unit -> build -> preview deploy
  -> acceptance -> front-door, blocks main-branch merge on any failure.
- **HANDOFF.md + HARDENING.md** — with the mandatory-audit-stack
  verdict table pre-scaffolded.

## Rules it satisfies

Every always-active rule in `~/.claude/rules/` gets a compliance line in
`HARDENING.md` — including `front-door-synthetic`,
`output-acceptance-gate`, `live-artifact-acceptance`, `model-tier`,
`currency-eur`, `python-hardening`, `security`, `always-parallelize`.

Rules the template alone cannot satisfy (need per-project work):
`prior-art-first`, `panel-pass`, `mandatory-audit-stack`.

## Scaffold a new project

```bash
py execution/templates/scaffold_web_app.py \
  --name my-new-site \
  --domain my-new-site.example.com \
  --output execution/personal_workflows/my_new_site
```

This will:
1. Copy the template tree to `--output`.
2. Replace `<PROJECT_NAME>` and `<PROJECT_DOMAIN>` placeholders.
3. Rename `tests/acceptance_PROJECT_NAME.py` and
   `tests/front_door_PROJECT_NAME.sh` to use the project slug.
4. `git init` + install pre-commit hook via `git config core.hooksPath`.
5. Make an initial commit.
6. Print the "next steps" runbook.

## Manual "install" after scaffold

```bash
cd <output-dir>
npm install                  # first-time only
npm run dev                  # local at localhost:4321
npm run test:unit            # tier 1
npm run build                # produces dist/
```

After first deploy:

```bash
SITE_URL=https://<PROJECT_DOMAIN> bash tests/front_door_<slug>.sh
SITE_URL=https://<PROJECT_DOMAIN> py tests/acceptance_<slug>.py
```

## Prior-art note

The template is patterned after `execution/personal_workflows/yoga_jitendra_site/`
because that codebase is the proven Astro+CF+i18n+Basic-Auth reference
in this workspace. It also incorporates every fix that landed in the
2026-08-04 workspace hardening audit (untracked-function gate,
verdict-table scaffold, tier-4 test hierarchy). We did NOT crib from
`npm create cloudflare` — its output is generic and lacks the workspace's
audit-stack integration.

## Updating the template

When a workspace rule evolves, propagate changes into this template via
the process documented in `TEMPLATE_CHANGES.md`.
