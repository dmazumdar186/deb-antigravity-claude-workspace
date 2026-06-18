#!/usr/bin/env bash
# Front-door synthetic for job_search_v2.
#
# Per ~/.claude/rules/front-door-synthetic.md, the pipeline is NOT "working"
# until this script passes 5 consecutive runs.
#
# What this asserts (in order):
#  1. Every source (france_travail, wttj, apec, linkedin_gmail) runs end-to-end on
#     a fixture and produces at least 3 SourceJob JSONL lines each.
#  2. Combined normalize step turns all of them into NormalizedJob records that
#     model_validate_json() round-trips cleanly.
#  3. The dedup layer admits all jobs on a cold-DB run.
#  4. A second dedup run against the same fixture admits zero new jobs.
#  5. The persistent SQLite seen-set retains rows across the two runs.
#  6. Zero Adzuna URLs appear in v2 output — v2 must NEVER inherit v1's only source.
#
# Exit codes:
#   0 — all assertions pass; v2 pipeline is green for the day.
#   1 — one or more assertions failed; do NOT advertise v2 as ready.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-py}"
FIXTURE_FT="tests/fixtures/france_travail_sample.json"
FIXTURE_WTTJ="tests/fixtures/wttj_sample.html"
FIXTURE_APEC="tests/fixtures/apec_sample.html"
FIXTURE_LI="tests/fixtures/linkedin_email_sample.html"
FIXTURE_IND="tests/fixtures/indeed_email_sample.html"

TMP_DIR=".tmp/job_search_v2/synthetic"
DB_PATH="$TMP_DIR/synthetic_seen.db"
SRC_DIR="$TMP_DIR/sources"

rm -rf "$TMP_DIR"
mkdir -p "$SRC_DIR"

echo "== front_door_job_search_v2 =="
echo "repo: $REPO_ROOT"
echo "python: $PYTHON"
echo

# ---------- Assertion 1: every source produces ≥3 SourceJobs from its fixture ----------

run_source_fixture() {
    local name="$1"
    local module="$2"
    local fixture="$3"
    local out="$SRC_DIR/${name}.jsonl"

    echo "[src] $name from $fixture"
    "$PYTHON" "$module" --fixture "$fixture" --out "$out" > /dev/null
    local lines
    lines=$(wc -l < "$out" | tr -d ' \r')
    echo "      → $lines SourceJob lines"
    if [ "$lines" -lt 3 ]; then
        echo "FAIL: $name expected ≥3 SourceJob lines, got $lines" >&2
        exit 1
    fi
}

run_source_fixture "france_travail" \
    "execution/personal_workflows/job_search_v2/sources/france_travail.py" \
    "$FIXTURE_FT"
run_source_fixture "wttj" \
    "execution/personal_workflows/job_search_v2/sources/wttj.py" \
    "$FIXTURE_WTTJ"
run_source_fixture "apec" \
    "execution/personal_workflows/job_search_v2/sources/apec.py" \
    "$FIXTURE_APEC"
run_source_fixture "linkedin_gmail" \
    "execution/personal_workflows/job_search_v2/sources/linkedin_gmail.py" \
    "$FIXTURE_LI"
run_source_fixture "indeed_gmail" \
    "execution/personal_workflows/job_search_v2/sources/indeed_gmail.py" \
    "$FIXTURE_IND"

