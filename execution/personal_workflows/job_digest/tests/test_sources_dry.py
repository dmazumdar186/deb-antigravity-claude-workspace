"""
description: Offline pytest coverage for job_digest source adapters. Verifies every
    adapter's dry(=True) fixture path returns validated SourceJob rows with no network,
    and that fetch_all() fans out correctly across a multi-country profile and isolates
    a raising adapter.
inputs: none (pure offline; fixtures under execution/personal_workflows/job_digest/fixtures/,
    shipped as package data — see C5 in the job_digest directive)
outputs: pytest results
"""

from __future__ import annotations

import pytest

from execution.personal_workflows.job_digest import registry
from execution.personal_workflows.job_digest.contracts import SourceJob
from execution.personal_workflows.job_digest.profile_schema import Profile
from execution.personal_workflows.job_digest.sources import (
    SOURCES,
    fetch_all,
    france_travail,
    hellowork,
    linkedin_guest_api,
    remoteok,
    weworkremotely,
    wttj_algolia,
)


def _profile(countries: list[str]) -> Profile:
    return Profile.model_validate({
        "candidate": {"name": "Test Candidate", "email": "test.candidate@example.com"},
        "roles": [{"title": "Product Manager", "synonyms": ["Product Owner"]}],
        "locations": {"countries": countries, "remote_ok": True},
        "screening": {
            "summary": "Product manager with 6 years of B2B SaaS experience across FR/DE/EU markets.",
        },
    })


FR_PROFILE = _profile(["FR"])
FR_DE_PROFILE = _profile(["FR", "DE"])


@pytest.mark.parametrize(
    "module,fr_only",
    [
        (linkedin_guest_api, False),
        (remoteok, False),
        (weworkremotely, False),
        (france_travail, True),
        (wttj_algolia, False),
        (hellowork, True),
    ],
)
def test_adapter_dry_fetch_returns_validated_jobs(module, fr_only):
    profile = FR_PROFILE
    country = registry.get("FR") if fr_only or module in (linkedin_guest_api, wttj_algolia) else None
    jobs = module.fetch(profile, country, dry=True)
    assert isinstance(jobs, list)
    assert len(jobs) >= 5, f"{module.__name__} fixture should have >=5 rows"
    for job in jobs:
        assert isinstance(job, SourceJob)
        assert job.title
        assert job.company


def test_sources_dict_exposes_all_adapters():
    assert set(SOURCES) == {
        "linkedin_guest_api", "remoteok", "weworkremotely",
        "france_travail", "wttj_algolia", "hellowork",
    }
    for fn in SOURCES.values():
        assert callable(fn)


def test_fetch_all_dry_two_country_profile_returns_expected_keys():
    results = fetch_all(FR_DE_PROFILE, dry=True, max_workers=4)

    # Global sources run once, no country suffix.
    assert "remoteok" in results
    assert "weworkremotely" in results

    # Country-scoped sources fan out per selected country that enables them.
    assert "linkedin_guest_api[FR]" in results
    assert "linkedin_guest_api[DE]" in results
    assert "wttj_algolia[FR]" in results
    assert "wttj_algolia[DE]" in results

    # France Travail and Hellowork are FR-only in the registry.
    assert "france_travail[FR]" in results
    assert "hellowork[FR]" in results
    assert "france_travail[DE]" not in results
    assert "hellowork[DE]" not in results

    for key, jobs in results.items():
        assert isinstance(jobs, list)
        assert len(jobs) > 0, f"{key} returned no dry-fixture jobs"


def test_n3a_france_travail_naive_posted_at_coerced_to_utc():
    """N3a: dateCreation/dateActualisation without a trailing 'Z' parse naive
    — _parse_offer must fall back to UTC like every other source adapter,
    rather than leaving posted_at naive (which later breaks a naive-vs-aware
    comparison, e.g. notifier/sheet.py's Top Matches cutoff)."""
    offer = {
        "id": "123",
        "intitule": "Ingenieur logiciel",
        "entreprise": {"nom": "Acme"},
        "lieuTravail": {"libelle": "Paris"},
        "description": "Une description.",
        "typeContratLibelle": "CDI",
        "dateCreation": "2026-01-01T12:00:00.000",  # no trailing Z, no offset
    }
    job = france_travail._parse_offer(offer)
    assert job is not None
    assert job.posted_at is not None
    assert job.posted_at.tzinfo is not None

    offer_z = dict(offer, dateCreation="2026-01-01T12:00:00Z")
    job_z = france_travail._parse_offer(offer_z)
    assert job_z.posted_at.tzinfo is not None


def test_fetch_all_isolates_a_raising_adapter(monkeypatch):
    def _boom(profile, country, *, dry=False):
        raise RuntimeError("simulated adapter failure")

    monkeypatch.setitem(SOURCES, "remoteok", _boom)

    results = fetch_all(FR_PROFILE, dry=True, max_workers=4)

    assert results["remoteok"] == []
    # Every other key still produced its normal (non-empty) fixture rows.
    other_keys = [k for k in results if k != "remoteok"]
    assert other_keys, "expected other sources to still run"
    for key in other_keys:
        assert len(results[key]) > 0, f"{key} should be unaffected by remoteok's failure"
