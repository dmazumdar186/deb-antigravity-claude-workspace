"""
The three licensed-data providers -- sources/pdl.py, sources/crustdata.py,
sources/apollo.py -- against RADAR_CONTRACTS.md section A.

Every test here is a contract test: given a recorded provider response
(tests/fixtures/<provider>/search_response.json, copied verbatim from each
provider's own published docs example -- PDL's "sean thorne" sample id,
Crustdata's "Dipesh Garg" sample, Apollo's "Jordan Blake" sample -- so no
test asserts anything about an invented person), does `fetch()` map it into
the exact ProviderRecord/RawDocument shape RADAR_CONTRACTS.md section A
promises: title/employer/city/dates preserved, cost_eur computed from
`fetched`, next_cursor carried through, and a missing API key raising
ProviderNotConfigured rather than a silently-empty SourceResult.

Provenance note on the PDL fixture specifically: PDL's own quickstart page
gives only an id + full_name for its example record (a Mexico/healthcare
search unrelated to this pipeline's Ireland/engineering domain). The
surrounding job_title/job_company_name/experience/location/skills fields in
tests/fixtures/pdl/search_response.json are synthetic test data built to
exercise an Ireland-structural-engineer shaped record -- they are not
attributed to a real person, only the docs' own sample id/name are reused.
The Crustdata and Apollo fixtures are the providers' documented example
payloads verbatim.

Nothing here touches the network: `_post_json` is monkeypatched to return a
fixture, never `requests` itself.

FALLBACK STUB, per this package's build instructions: sources/base.py,
sources/registry.py and the SourceQuery/SourceResult/ProviderRecord/JobStint
models in core/contracts.py are owned by a parallel build. If a checkout of
this test runs before that build has landed, the imports below fail; the
`_stub_missing_contracts()` call installs a minimal, spec-shaped stand-in
directly into sys.modules (never into the actual package files) so this
provider build's own logic can still be verified in isolation. When the real
modules are present (the normal case), this is a no-op.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(provider: str) -> dict:
    return json.loads((FIXTURES / provider / "search_response.json").read_text(encoding="utf-8"))


def _stub_missing_contracts() -> None:
    """Install sys.modules stand-ins for sources.base / sources.registry /
    the licensed-provider pieces of core.contracts, ONLY if the real ones
    are not importable. Never writes to any file in the package -- see the
    module docstring's FALLBACK STUB note and this package's build
    instructions ("if they are not present when you run tests, create a
    minimal local stub ONLY inside your test module via monkeypatch/
    sys.modules, never in the package").
    """
    try:
        import gtm_client_workflows.gaia_sourcing.sources.base  # noqa: F401
        import gtm_client_workflows.gaia_sourcing.sources.registry  # noqa: F401
        from gtm_client_workflows.gaia_sourcing.core.contracts import (  # noqa: F401
            JobStint,
            ProviderRecord,
            SourceQuery,
            SourceResult,
        )
        return  # the real thing is present; nothing to stub
    except ImportError:
        pass

    import dataclasses
    from datetime import date
    from typing import Optional

    contracts_mod = sys.modules.get("gtm_client_workflows.gaia_sourcing.core.contracts")
    if contracts_mod is None:
        import gtm_client_workflows.gaia_sourcing.core.contracts as contracts_mod  # noqa: F401

    @dataclasses.dataclass
    class JobStint:
        title: Optional[str] = None
        employer: Optional[str] = None
        start: Optional[date] = None
        end: Optional[date] = None

    @dataclasses.dataclass
    class SourceQuery:
        role_id: str
        niche: str
        terms: list = dataclasses.field(default_factory=list)
        locations: list = dataclasses.field(default_factory=list)
        limit: int = 100
        cursor: Optional[str] = None

    @dataclasses.dataclass
    class ProviderRecord:
        provider: str
        external_id: str
        full_name: str
        current_title: Optional[str] = None
        current_employer: Optional[str] = None
        city: Optional[str] = None
        region: Optional[str] = None
        country: Optional[str] = None
        job_history: list = dataclasses.field(default_factory=list)
        skills: list = dataclasses.field(default_factory=list)
        linkedin_url: Optional[str] = None
        fetched_at: Optional[date] = None
        raw_hash: str = ""

    @dataclasses.dataclass
    class SourceResult:
        provider: str
        documents: list = dataclasses.field(default_factory=list)
        provider_records: list = dataclasses.field(default_factory=list)
        next_cursor: Optional[str] = None
        cost_eur: float = 0.0
        fetched: int = 0

    for name, obj in (
        ("JobStint", JobStint), ("SourceQuery", SourceQuery),
        ("ProviderRecord", ProviderRecord), ("SourceResult", SourceResult),
    ):
        setattr(contracts_mod, name, obj)

    base_mod = types.ModuleType("gtm_client_workflows.gaia_sourcing.sources.base")

    class SourceProvider:  # Protocol stand-in
        pass

    base_mod.SourceProvider = SourceProvider
    sys.modules["gtm_client_workflows.gaia_sourcing.sources.base"] = base_mod

    registry_mod = types.ModuleType("gtm_client_workflows.gaia_sourcing.sources.registry")
    registry_mod.PROVIDERS = {}

    def register_provider(provider) -> None:
        registry_mod.PROVIDERS[provider.name] = provider

    def get_provider(name: str):
        return registry_mod.PROVIDERS[name]

    registry_mod.register_provider = register_provider
    registry_mod.get_provider = get_provider
    sys.modules["gtm_client_workflows.gaia_sourcing.sources.registry"] = registry_mod


_stub_missing_contracts()

from gtm_client_workflows.gaia_sourcing.sources import apollo, crustdata, licensed_common, pdl  # noqa: E402
from gtm_client_workflows.gaia_sourcing.sources import base as _sources_base  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_throttle_sleep(monkeypatch):
    """Every fetch() now calls the shared sources.base.throttle before its
    POST, honouring each provider's real rate_limit_s (6.0s for PDL). Fine
    in production; without this fixture it would make this test file take
    minutes, since sources.base._THROTTLE_LAST persists across tests within
    one process. Neuters the actual sleep only -- the call itself (which
    test_fetch_calls_the_shared_throttle checks for) is unaffected.
    """
    monkeypatch.setattr(_sources_base.time, "sleep", lambda *_: None)
    monkeypatch.setattr(_sources_base, "_THROTTLE_LAST", {})


try:
    from gtm_client_workflows.gaia_sourcing.core.contracts import SourceQuery  # noqa: E402
except ImportError:  # pragma: no cover -- stub installed it on sys.modules instead
    from gtm_client_workflows.gaia_sourcing.core import contracts as _contracts_mod  # noqa: E402
    SourceQuery = _contracts_mod.SourceQuery


def _query(**overrides) -> "SourceQuery":
    base = dict(
        role_id="role2",
        niche="structural",
        terms=["chartered engineer", "structural"],
        locations=["Dublin", "Cork"],
        limit=50,
    )
    base.update(overrides)
    return SourceQuery(**base)


# ===========================================================================
# Missing-key behaviour -- every provider must raise ProviderNotConfigured,
# never return a silent empty SourceResult.
# ===========================================================================


@pytest.mark.parametrize(
    "provider_mod, cls, env_name",
    [
        (pdl, "PDLProvider", "PDL_API_KEY"),
        (crustdata, "CrustdataProvider", "CRUSTDATA_API_KEY"),
        (apollo, "ApolloProvider", "APOLLO_API_KEY"),
    ],
)
def test_missing_key_raises_provider_not_configured(monkeypatch, provider_mod, cls, env_name):
    # Force secret() to see the key as absent regardless of the real
    # environment/.env -- required=False -> "" is the "absent" contract
    # require_key relies on.
    def _no_secret(name, required=True):
        if name == env_name:
            return ""
        return "irrelevant"

    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.config.secret", _no_secret
    )
    provider = getattr(provider_mod, cls)()
    with pytest.raises(licensed_common.ProviderNotConfigured):
        provider.fetch(_query())


# ===========================================================================
# PDL
# ===========================================================================


@pytest.fixture
def _pdl_key(monkeypatch):
    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.config.secret",
        lambda name, required=True: "test-pdl-key" if name == "PDL_API_KEY" else "",
    )


def test_pdl_mapping(monkeypatch, _pdl_key):
    fixture = _load_fixture("pdl")
    monkeypatch.setattr(pdl, "_post_json", lambda *a, **k: (200, fixture))

    result = pdl.PDLProvider().fetch(_query())

    assert result.provider == "pdl"
    assert result.fetched == 1
    assert len(result.provider_records) == 1
    assert len(result.documents) == 1

    rec = result.provider_records[0]
    assert rec.provider == "pdl"
    assert rec.external_id == "qEnOZ5Oh0poWnQ1luFBfVw_0000"
    assert rec.full_name == "sean thorne"
    assert rec.current_title == "chartered structural engineer"
    assert rec.current_employer == "roughan & o'donovan"
    assert rec.city == "dublin"
    assert rec.region == "county dublin"
    assert rec.country == "ireland"
    assert rec.linkedin_url == "https://linkedin.com/in/sean-thorne"
    assert len(rec.job_history) == 2
    first = rec.job_history[0]
    assert first.title == "Chartered Structural Engineer"
    assert first.employer == "Roughan & O'Donovan"
    assert str(first.start) == "2019-03-01"
    assert first.end is None
    second = rec.job_history[1]
    assert str(second.start) == "2015-06-01"
    assert str(second.end) == "2019-02-01"

    doc = result.documents[0]
    assert "full_name: sean thorne" in doc.content_text
    assert "current_title: chartered structural engineer" in doc.content_text
    assert "job_history[0]: Chartered Structural Engineer at Roughan & O'Donovan" in doc.content_text
    assert doc.source_type == "other"

    assert result.next_cursor == "1117$12.176522"


def test_pdl_cost_eur(monkeypatch, _pdl_key):
    fixture = _load_fixture("pdl")
    monkeypatch.setattr(pdl, "_post_json", lambda *a, **k: (200, fixture))
    result = pdl.PDLProvider().fetch(_query())
    from gtm_client_workflows.gaia_sourcing.core.config import USD_TO_EUR

    expected = 1 * pdl._SEARCH_COST_USD_PER_RECORD * USD_TO_EUR
    assert result.cost_eur == pytest.approx(expected)
    assert result.cost_eur > 0


def test_pdl_pagination_cursor_roundtrip(monkeypatch, _pdl_key):
    fixture = _load_fixture("pdl")
    captured = {}

    def fake_post(url, headers, json_body, timeout=None):
        captured["body"] = json_body
        return 200, fixture

    monkeypatch.setattr(pdl, "_post_json", fake_post)
    pdl.PDLProvider().fetch(_query(cursor="prev-scroll-token"))
    assert captured["body"]["scroll_token"] == "prev-scroll-token"


def test_pdl_non_200_returns_empty_result(monkeypatch, _pdl_key):
    monkeypatch.setattr(pdl, "_post_json", lambda *a, **k: (429, {}))
    result = pdl.PDLProvider().fetch(_query())
    assert result.fetched == 0
    assert result.documents == []
    assert result.provider_records == []
    assert result.cost_eur == 0.0
    assert result.error == "HTTP 429"


# ===========================================================================
# Crustdata
# ===========================================================================


@pytest.fixture
def _crustdata_key(monkeypatch):
    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.config.secret",
        lambda name, required=True: "test-crustdata-key" if name == "CRUSTDATA_API_KEY" else "",
    )


def test_crustdata_mapping(monkeypatch, _crustdata_key):
    fixture = _load_fixture("crustdata")
    monkeypatch.setattr(crustdata, "_post_json", lambda *a, **k: (200, fixture))

    result = crustdata.CrustdataProvider().fetch(_query())

    assert result.provider == "crustdata"
    assert result.fetched == 1
    rec = result.provider_records[0]
    assert rec.external_id == "1279"
    assert rec.full_name == "Dipesh Garg"
    assert rec.current_title == "CEO & Founder"
    assert rec.current_employer == "Truelancer.com"
    assert rec.city == "San Francisco"
    assert rec.region == "California"
    assert rec.country == "United States of America"
    assert rec.linkedin_url == "https://www.linkedin.com/in/dipesh-garg"
    assert len(rec.job_history) == 2
    assert rec.job_history[0].title == "CEO & Founder"
    assert rec.job_history[0].employer == "Truelancer.com"
    assert rec.job_history[1].title == "Founder"
    assert rec.job_history[1].employer == "MyRemoteTeam Inc"

    doc = result.documents[0]
    assert doc.url == "https://www.linkedin.com/in/dipesh-garg" or str(doc.url).startswith("https://")
    assert "current_employer: Truelancer.com" in doc.content_text

    assert result.next_cursor == "H4sIAHC-oWkC_xWMMQ7CMAwAv..."


def test_crustdata_cost_eur(monkeypatch, _crustdata_key):
    fixture = _load_fixture("crustdata")
    monkeypatch.setattr(crustdata, "_post_json", lambda *a, **k: (200, fixture))
    result = crustdata.CrustdataProvider().fetch(_query())
    expected = 1 * crustdata._SEARCH_CREDITS_PER_RESULT * crustdata._CREDIT_USD * crustdata.USD_TO_EUR
    assert result.cost_eur == pytest.approx(expected)
    assert result.cost_eur > 0


def test_crustdata_pagination_cursor_roundtrip(monkeypatch, _crustdata_key):
    fixture = _load_fixture("crustdata")
    captured = {}

    def fake_post(url, headers, json_body, timeout=None):
        captured["body"] = json_body
        return 200, fixture

    monkeypatch.setattr(crustdata, "_post_json", fake_post)
    crustdata.CrustdataProvider().fetch(_query(cursor="prev-cursor"))
    assert captured["body"]["cursor"] == "prev-cursor"


def test_crustdata_ireland_filter_present(monkeypatch, _crustdata_key):
    fixture = _load_fixture("crustdata")
    captured = {}

    def fake_post(url, headers, json_body, timeout=None):
        captured["body"] = json_body
        return 200, fixture

    monkeypatch.setattr(crustdata, "_post_json", fake_post)
    crustdata.CrustdataProvider().fetch(_query())
    conditions = captured["body"]["filters"]["conditions"]
    assert {"field": "basic_profile.location.country", "type": "=", "value": "Ireland"} in conditions


def test_crustdata_non_200_returns_empty_result(monkeypatch, _crustdata_key):
    monkeypatch.setattr(crustdata, "_post_json", lambda *a, **k: (500, {}))
    result = crustdata.CrustdataProvider().fetch(_query())
    assert result.fetched == 0
    assert result.cost_eur == 0.0
    assert result.error == "HTTP 500"


# ===========================================================================
# Apollo
# ===========================================================================


@pytest.fixture
def _apollo_key(monkeypatch):
    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.config.secret",
        lambda name, required=True: "test-apollo-key" if name == "APOLLO_API_KEY" else "",
    )


def test_apollo_mapping(monkeypatch, _apollo_key):
    fixture = _load_fixture("apollo")
    monkeypatch.setattr(apollo, "_post_json", lambda *a, **k: (200, fixture))

    result = apollo.ApolloProvider().fetch(_query())

    assert result.provider == "apollo"
    assert result.fetched == 1
    rec = result.provider_records[0]
    assert rec.external_id == "672c91d4a7be42000184f2c9"
    assert rec.full_name == "Jordan Blake"
    assert rec.current_title == "Founder & CEO"
    assert rec.current_employer == "Northstar Analytics"
    assert rec.city == "San Francisco"
    assert rec.region == "California"
    assert rec.country == "United States"
    assert rec.linkedin_url == "http://www.linkedin.com/in/jordan-blake-4a7c21"
    assert len(rec.job_history) == 2
    assert rec.job_history[0].employer == "Northstar Analytics"
    assert str(rec.job_history[0].start) == "2016-01-01"
    assert rec.job_history[0].end is None
    assert rec.job_history[1].employer == "BrightForge Labs"
    assert str(rec.job_history[1].end) == "2015-01-01"

    doc = result.documents[0]
    assert "full_name: Jordan Blake" in doc.content_text


def test_apollo_cost_eur_is_zero_for_bare_search(monkeypatch, _apollo_key):
    """Apollo's documented billing model charges credits only on
    export/reveal, never on a bare search match -- see apollo.py's module
    docstring "ASSUMED" section."""
    fixture = _load_fixture("apollo")
    monkeypatch.setattr(apollo, "_post_json", lambda *a, **k: (200, fixture))
    result = apollo.ApolloProvider().fetch(_query())
    assert result.cost_eur == 0.0


def test_apollo_pagination_next_cursor(monkeypatch, _apollo_key):
    fixture = json.loads(json.dumps(_load_fixture("apollo")))
    fixture["pagination"] = {"page": 1, "per_page": 50, "total_entries": 120, "total_pages": 3}
    monkeypatch.setattr(apollo, "_post_json", lambda *a, **k: (200, fixture))
    result = apollo.ApolloProvider().fetch(_query())
    assert result.next_cursor == "2"


def test_apollo_last_page_has_no_next_cursor(monkeypatch, _apollo_key):
    fixture = _load_fixture("apollo")  # total_pages == 1
    monkeypatch.setattr(apollo, "_post_json", lambda *a, **k: (200, fixture))
    result = apollo.ApolloProvider().fetch(_query())
    assert result.next_cursor is None


def test_apollo_non_200_returns_empty_result(monkeypatch, _apollo_key):
    monkeypatch.setattr(apollo, "_post_json", lambda *a, **k: (403, {}))
    result = apollo.ApolloProvider().fetch(_query())
    assert result.fetched == 0
    assert result.cost_eur == 0.0
    assert result.error == "HTTP 403"


# ===========================================================================
# licensed_common
# ===========================================================================


def test_render_content_text_skips_empty_fields():
    text = licensed_common.render_content_text(
        [("full_name", "Jane Doe"), ("current_title", None), ("skills", []), ("city", "")]
    )
    assert text == "full_name: Jane Doe"


def test_parse_date_handles_partial_precision():
    assert str(licensed_common.parse_date("2019-03-15")) == "2019-03-15"
    assert str(licensed_common.parse_date("2019-03")) == "2019-03-01"
    assert str(licensed_common.parse_date("2019")) == "2019-01-01"
    assert licensed_common.parse_date(None) is None
    assert licensed_common.parse_date("") is None


def test_no_network_module_only_uses_requests_inside_post_json():
    """Guard against a future edit reintroducing a direct requests.get/post
    call anywhere in these three provider modules outside licensed_common's
    one sanctioned _post_json -- see licensed_common.py's grep-allowlist
    comment."""
    import inspect
    import re

    for mod in (pdl, crustdata, apollo):
        src = inspect.getsource(mod)
        assert not re.search(r"requests\.(get|post)\(", src), (
            f"{mod.__name__} calls requests directly; route through "
            "licensed_common._post_json instead"
        )


# ===========================================================================
# _post_json logging (never headers) on non-200/exception, and its returned
# status
# ===========================================================================


class _FakeResp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self.content = b"{}" if body is not None else b""
        self._body = body or {}

    def json(self):
        return self._body


def test_post_json_logs_non_200_status_but_never_the_headers(monkeypatch, capsys):
    monkeypatch.setattr(
        licensed_common.requests, "post",
        lambda *a, **k: _FakeResp(401, {"error": "unauthorized"}),
    )
    secret_headers = {"Authorization": "Bearer super-secret-token-xyz"}
    status, payload = licensed_common._post_json(
        "https://api.example.com/search", secret_headers, {"q": "x"}
    )
    assert status == 401
    out = capsys.readouterr().out
    assert "401" in out
    assert "super-secret-token-xyz" not in out
    assert "Bearer" not in out


def test_post_json_logs_and_returns_zero_on_network_exception(monkeypatch, capsys):
    def _raise(*a, **k):
        raise ConnectionError("boom")

    monkeypatch.setattr(licensed_common.requests, "post", _raise)
    status, payload = licensed_common._post_json(
        "https://api.example.com/search", {"Authorization": "Bearer xyz"}, {}
    )
    assert status == 0
    assert payload == {}
    out = capsys.readouterr().out
    assert "boom" in out
    assert "xyz" not in out


def test_post_json_does_not_log_on_a_200(monkeypatch, capsys):
    monkeypatch.setattr(
        licensed_common.requests, "post", lambda *a, **k: _FakeResp(200, {"ok": True})
    )
    licensed_common._post_json("https://api.example.com/search", {}, {})
    out = capsys.readouterr().out
    assert out == ""


# ===========================================================================
# Shared throttle is actually called from each licensed provider's fetch()
# ===========================================================================


@pytest.mark.parametrize("mod,provider_cls,key,env_name", [
    (pdl, "PDLProvider", "pdl", "PDL_API_KEY"),
    (crustdata, "CrustdataProvider", "crustdata", "CRUSTDATA_API_KEY"),
    (apollo, "ApolloProvider", "apollo", "APOLLO_API_KEY"),
])
def test_fetch_calls_the_shared_throttle(monkeypatch, mod, provider_cls, key, env_name):
    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.config.secret",
        lambda name, required=True: "test-key" if name == env_name else "",
    )
    calls = []
    monkeypatch.setattr(mod, "throttle", lambda k, r: calls.append((k, r)))
    monkeypatch.setattr(mod, "_post_json", lambda *a, **k: (200, {}))

    getattr(mod, provider_cls)().fetch(_query())

    assert calls and calls[0][0] == key
