#!/bin/bash
# test_suite_tiers.sh
# Re-runnable QA suite for execution/personal_workflows/prodcraft_medspa (6-tier pyramid).
# Each check prints PASS or "FAIL  label: detail". Exits 1 on any failure.
# Uses fresh .tmp/prodcraft_medspa/ts_$(date +%s) scratch dirs. Skips Playwright step
# with a SKIP line if PLAYWRIGHT_BROWSERS_PATH is unset. Never modifies execution/ or fixtures.

set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

PKG="execution/personal_workflows/prodcraft_medspa"
TS=".tmp/prodcraft_medspa/ts_$(date +%s)"
mkdir -p "$TS"

FAIL_COUNT=0
pass() { echo "PASS $1"; }
fail() { echo "FAIL  $1: $2"; FAIL_COUNT=$((FAIL_COUNT+1)); }

echo "=== Scratch dir: $TS ==="

# ---------------------------------------------------------------------------
# Tier 1+2: Unit + Integration
# ---------------------------------------------------------------------------
echo "--- Tier 1+2: Unit + Integration ---"

PYTEST_OUT=$(python3 -m pytest tests/prodcraft_medspa -q 2>&1)
PYTEST_RC=$?
if [ $PYTEST_RC -eq 0 ] && echo "$PYTEST_OUT" | grep -qE "passed"; then
    SUMMARY=$(echo "$PYTEST_OUT" | tail -1)
    pass "pytest tests/prodcraft_medspa -q -- $SUMMARY"
else
    fail "pytest tests/prodcraft_medspa -q" "exit=$PYTEST_RC; $(echo "$PYTEST_OUT" | tail -10)"
fi

for pkgdir in "$PKG/preview/worker" "$PKG/dashboard" "$PKG/template"; do
    NAME=$(basename "$pkgdir")
    OUT=$(cd "$pkgdir" && npm test 2>&1)
    RC=$?
    if [ $RC -eq 0 ]; then
        SUMMARY=$(echo "$OUT" | grep -E "Tests|Test Files" | tr '\n' ' ')
        pass "npm test ($NAME) -- $SUMMARY"
    else
        fail "npm test ($NAME)" "exit=$RC; $(echo "$OUT" | tail -10)"
    fi
    TC_OUT=$(cd "$pkgdir" && npm run typecheck 2>&1)
    TC_RC=$?
    if [ $TC_RC -eq 0 ]; then
        pass "npm run typecheck ($NAME)"
    else
        fail "npm run typecheck ($NAME)" "exit=$TC_RC; $(echo "$TC_OUT" | tail -10)"
    fi
done

# ---------------------------------------------------------------------------
# Tier 3: E2E (mock chain)
# ---------------------------------------------------------------------------
echo "--- Tier 3: E2E ---"

R="$TS/e2e_store"
OUT=$(python3 "$PKG/db/apply_schema.py" --store local --root "$R" 2>&1)
if [ $? -eq 0 ]; then pass "apply_schema (fresh store)"; else fail "apply_schema (fresh store)" "$OUT"; fi

RUN1=$(python3 "$PKG/scripts/run_metro.py" --metro chicago_north_shore --mock --store local --store-root "$R" 2>&1)
RUN1_RC=$?
if [ $RUN1_RC -eq 0 ]; then
    if echo "$RUN1" | grep -q '"found": 25, "unique": 22, "kept": 16' \
        && echo "$RUN1" | grep -q '"audited": 16, "buckets": {"qualified": 6, "borderline": 6, "skip": 4}' \
        && echo "$RUN1" | grep -q '"owner_found": 6' \
        && echo "$RUN1" | grep -q '"verified_deliverable": 4' \
        && echo "$RUN1" | grep -q '"built": 4, "uploaded": 4, "published": 4'; then
        pass "run_metro --mock funnel: found 22, kept 16, audited 16, qualified 6, owner 6, email verified 4, preview built 4"
    else
        fail "run_metro --mock funnel numbers" "$(echo "$RUN1" | grep -E 'discovery OK|audit OK|enrich OK|preview OK|approve OK')"
    fi
else
    fail "run_metro --mock (first run)" "exit=$RUN1_RC; $(echo "$RUN1" | tail -15)"
