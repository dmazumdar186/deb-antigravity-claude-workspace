"""GreenJobs daily D1 backup to GreenJobs' own R2 bucket (dry-run by default).

description: Exports the live D1 database (`wrangler d1 export --remote`),
  records the row count of every table the schema defines, uploads the dump
  to R2 as d1/<YYYY-MM-DD>.sql and appends a backup_log row (key, bytes,
  sha256, counts). Idempotent: a day that already has a good live backup is
  skipped. Dry-run prints the commands and writes nothing remote. Backup age
  is graded by metrics.py (B1); the quarterly restore drill is
  d1_restore_drill.py (B2). Sold as part of the maintenance service (P8).
inputs: [--live] [--db greenjobs] [--bucket env GJ_BACKUP_BUCKET|greenjobs-backups] [--state-dir DIR] [--date YYYY-MM-DD]
  env (live): CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID (wrangler reads them)
outputs: <state>/backup_log.jsonl, <state>/cost_ledger.jsonl (live), R2 object <bucket>/d1/<date>.sql (live);
  exit 0 ok/skipped, 1 failed (fail loud: a missed backup is a missed deliverable)
Schedule: daily, outside 09:00-17:00 UTC.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # cloud sessions carry env vars only
    pass

SCHEMA = C.MIGRATION / "d1" / "schema.sql"
WRANGLER = ["npx", "--no-install", "--prefix=execution/gtm_client_workflows/greenjobs_redesign/platform_worker", "wrangler"]  # pinned (package-lock.json)
Runner = Callable[[list[str]], tuple[int, str]]


def tables(schema: Path = SCHEMA) -> list[str]:
    """Tables the schema creates (the source of truth; never a copied list)."""
    return re.findall(
        r"CREATE TABLE IF NOT EXISTS (\w+)", schema.read_text(encoding="utf-8")
    )


def count_sql(names: list[str]) -> str:
    return " UNION ALL ".join(
        f"SELECT '{t}' AS t, count(*) AS n FROM {t}" for t in names
    )


def parse_counts(stdout: str) -> dict[str, int]:
    """wrangler d1 execute --json -> [{"results": [{"t":..,"n":..}], ...}]"""
    js = json.loads(stdout[stdout.index("[") :])
    rows = [r for block in js for r in block.get("results", [])]
    return {r["t"]: int(r["n"]) for r in rows}


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    return p.returncode, p.stdout + ("\n" + p.stderr if p.returncode else "")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def already_done(log: Path, key: str) -> bool:
    return any(
        r.get("key") == key and r.get("ok") is True and r.get("mode") == "live"
        for r in C.read_jsonl(log)
    )


def backup(
    state: Path, date: str, db: str, bucket: str, live: bool, runner: Runner = run_cmd
) -> dict[str, Any]:
    log = Path(state) / "backup_log.jsonl"
    key = f"d1/{date}.sql"
    names = tables()
    with tempfile.TemporaryDirectory() as td:
        dump = Path(td) / f"{date}.sql"
        cmds = {
            "export": WRANGLER
            + ["d1", "export", db, "--remote", "--output", str(dump)],
            "counts": WRANGLER
            + [
                "d1",
                "execute",
                db,
                "--remote",
                "--json",
                "--command",
                count_sql(names),
            ],
            "upload": WRANGLER
            + [
                "r2",
                "object",
                "put",
                f"{bucket}/{key}",
                "--file",
                str(dump),
                "--remote",
            ],
        }
        if not live:
            row = {
                "at": C.now_iso(),
                "mode": "dry_run",
                "key": key,
                "ok": None,
                "commands": [" ".join(c) for c in cmds.values()],
                "spend_usd": 0.00,
            }
            C.append_jsonl(log, row)
            return {"status": "dry_run", **row}
        if already_done(log, key):
            return {"status": "skipped", "key": key}
        missing = [
            v
            for v in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
            if not os.environ.get(v)
        ]
        if missing:
            row = {
                "at": C.now_iso(),
                "mode": "live",
                "key": key,
                "ok": False,
                "error": f"missing env {', '.join(missing)}",
            }
            C.append_jsonl(log, row)
            return {"status": "failed", **row}
        # Counts first, export second: rows written between the two make the dump >= counts, which the drill accepts.
        code, out = runner(cmds["counts"])
        counts = parse_counts(out) if code == 0 else {}
        if code == 0:
            code, out = runner(cmds["export"])
        if code == 0 and (not dump.exists() or dump.stat().st_size == 0):
            code, out = 1, "export produced no file"
        if code == 0:
            size, digest = dump.stat().st_size, sha256_file(dump)
            code, out = runner(cmds["upload"])
        ok = code == 0
        row = {
            "at": C.now_iso(),
            "mode": "live",
            "key": key,
            "ok": ok,
            "bucket": bucket,
            "db": db,
        }
        if ok:
            row.update({"bytes": size, "sha256": digest, "counts": counts})
            C.append_jsonl(
                Path(state) / "cost_ledger.jsonl",
                {
                    "at": row["at"],
                    "service": "cloudflare-r2",
                    "units": size,
                    "unit": "bytes",
                    "cost_usd": 0.00,
                    "key": key,
                },
            )
        else:
            row["error"] = out[-500:]
        C.append_jsonl(log, row)
        return {"status": "ok" if ok else "failed", **row}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--db", default="greenjobs")
    ap.add_argument(
        "--bucket", default=os.environ.get("GJ_BACKUP_BUCKET", "greenjobs-backups")
    )
    ap.add_argument("--state-dir", type=Path, default=C.STATE_DIR)
    ap.add_argument("--date", default=C.now_iso()[:10])
    a = ap.parse_args(argv)
    r = backup(a.state_dir, a.date, a.db, a.bucket, a.live)
    print(
        f"backup {r['status']}: {r.get('key')}"
        + (f" ({r.get('error')})" if r.get("error") else "")
    )
    if r["status"] == "dry_run":
        print("\n".join("  " + c for c in r["commands"]))
    return 1 if r["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
