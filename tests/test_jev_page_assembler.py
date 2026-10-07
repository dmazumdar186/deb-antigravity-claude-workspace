"""Offline tests for execution/content/jev_page_assembler (Jev is monkeypatched)."""
from __future__ import annotations

import threading
import urllib.request
from email.message import Message

import pytest

from execution.content.jev_page_assembler import assembler, server
from execution.modules import jev_client

LIB = assembler.load_library()


@pytest.fixture(autouse=True)
def _clear():
    assembler.clear_cache()
    yield
    assembler.clear_cache()


def _fake_ok(calls):
    picks = {"theme": "bold-dark", "hero": "product-demo", "primary_cta": "book-call",
             "proof": "case-study-numbers", "form": "qualify-3-fields",
             "faq": "security-objections", "footer": "full-links"}

    def fake(state, questions, **kw):
        calls.append(questions)
        ans = {k: {"choice": v, "confidence": 0.9} for k, v in picks.items()}
        ans["buyer_stage"] = {"noul": 0.8}
        return jev_client.JevResult(answers=ans, cost_usd=0.0002, latency_ms=5)
    return fake, picks


def test_library_valid():
    for slot in assembler.SLOTS:
        assert len(LIB[slot]) >= 2, slot
        for name, v in LIB[slot].items():
            assert v["description"] and "when" in v
            assert "<script src" not in v.get("html", "").lower()
    for k, v in assembler.DEFAULT_CHOICES.items():
        assert v in LIB[k]
    assert len(assembler.load_personas()) == 6


def test_request_parsing():
    h = Message()
    h["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148"
    h["Referer"] = "https://www.google.com/"
    h["Accept-Language"] = "de-DE,de;q=0.9"
    h["Cookie"] = "jev_seen=1"
    v = server.visitor_from_request(h, "/?utm_source=li&utm_campaign=q4&hour=23")
    assert v["device"] == "mobile" and v["utm_source"] == "li" and v["utm_campaign"] == "q4"
    assert v["locale"] == "de-DE" and v["returning"] is True and v["hour_local"] == 23
    assert server.device_from_ua("Mozilla/5.0 (Windows NT 10.0)") == "desktop"
    assert server.device_from_ua("Mozilla/5.0 (iPad)") == "tablet"
    assert server.visitor_from_request(Message(), "/", now_hour=4)["returning"] is False


def test_assembly_one_call_and_cache(monkeypatch):
    calls = []
    fake, picks = _fake_ok(calls)
    monkeypatch.setattr(jev_client, "decide", fake)
    p = assembler.load_personas()["linkedin-cto"]
    r = assembler.assemble(p, library=LIB)
    assert len(calls) == 1 and set(calls[0]) == set(assembler.SLOTS) | {"buyer_stage"}
    assert r["choices"] == picks and r["error"] is None and r["buyer_stage"] == 0.8
    assert "Security questions" in r["html"] and "Request a call" in r["html"]
    assert "#0f1115" in r["html"] and "{{" not in r["html"]
    r2 = assembler.assemble(p, library=LIB)
    assert len(calls) == 1 and r2["cached"] and r2["cost"] == 0.0


def test_file_cache(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(jev_client, "decide", _fake_ok(calls)[0])
    f = tmp_path / "c.json"
    p = assembler.load_personas()["newsletter-reader"]
    assembler.assemble(p, library=LIB, cache_file=f)
    assembler.clear_cache()
    assert assembler.assemble(p, library=LIB, cache_file=f)["cached"] and len(calls) == 1


def test_fail_open(monkeypatch):
    monkeypatch.setattr(jev_client, "decide",
                        lambda *a, **k: jev_client.JevResult(error="HTTP 500"))
    r = assembler.assemble({"device": "mobile"}, library=LIB, debug=True)
    assert r["choices"] == assembler.DEFAULT_CHOICES and r["error"]
    assert "<h1>" in r["html"] and "FALLBACK" in r["html"]

    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(jev_client, "decide", boom)
    assembler.clear_cache()
    assert assembler.assemble({"device": "x"}, library=LIB)["choices"] == assembler.DEFAULT_CHOICES


def test_server_roundtrip(monkeypatch):
    monkeypatch.setattr(jev_client, "decide", _fake_ok([])[0])
    srv = server.make_server(0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/?debug=1&utm_source=x",
                                     headers={"User-Agent": "iPhone Mobile"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            assert "jev_seen=1" in resp.headers.get("Set-Cookie", "")
        assert "jev-debug" in body and "Security questions" in body
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/preview?persona=linkedin-cto", timeout=5) as resp:
            assert resp.status == 200
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/preview?persona=nope", timeout=5)
    finally:
        srv.shutdown()
        srv.server_close()
