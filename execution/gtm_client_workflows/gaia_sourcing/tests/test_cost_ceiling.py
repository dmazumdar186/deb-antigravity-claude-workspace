"""
The cost ceiling, which for three sessions did not exist.

RunConfig declared `max_cost_eur = 30.0` with the comment "the run aborts
rather than silently overspending (SPEC.md section 14)". The only thing that
enforced it was a CostTracker in core/llm.py -- a module nothing imported,
superseded by core/providers.py. Every layer dutifully appended its cost
metadata to a RUN_COST list that nothing ever read, so the live path had no
ceiling at all, on a pipeline that makes per-candidate Opus calls across four
stages.

The failure mode this guards against is not a big single call. It is a loop.
"""

from __future__ import annotations

import pytest

from gtm_client_workflows.gaia_sourcing.core import providers
from gtm_client_workflows.gaia_sourcing.core.config import PRICING, USD_TO_EUR


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setattr(providers, "ROUTING", dict(providers.ROUTING))
    monkeypatch.setattr(providers.time, "sleep", lambda *_: None)
    providers.reset_spend()
    yield
    providers.reset_spend()


# ---------------------------------------------------------------------------
# Cache-aware pricing (python-hardening rule 4)
# ---------------------------------------------------------------------------


def test_cache_reads_are_no_longer_free():
    """The Anthropic backend collects cache_read_input_tokens and the cost
    function ignored them, so every cached call understated its own cost.
    Under prompt caching that is most of the input on a long run."""
    stats = {"input_tokens": 0, "output_tokens": 0,
             "cache_read_tokens": 1_000_000, "cache_write_tokens": 0}

    assert providers.cost_eur("claude-opus-5", stats) > 0


def test_cache_writes_are_dearer_than_reads():
    read = providers.cost_eur("claude-opus-5", {"cache_read_tokens": 1_000_000})
    write = providers.cost_eur("claude-opus-5", {"cache_write_tokens": 1_000_000})

    assert write > read


def test_cache_pricing_matches_the_published_ratios():
    """cache_read is 0.1x input and cache_write 1.25x, per the model-tier rule."""
    inp = providers.cost_eur("claude-opus-5", {"input_tokens": 1_000_000})
    read = providers.cost_eur("claude-opus-5", {"cache_read_tokens": 1_000_000})
    write = providers.cost_eur("claude-opus-5", {"cache_write_tokens": 1_000_000})

    assert read == pytest.approx(inp * 0.1, rel=0.05)
    assert write == pytest.approx(inp * 1.25, rel=0.05)


def test_the_eur_table_tracks_the_usd_source_of_truth():
    for model in ("claude-opus-5", "claude-sonnet-5"):
        expected = PRICING[model]["input"] * USD_TO_EUR
        assert providers.PRICE_EUR[model]["input"] == pytest.approx(expected, rel=0.02)


# ---------------------------------------------------------------------------
# The ceiling itself
# ---------------------------------------------------------------------------


def _backend(cost_per_call_tokens: int):
    def fake(model, system, user, tool, max_tokens, temperature):
        return {"ok": True}, {"input_tokens": cost_per_call_tokens,
                              "output_tokens": 0, "cache_read_tokens": 0,
                              "cache_write_tokens": 0}
    return fake


def test_spend_accumulates_across_calls(monkeypatch):
    monkeypatch.setitem(providers._BACKENDS, "gemini", _backend(1_000_000))
    monkeypatch.setattr(providers, "PRICE_EUR",
                        {**providers.PRICE_EUR, "gemini-2.5-flash":
                         {"input": 1.0, "output": 1.0}})
    providers.set_plan("free")

    providers.call_role(providers.ROLE_EXTRACT, "s", "u", {"name": "t"})
    first = providers.spend_eur()
    providers.call_role(providers.ROLE_EXTRACT, "s", "u", {"name": "t"})

    assert first == pytest.approx(1.0)
    assert providers.spend_eur() == pytest.approx(2.0)


