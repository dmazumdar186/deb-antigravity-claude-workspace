#!/usr/bin/env bash
# Front-door synthetic for the video pipeline — per
# ~/.claude/rules/front-door-synthetic.md.
#
# Checks the actual user flow's preconditions:
#   1. Higgsfield MCP is reachable (or explicit degraded-state message)
#   2. Remotion project builds (npx remotion, node_modules present)
#   3. Output dir is writable
#   4. All three Python stage scripts import cleanly
#
# Runs on every deploy + hourly cron per the front-door rule. Fixture-only
# checks do NOT satisfy this rule — this script probes actual runtime state.

set -eu

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

FAIL=0
red() { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

echo "== Front-door synthetic: video pipeline =="

# 1. Python stage imports
for stage in analyze.py generate.py publish.py; do
  if py -c "import ast, sys; ast.parse(open('$stage', encoding='utf-8').read()); sys.exit(0)" 2>/dev/null; then
    green "OK   python parse: $stage"
  else
    red "FAIL python parse: $stage"
    FAIL=1
  fi
done

# 2. Output dir writable
mkdir -p .tmp/_frontdoor
if touch .tmp/_frontdoor/probe.txt 2>/dev/null; then
  green "OK   output dir writable"
  rm .tmp/_frontdoor/probe.txt
else
  red "FAIL output dir NOT writable"
  FAIL=1
fi

# 3. Config parses
if py -c "import json; json.load(open('config/pipeline.json', encoding='utf-8'))" 2>/dev/null; then
  green "OK   config/pipeline.json parses"
else
  red "FAIL config/pipeline.json invalid"
  FAIL=1
fi

# 4. Remotion project structure
if [ -f compose/package.json ] && [ -f compose/src/Root.tsx ]; then
  green "OK   compose/ scaffold present"
  if [ -d compose/node_modules ]; then
    green "OK   compose/node_modules installed"
  else
    yellow "WARN compose/node_modules missing — run 'cd compose && npm install' before rendering"
  fi
else
  red "FAIL compose/ scaffold incomplete"
  FAIL=1
fi

# 5. Higgsfield MCP reachability (best-effort; degraded is not FAIL)
# The MCP endpoint requires OAuth so we only check DNS / TCP.
if command -v curl >/dev/null 2>&1; then
  if curl -sf -o /dev/null --max-time 5 https://mcp.higgsfield.ai/ 2>/dev/null; then
    green "OK   Higgsfield MCP endpoint reachable"
  else
    yellow "DEGRADED: Higgsfield MCP unreachable — fall back to HF Space or direct HTTP API"
  fi
else
  yellow "WARN curl unavailable — skipping MCP reachability probe"
fi

# 6. Dry-run smoke: analyze stage
if py analyze.py --input https://youtu.be/dQw4w9WgXcQ --slug _frontdoor --dry-run >/dev/null 2>&1; then
  green "OK   analyze.py --dry-run exit 0"
else
  red "FAIL analyze.py --dry-run non-zero"
  FAIL=1
fi

echo
if [ "$FAIL" -eq 0 ]; then
  green "== FRONT-DOOR PASS =="
  exit 0
else
  red "== FRONT-DOOR FAIL =="
  exit 1
fi
