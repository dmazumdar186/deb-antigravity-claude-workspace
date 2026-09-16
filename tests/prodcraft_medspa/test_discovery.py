"""
test_discovery.py
description: Tests for discovery/tiles.py, discovery/places_search.py, and discovery/verify_counts.py.
inputs: N/A (pytest); uses the `local_store` fixture from conftest.py and discovery/fixtures/.
outputs: pass/fail via pytest.
"""

from __future__ import annotations

import json

import pytest

from execution.personal_workflows.prodcraft_medspa.discovery import places_search
from execution.personal_workflows.prodcraft_medspa.discovery.tiles import (
    Tile,
    covering_tiles,
    known_metros,
    load_tiles,
    metro_state,
)

ALL_METROS = [
    "chicago_north_shore",
    "minneapolis_st_paul",
    "columbus",
    "detroit",
    "indianapolis",
    "kansas_city",
    "st_louis",
    "cleveland",
    "cincinnati",
    "milwaukee",
]

EXPECTED_DROPPED = {"chain": 2, "not_operational": 1, "too_small": 2, "no_name": 1}
EXPECTED_FOUND = 25
EXPECTED_UNIQUE = 22
EXPECTED_KEPT = 16


# ---------------------------------------------------------------------------
# tiles.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("metro", ALL_METROS)
def test_tile_loading_all_metros(metro):
    tiles = load_tiles(metro)
    assert len(tiles) >= 4
    for tile in tiles:
        assert isinstance(tile, Tile)
        assert tile.name
        # Continental US bounding box (loose), just to catch swapped/garbage coords.
        assert 24.0 <= tile.lat <= 50.0
        assert -125.0 <= tile.lng <= -66.0
        assert tile.radius_m > 0


def test_known_metros_matches_expected_set():
    assert set(known_metros()) == set(ALL_METROS)


def test_load_tiles_unknown_metro_raises():
    with pytest.raises(FileNotFoundError):
        load_tiles("nowhere_metro")


def test_metro_state():
    assert metro_state("chicago_north_shore") == "IL"
    assert metro_state("minneapolis_st_paul") == "MN"
    assert metro_state("nowhere_metro") is None


def test_covering_tiles_helper():
    centers = [("A", 42.0, -87.0), ("B", 42.1, -87.1)]
    tiles = covering_tiles(centers, radius_m=1500)
    assert tiles == [Tile("A", 42.0, -87.0, 1500), Tile("B", 42.1, -87.1, 1500)]


# ---------------------------------------------------------------------------
# places_search.py — field mask, filtering, slug collisions, pagination
# ---------------------------------------------------------------------------


def test_field_mask_exact():
    expected = (
        "places.id,places.displayName,places.formattedAddress,places.location,"
        "places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,"
        "places.regularOpeningHours,places.businessStatus,places.primaryType,nextPageToken"
    )
    assert places_search.FIELD_MASK == expected


def test_matches_chain():
    chains = ["ideal image", "laseraway"]
    assert places_search._matches_chain("Ideal Image Northbrook", chains)
    assert places_search._matches_chain("LaserAway Evanston", chains)
    assert not places_search._matches_chain("Glow Aesthetics", chains)


def test_matches_chain_is_word_bounded_not_substring():
    chains = ["ulta", "ideal image"]
    assert places_search._matches_chain("Ulta Beauty Skokie", chains)
    assert places_search._matches_chain("ULTA", chains)
    assert not places_search._matches_chain("Consultation Skin Clinic", chains)
    assert not places_search._matches_chain("Aesthetic Consultants of Evanston", chains)
    assert not places_search._matches_chain("Multa Beauty", chains)


def test_parse_city():
    assert places_search._parse_city("530 Green Bay Rd, Winnetka, IL 60093, USA") == "Winnetka"
    assert places_search._parse_city("") == ""


