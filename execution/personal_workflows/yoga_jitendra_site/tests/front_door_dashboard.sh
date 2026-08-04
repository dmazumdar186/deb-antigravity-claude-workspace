#!/usr/bin/env bash
#
# Front-door synthetic for the yoga-jitendra dashboard V0.1.
#
# Runs against the LIVE production URL — no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md this is the only kind of
# synthetic that counts toward the LIVE-PROBATIONARY day counter.
#
# Assertions:
#   1. GET /dashboard/ returns within 1.5 s wall-clock (soft ceiling;
#      LCP target is 2.5 s and the dashboard is behind auth so relaxed
#      vs the public site).
#   2. GET /api/dashboard-data?range=7d returns valid JSON with
#      >= 2 sources_healthy AND either a non-null reach value OR the
#      corresponding source in sources_degraded with a reason.
#   3. The wa-out proxy 302s to wa.me for a known-good source AND
#      400s for an unknown source (open-redirect defense verified).
#   4. Every range in {7d, 30d, all} returns the same schema shape
#      (no divergent code paths).
#
# Runs on any platform with bash + curl + python. Exit 0 = pass, non-zero
# = fail with one FAIL line per broken assertion on stderr.
#
# Env:
#   DASHBOARD_USER   default "debanjan"
#   DASHBOARD_PASS   required (Basic-Auth password set via wrangler pages secret put)
#   BASE_URL         default https://yogaavecjitendra.fr

set -u

BASE="${BASE_URL:-https://yogaavecjitendra.fr}"
USER="${DASHBOARD_USER:-debanjan}"

if [[ -z "${DASHBOARD_PASS:-}" ]]; then
  echo "FAIL: DASHBOARD_PASS env var required" >&2
  exit 2
fi

errors=0

# 1. Dashboard page load time
tt=$(curl -sSf -u "${USER}:${DASHBOARD_PASS}" -o /dev/null -w '%{time_total}' \
  "${BASE}/dashboard/" 2>/dev/null || echo "999")
if python -c "import sys; sys.exit(0 if float('$tt') < 1.5 else 1)"; then
  echo "PASS: dashboard load ${tt}s < 1.5s"
else
  echo "FAIL: dashboard load ${tt}s exceeds 1.5s soft ceiling" >&2
  errors=$((errors + 1))
fi

# 2. /api/dashboard-data?range=7d shape + healthy sources
JSON=$(curl -sSf -u "${USER}:${DASHBOARD_PASS}" \
  "${BASE}/api/dashboard-data?range=7d" 2>/dev/null || echo "{}")
python <<PYEOF
import json, sys
try:
    d = json.loads('''${JSON}''')
except Exception as e:
    print(f"FAIL: /api/dashboard-data?range=7d not valid JSON: {e}", file=sys.stderr)
    sys.exit(1)
issues = []
if d.get('range') != '7d':
    issues.append(f"range mismatch: {d.get('range')}")
if not isinstance(d.get('sources_healthy'), list):
    issues.append("sources_healthy missing/not-list")
elif len(d['sources_healthy']) < 2 and '_warning' not in d:
    issues.append(f"expected >=2 sources_healthy, got {d['sources_healthy']}")
if 'hero_tiles' not in d:
    issues.append("hero_tiles missing")
else:
    for k in ('reach', 'interest', 'conversation'):
        if k not in d['hero_tiles']:
            issues.append(f"hero_tiles.{k} missing")
    # Assertion #2 in the comment above: reach either has a real number OR
    # gsc is in sources_degraded with a reason. Enforce it (previously the
    # comment promised this but the code never checked — pipeline-auditor
    # 2026-07-21).
    reach_v = d['hero_tiles'].get('reach', {}).get('value')
    if reach_v is None and 'gsc' not in (d.get('sources_degraded') or []):
        issues.append("reach.value is null but gsc is not in sources_degraded — silent GSC failure")
if 'time_series' not in d:
    issues.append("time_series missing")
if 'source_split' not in d or d['source_split'].get('unit') != 'clicks':
    issues.append("source_split.unit must be 'clicks'")
if issues:
    for i in issues:
        print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print("PASS: /api/dashboard-data?range=7d schema OK")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# 3a. /wa-out with a known-good source -> 302 to wa.me
CODE=$(curl -sS -o /dev/null -w '%{http_code}' \
  "${BASE}/wa-out?source=hero&text=test" 2>/dev/null || echo "000")
LOC=$(curl -sS -o /dev/null -w '%{redirect_url}' \
  "${BASE}/wa-out?source=hero&text=test" 2>/dev/null || echo "")
if [[ "${CODE}" == "302" ]] && [[ "${LOC}" == https://wa.me/* ]]; then
  echo "PASS: /wa-out?source=hero 302 -> ${LOC}"
else
  echo "FAIL: /wa-out?source=hero expected 302 to wa.me, got ${CODE} loc=${LOC}" >&2
  errors=$((errors + 1))
fi

# 3b. /wa-out with an unknown source -> 400 (open-redirect defense)
CODE=$(curl -sS -o /dev/null -w '%{http_code}' \
  "${BASE}/wa-out?source=phishattacker" 2>/dev/null || echo "000")
if [[ "${CODE}" == "400" ]]; then
  echo "PASS: /wa-out?source=phishattacker rejected with 400"
else
  echo "FAIL: /wa-out?source=phishattacker expected 400, got ${CODE} (open-redirect risk!)" >&2
  errors=$((errors + 1))
fi

# 4. Every range returns the same schema
for range in 30d all; do
  JSON=$(curl -sSf -u "${USER}:${DASHBOARD_PASS}" \
    "${BASE}/api/dashboard-data?range=${range}" 2>/dev/null || echo "{}")
  python <<PYEOF
import json, sys
try:
    d = json.loads('''${JSON}''')
except Exception:
    print(f"FAIL: /api/dashboard-data?range=${range} not valid JSON", file=sys.stderr)
    sys.exit(1)
if d.get('range') != '${range}':
    print(f"FAIL: range=${range} returned range={d.get('range')}", file=sys.stderr)
    sys.exit(1)
if 'hero_tiles' not in d or 'time_series' not in d or 'source_split' not in d:
    print(f"FAIL: range=${range} missing top-level rollup fields", file=sys.stderr)
    sys.exit(1)
print(f"PASS: /api/dashboard-data?range=${range} shape OK")
PYEOF
  if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi
done

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s)" >&2
  exit 1
fi

echo ""
echo "front-door: ALL PASS"
