"""
Text recovery for scanned PDFs, and the honesty it owes.

46 of the 72 oral-hearing witness documents discovered across MetroLink and
DART+ West are image-only scans with no text layer, and on DART+ West that is
precisely where the consultancy witnesses live. Recovering them is the only
route to a Role 2 shortlist that is not padded with the wrong profession.

The recovery is a model reading an image, so a claim validated against it is
a weaker claim than one validated against a document's own text. These tests
exist mostly to make sure that difference stays visible and that a model
which summarises instead of transcribing is refused.
"""

from __future__ import annotations

from datetime import date

import pytest

from gtm_client_workflows.gaia_sourcing.core import cache, ocr
from gtm_client_workflows.gaia_sourcing.core.contracts import RawDocument


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class _Usage:
    def __init__(self, inp=0, out=0):
        self.input_tokens = inp
        self.output_tokens = out
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0


def _client(monkeypatch, text, pages=10, usage=None):
    class FakeClient:
        messages = None

        def create(self, **kw):
            r = _Resp(text)
            r.usage = usage or _Usage()
            return r

    fake = FakeClient()
    fake.messages = fake
    monkeypatch.setattr(ocr, "_anthropic_client", lambda: fake, raising=False)
    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.providers._anthropic_client",
        lambda: fake,
    )
    monkeypatch.setattr(ocr, "page_count", lambda raw: pages)


PAGE = "I am a Chartered Engineer with 22 years of experience. " * 30


def test_a_scan_is_transcribed(monkeypatch):
    _client(monkeypatch, PAGE, pages=10)

    out = ocr.transcribe_pdf(b"%PDF-fake", "https://pleanala.ie/x.pdf")

    assert out and "Chartered Engineer" in out


def test_a_summary_instead_of_a_transcription_is_refused(monkeypatch, capsys):
    """A model that summarises produces a short, fluent document -- and
    short-and-fluent is exactly the shape that would sail through the
    validator while containing sentences the scan never had."""
    _client(monkeypatch, "This document is a witness statement by an engineer.",
            pages=16)

    assert ocr.transcribe_pdf(b"%PDF-fake", "https://pleanala.ie/x.pdf") is None
    assert "suspiciously short" in capsys.readouterr().out


def test_an_empty_transcription_is_not_a_document(monkeypatch):
    _client(monkeypatch, "   ", pages=4)

    assert ocr.transcribe_pdf(b"%PDF-fake") is None


def test_an_api_failure_degrades_the_run_rather_than_ending_it(monkeypatch, capsys):
    class Boom:
        messages = None

        def create(self, **kw):
            raise RuntimeError("overloaded")

    b = Boom()
    b.messages = b
    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.providers._anthropic_client",
        lambda: b)
    monkeypatch.setattr(ocr, "page_count", lambda raw: 5)

    assert ocr.transcribe_pdf(b"%PDF-fake", "https://x.ie/a.pdf") is None
    assert "transcription failed" in capsys.readouterr().out


@pytest.mark.parametrize("pages", [0, None, 500])
def test_a_bundle_or_an_unreadable_pdf_is_not_sent(monkeypatch, pages):
    """Above the page cap it is a hearing bundle, not one person's statement."""
    monkeypatch.setattr(ocr, "page_count", lambda raw: pages)

    def explode():
        raise AssertionError("must not call the API")

    monkeypatch.setattr(
        "gtm_client_workflows.gaia_sourcing.core.providers._anthropic_client",
        lambda: explode())

    assert ocr.transcribe_pdf(b"%PDF-fake") is None


def test_an_oversized_file_is_not_sent(monkeypatch):
    assert ocr.transcribe_pdf(b"x" * (ocr._MAX_BYTES + 1)) is None


def test_an_empty_body_is_not_sent():
    assert ocr.transcribe_pdf(b"") is None


def test_transcription_spend_lands_on_the_run_total(monkeypatch):
    """This path calls the Anthropic client directly rather than through
    call_role, so on its first run it spent real money entirely outside the
    tracker -- the exact defect the tracker had just been built to fix,
    reintroduced by the next feature. A 51-document batch drained the
    account's remaining balance and the ceiling never saw a cent of it."""
    from gtm_client_workflows.gaia_sourcing.core import providers

    providers.reset_spend()
    _client(monkeypatch, PAGE, pages=10, usage=_Usage(inp=1_000_000, out=100_000))

    ocr.transcribe_pdf(b"%PDF-fake", "https://pleanala.ie/x.pdf")

    assert providers.spend_eur() > 0
    providers.reset_spend()


def test_a_refused_transcription_still_records_what_it_cost(monkeypatch):
    """A summarising model is refused on output, but the call was still paid
    for. Not recording it would let a run of refusals spend without limit."""
    from gtm_client_workflows.gaia_sourcing.core import providers

    providers.reset_spend()
    _client(monkeypatch, "too short", pages=40, usage=_Usage(inp=500_000, out=50))

    assert ocr.transcribe_pdf(b"%PDF-fake") is None
    assert providers.spend_eur() > 0
    providers.reset_spend()


# ---------------------------------------------------------------------------
# Provenance -- the flag that keeps the weaker guarantee visible
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, content, ctype="application/pdf"):
        self.status_code = 200
        self.content = content
        self.headers = {"Content-Type": ctype}


