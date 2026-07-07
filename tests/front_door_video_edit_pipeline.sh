#!/usr/bin/env bash
# Front-door synthetic for prodcraft_video_edit_pipeline.py (per
# ~/.claude/rules/front-door-synthetic.md). Phase 1b: exercises the schema +
# sensitivity + consent gates in dry-run mode against fixture inputs. Does NOT
# hit live infrastructure yet — that's the LIVE-PROBATIONARY variant scheduled
# for Phase 3 (real Higgsfield / HF-Space run).
#
# Naming note: this is intentionally a FIXTURE-based synthetic per the
# rule's exhibit-B tightening. It is renamed from "front_door_*" to
# "front_door_*" here only because the pipeline is not yet deployed to any
# live surface — the moment Phase 2/3 wires Higgsfield MCP, this script gets
# renamed to `parser_video_edit_pipeline.sh` and a real live-hitting
# `front_door_video_edit_pipeline.sh` replaces it (per the rule).

set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE_ROOT"

PIPELINE="execution/video/prodcraft_video_edit_pipeline.py"
[ -f "$PIPELINE" ] || { echo "FAIL: $PIPELINE missing"; exit 1; }

echo "=== front-door: prodcraft_video_edit_pipeline (Phase 1b, fixture-based) ==="

# 1. --help must print without crashing.
echo "[1/5] --help"
py "$PIPELINE" --help > /dev/null || { echo "FAIL: --help crashed"; exit 1; }
echo "  OK"

# 2. Sensitivity gate must reject Kling for sensitive footage.
echo "[2/5] sensitivity gate rejects kling-3 when sensitive"
set +e
OUT=$(py "$PIPELINE" \
  --source tests/fixtures/video_edit_pipeline/marker_talking_head_3s.mp4 \
  --trigger "at exactly 2.9 seconds" \
  --change "change his outfit to a hoodie with a chain" \
  --model kling-3 \
  --sensitivity sensitive \
  --consent-verified tests/fixtures/video_edit_pipeline/consent_release_alice.md \
  --skip-duration-check \
  --dry-run 2>&1)
CODE=$?
set -e
[ "$CODE" = "2" ] || { echo "FAIL: expected exit 2, got $CODE. output: $OUT"; exit 1; }
echo "$OUT" | grep -q "SENSITIVITY_BLOCKED" || { echo "FAIL: expected SENSITIVITY_BLOCKED in stderr. output: $OUT"; exit 1; }
echo "  OK (blocked with SENSITIVITY_BLOCKED)"

# 3. Missing --sensitivity must fail.
echo "[3/5] missing --sensitivity errors"
set +e
OUT=$(py "$PIPELINE" \
  --source tests/fixtures/video_edit_pipeline/marker_talking_head_3s.mp4 \
  --trigger "at exactly 2.9 seconds" \
  --change "change his outfit to a hoodie" \
  --model gemini-omni \
  --skip-duration-check \
  --dry-run 2>&1)
CODE=$?
set -e
[ "$CODE" = "2" ] || { echo "FAIL: expected exit 2, got $CODE. output: $OUT"; exit 1; }
echo "$OUT" | grep -q "MISSING_SENSITIVITY" || { echo "FAIL: expected MISSING_SENSITIVITY. output: $OUT"; exit 1; }
echo "  OK"

# 4. A positive dry-run triplet must succeed and produce manifest.json.
echo "[4/5] positive dry-run produces manifest.json"
mkdir -p tests/fixtures/video_edit_pipeline
touch tests/fixtures/video_edit_pipeline/marker_talking_head_3s.mp4
TMP_OUT=$(mktemp -d)
py "$PIPELINE" \
  --source tests/fixtures/video_edit_pipeline/marker_talking_head_3s.mp4 \
  --trigger "when the man snaps his fingers at 2.9 seconds" \
  --change "change his outfit to a cool looking hoodie with a chain" \
  --model gemini-omni \
  --sensitivity sensitive \
  --consent-verified tests/fixtures/video_edit_pipeline/consent_release_alice.md \
  --out "$TMP_OUT" \
  --skip-duration-check \
  --dry-run > /dev/null || { echo "FAIL: dry-run crashed"; exit 1; }
[ -f "$TMP_OUT/manifest.json" ] || { echo "FAIL: manifest.json not written to $TMP_OUT"; exit 1; }
# consent_audit block must contain sha256 (proves the audit trail is populated).
grep -q "sha256" "$TMP_OUT/manifest.json" || { echo "FAIL: manifest missing consent_audit.sha256"; exit 1; }
rm -rf "$TMP_OUT"
echo "  OK (manifest written + consent audited)"

# 5. The full acceptance corpus in --dry-run.
echo "[5/5] acceptance corpus --dry-run"
py tests/acceptance_video_edit_pipeline.py --dry-run > /tmp/acceptance_v2v.out 2>&1 || {
  echo "FAIL: acceptance corpus failed. Output:"
  cat /tmp/acceptance_v2v.out
  exit 1
}
tail -3 /tmp/acceptance_v2v.out
echo "  OK"

echo ""
echo "=== front-door PASS (Phase 1b, fixture-based) ==="
echo "Next: Phase 2 = install Higgsfield MCP + read ToS. Then rename this script"
echo "      to parser_*.sh and add a live-hitting front_door_*.sh per rule."
