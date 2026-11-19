#!/usr/bin/env bash
#
# Front-door synthetic for the prodcraft-preview-host Worker
# (preview/worker/src/index.ts), served on the wildcard route
# *.preview.prodcraft.fyi/*. Hits the LIVE route, no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md.
#
# Read-only: only GETs. /remove is fetched with GET (confirmation form) and
# never POSTed; no control-plane call carries a secret.
#
# Assertions (on a probe host whose slug is never published):
#   1. GET /robots.txt returns 200 "Disallow: /" with X-Robots-Tag noindex.
#   2. GET / returns the Worker's own 404 page ("Preview not found") with
#      X-Robots-Tag noindex and the Worker CSP (frame-ancestors 'none'); a
#      Cloudflare error page or wildcard-DNS miss fails.
#   3. GET /remove returns 200 with the takedown confirmation form
#      ("Remove this concept preview?", POST /remove, the probe host name).
#   4. GET /api/meta without a bearer returns 401 {"error":"unauthorized"}
#      (control plane is locked).
#   5. Optional: if PREVIEW_URL is set to a real armed preview
#      (https://{slug}-{suffix}.preview.prodcraft.fyi), GET it and require
#      200 text/html with X-Robots-Tag noindex and none of the Worker's
#      not-found / removed / expired pages.
#
# Exit 0 = pass, non-zero = fail (one FAIL line per broken assertion).
#
# Env:
#   SITE_URL     default https://front-door-probe-000000.preview.prodcraft.fyi
#                (wrangler.toml route *.preview.prodcraft.fyi/*; slug never published)
#   PREVIEW_URL  optional, a live armed preview to check end to end

set -euo pipefail

SITE_URL="${SITE_URL:-https://front-door-probe-000000.preview.prodcraft.fyi}"
SITE_URL="${SITE_URL%/}"
PROBE_HOST="${SITE_URL#*://}"
PROBE_HOST="${PROBE_HOST%%/*}"
PREVIEW_URL="${PREVIEW_URL:-}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

# req NAME URL [curl args...] -> prints HTTP status; headers/body in $TMP
req() {
  local name="$1" url="$2" code
  shift 2
  code="$(curl -sS -m 15 --connect-timeout 10 \
    -D "$TMP/$name.h" -o "$TMP/$name.b" -w '%{http_code}' \
    "$@" "$url" 2>"$TMP/$name.err")" || true
  echo "${code:-000}"
}
hdr() { grep -i "^$2:" "$TMP/$1.h" 2>/dev/null | tail -n1 | cut -d: -f2- | tr -d '\r' | sed 's/^ *//' || true; }
body_has() { grep -qF -- "$2" "$TMP/$1.b" 2>/dev/null; }
snippet() { { head -c 200 "$TMP/$1.b"; cat "$TMP/$1.err"; } 2>/dev/null | tr '\n' ' ' || true; }

# 1. robots.txt
CODE="$(req robots "${SITE_URL}/robots.txt")"
if [[ "$CODE" == "200" ]] && body_has robots "Disallow: /" && [[ "$(hdr robots x-robots-tag)" == *noindex* ]]; then
  pass "GET /robots.txt -> 200 Disallow: /, noindex"
else
  fail "GET /robots.txt expected 200 'Disallow: /' + noindex, got ${CODE} ($(snippet robots))"
fi

# 2. Unknown slug -> Worker 404 page
CODE="$(req root "${SITE_URL}/")"
CSP="$(hdr root content-security-policy)"
if [[ "$CODE" == "404" ]] && body_has root "Preview not found" \
   && [[ "$(hdr root x-robots-tag)" == *noindex* ]] && [[ "$CSP" == *"frame-ancestors 'none'"* ]]; then
  pass "GET / on probe host -> Worker 404 'Preview not found', noindex, CSP"
else
  fail "GET / on probe host expected Worker 404 'Preview not found' + noindex + CSP, got ${CODE}, csp '${CSP}' ($(snippet root))"
fi

# 3. Takedown confirmation form (GET only)
CODE="$(req remove "${SITE_URL}/remove")"
if [[ "$CODE" == "200" ]] && body_has remove "Remove this concept preview?" \
   && body_has remove 'action="/remove"' && body_has remove "Remove ${PROBE_HOST}"; then
  pass "GET /remove -> 200 confirmation form for ${PROBE_HOST}"
else
  fail "GET /remove expected 200 confirmation form for ${PROBE_HOST}, got ${CODE} ($(snippet remove))"
fi

# 4. Control plane locked
CODE="$(req meta "${SITE_URL}/api/meta?host=${PROBE_HOST}")"
if [[ "$CODE" == "401" ]] && body_has meta '"error":"unauthorized"'; then
  pass "GET /api/meta without bearer -> 401 unauthorized"
else
  fail "GET /api/meta without bearer expected 401 unauthorized, got ${CODE} ($(snippet meta)) (control-plane auth regression!)"
fi

# 5. Optional: a real armed preview end to end
if [[ -n "$PREVIEW_URL" ]]; then
  CODE="$(req live "${PREVIEW_URL%/}/")"
  CTYPE="$(hdr live content-type)"
  if [[ "$CODE" == "200" ]] && [[ "$CTYPE" == text/html* ]] && [[ "$(hdr live x-robots-tag)" == *noindex* ]] \
     && ! body_has live "Preview not found" && ! body_has live "has been removed" && ! body_has live "has expired"; then
    pass "GET ${PREVIEW_URL} -> 200 live preview, noindex"
  else
    fail "GET ${PREVIEW_URL} expected 200 live preview HTML + noindex, got ${CODE}, content-type '${CTYPE}' ($(snippet live))"
  fi
else
  echo "INFO: PREVIEW_URL unset; armed-preview check (5) not run"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s) against ${SITE_URL}" >&2
  exit 1
fi
echo ""
echo "front-door: ALL PASS (${SITE_URL})"
