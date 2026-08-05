#!/usr/bin/env bash
#
# Front-door synthetic for cv-optimizer-api Worker.
# Hits the LIVE production URL — no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md.
#
# Assertions:
#   1. GET /api/health returns 200 with status:"ok", kv_check:"pass",
#      and every entry in secrets_present is true (worker_secret,
#      gemini, anthropic, firecrawl).
#   2. version is non-empty (surfaces bad build stamp).
#   3. prompt_fingerprint + schema_fingerprint are non-empty (surfaces
#      a broken embed-prompts.mjs build step producing empty stubs).
#   4. POST /api/optimize WITHOUT X-Worker-Secret is rejected
#      (401/403) — verifies the auth guard hasn't regressed.
#
# Exit 0 = pass, non-zero = fail.
#
# Env:
#   SITE_URL   default https://cv-optimizer-api.debanjan186.workers.dev

set -u

SITE_URL="${SITE_URL:-https://cv-optimizer-api.debanjan186.workers.dev}"
errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

JSON=$(curl -sSf -m 10 "${SITE_URL}/api/health" 2>/dev/null || echo "{}")
python <<PYEOF
import json, sys
try:
    d = json.loads('''${JSON}''')
except Exception as e:
    print(f"FAIL: /api/health not valid JSON: {e}", file=sys.stderr)
    sys.exit(1)
issues = []
if d.get("status") != "ok":
    issues.append(f"status != 'ok' (got {d.get('status')!r})")
if d.get("kv_check") != "pass":
    issues.append(f"kv_check != 'pass' — RATE_LIMIT KV broken")
sp = d.get("secrets_present") or {}
for k in ("worker_secret", "gemini", "anthropic", "firecrawl"):
    if not sp.get(k):
        issues.append(f"secrets_present.{k} != true")
if not d.get("version"):
    issues.append("version missing (bad build stamp)")
for fp in ("prompt_fingerprint", "schema_fingerprint"):
    if not d.get(fp):
        issues.append(f"{fp} missing — embed-prompts.mjs build step likely broken")
if issues:
    for i in issues: print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print(f"PASS: /api/health OK — version={d['version']}, prompt_fp={d['prompt_fingerprint']}")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# ---------- 4. POST /api/optimize requires X-Worker-Secret ----------
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' \
  -X POST -H "content-type: application/json" -d '{}' \
  "${SITE_URL}/api/optimize" 2>/dev/null || echo "000")
if [[ "${CODE}" =~ ^(401|403)$ ]]; then
  pass "POST /api/optimize without secret rejected (HTTP ${CODE})"
else
  fail "POST /api/optimize without secret expected 401/403, got ${CODE} — auth guard regression!"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s)" >&2
  exit 1
fi

echo ""
echo "front-door: ALL PASS"
