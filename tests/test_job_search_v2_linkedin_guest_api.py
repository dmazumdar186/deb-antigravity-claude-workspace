"""Parser tests for sources/linkedin_guest_api.py.

Tests the HTML parser against minimal fixtures that mimic the real LinkedIn jobs-guest
response shape observed on 2026-06-18. Per the 2026-06-18 tightening of the front-door
rule (fixture tests are NOT front-door synthetics), these live under tests/parser_/unit_
naming and assert PARSER correctness only. Live coverage = tests/front_door_*.sh.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from execution.personal_workflows.job_search_v2.contracts import JobSource
from execution.personal_workflows.job_search_v2.sources import linkedin_guest_api as lga


# Minimal valid LinkedIn jobs-guest search-page HTML — one job card, all parser-visible
# selectors present. Mirrors the live response shape (h3.base-search-card__title,
# h4.base-search-card__subtitle, span.job-search-card__location, a.base-card__full-link,
# time[datetime], div.base-card[data-entity-urn]).
_MINIMAL_HTML = """
<html><body>
<ul>
  <li>
    <div class="base-card" data-entity-urn="urn:li:jobPosting:4428049765">
      <a class="base-card__full-link" href="https://fr.linkedin.com/jobs/view/product-owner-aem-at-nexton-4428049765?utm_source=alert"></a>
      <h3 class="base-search-card__title">Product Owner AEM H/F</h3>
      <h4 class="base-search-card__subtitle">NEXTON</h4>
      <span class="job-search-card__location">Paris, Île-de-France, France</span>
      <time datetime="2026-06-16">2 days ago</time>
    </div>
  </li>
</ul>
</body></html>
""".strip()


def test_parse_minimal_card_extracts_all_fields():
    cards = lga._parse_cards(_MINIMAL_HTML)
    assert len(cards) == 1
    card = cards[0]
    assert card["job_id"] == "4428049765"
    assert card["title"] == "Product Owner AEM H/F"
    assert card["company"] == "NEXTON"
    assert "Paris" in card["location"]
    assert card["apply_url"].startswith("https://fr.linkedin.com/jobs/view/")
    assert card["posted_iso"] == "2026-06-16"


def test_card_to_source_job_emits_valid_sourcejob():
    cards = lga._parse_cards(_MINIMAL_HTML)
    sj = lga._card_to_source_job(cards[0])
    assert sj is not None
    assert sj.source == JobSource.LINKEDIN_GUEST_API
    assert sj.source_id == "4428049765"
    assert sj.title == "Product Owner AEM H/F"
    assert sj.company == "NEXTON"
    # posted_at must be tz-aware (parser supplies UTC if naive)
    assert sj.posted_at is not None
    assert sj.posted_at.tzinfo is not None


def test_parse_cards_handles_empty_html():
    cards = lga._parse_cards("<html><body></body></html>")
    assert cards == []


def test_parse_cards_skips_cards_without_job_id():
    """Cards missing the urn:li:jobPosting:NNN selector AND the href-with-id fallback
    AND any nested-urn fallback must be dropped silently — not crash the parser."""
    html = """
    <div class="base-card">
      <h3 class="base-search-card__title">No ID Job</h3>
      <h4 class="base-search-card__subtitle">Unknown</h4>
    </div>
    """
    cards = lga._parse_cards(html)
    assert cards == []


def test_blocked_marker_detection_is_case_insensitive():
    assert lga._looks_blocked("Please CAPTCHA verify") is True
    assert lga._looks_blocked("normal HTML content") is False
    assert lga._looks_blocked("location: /checkpoint/challenge") is True


def test_fetch_from_fixture_missing_file_returns_empty():
    """Resilience: a missing fixture path must not raise — return [] so the
    orchestrator survives a misconfigured fixture path."""
    jobs = lga.fetch_from_fixture(Path("/nonexistent/fixture/path.html"))
    assert jobs == []
