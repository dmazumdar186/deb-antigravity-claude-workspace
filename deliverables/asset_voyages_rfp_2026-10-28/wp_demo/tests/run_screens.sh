#!/usr/bin/env bash
# Screenshots on a fresh seed: new Playground, screens.spec.js only, French locale.
set -uo pipefail
cd "$(dirname "$0")/.."
export LANG=fr_FR.UTF-8 LANGUAGE=fr_FR:fr LC_ALL=fr_FR.UTF-8
tests/stop_server.sh; sleep 2
tests/start_server.sh > .tmp/pg-screens.log 2>&1 &
for i in $(seq 1 100); do grep -q "Ready!" .tmp/pg-screens.log 2>/dev/null && break; sleep 3; done
grep -q "Ready!" .tmp/pg-screens.log || { echo "Playground did not start"; exit 1; }
cd tests
SHOTS=1 node node_modules/playwright/cli.js test --reporter=list
code=$?
cd ..; tests/stop_server.sh; exit $code
