#!/usr/bin/env bash
# QA monkey (../qa/A/monkey_A.mjs) against a fresh local Playground: seed 20261105, 300 actions x 4 roles.
set -uo pipefail
cd "$(dirname "$0")/.."
tests/stop_server.sh; sleep 2
tests/start_server.sh > .tmp/pg-monkey-${WP_PORT:-9400}.log 2>&1 &
for i in $(seq 1 100); do grep -q "Ready!" .tmp/pg-monkey-${WP_PORT:-9400}.log 2>/dev/null && break; sleep 3; done
grep -q "Ready!" .tmp/pg-monkey-${WP_PORT:-9400}.log || { echo "Playground did not start"; exit 1; }
( cd ../qa/A && WP_BASE=http://127.0.0.1:${WP_PORT:-9400} node monkey_A.mjs 20261105 300 )
code=$?
tests/stop_server.sh; exit $code
