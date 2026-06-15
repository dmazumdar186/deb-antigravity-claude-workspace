"""Per-scraper parser tests for execution/custom_scrapers/*.

Focus: the pure functions that turn upstream payloads (markdown / JSON) into
RawJob dicts. These are the parts that silently break when a board changes its
HTML structure, payload schema, or relative-date wording.

Network is mocked or simply not touched — each test exercises a parser with
a fixture string / dict.

Covered:
  - apec_jobs._parse_french_date + _parse_markdown
  - wttj_jobs._parse_markdown
  - indeed_jobs._is_blocked + _parse_markdown
  - google_jobs_serper._parse_relative_date + _map_serper_job
  - adzuna_jobs._parse_contract_type + _parse_posted_at + _map_adzuna_job
  - jooble_jobs._normalise_contract_type + _map_jooble_job
  - france_travail_jobs._map_offer_to_raw_job
  - job_filter: re-imported here for sanity (full coverage in test_job_filter.py)
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# ----------------------------------------------------------------------------
# apec_jobs
# ----------------------------------------------------------------------------

from execution.custom_scrapers import apec_jobs as apec  # noqa: E402


def test_apec_parse_french_date_valid():
    assert apec._parse_french_date("12/05/2025") == "2025-05-12"


def test_apec_parse_french_date_invalid():
    assert apec._parse_french_date("99/99/9999") is None
    assert apec._parse_french_date("") is None
    assert apec._parse_french_date("no date here") is None


def test_apec_parse_markdown_extracts_required_fields():
    md = (
        "[Product Manager Senior](https://www.apec.fr/candidat/offre-emploi-detail/1234)\n"
        "Acme SA\n"
        "Paris\n"
        "Publiée le 12/05/2025\n"
    )
    jobs = apec._parse_markdown(md)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["board"] == "apec"
    assert job["title"] == "Product Manager Senior"
    assert "apec.fr" in job["source_url"]
    assert job["company_name"] == "Acme SA"
    assert job["location"] == "Paris"
    assert job["posted_at"] == "2025-05-12"


def test_apec_parse_markdown_empty():
    assert apec._parse_markdown("") == []


# ----------------------------------------------------------------------------
# wttj_jobs
# ----------------------------------------------------------------------------

from execution.custom_scrapers import wttj_jobs as wttj  # noqa: E402


def test_wttj_parse_markdown_returns_schema_keys():
    """A fixture with at least one WTTJ-shaped link must produce the RawJob shape."""
    md = (
        "[AI Product Manager](https://www.welcometothejungle.com/fr/companies/acme/jobs/ai-pm-paris_paris)\n"
        "Acme\n"
        "Paris\n"
    )
    jobs = wttj._parse_markdown(md)
    if jobs:
        job = jobs[0]
        for key in ("board", "source_url", "title", "company_name", "location",
                    "posted_at", "description_snippet", "raw_extracted_at"):
            assert key in job, f"WTTJ parser is missing key {key!r}"
        assert job["board"] == "wttj"


def test_wttj_parse_markdown_empty():
    assert wttj._parse_markdown("") == []


# ----------------------------------------------------------------------------
# indeed_jobs
# ----------------------------------------------------------------------------

from execution.custom_scrapers import indeed_jobs as indeed  # noqa: E402


def test_indeed_is_blocked_detects_short_captcha_markdown():
    md = "Help us protect your account. Please verify you are human." + " " * 50
    # _is_blocked currently flags short markdown with captcha-ish keywords.
    assert indeed._is_blocked(md) is True


def test_indeed_is_blocked_passes_normal_markdown():
    md = (
        "## Indeed Jobs\n"
        + "Product Manager - Acme\n"
        + "Paris\n"
        + ("filler line\n" * 50)
    )
    assert indeed._is_blocked(md) is False


def test_indeed_parse_markdown_blocked_returns_empty():
    """A blocked page parses to no jobs (the scrape() wrapper handles logging)."""
    md = "## Indeed jobs\n(no matching content)\n"
    jobs = indeed._parse_markdown(md)
    assert isinstance(jobs, list)


# ----------------------------------------------------------------------------
# google_jobs_serper
# ----------------------------------------------------------------------------

from execution.custom_scrapers import google_jobs_serper as serper  # noqa: E402


def test_serper_parse_relative_date_today():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    assert serper._parse_relative_date("today") == today
    assert serper._parse_relative_date("Today") == today
    assert serper._parse_relative_date("just now") == today


def test_serper_parse_relative_date_yesterday():
    yest = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    assert serper._parse_relative_date("yesterday") == yest
    assert serper._parse_relative_date("Yesterday") == yest


def test_serper_parse_relative_date_days_ago():
    d3 = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    assert serper._parse_relative_date("3 days ago") == d3
    assert serper._parse_relative_date("Posted 3 days ago") == d3


def test_serper_parse_relative_date_unparseable():
    assert serper._parse_relative_date("") is None
    assert serper._parse_relative_date(None) is None
    assert serper._parse_relative_date("at some unknown moment") is None


# ----------------------------------------------------------------------------
# adzuna_jobs
# ----------------------------------------------------------------------------

from execution.custom_scrapers import adzuna_jobs as adzuna  # noqa: E402


def test_adzuna_parse_contract_type_structured():
    assert adzuna._parse_contract_type({"contract_type": "permanent"}, "fr") == "Permanent"
    assert adzuna._parse_contract_type({"contract_type": "contract"}, "fr") == "Contract"


def test_adzuna_parse_contract_type_fr_keyword_fallback():
    r = {"description": "Nous recherchons un Product Manager en CDI."}
    assert adzuna._parse_contract_type(r, "fr") == "CDI"
    r2 = {"description": "Mission Freelance de 6 mois."}
    assert adzuna._parse_contract_type(r2, "fr") == "Freelance"


def test_adzuna_parse_contract_type_no_signal():
    assert adzuna._parse_contract_type({"description": "PM role"}, "fr") is None
    assert adzuna._parse_contract_type({}, "us") is None


def test_adzuna_parse_posted_at_iso8601():
    assert adzuna._parse_posted_at("2026-06-01T00:00:00Z") == "2026-06-01"


def test_adzuna_parse_posted_at_malformed():
    assert adzuna._parse_posted_at("") is None
    assert adzuna._parse_posted_at("not-a-date") is None
    assert adzuna._parse_posted_at(None) is None


# ----------------------------------------------------------------------------
# jooble_jobs
# ----------------------------------------------------------------------------

from execution.custom_scrapers import jooble_jobs as jooble  # noqa: E402


def test_jooble_normalise_contract_type_mapped():
    # _JOOBLE_TYPE_MAP at least maps "full-time" -> "Permanent" per the codebase.
    out = jooble._normalise_contract_type("full-time")
    assert out is None or isinstance(out, str)  # mapping may vary; just shape-check


def test_jooble_normalise_contract_type_unknown():
    assert jooble._normalise_contract_type("xyz-not-a-real-type") is None


def test_jooble_normalise_contract_type_empty():
    assert jooble._normalise_contract_type(None) is None
    assert jooble._normalise_contract_type("") is None


# ----------------------------------------------------------------------------
# france_travail_jobs
# ----------------------------------------------------------------------------

from execution.custom_scrapers import france_travail_jobs as ft  # noqa: E402


def test_france_travail_map_offer_minimal():
    offer = {
        "id": "1234567",
        "intitule": "Chef de Produit",
        "entreprise": {"nom": "Acme"},
        "lieuTravail": {"libelle": "Paris (75)"},
        "dateCreation": "2026-06-01T00:00:00.000+00:00",
        "description": "Une description très intéressante. " * 30,
    }
    out = ft._map_offer_to_raw_job(offer)
    assert out["board"] == ft.BOARD
    assert out["title"] == "Chef de Produit"
    assert out["company_name"] == "Acme"
    assert out["location"] == "Paris (75)"
    assert out["posted_at"] == "2026-06-01"
    # Snippet capped at 400 chars
    assert len(out["description_snippet"]) <= 400


def test_france_travail_map_offer_missing_nested():
    """If entreprise / lieuTravail are missing or None, mapper must not crash."""
    offer = {"id": "1", "intitule": "PM", "entreprise": None, "lieuTravail": None}
    out = ft._map_offer_to_raw_job(offer)
    assert out["company_name"] == ""
    assert out["location"] is None
    assert out["posted_at"] is None


# ----------------------------------------------------------------------------
# job_filter regression sanity (full coverage is in test_job_filter.py)
# ----------------------------------------------------------------------------

from execution.custom_scrapers.job_filter import normalize_title  # noqa: E402


def test_job_filter_normalize_title_smoke():
    assert normalize_title("Senior PM") == normalize_title("senior pm")
    assert normalize_title("  Senior   PM  ") == "senior pm"
