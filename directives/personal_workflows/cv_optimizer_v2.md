# CV Optimizer v2 — Cloudflare Pages + Worker

## Purpose

Personal ATS-optimized CV generator. Paste a job posting URL (or JD text) + upload a CV PDF; receive an optimized CV that matches the JD's requirements while staying truthful, ready to print to PDF. 100% free (Gemini Flash + Cloudflare Pages + Worker free tiers). Personal use only — protected by Cloudflare Access if exposed publicly.

## When to invoke

- Debanjan applies to a new role and wants an ATS-aligned version of his CV in <30s.
- v1 (`cv_optimizer_agent.py`) is still available as the offline CLI fallback for paid Anthropic optimization or when Gemini is rate-limited.

## Inputs

- `cv`: PDF file — uploaded via the web form; pdf.js parses to text client-side.
- `jd_url`: string (optional) — public job posting URL. Works on WTTJ, Indeed, Greenhouse, Lever, company career pages.
- `jd_text`: string (optional) — JD text pasted directly. Used as fallback when the URL is login-walled (LinkedIn) or thin.

At least one of `jd_url` or `jd_text` must be provided.

## Outputs

- HTML preview of the optimized CV (live in browser iframe).
- A4 1-2 page printable PDF (via browser's "Print → Save as PDF").
- Inline ATS score (0-100) + recommendations list (not auto-applied).
- Detected language (en / fr / es / de).

## Exit Criteria (declarative — read this before claiming "done")

The system is "done" when ALL of these hold (each must be machine-verifiable):

- `worker/` deploys via `wrangler deploy` with exit code 0 and the printed URL responds 200 on `GET /api/health`.
- `web/` deploys via `wrangler pages deploy . --project-name=cv-optimizer` with exit code 0 and the printed URL serves `index.html` over HTTPS.
- `wrangler pages secret list --project-name=cv-optimizer` shows both `WORKER_URL` and `WORKER_SECRET` set.
- `curl https://<pages-url>` returns HTML containing the form (`<input id="jd-url">` present).
- Browser DevTools → Sources → `app.js` contains NO secret strings (no `WORKER_SECRET`, no API keys).
- Posting a valid CV PDF + a WTTJ JD URL returns a CVSpec JSON with at least: `language_detected`, `ats_score > 0`, `name`, `experience.length >= 1`, `skills.length >= 1`.
- Print → Save as PDF produces a 1-2 page A4 document with all sections visible.
- After 3 sample runs, Cloudflare dashboard shows $0.00 spend and Gemini Studio shows the calls under the free quota.

## Scripts (Layer 3)

- `execution/personal_workflows/cv_optimizer_v2/worker/` — Cloudflare Worker (TypeScript). Handles auth, rate-limit, Firecrawl scraping, Gemini optimize.
- `execution/personal_workflows/cv_optimizer_v2/web/` — Cloudflare Pages static frontend + Pages Function proxy.
- `execution/personal_workflows/cv_optimizer_v2/prompts/` — system_prompt.md + cv_response_schema.json + test_schema.js (one-shot schema validation).

## Edge cases

- **JD URL behind login (LinkedIn)** → Worker returns `{error: "jd_scrape_failed", reason: "login_wall"}`; frontend banner directs user to the textarea + auto-focuses it.
- **PDF is image-only / scanned** → pdf.js extracts no text; cv_status shows "Failed to parse" + user prompted to upload a text-extractable PDF.
- **CV too long (>50K chars)** → Worker returns 400; user trims or splits before retrying.
- **Gemini quota exceeded (free tier 15 RPM)** → Worker returns 502 with Gemini's error in detail; user waits 1 min before retrying.
- **Cloudflare Access bouncing user** → check Zero Trust dashboard policy includes the user's email.
- **Worker rate limit (10/hr/IP)** → user gets 429 with retry_after_seconds; legitimate use should never hit this.
- **AM lockdown reminder**: this tool does NOT touch AM credentials, endpoints, or data. AM remains frozen.

## Front-door synthetic

**Rule:** `~/.claude/rules/front-door-synthetic.md` — the project cannot be called "working" until this synthetic passes 5 consecutive runs.

### Health synthetic (no quota cost)
```
py execution/personal_workflows/cv_optimizer_v2/tests/front_door.py --runs 5
```
Tests `GET /api/health` and `HEAD` on the Pages site. No Gemini calls. Safe to run in CI and on every deploy.

### POST /api/optimize synthetic (opt-in — burns ~1 Gemini call per run)
```
# Requires WORKER_SECRET in .env:
#   echo "WORKER_SECRET=<your-secret>" >> .env
# Then:
CV_OPTIMIZE_LIVE=1 py -m pytest tests/test_cv_optimizer_v2_front_door_optimize.py -v -s
```
- Gate env var: `CV_OPTIMIZE_LIVE=1` (skipped by default to protect free-tier quota).
- Fixture: `tests/fixtures/cv_optimize_request.json` — synthetic PM CV + OpenAI-style JD.
- Artifact saved to: `tests/.tmp/cv_optimizer_v2_synthetic_latest.json` after each run.
- On HTTP 429 (Gemini quota): `pytest.skip` — degraded-state, not regression.
- On HTTP 200 with invalid CVSpec: hard `FAIL` — contract regression.

**Required secrets for full live run:**
- `WORKER_SECRET` — add to workspace `.env` (same value as Cloudflare secret `WORKER_SECRET`).

**Last verified:** 2026-06-15 — `test_optimize_rejects_bad_secret` PASS (Worker live, auth enforced). Full CVSpec run pending `WORKER_SECRET` in local `.env`.

## Changelog

- 2026-06-15: Front-door POST synthetic added (`tests/test_cv_optimizer_v2_front_door_optimize.py`).
- 2026-06-12: Initial scaffold — Phase 1-3 (schema gate, Worker, Frontend) shipped. Deploy pending user wrangler auth.
