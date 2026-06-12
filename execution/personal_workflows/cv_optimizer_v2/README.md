# CV Optimizer v2 — Deploy Guide

## Architecture

Browser (Cloudflare Pages) → Pages Function proxy (server-side secret holder) → Cloudflare Worker → Firecrawl (JD scrape) + Gemini Flash (optimize) → CVSpec JSON → HTML preview → browser Print to PDF. The Pages Function is the key security layer: it holds `WORKER_SECRET` in server-side env vars and injects the header before forwarding to the Worker. The browser never sees any secrets.

```
Browser (Pages static)
  └─ POST /api/optimize (same-origin)
       └─ Pages Function (functions/api/optimize.js)
            │ reads WORKER_URL + WORKER_SECRET from Pages env
            └─ HTTPS POST to Worker with X-Worker-Secret header
                  └─ Cloudflare Worker (cv-optimizer-api)
                       ├─ Firecrawl scrape (if jd_url)
                       ├─ Gemini Flash (responseSchema)
                       └─ CVSpec JSON → back to browser
```

## Prerequisites

- `wrangler` installed globally: `npm install -g wrangler`
- `.env` contains `GEMINI_API_KEY` and `FIRECRAWL_API_KEY`
- Free Cloudflare account at dash.cloudflare.com
- Run `wrangler login` (browser auth, one-time)

## Worker Deploy (steps 1–5)

```bash
# From execution/personal_workflows/cv_optimizer_v2/worker/
cd worker

# Step 1: Create KV namespace for rate limiting
wrangler kv:namespace create RATE_LIMIT
# Copy the id and preview_id values into wrangler.toml [[kv_namespaces]] block

# Step 2: Set secrets (prompted interactively — do NOT paste into wrangler.toml)
wrangler secret put WORKER_SECRET
# Generate a 32-char random: openssl rand -hex 16
# Or PowerShell: -join ((48..57+65..90+97..122) | Get-Random -Count 32 | %{[char]$_})

# Step 3: Set Gemini key
wrangler secret put GEMINI_API_KEY
# Paste from .env

# Step 4: Set Firecrawl key
wrangler secret put FIRECRAWL_API_KEY
# Paste from .env

# Step 5: Deploy
wrangler deploy
# Note the Worker URL printed (e.g. https://cv-optimizer-api.<account>.workers.dev)
```

Verify: `curl https://cv-optimizer-api.<account>.workers.dev/api/health` should return JSON with `status: "ok"`.

## Pages Deploy (steps 6–8)

```bash
# From execution/personal_workflows/cv_optimizer_v2/web/
cd ../web

# Step 6: Initial deploy
wrangler pages deploy . --project-name=cv-optimizer --compatibility-date=2024-01-01
# Note the Pages URL (e.g. https://cv-optimizer.pages.dev)

# Step 7: Set server-side env vars (NEVER in client JS — Pages Function reads these)
wrangler pages secret put WORKER_URL --project-name=cv-optimizer
# Paste Worker URL from Step 5

wrangler pages secret put WORKER_SECRET --project-name=cv-optimizer
# Paste the SAME secret as Step 2

# Step 8: Re-deploy so env vars take effect
wrangler pages deploy . --project-name=cv-optimizer
```

Verify: `curl https://cv-optimizer.pages.dev` returns HTML containing `<input id="jd-url">`.

## Optional: Cloudflare Access Gate (step 9)

Recommended even for personal use — adds email OTP gate, free for ≤50 users.

1. Go to `dash.cloudflare.com/zero-trust` (NOT Pages Settings — Cloudflare moved this in 2023).
2. Access → Applications → Add → Self-hosted.
3. Domain: your Pages URL (e.g. `cv-optimizer.pages.dev`).
4. Policy: Include → Emails → `debanjan186@gmail.com`.
5. Save. Takes effect immediately.

## Smoke Test (steps 10–11)

```bash
# Step 10: Open the Pages URL in browser
# - Upload your CV PDF
# - Paste a WTTJ or Indeed job posting URL
# - Click "Optimize"
# - Confirm preview appears with name, experience, skills, ATS score
# - Click Print → Save as PDF → confirm 1-2 page A4

# Step 11: Security check
# Browser DevTools → Sources → app.js
# Confirm: NO WORKER_SECRET, NO API keys visible
# Only a fetch() call to /api/optimize (same-origin)
```

## Local Dev (no deploy needed)

Worker local dev:
```bash
cd worker
npx wrangler dev
# Worker runs at http://localhost:8787
# Test: curl http://localhost:8787/api/health
```

Frontend local dev:
```bash
cd web
python -m http.server 8080
# Open http://localhost:8080
# NOTE: local dev cannot call the Pages Function (/api/optimize returns 404)
# For local UI iteration, temporarily hardcode a mock CVSpec in app.js
# or point directly at a deployed Worker with a test secret
```

## Troubleshooting

**1. `wrangler deploy` fails with "account_id not set"**
- Run `wrangler whoami` — if invalid, run `wrangler login` again.
- Or set `CLOUDFLARE_ACCOUNT_ID` env var from the Cloudflare dashboard (top-right → Account ID).

**2. `/api/optimize` returns 401 Unauthorized**
- Pages Function is not injecting `X-Worker-Secret` correctly.
- Check: `wrangler pages secret list --project-name=cv-optimizer` — both `WORKER_URL` and `WORKER_SECRET` must appear.
- Re-deploy pages after setting secrets (Step 8 is mandatory).

**3. `jd_scrape_failed` error on a non-LinkedIn URL**
- Firecrawl returned <200 chars or a login-wall keyword. The page may require JS rendering.
- Workaround: paste the JD text directly into the textarea (first-class path, same quality).

**4. PDF parse returns empty text**
- The PDF is image-based (scanned). pdf.js cannot extract text from scanned images.
- Fix: use a text-layer PDF (save from Word/Google Docs, not a scan).

**5. Gemini returns 429 / quota exceeded**
- Free tier is 15 RPM. Wait 60 seconds and retry.
- If hitting quota repeatedly, check Gemini Studio for usage. Personal use should stay well under 1500 RPD limit.
