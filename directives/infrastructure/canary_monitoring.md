# Canary Monitoring for Deployed Services

A canary is a small, scheduled, cheap probe that exercises a deployed system the way a user would, *without* burning the real budget. It catches breakage (silent config drift, expired credentials, upstream outage, deploy regression, credit balance near zero) before real (expensive) traffic does.

This directive is the concrete how-to. The cross-workspace principle lives in `~/.claude/CLAUDE.md` under "Canary-readiness for deployed services".

## Goal

Ship every deployed service with three components that together act as a zero-credit early-warning system:
1. A `/api/health` endpoint surfacing upstream credit balances + secret presence + last-success timestamps + build SHA.
2. A `--dry-run` mode on every cost-incurring code path that returns `would_*` counters and makes no external paid API calls.
3. A scheduled external probe (the canary itself) that hits both every 5–15 min and alerts on failure or anomaly.

## When to Use

- **Always for:** Cloudflare Workers, Modal endpoints, Vercel/Netlify functions, deployed Python/Node services, scheduled cron pipelines, webhook receivers, anything that calls paid APIs in production.
- **Skip for:** local CLI scripts, libraries, static sites with no backend, throwaway prototypes, anything run manually with no live runtime.

## Inputs

| Input | Purpose |
|-------|---------|
| Service base URL | The deployed endpoint root (e.g. `https://<service>.workers.dev`) |
| Health-check secret | Optional auth header for `/api/health` and dry-run if the routes shouldn't be public |
| Upstream provider list | Which providers need credit-balance checks (LLM, email-find, email-verify, search, etc.) |
| Required env vars list | Used to confirm secret presence — names only, never values |
| Alert channel | Telegram chat ID / Slack webhook / email / SMS — wherever the operator actually looks |
| Expected cron cadence (per scheduled job) | Used to set the `last_success_within_seconds` threshold |

## Tools/Scripts

| Reference | Purpose |
|-----------|---------|
| `~/.claude/CLAUDE.md` → "Canary-readiness for deployed services" | Cross-workspace principle and scheduler shortlist |
| `directives/gtm_client_workflows/_baseline_worker_checklist.md` | The Worker-engagement baseline; canary is one of its prerequisites |

## Outputs

- A live `/api/health` route returning the JSON shape below.
- A `?dry_run=true` (or `--dry-run` flag) path that mirrors every cost-incurring entrypoint and returns `would_*` counts.
- A scheduled probe running every 5–15 min on an external scheduler.
- An alert routed to the operator's actual channel.

## Steps

### 1. Implement `/api/health`

Return a JSON object with this shape. Keep it cheap — no paid API calls inside the handler. Cache upstream balances in KV for 1–5 min so repeated probes don't hammer provider APIs.

```json
{
  "status": "green" | "yellow" | "red",
  "build_sha": "<git short sha>",
  "deployed_at": "<ISO timestamp>",
  "secrets": {
    "<NAME>": true,
    "<NAME>": false
  },
  "upstreams": {
    "<provider>": {
      "credits_remaining": <number or null>,
      "last_checked": "<ISO timestamp>",
      "below_threshold": true | false
    }
  },
  "scheduled_jobs": {
    "<job_name>": {
      "last_success": "<ISO timestamp>",
      "last_success_within_seconds": 1800,
      "expected_interval_seconds": 900,
      "overdue": false
    }
  }
}
```

Roll-up rule for `status`:
- `red`: any required secret missing, any upstream below hard threshold, any scheduled job overdue by more than 2× its interval.
- `yellow`: any upstream below soft threshold, any job overdue by 1–2× its interval.
- `green`: otherwise.

If the service handles multiple tenants, expose `/api/health?tenant=<slug>` or fold per-tenant state into the response.

Auth: if the health route shouldn't be public, accept a `X-Health-Check-Secret` header (separate from any other secret) so the canary can authenticate without using operator credentials.

### 2. Implement `--dry-run` mode

On every cost-incurring entrypoint (HTTP route, CLI command, cron handler):
- Accept the same inputs as the real path.
- Walk the same code path *up to* any external paid call.
- Skip the paid call, increment a `would_*` counter instead (`would_send`, `would_charge`, `would_enrich`, `would_classify`).
- Return the counters in the response: `{ "dry_run": true, "would_send": 47, "would_skip": 12, "reasons": {...} }`.

Dry-run must be deterministic with respect to fixtures — given the same input list, it should produce the same `would_*` counts. This is what lets the canary assert "would_send did not collapse to zero between yesterday and today."

Common implementation patterns:
- A `dry_run: bool` field passed through the call chain.
- A module-level `mock_external_calls()` switch in test/dry-run mode.
- An environment-aware adapter: real client in prod, recording stub in dry-run.

### 3. Choose and configure a scheduler

| Option | Free tier | Best for |
|--------|-----------|----------|
| Cloudflare Cron Triggers (same Worker) | Yes | Worker-hosted services; canary lives in the Worker itself, hits its own `/api/health` |
| AWS CloudWatch Synthetics | ~$0.0017/run + Lambda | Full headless-browser flows, screenshots, multi-step UI canaries |
| UptimeRobot | 50 monitors, 5-min interval | Simple HTTP probe with alerting; no scripting |
| Better Stack (Heartbeats + Uptime) | Free starter tier | Cleaner UI, Slack/Telegram alerts built in |
| cron-job.org | Free | Plain scheduled HTTP GET, basic alerting |
| GitHub Actions cron | Free for public repos, generous for private | Run a small Python/JS script that probes and parses, posts to webhook on fail |

