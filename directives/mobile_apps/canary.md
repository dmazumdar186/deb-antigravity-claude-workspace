# Mobile App Canary — Health + Dry-Run + Scheduled Probe

## Goal

Every deployed mobile app (anything past Phase 4a) must implement the three canary components from `~/.claude/CLAUDE.md` → "Canary-readiness for deployed services": a JSON `/api/health` endpoint, `--dry-run` on every cost-incurring path, and a scheduled external probe. For mobile apps, the probe is `mobile_app_canary.py` invoked every 15 minutes by Modal cron — single canary mechanism, no separate Worker.

## Inputs

- App slug + Worker URL from registry (`<slug>.worker_url`)
- App's `/api/health` reachable + returns the expected JSON shape
- Modal token + `WORKER_SECRET` available to the canary's Modal app
- Telegram chat ID or Slack webhook for alerts (configured in user's existing notification setup)

## Tools/Scripts

- `execution/mobile_apps/mobile_app_canary.py` — iterates `registry.json`, pings each app's `/api/health`, asserts invariants, alerts on failure; deduplicates alerts via `.tmp/canary_state.json`
- `directives/infrastructure/canary_monitoring.md` — the general principle (read first)
- Modal cron (every 15 min) — the scheduler

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | off | Parse registry only; no HTTP calls, no state written |
| `--timeout <s>` | 10 | Per-request timeout in seconds |
| `--max-workers <N>` | 8 | Thread pool size for parallel pings |
| `--alert {none,console,webhook,both}` | `console` | Alert delivery mode |
| `--webhook-url <url>` | `$MOBILE_CANARY_WEBHOOK_URL` | Webhook endpoint for alert POSTs |
| `--alert-threshold <N>` | 3 | Fire repeated alert every N consecutive failures (even without a transition) |

### Alert Dedup Semantics

State is persisted at `.tmp/canary_state.json` (gitignored). Schema per check:

```json
{
  "last_run_at": "<ISO-8601>",
  "checks": {
    "<slug>": {
      "status": "pass|fail",
      "last_status_change_at": "<ISO-8601>",
      "consecutive_failures": 0
    }
  }
}
```

An alert fires **only** when:
1. The check status transitions (`pass→fail` or `fail→pass`), **or**
2. `consecutive_failures` reaches `--alert-threshold` (default 3) and every subsequent multiple of that threshold (3, 6, 9 …).

Apps with no `health_url` (`missing-health-url`) are excluded from state tracking and never trigger alerts.

### Alert Delivery

- **console**: prints an ANSI-coloured banner with slug, status, consecutive_failures, last_status_change_at, detail message.
- **webhook**: HTTP POST (10s timeout) to `--webhook-url` with JSON payload `{check_name, status, message, consecutive_failures, last_status_change_at, trigger}`. Delivery failures are logged to stderr but do not crash the canary.
- **both**: console + webhook simultaneously.
- **none**: state is still updated; no alerts emitted.

### State File Safety

Writes are atomic: canary writes to a sibling `.tmp/canary_state_<uuid>.json.tmp` then renames to `canary_state.json`. A failed rename logs to stderr but does not abort the run.

## Required `/api/health` shape (mobile apps)

```json
{
  "status": "ok",
  "version": "<git short sha>",
  "build_sha": "<git short sha>",
  "kv_check": true,
  "timestamp": "<ISO>",
  "upstream_credit_balances": {
    "openrouter": { "credits_remaining": 4.32, "last_checked": "<ISO>" }
  },
  "secrets_present": {
    "WORKER_SECRET": true,
    "OPENROUTER_API_KEY": true
  },
  "last_success_per_job": {
    "refresh": { "ts": "<ISO>", "within_seconds": 14400 }
  }
}
```

Match this shape exactly so `mobile_app_canary.py` can assert against it without per-app special cases.

## Required `--dry-run` paths

Every cost-incurring function must accept `--dry-run` (CLI) or `?dry_run=true` (HTTP) and return `would_*` counters without external paid calls:

- Phase 4b Modal cron functions — `dry_run=True` skips OpenRouter + Worker writes, returns `{"would_call_openrouter": true, "would_post_to_kv": true}`
- Phase 5a LLM helper — `dry_run=True` returns `{"would_call": "<model>", "estimated_cost_usd": <prefix-estimate>}`
- Phase 4a Worker webhook receivers — `?dry_run=true` query param walks the code path, skips KV writes, returns `{"would_write_kv": true}`

## Steps

1. **Implement `/api/health`** in the Phase 4a Worker (done in that phase; this directive is the contract). Verify the shape matches above.
2. **Verify `--dry-run` paths exist** in every function listed above. Phase 5a / Phase 4b directives already mandate them — this directive is a final cross-check.
3. **Write the canary script.** `execution/mobile_apps/mobile_app_canary.py`:
   ```python
   def main():
       registry = load_registry()
       for app in registry["apps"]:
           if not app.get("health_url"): continue
           assert_health(app)
           assert_dry_run(app)
   ```
   Each assertion failure → alert with `{slug, assertion_failed, response_body, timestamp}`.
4. **Threading.** If iterating many apps in parallel, wrap shared mutable state with `threading.Lock` (hardening rule #2). Atomic per-app failures should not corrupt the run summary.
5. **Schedule via Modal cron.**
   ```python
   @app.function(image=image, schedule=modal.Cron("*/15 * * * *"))
   def canary_run():
       subprocess.run(["py", "mobile_app_canary.py"], encoding="utf-8", errors="replace", check=True)
   ```
   Modal-side scheduling, not Cloudflare Cron Triggers — the canary monitors Workers, so it shouldn't share their infra.
6. **Alert dedup.** Canary tracks last alert state in `.tmp/canary_state.json`. Only alert on status transitions (`pass→fail` or `fail→pass`) or when `consecutive_failures` hits `--alert-threshold` (default 3). See "Alert Dedup Semantics" in Tools/Scripts above for the full schema and firing rules.
7. **Manual smoke.** Run `py execution/mobile_apps/mobile_app_canary.py --dry-run` (canary itself supports dry-run — no alert sent, just prints what it would assert). Then deliberately break something (rotate the Worker secret) and confirm a real alert fires.
8. **Document the alert channel** in registry: `<slug>.canary_alert_channel: "telegram:<chat-id>"` or `"slack:<webhook>"`.

## Outputs

- `/api/health` live on every deployed app (mandatory)
- `--dry-run` on every cost-incurring path (mandatory)
- `mobile_app_canary.py` running on a 15-min Modal cron
- `.tmp/canary_state.json` — last-known-good per app
- Alert routed to configured channel on state change

## Edge Cases

- **App with no Worker yet.** Skip silently — canary only iterates apps with `health_url` set. Phase 1-3 apps are out of scope.
- **Worker cold start.** First probe after long idle can take 3-5s. Don't fail on slow response; timeout at 10s.
- **Credit balance below threshold but service still works.** Status should be `yellow`, not `red`. Canary alerts only on `red` to avoid noise — `yellow` is captured in the dashboard.
- **Canary itself fails.** If Modal cron breaks, no one watches the canary. Optional: hook a Better Stack Heartbeat to the canary's own success ping — alerts when the canary *stops* running, not when it reports failure.
- **Multi-tenant Workers.** If one Worker serves multiple apps, `/api/health?tenant=<slug>` per app. Canary loops over the tenant list, not just the URL.
- **`would_send = 0` after Phase 5a is integrated.** The Phase 5a LLM helper's `would_call` should be truthy in dry-run; if it goes false, alert. (Anomaly detection threshold baseline: 7-day rolling per app.)
- **Secret leak in `/api/health`.** `secrets_present` is boolean per key — NEVER include values. If a sub-agent accidentally returns secret values, the canary's first job is to detect it (regex for secret-like substrings in the response) and alert.

## Exit Criteria

- `py execution/mobile_apps/mobile_app_canary.py --dry-run` exits `0` and prints which apps it would assert against (registry parsed successfully), without making any HTTP calls.
- For every app in `registry.json` with `health_url` set: a live probe to `/api/health` returns HTTP 200 with the required JSON shape (`status`, `version`, `build_sha`, `kv_check`, `upstream_credit_balances`, `secrets_present`, `last_success_per_job`).
- A deliberately-broken app (rotate Worker secret to an invalid value) causes `mobile_app_canary.py` to print a console alert within one run and set `"status": "fail"` in `.tmp/canary_state.json`.
- `.tmp/canary_state.json` exists after the first real run and contains a `checks` object with one entry per probed app slug.
- The Modal cron entry `*/15 * * * *` is visible in the Modal dashboard for the canary function.

## Notes

- This is the **sole canary mechanism** — no separate Worker per the plan (skeptic round 1 removed that). The Modal-cron-driven Python canary covers all mobile apps.
- The 3-component pattern (health + dry-run + probe) is workspace-wide policy from `~/.claude/CLAUDE.md`. Mobile apps inherit it; no exceptions.
- Cost: canary makes 4 probes/hr × 24h × 30d = ~2,880 calls/month per app. All hit cached `/api/health` (no upstream calls) → effectively $0.
- The general principle and scheduler shortlist live in `directives/infrastructure/canary_monitoring.md`. This directive is the mobile-apps specialization.