def test_process_places_classifies_and_dedupes():
    tile_a = Tile("Winnetka", 42.1061, -87.7392, 3000)
    tile_b = Tile("Northbrook", 42.1275, -87.8289, 3000)
    chains = ["ideal image"]

    p_ok = {"id": "p1", "displayName": {"text": "Glow Aesthetics"}, "formattedAddress": "1 Main St, Winnetka, IL 60093, USA", "location": {"latitude": 1, "longitude": 2}, "userRatingCount": 50, "businessStatus": "OPERATIONAL"}
    p_chain = {"id": "p2", "displayName": {"text": "Ideal Image Northbrook"}, "formattedAddress": "2 Main St, Northbrook, IL 60062, USA", "location": {"latitude": 1, "longitude": 2}, "userRatingCount": 200, "businessStatus": "OPERATIONAL"}
    p_closed = {"id": "p3", "displayName": {"text": "Old Spa"}, "formattedAddress": "3 Main St, Winnetka, IL 60093, USA", "location": {}, "userRatingCount": 40, "businessStatus": "CLOSED_PERMANENTLY"}
    p_small = {"id": "p4", "displayName": {"text": "Tiny Spa"}, "formattedAddress": "4 Main St, Winnetka, IL 60093, USA", "location": {}, "userRatingCount": 3, "businessStatus": "OPERATIONAL"}
    p_noname = {"id": "p5", "displayName": {"text": ""}, "formattedAddress": "5 Main St, Winnetka, IL 60093, USA", "location": {}, "userRatingCount": 40, "businessStatus": "OPERATIONAL"}
    p_dup = dict(p_ok)  # same id "p1" seen again in a second tile -> must not double count

    raw = [(tile_a, p_ok), (tile_a, p_chain), (tile_a, p_closed), (tile_a, p_small), (tile_a, p_noname), (tile_b, p_dup)]
    unique_rows, dropped = places_search.process_places(raw, chains, "chicago_north_shore", "IL", {})

    assert len(unique_rows) == 5  # p1..p5, p_dup collapsed into p1
    by_id = {r["place_id"]: r for r in unique_rows}
    assert by_id["p1"]["drop_reason"] is None
    assert by_id["p1"]["suburb"] == "Winnetka"  # first tile seen wins, not the duplicate's tile
    assert by_id["p2"]["drop_reason"] == "chain"
    assert by_id["p2"]["is_chain"] is True
    assert by_id["p3"]["drop_reason"] == "not_operational"
    assert by_id["p4"]["drop_reason"] == "too_small"
    assert by_id["p5"]["drop_reason"] == "no_name"
    assert dropped == {"chain": 1, "not_operational": 1, "too_small": 1, "no_name": 1}


def test_slug_collision_appends_city_then_number():
    existing: dict[str, str] = {}
    slug1 = places_search._resolve_slug("Glow Aesthetics", "place-A", "Winnetka", existing)
    assert slug1 == "glow-aesthetics"

    # Different place_id, same name -> collision -> city suffix.
    slug2 = places_search._resolve_slug("Glow Aesthetics", "place-B", "Northbrook", existing)
    assert slug2 == "glow-aesthetics-northbrook"
    assert slug2 != slug1

    # Same base name AND same city as slug2's collision target -> falls through to numeric suffix.
    slug3 = places_search._resolve_slug("Glow Aesthetics", "place-C", "Northbrook", existing)
    assert slug3 == "glow-aesthetics-2"

    # Re-processing place-A again must be idempotent: same slug returned, no new suffix.
    slug1_again = places_search._resolve_slug("Glow Aesthetics", "place-A", "Winnetka", existing)
    assert slug1_again == slug1


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    """Returns 2 pages with nextPageToken, then a 3rd with none — exercises the pagination cap."""

    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.calls = 0

    def post(self, url, json=None, headers=None, timeout=None):
        payload = self.pages[self.calls]
        self.calls += 1
        return _FakeResponse(payload)


def test_pagination_three_pages_then_stop():
    tile = Tile("Winnetka", 42.1061, -87.7392, 3000)
    pages = [
        {"places": [{"id": "p1"}], "nextPageToken": "tok1"},
        {"places": [{"id": "p2"}], "nextPageToken": "tok2"},
        {"places": [{"id": "p3"}]},  # no nextPageToken -> stop
    ]
    session = _FakeSession(pages)
    places, calls = places_search.search_all_pages(session, "fake-key", "med spa", tile, sleep_fn=lambda s: None)
    assert calls == 3
    assert session.calls == 3
    assert [p["id"] for p in places] == ["p1", "p2", "p3"]


