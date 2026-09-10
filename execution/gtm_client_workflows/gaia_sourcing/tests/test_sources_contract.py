"""
Contract tests for RADAR_CONTRACTS.md section A: sources/base.py,
sources/registry.py, sources/engineers_ireland.py, sources/istructe.py,
sources/ice.py, sources/registers.py.

No network. Every fixture under tests/fixtures/registers/ is either a real
page this build actually fetched (documented in the corresponding plugin's
module docstring) or explicitly labelled SYNTHETIC (see
synthetic_register_row.txt) -- this file never treats the two as the same
kind of evidence.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pytest

from gtm_client_workflows.gaia_sourcing.core.contracts import (
    Person,
    ProviderRecord,
    RawDocument,
    SourceQuery,
    SourceResult,
)
from gtm_client_workflows.gaia_sourcing.sources import (
    engineers_ireland,
    ice,
    istructe,
    registers,
    registry,
)
from gtm_client_workflows.gaia_sourcing.sources.base import FixtureProvider, SourceProvider

FIXTURES = Path(__file__).parent / "fixtures" / "registers"


def _rawdoc(text: str, url: str, source_type: str = "professional_body") -> RawDocument:
    return RawDocument(
        doc_id="d-" + str(abs(hash(text)) % 10_000_000),
        url=url,
        source_type=source_type,
        fetched_at=date(2026, 9, 10),
        content_text=text,
        http_status=200,
    )


# ===========================================================================
# Fixture -> RawDocument mapping
# ===========================================================================


def test_the_engineers_ireland_fixture_is_the_real_static_landing_page():
    """The real, robots-allowed page this plugin actually fetches. No search
    results on it -- see sources/engineers_ireland.py's module docstring for
    why lookup_person is honest about that."""
    text = (FIXTURES / "engineers_ireland_find_a_member.txt").read_text(encoding="utf-8")

    assert "Find a member" in text
    assert "GDPR" in text
    # No member names on this page -- confirms it is the landing page, not a
    # results page (which this plugin was never able to reach).
    assert "CEng" not in text


def test_a_fixture_loads_into_a_valid_rawdocument():
    text = (FIXTURES / "engineers_ireland_find_a_member.txt").read_text(encoding="utf-8")
    doc = _rawdoc(text, "https://www.engineersireland.ie/Professionals/Membership/Members/Find-a-member",
                  source_type="engineers_ireland_register")

    assert doc.content_text == text
    assert doc.source_type == "engineers_ireland_register"


@pytest.mark.parametrize("filename", [
    "istructe_directory_cloudflare_challenge.html",
    "ice_directory_cloudflare_challenge.html",
])
def test_the_cloudflare_fixtures_are_the_real_blocked_response(filename):
    """These are what a plain fetch of the IStructE / ICE directory actually
    returned live on 2026-09-10 -- a Cloudflare bot-challenge page, not a
    directory listing. Recorded as the real evidence for why those two
    plugins route through fetch_rendered rather than core.cache.fetch."""
    text = (FIXTURES / filename).read_text(encoding="utf-8")

    assert len(text.encode("utf-8")) <= 30_000
    assert "cloudflare" in text.lower() or "challenge" in text.lower()


# ===========================================================================
# registers.py -- name-matching and the claim emitter
# ===========================================================================


def test_a_person_named_in_the_same_line_is_matched():
    text = (FIXTURES / "synthetic_register_row.txt").read_text(encoding="utf-8")

    fragment = registers.fragment_with_both_names(text, "Jane", "Testperson")

    assert fragment is not None
    assert "Jane Testperson" in fragment
    assert "CEng MIEI" in fragment


def test_a_different_persons_row_is_not_matched():
    text = (FIXTURES / "synthetic_register_row.txt").read_text(encoding="utf-8")

    assert registers.fragment_with_both_names(text, "Jane", "Otherperson") is None


def test_the_real_landing_page_matches_nobody():
    """Confirms the honest-degrade claim in engineers_ireland.py's docstring:
    the real page has no member listing, so no name lookup succeeds against it."""
    text = (FIXTURES / "engineers_ireland_find_a_member.txt").read_text(encoding="utf-8")

    assert registers.fragment_with_both_names(text, "Jane", "Testperson") is None


def test_a_claim_is_emitted_only_when_both_names_co_occur():
    text = (FIXTURES / "synthetic_register_row.txt").read_text(encoding="utf-8")
    doc = _rawdoc(text, "https://example.org/directory")
    person = Person(person_id="p1", full_name="Jane Testperson")

    claims = registers.claims_from_register_doc(doc, person)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.dimension == "chartership"
    assert claim.confidence == "direct"
    assert "Jane Testperson" in claim.evidence_quote
    assert claim.source_doc_id == doc.doc_id


def test_no_claim_when_the_person_is_not_in_the_document():
    text = (FIXTURES / "synthetic_register_row.txt").read_text(encoding="utf-8")
    doc = _rawdoc(text, "https://example.org/directory")
    person = Person(person_id="p9", full_name="Someone Else")

    assert registers.claims_from_register_doc(doc, person) == []


def test_a_single_word_name_never_emits_a_claim():
    """A surname-only or forename-only 'name' can never be verified as a
    specific person -- claims_from_register_doc must refuse it outright."""
    text = (FIXTURES / "synthetic_register_row.txt").read_text(encoding="utf-8")
    doc = _rawdoc(text, "https://example.org/directory")
    person = Person(person_id="p1", full_name="Jane")

    assert registers.claims_from_register_doc(doc, person) == []


# ===========================================================================
# robots.txt gate
# ===========================================================================


def test_path_allowed_by_robots_respects_disallow_prefixes():
    assert registers.path_allowed_by_robots("/find-an-engineer/members-directory/", [
        "/my-account/", "/checkout/",
    ]) is True
    assert registers.path_allowed_by_robots("/checkout/basket", [
        "/my-account/", "/checkout/",
    ]) is False


def test_an_empty_disallow_list_allows_everything():
    """ICE's generic User-agent group is a blanket Allow: / -- verified live
    2026-09-10 -- so its plugin carries no disallow prefixes at all."""
    assert registers.path_allowed_by_robots("/anything/at/all", []) is True


@pytest.mark.parametrize("module,provider_cls,path_attr", [
    (engineers_ireland, engineers_ireland.EngineersIrelandProvider, "LANDING_PATH"),
    (istructe, istructe.IStructEProvider, "DIRECTORY_PATH"),
    (ice, ice.ICEProvider, "DIRECTORY_PATH"),
])
def test_a_disallowed_path_yields_an_empty_result_and_a_log_line(
    monkeypatch, capsys, module, provider_cls, path_attr
):
    """If robots.txt ever disallows the path this plugin reads, fetch() must
    degrade to an empty SourceResult and say so -- never scrape anyway."""
    monkeypatch.setattr(module, "path_allowed_by_robots", lambda *a, **kw: False)
    provider = provider_cls()

    result = provider.fetch(SourceQuery(role_id="r1", niche="structural", terms=["Jane Testperson"]))

    assert result == SourceResult(provider=provider.name, documents=[], fetched=0)
    out = capsys.readouterr().out
    assert "blocked_by_robots=True" in out
    assert getattr(module, path_attr) in out


# ===========================================================================
# lookup_person -- honest degrade, never a fabricated match
# ===========================================================================


@pytest.mark.parametrize("module,fetch_fn_name", [
    (engineers_ireland, "fetch"),
    (istructe, "fetch_rendered"),
    (ice, "fetch_rendered"),
])
def test_lookup_person_returns_none_when_the_page_has_no_match(monkeypatch, module, fetch_fn_name):
    text = (FIXTURES / "engineers_ireland_find_a_member.txt").read_text(encoding="utf-8")
    doc = _rawdoc(text, "https://example.org/x")
    monkeypatch.setattr(module, fetch_fn_name, lambda *a, **kw: doc)

    assert module.lookup_person("Jane Testperson") is None


@pytest.mark.parametrize("module,fetch_fn_name", [
    (engineers_ireland, "fetch"),
    (istructe, "fetch_rendered"),
    (ice, "fetch_rendered"),
])
def test_lookup_person_returns_the_document_when_both_names_co_occur(monkeypatch, module, fetch_fn_name):
    text = (FIXTURES / "synthetic_register_row.txt").read_text(encoding="utf-8")
    doc = _rawdoc(text, "https://example.org/x")
    monkeypatch.setattr(module, fetch_fn_name, lambda *a, **kw: doc)

    found = module.lookup_person("Jane Testperson")

    assert found is doc


@pytest.mark.parametrize("module,fetch_fn_name", [
    (engineers_ireland, "fetch"),
    (istructe, "fetch_rendered"),
    (ice, "fetch_rendered"),
])
def test_lookup_person_degrades_when_the_page_is_unreachable(monkeypatch, capsys, module, fetch_fn_name):
    monkeypatch.setattr(module, fetch_fn_name, lambda *a, **kw: None)

    assert module.lookup_person("Jane Testperson") is None
    assert "unreachable" in capsys.readouterr().out


@pytest.mark.parametrize("module", [engineers_ireland, istructe, ice])
def test_lookup_person_refuses_a_single_word_name(module):
    """Never even attempts a fetch for a name that cannot possibly be
    verified as a specific person -- a one-word 'name' matches everyone."""
    assert module.lookup_person("Madonna") is None


# ===========================================================================
# Rate limiting -- monkeypatched time, per RADAR_CONTRACTS.md's
# rate_limit_s >= 2.0 floor
# ===========================================================================


@pytest.mark.parametrize("module,provider_cls", [
    (engineers_ireland, engineers_ireland.EngineersIrelandProvider),
    (istructe, istructe.IStructEProvider),
    (ice, ice.ICEProvider),
])
def test_the_declared_rate_limit_meets_the_floor(module, provider_cls):
    assert provider_cls().rate_limit_s >= 2.0


def test_the_throttle_sleeps_for_the_remaining_window(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(engineers_ireland.time, "monotonic", lambda: clock[0])
    sleeps: list[float] = []
    monkeypatch.setattr(engineers_ireland.time, "sleep", lambda s: sleeps.append(s))
    engineers_ireland._last_hit = 0.0

    engineers_ireland._throttle(3.0)  # first call: no prior hit this run -> big wait clamped by clock
    clock[0] = 101.0  # 1s later, still inside the 3s window
    engineers_ireland._throttle(3.0)

    assert sleeps[-1] == pytest.approx(2.0, abs=0.01)


def test_the_throttle_does_not_sleep_once_the_window_has_passed(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(engineers_ireland.time, "monotonic", lambda: clock[0])
    sleeps: list[float] = []
    monkeypatch.setattr(engineers_ireland.time, "sleep", lambda s: sleeps.append(s))
    engineers_ireland._last_hit = 100.0

    clock[0] = 105.0  # well past the 3s window
    engineers_ireland._throttle(3.0)

    assert sleeps == []


# ===========================================================================
# Registry
# ===========================================================================


def test_the_three_register_providers_are_registered():
    for name in ("engineers_ireland", "istructe", "ice"):
        provider = registry.get_provider(name)
        assert isinstance(provider, SourceProvider)
        assert provider.name == name


def test_get_provider_raises_a_clear_error_for_an_unknown_name():
    # Not "pdl"/"crustdata"/"apollo": those are licensed providers built and
    # registered separately, and may or may not be registered by the time
    # this suite runs alongside that build -- this name is guaranteed unused.
    with pytest.raises(KeyError, match="__definitely_unregistered__"):
        registry.get_provider("__definitely_unregistered__")


def test_register_provider_adds_to_the_dict_without_clobbering_existing_entries():
    before = dict(registry.PROVIDERS)
    fixture = FixtureProvider(name="__test_only__")

    registry.register_provider(fixture)

    try:
        assert registry.get_provider("__test_only__") is fixture
        for name in before:
            assert name in registry.PROVIDERS
    finally:
        del registry.PROVIDERS["__test_only__"]


# ===========================================================================
# FixtureProvider round-trip
# ===========================================================================


def test_fixture_provider_round_trips_documents_and_records():
    doc = _rawdoc("Jane Testperson, CEng MIEI.", "https://example.org/x")
    record = ProviderRecord(
        provider="fixture", external_id="ext-1", full_name="Jane Testperson",
        fetched_at=date(2026, 9, 10), raw_hash="abc123",
    )
    provider = FixtureProvider(name="fx", documents=[doc], provider_records=[record],
                                rate_limit_s=0.0, cost_per_doc_eur=0.01)

    result = provider.fetch(SourceQuery(role_id="r1", niche="structural", limit=100))

    assert result.provider == "fx"
    assert result.documents == [doc]
    assert result.provider_records == [record]
    assert result.fetched == 2
    assert provider.cost_eur(result) == pytest.approx(0.02)


def test_fixture_provider_respects_the_query_limit():
    docs = [_rawdoc(f"person {i}", f"https://example.org/{i}") for i in range(5)]
    provider = FixtureProvider(name="fx", documents=docs)

    result = provider.fetch(SourceQuery(role_id="r1", niche="structural", limit=2))

    assert len(result.documents) == 2


def test_fixture_provider_conforms_to_the_source_provider_protocol():
    provider = FixtureProvider(name="fx")
    assert isinstance(provider, SourceProvider)
