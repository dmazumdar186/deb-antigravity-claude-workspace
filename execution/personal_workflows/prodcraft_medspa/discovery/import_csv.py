"""
import_csv.py
description: Ingest a manually curated CSV of prospects (e.g. produced by a web-search session
    when no GOOGLE_PLACES_API_KEY is available) into the businesses table, applying the same
    chain/no_name/too_small filters and slug-resolution logic as discovery/places_search.py's
    process_places() (reused by import, not copied). Every row is upserted (kept or dropped).
inputs: --csv PATH (required), --metro X (required), --source NAME (default "manual", recorded as
    discovery_source "csv:<source>"), --mock, --store {local,supabase}, --store-root PATH.
    CSV header row (case-insensitive; extra columns ignored): name (required column — a row's own
    name value may still be blank, which drops as no_name), website, phone, address, city, state,
    rating, review_count, email, owner_name, place_id (optional; derived as
    "import:<sha1(name|address)[:16]>" when missing or blank).
outputs: Upserted `businesses` rows (kept or dropped; every drop carries a drop_reason); when a
    row's `email` column is set, owner_email/email_status="unverified"/email_source="csv" are also
    set. One JSON stat line to stdout:
    {"script":"import_csv","in":n,"unique":n,"kept":n,"dropped":{...}}.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

# execution/personal_workflows/prodcraft_medspa/discovery/import_csv.py -> repo root is 4 parents up.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.discovery.places_search import (  # noqa: E402
    _matches_chain,
    _preload_existing_slugs,
    _resolve_slug,
)
from execution.personal_workflows.prodcraft_medspa.scripts._stage_runner import reject_mock_with_supabase  # noqa: E402

# Deliberately excludes "not_operational": a manually curated list is assumed operational (there
# is no Places `businessStatus` field to distrust here), per the operator's build instructions.
DROP_REASONS = ("chain", "no_name", "too_small")
REQUIRED_HEADER = "name"

# Strict: no whitespace anywhere (rejects "name @ex.com" / trailing-space paste artifacts from a
# spreadsheet), and a TLD of at least 2 letters is required (rejects "owner@localcompany" typos).
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$")


def _valid_email(value: str | None) -> bool:
    return bool(value) and bool(_EMAIL_RE.match(value)) and " " not in value


def _derive_place_id(name: str, address: str) -> str:
    digest = hashlib.sha1(f"{name}|{address}".encode("utf-8")).hexdigest()[:16]
    return f"import:{digest}"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Case-insensitive header read; extra columns ignored. Raises ValueError when the header row
    has no `name` column (nothing else is loaded — a clean, fast failure)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return []
        lowered = [h.strip().lower() for h in header]
        if REQUIRED_HEADER not in lowered:
            raise ValueError(
                f"CSV {path} is missing a required '{REQUIRED_HEADER}' column header "
                f"(found: {', '.join(lowered) or '(empty header row)'})"
            )
        rows: list[dict[str, str]] = []
        for raw_row in reader:
            if not any(cell.strip() for cell in raw_row):
                continue  # skip fully blank lines
            row: dict[str, str] = {}
            for i, key in enumerate(lowered):
                row[key] = raw_row[i].strip() if i < len(raw_row) else ""
            rows.append(row)
        return rows


def _parse_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Filtering / processing
# ---------------------------------------------------------------------------


def process_csv_rows(
    csv_rows: list[dict[str, str]],
    chains: list[str],
    metro: str,
    source: str,
    existing_slugs: dict[str, str],
) -> tuple[list[dict], dict[str, int]]:
    """Dedupe on place_id (first row seen wins within this file), classify, slugify. Mirrors
    discovery.places_search.process_places() for CSV rows: same chain word-bounded match and
    too_small threshold, but no not_operational concept (see DROP_REASONS)."""
    seen: dict[str, dict] = {}
    order: list[str] = []
    dropped_counts = {reason: 0 for reason in DROP_REASONS}

    for row in csv_rows:
        name = (row.get("name") or "").strip()
        address = (row.get("address") or "").strip()
        place_id = (row.get("place_id") or "").strip() or _derive_place_id(name, address)
        if place_id in seen:
            continue  # duplicate place_id within the same file — first row seen wins

        review_count = _parse_int(row.get("review_count"))

        drop_reason: str | None = None
        is_chain = False
        if not name:
            drop_reason = "no_name"
        elif _matches_chain(name, chains):
            drop_reason = "chain"
            is_chain = True
        elif review_count is not None and review_count < 10:
            drop_reason = "too_small"
        # review_count missing entirely is treated as unknown, not too_small — kept.

        if drop_reason:
            dropped_counts[drop_reason] += 1

        city = (row.get("city") or "").strip() or None
        slug = _resolve_slug(name, place_id, city or "", existing_slugs)

        email_raw = (row.get("email") or "").strip() or None
        email = email_raw if _valid_email(email_raw) else None
        owner_name = (row.get("owner_name") or "").strip() or None

        biz_row: dict = {
            "place_id": place_id,
            "name": name,
            "slug": slug,
            "address": address or None,
            "city": city,
            "suburb": city,
            "metro": metro,
            "state": (row.get("state") or "").strip() or None,
            "phone": (row.get("phone") or "").strip() or None,
            "website_url": (row.get("website") or "").strip() or None,
            "final_url": None,
            "rating": _parse_float(row.get("rating")),
            "review_count": review_count,
            "business_status": "OPERATIONAL",  # not_operational never applies to a manual list
            "is_chain": is_chain,
            "drop_reason": drop_reason,
            "discovery_source": f"csv:{source}",
        }
        if owner_name:
            biz_row["owner_name"] = owner_name
        if email:
            biz_row["owner_email"] = email
            biz_row["email_status"] = "unverified"
            biz_row["email_source"] = "csv"

        seen[place_id] = biz_row
        order.append(place_id)

    unique_rows = [seen[pid] for pid in order]
    return unique_rows, dropped_counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a manually curated CSV of prospects into the businesses table."
    )
    parser.add_argument("--csv", dest="csv_path", required=True, help="Path to the CSV file")
    parser.add_argument("--metro", required=True, help="Metro slug, e.g. chicago_north_shore")
    parser.add_argument("--source", default="manual", help="Recorded as discovery_source csv:<source>")
    parser.add_argument("--mock", action="store_true", help="No network either way — kept for CONTRACTS.md symmetry")
    parser.add_argument("--store", choices=["local", "supabase"], default=None, help="Default: PRODCRAFT_STORE env, then local")
    parser.add_argument("--store-root", default=None, help="LocalStore root dir override")
    return parser


def _stat_line(n_in: int, unique: int, kept: int, dropped: dict[str, int]) -> str:
    return json.dumps({"script": "import_csv", "in": n_in, "unique": unique, "kept": kept, "dropped": dropped})


def main(argv: list[str] | None = None) -> None:
    config.bootstrap()
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    store_kind = reject_mock_with_supabase(parser, args)  # --mock implies local; never supabase

    csv_path = Path(args.csv_path)
    try:
        csv_rows = _read_csv_rows(csv_path)
    except (OSError, ValueError) as exc:
        notify.error("discovery.import_csv", str(exc))
        print(f"import_csv failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        store = get_store(kind=store_kind, root=args.store_root)
    except Exception as exc:  # noqa: BLE001 — surfaced via the error channel, not a silent skip
        notify.error("discovery.import_csv", f"store init failed: {exc}")
        print(f"store init failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        chains = store.chains()
    except Exception as exc:  # noqa: BLE001 — an unseeded/empty chains table is not fatal, just log it
        print(f"[import_csv] could not load chains (treated as empty): {exc}", file=sys.stderr)
        chains = []

    existing_slugs = _preload_existing_slugs(store, args.metro)
    unique_rows, dropped = process_csv_rows(csv_rows, chains, args.metro, args.source, existing_slugs)

    for row in unique_rows:
        stored = store.upsert_business(row)
        store.log_event(
            "business", stored["id"], "import", {"source": row.get("discovery_source"), "had_email": bool(row.get("owner_email"))}
        )

    kept = sum(1 for row in unique_rows if row["drop_reason"] is None)
    print(_stat_line(len(csv_rows), len(unique_rows), kept, dropped))


if __name__ == "__main__":
    main()
