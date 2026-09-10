"""
tiles.py
description: Tile dataclass + loader for per-metro Google Places search tiles (suburb-centered circles).
inputs: tiles/{metro}.json files (metro, state, tiles[]); imported by places_search.py and tests.
outputs: Tile dataclasses; pure functions, no filesystem writes, no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TILES_DIR = Path(__file__).resolve().parent / "tiles"

DEFAULT_RADIUS_M = 3000


@dataclass(frozen=True)
class Tile:
    name: str
    lat: float
    lng: float
    radius_m: int = DEFAULT_RADIUS_M


def known_metros() -> list[str]:
    """Metro slugs with a tile file, sorted."""
    if not TILES_DIR.exists():
        return []
    return sorted(p.stem for p in TILES_DIR.glob("*.json"))


def _load_raw(metro: str) -> dict:
    path = TILES_DIR / f"{metro}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No tile file for metro '{metro}' at {path}. Known metros: {', '.join(known_metros())}"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_tiles(metro: str) -> list[Tile]:
    """Load the tile list for `metro` from tiles/{metro}.json.

    Raises FileNotFoundError with a clear message (including known metros) if the
    metro has no tile file.
    """
    data = _load_raw(metro)
    return [
        Tile(
            name=t["name"],
            lat=float(t["lat"]),
            lng=float(t["lng"]),
            radius_m=int(t.get("radius_m", DEFAULT_RADIUS_M)),
        )
        for t in data.get("tiles", [])
    ]


def metro_state(metro: str) -> str | None:
    """Two-letter state code stored in tiles/{metro}.json, or None if the metro/file is missing."""
    try:
        data = _load_raw(metro)
    except FileNotFoundError:
        return None
    return data.get("state")


def covering_tiles(centers: list[tuple[str, float, float]], radius_m: int = DEFAULT_RADIUS_M) -> list[Tile]:
    """Build Tile objects from (name, lat, lng) centers at a uniform radius.

    Helper for constructing new tile files or ad-hoc tiling from a suburb-center
    list; does not read or write any file.
    """
    return [Tile(name=name, lat=lat, lng=lng, radius_m=radius_m) for name, lat, lng in centers]