@pytest.fixture
def cached(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_throttle", lambda url: None)
    monkeypatch.setattr(cache.requests, "get",
                        lambda url, **kw: FakeResponse(b"%PDF scanned"))
    monkeypatch.setattr(cache, "_pdf_to_text", lambda raw: "")
    return tmp_path


def test_a_recovered_scan_is_marked_as_ocr(cached, monkeypatch):
    monkeypatch.setattr(cache, "log_ocr", lambda url, chars: None)
    monkeypatch.setattr("gtm_client_workflows.gaia_sourcing.core.ocr.transcribe_pdf",
                        lambda raw, url="": PAGE)

    doc = cache.fetch("https://pleanala.ie/scan.pdf")

    assert doc is not None
    assert doc.text_source == "ocr"
    assert "Chartered Engineer" in doc.content_text


def test_the_ocr_mark_survives_a_cache_round_trip(cached, monkeypatch):
    """The flag has to reach the renderer, which reads from cache on re-run."""
    monkeypatch.setattr(cache, "log_ocr", lambda url, chars: None)
    monkeypatch.setattr("gtm_client_workflows.gaia_sourcing.core.ocr.transcribe_pdf",
                        lambda raw, url="": PAGE)
    cache.fetch("https://pleanala.ie/scan.pdf")

    def explode(*a, **kw):
        raise AssertionError("a cached document must not be re-transcribed")

    monkeypatch.setattr("gtm_client_workflows.gaia_sourcing.core.ocr.transcribe_pdf",
                        explode)

    assert cache.fetch("https://pleanala.ie/scan.pdf").text_source == "ocr"


def test_a_text_layer_document_is_never_marked_ocr(cached, monkeypatch):
    monkeypatch.setattr(cache, "_pdf_to_text", lambda raw: "Real text layer. " * 40)

    def explode(*a, **kw):
        raise AssertionError("a readable PDF must not be sent for transcription")

    monkeypatch.setattr("gtm_client_workflows.gaia_sourcing.core.ocr.transcribe_pdf",
                        explode)

    assert cache.fetch("https://pleanala.ie/born-digital.pdf").text_source == "text_layer"


def test_a_scan_that_cannot_be_recovered_is_still_a_failed_fetch(cached, monkeypatch):
    """Unrecovered, it must stay `empty_after_parse` -- never an empty document
    whose content hash collapses it onto every other empty document."""
    monkeypatch.setattr("gtm_client_workflows.gaia_sourcing.core.ocr.transcribe_pdf",
                        lambda raw, url="": None)

    assert cache.fetch("https://pleanala.ie/unreadable.pdf") is None


def test_html_is_never_routed_through_transcription(cached, monkeypatch):
    monkeypatch.setattr(cache.requests, "get",
                        lambda url, **kw: FakeResponse(b"<html></html>", "text/html"))

    def explode(*a, **kw):
        raise AssertionError("only PDFs are transcribed")

    monkeypatch.setattr("gtm_client_workflows.gaia_sourcing.core.ocr.transcribe_pdf",
                        explode)

    assert cache.fetch("https://example.ie/empty") is None


# ---------------------------------------------------------------------------
# The provenance has to reach the card, or marking it achieved nothing
# ---------------------------------------------------------------------------


def _claim(doc_id: str) -> dict:
    return {
        "dimension": "statutory_process",
        "assertion": "Gave evidence at the oral hearing.",
        "evidence_quote": "I gave evidence at the oral hearing",
        "source_url": "https://www.pleanala.ie/x.pdf",
        "source_doc_id": doc_id,
    }


def test_a_quote_from_a_scan_says_so_on_the_card(monkeypatch):
    """L6 checked this quote against a transcription, not against the
    document's own text. A reader weighing the evidence deserves to know
    which kind they are looking at."""
    from gtm_client_workflows.gaia_sourcing.render import render

    monkeypatch.setattr(render, "_OCR_DOC_IDS", {"scanned"})

    html = render._claim_html(_claim("scanned"))

    assert "OCR" in html
    assert "scanned document" in html


def test_a_quote_from_a_text_layer_carries_no_such_note(monkeypatch):
    from gtm_client_workflows.gaia_sourcing.render import render

    monkeypatch.setattr(render, "_OCR_DOC_IDS", {"scanned"})

    html = render._claim_html(_claim("born_digital"))

    assert "OCR" not in html


def test_the_ocr_document_set_is_read_from_the_document_store(tmp_path, monkeypatch):
    from gtm_client_workflows.gaia_sourcing.render import render

    monkeypatch.setattr(render, "RUN_DIR", tmp_path)
    (tmp_path / "docs.jsonl").write_text(
        '{"doc_id": "a", "text_source": "ocr"}\n'
        '{"doc_id": "b", "text_source": "text_layer"}\n'
        '{"doc_id": "c"}\n'
        '{"doc_id": "torn", "text_sou\n',
        encoding="utf-8",
    )

    assert render.load_ocr_doc_ids() == {"a"}


def test_a_missing_document_store_is_not_an_error(tmp_path, monkeypatch):
    from gtm_client_workflows.gaia_sourcing.render import render

    monkeypatch.setattr(render, "RUN_DIR", tmp_path)

    assert render.load_ocr_doc_ids() == set()


def test_documents_written_before_the_flag_existed_still_load():
    """Backward compatibility: docs.jsonl carries records with no text_source."""
    doc = RawDocument(
        doc_id="d1", url="https://example.ie/a", source_type="other",
        fetched_at=date(2026, 8, 19), content_text="x", http_status=200,
    )

    assert doc.text_source == "text_layer"
