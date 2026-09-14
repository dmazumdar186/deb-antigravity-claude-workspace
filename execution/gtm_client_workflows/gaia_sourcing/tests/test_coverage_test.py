"""
run.py's `run_coverage_test` -- the go/no-go check against a licensed source
provider's real API (RADAR_CONTRACTS.md section A). Before this fix, a
provider returning a non-200 (bad/expired key, wrong plan) produced a
SourceResult with fetched=0 and no way to tell that apart from "the query
genuinely matched nobody" -- so it printed a false "NO-GO: 0/50" and exited
0, which reads as "this niche has no candidates" rather than "the call
failed". Also covers the placeholder-cost label (every licensed provider's
cost_eur rests on an UNVERIFIED per-record rate).

`run_coverage_test` imports the provider module lazily (`import importlib;
importlib.import_module(module_path)`) purely for its self-registration side
effect, then looks the provider up via sources.registry.get_provider. These
tests monkeypatch `importlib.import_module` to register a fake provider
instead of importing the real, network-backed pdl/crustdata/apollo modules.
"""

from __future__ import annotations

import types

import pytest

from gtm_client_workflows.gaia_sourcing import run as R
from gtm_client_workflows.gaia_sourcing.core.contracts import SourceResult
from gtm_client_workflows.gaia_sourcing.sources.licensed_common import ProviderNotConfigured
from gtm_client_workflows.gaia_sourcing.sources import registry


class _FakeProvider:
    name = "pdl"

    def __init__(self, result: SourceResult):
        self._result = result

    def fetch(self, query):
        return self._result


class _RaisingProvider:
    name = "pdl"

    def __init__(self, exc: Exception):
        self._exc = exc

    def fetch(self, query):
        raise self._exc


@pytest.fixture
def register_fake_pdl(monkeypatch):
    """Returns a function: call it with a provider instance to have
    run_coverage_test("pdl", ...) find that provider, without importing the
    real sources/pdl.py module."""

    def _do(provider) -> None:
        def _fake_import_module(name):
            registry.register_provider(provider)
            return types.ModuleType(name)

        monkeypatch.setattr("importlib.import_module", _fake_import_module)

    return _do


def test_non_200_error_is_surfaced_and_exits_non_zero(register_fake_pdl, capsys):
    register_fake_pdl(_FakeProvider(SourceResult(provider="pdl", fetched=0, error="HTTP 401")))

    rc = R.run_coverage_test("pdl", "structural")

    out = capsys.readouterr().out
    assert rc == 1
    assert "HTTP 401" in out
    assert "NO-GO" not in out


def test_go_no_go_still_works_when_there_is_no_error(register_fake_pdl, capsys):
    register_fake_pdl(_FakeProvider(SourceResult(provider="pdl", fetched=0, error=None)))

    rc = R.run_coverage_test("pdl", "structural")

    out = capsys.readouterr().out
    assert rc == 0
    assert "NO-GO" in out


def test_cost_is_labelled_as_a_placeholder_estimate(register_fake_pdl, capsys):
    register_fake_pdl(
        _FakeProvider(SourceResult(provider="pdl", fetched=0, cost_eur=1.2345, error=None))
    )

    R.run_coverage_test("pdl", "structural")

    out = capsys.readouterr().out
    assert "(estimated, placeholder rate)" in out


def test_unknown_provider_returns_error():
    assert R.run_coverage_test("not_a_real_provider", "structural") == 1


def test_provider_not_configured_is_reported_not_raised(register_fake_pdl, capsys):
    register_fake_pdl(_RaisingProvider(ProviderNotConfigured("PDL_API_KEY is not set")))

    rc = R.run_coverage_test("pdl", "structural")

    assert rc == 1
    assert "PDL_API_KEY" in capsys.readouterr().out
