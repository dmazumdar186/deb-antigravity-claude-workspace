#!/usr/bin/env bash
# Smoke-test a deployed worker: one reply that SHOULD notify, one that should NOT.
#
# Usage:
#   WEBHOOK_SECRET=xxx ./scripts/test-webhook.sh https://your-worker.workers.dev/webhook
set -euo pipefail

URL="${1:-}"
if [[ -z "$URL" ]]; then
  echo "usage: $0 <worker-webhook-url>" >&2
  exit 1
fi
: "${WEBHOOK_SECRET:?set WEBHOOK_SECRET in your environment}"

echo "--- health ---"
curl -sS "${URL%/webhook*}/health"; echo

echo "--- positive reply (expect notified:true, and a Telegram message) ---"
curl -sS -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"event_type":"reply_received","lead_email":"test@example.com","firstName":"Test","companyName":"Acme","campaign_name":"Smoke Test","reply_subject":"Re: hello","reply_text_snippet":"This sounds interesting. When can we chat?"}'
echo

echo "--- not-interested reply (expect notified:false, NO Telegram message) ---"
curl -sS -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -d '{"event_type":"reply_received","lead_email":"neg@example.com","firstName":"Neg","campaign_name":"Smoke Test","reply_subject":"Re: hello again","reply_text_snippet":"Not interested, please remove me."}'
echo

echo "--- bad secret (expect 401) ---"
curl -sS -o /dev/null -w "%{http_code}\n" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: definitely-wrong" \
  -d '{"event_type":"reply_received","reply_text_snippet":"hi"}'
