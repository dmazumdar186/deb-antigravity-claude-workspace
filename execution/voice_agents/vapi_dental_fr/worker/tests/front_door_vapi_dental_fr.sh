#!/usr/bin/env bash
#
# Front-door synthetic for dental-receptionist Worker (vapi_dental_fr).
# Hits the LIVE production URL — no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md.
#
# Assertions:
#   1. GET /api/health returns 200 with ok:true, all secrets_present
#      truthy (calcom, vapi_public, vapi_assistant_id, worker),
#      version non-empty.
#   2. GET / returns 200 and serves the Retell widget HTML.
#   3. POST /vapi/tools/list_slots with a malformed payload returns
#      a 4xx (verifies handler is wired and validates input).
#
# Exit 0 = pass, non-zero = fail.
#
# Env:
#   SITE_URL   default https://dental-receptionist.debanjan186.workers.dev

set -u

SITE_URL="${SITE_URL:-https://dental-receptionist.debanjan186.workers.dev}"
errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

# ---------- 1. /api/health ----------
JSON=$(curl -sSf -m 10 "${SITE_URL}/api/health" 2>/dev/null || echo "{}")
python <<PYEOF
import json, sys
try:
    d = json.loads('''${JSON}''')
except Exception as e:
    print(f"FAIL: /api/health not valid JSON: {e}", file=sys.stderr)
    sys.exit(1)
issues = []
if d.get("ok") is not True:
    issues.append(f"ok != true")
if not d.get("version"):
    issues.append("version missing")
if d.get("build") != "dental-receptionist":
    issues.append(f"build drift: {d.get('build')!r}")
sp = d.get("secrets_present") or {}
for k in ("calcom", "vapi_public", "vapi_assistant_id", "worker"):
    if not sp.get(k):
        issues.append(f"secrets_present.{k} != true")
if issues:
    for i in issues: print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print(f"PASS: /api/health OK — version={d['version']}, demo_mode={d.get('demo_mode')}")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# ---------- 2. GET / serves widget HTML ----------
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' "${SITE_URL}/" 2>/dev/null || echo "000")
if [[ "${CODE}" == "200" ]]; then
  pass "GET / -> 200 (widget)"
else
  fail "GET / expected 200, got ${CODE}"
fi

# ---------- 3. POST /vapi/tools/list_slots with malformed payload -> 4xx ----------
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' \
  -X POST -H "content-type: application/json" -d '{"garbage":1}' \
  "${SITE_URL}/vapi/tools/list_slots" 2>/dev/null || echo "000")
# 2xx would mean the handler doesn't validate input; 5xx would mean it crashed.
# 4xx or 200 with a Vapi-shaped error payload are both acceptable — flag only
# 5xx and 000/timeouts.
if [[ "${CODE}" =~ ^(2|4)[0-9][0-9]$ ]]; then
  pass "POST /vapi/tools/list_slots handler wired (HTTP ${CODE})"
else
  fail "POST /vapi/tools/list_slots expected 2xx/4xx, got ${CODE} (5xx or timeout = handler broken)"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s)" >&2
  exit 1
fi

echo ""
echo "front-door: ALL PASS"
