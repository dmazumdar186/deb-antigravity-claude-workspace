#!/usr/bin/env bash
# Full suite: fresh Playground, then every spec in order. Output: .tmp/results.json + screens/.
set -uo pipefail
cd "$(dirname "$0")/.."
tests/stop_server.sh
sleep 2
rm -f .tmp/suite-state.json
tests/start_server.sh > .tmp/pg.log 2>&1 &
for i in $(seq 1 100); do grep -q "Ready!" .tmp/pg.log 2>/dev/null && break; sleep 3; done
grep -q "Ready!" .tmp/pg.log || { echo "Playground did not start"; tail -20 .tmp/pg.log; exit 1; }
cd tests
node node_modules/playwright/cli.js test "$@"
code=$?
cd ..
tests/stop_server.sh
exit $code
