"""
apply_schema.py
description: Apply schema.sql (Supabase/Postgres) then seed chains + config into the store.
inputs: --store {local,supabase} (default env PRODCRAFT_STORE, fallback local); --root (LocalStore dir);
        env SUPABASE_DB_URL (optional, enables psycopg apply), SUPABASE_URL, SUPABASE_SERVICE_KEY.
outputs: Schema applied to Postgres (or printed for manual paste); seed_chains.json/seed_config.json
         written into the target store; stdout one-line JSON stat.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common.store import (  # noqa: E402
    LocalStore,
    SupabaseStore,
    get_store,
)

SCHEMA_PATH = PKG_ROOT / "db" / "schema.sql"
SEED_CHAINS_PATH = PKG_ROOT / "db" / "seed_chains.json"
SEED_CONFIG_PATH = PKG_ROOT / "db" / "seed_config.json"


def _apply_schema_supabase() -> str:
    """Apply schema.sql via psycopg if SUPABASE_DB_URL + psycopg are available.

    Otherwise print the SQL and instruct the operator to paste it into the
    Supabase SQL editor. Returns a status string for the stat line.
    """
    import os

    db_url = os.environ.get("SUPABASE_DB_URL")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    if not db_url:
        print("SUPABASE_DB_URL not set — paste the SQL below into the Supabase SQL editor:\n")
        print(sql)
        return "printed_for_manual_paste"

    try:
        import psycopg  # type: ignore[import-untyped]
    except ImportError:
        print("psycopg not installed — paste the SQL below into the Supabase SQL editor:\n")
        print(sql)
        return "printed_for_manual_paste"

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    return "applied_via_psycopg"


def _seed_chains(store) -> int:
    patterns = json.loads(SEED_CHAINS_PATH.read_text(encoding="utf-8"))
    if isinstance(store, LocalStore):
        store.load_chains(patterns)
        return len(patterns)
    # SupabaseStore: upsert each chain row via PostgREST.
    count = 0
    for entry in patterns:
        store._request(  # noqa: SLF001 — apply_schema is the one sanctioned direct-call site
            "POST",
            "chains?on_conflict=pattern",
            headers=store._headers(prefer="resolution=merge-duplicates"),  # noqa: SLF001
            json=entry,
        )
        count += 1
    return count


def _seed_config(store) -> int:
    config = json.loads(SEED_CONFIG_PATH.read_text(encoding="utf-8"))
    for key, value in config.items():
        store.set_config(key, value)
    return len(config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply schema.sql and seed chains + config")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--root", default=".tmp/prodcraft_medspa/store", help="LocalStore root dir")
    args = parser.parse_args()

    import os

    store_kind = args.store or os.environ.get("PRODCRAFT_STORE") or "local"

    schema_status = "skipped"
    if store_kind == "supabase":
        schema_status = _apply_schema_supabase()

    if store_kind == "supabase":
        store = SupabaseStore()
    else:
        store = get_store(kind="local", root=args.root)

    chains_seeded = _seed_chains(store)
    config_seeded = _seed_config(store)

    stat = {
        "script": "apply_schema",
        "in": 0,
        "out": chains_seeded + config_seeded,
        "dropped": {},
        "store": store_kind,
        "schema_status": schema_status,
        "chains_seeded": chains_seeded,
        "config_keys_seeded": config_seeded,
    }
    print(json.dumps(stat))


if __name__ == "__main__":
    main()
