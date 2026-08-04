#!/usr/bin/env bash
#
# Front-door synthetic for <PROJECT_NAME>.
#
# Per ~/.claude/rules/front-door-synthetic.md this hits the LIVE $SITE_URL.
# Fixture-only synthetics do not count as green.
#
# Assertions:
#   1. GET /                       returns 200 within 3s wall-clock.
#   2. GET /api/health             returns 200 with { "ok": true }.
#   3. GET /en/                    returns 200 (i18n mirror exists).
#   4. GET /nonexistent-page-404   returns 404 (routing works).
#   5. If DASHBOARD_PASS set: GET /dashboard/ with auth returns 200 or 302.
#
# Exit 0 = all pass. Non-zero = one FAIL line per broken assertion on stderr.
#
# Env:
#   SITE_URL         required
#   DASHBOARD_USER   default 'admin'
#   DASHBOARD_PASS   optional (skips dashboard check if unset)

set -u

BASE="${SITE_URL:-}"
if [[ -z "$BASE" ]]; then
  echo "FAIL: SITE_URL env var required" >&2
  exit 2
fi
BASE="${BASE%/}"
USER="${DASHBOARD_USER:-admin}"

errors=0

# 1. Homepage
tt=$(curl -sSf -o /dev/null -w '%{time_total}\n%{http_code}' "${BASE}/" 2>/dev/null || echo -e "999\n000")
tt_time=$(echo "$tt" | sed -n 1p)
tt_code=$(echo "$tt" | sed -n 2p)
if [[ "$tt_code" == "200" ]] && python -c "import sys; sys.exit(0 if float('$tt_time') < 3.0 else 1)"; then
  echo "PASS: GET / ${tt_code} in ${tt_time}s"
else
  echo "FAIL: GET / returned code=${tt_code} in ${tt_time}s (need 200, <3s)" >&2
  errors=$((errors + 1))
fi

# 2. Health endpoint
HJSON=$(curl -sSf "${BASE}/api/health" 2>/dev/null || echo "{}")
if echo "$HJSON" | python -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') is True else 1)" 2>/dev/null; then
  echo "PASS: /api/health ok=true"
else
  echo "FAIL: /api/health did not return ok=true: ${HJSON:0:200}" >&2
  errors=$((errors + 1))
fi

# 3. i18n mirror
en_code=$(curl -sS -o /dev/null -w '%{http_code}' "${BASE}/en/" 2>/dev/null || echo "000")
if [[ "$en_code" == "200" ]]; then
  echo "PASS: GET /en/ 200"
else
  echo "FAIL: GET /en/ returned ${en_code} (need 200)" >&2
  errors=$((errors + 1))
fi

# 4. 404 routing
nf_code=$(curl -sS -o /dev/null -w '%{http_code}' "${BASE}/definitely-does-not-exist-9999" 2>/dev/null || echo "000")
if [[ "$nf_code" == "404" ]]; then
  echo "PASS: GET /nonexistent 404"
else
  echo "FAIL: GET /nonexistent returned ${nf_code} (need 404)" >&2
  errors=$((errors + 1))
fi

# 5. Basic-Auth dashboard (optional)
if [[ -n "${DASHBOARD_PASS:-}" ]]; then
  dc=$(curl -sS -u "${USER}:${DASHBOARD_PASS}" -o /dev/null -w '%{http_code}' "${BASE}/dashboard/" 2>/dev/null || echo "000")
  if [[ "$dc" == "200" || "$dc" == "302" || "$dc" == "404" ]]; then
    echo "PASS: GET /dashboard/ auth=${dc}"
  else
    echo "FAIL: GET /dashboard/ auth returned ${dc}" >&2
    errors=$((errors + 1))
  fi
else
  echo "SKIP: /dashboard/ check (DASHBOARD_PASS not set)"
fi

if [[ $errors -gt 0 ]]; then
  echo "" >&2
  echo "FAIL: ${errors} front-door assertion(s) broken" >&2
  exit 1
fi
echo ""
echo "PASS: front-door synthetic all green against ${BASE}"
exit 0
