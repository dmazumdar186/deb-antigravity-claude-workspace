"""
test_job_filter.py
description: pytest test suite for execution/custom_scrapers/job_filter.py. Verifies title filtering, language detection, hash stability, and end-to-end CandidateJob field completeness using the real config/job_tracker.json.
inputs: Inline RawJob dicts; config loaded via _jt_utils.load_jt_config().
outputs: pytest pass/fail assertions.
"""

import pytest
from datetime import datetime, timezone

from execution.personal_workflows._jt_utils import load_jt_config, now_iso
from execution.custom_scrapers.job_filter import filter_jobs, detect_language, is_kept_title


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def config():
    """Load the real job_tracker.json config once per session."""
    return load_jt_config()


def _make_raw(
    title: str,
    description_snippet: str = "",
    company_name: str = "Acme Corp",
    location: str | None = "Paris, France",
    board: str = "wttj",
) -> dict:
    """Build a minimal RawJob dict for test use."""
    return {
        "board": board,
        "source_url": "https://example.com/job/1",
        "title": title,
        "company_name": company_name,
        "location": location,
        "posted_at": None,
        "description_snippet": description_snippet,
        "raw_extracted_at": now_iso(),
    }


# ---------------------------------------------------------------------------
# Helper: run filter_jobs and return the single result
# ---------------------------------------------------------------------------

def _filter_one(title: str, description_snippet: str, config: dict, **kwargs) -> dict:
    raw = _make_raw(title, description_snippet, **kwargs)
    results = filter_jobs([raw], config)
    assert len(results) == 1
    return results[0]


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestAcceptedJobs:
    def test_senior_product_manager_en(self, config):
        """'Senior Product Manager' with English description → accepted, language='en'."""
        desc = (
            "We are looking for a Senior Product Manager to join our growing team. "
            "You will own the product roadmap and work closely with engineering."
        )
        result = _filter_one("Senior Product Manager", desc, config)
        assert result["passed_filters"] is True
        assert result["filter_reason"] == "accepted"
        assert result["language"] == "en"

    def test_product_manager_hf_fr(self, config):
        """'Product Manager (H/F)' with French description → accepted, language='fr'."""
        desc = (
            "Nous recherchons un Product Manager expérimenté pour définir "
            "la stratégie produit et coordonner les équipes techniques."
        )
        result = _filter_one("Product Manager (H/F)", desc, config)
        assert result["passed_filters"] is True
        assert result["filter_reason"] == "accepted"
        assert result["language"] == "fr"

    def test_chef_de_produit_senior_fr(self, config):
        """'Chef de Produit Senior' with French description → accepted, language='fr'."""
        desc = (
            "Rejoignez notre équipe en tant que Chef de Produit Senior. "
            "Vous piloterez le cycle de vie du produit de bout en bout."
        )
        result = _filter_one("Chef de Produit Senior", desc, config)
        assert result["passed_filters"] is True
        assert result["filter_reason"] == "accepted"
        assert result["language"] == "fr"


