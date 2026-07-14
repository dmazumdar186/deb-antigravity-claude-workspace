# self_outbound_webhook_worker

Cloudflare Worker that receives Instantly webhook events for the `self_outbound_system_v2` campaign, HMAC-verifies the signature, persists the event to KV, and fires a Telegram alert.

Local sync (Python) reads KV, calls `suppression_writer.add_bulk()`, then deletes consumed KV keys.

## One-time deploy

```bash
cd execution/infrastructure/self_outbound_webhook_worker

# 1. Create KV namespace, paste the returned id into wrangler.toml
wrangler kv namespace create SUPP_EVENTS
# Then edit wrangler.toml: uncomment the [[kv_namespaces]] block and paste the id.

# 2. Provision secrets (one at a time)
wrangler secret put INSTANTLY_WEBHOOK_SECRET   # paste the shared HMAC secret from Instantly Settings -> Webhooks
wrangler secret put TELEGRAM_BOT_TOKEN         # optional, for alerts
wrangler secret put TELEGRAM_CHAT_ID           # optional, for alerts
wrangler secret put WORKER_SECRET              # optional, for /manual endpoint (any long random string)

# 3. Deploy
wrangler deploy
```

Wrangler prints the worker URL — something like `https://self-outbound-webhook.<subdomain>.workers.dev/`.

## Register with Instantly

Instantly UI -> Settings -> Webhooks -> Add Webhook
- URL: `https://<worker-url>/instantly`
- Events: `reply_received`, `email_bounced`, `unsubscribed`, `marked_as_spam`
- Signature secret: same value you set as `INSTANTLY_WEBHOOK_SECRET`

## Endpoints

- `GET /health` — 200 with `{ok, ts, kv_bound, hmac_secret_bound, telegram_alert_bound}`. Watch this from an uptime monitor.
- `POST /instantly` — HMAC-verified via `X-Instantly-Signature`. Enqueues suppression event to KV.
- `POST /manual` — Auth via `X-Worker-Secret` header. Body: `{email, reason}`. For operator use (curl, Telegram bot command).

## Test the HMAC path locally without a real Instantly event

```bash
SECRET='<paste-your-secret>'
BODY='{"event_type":"reply_received","lead_email":"test@example.com"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')
curl -X POST https://<worker-url>/instantly \
  -H "content-type: application/json" \
  -H "x-instantly-signature: $SIG" \
  -d "$BODY"
```

Expected response: `{"ok":true,"enqueued":"event:...","type":"reply_received","email":"test@example.com","reason":"negative_reply"}`.

## KV event shape

```json
{
  "type": "reply_received",
  "email": "prospect@example.com",
  "reason": "negative_reply",
  "source": "webhook",
  "campaign_tag": "debanjanm-outbound-v2",
  "received_at": "2026-07-14T10:23:00.000Z",
  "raw": { "...": "full Instantly payload" }
}
```

Keys are `event:<iso>:<random-6-char>`. TTL: 30 days as a backstop; local sync should consume them within minutes to hours.

## Local sync (to be written in a follow-up)

A Python script at `execution/personal_workflows/self_outbound_system/sync_suppression_from_kv.py` will:
1. `wrangler kv key list --binding=SUPP_EVENTS --prefix=event:` — list all pending events
2. `wrangler kv key get --binding=SUPP_EVENTS <key>` — fetch each payload
3. Call `suppression_writer.add_bulk([{email, reason, source: "webhook"}])`
4. `wrangler kv key delete --binding=SUPP_EVENTS <key>` — mark consumed

Not written yet; the KV events accumulate safely with a 30-day TTL until the operator authorizes the sync script.

## Revert

```bash
wrangler delete self-outbound-webhook
```

Then remove the webhook from Instantly's dashboard.
