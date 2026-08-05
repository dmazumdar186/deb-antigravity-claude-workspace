#!/usr/bin/env bash
#
# Front-door synthetic for self-outbound-webhook Worker.
# Hits the LIVE production URL — no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md.
#
# Assertions:
#   1. GET /health returns 200 with { ok: true, kv_bound: true,
#      hmac_secret_bound: true, campaign_tag: "debanjanm-outbound-v2" }.
#   2. GET / (unknown route) returns 404 with { ok: false }.
#   3. POST /instantly WITHOUT a valid HMAC signature is rejected
#      (401/403/400) — verifies the guard hasn't regressed to accept-all.
#
# Exit 0 = pass, non-zero = fail.
#
# Env:
#   SITE_URL   default https://self-outbound-webhook.debanjan186.workers.dev

set -u

SITE_URL="${SITE_URL:-https://self-outbound-webhook.debanjan186.workers.dev}"
errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

# ---------- 1. /health payload ----------
JSON=$(curl -sSf -m 10 "${SITE_URL}/health" 2>/dev/null || echo "{}")
python <<PYEOF
import json, sys
try:
    d = json.loads('''${JSON}''')
except Exception as e:
    print(f"FAIL: /health not valid JSON: {e}", file=sys.stderr)
    sys.exit(1)
issues = []
if d.get("ok") is not True:
    issues.append(f"ok != true (got {d.get('ok')!r})")
if d.get("kv_bound") is not True:
    issues.append(f"kv_bound != true — SUPP_EVENTS binding missing")
if d.get("hmac_secret_bound") is not True:
    issues.append("hmac_secret_bound != true — INSTANTLY_WEBHOOK_SECRET missing")
if d.get("campaign_tag") != "debanjanm-outbound-v2":
    issues.append(f"campaign_tag drift: {d.get('campaign_tag')!r}")
if issues:
    for i in issues: print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print("PASS: /health payload shape")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# ---------- 2. Unknown route returns 404 ----------
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' "${SITE_URL}/" 2>/dev/null || echo "000")
if [[ "${CODE}" == "404" ]]; then
  pass "GET / -> 404 (unknown route)"
else
  fail "GET / expected 404, got ${CODE}"
fi

# ---------- 3. POST /instantly without HMAC is rejected ----------
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' \
  -X POST -H "content-type: application/json" \
  -d '{"event_type":"reply_received","email":"probe@example.com"}' \
  "${SITE_URL}/instantly" 2>/dev/null || echo "000")
if [[ "${CODE}" =~ ^(400|401|403)$ ]]; then
  pass "POST /instantly without HMAC rejected (HTTP ${CODE})"
else
  fail "POST /instantly without HMAC expected 400/401/403, got ${CODE} — auth guard regression!"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s)" >&2
  exit 1
fi

echo ""
echo "front-door: ALL PASS"
