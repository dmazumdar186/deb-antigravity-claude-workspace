#!/usr/bin/env bash
# GreenJobs migration build pack: every offline test tier in one command.
# No network, no secrets, no .env needed. Exit 0 only if every tier is green.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
PY="${PYTHON:-python3}"
fail=0

echo "== 1/5 D1 schema: applies twice (idempotent), all upserts compile, migrations 0001..000N apply twice on a fresh DB and on the old schema"
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
# statements for the migration-0002/0003 tables (upserts_0003.sql) compile against the migrated schema
parts = re.split(r"^-- name: (\w+)\s*$", open(base + "upserts_0003.sql", encoding="utf-8").read(), flags=re.M)
named = 0
for name, body in zip(parts[1::2], parts[2::2]):
    s = re.sub(r"--[^\n]*", "", body).strip().rstrip(";")
    n = max([int(x) for x in re.findall(r"\?(\d+)", s)] or [0])
    c.execute("EXPLAIN " + s, [None] * n); named += 1
assert named >= 13, named
# the OLD schema (as deployed before 2026-11-20): every migration in order 0001 -> 000N, twice, keeps the data
old = sqlite3.connect(":memory:"); old.isolation_level = None
old.executescript(open("tests/greenjobs_redesign/fixtures/d1/schema_pre_2026-11-20.sql", encoding="utf-8").read())
old.execute("PRAGMA foreign_keys = ON")
old.execute("INSERT INTO employers (id, site, source, source_id, name, name_norm, created_at, updated_at) VALUES ('ie:strat:emp-1','ie','strategies','1','Acme','acme','t','t')")
old.execute("""INSERT INTO jobs (id, site, source, source_id, employer_id, title, location, description, status, created_by, created_at, updated_at)
               VALUES ('ie:strat:1','ie','strategies','1','ie:strat:emp-1','Ecologist','Cork','Lead habitat surveys across Munster.','live','import','t','t')""")
names = [m.rsplit("/", 1)[-1] for m in migs]
assert names == sorted(names) and [n[:4] for n in names] == [f"{i:04d}" for i in range(1, len(names) + 1)], names
for _ in range(2):
    for m in migs:
        old.executescript("BEGIN;\n" + open(m, encoding="utf-8").read() + "\nCOMMIT;")
assert old.execute("SELECT id, title FROM jobs").fetchall() == [("ie:strat:1", "Ecologist")]
assert old.execute("PRAGMA foreign_key_check").fetchall() == []
tables = {r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert {"job_facets", "job_review", "job_links", "employer_accounts", "alert_meta", "newsletter_subscribers"} <= tables, tables
assert "taxonomy_terms" not in tables  # the vocabulary is taxonomy.json only
fcols = [r[1] for r in old.execute("PRAGMA table_info(job_facets)")]
assert {"level", "search_text", "sector_confidence", "sector_method", "source_sectors_json"} <= set(fcols), fcols
print(f"ok: schema x2, {len(stmts)} upserts, {len(migs)} migration(s) x2 + schema again, {named} 0002/0003 statements; "
      f"old schema + {names[0]}..{names[-1]} x2 keeps data")
EOF

echo "== 2/5 import validator + apply mode + Gaia feed sync + classifier / D1 import + frozen taxonomy (pytest)"
"$PY" -m pytest -q tests/greenjobs_redesign/test_strategies_import.py tests/greenjobs_redesign/test_strategies_real_headers.py tests/greenjobs_redesign/test_apply_mode_site.py tests/greenjobs_redesign/test_gaia_feed_sync.py tests/greenjobs_redesign/test_d1_classifier_import.py tests/greenjobs_redesign/test_platform_taxonomy.py || fail=1

echo "== 3/5 Worker unit tests + BDD features + D1-rendered board: parity with build_site.py and the E2E deploy gate (node --test)"
node --no-warnings --test 'tests/greenjobs_redesign/platform/*.test.mjs' || fail=1
# live figures on the static pages (live.js) and the KPI dashboard's /api/stats refresh (dashboard.js)
(cd deliverables/greenjobs_redesign_2026-09-22/src/js && node --test live.test.js dashboard.test.js) || fail=1

echo "== 4/5 ops: redirects, DNS watcher, probe + incidents, metrics + status page, backups, acceptance, reports"
"$PY" -m pytest -q tests/greenjobs_redesign/ops || fail=1
node --no-warnings --test tests/greenjobs_redesign/ops/redirect_rules.test.mjs || fail=1

echo "== 5/5 no candidate data staged"
if git ls-files --cached --others --exclude-standard | grep -E '^deliverables/greenjobs_migration_2026-11-06/.*\.csv$'; then
  echo "FAIL: CSV under the migration deliverable"; fail=1
else echo "ok: no CSV in the migration deliverable"; fi

[ "$fail" -eq 0 ] && echo "ALL GREEN" || { echo "RED"; exit 1; }