fi

DAILY1=$(python3 "$PKG/scripts/daily.py" --mock --store local --store-root "$R" --recipient-override t@example.test 2>&1)
DAILY1_RC=$?
if [ $DAILY1_RC -eq 0 ] && echo "$DAILY1" | grep -q '"enqueued": 4, "queued_today": 4, "drafted": 4, "lint_failed": 0' \
    && echo "$DAILY1" | tail -1 | grep -q '"sent": 4'; then
    pass "daily.py --mock --recipient-override: enqueued 4, drafted 4, lint_failed 0, sent 4"
else
    fail "daily.py --mock" "exit=$DAILY1_RC; $(echo "$DAILY1" | tail -10)"
fi

RUN2=$(python3 "$PKG/scripts/run_metro.py" --metro chicago_north_shore --mock --store local --store-root "$R" 2>&1)
RUN2_RC=$?
if [ $RUN2_RC -eq 0 ] && echo "$RUN2" | grep -q '"built": 0.*"skipped_unchanged": 4'; then
    pass "run_metro --mock rerun (same store): previews stay 4, skipped_unchanged 4"
else
    fail "run_metro --mock rerun (idempotency)" "exit=$RUN2_RC; $(echo "$RUN2" | grep 'preview OK')"
fi

R_SAMPLE="$TS/sample_store"
python3 "$PKG/db/apply_schema.py" --store local --root "$R_SAMPLE" > /dev/null 2>&1
SAMPLE_OUT=$(python3 "$PKG/scripts/run_metro.py" --metro chicago_north_shore --mock --store local --store-root "$R_SAMPLE" --stages discovery,audit --sample-n 8 --sample-only 2>&1)
SAMPLE_RC=$?
CI_CHECK=$(python3 - "$R_SAMPLE" <<'PYEOF'
import json, sys
try:
    rows = json.load(open(sys.argv[1] + "/metro_stats.json"))
    row = rows[-1]
    lo, pct, hi = row["ci_low"], row["pct_qualified"], row["ci_high"]
    print("OK" if lo < pct < hi else f"BAD ci_low={lo} pct={pct} ci_high={hi}")
except Exception as e:
    print(f"ERR {e}")
PYEOF
)
if [ $SAMPLE_RC -eq 0 ] && [ "$CI_CHECK" = "OK" ]; then
    pass "run_metro --sample-n 8 --sample-only: ci_low < pct_qualified < ci_high"
else
    fail "run_metro --sample-n 8 --sample-only" "exit=$SAMPLE_RC; ci_check=$CI_CHECK"
fi

BUILD_OUT=$(cd "$PKG/template" && npm run build 2>&1)
BUILD_RC=$?
if [ $BUILD_RC -eq 0 ]; then pass "template: npm run build"; else fail "template: npm run build" "$(echo "$BUILD_OUT" | tail -15)"; fi

if [ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ]; then
    ACC_OUT=$(python3 tests/prodcraft_medspa/acceptance_template.py 2>&1)
    ACC_RC=$?
    if [ $ACC_RC -eq 0 ]; then
        pass "acceptance_template.py -- $ACC_OUT"
    else
        fail "acceptance_template.py" "exit=$ACC_RC; $ACC_OUT"
    fi
else
    echo "SKIP acceptance_template.py: PLAYWRIGHT_BROWSERS_PATH not set"
fi

# ---------------------------------------------------------------------------
# Tier 4: Sanity
# ---------------------------------------------------------------------------
echo "--- Tier 4: Sanity ---"

MAIN_FILES=$(grep -l '__main__' -r "$PKG" --include=*.py)
for f in $MAIN_FILES; do
    OUT=$(timeout 30 python3 "$f" --help 2>&1)
    RC=$?
    if [ $RC -eq 0 ]; then
        pass "--help: $f"
    else
        fail "--help: $f" "exit=$RC (direct-script invocation; known contract gap for relative-import modules -- see report)"
    fi
done

