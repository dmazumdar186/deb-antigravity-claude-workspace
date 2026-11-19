#!/usr/bin/env bash
#
# Front-door synthetic for the ProdCraft Med Spa operator dashboard
# (Cloudflare Pages project prodcraft-medspa-dashboard). Hits the LIVE site,
# no fixtures. Per ~/.claude/rules/front-door-synthetic.md.
#
# Read-only: only GETs. No queue transition, draft, preview status or config
# POST is ever sent.
#
# Assertions:
#   1. GET / without credentials returns 401 with the dashboard's own
#      WWW-Authenticate realm "ProdCraft Med Spa Dashboard" and
#      X-Robots-Tag: noindex (functions/_middleware.ts). A 503 means
#      DASHBOARD_PASS is missing on the Pages project; a 200 means the gate
#      is open. Both fail.
#   2. GET / with Basic Auth returns 200 and the real dashboard shell
#      (public/index.html: "ProdCraft <span>Med Spa</span>" header and the
#      Queue / Previews / Stats / Config tabs).
#   3. GET /app.js with Basic Auth returns 200 and calls /api/stats.
#   4. GET /api/stats with Basic Auth returns 200 JSON with funnel_by_metro,
#      reply_rate_per_touch, bounce_rate_30d and phase0 (proves the Pages
#      Function reaches Supabase with the service key).
#   5. GET /api/config with Basic Auth returns 200 JSON with proof_lines,
#      sender and phase0.
#
# Exit 0 = pass, non-zero = fail (one FAIL line per broken assertion).
#
# Env:
#   SITE_URL         default https://prodcraft-medspa-dashboard.pages.dev
#                    (wrangler.toml `name` = Pages project -> <name>.pages.dev)
#   DASHBOARD_USER   required (Pages secret, see dashboard/README.md)
#   DASHBOARD_PASS   required (Pages secret, see dashboard/README.md)

set -euo pipefail

SITE_URL="${SITE_URL:-https://prodcraft-medspa-dashboard.pages.dev}"
SITE_URL="${SITE_URL%/}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

if [[ -z "${DASHBOARD_USER:-}" || -z "${DASHBOARD_PASS:-}" ]]; then
  echo "FAIL: DASHBOARD_USER and DASHBOARD_PASS must be set (the dashboard is 100% behind Basic Auth;" >&2
  echo "      without them only the auth gate can be checked, which is not the user flow)." >&2
  exit 2
fi

# req NAME PATH [curl args...] -> prints HTTP status; headers/body in $TMP
req() {
  local name="$1" path="$2" code
  shift 2
  code="$(curl -sS -m 20 --connect-timeout 10 \
    -D "$TMP/$name.h" -o "$TMP/$name.b" -w '%{http_code}' \
    "$@" "${SITE_URL}${path}" 2>"$TMP/$name.err")" || true
  echo "${code:-000}"
}
hdr() { grep -i "^$2:" "$TMP/$1.h" 2>/dev/null | tail -n1 | cut -d: -f2- | tr -d '\r' | sed 's/^ *//' || true; }
body_has() { grep -qF -- "$2" "$TMP/$1.b" 2>/dev/null; }
snippet() { { head -c 200 "$TMP/$1.b"; cat "$TMP/$1.err"; } 2>/dev/null | tr '\n' ' ' || true; }
AUTH=(-u "${DASHBOARD_USER}:${DASHBOARD_PASS}")

# 1. Auth gate
CODE="$(req gate /)"
WWW="$(hdr gate www-authenticate)"
ROBOTS="$(hdr gate x-robots-tag)"
if [[ "$CODE" == "401" ]] && [[ "$WWW" == *'realm="ProdCraft Med Spa Dashboard"'* ]] && [[ "$ROBOTS" == *noindex* ]]; then
  pass "GET / unauthenticated -> 401 dashboard realm, noindex"
elif [[ "$CODE" == "503" ]]; then
  fail "GET / unauthenticated -> 503: DASHBOARD_PASS missing on the Pages project ($(snippet gate))"
else
  fail "GET / unauthenticated expected 401 + realm + noindex, got ${CODE}, www-authenticate '${WWW}', x-robots-tag '${ROBOTS}' (gate open or wrong deploy)"
fi

# 2. Dashboard shell
CODE="$(req home / "${AUTH[@]}")"
missing=()
for marker in 'ProdCraft <span>Med Spa</span>' 'data-tab="queue"' 'data-tab="previews"' 'data-tab="stats"' 'data-tab="config"' 'id="queue-list"'; do
  body_has home "$marker" || missing+=("$marker")
done
if [[ "$CODE" == "200" ]] && [[ ${#missing[@]} -eq 0 ]]; then
  pass "GET / authenticated -> 200 dashboard shell with 4 tabs"
else
  fail "GET / authenticated expected 200 dashboard shell, got ${CODE}; missing markers: ${missing[*]:-none} ($(snippet home))"
fi

# 3. Frontend bundle
CODE="$(req appjs /app.js "${AUTH[@]}")"
if [[ "$CODE" == "200" ]] && body_has appjs "api('/api/stats')"; then
  pass "GET /app.js -> 200, wires /api/stats"
else
  fail "GET /app.js expected 200 with api('/api/stats'), got ${CODE} ($(snippet appjs))"
fi

# json_keys NAME KEY... -> checks body is a JSON object holding every KEY
json_keys() {
  local name="$1"
  shift
  python3 - "$TMP/$name.b" "$@" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as e:
    print(f"not valid JSON ({e})"); sys.exit(1)
if not isinstance(d, dict):
    print("not a JSON object"); sys.exit(1)
if "error" in d:
    print(f"error payload: {str(d['error'])[:200]}"); sys.exit(1)
missing = [k for k in sys.argv[2:] if k not in d]
if missing:
    print("missing keys: " + ", ".join(missing)); sys.exit(1)
PY
}

# 4. /api/stats (Supabase read)
CODE="$(req stats /api/stats "${AUTH[@]}")"
if [[ "$CODE" == "200" ]] && ERR="$(json_keys stats funnel_by_metro reply_rate_per_touch bounce_rate_30d phase0)"; then
  pass "GET /api/stats -> 200 funnel JSON"
else
  fail "GET /api/stats expected 200 funnel JSON, got ${CODE}: ${ERR:-$(snippet stats)}"
fi
ERR=""

# 5. /api/config (Supabase read)
CODE="$(req config /api/config "${AUTH[@]}")"
if [[ "$CODE" == "200" ]] && ERR="$(json_keys config proof_lines sender phase0)"; then
  pass "GET /api/config -> 200 config JSON"
else
  fail "GET /api/config expected 200 config JSON, got ${CODE}: ${ERR:-$(snippet config)}"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s) against ${SITE_URL}" >&2
  exit 1
fi
echo ""
echo "front-door: ALL PASS (${SITE_URL})"
