#!/usr/bin/env bash
# Front-door synthetic for {{APP_SLUG}}.
# Hits the deployed backend + validates the OTA update channel manifest.
# Exits 0 on PASS, non-zero on FAIL. Emits a one-line summary either way.
#
# Per ~/.claude/rules/front-door-synthetic.md: this must run against LIVE infra,
# not fixtures. Do not point at localhost.

set -euo pipefail

API_URL="${API_BASE_URL:?set API_BASE_URL to the deployed backend base URL}"
UPDATE_URL="${EAS_UPDATE_URL:-}"  # optional: if set, we probe it too
STATUS=0

echo "[front-door] target: ${API_URL}"

# --- 1. Backend health ---
HEALTH_URL="${API_URL%/}/api/health"
HEALTH_JSON=$(curl -fsSL --max-time 10 "${HEALTH_URL}" || echo "")
if [[ -z "${HEALTH_JSON}" ]]; then
  echo "[front-door] FAIL: /api/health unreachable at ${HEALTH_URL}" >&2
  STATUS=1
elif ! echo "${HEALTH_JSON}" | grep -q '"ok":true'; then
  echo "[front-door] FAIL: /api/health did not return ok:true" >&2
  echo "  body: ${HEALTH_JSON}" >&2
  STATUS=1
else
  echo "[front-door] PASS: /api/health ok"
fi

# --- 2. OTA update manifest (if configured) ---
if [[ -n "${UPDATE_URL}" ]]; then
  MANIFEST=$(curl -fsSL --max-time 10 \
    -H "expo-runtime-version: 1.0.0" \
    -H "expo-platform: ios" \
    "${UPDATE_URL}" || echo "")
  if [[ -z "${MANIFEST}" ]]; then
    echo "[front-door] FAIL: OTA manifest unreachable at ${UPDATE_URL}" >&2
    STATUS=1
  else
    echo "[front-door] PASS: OTA manifest reachable"
  fi
else
  echo "[front-door] SKIP: EAS_UPDATE_URL not set (OTA not configured yet)"
fi

# --- 3. Python acceptance gate (delegated) ---
if command -v py >/dev/null 2>&1; then
  PYCMD=py
elif command -v python3 >/dev/null 2>&1; then
  PYCMD=python3
else
  PYCMD=python
fi
if ! API_BASE_URL="${API_URL}" "${PYCMD}" "$(dirname "$0")/acceptance_{{APP_SLUG}}.py"; then
  STATUS=1
fi

exit ${STATUS}
