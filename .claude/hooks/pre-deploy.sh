#!/usr/bin/env bash
# pre-deploy.sh
# Runs the project's eval suite before any deploy. Exits non-zero (blocking) if pass
# rate is below EVAL_THRESHOLD. Intended to run under Git Bash on Windows.
#
# Usage: sourced by the Claude Code pre-tool-use hook (see .claude/settings.json)
#        or called directly: bash .claude/hooks/pre-deploy.sh
#
# Configuration:
#   EVAL_THRESHOLD   Minimum pass rate (0-100, integer). Default: 90.
#                    User-facing projects should set 95 in their deploy scripts.
#   EVAL_DIR         Override search path (default: searches tests/, .tmp/cv_test/, eval/)
#
# Note: chmod +x is a no-op on Windows NTFS but is set here for portability if
# this script is ever run from WSL or a Unix host that clones this repo.

set -euo pipefail

THRESHOLD="${EVAL_THRESHOLD:-90}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Ordered list of candidate eval scripts (first found wins)
EVAL_CANDIDATES=(
    "tests/visual_matrix.py"
    "tests/eval.py"
    "tests/test_matrix.py"
    "eval/visual_matrix.py"
    "eval/eval.py"
    "eval/test_matrix.py"
    ".tmp/cv_test/visual_matrix.py"
    ".tmp/cv_test/eval.py"
    "eval/run_eval.sh"
    "tests/run_eval.sh"
)

EVAL_SCRIPT=""
for candidate in "${EVAL_CANDIDATES[@]}"; do
    full_path="${REPO_ROOT}/${candidate}"
    if [[ -f "$full_path" ]]; then
        EVAL_SCRIPT="$full_path"
        echo "[pre-deploy] Found eval script: ${candidate}"
        break
    fi
done

if [[ -z "$EVAL_SCRIPT" ]]; then
    echo "[pre-deploy] No eval script found in standard locations."
    echo "[pre-deploy] Searched: tests/, eval/, .tmp/cv_test/"
    echo "[pre-deploy] Expected filenames: visual_matrix.py, eval.py, test_matrix.py, run_eval.sh"
    echo "[pre-deploy] DEPLOY BLOCKED: no eval suite present."
    echo "[pre-deploy] Write the eval first (see ~/.claude/rules/eval-first.md), then deploy."
    exit 1
fi

# Run the eval script and capture output + exit code
echo "[pre-deploy] Running eval suite (threshold: ${THRESHOLD}%)..."
echo "[pre-deploy] Script: ${EVAL_SCRIPT}"
echo ""

EVAL_OUTPUT=""
EVAL_EXIT=0

if [[ "$EVAL_SCRIPT" == *.py ]]; then
    EVAL_OUTPUT=$(py "$EVAL_SCRIPT" 2>&1) || EVAL_EXIT=$?
elif [[ "$EVAL_SCRIPT" == *.sh ]]; then
    EVAL_OUTPUT=$(bash "$EVAL_SCRIPT" 2>&1) || EVAL_EXIT=$?
fi

echo "$EVAL_OUTPUT"
echo ""

# Try to extract pass rate from output. Eval scripts should print a line like:
#   EVAL_PASS_RATE=87
#   Pass rate: 87%
#   87/100 passed
# If no structured line found, use exit code: 0 = 100%, non-zero = 0%.

PASS_RATE=""

if echo "$EVAL_OUTPUT" | grep -qE "^EVAL_PASS_RATE=[0-9]+"; then
    PASS_RATE=$(echo "$EVAL_OUTPUT" | grep -E "^EVAL_PASS_RATE=[0-9]+" | tail -1 | cut -d= -f2)
elif echo "$EVAL_OUTPUT" | grep -qiE "pass rate:?\s+[0-9]+%?"; then
    PASS_RATE=$(echo "$EVAL_OUTPUT" | grep -iE "pass rate:?\s+[0-9]+%?" | tail -1 | grep -oE "[0-9]+" | tail -1)
elif echo "$EVAL_OUTPUT" | grep -qE "[0-9]+/[0-9]+ passed"; then
    NUMS=$(echo "$EVAL_OUTPUT" | grep -E "[0-9]+/[0-9]+ passed" | tail -1 | grep -oE "[0-9]+/[0-9]+")
    NUMERATOR=$(echo "$NUMS" | cut -d/ -f1)
    DENOMINATOR=$(echo "$NUMS" | cut -d/ -f2)
    if [[ -n "$DENOMINATOR" && "$DENOMINATOR" -gt 0 ]]; then
        PASS_RATE=$(( NUMERATOR * 100 / DENOMINATOR ))
    fi
fi

if [[ -z "$PASS_RATE" ]]; then
    # Fall back to exit code
    if [[ "$EVAL_EXIT" -eq 0 ]]; then
        PASS_RATE=100
        echo "[pre-deploy] No structured pass rate found in output; exit code 0 assumed = 100%."
    else
        PASS_RATE=0
        echo "[pre-deploy] No structured pass rate found in output; non-zero exit assumed = 0%."
    fi
fi

echo "[pre-deploy] Pass rate: ${PASS_RATE}%  |  Threshold: ${THRESHOLD}%"

if [[ "$PASS_RATE" -lt "$THRESHOLD" ]]; then
    echo ""
    echo "==========================================================="
    echo "  DEPLOY BLOCKED: eval pass rate ${PASS_RATE}% < threshold ${THRESHOLD}%"
    echo "==========================================================="
    echo ""
    echo "Fix the failing evals before deploying."
    echo "Exhibit A: CV Optimizer 2026-06-14 — shallow 9/9 PASS masked a 2/8 deep eval."
    echo "See ~/.claude/rules/eval-first.md for the eval-first policy."
    exit 1
fi

echo "[pre-deploy] Eval suite PASSED (${PASS_RATE}% >= ${THRESHOLD}%). Proceeding with deploy."
exit 0