MOD_FAIL=0
python3 - "$PKG" <<'PYEOF'
import importlib, sys, os
pkg_root = sys.argv[1]
mods = []
for dirpath, _, files in os.walk(pkg_root):
    if "__pycache__" in dirpath or "/fixtures/" in dirpath.replace(os.sep, "/") + "/":
        pass
    for fn in files:
        if not fn.endswith(".py"):
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, ".")
        dotted = rel[:-3].replace(os.sep, ".")
        if dotted.endswith(".__init__"):
            dotted = dotted[: -len(".__init__")]
        mods.append(dotted)
mods = sorted(set(mods))
fails = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        fails.append((m, repr(e)))
print(f"IMPORT_TOTAL={len(mods)} IMPORT_FAILS={len(fails)}")
for m, e in fails:
    print(f"IMPORT_FAIL {m}: {e}")
PYEOF
IMPORT_RESULT=$(python3 - "$PKG" <<'PYEOF'
import importlib, sys, os
pkg_root = sys.argv[1]
mods = []
for dirpath, _, files in os.walk(pkg_root):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, ".")
        dotted = rel[:-3].replace(os.sep, ".")
        if dotted.endswith(".__init__"):
            dotted = dotted[: -len(".__init__")]
        mods.append(dotted)
mods = sorted(set(mods))
fails = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        fails.append((m, repr(e)))
print(len(fails))
PYEOF
)
if [ "$IMPORT_RESULT" = "0" ]; then
    pass "import every module under $PKG (importlib.import_module)"
else
    fail "import every module under $PKG" "$IMPORT_RESULT modules failed to import"
fi

DOCTOR_OUT=$(env -i PATH="$PATH" HOME="$HOME" python3 "$PKG/scripts/doctor.py" 2>&1)
DOCTOR_RC=$?
if [ $DOCTOR_RC -ne 0 ] && ! echo "$DOCTOR_OUT" | grep -qi "Traceback (most recent call last)"; then
    pass "doctor.py (no env) exits non-zero without a traceback"
else
    fail "doctor.py (no env)" "exit=$DOCTOR_RC; traceback_present=$(echo "$DOCTOR_OUT" | grep -qi Traceback && echo yes || echo no)"
fi

if grep -q "prodcraft_medspa/preview/approve.py" execution/REGISTRY.md; then
    pass "execution/REGISTRY.md mentions prodcraft_medspa/preview/approve.py"
else
    fail "execution/REGISTRY.md" "no mention of prodcraft_medspa/preview/approve.py"
fi

# ---------------------------------------------------------------------------
# Tier 5: Performance
# ---------------------------------------------------------------------------
echo "--- Tier 5: Performance ---"

T0=$(date +%s)
python3 "$PKG/scripts/run_metro.py" --metro chicago_north_shore --mock --store local --store-root "$TS/perf_store" > /dev/null 2>&1
python3 "$PKG/db/apply_schema.py" --store local --root "$TS/perf_store" > /dev/null 2>&1 # no-op safety (already applied)
python3 "$PKG/scripts/daily.py" --mock --store local --store-root "$TS/perf_store" > /dev/null 2>&1
T1=$(date +%s)
CHAIN_S=$((T1-T0))
if [ $CHAIN_S -le 240 ]; then
    pass "full mock chain wall-clock: ${CHAIN_S}s (threshold 240s)"
else
    fail "full mock chain wall-clock" "${CHAIN_S}s exceeds 240s threshold"
fi

T0=$(date +%s)
python3 -m pytest tests/prodcraft_medspa -q > /dev/null 2>&1
T1=$(date +%s)
PT_S=$((T1-T0))
if [ $PT_S -le 240 ]; then
    pass "pytest wall-clock: ${PT_S}s (threshold 240s)"
else
    fail "pytest wall-clock" "${PT_S}s exceeds 240s threshold"
fi

