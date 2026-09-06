"""
description: Offline tests for normalizer/normalize.py's _detect_remote (C3).
inputs: none (uses the exact location strings shipped in tests/fixtures*)
outputs: pytest assertions
"""

from __future__ import annotations

from ..contracts import RemoteMode
from ..normalizer.normalize import _detect_remote


def test_bare_remote_location_strings_are_remote() -> None:
    """Exact strings RemoteOK/WeWorkRemotely put in location_raw — none of
    these name a city/region, so they must resolve to REMOTE, not HYBRID
    (C3: was defaulting to HYBRID, which filters then dropped)."""
    for loc in [
        "Remote",
        "Remote (Worldwide)",
        "Remote (US)",
        "Remote (EU)",
        "Remote (Canada)",
        "Remote (Anywhere)",
        "Remote (US Time Zones)",
        "Remote (Europe)",
        "Anywhere",
        "Worldwide",
    ]:
        assert _detect_remote(loc, "") == RemoteMode.REMOTE, loc


def test_hybrid_location_string() -> None:
    assert _detect_remote("Hybrid - Paris, France", "") == RemoteMode.HYBRID
    assert _detect_remote("Hybride - Lyon", "") == RemoteMode.HYBRID


def test_onsite_location_string() -> None:
    assert _detect_remote("On-site - Berlin, Germany", "") == RemoteMode.ONSITE
    assert _detect_remote("Présentiel - Paris", "") == RemoteMode.ONSITE


def test_city_location_falls_through_to_description_heuristic() -> None:
    # A real city name is not a bare-remote string, so it must not be
    # short-circuited to REMOTE just because the description mentions remote work.
    assert _detect_remote("Paris, Île-de-France, France", "") == RemoteMode.UNKNOWN
    assert (
        _detect_remote("Berlin, Germany", "This role is hybrid, 3 days in office.")
        == RemoteMode.HYBRID
    )
