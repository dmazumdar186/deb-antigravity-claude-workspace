#!/usr/bin/env bash
# Front-door synthetic for the freelance portfolio site.
# Per ~/.claude/rules/front-door-synthetic.md: hits the live URL like a real user
# would and asserts the artifact contract (key sections render, CTAs present).
#
# Usage:
#   bash tests/front_door_portfolio_site.sh <url>
#   bash tests/front_door_portfolio_site.sh http://127.0.0.1:4321        # local dev
#   bash tests/front_door_portfolio_site.sh https://portfolio-debanjan.pages.dev
#
# Exit 0 = green; non-zero = deploy/probation count blocked.

set -euo pipefail

URL="${1:-}"
if [ -z "$URL" ]; then
  echo "USAGE: $0 <url>" >&2
  exit 2
fi

HTML_FILE="$(mktemp)"
trap 'rm -f "$HTML_FILE"' EXIT

echo ">> Fetching $URL"
HTTP_STATUS=$(curl -sS -L -o "$HTML_FILE" -w "%{http_code}" --max-time 30 "$URL" || echo "000")
if [ "$HTTP_STATUS" != "200" ]; then
  echo "FAIL: HTTP $HTTP_STATUS from $URL" >&2
  exit 1
fi

BYTES=$(wc -c < "$HTML_FILE")
echo ">> HTTP 200, ${BYTES} bytes"
if [ "$BYTES" -lt 5000 ]; then
  echo "FAIL: response body suspiciously small (${BYTES} bytes)" >&2
  exit 1
fi

FAILS=0
check() {
  local desc="$1"; local pattern="$2"
  if grep -qE "$pattern" "$HTML_FILE"; then
    echo "  OK  $desc"
  else
    echo "  FAIL $desc (pattern: $pattern)" >&2
    FAILS=$((FAILS + 1))
  fi
}

echo ">> Asserting hero contract"
check "brand: ProdCraft"        "ProdCraft"
check "operator name caption"   "Debanjan Mazumdar"
check "founder attribution"     "[Ff]ounder"
check "headline outcome-led"    "senior AI engineer.*missing|AI engineer your roadmap"
check "subhead present"         "Without the FTE|agency timeline|Built with Claude Code"
check "primary CTA present"     "Book a free build session|cal\\.com"
check "secondary CTA present"   "See what (I.?ve|we.?ve) shipped|#systems"

echo ">> Asserting proof bar (money flex first)"
check "money flex \$1M+"            "\\\$1M"
check "quality flex +45% adoption"  "\\+45"
check "speed flex <30 days"         "(<|&lt;)30"
check "subtext 48,000+ emails"      "48,000"
check "subtext 4%+ reply"           "4%\\+? reply"
check "headcount-replace receipt"   "\\\$200K|SDR headcount"

echo ">> Asserting services"
check "services section anchor" "id=\"services\""
check "service: outbound"       "outbound"
check "service: AI sales"       "AI sales|sales assistants"
check "service: AI operations"  "AI operations"

echo ">> Asserting systems grid"
check "systems section anchor"  "id=\"systems\""
check "system: outbound engine" "Outbound Engine"
check "system: enterprise"      "Enterprise Adoption"
check "system: CV optimizer"    "CV Optimizer"
check "system: ProdCraft"       "ProdCraft"
check "system: mobile pipeline" "Shipping Pipeline|Mobile"
check "system: operator stack"  "Operator Stack|Agents"

echo ">> Asserting stack + how-i-work + recommendations"
check "stack: Claude"           "Claude"
check "stack: Cloudflare"       "Cloudflare"
check "how-i-work objections"   "ship in days|senior operator|walk.away"
check "recommendations section" "[Rr]ecommendations|shipped with"

echo ">> Asserting final CTA + footer"
check "contact anchor"          "id=\"contact\""
check "final CTA primary"       "Book a free build session|cal\\.com"
check "cal.com booking link"    "cal\\.com/debanjan-mazumdar-ben5rd"
check "LinkedIn link"           "linkedin\\.com"
check "footer nav present"      "id=\"contact\""

if [ "$FAILS" -gt 0 ]; then
  echo
  echo "FAIL: $FAILS front-door assertion(s) broke. Synthetic NOT green; LIVE-PROBATIONARY count cannot start." >&2
  exit 1
fi

echo
echo "PASS: portfolio_site front-door synthetic green against $URL"
