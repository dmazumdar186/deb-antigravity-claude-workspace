#!/usr/bin/env bash
# FRONT-DOOR SYNTHETIC - instantly_reply_notifier
#
# Per ~/.claude/rules/front-door-synthetic.md this hits LIVE infrastructure only.
# It contains no fixtures. It answers one question: if a lead replies right now,
# does a message land on the operator's phone?
#
# It checks the whole chain, not just the worker:
#   1. The live worker answers /health and Telegram is actually bound.
#   2. The Instantly webhook is still registered and enabled on the account
#      (a deleted or disabled webhook is invisible from the worker's side -
#      the worker looks perfectly healthy while Instantly sends it nothing).
#   3. A real POST through the public URL produces notified:true, meaning
#      Telegram's API returned 2xx - not "we tried", but "it was accepted".
#
# Usage:
#   bash tests/front_door_instantly_reply_notifier.sh
# Env (read from the workspace .env if not already exported):
#   NOTIFIER_WEBHOOK_SECRET, INSTANTLY_NOTIFIER_API_KEY
set -uo pipefail

LIVE_URL="${LIVE_URL:-https://instantly-reply-notifier.debanjan186.workers.dev}"
ENV_FILE="${ENV_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)/.env}"

read_env() {
  local key="$1"
  [[ -f "$ENV_FILE" ]] || return 0
  grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r"'
}

SECRET="${NOTIFIER_WEBHOOK_SECRET:-$(read_env NOTIFIER_WEBHOOK_SECRET)}"
IKEY="${INSTANTLY_NOTIFIER_API_KEY:-$(read_env INSTANTLY_NOTIFIER_API_KEY)}"

FAIL=0
fail() { echo "  FAIL: $*"; FAIL=1; }
pass() { echo "  PASS: $*"; }

echo "=== 1. Worker health (live) ==="
HEALTH=$(curl -sS -m 20 "${LIVE_URL}/health" 2>&1)
echo "  $HEALTH"
if ! printf '%s' "$HEALTH" | grep -q '"status":"ok"'; then
  fail "worker did not return status ok"
elif ! printf '%s' "$HEALTH" | grep -q '"telegram_bound":true'; then
  fail "telegram_bound is not true - notifications cannot reach any phone"
else
  pass "worker healthy, Telegram bound"
fi

echo
echo "=== 2. Instantly webhook still registered (live) ==="
if [[ -z "$IKEY" ]]; then
  fail "INSTANTLY_NOTIFIER_API_KEY unavailable - cannot verify registration"
else
  HOOKS=$(curl -sS -m 20 "https://api.instantly.ai/api/v2/webhooks" -H "Authorization: Bearer $IKEY" 2>&1)
  if printf '%s' "$HOOKS" | grep -q "${LIVE_URL}/webhook"; then
    pass "reply_received webhook points at this worker"
    if printf '%s' "$HOOKS" | grep -q '"X-Webhook-Secret"'; then
      pass "webhook carries the X-Webhook-Secret header"
    else
      fail "webhook registered WITHOUT the secret header - the worker will 401 every delivery"
    fi
  else
    fail "no Instantly webhook points at ${LIVE_URL}/webhook - replies go nowhere"
  fi
fi

echo
echo "=== 3. End-to-end: real POST must actually deliver to Telegram ==="
if [[ -z "$SECRET" ]]; then
  fail "NOTIFIER_WEBHOOK_SECRET unavailable - cannot post"
else
  RESP=$(curl -sS -m 30 -X POST "${LIVE_URL}/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Webhook-Secret: ${SECRET}" \
    -d "{\"event_type\":\"reply_received\",\"lead_email\":\"front-door@example.com\",\"firstName\":\"Front\",\"lastName\":\"Door\",\"companyName\":\"Synthetic\",\"campaign_name\":\"FRONT DOOR SYNTHETIC\",\"reply_subject\":\"fd-$(date +%s%N)\",\"reply_text_snippet\":\"This sounds interesting. When can we chat?\"}" 2>&1)
  echo "  $RESP"
  if printf '%s' "$RESP" | grep -q '"notified":true'; then
    pass "Telegram accepted the message (a real notification was sent)"
  else
    fail "message did NOT reach Telegram"
  fi
  if printf '%s' "$RESP" | grep -q 'notify_error'; then
    fail "notify_error present - delivery failed"
  fi
fi

echo
echo "========================================"
if (( FAIL )); then
  echo "  FRONT DOOR: FAILING"
  echo "========================================"
  exit 1
fi
echo "  FRONT DOOR: PASSING"
echo "========================================"
