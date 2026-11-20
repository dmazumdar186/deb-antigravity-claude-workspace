"""GreenJobs quarterly restore drill: restore the latest D1 backup into a scratch database and check row counts.

description: Takes the newest good backup in backup_log.jsonl, downloads it
  from R2, creates a scratch D1 database named greenjobs-drill-<date>,
  executes the dump into it, counts every schema table and compares with the
  counts recorded at backup time (restored >= recorded, because the export
  runs just after the counts), then deletes the scratch database. Only a
  database whose name starts with greenjobs-drill- is ever deleted.
  `--sqlite FILE` restores a local dump into an in-memory SQLite instead (an
  offline check of the same dump; used by the tests). Dry-run by default.
inputs: [--live] [--sqlite DUMP.sql] [--bucket ...] [--state-dir DIR]
  env (live): CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
outputs: <state>/restore_drill_log.jsonl {at, mode, key, ok, detail}; exit 0 pass, 1 fail
Schedule: quarterly (first Monday of Jan/Apr/Jul/Oct), graded by metrics.py B2.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402
import d1_backup as BK  # noqa: E402

SCRATCH_PREFIX = "greenjobs-drill-"


def compare(recorded: dict[str, int], restored: dict[str, int]) -> list[str]:
    problems = [
        f"{t}: restored {restored.get(t)} < recorded {n}"
        for t, n in recorded.items()
        if restored.get(t) is None or restored[t] < n
    ]
    if not recorded:
        problems.append("backup row has no recorded counts")
    return problems


def restore_sqlite(dump: Path, names: list[str]) -> dict[str, int]:
    con = sqlite3.connect(":memory:")
    con.executescript(dump.read_text(encoding="utf-8"))
    return {
        t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in names
    }  # names come from schema.sql, not input


def latest_backup(state: Path) -> dict[str, Any] | None:
    rows = [
        r
        for r in C.read_jsonl(Path(state) / "backup_log.jsonl")
        if r.get("ok") is True and r.get("mode") == "live"
    ]
    return max(rows, key=lambda r: r["at"]) if rows else None


def drill(
    state: Path,
    bucket: str,
    live: bool,
    sqlite_dump: Path | None = None,
    recorded: dict[str, int] | None = None,
    runner: BK.Runner = BK.run_cmd,
) -> dict[str, Any]:
    log = Path(state) / "restore_drill_log.jsonl"
    names = BK.tables()
    if sqlite_dump:
        restored = restore_sqlite(sqlite_dump, names)
        problems = compare(recorded or {}, restored)
        row = {
            "at": C.now_iso(),
            "mode": "sqlite",
            "key": str(sqlite_dump.name),
            "ok": not problems,
            "detail": "; ".join(problems) or f"counts {restored}",
        }
        C.append_jsonl(log, row)
        return row
    b = latest_backup(state)
    if not b:
        row = {
            "at": C.now_iso(),
            "mode": "live" if live else "dry_run",
            "key": None,
            "ok": False,
            "detail": "no good backup to restore",
        }
        C.append_jsonl(log, row)
        return row
    scratch = SCRATCH_PREFIX + C.now_iso()[:10].replace("-", "")
    assert scratch.startswith(SCRATCH_PREFIX)
    with tempfile.TemporaryDirectory() as td:
        dump = Path(td) / "restore.sql"
        steps = [
            BK.WRANGLER
            + [
                "r2",
                "object",
                "get",
                f"{bucket}/{b['key']}",
                "--file",
                str(dump),
                "--remote",
            ],
            BK.WRANGLER + ["d1", "create", scratch],
            BK.WRANGLER
            + ["d1", "execute", scratch, "--remote", "--yes", "--file", str(dump)],
            BK.WRANGLER
            + [
                "d1",
                "execute",
                scratch,
                "--remote",
                "--json",
                "--command",
                BK.count_sql(names),
            ],
        ]
        cleanup = BK.WRANGLER + ["d1", "delete", scratch, "--skip-confirmation"]
        if not live:
            row = {
                "at": C.now_iso(),
                "mode": "dry_run",
                "key": b["key"],
                "ok": None,
                "detail": " && ".join(" ".join(s) for s in steps + [cleanup]),
            }
            C.append_jsonl(log, row)
            return row
        missing = [
            v
            for v in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
            if not os.environ.get(v)
        ]
        out, code, restored = "", 0, {}
        if missing:
            code, out = 1, f"missing env {', '.join(missing)}"
        created = False
        for n, cmd in enumerate(steps if not missing else []):
            code, out = runner(cmd)
            if code != 0:
                break
            created = created or n == 1
            if n == 3:
                restored = BK.parse_counts(out)
        if created:
            runner(cleanup)  # scratch database only (name prefix asserted above)
        problems = (
            [f"step failed: {out[-300:]}"]
            if code != 0
            else compare(b.get("counts") or {}, restored)
        )
        row = {
            "at": C.now_iso(),
            "mode": "live",
            "key": b["key"],
            "ok": not problems,
            "detail": "; ".join(problems) or f"counts {restored}",
        }
        C.append_jsonl(log, row)
        return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true")
    ap.add_argument(
        "--sqlite",
        type=Path,
        help="restore this local dump into in-memory SQLite (offline check)",
    )
    ap.add_argument(
        "--bucket", default=os.environ.get("GJ_BACKUP_BUCKET", "greenjobs-backups")
    )
    ap.add_argument("--state-dir", type=Path, default=C.STATE_DIR)
    a = ap.parse_args(argv)
    r = drill(a.state_dir, a.bucket, a.live, a.sqlite)
    print(f"restore drill {r['mode']}: ok={r['ok']} {r['detail']}")
    return 0 if r["ok"] is not False else 1


if __name__ == "__main__":
    sys.exit(main())
