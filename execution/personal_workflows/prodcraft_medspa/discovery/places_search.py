"""
places_search.py
description: Tile a metro's target suburbs, run Google Places Text Search (New) per tile/query, dedupe,
  filter chains/closed/too-small/unnamed listings, and upsert every result (kept or dropped) to the store.
inputs: --metro (required), --mock, --store {local,supabase}, --store-root PATH, --queries "a,b,c",
  --max-tiles N, --dry-run; env GOOGLE_PLACES_API_KEY (live only), PRODCRAFT_STORE.
outputs: Upserted `businesses` rows (every found unique place, dropped or kept, carries a drop_reason);
  one JSON stat line to stdout: {"script","metro","tiles","api_calls","found","unique","kept","dropped",
  "est_cost_usd"}.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# execution/personal_workflows/prodcraft_medspa/discovery/places_search.py -> repo root is 4 parents up.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, http, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.slug import slugify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.discovery.tiles import (  # noqa: E402
    Tile,
    load_tiles,
    metro_state,
)

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Exact per CONTRACTS.md / PROJECT_SPEC.md §4 field mask, plus nextPageToken for pagination.
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,"
    "places.regularOpeningHours,places.businessStatus,places.primaryType,nextPageToken"
)

DEFAULT_QUERIES = ["med spa", "medical spa", "laser hair removal", "aesthetic clinic", "botox"]
PAGE_SIZE = 20
MAX_PAGES = 3
RATE_DELAY_S = 0.1  # <=10 req/s
COST_PER_REQUEST_USD = 0.035  # Enterprise SKU (regularOpeningHours + nationalPhoneNumber)
FREE_MONTHLY_REQUESTS = 5000

DROP_REASONS = ("chain", "not_operational", "too_small", "no_name")


# ---------------------------------------------------------------------------
# Live search (Places API New)
# ---------------------------------------------------------------------------


def _search_body(query: str, tile: Tile, page_token: str | None) -> dict:
    body: dict[str, Any] = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": tile.lat, "longitude": tile.lng},
                "radius": tile.radius_m,
            }
        },
        "pageSize": PAGE_SIZE,
    }
    if page_token:
        body["pageToken"] = page_token
    return body


def _post_search(session: Any, api_key: str, query: str, tile: Tile, page_token: str | None = None) -> dict:
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
        "Content-Type": "application/json",
    }
    resp = session.post(PLACES_SEARCH_URL, json=_search_body(query, tile, page_token), headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def search_all_pages(
    session: Any,
    api_key: str,
    query: str,
    tile: Tile,
    max_pages: int = MAX_PAGES,
    sleep_fn=time.sleep,
) -> tuple[list[dict], int]:
    """Paginate one query/tile up to `max_pages` (60-result cap). Returns (places, api_calls)."""
    places: list[dict] = []
    calls = 0
    page_token: str | None = None
    for _ in range(max_pages):
        data = _post_search(session, api_key, query, tile, page_token)
        calls += 1
        places.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        sleep_fn(RATE_DELAY_S)
        if not page_token:
            break
    return places, calls


# ---------------------------------------------------------------------------
# Mock search
# ---------------------------------------------------------------------------


def _load_fixture(metro: str) -> dict | None:
    path = Path(__file__).resolve().parent / "fixtures" / f"places_{metro}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _mock_places_for_tile_query(fixture_data: dict, tile_name: str, query: str) -> list[dict]:
    return fixture_data.get("tiles", {}).get(tile_name, {}).get(query, [])


def _generate_synthetic_mock(metro: str, tile: Tile, n: int = 5) -> list[dict]:
    """Deterministic 5-row synthetic result set for any metro without a dedicated fixture."""
    out = []
    for i in range(1, n + 1):
        out.append(
            {
                "id": f"mock_{metro}_{i:03d}",
                "displayName": {"text": f"{tile.name} Aesthetics {i}"},
                "formattedAddress": f"{100 * i} Main St, {tile.name}, USA",
                "location": {"latitude": tile.lat + 0.001 * i, "longitude": tile.lng + 0.001 * i},
                "nationalPhoneNumber": f"(847) 555-02{i:02d}",
                "websiteUri": f"https://example-medspa-{metro}-{i}.test",
                "rating": 4.5,
                "userRatingCount": 20 + i * 5,
                "businessStatus": "OPERATIONAL",
                "primaryType": "spa",
            }
        )
    return out


# ---------------------------------------------------------------------------
# Filtering / processing
# ---------------------------------------------------------------------------


def _matches_chain(name: str, chains: list[str]) -> bool:
    lowered = name.lower()
    return any(pattern.lower() in lowered for pattern in chains if pattern)


def _parse_city(formatted_address: str) -> str:
    """Best-effort city extraction from 'Street, City, ST ZIP, USA' (or shorter)."""
    parts = [p.strip() for p in (formatted_address or "").split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[-3]
    if len(parts) == 2:
        return parts[0]
    return parts[0] if parts else ""


def _resolve_slug(name: str, place_id: str, city: str, existing_slugs: dict[str, str]) -> str:
    """slugify(name); on collision with a different place_id, append -{city} then -2, -3, ...

    `existing_slugs` maps slug -> place_id and is mutated in place so later rows
    in the same run see prior assignments (and re-runs of the same place_id are
    idempotent: the same place_id reusing its own slug is not a collision).
    """
    base = slugify(name or "business")
    candidate = base
    if candidate in existing_slugs and existing_slugs[candidate] != place_id:
        candidate = f"{base}-{slugify(city)}" if city else f"{base}-2"
        if candidate in existing_slugs and existing_slugs[candidate] != place_id:
            n = 2
            candidate = f"{base}-{n}"
            while candidate in existing_slugs and existing_slugs[candidate] != place_id:
                n += 1
                candidate = f"{base}-{n}"
    existing_slugs[candidate] = place_id
    return candidate


def process_places(
    raw_places: list[tuple[Tile, dict]],
    chains: list[str],
    metro: str,
    state: str | None,
    existing_slugs: dict[str, str],
) -> tuple[list[dict], dict[str, int]]:
    """Dedupe on place id (first tile seen wins), classify, slugify. Returns (unique_rows, dropped_counts)."""
    seen: dict[str, dict] = {}
    order: list[str] = []
    dropped_counts = {reason: 0 for reason in DROP_REASONS}

    for tile, p in raw_places:
        place_id = p.get("id") or ""
        if not place_id or place_id in seen:
            continue  # no id at all can't be tracked; duplicate ids keep the first (earliest tile) occurrence

        name = ((p.get("displayName") or {}).get("text") or "").strip()
        rating_count = p.get("userRatingCount")
        business_status = p.get("businessStatus") or "OPERATIONAL"

        drop_reason: str | None = None
        is_chain = False
        if not name:
            drop_reason = "no_name"
        elif _matches_chain(name, chains):
            drop_reason = "chain"
            is_chain = True
        elif business_status != "OPERATIONAL":
            drop_reason = "not_operational"
        elif rating_count is None or rating_count < 10:
            drop_reason = "too_small"

        if drop_reason:
            dropped_counts[drop_reason] += 1

        address = p.get("formattedAddress") or ""
        city = _parse_city(address)
        location = p.get("location") or {}
        slug = _resolve_slug(name, place_id, city, existing_slugs)

        row = {
            "place_id": place_id,
            "name": name,
            "slug": slug,
            "address": address or None,
            "city": city or None,
            "suburb": tile.name,
            "metro": metro,
            "state": state,
            "lat": location.get("latitude"),
            "lng": location.get("longitude"),
            "phone": p.get("nationalPhoneNumber"),
            "website_url": p.get("websiteUri"),
            "final_url": None,
            "rating": p.get("rating"),
            "review_count": rating_count,
            "primary_type": p.get("primaryType"),
            "business_status": business_status,
            "is_chain": is_chain,
            "drop_reason": drop_reason,
        }
        seen[place_id] = row
        order.append(place_id)

    unique_rows = [seen[pid] for pid in order]
    return unique_rows, dropped_counts


def _preload_existing_slugs(store, metro: str) -> dict[str, str]:
    existing_slugs: dict[str, str] = {}
    try:
        for b in store.find_businesses(metro=metro):
            slug = b.get("slug")
            place_id = b.get("place_id")
            if slug and place_id:
                existing_slugs[slug] = place_id
    except Exception as exc:  # noqa: BLE001 — a fresh/empty store is expected; log, don't fail the run
        print(f"[places_search] could not preload existing slugs (treated as empty): {exc}", file=sys.stderr)
    return existing_slugs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google Places Text Search (New) discovery for one metro.")
    parser.add_argument("--metro", required=True, help="Metro slug, e.g. chicago_north_shore")
    parser.add_argument("--mock", action="store_true", help="Read fixtures/ instead of calling the live API")
    parser.add_argument("--store", choices=["local", "supabase"], default=None, help="Default: PRODCRAFT_STORE env, then local")
    parser.add_argument("--store-root", default=None, help="LocalStore root dir override")
    parser.add_argument("--queries", default=None, help="Comma-separated query list (default: the 5 spec queries)")
    parser.add_argument("--max-tiles", type=int, default=None, help="Limit to the first N tiles")
    parser.add_argument("--dry-run", action="store_true", help="Print the tile/query plan and cost estimate; no network, no writes")
    return parser


def _print_plan(metro: str, tiles: list[Tile], queries: list[str]) -> None:
    print(f"Plan for metro={metro}: {len(tiles)} tiles x {len(queries)} queries")
    for tile in tiles:
        print(f"  tile: {tile.name} ({tile.lat}, {tile.lng}) r={tile.radius_m}m")
    print(f"  queries: {', '.join(queries)}")
    print(
        f"  Note: Google Places grants {FREE_MONTHLY_REQUESTS:,} free Text Search Pro requests/month; "
        f"the estimate below assumes none of that quota remains."
    )


def _stat_line(metro: str, tiles: int, api_calls: int, found: int, unique: int, kept: int, dropped: dict[str, int]) -> str:
    return json.dumps(
        {
            "script": "places_search",
            "metro": metro,
            "tiles": tiles,
            "api_calls": api_calls,
            "found": found,
            "unique": unique,
            "kept": kept,
            "dropped": dropped,
            "est_cost_usd": round(api_calls * COST_PER_REQUEST_USD, 2),
        }
    )


def main(argv: list[str] | None = None) -> None:
    settings = config.bootstrap()
    args = build_arg_parser().parse_args(argv)
    queries = [q.strip() for q in args.queries.split(",") if q.strip()] if args.queries else list(DEFAULT_QUERIES)

    try:
        tiles = load_tiles(args.metro)
    except FileNotFoundError as exc:
        notify.error("discovery", str(exc))
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if args.max_tiles:
        tiles = tiles[: args.max_tiles]
    state = metro_state(args.metro)

    if args.dry_run:
        _print_plan(args.metro, tiles, queries)
        est_calls = len(tiles) * len(queries)
        dropped = {reason: 0 for reason in DROP_REASONS}
        print(_stat_line(args.metro, len(tiles), est_calls, 0, 0, 0, dropped))
        return

    try:
        store = get_store(kind=args.store or settings.store_kind, root=args.store_root)
    except Exception as exc:  # noqa: BLE001 — surfaced via the error channel, not a silent skip
        notify.error("discovery", f"store init failed: {exc}")
        print(f"store init failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        chains = store.chains()
    except Exception as exc:  # noqa: BLE001 — an unseeded/empty chains table is not fatal, just log it
        print(f"[places_search] could not load chains (treated as empty): {exc}", file=sys.stderr)
        chains = []

    api_calls = 0
    found = 0
    raw_places: list[tuple[Tile, dict]] = []

    try:
        if args.mock:
            fixture_data = _load_fixture(args.metro)
            for tile in tiles:
                for query in queries:
                    api_calls += 1
                    if fixture_data is not None:
                        places = _mock_places_for_tile_query(fixture_data, tile.name, query)
                    else:
                        # No dedicated fixture for this metro: deterministic 5 synthetic rows,
                        # attributed to the first tile/first query only so counts stay small and stable.
                        places = (
                            _generate_synthetic_mock(args.metro, tiles[0])
                            if tile is tiles[0] and query == queries[0]
                            else []
                        )
                    found += len(places)
                    for p in places:
                        raw_places.append((tile, p))
        else:
            missing = settings.missing_for_stage("discovery")
            if missing:
                raise RuntimeError(f"missing required env for discovery: {', '.join(missing)} (or pass --mock)")
            session = http.session()
            for tile in tiles:
                for query in queries:
                    places, calls = search_all_pages(session, settings.GOOGLE_PLACES_API_KEY, query, tile)
                    api_calls += calls
                    found += len(places)
                    for p in places:
                        raw_places.append((tile, p))
    except Exception as exc:  # noqa: BLE001 — top-level failure goes to the error channel then exits non-zero
        notify.error("discovery", f"{args.metro}: {exc}")
        print(f"places_search failed for {args.metro}: {exc}", file=sys.stderr)
        sys.exit(1)

    existing_slugs = _preload_existing_slugs(store, args.metro)
    unique_rows, dropped = process_places(raw_places, chains, args.metro, state, existing_slugs)

    for row in unique_rows:
        store.upsert_business(row)

    kept = sum(1 for row in unique_rows if row["drop_reason"] is None)

    print(
        f"Note: {FREE_MONTHLY_REQUESTS:,} free Google Places Text Search Pro requests/month; "
        f"est_cost_usd below assumes none of that quota remains."
    )
    print(_stat_line(args.metro, len(tiles), api_calls, found, len(unique_rows), kept, dropped))


if __name__ == "__main__":
    main()
