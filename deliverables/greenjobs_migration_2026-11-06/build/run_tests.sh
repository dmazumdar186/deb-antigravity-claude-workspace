#!/usr/bin/env bash
# GreenJobs migration build pack: every offline test tier in one command.
# No network, no secrets, no .env needed. Exit 0 only if every tier is green.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
PY="${PYTHON:-python3}"
fail=0

echo "== 1/4 D1 schema: applies twice (idempotent), all upserts compile, migrations apply twice"
"$PY" - <<'EOF' || fail=1
import re, sqlite3, sys
base = "deliverables/greenjobs_migration_2026-11-06/build/d1/"
c = sqlite3.connect(":memory:")
schema = open(base + "schema.sql", encoding="utf-8").read()
c.executescript(schema); c.executescript(schema)
ups = re.sub(r"--[^\n]*", "", open(base + "upserts.sql", encoding="utf-8").read())
stmts = [s.strip() for s in ups.split(";") if s.strip()]
for s in stmts:
    n = max([int(x) for x in re.findall(r"\?(\d+)", s)] or [0])
    c.execute("EXPLAIN " + s, [None] * n)
import glob
migs = sorted(glob.glob(base + "migrations/*.sql"))
c.isolation_level = None
for m in migs:
    sql = open(m, encoding="utf-8").read()
    for _ in range(2):  # each migration is idempotent and runs as one transaction, as D1 runs a --file
        c.executescript("BEGIN;\n" + sql + "\nCOMMIT;")
c.executescript(schema)
assert c.execute("PRAGMA foreign_key_check").fetchall() == []
print(f"ok: schema x2, {len(stmts)} upserts, {len(migs)} migration(s) x2 + schema again")
EOF

echo "== 2/4 import validator + apply mode + Gaia feed sync + frozen taxonomy (pytest)"
"$PY" -m pytest -q tests/greenjobs_redesign/test_strategies_import.py tests/greenjobs_redesign/test_strategies_real_headers.py tests/greenjobs_redesign/test_apply_mode_site.py tests/greenjobs_redesign/test_gaia_feed_sync.py tests/greenjobs_redesign/test_platform_taxonomy.py || fail=1

echo "== 3/4 Worker unit tests + BDD features + D1-rendered board: parity with build_site.py and the E2E deploy gate (node --test)"
node --no-warnings --test 'tests/greenjobs_redesign/platform/*.test.mjs' || fail=1
# live figures on the static pages (live.js) and the KPI dashboard's /api/stats refresh (dashboard.js)
(cd deliverables/greenjobs_redesign_2026-09-22/src/js && node --test live.test.js dashboard.test.js) || fail=1

echo "== 4/4 no candidate data staged"
if git ls-files --cached --others --exclude-standard | grep -E '^deliverables/greenjobs_migration_2026-11-06/.*\.csv$'; then
  echo "FAIL: CSV under the migration deliverable"; fail=1
else echo "ok: no CSV in the migration deliverable"; fi

[ "$fail" -eq 0 ] && echo "ALL GREEN" || { echo "RED"; exit 1; }
