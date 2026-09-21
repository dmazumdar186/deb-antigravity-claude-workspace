"""
Contract tests for sources/serper_people.py -- RADAR_CONTRACTS.md section A.

Fixture-first, no network: tests/fixtures/serper_people/search_response.json
is a Serper response shaped exactly like the real API's documented reply
(searchParameters + organic), built with placeholder names ("Aoife Example",
"Cian Example", ...) -- no real person is referenced anywhere in this file.
`urllib.request.urlopen` is monkeypatched to hand back that fixture (or a
per-test variant); `serper_people.SEARCH_URL`/real network is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import SourceQuery
from gtm_client_workflows.gaia_sourcing.sources import serper_people
from gtm_client_workflows.gaia_sourcing.sources.licensed_common import ProviderNotConfigured

FIXTURES = Path(__file__).parent / "fixtures" / "serper_people"


def _fixture() -> dict:
    return json.loads((FIXTURES / "search_response.json").read_text(encoding="utf-8"))


class _Resp:
    def __init__(self, body: dict, status: int = 200):
        self._body = body
        self._status = status

    def getcode(self):
        return self._status

    def read(self):
        return json.dumps(self._body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _serper(monkeypatch, body: dict, requests_out: list | None = None):
    """Every urlopen call returns `body`; if `requests_out` is given, the
    raw JSON body of every request is appended to it so a test can assert
    on num/gl/hl or count calls."""

    def fake_urlopen(req, timeout=None):
        if requests_out is not None:
            requests_out.append(json.loads(req.data.decode("utf-8")))
        return _Resp(body)

    monkeypatch.setattr(serper_people.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(serper_people, "require_key", lambda name: "test-key")


def _query(**overrides) -> SourceQuery:
    base = dict(
        role_id="role1_senior_structural_engineer",
        niche="structural",
        terms=["senior structural engineer"],
        locations=["Cork"],
        limit=100,
    )
    base.update(overrides)
    return SourceQuery(**base)


# ---------------------------------------------------------------------------
# title/snippet mapping
# ---------------------------------------------------------------------------


def test_full_title_dash_dash_shape_reads_name_title_employer():
    full_name, title, employer = serper_people._parse_title(
        "Aoife Example - Senior Structural Engineer - DBFL | LinkedIn"
    )
    assert full_name == "Aoife Example"
    assert title == "Senior Structural Engineer"
    assert employer == "DBFL"


def test_en_dash_title_at_employer_shape():
    full_name, title, employer = serper_people._parse_title(
        "Cian Example – Associate Director at Arup"
    )
    assert full_name == "Cian Example"
    assert title == "Associate Director"
    assert employer == "Arup"


def test_bare_name_only_title_has_no_title_or_employer():
    full_name, title, employer = serper_people._parse_title("Niamh Example | LinkedIn")
    assert full_name == "Niamh Example"
    assert title is None
    assert employer is None


def test_an_unparseable_title_still_yields_no_blank_record():
    full_name, title, employer = serper_people._parse_title("")
    assert full_name == ""


# ---------------------------------------------------------------------------
# location parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("Location: Cork · 500+ connections", ("Cork", "IE")),
        ("County Kerry · 8 years experience", ("Kerry", "IE")),
        ("Dublin, Ireland · Structural Engineer", ("Dublin", "IE")),
        ("Ireland · Structural Engineer", (None, "IE")),
        ("Manchester, United Kingdom · Structural Engineer", (None, None)),
        ("", (None, None)),
    ],
)
def test_location_parsing(snippet, expected):
    assert serper_people._parse_location(snippet) == expected


# ---------------------------------------------------------------------------
# fetch() end to end against the fixture
# ---------------------------------------------------------------------------


def test_fetch_maps_every_unique_profile_and_drops_non_profile_links(monkeypatch):
    _serper(monkeypatch, _fixture())
    result = serper_people.SerperPeopleProvider().fetch(_query())

    assert result.error is None
    assert result.cost_eur == 0.0
    links = {r.external_id for r in result.provider_records}
    # the company page and the duplicate (query-string) profile are excluded
    assert "https://ie.linkedin.com/company/sample-engineers" not in links
    assert len(links) == len(result.provider_records), "external_id must de-dup"
    # aoife's profile appears once despite being returned twice (plain + ?trk=)
    aoife = [r for r in result.provider_records if r.full_name == "Aoife Example"]
    assert len(aoife) == 1
    assert aoife[0].external_id == "https://ie.linkedin.com/in/aoife-example-12345"
    assert aoife[0].current_title == "Senior Structural Engineer"
    assert aoife[0].current_employer == "DBFL"
    assert aoife[0].city == "Cork"
    assert aoife[0].country == "IE"
    assert aoife[0].linkedin_url == aoife[0].external_id


def test_fetch_emits_one_raw_document_per_record_with_the_exact_quote_shape(monkeypatch):
    _serper(monkeypatch, _fixture())
    result = serper_people.SerperPeopleProvider().fetch(_query())

    assert len(result.documents) == len(result.provider_records)
    aoife_doc = next(d for d in result.documents if "aoife-example" in str(d.url))
    expected = (
        "title: Aoife Example - Senior Structural Engineer - DBFL | LinkedIn\n"
        "snippet: Location: Cork · 500+ connections · "
        "Experience: DBFL Consulting Engineers\n"
        "url: https://ie.linkedin.com/in/aoife-example-12345"
    )
    assert aoife_doc.content_text == expected


def test_num_is_always_ten_regardless_of_query_limit(monkeypatch):
    sent = []
    _serper(monkeypatch, _fixture(), requests_out=sent)
    serper_people.SerperPeopleProvider().fetch(_query(limit=3))

    assert sent, "no request was captured"
    assert all(body["num"] == 10 for body in sent)
    assert all(body["gl"] == "ie" and body["hl"] == "en" for body in sent)


def test_three_query_variants_run_per_term_and_location(monkeypatch):
    sent = []
    _serper(monkeypatch, _fixture(), requests_out=sent)
    serper_people.SerperPeopleProvider().fetch(
        _query(terms=["senior structural engineer"], locations=["Cork", "Dublin"])
    )

    # 1 term x 2 locations x 3 variants (base, CEng/MIEI, Chartered Engineer)
    assert len(sent) == 6
    queries = {body["q"] for body in sent}
    assert any("CEng" in q for q in queries)
    assert any("Chartered Engineer" in q for q in queries)


def test_result_is_truncated_to_the_query_limit(monkeypatch):
    _serper(monkeypatch, _fixture())
    result = serper_people.SerperPeopleProvider().fetch(_query(limit=1))
    assert len(result.provider_records) == 1
    assert len(result.documents) == 1


def test_missing_key_raises_provider_not_configured(monkeypatch):
    # Force secret() to see SERPER_API_KEY as absent regardless of the real
    # environment/.env -- required=False -> "" is the "absent" contract
    # require_key relies on (same pattern as test_licensed_providers.py).
    def _no_secret(name, required=True):
        if name == "SERPER_API_KEY":
            return ""
        return "irrelevant"

    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.config.secret", _no_secret
    )
    with pytest.raises(ProviderNotConfigured):
        serper_people.SerperPeopleProvider().fetch(_query())


def test_an_http_400_on_every_query_surfaces_as_a_result_error(monkeypatch):
    monkeypatch.setattr(serper_people, "require_key", lambda name: "test-key")

    def fake_urlopen(req, timeout=None):
        import urllib.error

        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)

    monkeypatch.setattr(serper_people.urllib.request, "urlopen", fake_urlopen)

    result = serper_people.SerperPeopleProvider().fetch(_query())
    assert result.error is not None
    assert "400" in result.error
    assert result.provider_records == []
    assert result.documents == []


def test_throttle_is_invoked_between_queries(monkeypatch):
    calls = []
    monkeypatch.setattr(
        serper_people, "throttle", lambda key, rate: calls.append((key, rate))
    )
    _serper(monkeypatch, _fixture())
    serper_people.SerperPeopleProvider().fetch(_query())

    assert calls, "throttle() was never called"
    assert all(key == "serper_people" for key, _ in calls)
    assert all(rate >= 1.0 for _, rate in calls)


def test_never_fetches_a_linkedin_page_directly():
    # discovery-only guardrail, verified structurally: the module's only
    # network call target is Serper's own API host.
    import inspect

    src = inspect.getsource(serper_people)
    assert "google.serper.dev" in src
    # every literal "linkedin.com" occurrence is inside a query string, a
    # regex, or a comment/docstring -- never a URL this module fetches.
    assert "fetch(\"https://" not in src
    assert "fetch_raw(" not in src
