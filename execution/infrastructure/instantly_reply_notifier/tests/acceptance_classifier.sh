#!/usr/bin/env bash
# Output-acceptance gate for the reply notifier.
#
# Asserts on the OUTCOME a human experiences - "did this reply reach my phone,
# or was it silently dropped" - not on mechanics like HTTP 200 or row counts.
# A notifier that drops a hot lead and one that is working look identical from
# the outside, so the drop cases matter as much as the notify cases.
#
# Usage:
#   ./tests/acceptance_classifier.sh http://127.0.0.1:8787/webhook       # local dev
#   WEBHOOK_SECRET=xxx ./tests/acceptance_classifier.sh https://<worker>/webhook
#
# Delivery strictness is decided from /health, not assumed:
#   telegram_bound=true  -> a notify case MUST come back notified:true. An
#                           attempted-but-failed send (notify_error) is a FAIL,
#                           because the phone got nothing.
#   telegram_bound=false -> local dev with no Telegram secrets. A notify case
#                           passes on notify_error, since "would have notified"
#                           is the most this configuration can prove.
# Without that branch the gate would print GREEN through a Telegram outage or a
# revoked bot token while zero messages reached the phone.
set -uo pipefail

URL="${1:-}"
if [[ -z "$URL" ]]; then
  echo "usage: $0 <webhook-url>" >&2
  exit 2
fi

SECRET_HEADER=()
if [[ -n "${WEBHOOK_SECRET:-}" ]]; then
  SECRET_HEADER=(-H "X-Webhook-Secret: ${WEBHOOK_SECRET}")
fi

TELEGRAM_BOUND="false"
PASS=0
FAIL=0
FAILURES=()

# post <expect: notify|drop> <label> <reply text>
post() {
  local expect="$1" label="$2" text="$3"
  # Unique subject per case so the 120s KV dedup never eats a test case.
  local subject="acceptance-$(date +%s%N)-${RANDOM}"

  local payload
  payload=$(cat <<JSON
{"event_type":"reply_received","lead_email":"acceptance+${RANDOM}@example.com","firstName":"Acceptance","lastName":"Test","companyName":"Test Co","campaign_name":"ACCEPTANCE GATE","reply_subject":"${subject}","reply_text_snippet":$(printf '%s' "$text" | python -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}
JSON
)

  local resp
  resp=$(curl -sS -m 30 -X POST "$URL" \
    -H "Content-Type: application/json" \
    "${SECRET_HEADER[@]}" \
    -d "$payload" 2>&1)

  local category notified has_error
  category=$(printf '%s' "$resp" | grep -oE '"category":"[^"]*"' | head -1 | cut -d'"' -f4)
  notified=$(printf '%s' "$resp" | grep -oE '"notified":(true|false)' | head -1 | cut -d: -f2)
  has_error=$(printf '%s' "$resp" | grep -c 'notify_error' || true)

  # "reached" means the message actually landed when Telegram is configured.
  local reached="no"
  if [[ "$notified" == "true" ]]; then
    reached="yes"
  elif [[ "$has_error" != "0" && "$TELEGRAM_BOUND" != "true" ]]; then
    # Only credit intent when Telegram genuinely is not configured.
    reached="yes"
  fi

  local ok="no"
  if [[ "$expect" == "notify" && "$reached" == "yes" ]]; then ok="yes"; fi
  if [[ "$expect" == "drop"   && "$reached" == "no"  ]]; then ok="yes"; fi

  if [[ "$ok" == "yes" ]]; then
    PASS=$((PASS+1))
    printf '  PASS  [%-6s] %-46s -> %s\n' "$expect" "$label" "${category:-?}"
  else
    FAIL=$((FAIL+1))
    FAILURES+=("$label (expected=$expect got category=${category:-?} reached=$reached)")
    printf '  FAIL  [%-6s] %-46s -> %s   %s\n' "$expect" "$label" "${category:-?}" "$resp"
  fi
}

echo "=== health ==="
HEALTH=$(curl -sS -m 15 "${URL%/webhook*}/health")
echo "$HEALTH"

TELEGRAM_BOUND=$(printf '%s' "$HEALTH" | grep -oE '"telegram_bound":(true|false)' | cut -d: -f2)
if [[ "$TELEGRAM_BOUND" == "true" ]]; then
  echo "telegram_bound=true -> notify cases must ACTUALLY deliver (notified:true)"
else
  echo "telegram_bound=false -> notify cases pass on intent only (local dev)"
fi
echo
echo "=== MUST REACH THE PHONE ==="
post notify "explicit booking request"          "This sounds interesting. When can we chat?"
post notify "asks for a call back"              "Can you call me at 555-123-4567 tomorrow?"
post notify "wants more info"                   "tell me more about what you do"
post notify "enthusiastic - 'sooo' not OOO"     "Sooo interested, lets talk this week!"
post notify "ROI question - not an OOO"         "What is the return on investment for this?"
post notify "ambiguous - who is this"           "Who is this and how did you get my email?"
# Annoyance is not a decline. These were classified "negative" by the LLM on
# 2026-08-25 and silently dropped - a curious lead vanishing is the worst
# failure this tool has. Keep them pinned.
post notify "suspicious but engaging"           "How did you get my email address?"
post notify "terse question mark"               "What is this about?"
post notify "blunt but no decline"              "I have no idea who you are."
# Regressions found by code review on 2026-08-25. Every one of these was
# silently dropped as not_interested / ooo by the shipped classifier while
# containing explicit buying or scheduling intent. Verified live before the fix.
post notify "booking confirm - 'we are good to go'"  "we are good to go, what time works Tuesday?"
post notify "booking confirm - 'all set for call'"   "We are all set for the call, see you then"
post notify "invitation - 'do not hesitate'"         "please do not hesitate to call me on my mobile"
post notify "forward to decision maker"              "I will pass this along to our VP of Marketing"
post notify "budget approved"                        "We already have budget approved for this quarter, lets talk"
post notify "no need to explain + booking"           "no need to explain further, lets set up a call"
post notify "travel-industry lead says vacation"     "We help clients book their dream vacation homes - interested"
post notify "HR-tech lead says leave"                "we build leave management software, tell me more"

echo
echo "=== MUST STAY SILENT ==="
post drop   "classic out of office"             "I am currently out of office until Monday."
post drop   "on leave"                          "I am on leave, be back on the 5th of next month."
post drop   "not interested + remove"           "Not interested, please remove me."
post drop   "standalone REMOVE above signature" $'REMOVE\n\nSent from my iPhone'
post drop   "unsubscribe"                       "unsubscribe"
post drop   "wrong person"                      "You have the wrong person, I do not handle this."
post drop   "explicit stop request"             "Please stop emailing me about this."
# The narrowed patterns must still catch the genuine declines they were for.
post drop   "genuine 'we are all set' decline"  "Thanks but we are all set, no thanks."
post drop   "genuine vendor decline"            "We already have a vendor for this."
post drop   "genuine stop-contacting"           "Please do not email me again."
post drop   "genuine vacation OOO"              "I am on vacation until the 12th with limited access to my email."

echo
echo "========================================"
echo "  PASS: $PASS   FAIL: $FAIL"
echo "========================================"
if (( FAIL > 0 )); then
  echo
  echo "Failures:"
  for f in "${FAILURES[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "Acceptance gate GREEN."
