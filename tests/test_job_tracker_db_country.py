"""Tests for the country-aware upsert_company collision guard + migration.

Covers:
  - Same name + same country merges to one company_id (existing behaviour, preserved)
  - Same name + different country yields DIFFERENT company_ids
  - SIREN match still takes precedence over name fallback (preserves prior contract)
  - Country defaults to 'FR' when not specified
  - Migration: old DB without `country` column gets the column added with default 'FR'
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.personal_workflows.job_tracker_db import init_db, upsert_company  # noqa: E402


def test_same_name_same_country_merges(tmp_path):
    conn = init_db(tmp_path / "t.db")
    id1 = upsert_company(conn, name="Acme", name_normalized="acme")
    id2 = upsert_company(conn, name="Acme", name_normalized="acme")
    assert id1 == id2


def test_same_name_different_country_splits(tmp_path):
    conn = init_db(tmp_path / "t.db")
    id_fr = upsert_company(conn, name="Siemens", name_normalized="siemens", country="FR")
    id_de = upsert_company(conn, name="Siemens", name_normalized="siemens", country="DE")
    assert id_fr != id_de
    rows = conn.execute("SELECT id, country FROM companies WHERE name_normalized = 'siemens'").fetchall()
    countries = {r["country"] for r in rows}
    assert countries == {"FR", "DE"}


def test_country_defaults_to_fr(tmp_path):
    conn = init_db(tmp_path / "t.db")
    cid = upsert_company(conn, name="Doctolib", name_normalized="doctolib")
    row = conn.execute("SELECT country FROM companies WHERE id = ?", (cid,)).fetchone()
    assert row["country"] == "FR"


def test_siren_match_overrides_country_split(tmp_path):
    """If SIREN matches, that wins over name/country fallback —
    avoids splitting a known FR company on a stray country='XX' upsert."""
    conn = init_db(tmp_path / "t.db")
    id1 = upsert_company(conn, name="Qonto", name_normalized="qonto", siren="819489626", country="FR")
    # Same SIREN, different country tag → should map to the SAME id (SIREN wins)
    id2 = upsert_company(conn, name="Qonto", name_normalized="qonto", siren="819489626", country="XX")
    assert id1 == id2


def test_migration_adds_country_to_old_db(tmp_path):
    """An old DB that was created before the country column existed must gain it."""
    db_path = tmp_path / "old.db"
    # Build the OLD schema by hand (no country column).
    raw = sqlite3.connect(str(db_path))
    raw.executescript("""
        CREATE TABLE companies (
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
    """)
    raw.execute(
        "INSERT INTO companies (name, name_normalized, first_seen_at, last_seen_at) VALUES (?,?,?,?)",
        ("OldRow", "oldrow", "2026-01-01", "2026-01-01"),
    )
    raw.commit()
    raw.close()

    # init_db should run the migration and add the country column with default 'FR'.
    conn = init_db(db_path)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(companies)").fetchall()}
    assert "country" in cols
    # Existing row gets the default value.
    row = conn.execute("SELECT country FROM companies WHERE name = 'OldRow'").fetchone()
    assert row["country"] == "FR"


def test_migration_idempotent(tmp_path):
    """Running init_db twice does not double-add the column or break."""
    db_path = tmp_path / "t.db"
    init_db(db_path)
    # Second open should not raise.
    conn = init_db(db_path)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(companies)").fetchall()]
    # Exactly one country column.
    assert cols.count("country") == 1
