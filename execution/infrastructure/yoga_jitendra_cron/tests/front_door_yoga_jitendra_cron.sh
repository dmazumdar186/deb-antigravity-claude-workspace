#!/usr/bin/env bash
#
# Front-door synthetic for yoga-jitendra-cron Worker.
# Hits the LIVE production URL — no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md.
#
# Assertions:
#   1. GET /health returns 200 with ok:true, kv_bound:true, all
#      secrets_present true, secrets_missing = [].
#   2. Dead-man: pipeline.last_run.date is not null and stale_hours
#      is <= 30 (cron fires daily at 06:00 Paris; >30h = one skipped run,
#      the exact 34-day-silence class the 2026-08-04 audit found).
#   3. Dead-man: pipeline.healthy is true.
#   4. Unauthenticated POST /run is rejected (401/403).
#
# Exit 0 = pass, non-zero = fail.
#
# Env:
#   SITE_URL   default https://yoga-jitendra-cron.debanjan186.workers.dev

set -u

SITE_URL="${SITE_URL:-https://yoga-jitendra-cron.debanjan186.workers.dev}"
errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

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
    issues.append(f"ok != true")
if d.get("kv_bound") is not True:
    issues.append("kv_bound != true — DASHBOARD_KV binding missing")
missing = d.get("secrets_missing") or []
if missing:
    issues.append(f"secrets_missing: {missing}")
pipeline = d.get("pipeline") or {}
last_run = pipeline.get("last_run")
if not last_run:
    issues.append("pipeline.last_run is null — cron has never fired successfully")
else:
    if not last_run.get("date"):
        issues.append("pipeline.last_run.date missing")
stale_hours = pipeline.get("stale_hours")
if stale_hours is None:
    issues.append("pipeline.stale_hours missing")
elif stale_hours > 30:
    issues.append(
        f"pipeline.stale_hours = {stale_hours} > 30h — cron has skipped a fire "
        f"(2026-08-04 audit class: shipped-claim survives silence)"
    )
if pipeline.get("healthy") is not True:
    issues.append(f"pipeline.healthy != true (got {pipeline.get('healthy')!r})")
if issues:
    for i in issues: print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print(f"PASS: /health OK — stale_hours={stale_hours}, last_run.date={last_run['date']}")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# ---------- 4. POST /run requires X-Worker-Secret ----------
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' \
  -X POST "${SITE_URL}/run" 2>/dev/null || echo "000")
if [[ "${CODE}" =~ ^(401|403)$ ]]; then
  pass "POST /run without secret rejected (HTTP ${CODE})"
else
  fail "POST /run without secret expected 401/403, got ${CODE} — auth guard regression!"
fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s)" >&2
  exit 1
fi

echo ""
echo "front-door: ALL PASS"
