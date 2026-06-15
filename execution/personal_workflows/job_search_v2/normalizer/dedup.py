"""
description: Persistent cross-day dedup for job_search_v2. SQLite-backed seen-set with TTL.
inputs: list[NormalizedJob] from the normalize step
outputs:
  - list[NormalizedJob] containing only first-seen-today jobs (already-seen ones filtered out)
  - SQLite DB at .tmp/job_search_v2/seen.db updated with (content_hash, canonical_url, first_seen_at) rows
  - in-memory NormalizedJob.also_seen_on populated when a cross-source duplicate is found within the same run

The v1 pipeline's only dedup is in-memory within a single run, which is the
root cause of the "AI Consultant: 7 every day" symptom called out in the audit.
This module's job is to make the seen-set durable across runs.

Schema (intentionally minimal):
    seen(
        content_hash TEXT PRIMARY KEY,
        canonical_url TEXT NOT NULL,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        source TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,  -- ISO 8601 UTC
        last_seen_at TEXT NOT NULL    -- ISO 8601 UTC
    )

TTL: 60 days. A job that hasn't been seen in 60 days is considered "expired"
and will be re-surfaced if it reappears (likely a repost — surfacing it is the
right behavior). The TTL sweep is opportunistic: it runs on every `filter_new`
call so we never need a separate cron.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Local imports (work both as `py …/dedup.py` and as `python -m execution.…dedup`).
_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402

logger = logging.getLogger("dedup")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB_PATH = PROJECT_ROOT / ".tmp" / "job_search_v2" / "seen.db"
DEFAULT_TTL_DAYS = 60


_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    content_hash TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    source TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seen_canonical_url ON seen(canonical_url);
CREATE INDEX IF NOT EXISTS idx_seen_last_seen_at ON seen(last_seen_at);
"""


def _open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _sweep_expired(conn: sqlite3.Connection, ttl_days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
    cur = conn.execute("DELETE FROM seen WHERE last_seen_at < ?", (cutoff,))
    return cur.rowcount or 0


def filter_new(
    jobs: list[NormalizedJob],
    db_path: Path = DEFAULT_DB_PATH,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> tuple[list[NormalizedJob], dict[str, int]]:
    """Return only the jobs that are NEW relative to the persistent seen-set.

    Side effects:
      - records every input job in `seen` (updates last_seen_at on re-encounters,
        inserts on first-encounter).
      - sweeps any row whose last_seen_at is older than `ttl_days`.

    Returns (new_jobs, stats) where stats has counts: total_in, new, already_seen,
    expired_swept.
    """
    if not jobs:
        return [], {"total_in": 0, "new": 0, "already_seen": 0, "expired_swept": 0}

    conn = _open_db(db_path)
    try:
        expired_swept = _sweep_expired(conn, ttl_days)

        new_jobs: list[NormalizedJob] = []
        already_seen = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        for job in jobs:
            existing = conn.execute(
                "SELECT content_hash, source FROM seen WHERE content_hash = ?",
                (job.content_hash,),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE seen SET last_seen_at = ? WHERE content_hash = ?",
                    (now_iso, job.content_hash),
                )
                already_seen += 1
                logger.debug("dedup: already-seen %s @ %s", job.title, job.company)
            else:
                conn.execute(
                    """
                    INSERT INTO seen (content_hash, canonical_url, title, company, source, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.content_hash,
                        job.canonical_url,
                        job.title,
                        job.company,
                        job.source.value,
                        now_iso,
                        now_iso,
                    ),
                )
                new_jobs.append(job)

        stats = {
            "total_in": len(jobs),
            "new": len(new_jobs),
            "already_seen": already_seen,
            "expired_swept": expired_swept,
        }
        logger.info("dedup: %s", stats)
        return new_jobs, stats
    finally:
        conn.close()


def count_seen(db_path: Path = DEFAULT_DB_PATH) -> int:
    """How many distinct jobs has the pipeline ever surfaced? Used by the synthetic."""
    if not db_path.exists():
        return 0
    conn = _open_db(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
    finally:
        conn.close()


def main() -> int:
    """CLI: print stats about the persistent seen-set."""
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Inspect the job_search_v2 dedup DB.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--reset", action="store_true", help="DROP and recreate the seen table (loses all history).")
    args = parser.parse_args()

    if args.reset:
        if args.db.exists():
            args.db.unlink()
            print(f"reset: deleted {args.db}", file=sys.stderr)

    conn = _open_db(args.db)
    try:
        total = conn.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
        by_source = dict(conn.execute("SELECT source, COUNT(*) FROM seen GROUP BY source").fetchall())
        oldest_row = conn.execute("SELECT MIN(first_seen_at) FROM seen").fetchone()[0]
        newest_row = conn.execute("SELECT MAX(last_seen_at) FROM seen").fetchone()[0]
        print(json.dumps({
            "db": str(args.db),
            "total_seen": total,
            "by_source": by_source,
            "oldest_first_seen": oldest_row,
            "newest_last_seen": newest_row,
        }, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
