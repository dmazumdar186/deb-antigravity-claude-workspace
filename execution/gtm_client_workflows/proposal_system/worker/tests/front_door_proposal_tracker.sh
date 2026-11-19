#!/usr/bin/env bash
#
# Front-door synthetic for the proposal-tracker Worker (worker/src/index.js).
# Hits the LIVE Worker URL, no fixtures. Per ~/.claude/rules/front-door-synthetic.md.
#
# Read-only: no proposal is opened (that would log an open and ping Telegram),
# nothing is published, no pixel is fetched.
#
# Assertions:
#   1. GET /health returns 200 JSON with ok:true, kv_bound:true (PROPOSALS KV
#      bound, so /p/<slug> can serve) and telegram_bound:true (open alerts can
#      fire), plus a ts stamp.
#   2. GET /p/<unknown slug> returns the Worker's own 404 "Not found" (proves
#      the proposal route reads KV; "KV not bound" 500 or a CF error page fails).
#   3. PUT /publish/<slug> without X-Publish-Secret returns 401
#      {"error":"unauthorised"} (publish auth guard; nothing is written).
#   4. GET /opens/<slug> without X-Publish-Secret returns 401 (open log is private).
#
# Exit 0 = pass, non-zero = fail (one FAIL line per broken assertion).
#
# Env:
#   SITE_URL   default https://proposal-tracker.debanjan186.workers.dev
#              (proposal_system/README.md, "Deployed 2026-09-30")

set -euo pipefail

SITE_URL="${SITE_URL:-https://proposal-tracker.debanjan186.workers.dev}"
SITE_URL="${SITE_URL%/}"
PROBE_SLUG="front-door-probe-nonexistent"
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
body_has() { grep -qF -- "$2" "$TMP/$1.b" 2>/dev/null; }
snippet() { { head -c 200 "$TMP/$1.b"; cat "$TMP/$1.err"; } 2>/dev/null | tr '\n' ' ' || true; }

# 1. /health
CODE="$(req health GET /health)"
if [[ "$CODE" != "200" ]]; then
  fail "GET /health expected 200, got ${CODE}: $(snippet health)"
elif HEALTH_ERR="$(python3 - "$TMP/health.b" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as e:
    print(f"not valid JSON ({e})"); sys.exit(1)
issues = []
if d.get("ok") is not True: issues.append(f"ok != true ({d.get('ok')!r})")
if d.get("kv_bound") is not True: issues.append("kv_bound != true (PROPOSALS KV unbound: /p/<slug> 500s)")
if d.get("telegram_bound") is not True: issues.append("telegram_bound != true (open alerts silently dropped)")
if not d.get("ts"): issues.append("ts missing")
if issues:
    print("; ".join(issues)); sys.exit(1)
PY
)"; then
  pass "GET /health -> ok, kv_bound, telegram_bound"
else
  fail "GET /health: ${HEALTH_ERR}"
fi

# 2. Proposal route reads KV (unknown slug -> Worker 404, no open recorded)
CODE="$(req page GET "/p/${PROBE_SLUG}")"
if [[ "$CODE" == "404" ]] && [[ "$(tr -d '\r\n' < "$TMP/page.b")" == "Not found" ]]; then
  pass "GET /p/${PROBE_SLUG} -> Worker 404 Not found"
else
  fail "GET /p/${PROBE_SLUG} expected Worker 404 'Not found', got ${CODE}: $(snippet page)"
fi

# 3. Publish auth guard
CODE="$(req publish PUT "/publish/${PROBE_SLUG}" -H "content-type: text/html" --data "<p>probe</p>")"
if [[ "$CODE" == "401" ]] && body_has publish '"error":"unauthorised"'; then
  pass "PUT /publish without secret -> 401 unauthorised"
else
  fail "PUT /publish without secret expected 401 unauthorised, got ${CODE}: $(snippet publish) (auth guard regression!)"
fi

# 4. Opens log is private
CODE="$(req opens GET "/opens/${PROBE_SLUG}")"
if [[ "$CODE" == "401" ]] && body_has opens '"error":"unauthorised"'; then
  pass "GET /opens without secret -> 401 unauthorised"
else
  fail "GET /opens without secret expected 401, got ${CODE}: $(snippet opens)"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s) against ${SITE_URL}" >&2
  exit 1
fi
echo ""
echo "front-door: ALL PASS (${SITE_URL})"
