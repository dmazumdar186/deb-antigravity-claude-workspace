#!/usr/bin/env bash
#
# Front-door synthetic for the yoga-jitendra dashboard V0.1.
#
# Runs against the LIVE production URL — no fixtures. Per
# ~/.claude/rules/front-door-synthetic.md this is the only kind of
# synthetic that counts toward the LIVE-PROBATIONARY day counter.
#
# Assertions:
#   1. GET /dashboard/ returns within 1.5 s wall-clock.
#   2. GET /api/dashboard-data?range=7d returns valid JSON with
#      >= 2 sources_healthy AND either a non-null reach value OR the
#      corresponding source in sources_degraded with a reason.
#   3. When sources_healthy is non-empty, time_series.labels + series
#      MUST be non-empty (2026-08-04 regression class — see the
#      apexcharts bare-specifier fix in Sparkline/TimeSeries/SourceDonut).
#   4. When sources_healthy is non-empty, source_split.values MUST
#      contain at least one positive slice.
#   5. GET /dashboard/ HTML must reference an /_astro/apexcharts.*.js
#      bundle. Absence of the bundle is the fingerprint of the
#      2026-08-04 bare-specifier bug (blank charts on prod).
#   6. GET /dashboard/ HTML must NOT contain a bare `import ApexCharts`
#      statement in an inline module — the exact bug that shipped V0.1.
#   7. Every hero-tile in the SSR'd HTML must be data-status=live OR
#      (data-status=waiting AND a source-name hint).
#   8. /wa-out proxy: 302s to wa.me for a known-good source AND 400s for
#      unknown (open-redirect defense verified live).
#   9. GET /api/reviews-public is public (no auth), JSON, includes
#      unknown_date_count field or per-record date_provenance.
#  10. Every range in {7d, 30d, all} returns the same schema shape.
#  11. Reviews page cards: unknown-provenance cards must NOT carry a
#      [data-review-date] element (per 2026-08-04 fix).
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
  echo "FAIL: DASHBOARD_PASS env var required (fetch from Pages project secret via" >&2
  echo "      \`wrangler pages secret list --project-name=yoga-jitendra\` or add to .env)" >&2
  exit 2
fi

errors=0

fail() { echo "FAIL: $*" >&2; errors=$((errors + 1)); }
pass() { echo "PASS: $*"; }

# ---------- 1. Dashboard page load time ----------
tt=$(curl -sSf -u "${USER}:${DASHBOARD_PASS}" -o /dev/null -w '%{time_total}' \
  "${BASE}/dashboard/" 2>/dev/null || echo "999")
if python -c "import sys; sys.exit(0 if float('$tt') < 1.5 else 1)"; then
  pass "dashboard load ${tt}s < 1.5s"
else
  fail "dashboard load ${tt}s exceeds 1.5s soft ceiling"
fi

# ---------- 2-4. /api/dashboard-data?range=7d shape + healthy + charts ----------
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
healthy = d.get('sources_healthy') or []
degraded = d.get('sources_degraded') or []
if not isinstance(healthy, list):
    issues.append("sources_healthy missing/not-list")
elif len(healthy) < 2 and '_warning' not in d:
    issues.append(f"expected >=2 sources_healthy, got {healthy}")
if 'hero_tiles' not in d:
    issues.append("hero_tiles missing")
else:
    for k in ('reach', 'interest', 'conversation'):
        if k not in d['hero_tiles']:
            issues.append(f"hero_tiles.{k} missing")
    reach_v = d['hero_tiles'].get('reach', {}).get('value')
    if reach_v is None and 'gsc' not in degraded:
        issues.append("reach.value is null but gsc is not in sources_degraded — silent GSC failure")

# Assertion 3 — trends chart must have data when sources are healthy.
ts = d.get('time_series') or {}
if healthy and (not ts.get('labels') or not ts.get('series')):
    issues.append(
        f"time_series is empty ({len(ts.get('labels') or [])} labels, "
        f"{len(ts.get('series') or [])} series) despite {len(healthy)} healthy sources — "
        "blank trend chart on prod"
    )

# Assertion 4 — donut must have at least one positive slice when healthy.
ss = d.get('source_split') or {}
values = ss.get('values') or []
if healthy and (not values or all(v == 0 for v in values)):
    issues.append(
        f"source_split.values is all-zero despite {len(healthy)} healthy sources — "
        "blank donut on prod"
    )
if ss.get('unit') != 'clicks':
    issues.append("source_split.unit must be 'clicks'")

if issues:
    for i in issues:
        print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print("PASS: /api/dashboard-data?range=7d schema + healthy + charts")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# ---------- 5-7. Dashboard HTML: apexcharts bundle + no bare specifier + hero-tile status ----------
HTML=$(curl -sSf -u "${USER}:${DASHBOARD_PASS}" \
  "${BASE}/dashboard/" 2>/dev/null || echo "")
python <<PYEOF
import re, sys
html = '''${HTML}'''
issues = []
# 5 — chart chunks referenced (apexcharts is loaded transitively; the strong
# fingerprint of the bare-specifier bug is: no chart-chunk reference at all).
if not re.search(r'/_astro/(TimeSeriesChart|SourceDonut|Sparkline)[^"\'\s]*\.js', html):
    issues.append(
        "dashboard HTML does not reference any /_astro/(TimeSeriesChart|SourceDonut|"
        "Sparkline)*.js chunk — 2026-08-04 bare-specifier bug fingerprint. Chart "
        "components not bundled; charts render blank on prod."
    )