**Default recommendation:** for a Cloudflare Worker service, use Cloudflare Cron Triggers — it's same-platform, free, and the canary code can live next to the service. For non-Cloudflare services, GitHub Actions cron + a 20-line script is the simplest cross-stack option.

### 4. Define the canary script

The canary does three things in order, all on every run:

```
1. GET /api/health
   - Assert status == "green" (or != "red", depending on alerting tolerance)
   - Assert no required secret is false
   - Assert no upstream is below hard threshold
   - Assert no scheduled job is overdue
2. POST /api/<main-entrypoint>?dry_run=true
   - With a small canned input set (e.g. one tenant, one fixture lead)
   - Assert response 200
   - Assert would_send > 0 (or whatever the invariant is — anomaly if it suddenly = 0)
   - Optional: assert would_send within ±25% of last week's baseline
3. On any assertion fail: send alert payload to operator channel
```

Keep the script under 50 lines. It should not depend on the service's own codebase — write it standalone in plain Python/JS so it can run on any scheduler.

### 5. Wire the alert

Alerts go to the channel the operator actually checks. Ask them on Day 1 (per the baseline checklist). Default targets:
- Telegram: `https://api.telegram.org/bot<TOKEN>/sendMessage` — JSON body with chat_id + text
- Slack: incoming webhook URL — JSON body with `text`
- Email: SES, Resend, or just `mailto:` via the scheduler if it supports it

Alert payload must include: timestamp, which assertion failed, the response body that triggered it, a link back to the dashboard / health endpoint. Don't just say "canary failed."

### 6. Deduplicate alerts

Without dedup, an outage spams the operator every 5 min. Either:
- The scheduler suppresses repeats (Better Stack, UptimeRobot do this natively), or
- The canary script tracks last-alert-state in a small KV/file and only re-alerts on state change (green→red, red→green) or every 30 min of sustained failure.

### 7. Test the canary itself

- Run the canary manually once, confirm it passes.
- Deliberately break something (rotate a key out, point at a 404 URL, set a `would_send` mock to 0). Confirm the canary fails and the alert arrives. Restore.
- Set a soft threshold on credit balance (e.g. 10% of monthly quota), confirm `yellow` status fires below it.

## Edge Cases

- **Don't put paid API calls inside `/api/health`.** A probe every 5 min × 24h × 30d = 8,640 calls/month. If health calls OpenRouter, that's billable traffic for a no-op. Cache upstream balances in KV with TTL.
- **Health endpoint can itself rate-limit.** If you accept an unauthenticated `/api/health`, expect bots to hit it. Either auth it with `X-Health-Check-Secret`, or rate-limit by IP, or return cached responses with a 60s TTL.
- **`would_send = 0` is not always a bug.** A pipeline with no fresh inputs on a Sunday legitimately produces 0. Distinguish "would_send dropped vs. yesterday" (anomaly) from "would_send is 0 because there's nothing to do" (expected). Anomaly thresholds need a baseline — track 7-day rolling.
- **Multi-tenant services need per-tenant health.** A single green roll-up hides one broken tenant in twelve. Expose per-tenant state, alert per-tenant.
- **Cron-job overdue detection has a chicken-and-egg.** If the cron is broken, the canary catches it. But if the *canary itself* is the cron job, who watches the canary? Use a different scheduler for the canary than for the service's own crons. Or use a separate "heartbeat" service (Better Stack Heartbeats, healthchecks.io) that alerts when it *stops* hearing from the cron.
- **Secrets shown as `false` in `/api/health` are an information leak.** The endpoint reveals which env vars exist. If the service is public, gate `/api/health` behind a secret. Never include secret *values*, only presence booleans.
- **Build SHA is useful for "is the deploy I just pushed the one running?"** Always emit it. `git rev-parse --short HEAD` at build time, injected as env var.
- **Don't canary the canary.** One layer is enough. Two layers is over-engineering for ~99% of cases.

## Exit Criteria

- `/api/health` on the deployed service returns HTTP 200 with a JSON body containing `status`, `build_sha`, `secrets`, and `upstreams` keys — no missing fields.
- `status` is `"green"` when all required secrets are present, all upstreams are above threshold, and no cron job is overdue (confirmed by a manual `GET /api/health` immediately after deploy).
- A dry-run POST to the main entrypoint (`?dry_run=true` or `--dry-run`) returns HTTP 200 with at least one `would_*` counter > 0 — confirming the dry-run path is wired and the pipeline would process real inputs.
- The scheduled canary probe (Cloudflare Cron, GitHub Actions, or equivalent) has at least one successful run recorded in its scheduler dashboard.
- A deliberately-broken canary (e.g. rotate a secret out) triggers an alert on the configured channel within 2× the probe interval.

## Changelog

- **2026-05-14** — Initial version. Generalizes the pattern from the Accessory Masters retrospective into a cross-project default for deployed services.
