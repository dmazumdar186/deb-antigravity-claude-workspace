#!/usr/bin/env bash
# GreenJobs: promote a sha that passed staging smoke to PRODUCTION. Dry-run by default.
#   bash .../deploy/promote.sh --staging-record path/to/staging/deploy_record.json
#   GREENJOBS_RELEASE_TARGET=production bash .../deploy/promote.sh --execute --staging-record ... [--allow-destructive] [--canary]
# The normal path is the GitHub workflow "greenjobs-promote" (required reviewer). From a terminal the same gates
# apply: HEAD must be the promoted sha, the tree clean, the staging record a full smoke pass for that sha, a D1
# backup stored before any migration, and an automatic rollback if the read-only smoke fails.
# Needs (execute only): GREENJOBS_PROD_CLOUDFLARE_API_TOKEN, GREENJOBS_PROD_CLOUDFLARE_ACCOUNT_ID.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
HERE="execution/gtm_client_workflows/greenjobs_redesign/deploy"
SHA="$(git rev-parse HEAD)"
LEDGER="${GREENJOBS_LEDGER_DIR:-.tmp/greenjobs_release/production}"
EXECUTE=0; CANARY=(); PASS=()
for a in "$@"; do
  case "$a" in
    --execute) EXECUTE=1; PASS+=("$a") ;;
    --canary) CANARY=(--canary) ;;
    *) PASS+=("$a") ;;
  esac
done

if [ "$EXECUTE" -eq 1 ] && [ -n "$(git status --porcelain)" ]; then
  echo "refusing: working tree is dirty; promote only the committed sha" >&2; exit 3
fi

python3 "$HERE/release.py" promote --sha "$SHA" --ledger-dir "$LEDGER" "${PASS[@]}"

if [ "$EXECUTE" -eq 1 ]; then
  set +e
  python3 "$HERE/smoke.py" --env production --sha "$SHA" --out "$LEDGER/smoke.json" "${CANARY[@]}"
  rc=$?
  set -e
  python3 "$HERE/release.py" record-smoke --ledger-dir "$LEDGER" --smoke "$LEDGER/smoke.json"
  if [ "$rc" -ne 0 ]; then
    echo "production smoke FAILED: rolling back to the recorded previous versions" >&2
    cp "$LEDGER/deploy_record.json" "$LEDGER/failed_deploy_record.json"
    python3 "$HERE/release.py" rollback --env production --record "$LEDGER/failed_deploy_record.json" --ledger-dir "$LEDGER" --execute
    python3 "$HERE/smoke.py" --env production --sha "$SHA" --out "$LEDGER/smoke_after_rollback.json" || true
    exit 1
  fi
else
  echo
  echo "then: python3 $HERE/smoke.py --env production --sha $SHA --out $LEDGER/smoke.json ${CANARY[*]}"
  echo "on smoke failure: python3 $HERE/release.py rollback --env production --record $LEDGER/deploy_record.json --execute"
fi
