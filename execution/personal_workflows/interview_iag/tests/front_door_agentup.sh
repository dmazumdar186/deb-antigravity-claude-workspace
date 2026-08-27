#!/usr/bin/env bash
# Front-door synthetic for AgentUp — hits the LIVE deployed URL, verifies:
#   1. GET /api/claude returns health payload with key_present=true
#   2. All 3 pages return 200 and contain their h1
#   3. POST /api/claude?mode=score with a fixture transcript returns a valid
#      scorecard (JSON with 7 required keys, scores in [0,100])
#
# Usage:
#   bash tests/front_door_agentup.sh https://agentup-iag.pages.dev
#
# Exit 0 on all-pass, non-zero on any failure.

set -eo pipefail

# SITE_URL is the workspace-standard name recognized by
# workspace_sast.py's front-door-fixture-only rule as a live-URL fingerprint.
# BASE is kept as the local alias so the rest of the script is unchanged.
SITE_URL="${SITE_URL:-${1:-https://agentup-iag.pages.dev}}"
BASE="${SITE_URL%/}"
FAIL_COUNT=0

fail() { echo "FAIL: $*" >&2; FAIL_COUNT=$((FAIL_COUNT + 1)); }
pass() { echo "PASS: $*"; }

# --- Health ---
echo "→ GET $BASE/api/claude"
HEALTH=$(curl -fsS -m 15 "$BASE/api/claude" || true)
if [ -z "$HEALTH" ]; then
  fail "health endpoint returned empty / non-200"
else
  echo "$HEALTH" | python -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('ok') is True, f'ok != true: {d}'
assert d.get('primary_model') == 'claude-sonnet-5', f'wrong primary_model: {d.get(\"primary_model\")}'
assert d.get('key_present') is True, 'no LLM key present on edge'
print('  health OK — primary={} fallback={} anthropic_key={} gemini_key={}'.format(
    d['primary_model'], d.get('fallback_model'), d.get('anthropic_key_present'), d.get('gemini_key_present')))
" || fail "health payload invalid"
  pass "GET /api/claude"
fi

# --- Static pages ---
for path in "" "/cases" "/dashboard"; do
  URL="$BASE$path/"
  echo "→ GET $URL"
  # -L follows redirects (CF may 308 /dashboard → /dashboard/); -f fails on 4xx/5xx.
  BODY=$(curl -fsSL -m 15 "$URL" 2>&1) || { fail "GET $URL — non-200"; continue; }
  case "$path" in
    "")           NEEDLE="Daily Training" ;;
    "/cases")     NEEDLE="My Cases" ;;
    "/dashboard") NEEDLE="My Dashboard" ;;
  esac
  # Astro emits `<h1 ...>\n<needle>\n</h1>` — grep for the needle after any h1 tag,
  # tolerating whitespace/newlines. `tr` collapses to one line first.
  if ! echo "$BODY" | tr '\n' ' ' | grep -qE "<h1[^>]*>\s*$NEEDLE"; then
    fail "$URL — h1 '$NEEDLE' not found"
  else
    pass "$URL — h1 '$NEEDLE' present"
  fi
done

# --- Live scoring roundtrip ---
echo "→ POST $BASE/api/claude (mode=score)"
FIXTURE=$(cat <<'EOF'
{
  "mode": "score",
  "scenario": "Customer is complaining about a duplicate charge on their bill.",
  "difficulty": "Beginner",
  "transcript": [
    { "role": "customer", "text": "Hi, I was charged twice on this month's bill." },
    { "role": "agent",    "text": "I'm sorry to hear that — let me pull up your account and check right away." },
    { "role": "customer", "text": "Thank you." },
    { "role": "agent",    "text": "I can confirm you were charged twice on the 12th. I'm reversing the duplicate now — you'll see the refund in 3-5 business days. Would you like a confirmation email?" },
    { "role": "customer", "text": "Yes please." },
    { "role": "agent",    "text": "Done — check your inbox in a few minutes. Anything else I can help with?" }
  ]
}
EOF
)
RESP=$(curl -fsS -m 30 -X POST "$BASE/api/claude" \
  -H "content-type: application/json" \
  -H "origin: $BASE" \
  -d "$FIXTURE" || echo "__CURL_FAIL__")

if echo "$RESP" | grep -q "__CURL_FAIL__"; then
  fail "scoring endpoint returned non-2xx"
else
  echo "$RESP" | python -c "
import json, sys
d = json.load(sys.stdin)
for k in ('empathyScore','accuracyScore','resolutionScore','professionalismScore','overallScore','strength','improvement'):
    assert k in d, f'missing key: {k}'
for k in ('empathyScore','accuracyScore','resolutionScore','professionalismScore','overallScore'):
    assert isinstance(d[k], int), f'{k} not int'
    assert 0 <= d[k] <= 100, f'{k} out of range: {d[k]}'
for k in ('strength','improvement'):
    assert isinstance(d[k], str) and len(d[k]) > 0, f'{k} empty'
print('  scoring OK — overall={}'.format(d['overallScore']))
" || fail "scorecard shape invalid"
  pass "POST /api/claude (mode=score) — live Claude roundtrip"
fi

echo ""
if [ "$FAIL_COUNT" -gt 0 ]; then
  echo "FRONT-DOOR SYNTHETIC: $FAIL_COUNT failure(s)."
  exit 1
fi
echo "FRONT-DOOR SYNTHETIC: all checks passed."
