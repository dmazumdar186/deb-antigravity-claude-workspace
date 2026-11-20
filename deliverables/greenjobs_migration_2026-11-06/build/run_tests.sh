#!/usr/bin/env bash
# GreenJobs migration build pack: every offline test tier in one command.
# No network, no secrets, no .env needed. Exit 0 only if every tier is green.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
PY="${PYTHON:-python3}"
fail=0

echo "== 1/5 D1 schema: applies twice (idempotent), all upserts compile, migrations apply twice"
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
# statements for the migration-0003 tables compile against the migrated schema
parts = re.split(r"^-- name: (\w+)\s*$", open(base + "upserts_0003.sql", encoding="utf-8").read(), flags=re.M)
named = 0
for name, body in zip(parts[1::2], parts[2::2]):
    s = re.sub(r"--[^\n]*", "", body).strip().rstrip(";")
    n = max([int(x) for x in re.findall(r"\?(\d+)", s)] or [0])
    c.execute("EXPLAIN " + s, [None] * n); named += 1
assert named >= 14, named
print(f"ok: schema x2, {len(stmts)} upserts, {len(migs)} migration(s) x2 + schema again, {named} 0003 statements")
EOF

echo "== 2/5 import validator + apply mode + Gaia feed sync + classifier / D1 import + export bot (pytest)"
"$PY" -m pytest -q tests/greenjobs_redesign/test_strategies_import.py tests/greenjobs_redesign/test_strategies_real_headers.py tests/greenjobs_redesign/test_apply_mode_site.py tests/greenjobs_redesign/test_gaia_feed_sync.py tests/greenjobs_redesign/test_d1_classifier_import.py tests/greenjobs_redesign/test_strategies_export_bot.py || fail=1

echo "== 3/5 Worker unit tests + BDD features (node --test)"
node --no-warnings --test 'tests/greenjobs_redesign/platform/*.test.mjs' || fail=1

echo "== 4/5 ops: redirects, DNS watcher, probe + incidents, metrics + status page, backups, acceptance, reports"
"$PY" -m pytest -q tests/greenjobs_redesign/ops || fail=1
node --no-warnings --test tests/greenjobs_redesign/ops/redirect_rules.test.mjs || fail=1

echo "== 5/5 no candidate data staged"
if git ls-files --cached --others --exclude-standard | grep -E '^deliverables/greenjobs_migration_2026-11-06/.*\.csv$'; then
  echo "FAIL: CSV under the migration deliverable"; fail=1
else echo "ok: no CSV in the migration deliverable"; fi

[ "$fail" -eq 0 ] && echo "ALL GREEN" || { echo "RED"; exit 1; }