def test_pagination_capped_at_max_pages_even_with_more_tokens():
    tile = Tile("Winnetka", 42.1061, -87.7392, 3000)
    pages = [
        {"places": [{"id": "p1"}], "nextPageToken": "tok1"},
        {"places": [{"id": "p2"}], "nextPageToken": "tok2"},
        {"places": [{"id": "p3"}], "nextPageToken": "tok3"},  # would keep going, but cap is 3
    ]
    session = _FakeSession(pages)
    places, calls = places_search.search_all_pages(session, "fake-key", "med spa", tile, sleep_fn=lambda s: None)
    assert calls == 3
    assert len(places) == 3


# ---------------------------------------------------------------------------
# End-to-end mock CLI run
# ---------------------------------------------------------------------------


def _seed_chains(store_root):
    """Seed the chain-exclusion list db/apply_schema.py would normally load, so discovery's
    chain filter has something to match against (a fresh test store starts with none)."""
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    seed_path = places_search.__file__
    seed_path = (
        places_search.Path(seed_path).resolve().parents[1] / "db" / "seed_chains.json"
    )
    with open(seed_path, encoding="utf-8") as f:
        patterns = json.load(f)
    LocalStore(root=store_root).load_chains(patterns)


def _run_mock_cli(store_root, capsys, metro="chicago_north_shore", extra_args=None):
    _seed_chains(store_root)
    argv = ["--metro", metro, "--mock", "--store", "local", "--store-root", str(store_root)]
    if extra_args:
        argv += extra_args
    places_search.main(argv)
    out = capsys.readouterr().out
    stat_line = out.strip().splitlines()[-1]
    return json.loads(stat_line)


def test_mock_end_to_end_exact_counts(tmp_path, capsys):
    store_root = tmp_path / "store"
    stat = _run_mock_cli(store_root, capsys)

    assert stat["script"] == "places_search"
    assert stat["metro"] == "chicago_north_shore"
    assert stat["found"] == EXPECTED_FOUND
    assert stat["unique"] == EXPECTED_UNIQUE
    assert stat["kept"] == EXPECTED_KEPT
    assert stat["dropped"] == EXPECTED_DROPPED
    assert stat["unique"] == stat["kept"] + sum(stat["dropped"].values())
    assert stat["est_cost_usd"] == round(stat["api_calls"] * places_search.COST_PER_REQUEST_USD, 2)


def test_mock_dedupe_across_tiles(tmp_path, capsys):
    store_root = tmp_path / "store"
    _run_mock_cli(store_root, capsys)

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store = LocalStore(root=store_root)
    businesses = store.find_businesses(metro="chicago_north_shore")
    place_ids = [b["place_id"] for b in businesses]
    assert len(place_ids) == len(set(place_ids))  # no duplicate rows written

    dup_biz = next(b for b in businesses if b["place_id"] == "place_chi_008")
    assert dup_biz["suburb"] == "Winnetka"  # first tile it was found in, not Northbrook


def test_mock_chain_rows_kept_and_flagged(tmp_path, capsys):
    store_root = tmp_path / "store"
    _run_mock_cli(store_root, capsys)

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store = LocalStore(root=store_root)
    businesses = store.find_businesses(metro="chicago_north_shore")
    chain_rows = [b for b in businesses if b["place_id"] in ("place_chi_011", "place_chi_016")]
    assert len(chain_rows) == 2
    for row in chain_rows:
        assert row["is_chain"] is True
        assert row["drop_reason"] == "chain"


def test_mock_idempotent_rerun(tmp_path, capsys):
    store_root = tmp_path / "store"
    stat1 = _run_mock_cli(store_root, capsys)
    stat2 = _run_mock_cli(store_root, capsys)

    assert stat1["found"] == stat2["found"]
    assert stat1["unique"] == stat2["unique"]
    assert stat1["kept"] == stat2["kept"]
    assert stat1["dropped"] == stat2["dropped"]

    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store = LocalStore(root=store_root)
    businesses = store.find_businesses(metro="chicago_north_shore")
    assert len(businesses) == EXPECTED_UNIQUE  # no duplicate rows after a second run
    place_ids = [b["place_id"] for b in businesses]
    assert len(place_ids) == len(set(place_ids))