def test_the_run_stops_when_the_ceiling_is_crossed(monkeypatch):
    """A runaway loop is the thing this catches, and it is only catchable if
    something sums the per-call costs. Nothing did."""
    monkeypatch.setitem(providers._BACKENDS, "gemini", _backend(1_000_000))
    monkeypatch.setattr(providers, "PRICE_EUR",
                        {**providers.PRICE_EUR, "gemini-2.5-flash":
                         {"input": 20.0, "output": 0.0}})
    providers.set_plan("free")

    providers.call_role(providers.ROLE_EXTRACT, "s", "u", {"name": "t"})  # EUR 20

    with pytest.raises(providers.CostCeilingExceeded, match="exceeds the ceiling"):
        providers.call_role(providers.ROLE_EXTRACT, "s", "u", {"name": "t"})


def test_the_ceiling_breach_is_not_retried(monkeypatch):
    """The generic handler in the retry loop would otherwise sleep and retry a
    budget breach three times, then re-raise it as an ordinary RuntimeError
    that run_all contains per item."""
    calls = {"n": 0}

    def counting(model, system, user, tool, max_tokens, temperature):
        calls["n"] += 1
        return {"ok": True}, {"input_tokens": 1_000_000, "output_tokens": 0}

    monkeypatch.setitem(providers._BACKENDS, "gemini", counting)
    monkeypatch.setattr(providers, "PRICE_EUR",
                        {**providers.PRICE_EUR, "gemini-2.5-flash":
                         {"input": 100.0, "output": 0.0}})
    providers.set_plan("free")

    with pytest.raises(providers.CostCeilingExceeded):
        providers.call_role(providers.ROLE_EXTRACT, "s", "u", {"name": "t"})

    assert calls["n"] == 1, "a budget breach must not be retried"


def test_the_ceiling_message_names_the_figure_and_the_remedy(monkeypatch):
    monkeypatch.setitem(providers._BACKENDS, "gemini", _backend(1_000_000))
    monkeypatch.setattr(providers, "PRICE_EUR",
                        {**providers.PRICE_EUR, "gemini-2.5-flash":
                         {"input": 100.0, "output": 0.0}})
    providers.set_plan("free")

    with pytest.raises(providers.CostCeilingExceeded) as exc:
        providers.call_role(providers.ROLE_EXTRACT, "s", "u", {"name": "t"})

    assert "EUR" in str(exc.value)
    assert "max_cost_eur" in str(exc.value)


def test_every_call_reports_the_running_total(monkeypatch):
    monkeypatch.setitem(providers._BACKENDS, "gemini", _backend(1_000))
    providers.set_plan("free")

    _out, meta = providers.call_role(providers.ROLE_EXTRACT, "s", "u", {"name": "t"})

    assert "run_total_eur" in meta and "cost_eur" in meta


# ---------------------------------------------------------------------------
# run_all must not contain it
# ---------------------------------------------------------------------------


def test_a_budget_breach_escapes_the_per_item_failure_containment(tmp_path,
                                                                 monkeypatch):
    """run_all degrades by one item on an ordinary error. For a ceiling breach
    that would mean burning the rest of the stage one contained failure at a
    time -- the opposite of what a ceiling is for."""
    from gtm_client_workflows.gaia_sourcing import run as R

    monkeypatch.setattr(R, "RUN_DIR", tmp_path)

    def work(n):
        raise providers.CostCeilingExceeded("over budget")

    with pytest.raises(providers.CostCeilingExceeded):
        R.run_all(work, [1, 2, 3, 4, 5], workers=2, label="t")


def test_an_ordinary_failure_is_still_contained(tmp_path, monkeypatch):
    from gtm_client_workflows.gaia_sourcing import run as R

    monkeypatch.setattr(R, "RUN_DIR", tmp_path)
    done = []

    def work(n):
        if n == 3:
            raise ValueError("one bad document")
        done.append(n)

    assert R.run_all(work, [1, 2, 3, 4, 5], workers=2, label="t") == 1
    assert sorted(done) == [1, 2, 4, 5]


def test_the_dead_cost_tracker_module_is_gone():
    """core/llm.py held the only enforcement, imported by nothing, while
    providers.py -- the module actually in the call path -- had none. Two
    pricing implementations, one of them unreachable, is how a declared
    ceiling ends up being decorative."""
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("gtm_client_workflows.gaia_sourcing.core.llm")
