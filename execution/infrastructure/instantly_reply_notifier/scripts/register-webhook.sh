#!/usr/bin/env bash
# Register the reply_received webhook on an Instantly account.
#
# Usage:
#   INSTANTLY_API_KEY=xxx WEBHOOK_SECRET=yyy \
#     ./scripts/register-webhook.sh https://your-worker.workers.dev/webhook
#
# Run it once per Instantly account, pointing each at its own route
# (/webhook for your account, /webhook/client for the second one).
#
# IMPORTANT - the `headers` field is not optional.
# The worker rejects any delivery without a matching X-Webhook-Secret header,
# and now fails closed when the secret is unset. An earlier version of this
# script omitted `headers` entirely, which registered a webhook that Instantly
# happily reported as active while the worker 401'd every single delivery.
# That failure is invisible from both dashboards - it looks exactly like
# "Instantly isn't firing". Always pass WEBHOOK_SECRET.
set -euo pipefail

TARGET_URL="${1:-}"
if [[ -z "$TARGET_URL" ]]; then
  echo "usage: $0 <worker-webhook-url>" >&2
  exit 1
fi
: "${INSTANTLY_API_KEY:?set INSTANTLY_API_KEY in your environment}"
: "${WEBHOOK_SECRET:?set WEBHOOK_SECRET - it must match the worker's secret, or every delivery 401s}"

curl -sS -X POST "https://api.instantly.ai/api/v2/webhooks" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(cat <<JSON
{
  "name": "reply notifier",
  "target_hook_url": "$TARGET_URL",
  "event_type": "reply_received",
  "headers": { "X-Webhook-Secret": "$WEBHOOK_SECRET" }
}
JSON
)"
echo

echo "Registered webhooks on this account (secret values redacted):"
curl -sS "https://api.instantly.ai/api/v2/webhooks" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  | sed -E "s/$WEBHOOK_SECRET/<REDACTED>/g"
echo