class TestRejectedByTitle:
    def test_junior_product_manager(self, config):
        """'Junior Product Manager' → rejected:junior."""
        desc = "Great opportunity for a junior to grow."
        result = _filter_one("Junior Product Manager", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:junior"

    def test_stagiaire_product_owner(self, config):
        """'Stagiaire Product Owner' → rejected:stage."""
        desc = "Stage de 6 mois au sein de notre équipe produit."
        result = _filter_one("Stagiaire Product Owner", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:stage"

    def test_product_owner_alternance(self, config):
        """'Product Owner — Alternance' → rejected:alternance."""
        desc = "Contrat en alternance pour accompagner notre Product Owner."
        result = _filter_one("Product Owner — Alternance", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:alternance"

    def test_apprenti_product_manager(self, config):
        """'Apprenti Product Manager' → rejected:apprenti."""
        desc = "Nous recrutons un apprenti pour notre département produit."
        result = _filter_one("Apprenti Product Manager", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:apprenti"

    def test_product_manager_intern(self, config):
        """'Product Manager Intern' → rejected:intern."""
        desc = "Summer internship opportunity for product enthusiasts."
        result = _filter_one("Product Manager Intern", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:intern"

    def test_assistant_product_manager(self, config):
        """'Assistant Product Manager' → rejected:assistant."""
        desc = "Support our product team as an assistant PM."
        result = _filter_one("Assistant Product Manager", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:assistant"

    def test_senior_backend_engineer(self, config):
        """'Senior Backend Engineer' with English desc → rejected:not_pm (no PM keyword)."""
        desc = "We need a senior backend engineer to build scalable microservices."
        result = _filter_one("Senior Backend Engineer", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:not_pm"


class TestRejectedByLanguage:
    def test_portuguese_desc_rejected_for_language(self, config):
        """Title is English (passes include list) but description is Portuguese → rejected:language.

        detect_language() only returns 'fr'/'en' (None for everything else), so language=None
        when Portuguese is detected — the language gate still fires because None not in allowed_langs.
        """
        desc = (
            "Estamos a procura de um gerente senior para liderar a nossa equipa de produto "
            "em Lisboa. Trabalhe connosco para construir solucoes inovadoras de software "
            "para o mercado europeu e ajude-nos a definir a estrategia de produto."
        )
        result = _filter_one("Senior Product Manager", desc, config, location="Lisboa")
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:language"
        # detect_language returns None for non-fr/en languages; gate still fires
        assert result["language"] not in ("fr", "en")

    def test_graduate_product_manager(self, config):
        """'Graduate Product Manager' → rejected:graduate."""
        desc = "Join our graduate program as a Product Manager."
        result = _filter_one("Graduate Product Manager", desc, config)
        assert result["passed_filters"] is False
        assert result["filter_reason"] == "rejected:graduate"


class TestHashStability:
    def test_identical_company_title_location_same_hash(self, config):
        """Two jobs with the same (company, title, location) must produce identical job_hash."""
        raw1 = _make_raw(
            "Product Manager",
            "Description one.",
            company_name="TechCo",
            location="Paris, France",
        )
        raw2 = _make_raw(
            "Product Manager",
            "Completely different description.",
            company_name="TechCo",
            location="Paris, France",
        )
        results = filter_jobs([raw1, raw2], config)
        assert len(results) == 2
        assert results[0]["job_hash"] == results[1]["job_hash"], (
            f"Expected identical hashes but got {results[0]['job_hash']!r} "
            f"and {results[1]['job_hash']!r}"
        )

    def test_different_location_different_hash(self, config):
        """Same (company, title) but different location → different hash."""
        raw1 = _make_raw("Product Manager", "Desc", company_name="TechCo", location="Paris")
        raw2 = _make_raw("Product Manager", "Desc", company_name="TechCo", location="Lyon")
        results = filter_jobs([raw1, raw2], config)
        assert results[0]["job_hash"] != results[1]["job_hash"]


class TestCandidateJobSchema:
    """Verify that all required CandidateJob fields are present in every output record."""

    _REQUIRED_FIELDS = [
        "board", "source_url", "title", "company_name", "location",
        "posted_at", "description_snippet", "raw_extracted_at",
        "job_hash", "title_normalized", "company_normalized",
        "language", "passed_filters", "filter_reason",
    ]

    def test_all_fields_present(self, config):
        raw = _make_raw("Product Manager", "Great role in a fast-growing startup.")
        results = filter_jobs([raw], config)
        result = results[0]
        for field in self._REQUIRED_FIELDS:
            assert field in result, f"Missing field: {field!r}"

    def test_passed_filters_is_bool(self, config):
        raw = _make_raw("Product Manager", "Great role.")
        result = filter_jobs([raw], config)[0]
        assert isinstance(result["passed_filters"], bool)
