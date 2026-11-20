#!/usr/bin/env bash
# GreenJobs: deploy the current commit to STAGING, then smoke it. Dry-run by default.
#   bash execution/gtm_client_workflows/greenjobs_redesign/deploy/stage.sh            # print the exact commands
#   GREENJOBS_RELEASE_TARGET=staging bash .../deploy/stage.sh --execute              # run them
# Needs (execute only): CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, and for the smoke write checks
# GREENJOBS_SMOKE_ACCESS_CLIENT_ID / _SECRET and GREENJOBS_SMOKE_BUILD_TOKEN (ENVIRONMENTS.md).
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
HERE="execution/gtm_client_workflows/greenjobs_redesign/deploy"
SHA="$(git rev-parse HEAD)"
LEDGER="${GREENJOBS_LEDGER_DIR:-.tmp/greenjobs_release/staging}"
EXECUTE=0
for a in "$@"; do [ "$a" = "--execute" ] && EXECUTE=1; done

if [ "$EXECUTE" -eq 1 ] && [ -n "$(git status --porcelain)" ]; then
  echo "refusing: working tree is dirty; staging deploys only committed content" >&2; exit 3
fi

python3 "$HERE/release.py" stage --sha "$SHA" --ledger-dir "$LEDGER" "$@"

if [ "$EXECUTE" -eq 1 ]; then
  set +e
  python3 "$HERE/smoke.py" --env staging --sha "$SHA" --out "$LEDGER/smoke.json"
  rc=$?
  set -e
  python3 "$HERE/release.py" record-smoke --ledger-dir "$LEDGER" --smoke "$LEDGER/smoke.json"
  exit "$rc"
else
  echo
  echo "then: python3 $HERE/smoke.py --env staging --sha $SHA --out $LEDGER/smoke.json"
  echo "then: python3 $HERE/release.py record-smoke --ledger-dir $LEDGER --smoke $LEDGER/smoke.json"
fi
