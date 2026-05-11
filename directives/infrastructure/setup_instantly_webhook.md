# Setup Instantly Webhook

## Goal

Configure Instantly v2 to POST `reply_received` events to the accessory-masters Cloudflare Worker, authenticated by the `X-Webhook-Secret` header. Without this, the worker rejects every webhook call (401) and replies only arrive via the 30-min cron poll fallback.

## When to run

- **Initial setup** — first time wiring up Instantly → Worker.
- **Secret rotation** — periodic or after a suspected leak. Re-running the script generates a fresh secret and updates both Cloudflare and Instantly atomically.
- **Worker URL change** — if the worker is redeployed under a different hostname, pass `--worker-url <new url>`.

## What it does

1. Loads `INSTANTLY_API_KEY` from `.env`.
2. Generates a fresh 32-byte URL-safe secret (or uses `INSTANTLY_WEBHOOK_SECRET_OVERRIDE` if set).
3. Lists existing Instantly webhooks; deletes any pointing at the same worker URL (re-runs are idempotent).
4. Pushes the secret to Cloudflare via `npx wrangler secret put INSTANTLY_WEBHOOK_SECRET` (from the worker's wrangler directory).
5. Calls `POST /api/v2/webhooks` to register a new webhook with `event_type: reply_received` and `headers: { "X-Webhook-Secret": <value> }`.
6. Prints a masked confirmation (`****abcd`). The full secret value is never logged.

## Prerequisites

- `INSTANTLY_API_KEY` in `.env`.
- `npx wrangler` available on PATH, logged into the right Cloudflare account.
- The worker is deployed (route `/api/webhook/reply` must exist and reference `env.INSTANTLY_WEBHOOK_SECRET`).

## Usage

```bash
# Preview without making changes
py execution/infrastructure/setup_instantly_webhook.py --dry-run

# List existing Instantly webhooks (for inspection)
py execution/infrastructure/setup_instantly_webhook.py --list

# Provision / rotate (the real run)
py execution/infrastructure/setup_instantly_webhook.py

# Re-use an existing secret instead of rotating
INSTANTLY_WEBHOOK_SECRET_OVERRIDE="..." py execution/infrastructure/setup_instantly_webhook.py

# Only update Instantly (skip wrangler) — for when the CF secret is already set
py execution/infrastructure/setup_instantly_webhook.py --no-cloudflare
```

## Expected output

```
Secret: ****abcd (generated)
Worker URL: https://accessory-masters-api.accessory-masters.workers.dev/api/webhook/reply
Existing webhooks pointing at this URL: 0
  cloudflare: set INSTANTLY_WEBHOOK_SECRET (****abcd)
  instantly: created webhook id=<uuid> event=reply_received
Done. Secret (last 4): ****abcd
```

## Verify after running

```bash
# Cloudflare secret exists
cd execution/infrastructure/api-proxy && npx wrangler secret list

# Worker rejects without header
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Content-Type: application/json" \
  -d '{"test":true}' \
  https://accessory-masters-api.accessory-masters.workers.dev/api/webhook/reply
# Expect: 401
```

To verify the accept path, capture the secret once at run time (e.g., `INSTANTLY_WEBHOOK_SECRET_OVERRIDE=$(py -c "import secrets; print(secrets.token_urlsafe(32))")` then export it before running) and curl with `-H "X-Webhook-Secret: $INSTANTLY_WEBHOOK_SECRET_OVERRIDE"`. Expected: `200`, body `{"success": true, "received": true, "skipped": "unrecognized_payload"}`.

## Failure modes

- **`INSTANTLY_API_KEY not set`** — add it to `.env` and re-run.
- **`wrangler secret put failed`** — usually a Cloudflare auth issue. Run `npx wrangler whoami` from `execution/infrastructure/api-proxy/` and re-authenticate. The script aborts before touching Instantly, so a wrangler failure leaves the integration unchanged.
- **`Instantly create webhook failed: 401`** — `INSTANTLY_API_KEY` is invalid or revoked. Regenerate in Instantly settings.
- **`Instantly create webhook failed: 422` / validation error** — Instantly v2 API contract may have changed. Run with `--list` and inspect existing webhooks for the current shape, update the script accordingly.
- **Worker still returns 401 after setup** — the Cloudflare deploy may not have picked up the new secret. Run `npx wrangler deploy` from the worker dir; secrets propagate within seconds but a redeploy forces it.

## Related

- Worker auth function: `checkWebhookAuth` (`execution/infrastructure/api-proxy/src/index.js:1704`)
- Worker route: `POST /api/webhook/reply` (`execution/infrastructure/api-proxy/src/index.js:214`)
- Fallback: `5/30 * * * *` cron polling via `pollAndProcessReplies`
