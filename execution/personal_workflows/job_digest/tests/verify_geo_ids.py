"""
description: Manual, network-touching geoId verification for job_digest's LinkedIn
    country registry. NOT collected by pytest (imports guarded by if __name__ ==
    "__main__" execution only, no test_ prefix). For each registry country, fetches ONE
    LinkedIn guest search page (keyword "manager", that geoId, 25 results) and checks
    that a majority of parsed location strings contain one of the country's aliases.
    Flips registry.py's verified=True for countries that pass (via direct source edit
    reported back to the operator, not applied automatically here — this script only
    PRINTS a table + a proposed diff; a human/agent applies it, per the task's
    "you MAY edit registry.py" scope).
inputs:
  - none (reads execution/personal_workflows/job_digest/registry.py's COUNTRIES)
  - network: hits linkedin.com/jobs-guest directly through the environment's HTTPS proxy
outputs:
  - stdout: a country / geoId / sample-locations / pass-fail-skipped table
  - stdout: a proposed registry.py verified=True / linkedin_geo_id diff (not applied)

Run: python3 execution/personal_workflows/job_digest/tests/verify_geo_ids.py

Respects a 3s delay between calls. Stops entirely (marks remaining countries
"skipped — blocked") on the first LinkedInBlockedError, so a block never triggers a
misleading fail. If the network itself is unavailable (DNS/connect failure on the
first call), says so plainly and marks every country "skipped — no network" without
touching registry.py.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import httpx

_PKG_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE = _PKG_DIR.parent.parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from execution.personal_workflows.job_digest import registry  # noqa: E402
from execution.personal_workflows.job_digest.sources.linkedin_guest_api import (  # noqa: E402
    HEADERS,
    SEARCH_URL,
    LinkedInBlockedError,
    _looks_blocked,
    _parse_cards,
)

KEYWORD = "manager"
RESULTS_TO_FETCH = 25
DELAY_BETWEEN_CALLS_S = 3.0
MAJORITY_THRESHOLD = 0.5


class NoNetworkError(RuntimeError):
    """Raised when the very first live call cannot even connect."""


def _fetch_one_page(client: httpx.Client, geo_id: str) -> list[dict]:
    params = {"keywords": KEYWORD, "geoId": geo_id, "start": 0}
    resp = client.get(SEARCH_URL, params=params, timeout=20.0)
    text = resp.text or ""
    if _looks_blocked(text):
        raise LinkedInBlockedError(f"block marker for geoId={geo_id}")
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} for geoId={geo_id}")
    return _parse_cards(text)[:RESULTS_TO_FETCH]


def _location_matches_country(location: str, aliases: tuple[str, ...]) -> bool:
    low = location.lower()
    return any(alias in low for alias in aliases)


def verify_all() -> dict[str, dict]:
    """Returns {iso2: {"geo_id", "status", "samples", "match_ratio"}}."""
    out: dict[str, dict] = {}
    blocked = False

    with httpx.Client(headers=HEADERS) as client:
        for i, (iso2, country) in enumerate(registry.COUNTRIES.items()):
            if blocked:
                out[iso2] = {
                    "geo_id": country.linkedin_geo_id, "status": "skipped — blocked",
                    "samples": [], "match_ratio": None,
                }
                continue

            if i > 0:
                time.sleep(DELAY_BETWEEN_CALLS_S)

            try:
                cards = _fetch_one_page(client, country.linkedin_geo_id)
            except LinkedInBlockedError as exc:
                print(f"BLOCKED on {iso2}: {exc} — stopping remaining checks.")
                blocked = True
                out[iso2] = {
                    "geo_id": country.linkedin_geo_id, "status": "skipped — blocked",
                    "samples": [], "match_ratio": None,
                }
                continue
            except httpx.HTTPError as exc:
                if i == 0:
                    raise NoNetworkError(
                        f"could not reach LinkedIn on the first call ({exc}); "
                        "network may be unavailable in this environment."
                    ) from exc
                out[iso2] = {
                    "geo_id": country.linkedin_geo_id, "status": f"skipped — HTTP error: {exc}",
                    "samples": [], "match_ratio": None,
                }
                continue

            locations = [c["location"] for c in cards if c.get("location")]
            samples = locations[:5]
            if not locations:
                out[iso2] = {
                    "geo_id": country.linkedin_geo_id, "status": "fail — no location data returned",
                    "samples": [], "match_ratio": 0.0,
                }
                continue

            matches = sum(1 for loc in locations if _location_matches_country(loc, country.aliases))
            ratio = matches / len(locations)
            status = "pass" if ratio >= MAJORITY_THRESHOLD else "fail"
            out[iso2] = {
                "geo_id": country.linkedin_geo_id, "status": status,
                "samples": samples, "match_ratio": ratio,
            }

    return out


def _resolve_geo_id_by_name(client: httpx.Client, country_name: str) -> str | None:
    """Best-effort: search with location=<name> and see which geoId LinkedIn's
    search-page HTML resolves to, by scanning for a urn:li:geo:<id> hint in the
    returned markup near a matching location string. Returns None if not found —
    LinkedIn does not expose a clean geo-resolution API on the guest surface, so
    this is a heuristic fallback, not authoritative."""
    try:
        resp = client.get(
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
            params={"keywords": KEYWORD, "location": country_name, "start": 0},
            timeout=20.0,
        )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    m = re.search(r"urn:li:geo:(\d+)", resp.text or "")
    return m.group(1) if m else None


def print_table(results: dict[str, dict]) -> None:
    print(f"{'ISO2':<5} {'geoId':<12} {'status':<28} sample locations")
    print("-" * 100)
    for iso2, r in results.items():
        samples = "; ".join(r["samples"]) if r["samples"] else "-"
        print(f"{iso2:<5} {r['geo_id']:<12} {r['status']:<28} {samples}")


def print_proposed_registry_changes(results: dict[str, dict]) -> None:
    to_verify = [iso2 for iso2, r in results.items() if r["status"] == "pass" and not registry.get(iso2).verified]
    if to_verify:
        print("\nProposed registry.py change — flip verified=True for:")
        for iso2 in to_verify:
            print(f"  {iso2} (geoId={registry.get(iso2).linkedin_geo_id})")
    else:
        print("\nNo registry.py verified= changes proposed from this run.")


if __name__ == "__main__":
    try:
        results = verify_all()
    except NoNetworkError as exc:
        print(f"NO NETWORK: {exc}")
        print("registry.py left untouched.")
        sys.exit(1)

    print_table(results)
    print_proposed_registry_changes(results)
