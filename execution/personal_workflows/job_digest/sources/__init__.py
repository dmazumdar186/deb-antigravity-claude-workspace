"""
description: Source registry + parallel fan-out dispatcher for job_digest. Every source
    module exposes fetch(profile, country, *, dry=False) -> list[SourceJob]; this module
    is the only place that knows which sources are country-scoped vs global and fans a
    profile out across its selected countries.
inputs: profile.Profile (via fetch_all)
outputs: SOURCES dict[str, Callable]; fetch_all() -> dict[str, list[SourceJob]] keyed
    "source[ISO2]" for country-scoped sources, "source" for global ones
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Callable

from .. import registry
from ..contracts import SourceJob
from ..profile_schema import Profile
from . import france_travail, hellowork, linkedin_guest_api, remoteok, weworkremotely, wttj_algolia

logger = logging.getLogger("job_digest.sources")

# Sources that take a country (fanned out once per selected country whose
# registry entry lists them). Everything else is a global feed, run once.
COUNTRY_SCOPED = {"linkedin_guest_api", "wttj_algolia", "france_travail", "hellowork"}

SOURCES: dict[str, Callable[..., list[SourceJob]]] = {
    "linkedin_guest_api": linkedin_guest_api.fetch,
    "remoteok": remoteok.fetch,
    "weworkremotely": weworkremotely.fetch,
    "france_travail": france_travail.fetch,
    "wttj_algolia": wttj_algolia.fetch,
    "hellowork": hellowork.fetch,
}


def _plan(profile: Profile) -> list[tuple[str, "registry.Country | None"]]:
    """Build the (source_name, country|None) call plan for this profile.

    Country-scoped sources fan out per selected country that enables them
    (registry.Country.sources); global sources run exactly once regardless
    of how many countries are selected.
    """
    plan: list[tuple[str, "registry.Country | None"]] = []
    enabled = set(profile.sources)
    global_sources = [s for s in enabled if s not in COUNTRY_SCOPED]
    for s in global_sources:
        plan.append((s, None))
    for country in profile.countries:
        for s in country.sources:
            if s in enabled and s in COUNTRY_SCOPED:
                plan.append((s, country))
    return plan


def _key(source_name: str, country: "registry.Country | None") -> str:
    return f"{source_name}[{country.iso2}]" if country is not None else source_name


def fetch_all(profile: Profile, *, dry: bool = False, max_workers: int = 4) -> dict[str, list[SourceJob]]:
    """Run every (source, country) pair from the profile's plan in a thread pool.

    Each call is isolated: an exception in one (source, country) is logged and
    yields [] for that key without affecting any other result.
    """
    plan = _plan(profile)
    results: dict[str, list[SourceJob]] = {}
    results_lock = Lock()

    def _call(source_name: str, country: "registry.Country | None") -> tuple[str, list[SourceJob]]:
        key = _key(source_name, country)
        fn = SOURCES[source_name]
        try:
            jobs = fn(profile, country, dry=dry)
        except Exception as exc:  # noqa: BLE001 — isolate one source's failure from the rest
            logger.warning("job_digest.sources: %s failed: %s", key, exc)
            return key, []
        return key, jobs

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_call, name, country) for name, country in plan]
        for fut in as_completed(futures):
            key, jobs = fut.result()
            with results_lock:
                results[key] = jobs

    if dry and sum(len(jobs) for jobs in results.values()) == 0:
        # C5: the shipped bundle depends on fixtures/*.jsonl existing next to
        # this package; a silent [] here (missing fixtures, bad packaging)
        # looks identical to "no jobs matched" unless we call it out.
        logger.warning("dry mode returned zero jobs — fixtures missing?")

    return results
