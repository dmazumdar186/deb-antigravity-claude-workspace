#!/usr/bin/env bash
# Front-door synthetic — 2026-06-18.
#
# Replaces the original fixture-only test. Runs TWO checks:
#   1. Parser test (cheap, fixture-based, catches per-source HTML/JSON regressions).
#   2. TRUE live synthetic — reads .tmp/job_search_v2/run_log.jsonl and asserts
#      total_fetched >= 5 AND non_zero_sources >= 2 AND latest live run < 25h old.
#
# Both must pass for the script to exit 0. continue-on-error in the workflow YAML
# means a DEGRADED day surfaces in the summary without breaking the cron.
#
# Naming context: this path is preserved as a compat point because the cron's
# workflow YAML still references it (PAT lacks `workflow` scope to update the YAML).
# The parser test is at tests/parser_job_search_v2.sh; the live synthetic is at
# tests/live_front_door_job_search_v2.py. When the YAML can be updated, this file
# should be deleted and the workflow should call both directly.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Cross-platform python launcher.
if [ -z "${PYTHON:-}" ]; then
    if command -v py >/dev/null 2>&1; then
        PYTHON="py"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON="python3"
    else
        PYTHON="python"
    fi
fi

echo "== front_door_job_search_v2 =="
echo "  repo: $REPO_ROOT"
echo "  python: $PYTHON"
echo

# --- Phase 1: parser test (fixture-based) ---
echo "[phase 1/2] parser test (fixture-based, cheap)"
echo "------------------------------------------------"
bash "$(dirname "$0")/parser_job_search_v2.sh"
echo

# --- Phase 2: live pipeline-stats synthetic (reads run_log.jsonl) ---
echo "[phase 2/3] live pipeline-stats synthetic (reads .tmp/job_search_v2/run_log.jsonl)"
echo "-----------------------------------------------------------------"
"$PYTHON" "$(dirname "$0")/live_front_door_job_search_v2.py" \
    --fetch-floor 5 \
    --nonzero-sources-floor 2 \
    --window 1
echo

# --- Phase 3: customer-POV synthetic (opens the actual Google Sheet) ---
# The previous front-door only watched the conveyor belt; this opens the box.
# Asserts per-tab column alignment (Contract holds contracts, Source holds sources),
# Link cells are URLs, Top Matches has data rows, Summary has the dashboard rows.
echo "[phase 3/3] customer-POV synthetic (opens the live Google Sheet)"
echo "-----------------------------------------------------------------"
"$PYTHON" "$(dirname "$0")/customer_pov_job_search_v2.py"
echo

echo "== front_door_job_search_v2: ALL PHASES PASS =="
