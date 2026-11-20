#!/usr/bin/env bash
# GreenJobs: roll an environment back to the previous Worker version + Pages deployments recorded in a
# deploy record (deploy_record.json from the ledger artifact). Dry-run by default: prints the exact commands.
#   bash .../deploy/rollback.sh --record path/to/deploy_record.json [--env production|staging]
#   GREENJOBS_RELEASE_TARGET=production bash .../deploy/rollback.sh --record ... --execute
# D1 is never restored automatically (that would discard writes made since the deploy); the D1 Time Travel
# restore command is printed for a human to run when the schema change itself is the cause.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
HERE="execution/gtm_client_workflows/greenjobs_redesign/deploy"
ENV_NAME="production"
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
LEDGER="${GREENJOBS_LEDGER_DIR:-.tmp/greenjobs_release/$ENV_NAME}"
python3 "$HERE/release.py" rollback --env "$ENV_NAME" --ledger-dir "$LEDGER" "${ARGS[@]}"
