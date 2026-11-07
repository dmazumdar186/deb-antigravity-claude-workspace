#!/usr/bin/env bash
# GreenJobs migration build pack: every offline test tier in one command.
# No network, no secrets, no .env needed. Exit 0 only if every tier is green.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
PY="${PYTHON:-python3}"
fail=0

echo "== 1/4 D1 schema: applies twice (idempotent), all upserts compile"
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
print(f"ok: schema x2, {len(stmts)} upserts")
EOF

echo "== 2/4 import validator (pytest)"
"$PY" -m pytest -q tests/greenjobs_redesign/test_strategies_import.py || fail=1

echo "== 3/4 Worker unit tests + BDD features (node --test)"
node --no-warnings --test tests/greenjobs_redesign/platform/ || fail=1

echo "== 4/4 no candidate data staged"
if git ls-files --cached --others --exclude-standard | grep -E '^deliverables/greenjobs_migration_2026-11-06/.*\.csv$'; then
  echo "FAIL: CSV under the migration deliverable"; fail=1
else echo "ok: no CSV in the migration deliverable"; fi

[ "$fail" -eq 0 ] && echo "ALL GREEN" || { echo "RED"; exit 1; }
