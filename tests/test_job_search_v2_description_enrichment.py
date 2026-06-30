"""
description: Unit tests for the three description-enrichment fixes shipped
    2026-06-30:
      - WTTJ: extract profile field from Algolia hit -> description_snippet
      - LinkedIn: detail-fetch + show-more-less-html__markup parsing
      - Hellowork: schema.org JobPosting JSON-LD extraction
    All tests are pure-function — no live HTTP, no Gemini, no fixtures from
    the LinkedIn rate-limited endpoint. The hellowork live-fetch path is
    covered by the smoke test in the source's main() instead.
inputs: pytest discovery
outputs: assertions
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))


# ---------- WTTJ ----------


def test_wttj_extracts_description_from_profile_field():
    """If the Algolia hit's `profile` is filled, _hit_to_source_job should
    populate description_snippet (HTML-stripped, capped at 2000 chars)."""
    from execution.personal_workflows.job_search_v2.sources.wttj_algolia import (
        _hit_to_source_job,
    )
    hit = {
        "objectID": "abc123",
        "name": "Senior AI Product Manager",
        "organization": {"name": "Acme AI", "slug": "acme-ai"},
        "slug": "senior-ai-product-manager",
        "office": {"city": "Paris", "country": "France"},
        "offices": [],
        "profile": (
            "<p>You will own the AI PM roadmap, write PRDs, drive evaluation. "
            "RAG + multi-agent experience required. GDPR compliance background "
            "a plus.</p>"
        ),
        "published_at": "2026-06-30T07:00:00+02:00",
        "contract_type": "permanent",
    }
    sj = _hit_to_source_job(hit)
    assert sj is not None
    # HTML tags must be stripped
    assert "<p>" not in sj.description_snippet
    assert "RAG" in sj.description_snippet
    assert "multi-agent" in sj.description_snippet
    assert len(sj.description_snippet) > 100


def test_wttj_empty_profile_yields_empty_description():
    """If `profile` is None (the case for ~10% of jobs), description should
    be empty, not 'None' or a crash."""
    from execution.personal_workflows.job_search_v2.sources.wttj_algolia import (
        _hit_to_source_job,
    )
    hit = {
        "objectID": "abc456",
        "name": "Product Manager",
        "organization": {"name": "Acme", "slug": "acme"},
        "slug": "pm-acme",
        "office": {"city": "Paris", "country": "France"},
        "offices": [],
        "profile": None,
        "published_at": "2026-06-30T07:00:00Z",
        "contract_type": "permanent",
    }
    sj = _hit_to_source_job(hit)
    assert sj is not None
    assert sj.description_snippet == ""


def test_wttj_description_capped_at_2000_chars():
    """Long descriptions get truncated to fit SourceJob.description_snippet
    max_length=2000 — otherwise Pydantic rejects."""
    from execution.personal_workflows.job_search_v2.sources.wttj_algolia import (
        _hit_to_source_job,
    )
    hit = {
        "objectID": "xyz",
        "name": "PM",
        "organization": {"name": "Acme", "slug": "acme"},
        "slug": "pm",
        "office": {"city": "Paris", "country": "France"},
        "offices": [],
        "profile": "x" * 5000,
        "published_at": "2026-06-30T07:00:00Z",
        "contract_type": "permanent",
    }
    sj = _hit_to_source_job(hit)
    assert sj is not None
    assert len(sj.description_snippet) == 2000


# ---------- LinkedIn detail enrichment ----------


def test_linkedin_card_uses_description_when_enriched():
    """_card_to_source_job now reads description_snippet from the card dict
    if present (set by _enrich_with_jd)."""
    from execution.personal_workflows.job_search_v2.sources.linkedin_guest_api import (
        _card_to_source_job,
    )
    card = {
        "job_id": "12345",
        "title": "Senior AI Product Manager",
        "company": "Mistral AI",
        "location": "Paris, France",
        "apply_url": "https://www.linkedin.com/jobs/view/12345",
        "posted_iso": "2026-06-30T07:00:00+00:00",
        "description_snippet": "Build LLM products. Lead PM team. RAG, multi-agent.",
    }
    sj = _card_to_source_job(card)
    assert sj is not None
    assert "RAG" in sj.description_snippet
    assert "LLM" in sj.description_snippet


def test_linkedin_card_without_description_does_not_crash():
    """Backward-compat: cards from fixtures don't have description_snippet
    and should fall back to empty, not KeyError."""
    from execution.personal_workflows.job_search_v2.sources.linkedin_guest_api import (
        _card_to_source_job,
    )
    card = {
        "job_id": "12346",
        "title": "PM",
        "company": "Acme",
        "location": "Paris",
        "apply_url": "https://www.linkedin.com/jobs/view/12346",
        "posted_iso": "",
        # description_snippet intentionally absent
    }
    sj = _card_to_source_job(card)
    assert sj is not None
    assert sj.description_snippet == ""


# ---------- Hellowork ----------


def test_hellowork_parse_jobposting_jsonld_extracts_all_fields():
    """The schema.org JobPosting blob is the ground truth for every Hellowork
    job page. The parser must handle it AND the alternative @graph
    wrapping shape, and must populate every SourceJob field correctly."""
    from execution.personal_workflows.job_search_v2.sources.hellowork import (
        _ld_to_source_job, _parse_job_posting_ld,
    )
    html = """
    <html><head>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"WebSite","name":"Hellowork"}
      </script>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"JobPosting",
       "title":"Senior AI Product Manager H/F",
       "description":"<p>Build the AI roadmap. Strong RAG/LLM background.</p>",
       "datePosted":"2026-06-30T08:00:00Z",
       "employmentType":"FULL_TIME",
       "hiringOrganization":{"@type":"Organization","name":"Mistral AI"},
       "jobLocation":{"@type":"Place","address":{
           "@type":"PostalAddress","addressLocality":"Paris",
           "addressRegion":"Île-de-France","addressCountry":"FR"}}}
      </script>
    </head><body>job content</body></html>
    """
    ld = _parse_job_posting_ld(html)
    assert ld is not None
    assert ld["title"] == "Senior AI Product Manager H/F"

    sj = _ld_to_source_job("80123456", ld)
    assert sj is not None
    assert sj.title == "Senior AI Product Manager H/F"
    assert sj.company == "Mistral AI"
    assert "Paris" in sj.location_raw
    assert sj.contract_type_raw == "FULL_TIME"
    # HTML stripped from description
    assert "<p>" not in sj.description_snippet
    assert "RAG/LLM" in sj.description_snippet
    # URL built from job_id
    assert "80123456" in str(sj.url)


def test_hellowork_handles_jobposting_in_graph_wrapper():
    """Some pages wrap JobPosting in @graph. The parser must traverse it."""
    from execution.personal_workflows.job_search_v2.sources.hellowork import (
        _parse_job_posting_ld,
    )
    html = """<script type="application/ld+json">
      {"@context":"https://schema.org","@graph":[
        {"@type":"WebSite","name":"Hellowork"},
        {"@type":"JobPosting","title":"Lead PM","description":"...",
         "hiringOrganization":{"name":"Acme"}}
      ]}
      </script>"""
    ld = _parse_job_posting_ld(html)
    assert ld is not None
    assert ld["title"] == "Lead PM"


def test_hellowork_extract_offer_ids_dedups_and_preserves_order():
    """Search pages list each offer multiple times (premium + regular slot).
    The extractor must dedup while preserving first-seen order."""
    from execution.personal_workflows.job_search_v2.sources.hellowork import (
        _extract_offer_ids,
    )
    html = (
        '<a href="/fr-fr/emplois/111.html">'
        '<a href="/fr-fr/emplois/222.html">'
        '<a href="/fr-fr/emplois/111.html">'  # dup
        '<a href="/fr-fr/emplois/333.html">'
    )
    ids = _extract_offer_ids(html)
    assert ids == ["111", "222", "333"]


def test_hellowork_ld_to_sourcejob_skips_missing_title():
    """SourceJob.title is required; skip the row instead of raising."""
    from execution.personal_workflows.job_search_v2.sources.hellowork import (
        _ld_to_source_job,
    )
    ld_no_title = {"description": "X", "hiringOrganization": {"name": "Acme"}}
    assert _ld_to_source_job("99", ld_no_title) is None
    ld_no_company = {"title": "Lead PM"}
    assert _ld_to_source_job("99", ld_no_company) is None


# ---------- contracts (HELLOWORK enum addition) ----------


def test_hellowork_enum_value_added():
    """The new JobSource.HELLOWORK enum value must exist for SourceJob to
    serialize with source='hellowork'."""
    from execution.personal_workflows.job_search_v2.contracts import JobSource
    assert JobSource.HELLOWORK.value == "hellowork"


def test_run_dispatch_includes_hellowork():
    """run._DISPATCH must route 'hellowork' to the new fetcher; without this
    the orchestrator silently ignores the source."""
    from execution.personal_workflows.job_search_v2 import run as run_mod
    from execution.personal_workflows.job_search_v2.contracts import JobSource
    assert JobSource.HELLOWORK.value in run_mod._DISPATCH
    assert callable(run_mod._DISPATCH[JobSource.HELLOWORK.value])
