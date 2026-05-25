"""
job_tracker_db.py
description: SQLite persistence layer for the French PM/PO Job Tracker. Manages companies, jobs, contacts, and notification logs with upsert semantics and time-windowed queries.
inputs: db_path (Path or str) passed to init_db(); structured dicts passed to each upsert function.
outputs: sqlite3.Connection (from init_db); row ids and boolean flags from upsert functions; list[dict] from query functions.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv; load_dotenv()

from execution.personal_workflows._jt_utils import now_iso  # noqa: E402


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY,
  siren TEXT UNIQUE,
  name TEXT NOT NULL,
  name_normalized TEXT NOT NULL,
  naf_code TEXT,
  website TEXT,
  is_digital_sector INTEGER,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_companies_norm ON companies(name_normalized);
CREATE INDEX IF NOT EXISTS idx_companies_siren ON companies(siren);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  job_hash TEXT UNIQUE NOT NULL,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  title TEXT NOT NULL,
  title_normalized TEXT NOT NULL,
  location TEXT,
  language TEXT,
  board TEXT NOT NULL,
  source_url TEXT NOT NULL,
  description_snippet TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS idx_jobs_window ON jobs(first_seen_at, status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  full_name TEXT NOT NULL,
  title TEXT,
  seniority TEXT,
  linkedin_url TEXT,
  source TEXT,
  fetched_at TEXT NOT NULL,
  UNIQUE(company_id, linkedin_url)
);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);

CREATE TABLE IF NOT EXISTS notifications_log (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  sent_at TEXT NOT NULL,
  recipient TEXT NOT NULL,
  job_ids_json TEXT NOT NULL,
  status TEXT NOT NULL,
  error_message TEXT
);
"""


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def init_db(db_path: Path | str) -> sqlite3.Connection:
    """Open (or create) the SQLite database at *db_path*, apply schema DDL, and return the connection.

    Connection settings:
    - detect_types=sqlite3.PARSE_DECLTYPES for transparent type conversion.
    - isolation_level=None (autocommit mode) — each statement commits immediately.
    - PRAGMA foreign_keys = ON enforced on every new connection.
    - Row factory set to sqlite3.Row so queries return dict-like rows.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(db_path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        isolation_level=None,  # autocommit
    )
    conn.row_factory = sqlite3.Row

    # Apply full DDL (CREATE IF NOT EXISTS statements are idempotent)
    conn.executescript(_DDL)

    return conn


# ---------------------------------------------------------------------------
# Company upsert
# ---------------------------------------------------------------------------

def upsert_company(
    conn: sqlite3.Connection,
    *,
    name: str,
    name_normalized: str,
    siren: str | None = None,
    naf_code: str | None = None,
    website: str | None = None,
    is_digital_sector: int | None = None,
) -> int:
    """Insert or update a company row; returns company_id.

    Match logic (in order):
    1. If siren is provided and a row with that siren exists → update and return its id.
    2. Else if a row with name_normalized exists → update and return its id.
    3. Else insert a new row.

    On update: refreshes last_seen_at and fills in any previously-null fields
    (naf_code, website, is_digital_sector) if the caller now supplies them.
    """
    ts = now_iso()
    existing_id: int | None = None

    # Try siren match first
    if siren:
        row = conn.execute("SELECT id FROM companies WHERE siren = ?", (siren,)).fetchone()
        if row:
            existing_id = row["id"]

    # Fall back to name_normalized match
    if existing_id is None:
        row = conn.execute(
            "SELECT id FROM companies WHERE name_normalized = ?", (name_normalized,)
        ).fetchone()
        if row:
            existing_id = row["id"]

    if existing_id is not None:
        # Update last_seen_at; fill nulls with newly known data
        conn.execute(
            """
            UPDATE companies SET
              last_seen_at = ?,
              siren = COALESCE(siren, ?),
              naf_code = COALESCE(naf_code, ?),
              website = COALESCE(website, ?),
              is_digital_sector = COALESCE(is_digital_sector, ?)
            WHERE id = ?
            """,
            (ts, siren, naf_code, website, is_digital_sector, existing_id),
        )
        return existing_id

    # Insert new row
    cursor = conn.execute(
        """
        INSERT INTO companies (siren, name, name_normalized, naf_code, website, is_digital_sector, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (siren, name, name_normalized, naf_code, website, is_digital_sector, ts, ts),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Job upsert
# ---------------------------------------------------------------------------

def upsert_job(
    conn: sqlite3.Connection,
    *,
    job_hash: str,
    company_id: int,
    title: str,
    title_normalized: str,
    location: str | None,
    language: str | None,
    board: str,
    source_url: str,
    description_snippet: str,
) -> tuple[int, bool]:
    """Insert or update a job row; returns (job_id, is_new).

    If job_hash already exists: updates last_seen_at only, returns (existing_id, False).
    Else: inserts with status='active', returns (new_id, True).
    """
    ts = now_iso()

    row = conn.execute("SELECT id FROM jobs WHERE job_hash = ?", (job_hash,)).fetchone()
    if row:
        conn.execute("UPDATE jobs SET last_seen_at = ? WHERE id = ?", (ts, row["id"]))
        return (row["id"], False)

    cursor = conn.execute(
        """
        INSERT INTO jobs
          (job_hash, company_id, title, title_normalized, location, language,
           board, source_url, description_snippet, first_seen_at, last_seen_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """,
        (
            job_hash, company_id, title, title_normalized, location, language,
            board, source_url, description_snippet, ts, ts,
        ),
    )
    return (cursor.lastrowid, True)


# ---------------------------------------------------------------------------
# Contact upsert
# ---------------------------------------------------------------------------

def upsert_contact(
    conn: sqlite3.Connection,
    *,
    company_id: int,
    full_name: str,
    title: str | None,
    seniority: str | None,
    linkedin_url: str | None,
    source: str,
) -> int:
    """Insert or update a contact row (UNIQUE on company_id + linkedin_url); returns contact_id."""
    ts = now_iso()

    # Try to find existing by (company_id, linkedin_url)
    if linkedin_url:
        row = conn.execute(
            "SELECT id FROM contacts WHERE company_id = ? AND linkedin_url = ?",
            (company_id, linkedin_url),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE contacts SET full_name=?, title=?, seniority=?, source=?, fetched_at=?
                WHERE id=?
                """,
                (full_name, title, seniority, source, ts, row["id"]),
            )
            return row["id"]

    cursor = conn.execute(
        """
        INSERT INTO contacts (company_id, full_name, title, seniority, linkedin_url, source, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (company_id, full_name, title, seniority, linkedin_url, source, ts),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Status management
# ---------------------------------------------------------------------------

def mark_expired(conn: sqlite3.Connection, window_days: int = 7) -> int:
    """Mark active jobs not seen within window_days as 'expired'. Returns affected row count."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    cursor = conn.execute(
        """
        UPDATE jobs SET status = 'expired'
        WHERE status = 'active'
          AND first_seen_at < ?
        """,
        (cutoff,),
    )
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def query_active_within_window(conn: sqlite3.Connection, window_days: int = 7) -> list[dict]:
    """Return active jobs first seen within window_days as a list of dicts."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    rows = conn.execute(
        """
        SELECT j.id, j.job_hash, j.title, j.title_normalized, j.location, j.language,
               j.board, j.source_url, j.description_snippet, j.first_seen_at, j.last_seen_at,
               c.id AS company_id, c.name AS company_name, c.website, c.naf_code, c.is_digital_sector
        FROM jobs j JOIN companies c ON c.id = j.company_id
        WHERE j.status = 'active'
          AND j.first_seen_at >= ?
        ORDER BY c.name, j.first_seen_at DESC
        """,
        (cutoff,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_contacts_for_company(conn: sqlite3.Connection, company_id: int) -> list[dict]:
    """Return up to 10 contacts for company_id, ordered by seniority bucket then fetched_at desc."""
    rows = conn.execute(
        """
        SELECT id, company_id, full_name, title, seniority, linkedin_url, source, fetched_at
        FROM contacts
        WHERE company_id = ?
        ORDER BY
          CASE seniority
            WHEN 'c_suite'   THEN 1
            WHEN 'vp'        THEN 2
            WHEN 'director'  THEN 3
            WHEN 'manager'   THEN 4
            WHEN 'lead'      THEN 5
            ELSE                  6
          END,
          fetched_at DESC
        LIMIT 10
        """,
        (company_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def recent_contact_cache_hit(conn: sqlite3.Connection, company_id: int, days: int) -> bool:
    """Return True if any contact for company_id was fetched within the last *days* days."""
    row = conn.execute(
        """
        SELECT 1 FROM contacts
        WHERE company_id = ?
          AND fetched_at >= datetime('now', ?)
        LIMIT 1
        """,
        (company_id, f"-{days} days"),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Notification logging
# ---------------------------------------------------------------------------

def log_notification(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    recipient: str,
    job_ids: list[int],
    status: str,
    error: str | None = None,
) -> int:
    """Insert a notifications_log row and return its id."""
    ts = now_iso()
    cursor = conn.execute(
        """
        INSERT INTO notifications_log (run_id, sent_at, recipient, job_ids_json, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, ts, recipient, json.dumps(job_ids), status, error),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Job Tracker DB utility. Initializes the SQLite database.",
    )
    parser.add_argument(
        "--init",
        metavar="DB_PATH",
        help="Create (or migrate) the database at DB_PATH and exit.",
    )
    args = parser.parse_args()

    if args.init:
        conn = init_db(args.init)
        conn.close()
        print(f"Database initialized at: {Path(args.init).resolve()}")
    else:
        parser.print_help()