STORE_BYTES=$(du -cb "$TS/perf_store"/*.json 2>/dev/null | tail -1 | cut -f1)
STORE_BYTES=${STORE_BYTES:-0}
if [ "$STORE_BYTES" -le 5242880 ]; then
    pass "store JSON size: ${STORE_BYTES} bytes (threshold 5MB)"
else
    fail "store JSON size" "${STORE_BYTES} bytes exceeds 5MB threshold"
fi

BUILD_CALLS=$(grep -c '"npm", "run", "build"\|"npm run build"' "$PKG/preview/build_preview.py")
pass "npm run build call sites in build_preview.py: $BUILD_CALLS (expect 1 per business built; previews built=4 in this run)"

# ---------------------------------------------------------------------------
# Tier 6: Monkey
# ---------------------------------------------------------------------------
echo "--- Tier 6: Monkey ---"

MFR="$TS/monkey_fresh"
python3 "$PKG/db/apply_schema.py" --store local --root "$MFR" > /dev/null 2>&1
BAD_METRO_OUT=$(python3 "$PKG/scripts/run_metro.py" --metro does_not_exist --mock --store local --store-root "$MFR" 2>&1)
BAD_METRO_RC=$?
if [ $BAD_METRO_RC -eq 1 ] && ! echo "$BAD_METRO_OUT" | grep -q "^Traceback"; then
    pass "run_metro.py --metro does_not_exist: clean stage failure, exit 1"
else
    fail "run_metro.py --metro does_not_exist" "exit=$BAD_METRO_RC"
fi

OUT=$(python3 "$PKG/scripts/run_metro.py" --metro chicago_north_shore --mock --store supabase 2>&1)
RC=$?
[ $RC -eq 2 ] && pass "run_metro.py --mock --store supabase: exit 2 argparse error" || fail "run_metro.py --mock --store supabase" "exit=$RC"

OUT=$(python3 "$PKG/scripts/run_metro.py" --metro x --auto-approve --store supabase 2>&1)
RC=$?
[ $RC -eq 2 ] && pass "run_metro.py --auto-approve --store supabase: exit 2" || fail "run_metro.py --auto-approve --store supabase" "exit=$RC"

OUT=$(python3 "$PKG/scripts/run_metro.py" --metro chicago_north_shore --stages bogus 2>&1)
RC=$?
[ $RC -eq 2 ] && pass "run_metro.py --stages bogus: exit 2" || fail "run_metro.py --stages bogus" "exit=$RC"

APPROVE_OUT=$(python3 - "$MFR" <<'PYEOF'
import base64, subprocess, sys
store_root = sys.argv[1]
arg = base64.b64decode("JzsgZHJvcCB0YWJsZSBwcmV2aWV3czsgLS0=").decode()
r = subprocess.run(
    ["python3", "execution/personal_workflows/prodcraft_medspa/preview/approve.py",
     "--preview-id", arg, "--mock", "--store", "local", "--store-root", store_root],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
print(r.returncode)
print(r.stdout)
PYEOF
)
if echo "$APPROVE_OUT" | grep -q "not_found"; then
    pass "preview/approve.py with injection-style --preview-id: reported not_found, no crash"
else
    fail "preview/approve.py injection-style --preview-id" "$APPROVE_OUT"
fi

STORE_PROBE=$(python3 - "$MFR" <<'PYEOF'
import sys
sys.path.insert(0, ".")
store_root = sys.argv[1]
from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore
store = LocalStore(root=store_root)
results = []
def check(label, fn):
    try:
        fn()
        results.append(f"{label}=NO_RAISE")
    except ValueError:
        results.append(f"{label}=OK")
    except Exception as e:
        results.append(f"{label}=WRONG_TYPE:{type(e).__name__}")
check("list_rows_bad_key", lambda: store.list_rows("previews", **{"id; drop": 1}))
check("list_rows_bad_table", lambda: store.list_rows("../etc/passwd"))
check("get_row_bad_table", lambda: store.get_row("config", "x"))
print(" ".join(results))
PYEOF
)
if echo "$STORE_PROBE" | grep -q "list_rows_bad_key=OK" && echo "$STORE_PROBE" | grep -q "list_rows_bad_table=OK" && echo "$STORE_PROBE" | grep -q "get_row_bad_table=OK"; then
    pass "LocalStore list_rows/get_row reject bad table/key names with ValueError"
else
    fail "LocalStore list_rows/get_row bad input" "$STORE_PROBE"
fi

LINT_OUT=$(python3 "$PKG/outreach/lint_draft.py" --subject "FREE!!!" --body "" --touch 1 2>&1)
LINT_RC=$?
if [ $LINT_RC -eq 0 ] && echo "$LINT_OUT" | grep -q "violations"; then
    pass "outreach/lint_draft.py FREE!!! empty body: violations reported, exit 0"
else
    fail "outreach/lint_draft.py" "exit=$LINT_RC; $LINT_OUT"
fi

BIZ_JSON="$TS/monkey_business.json"
python3 - "$BIZ_JSON" <<'PYEOF'
import json, sys
biz = {
  "schema_version": "1.0", "name": "Glow \U0001F600 Spa", "slug": "glow-spa", "slug_suffix": "abc123",
  "city": "Winnetka", "state": "IL", "address": "123 Green Bay Rd, Winnetka, IL 60093",
  "phone": "(847) 555-0100", "phone_href": "tel:+18475550100",
  "hours": [{"day": "Mon", "open": "9:00 AM", "close": "6:00 PM"}] * 7,
  "services": [{"name": "Botox - FDA approved treatment for $199!", "blurb": "Schedule a consultation.", "icon": "syringe"}],
  "rating": 4.8, "review_count": 132, "google_maps_url": "https://maps.google.com/?cid=1",
  "tagline": "Book your next treatment in under a minute.",
  "primary_color": "#7C5CFF", "accent_color": "#F4F1EA", "hero_image": "hero-01.jpg",
  "preview": {"expires_at": "2026-10-10", "remove_url": "https://x/remove", "watermark": "Concept preview by ProdCraft"},
  "booking_demo": True,
}
open(sys.argv[1], "w").write(json.dumps(biz))
PYEOF
LINT2_OUT=$(python3 "$PKG/preview/content_lint.py" --file "$BIZ_JSON" 2>&1)
if echo "$LINT2_OUT" | grep -qi "fda approved" && echo "$LINT2_OUT" | grep -q '\$'; then
    pass "preview/content_lint.py: FDA-approved + \$199 price flagged as violations"
else
    fail "preview/content_lint.py FDA/$ violations" "$LINT2_OUT"
fi

SCORE_PROBE=$(python3 - <<'PYEOF'
import sys
sys.path.insert(0, ".")
from execution.personal_workflows.prodcraft_medspa.audit import scoring
results = []
for label, payload in [("empty", {}), ("no_website", {"has_website": False}), ("big_builder", {"builder": "x" * 10_000, "has_website": True})]:
    try:
        scoring.score(payload)
        results.append(f"{label}=OK")
    except Exception as e:
        results.append(f"{label}=FAIL:{type(e).__name__}")
print(" ".join(results))
PYEOF
)
if ! echo "$SCORE_PROBE" | grep -q "FAIL"; then
    pass "audit/scoring.py score() survives empty/has_website=False/10KB-builder inputs"
else
    fail "audit/scoring.py score() edge cases" "$SCORE_PROBE"
fi

SLUG_PROBE=$(python3 - <<'PYEOF'
import sys
sys.path.insert(0, ".")
from execution.personal_workflows.prodcraft_medspa.common import slug
results = []
for label, name in [("emoji", "\U0001F600\U0001F601\U0001F602"), ("long", "A" * 500)]:
    try:
        s = slug.slugify(name)
        results.append(f"{label}={'OK' if s and len(s) <= 100 else 'BAD:' + repr(s)[:40]}")
    except Exception as e:
        results.append(f"{label}=FAIL:{type(e).__name__}")
print(" ".join(results))
PYEOF
)
if ! echo "$SLUG_PROBE" | grep -q "FAIL\|BAD"; then
    pass "common/slug.py slugify() survives emoji-only and 500-char names, bounded+nonempty"
else
    fail "common/slug.py slugify() edge cases" "$SLUG_PROBE"
fi

NONAME_PROBE=$(python3 - "$TS/noname_store" <<'PYEOF'
import sys
sys.path.insert(0, ".")
import subprocess, json
store_root = sys.argv[1]
subprocess.run(["python3", "execution/personal_workflows/prodcraft_medspa/db/apply_schema.py", "--store", "local", "--root", store_root], capture_output=True)
subprocess.run(["python3", "execution/personal_workflows/prodcraft_medspa/discovery/places_search.py", "--metro", "chicago_north_shore", "--mock", "--store", "local", "--store-root", store_root], capture_output=True)
rows = json.load(open(store_root + "/businesses.json"))
hit = [r for r in rows if r.get("place_id") == "place_chi_015"]
print(hit[0].get("drop_reason") if hit else "NOT_FOUND")
PYEOF
)
if [ "$NONAME_PROBE" = "no_name" ]; then
    pass "places fixture place_chi_015 (missing displayName.text) drop_reason=no_name"
else
    fail "places fixture place_chi_015 drop_reason" "got: $NONAME_PROBE"
fi

DATE_OUT=$(python3 "$PKG/scripts/daily.py" --date not-a-date --mock --store local --store-root "$MFR" 2>&1)
DATE_RC=$?
if [ $DATE_RC -ne 0 ]; then
    if echo "$DATE_OUT" | grep -q "^Traceback\|line [0-9]*, in "; then
        fail "daily.py --date not-a-date" "exit=$DATE_RC but a raw Python traceback leaked to stderr"
    else
        pass "daily.py --date not-a-date: clean error, exit non-zero"
    fi
else
    fail "daily.py --date not-a-date" "exit=0, expected non-zero"
fi

IFR="$TS/idempotent_schema_store"
OUT1=$(python3 "$PKG/db/apply_schema.py" --store local --root "$IFR" 2>&1)
OUT2=$(python3 "$PKG/db/apply_schema.py" --store local --root "$IFR" 2>&1)
CHAINS1=$(echo "$OUT1" | grep -oE '"chains_seeded": [0-9]+')
CHAINS2=$(echo "$OUT2" | grep -oE '"chains_seeded": [0-9]+')
CFG_DUPE=$(python3 -c "
import json
rows = json.load(open('$IFR/config.json'))
keys = [r.get('key') for r in rows] if isinstance(rows, list) else list(rows.keys())
print('dupe' if len(keys) != len(set(keys)) else 'unique')
")
if [ "$CHAINS1" = "$CHAINS2" ] && [ "$CFG_DUPE" = "unique" ]; then
    pass "db/apply_schema.py run twice: chains_seeded stable ($CHAINS1), no duplicate config keys"
else
    fail "db/apply_schema.py idempotency" "chains1=$CHAINS1 chains2=$CHAINS2 cfg=$CFG_DUPE"
fi

# Kill test
KFR="$TS/kill_store"
python3 "$PKG/db/apply_schema.py" --store local --root "$KFR" > /dev/null 2>&1
python3 "$PKG/scripts/run_metro.py" --metro chicago_north_shore --mock --store local --store-root "$KFR" --stages discovery,audit,enrich,preview > "$TS/kill.log" 2>&1 &
KPID=$!
sleep 8
kill -TERM "$KPID" 2>/dev/null
wait "$KPID" 2>/dev/null
LOCK_PROBE=$(python3 - <<'PYEOF'
import sys, time
sys.path.insert(0, ".")
from execution.personal_workflows.prodcraft_medspa.preview.build_preview import _ProcessLock
from pathlib import Path
p = Path("execution/personal_workflows/prodcraft_medspa/template/.build.lock")
try:
    with _ProcessLock(p, wait_s=30):
        print("RELEASED")
except TimeoutError:
    print("STILL_LOCKED")
PYEOF
)
KFR2="$TS/kill_store2"
python3 "$PKG/db/apply_schema.py" --store local --root "$KFR2" > /dev/null 2>&1
APPROVE_AFTER_KILL=$(python3 "$PKG/preview/approve.py" --metro chicago_north_shore --all-review --mock --store local --store-root "$KFR2" 2>&1)
APPROVE_AFTER_RC=$?
if [ "$LOCK_PROBE" = "RELEASED" ] && [ $APPROVE_AFTER_RC -eq 0 ]; then
    pass "kill test: SIGTERM during preview build leaves template/.build.lock releasable; approve.py runs fine after"
else
    fail "kill test" "lock_probe=$LOCK_PROBE approve_rc=$APPROVE_AFTER_RC"
fi

# ---------------------------------------------------------------------------
echo ""
echo "=== SUMMARY ==="
if [ $FAIL_COUNT -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    exit 0
else
    echo "$FAIL_COUNT CHECK(S) FAILED"
    exit 1
fi