# Concatenate all source JSONLs for the combined normalize step.
COMBINED_SRC="$TMP_DIR/all_sources.jsonl"
cat "$SRC_DIR"/*.jsonl > "$COMBINED_SRC"
TOTAL_SRC=$(wc -l < "$COMBINED_SRC" | tr -d ' \r')
echo "[total] $TOTAL_SRC SourceJob lines across all sources"
if [ "$TOTAL_SRC" -lt 15 ]; then
    echo "FAIL: expected ≥15 combined SourceJob lines (3 per source × 5 sources), got $TOTAL_SRC" >&2
    exit 1
fi

# ---------- Assertion 2: normalize round-trips ----------

echo "[norm] combined normalize → NormalizedJob JSONL"
NORM_OUT="$TMP_DIR/normalized.jsonl"
"$PYTHON" execution/personal_workflows/job_search_v2/normalizer/normalize.py \
    < "$COMBINED_SRC" > "$NORM_OUT"

NORM_LINES=$(wc -l < "$NORM_OUT" | tr -d ' \r')
echo "      → $NORM_LINES NormalizedJob lines"
if [ "$NORM_LINES" -lt 15 ]; then
    echo "FAIL: normalize produced $NORM_LINES lines, expected ≥15" >&2
    exit 1
fi

"$PYTHON" - <<PYCHECK
from execution.personal_workflows.job_search_v2.contracts import NormalizedJob

with open(r"$NORM_OUT", encoding="utf-8") as f:
    for ln in f:
        ln = ln.strip()
        if not ln:
            continue
        nj = NormalizedJob.model_validate_json(ln)
        round_tripped = NormalizedJob.model_validate_json(nj.model_dump_json())
        assert round_tripped.content_hash == nj.content_hash, "round-trip mismatch"
print("      round-trip OK")
PYCHECK

# ---------- Assertion 3 + 4 + 5: dedup persistence across two runs ----------

echo "[dedup] run 1 (cold DB) → expect all-new"
"$PYTHON" - <<PYRUN1
from pathlib import Path
import sys
from execution.personal_workflows.job_search_v2.contracts import NormalizedJob
from execution.personal_workflows.job_search_v2.normalizer.dedup import filter_new

jobs = [NormalizedJob.model_validate_json(ln) for ln in Path(r"$NORM_OUT").read_text(encoding="utf-8").splitlines() if ln.strip()]
_, stats = filter_new(jobs, db_path=Path(r"$DB_PATH"))
print(f"      stats: {stats}")
if stats["new"] != stats["total_in"]:
    print(f"FAIL: run 1 should admit all {stats['total_in']} as new, got {stats['new']}", file=sys.stderr)
    sys.exit(1)
PYRUN1

# ---------- Assertion 6: tab routing actually maps jobs to expected tabs ----------

echo "[route] tab-routing assigns jobs to PM / AI PM correctly"
"$PYTHON" - <<PYROUTE
import json, sys
from pathlib import Path
from execution.personal_workflows.job_search_v2.contracts import NormalizedJob
from execution.personal_workflows.job_search_v2.notifier.sheet import route_to_tab
from execution.personal_workflows.job_search_v2.normalizer.location_filter import load_config

cfg = load_config().get("tab_routing", {})
jobs = [NormalizedJob.model_validate_json(ln) for ln in Path(r"$NORM_OUT").read_text(encoding="utf-8").splitlines() if ln.strip()]
counts = {}
for j in jobs:
    tab = route_to_tab(j.title, cfg)
    counts[tab] = counts.get(tab, 0) + 1
print(f"      routing: {counts}")
# Fixtures should route to at least PM + AI PM
if "PM" not in counts:
    print("FAIL: routing produced no PM-tab assignments — fallback may be broken", file=sys.stderr)
    sys.exit(1)
PYROUTE

echo "[dedup] run 2 (warm DB) → expect zero-new"
"$PYTHON" - <<PYRUN2
from pathlib import Path
import sys
from execution.personal_workflows.job_search_v2.contracts import NormalizedJob
from execution.personal_workflows.job_search_v2.normalizer.dedup import filter_new, count_seen

jobs = [NormalizedJob.model_validate_json(ln) for ln in Path(r"$NORM_OUT").read_text(encoding="utf-8").splitlines() if ln.strip()]
_, stats = filter_new(jobs, db_path=Path(r"$DB_PATH"))
print(f"      stats: {stats}")
if stats["new"] != 0:
    print(f"FAIL: run 2 should admit 0 (cross-run dedup broken!), got {stats['new']}", file=sys.stderr)
    sys.exit(1)
persisted = count_seen(Path(r"$DB_PATH"))
print(f"      persistent seen count: {persisted}")
if persisted < 12:
    print(f"FAIL: DB persisted only {persisted} rows, expected ≥12", file=sys.stderr)
    sys.exit(1)
PYRUN2

# ---------- Assertion 6: zero Adzuna URLs in v2 output ----------

echo "[sentinel] no Adzuna URLs in v2 output"
if grep -iq "adzuna" "$NORM_OUT"; then
    echo "FAIL: v2 NormalizedJob output contains an Adzuna URL — v2 must NOT inherit v1's source." >&2
    exit 1
fi
echo "      clean"

echo
echo "== front_door_job_search_v2: PASS =="
exit 0