def test_dry_run_makes_no_writes(tmp_path, capsys):
    store_root = tmp_path / "store"
    argv = ["--metro", "chicago_north_shore", "--dry-run", "--store-root", str(store_root)]
    places_search.main(argv)

    out = capsys.readouterr().out
    stat_line = out.strip().splitlines()[-1]
    stat = json.loads(stat_line)
    assert stat["found"] == 0
    assert stat["unique"] == 0
    assert stat["kept"] == 0
    assert not store_root.exists()  # dry-run touches no store at all


def test_mock_other_metro_generates_synthetic_rows(tmp_path, capsys):
    store_root = tmp_path / "store"
    stat = _run_mock_cli(store_root, capsys, metro="columbus")
    assert stat["found"] == 5
    assert stat["unique"] == 5


# ---------------------------------------------------------------------------
# verify_counts.py
# ---------------------------------------------------------------------------


def test_verify_counts_flags_low_suburbs(tmp_path, capsys):
    from execution.personal_workflows.prodcraft_medspa.discovery import verify_counts

    store_root = tmp_path / "store"
    _run_mock_cli(store_root, capsys)
    capsys.readouterr()  # clear places_search output

    argv = ["--metro", "chicago_north_shore", "--store-root", str(store_root)]
    verify_counts.main(argv)
    out = capsys.readouterr().out
    stat_line = out.strip().splitlines()[-1]
    stat = json.loads(stat_line)

    assert stat["script"] == "verify_counts"
    assert stat["suburbs"] >= 4
    assert stat["flagged"] == 2  # Northbrook (5/20) and Highland Park (0/5) per the manual fixture


# ---------------------------------------------------------------------------
# import_csv.py
# ---------------------------------------------------------------------------


def _write_csv(path, header, rows):
    import csv as _csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def test_import_csv_missing_review_count_kept():
    from execution.personal_workflows.prodcraft_medspa.discovery import import_csv

    rows = [{"name": "Unrated Spa", "address": "1 Main St", "review_count": ""}]
    unique, dropped = import_csv.process_csv_rows(rows, [], "chicago_north_shore", "manual", {})
    assert unique[0]["drop_reason"] is None
    assert unique[0]["review_count"] is None
    assert dropped == {"chain": 0, "no_name": 0, "too_small": 0}


def test_import_csv_keeps_and_drops_correctly():
    from execution.personal_workflows.prodcraft_medspa.discovery import import_csv

    chains = ["ulta"]
    rows = [
        {"name": "Glow Aesthetics", "address": "1 Main St", "review_count": "50"},
        {"name": "Ulta Beauty", "address": "2 Main St", "review_count": "500"},
        {"name": "Tiny Spa", "address": "3 Main St", "review_count": "3"},
        {"name": "", "address": "4 Main St", "review_count": "40"},
    ]
    unique, dropped = import_csv.process_csv_rows(rows, chains, "chicago_north_shore", "manual", {})
    assert len(unique) == 4
    by_name = {r["name"]: r for r in unique}
    assert by_name["Glow Aesthetics"]["drop_reason"] is None
    assert by_name["Ulta Beauty"]["drop_reason"] == "chain"
    assert by_name["Ulta Beauty"]["is_chain"] is True
    assert by_name["Tiny Spa"]["drop_reason"] == "too_small"
    assert unique[3]["drop_reason"] == "no_name"  # the blank-name row (no "name" key to look up by)
    assert dropped == {"chain": 1, "no_name": 1, "too_small": 1}


def test_import_csv_derives_stable_place_id_from_name_and_address():
    from execution.personal_workflows.prodcraft_medspa.discovery import import_csv

    id1 = import_csv._derive_place_id("Glow Aesthetics", "1 Main St")
    id2 = import_csv._derive_place_id("Glow Aesthetics", "1 Main St")
    id3 = import_csv._derive_place_id("Glow Aesthetics", "2 Main St")
    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("import:")


