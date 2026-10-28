#!/usr/bin/env bash
# Run every automated gate on site/ and collect output: research/warroom/gates_<tag>.txt. Usage: bash research/gates.sh <tag>
set -u
TAG="${1:-x}"; OUT="research/warroom/gates_${TAG}.txt"; ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
{ echo "# gates $TAG $(date -u +%FT%TZ)"
  echo "## site_check"; node ../../.claude/skills/site-redesign/scripts/site_check.mjs --site site --pages /,/privacy/ --allow-hosts static.cloudflareinsights.com,cloudflareinsights.com 2>&1 | tail -40
  node research/serve_csp.mjs site 8794 >/tmp/serve_csp.log 2>&1 & SP=$!; sleep 2
  echo "## functional_v4"; timeout 600 node research/functional_v4.mjs http://localhost:8794 2>&1 | tail -60
  echo "## screens_v4"; rm -rf research/screens_v4; timeout 600 node research/screens_v4.mjs http://localhost:8794 2>&1 | tail -20; ls research/screens_v4 2>/dev/null | wc -l | sed 's/^/pngs: /'
  echo "## grep forbidden"; grep -n -i -E "jitendra|lorem|TODO|placeholder" site/index.html site/js/*.js site/css/*.css | head -10 || true
  echo "## weight"; du -ch site/index.html site/css/styles.css site/js/*.js | tail -1
  kill $SP 2>/dev/null
} > "$OUT" 2>&1
echo "$OUT"; grep -c -i -E "fail|error|✗" "$OUT" | sed 's/^/fail-ish lines: /'
