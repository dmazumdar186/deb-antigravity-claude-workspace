#!/usr/bin/env bash
#
# Front-door synthetic for the greenjobs-ask Worker ("Ask GreenJobs" backend,
# worker/index.js). Hits the LIVE Worker URL, no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md.
#
# Never sends a query that reaches OpenRouter: every request below is answered
# by the Worker before the rate limiter, the dataset fetch and the model call.
#
# Assertions:
#   1. GET / returns 404 JSON {"error":"POST /ask"} (the Worker's own route
#      guard, not a Cloudflare error page) with access-control-allow-origin set
#      to the demo site origin (wrangler.toml ALLOWED_ORIGIN).
#   2. OPTIONS /ask (CORS preflight from the demo site) returns 204 with the
#      same allow-origin and allow-methods listing POST.
#   3. POST /ask from a foreign Origin returns 403 {"error":"origin not allowed"}
#      (origin lock has not regressed; nothing is billed).
#
# Exit 0 = pass, non-zero = fail (one FAIL line per broken assertion).
#
# Env:
#   SITE_URL        default https://greenjobs-ask.debanjan186.workers.dev
#                   (wrangler.toml name + the account's workers.dev subdomain)
#   ALLOWED_ORIGIN  default https://greenjobs-redesign.pages.dev (wrangler.toml)

set -euo pipefail

SITE_URL="${SITE_URL:-https://greenjobs-ask.debanjan186.workers.dev}"
SITE_URL="${SITE_URL%/}"
ALLOWED_ORIGIN="${ALLOWED_ORIGIN:-https://greenjobs-redesign.pages.dev}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

# req NAME METHOD PATH [curl args...] -> prints HTTP status; headers/body in $TMP
req() {
  local name="$1" method="$2" path="$3" code
  shift 3
  code="$(curl -sS -m 15 --connect-timeout 10 -X "$method" \
    -D "$TMP/$name.h" -o "$TMP/$name.b" -w '%{http_code}' \
    "$@" "${SITE_URL}${path}" 2>"$TMP/$name.err")" || true
  echo "${code:-000}"
}
hdr() { grep -i "^$2:" "$TMP/$1.h" 2>/dev/null | tail -n1 | cut -d: -f2- | tr -d '\r' | sed 's/^ *//' || true; }
body_has() { grep -qF -- "$2" "$TMP/$1.b" 2>/dev/null; }

# 1. Route guard on GET /
CODE="$(req root GET /)"
ACAO="$(hdr root access-control-allow-origin)"
if [[ "$CODE" == "404" ]] && body_has root '"error":"POST /ask"' && [[ "$ACAO" == "$ALLOWED_ORIGIN" ]]; then
  pass "GET / -> 404 Worker route guard, allow-origin ${ACAO}"
else
  fail "GET / expected 404 {\"error\":\"POST /ask\"} + allow-origin ${ALLOWED_ORIGIN}; got ${CODE}, allow-origin '${ACAO}', body: $(head -c 200 "$TMP/root.b" 2>/dev/null; cat "$TMP/root.err" 2>/dev/null)"
fi

# 2. CORS preflight from the demo site
CODE="$(req pre OPTIONS /ask -H "Origin: ${ALLOWED_ORIGIN}" -H "Access-Control-Request-Method: POST")"
ACAO="$(hdr pre access-control-allow-origin)"
METHODS="$(hdr pre access-control-allow-methods)"
if [[ "$CODE" == "204" ]] && [[ "$ACAO" == "$ALLOWED_ORIGIN" ]] && [[ "$METHODS" == *POST* ]]; then
  pass "OPTIONS /ask -> 204, allow-origin ${ACAO}, methods ${METHODS}"
else
  fail "OPTIONS /ask expected 204 + allow-origin ${ALLOWED_ORIGIN} + POST; got ${CODE}, '${ACAO}', '${METHODS}'"
fi

# 3. Origin lock (no model call: rejected before rate limit / dataset / OpenRouter)
CODE="$(req foreign POST /ask -H "Origin: https://front-door-probe.invalid" \
  -H "content-type: application/json" --data '{"edition":"ie","query":"x","limit":1}')"
if [[ "$CODE" == "403" ]] && body_has foreign '"error":"origin not allowed"'; then
  pass "POST /ask from foreign origin -> 403 origin not allowed"
else
  fail "POST /ask from foreign origin expected 403 origin not allowed; got ${CODE}: $(head -c 200 "$TMP/foreign.b" 2>/dev/null)"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s) against ${SITE_URL}" >&2
  exit 1
fi
echo ""
echo "front-door: ALL PASS (${SITE_URL})"