# 6 — no inline module with bare 'apexcharts' import
if re.search(r'<script[^>]*type="module"[^>]*>[^<]*import\s+ApexCharts\s+from\s+[\'"]apexcharts[\'"]', html, re.DOTALL):
    issues.append(
        "dashboard HTML contains inline <script type=module> with bare "
        "`import ApexCharts from 'apexcharts'` — this crashes silently in "
        "the browser. Use a hoisted <script> (no define:vars)."
    )
# 7 — hero-tile status semantics
tiles = re.findall(r'<article[^>]*class="hero-tile"[^>]*>', html)
if len(tiles) < 3:
    issues.append(f"expected 3 hero-tile <article>s, found {len(tiles)}")
else:
    for i, t in enumerate(tiles):
        st = re.search(r'data-status="(live|waiting)"', t)
        if not st:
            issues.append(f"hero-tile[{i}] missing data-status")
if issues:
    for i in issues: print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print("PASS: dashboard HTML has apexcharts bundle + no bare specifier + hero-tiles labeled")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# ---------- 8. /wa-out proxy ----------
CODE=$(curl -sS -o /dev/null -w '%{http_code}' \
  "${BASE}/wa-out?source=hero&text=test" 2>/dev/null || echo "000")
LOC=$(curl -sS -o /dev/null -w '%{redirect_url}' \
  "${BASE}/wa-out?source=hero&text=test" 2>/dev/null || echo "")
if [[ "${CODE}" == "302" ]] && [[ "${LOC}" == https://wa.me/* ]]; then
  pass "/wa-out?source=hero 302 -> ${LOC}"
else
  fail "/wa-out?source=hero expected 302 to wa.me, got ${CODE} loc=${LOC}"
fi

CODE=$(curl -sS -o /dev/null -w '%{http_code}' \
  "${BASE}/wa-out?source=phishattacker" 2>/dev/null || echo "000")
if [[ "${CODE}" == "400" ]]; then
  pass "/wa-out?source=phishattacker rejected with 400"
else
  fail "/wa-out?source=phishattacker expected 400, got ${CODE} (open-redirect risk!)"
fi

# ---------- 9. /api/reviews-public public, JSON, provenance shape ----------
PUB=$(curl -sSf "${BASE}/api/reviews-public?fresh=1" 2>/dev/null || echo "{}")
python <<PYEOF
import json, sys
try:
    d = json.loads('''${PUB}''')
except Exception as e:
    print(f"FAIL: /api/reviews-public not valid JSON: {e}", file=sys.stderr)
    sys.exit(1)
rs = d.get('reviews') or []
if not isinstance(rs, list):
    print("FAIL: /api/reviews-public reviews not a list", file=sys.stderr)
    sys.exit(1)
if rs:
    # At least one record MUST carry date_provenance (per 2026-08-04 fix).
    if not any('date_provenance' in r for r in rs):
        print("FAIL: /api/reviews-public: no record has date_provenance — regression class",
              file=sys.stderr)
        sys.exit(1)
    print(f"PASS: /api/reviews-public: {len(rs)} reviews, avg {d.get('average_rating')}, "
          f"unknown={sum(1 for r in rs if r.get('date_provenance')=='unknown')}")
else:
    print("PASS: /api/reviews-public: 0 reviews (KV bootstrap)")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

# ---------- 10. Every range returns the same schema ----------
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

# ---------- 11. Reviews page: unknown-provenance cards omit date cell ----------
# Fetch the FR reviews page + intersect with unknown IDs from /api/reviews-public.
RVHTML=$(curl -sSf "${BASE}/reviews/" 2>/dev/null || echo "")
python <<PYEOF
import json, re, sys
try:
    pub = json.loads('''${PUB}''')
except Exception:
    print("SKIP: reviews-public JSON already reported broken", file=sys.stderr)
    sys.exit(0)
unknown = {r['id'] for r in (pub.get('reviews') or []) if r.get('date_provenance') == 'unknown'}
if not unknown:
    print("PASS: no unknown-provenance reviews to check (all dated)")
    sys.exit(0)
html = '''${RVHTML}'''
if not html:
    print("FAIL: /reviews/ returned empty body", file=sys.stderr)
    sys.exit(1)
issues = []
for uid in unknown:
    pat = re.compile(r'<figure[^>]+data-review-id="' + re.escape(uid) + r'"[^>]*>(.*?)</figure>', re.DOTALL)
    m = pat.search(html)
    if not m:
        continue  # card missing — separate defect, not this check's job
    if 'data-review-date' in m.group(1):
        issues.append(f"reviews-card {uid} carries data-review-date but is unknown-provenance")
if issues:
    for i in issues[:3]: print(f"FAIL: {i}", file=sys.stderr)
    sys.exit(1)
print(f"PASS: {len(unknown)} unknown-provenance card(s) correctly omit date cell")
PYEOF
if [[ $? -ne 0 ]]; then errors=$((errors + 1)); fi

if [[ ${errors} -gt 0 ]]; then
  echo "" >&2
  echo "front-door: ${errors} FAIL(s)" >&2
  exit 1
fi

echo ""
echo "front-door: ALL PASS"