def test_import_csv_sets_unverified_email_fields_when_email_given():
    from execution.personal_workflows.prodcraft_medspa.discovery import import_csv

    rows = [
        {"name": "Glow Aesthetics", "address": "1 Main St", "email": "owner@example-medspa-import.test"},
        {"name": "No Email Spa", "address": "2 Main St"},
    ]
    unique, _ = import_csv.process_csv_rows(rows, [], "chicago_north_shore", "manual", {})
    by_name = {r["name"]: r for r in unique}
    glow = by_name["Glow Aesthetics"]
    assert glow["owner_email"] == "owner@example-medspa-import.test"
    assert glow["email_status"] == "unverified"
    assert glow["email_source"] == "csv"
    no_email = by_name["No Email Spa"]
    assert "owner_email" not in no_email
    assert "email_status" not in no_email


def test_import_csv_cli_missing_name_column_errors(tmp_path, capsys):
    from execution.personal_workflows.prodcraft_medspa.discovery import import_csv

    csv_path = tmp_path / "bad.csv"
    _write_csv(csv_path, ["website", "phone"], [["https://example-medspa-x.test", "(847) 555-0100"]])

    with pytest.raises(SystemExit) as exc_info:
        import_csv.main(["--csv", str(csv_path), "--metro", "chicago_north_shore", "--store-root", str(tmp_path / "store")])
    assert exc_info.value.code != 0
    assert "name" in capsys.readouterr().err.lower()


def test_import_csv_cli_end_to_end_and_idempotent_rerun(tmp_path, capsys):
    from execution.personal_workflows.prodcraft_medspa.discovery import import_csv
    from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore

    store_root = tmp_path / "store"
    _seed_chains(store_root)

    csv_path = tmp_path / "prospects.csv"
    _write_csv(
        csv_path,
        ["Name", "Website", "Phone", "Address", "City", "State", "Review_Count", "Email"],
        [
            [
                "Example Med Spa One",
                "https://example-medspa-import-1.test",
                "(847) 555-0101",
                "1 Main St",
                "Winnetka",
                "IL",
                "80",
                "owner1@example-medspa-import-1.test",
            ],
            ["Ulta Beauty", "https://ulta.example.test", "(847) 555-0102", "2 Main St", "Winnetka", "IL", "500", ""],
            ["Tiny New Spa", "https://example-medspa-import-2.test", "(847) 555-0103", "3 Main St", "Winnetka", "IL", "2", ""],
            ["", "", "(847) 555-0104", "4 Main St", "Winnetka", "IL", "40", ""],
        ],
    )

    argv = ["--csv", str(csv_path), "--metro", "chicago_north_shore", "--source", "web_search", "--store-root", str(store_root)]
    import_csv.main(argv)
    out = capsys.readouterr().out
    stat1 = json.loads(out.strip().splitlines()[-1])
    assert stat1["script"] == "import_csv"
    assert stat1["in"] == 4
    assert stat1["unique"] == 4
    assert stat1["kept"] == 1
    assert stat1["dropped"] == {"chain": 1, "no_name": 1, "too_small": 1}

    store = LocalStore(root=store_root)
    businesses = store.find_businesses(metro="chicago_north_shore")
    assert len(businesses) == 4
    kept = next(b for b in businesses if b["name"] == "Example Med Spa One")
    assert kept["discovery_source"] == "csv:web_search"
    assert kept["owner_email"] == "owner1@example-medspa-import-1.test"
    assert kept["email_status"] == "unverified"
    assert kept["email_source"] == "csv"
    assert kept["drop_reason"] is None

    # Re-import the same file: idempotent (place_ids are stable, upsert merges — no duplicates).
    import_csv.main(argv)
    capsys.readouterr()
    store2 = LocalStore(root=store_root)
    businesses2 = store2.find_businesses(metro="chicago_north_shore")
    assert len(businesses2) == 4
    place_ids = [b["place_id"] for b in businesses2]
    assert len(place_ids) == len(set(place_ids))
