"""
core/providers.py and core/cache.py -- the two modules everything else sits on.

providers.py was at 20% and cache.py at 43%, and between them they own three
properties the pipeline's honesty depends on:

  - a truncated model response is DROPPED, never repaired (a half-parsed claim
    list is how invented data gets in);
  - a fetch that returns 200 but no readable text is a FAILED fetch, not an
    empty document (I9, and the bug that collapsed 51 sources onto one doc_id);
  - cache.normalise_ws and validator.normalize must agree, or every verbatim
    quote fails to match and the whole run drops to zero.

No test here touches the network.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from gtm_client_workflows.gaia_sourcing.core import cache, providers


# ===========================================================================
# providers -- routing, retry, and cost
# ===========================================================================


@pytest.fixture(autouse=True)
def _restore_routing(monkeypatch):
    monkeypatch.setattr(providers, "ROUTING", dict(providers.ROUTING))
    monkeypatch.setattr(providers.time, "sleep", lambda *_: None)


TOOL = {
    "name": "emit",
    "description": "d",
    "input_schema": {
        "type": "object",
        "properties": {
            "tier": {"type": "string", "enum": ["A", "B"]},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"quote": {"type": "string"}},
                    "required": ["quote"],
                },
            },
        },
        "required": ["tier"],
    },
}


def test_gemini_schema_translation_keeps_enums_and_nesting():
    out = providers._to_gemini_schema(TOOL["input_schema"])

    assert out["type"] == "OBJECT"
    assert out["required"] == ["tier"]
    assert out["properties"]["tier"]["enum"] == ["A", "B"]
    assert out["properties"]["claims"]["type"] == "ARRAY"
    assert out["properties"]["claims"]["items"]["properties"]["quote"]["type"] == "STRING"


def test_a_truncated_response_is_dropped_never_repaired(monkeypatch):
    """Hitting maxOutputTokens mid-array yields half a claim list.

    Salvaging what parsed is precisely how an unevidenced assertion enters the
    pipeline, so the whole response is discarded instead.
    """
    monkeypatch.setattr(providers, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(providers, "_post_json", lambda *a, **kw: {
        "candidates": [{"content": {"parts": [{"text": '{"claims": [{"quote": "half'}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 8000},
    })

    out, stats = providers._call_gemini("gemini-2.5-flash", "s", "u", TOOL, 8000, 0.0)

    assert out is None
    assert stats["output_tokens"] == 8000, "the failed call still cost tokens"


def test_an_empty_candidate_list_is_not_an_empty_result(monkeypatch):
    monkeypatch.setattr(providers, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(providers, "_post_json", lambda *a, **kw: {"candidates": []})

    out, _ = providers._call_gemini("gemini-2.5-flash", "s", "u", TOOL, 100, 0.0)
    assert out is None


def test_openrouter_reads_the_forced_tool_call(monkeypatch):
    monkeypatch.setattr(providers, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(providers, "_post_json", lambda *a, **kw: {
        "choices": [{"message": {"tool_calls": [
            {"function": {"name": "emit", "arguments": '{"tier": "A"}'}}
        ]}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
    })

    out, stats = providers._call_openrouter("m", "s", "u", TOOL, 100, 0.0)

    assert out == {"tier": "A"}
    assert stats["input_tokens"] == 12


def test_a_reply_that_answered_a_different_tool_is_discarded(monkeypatch):
    monkeypatch.setattr(providers, "secret", lambda *a, **kw: "k")
    monkeypatch.setattr(providers, "_post_json", lambda *a, **kw: {
        "choices": [{"message": {"tool_calls": [
            {"function": {"name": "something_else", "arguments": '{"tier": "A"}'}}
        ]}}],
    })

    out, _ = providers._call_openrouter("m", "s", "u", TOOL, 100, 0.0)
    assert out is None


def _http_error(code: int, headers: dict | None = None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://x", code, "err", headers or {}, None  # type: ignore[arg-type]
    )


def test_a_rate_limit_is_retried(monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429)
        return {"ok": True}, {"input_tokens": 1, "output_tokens": 1}

    monkeypatch.setitem(providers._BACKENDS, "gemini", flaky)
    providers.set_plan("free")

    out, _ = providers.call_role(providers.ROLE_EXTRACT, "s", "u", TOOL)

    assert out == {"ok": True}
    assert calls["n"] == 2


def test_a_contract_error_is_not_retried_three_times(monkeypatch):
    """A 400 is permanent -- a bad schema or a deprecated parameter. Retrying
    just triples the latency of a failure that will never succeed."""
    calls = {"n": 0}

    def bad_request(*a, **kw):
        calls["n"] += 1
        raise RuntimeError("invalid_request_error: temperature is deprecated")

    monkeypatch.setitem(providers._BACKENDS, "gemini", bad_request)
    providers.set_plan("free")

    with pytest.raises(RuntimeError, match="rejected the request"):
        providers.call_role(providers.ROLE_EXTRACT, "s", "u", TOOL)

    assert calls["n"] == 1


def test_a_non_retryable_http_status_raises_with_the_body(monkeypatch):
    monkeypatch.setitem(
        providers._BACKENDS, "gemini",
        lambda *a, **kw: (_ for _ in ()).throw(_http_error(404)),
    )
    providers.set_plan("free")

    with pytest.raises(RuntimeError, match="HTTP 404"):
        providers.call_role(providers.ROLE_EXTRACT, "s", "u", TOOL)


def test_exhausted_retries_raise_rather_than_return_nothing(monkeypatch):
    """Returning None here would look identical to "the model found nothing"."""
    monkeypatch.setitem(
        providers._BACKENDS, "gemini",
        lambda *a, **kw: (_ for _ in ()).throw(TimeoutError("slow")),
    )
    providers.set_plan("free")

    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        providers.call_role(providers.ROLE_EXTRACT, "s", "u", TOOL, max_retries=3)


def test_a_gemini_rate_limit_widens_the_interval_for_the_rest_of_the_run(monkeypatch):
    """A fixed interval lost 3 of 19 documents on the first real run: retries
    after a 429 stack on top of the normal cadence and re-trip the same limit."""
    monkeypatch.setattr(providers, "_GEMINI_MIN_INTERVAL", 6.5)

    providers._gemini_penalise()

    assert providers._GEMINI_MIN_INTERVAL > 6.5


def test_the_interval_never_widens_without_bound(monkeypatch):
    monkeypatch.setattr(providers, "_GEMINI_MIN_INTERVAL", 29.0)

    for _ in range(10):
        providers._gemini_penalise()

    assert providers._GEMINI_MIN_INTERVAL <= providers._GEMINI_INTERVAL_CEILING


def test_a_run_of_successes_narrows_the_interval_again(monkeypatch):
    monkeypatch.setattr(providers, "_GEMINI_MIN_INTERVAL", 20.0)
    monkeypatch.setattr(providers, "_GEMINI_OK_STREAK", 0)

    for _ in range(8):
        providers._gemini_reward()

    assert providers._GEMINI_MIN_INTERVAL < 20.0


def test_the_interval_never_narrows_below_the_free_tier_floor(monkeypatch):
    monkeypatch.setattr(providers, "_GEMINI_MIN_INTERVAL", 6.6)
    monkeypatch.setattr(providers, "_GEMINI_OK_STREAK", 0)

    for _ in range(200):
        providers._gemini_reward()

    assert providers._GEMINI_MIN_INTERVAL >= 6.5, "10 RPM is 6s; below that is a 429"


def test_an_unknown_model_is_priced_as_the_dearest_one():
    """Cost estimates must never flatter a model we forgot to add."""
    unknown = providers.cost_eur("some/new-model-2027", {"input_tokens": 1_000_000,
                                                         "output_tokens": 0})
    opus = providers.cost_eur("claude-opus-5", {"input_tokens": 1_000_000,
                                                "output_tokens": 0})
    assert unknown >= opus


def test_every_model_the_router_can_select_has_a_price():
    """Without this, a routing change silently falls back to the guess price."""
    routed = {model for plan in providers.PLANS.values()
              for _prov, model in plan.values()}

    assert routed <= set(providers.PRICE_EUR), (
        "models routable but unpriced: " + str(routed - set(providers.PRICE_EUR))
    )


def test_prices_are_in_eur_not_usd():
    """The operator reads these figures and lives in Paris."""
    from gtm_client_workflows.gaia_sourcing.core.config import PRICING, USD_TO_EUR

    eur = providers.PRICE_EUR["claude-opus-5"]["input"]
    usd = PRICING["claude-opus-5"]["input"]

    assert eur == pytest.approx(usd * USD_TO_EUR, rel=0.02)


def test_set_plan_rejects_a_name_it_does_not_know():
    with pytest.raises(ValueError, match="Unknown plan"):
        providers.set_plan("cheapest")


def test_every_plan_routes_every_role():
    for name, plan in providers.PLANS.items():
        assert set(plan) == {providers.ROLE_EXTRACT, providers.ROLE_JUDGE,
                             providers.ROLE_MESSAGE}, name


def test_haiku_is_never_routable():
    """Banned workspace-wide per ~/.claude/rules/model-tier.md."""
    routed = {m for plan in providers.PLANS.values() for _p, m in plan.values()}
    assert not any("haiku" in m.lower() for m in routed)


@pytest.mark.parametrize("funded,expected", [(True, "anthropic"), (False, "hybrid")])
def test_autoselect_picks_the_best_plan_the_credentials_can_pay_for(
    monkeypatch, funded, expected
):
    monkeypatch.setattr(providers, "anthropic_is_funded", lambda: funded)

    assert providers.autoselect_plan(verbose=False) == expected
    assert providers.ROUTING == providers.PLANS[expected]


def test_an_empty_credit_balance_reads_as_unfunded(monkeypatch):
    class FakeClient:
        def __init__(self, **kw):
            self.messages = self

        def create(self, **kw):
            raise RuntimeError("Your credit balance is too low to access the API")

    monkeypatch.setattr(providers, "secret", lambda *a, **kw: "k")
    monkeypatch.setitem(__import__("sys").modules, "anthropic",
                        type("M", (), {"Anthropic": FakeClient}))

    assert providers.anthropic_is_funded() is False


# ===========================================================================
# cache -- I9: every fetch goes through the cache; no layer re-fetches
# ===========================================================================


class FakeResponse:
    def __init__(self, status=200, content=b"", ctype="text/html"):
        self.status_code = status
        self.content = content
        self.headers = {"Content-Type": ctype}


@pytest.fixture
def cached(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_throttle", lambda url: None)
    return tmp_path


def _serve(monkeypatch, response, counter=None):
    def get(url, **kw):
        if counter is not None:
            counter["n"] += 1
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(cache.requests, "get", get)


HTML = b"<html><head><title>Our People</title></head><body><p>Brian Murphy, CEng MIEI</p></body></html>"


def test_a_page_is_fetched_once_and_read_from_disk_thereafter(cached, monkeypatch):
    """I9. Re-running any layer must be free and offline."""
    hits = {"n": 0}
    _serve(monkeypatch, FakeResponse(content=HTML), hits)

    first = cache.fetch("https://example.ie/people")
    second = cache.fetch("https://example.ie/people")

    assert hits["n"] == 1
    assert first.doc_id == second.doc_id
    assert "Brian Murphy" in second.content_text
    assert second.title == "Our People"


def test_two_unreadable_pdfs_do_not_collapse_onto_one_document(cached, monkeypatch):
    """content_id("") is the SHA of the empty string.

    Cached as ok:true, every image-only scan becomes the same doc_id, and 51
    distinct sources keyed to a single empty entry. Nothing false shipped --
    the validator fails closed against an empty document -- but the drop then
    reads as a hallucination rather than as "this source was never readable".
    """
    _serve(monkeypatch, FakeResponse(content=b"%PDF-1.4 scanned image only",
                                     ctype="application/pdf"))
    monkeypatch.setattr(cache, "_pdf_to_text", lambda raw: "   \n  \n ")

    a = cache.fetch("https://pleanala.ie/scan_a.pdf")
    b = cache.fetch("https://pleanala.ie/scan_b.pdf")

    assert a is None and b is None
    meta = json.loads((cached / (cache.url_key("https://pleanala.ie/scan_a.pdf")
                                 + ".meta.json")).read_text(encoding="utf-8"))
    assert meta["ok"] is False
    assert meta["error"] == "empty_after_parse"
    assert meta["bytes"] > 0, "the diagnosis needs the byte count to be legible"


def test_a_permanent_404_is_not_retried_on_every_later_pass(cached, monkeypatch):
    hits = {"n": 0}
    _serve(monkeypatch, FakeResponse(status=404), hits)

    assert cache.fetch("https://example.ie/gone") is None
    assert cache.fetch("https://example.ie/gone") is None
    assert hits["n"] == 1


def test_a_network_failure_is_recorded_rather_than_swallowed(cached, monkeypatch):
    _serve(monkeypatch, ConnectionError("dns"))

    assert cache.fetch("https://nowhere.invalid/x") is None

    meta = json.loads((cached / (cache.url_key("https://nowhere.invalid/x")
                                 + ".meta.json")).read_text(encoding="utf-8"))
    assert meta["ok"] is False
    assert "ConnectionError" in meta["error"]


def test_a_parse_failure_degrades_the_run_rather_than_killing_it(cached, monkeypatch):
    _serve(monkeypatch, FakeResponse(content=b"%PDF-broken", ctype="application/pdf"))
    monkeypatch.setattr(cache, "_pdf_to_text",
                        lambda raw: (_ for _ in ()).throw(ValueError("not a pdf")))

    assert cache.fetch("https://example.ie/broken.pdf") is None

    meta = json.loads((cached / (cache.url_key("https://example.ie/broken.pdf")
                                 + ".meta.json")).read_text(encoding="utf-8"))
    assert meta["error"].startswith("parse:")


def test_force_re_fetches_a_cached_page(cached, monkeypatch):
    hits = {"n": 0}
    _serve(monkeypatch, FakeResponse(content=HTML), hits)

    cache.fetch("https://example.ie/people")
    cache.fetch("https://example.ie/people", force=True)

    assert hits["n"] == 2


def test_script_and_style_never_reach_the_text(cached, monkeypatch):
    """An unstripped <script> is text a quote could 'verify' against."""
    _serve(monkeypatch, FakeResponse(
        content=b"<html><body><script>var chartered='CEng MIEI';</script>"
                b"<p>Real content here</p></body></html>"))

    doc = cache.fetch("https://example.ie/p")

    assert "Real content here" in doc.content_text
    assert "var chartered" not in doc.content_text


def test_the_rendered_and_raw_copies_of_one_url_coexist(cached, monkeypatch):
    """A firm's directory is fetched raw for links and rendered for content;
    one overwriting the other would silently swap what a claim cites."""
    assert cache.url_key("https://x.ie/p") != cache.url_key("RENDERED::https://x.ie/p")


def test_a_rendered_page_is_served_from_cache_without_a_firecrawl_call(
    cached, monkeypatch
):
    key = cache.url_key("RENDERED::https://ocsc.ie/people")
    (cached / (key + ".body")).write_text("42.7k chars of CEng MIEI", encoding="utf-8")
    (cached / (key + ".meta.json")).write_text(json.dumps({
        "ok": True, "doc_id": "abc", "url": "https://ocsc.ie/people",
        "source_type": "company_bio", "fetched_at": "2026-08-19", "title": "People",
    }), encoding="utf-8")

    def explode(*a, **kw):
        raise AssertionError("a cached render must not be re-bought")

    monkeypatch.setattr(cache.requests, "post", explode)

    doc = cache.fetch_rendered("https://ocsc.ie/people")

    assert doc.doc_id == "abc"
    assert "CEng MIEI" in doc.content_text


def test_a_render_that_returned_nothing_is_recorded_as_a_failure(cached, monkeypatch):
    monkeypatch.setattr(cache, "secret", lambda *a, **kw: "k", raising=False)
    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.config.secret", lambda *a, **kw: "k")

    class Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"data": {"markdown": "   "}}

    monkeypatch.setattr(cache.requests, "post", lambda *a, **kw: Resp())

    assert cache.fetch_rendered("https://ocsc.ie/people") is None


def test_fetch_raw_preserves_the_markup_that_link_discovery_needs(cached, monkeypatch):
    """fetch() stores extracted text, which discards href attributes."""
    monkeypatch.setattr(cache.requests, "get",
                        lambda url, **kw: FakeResponse(content=HTML))

    raw = cache.fetch_raw("https://example.ie/case")

    assert b"<html>" in raw
    assert cache.fetch_raw("https://example.ie/case") == raw


@pytest.mark.parametrize("status,expected_alive", [(200, True), (404, False)])
def test_head_ok_reports_the_status_it_saw(cached, monkeypatch, status, expected_alive):
    monkeypatch.setattr(cache.requests, "head",
                        lambda url, **kw: FakeResponse(status=status))

    assert cache.head_ok("https://example.ie/p") == (expected_alive, status)


def test_a_host_that_refuses_head_is_retried_with_get(cached, monkeypatch):
    """Several Irish consultancy sites answer a bare HEAD with 403 -- including
    one whose page this pipeline had already rendered successfully."""
    monkeypatch.setattr(cache.requests, "head",
                        lambda url, **kw: FakeResponse(status=403))
    monkeypatch.setattr(cache.requests, "get",
                        lambda url, **kw: FakeResponse(status=200))

    assert cache.head_ok("https://ocsc.ie/people") == (True, 200)


def test_head_never_raises_on_a_dead_host(cached, monkeypatch):
    monkeypatch.setattr(cache.requests, "head",
                        lambda url, **kw: (_ for _ in ()).throw(OSError("no route")))

    assert cache.head_ok("https://nowhere.invalid") == (False, 0)


# ---------------------------------------------------------------------------
# The cross-module invariant that would empty the deliverable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", [
    "Chartered   Engineer\n\n\n\n(CEng MIEI)",
    "  leading and trailing  ",
    "tabs\tand\tspaces",
    "Michael O’Reilly, Iarnród Éireann",
    "line one\r\nline two",
    "a   non-breaking space",
])
def test_stored_text_still_contains_its_own_quotes_after_normalisation(raw):
    """cache.normalise_ws and validator.normalize must agree.

    normalise_ws runs once, at fetch, on what gets stored. normalize runs at
    validation, on both the stored text and the model's copy of a quote. If
    normalise_ws collapses a sequence that normalize does not, a verbatim
    quote taken from the stored document stops matching the stored document --
    and L6 drops every claim in the run while reporting a 100% hallucination
    rate.
    """
    from gtm_client_workflows.gaia_sourcing.layers.validator import normalize

    stored = cache.normalise_ws(raw)

    assert normalize(stored) in normalize(stored)
    assert normalize(raw) == normalize(stored), (
        "normalise_ws changed the text in a way validator.normalize does not undo"
    )


def test_normalise_ws_keeps_paragraph_breaks_but_collapses_runs():
    out = cache.normalise_ws("para one\n\n\n\n\npara two")
    assert out == "para one\n\npara two"
