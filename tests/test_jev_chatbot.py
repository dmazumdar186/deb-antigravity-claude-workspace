"""Offline tests for execution/rag/jev_chatbot.py (jev_client.decide monkeypatched)."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from execution.modules import jev_client
from execution.modules.jev_client import JevResult
from execution.rag import jev_chatbot
from execution.rag.jev_chatbot import JevChatbot, make_server

DOC_A = ("# Jev switch\n\nTo switch Jev off for a private prompt run the slash command jev off. "
         "The router stops sending prompt text to OpenRouter. Turn it back on with jev on later. "
         "Nothing else changes in the session. The setting persists until you flip it again. "
         "This keeps confidential work local and private for as long as you need.\n")
DOC_B = ("# Ad tagger\n\nThe ad library tagger script tags competitor ads by hook, offer and format. "
         "It reads an Ad Library export and writes one row per ad with typed labels for each. "
         "Use it when you need to read hundreds of competitor ads quickly and cheaply.\n")


def fake(intent="question_about_corpus", top="0", top_p=0.9):
    def decide(state, questions, **_):
        if "intent" in questions:
            return JevResult(answers={"intent": {"choice": intent}}, cost_usd=0.00001)
        if "any" in questions:
            opts = list(questions["best"]["criteria"])
            pick = top if top in opts else opts[0]
            return JevResult(answers={"best": {"choice": pick, "probabilities": {pick: top_p}},
                                      "any": {"noul": 1.0}}, cost_usd=0.0001)
        if "best" in questions:
            opts = [k for k in questions["best"]["criteria"]]
            probs = {k: (top_p if k == top else (1 - top_p) / max(1, len(opts) - 1)) for k in opts}
            return JevResult(answers={"best": {"choice": top, "probabilities": probs}}, cost_usd=0.0001)
        if "sent" in questions:
            return JevResult(answers={"sent": {"choice": "0", "probabilities": {"0": 0.7, "1": 0.2}}})
        return JevResult(error="unexpected")
    return decide


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    (tmp_path / "a.md").write_text(DOC_A, encoding="utf-8")
    (tmp_path / "b.md").write_text(DOC_B, encoding="utf-8")
    return tmp_path


def bot(corpus: Path, **kw) -> JevChatbot:
    return JevChatbot(corpus, log_path=None, ledger_path=None, **kw)


def test_greeting_and_out_of_scope(corpus, monkeypatch):
    monkeypatch.setattr(jev_client, "decide", fake(intent="greeting"))
    b = bot(corpus, name="test docs")
    a = b.ask("hello there")
    assert a.kind == "greeting" and "test docs" in a.text and b.index_builds == 0
    monkeypatch.setattr(jev_client, "decide", fake(intent="out_of_scope"))
    a = b.ask("weather in Paris")
    assert a.kind == "out_of_scope" and a.text.startswith("I only know about test docs")


def test_verbatim_answer_and_alternatives(corpus, monkeypatch):
    for n in range(60):  # filler files -> three stage-1 batches -> stage 2 + alternatives
        (corpus / f"z{n:02d}.md").write_text(f"# Filler {n}\n\n" + "word " * 50, encoding="utf-8")
    b = bot(corpus)
    chunks = b.chunks()
    i = next(k for k, c in enumerate(chunks) if c["file"].endswith("a.md"))
    monkeypatch.setattr(jev_client, "decide", fake(top=str(i)))
    a = b.ask("how do I switch jev off")
    assert a.kind == "answer" and a.cost > 0
    src = chunks[i]["text"]
    sents = [s for s in jev_chatbot.jev_find._SENT_RE.split(a.text) if s.strip()]
    assert 2 <= len(sents) <= 3 and all(s in src for s in sents)  # verbatim, trimmed
    c = chunks[i]
    assert a.source.endswith(f"a.md:{c['line_start']}-{c['line_end']}")
    assert len(a.alternatives) == 2 and all(x["source"] != a.source for x in a.alternatives)


def test_low_probability_is_unsure(corpus, monkeypatch):
    b = bot(corpus)
    monkeypatch.setattr(jev_client, "decide", fake(top="0", top_p=0.3))
    a = b.ask("something vague about ads")
    assert a.kind == "unsure" and a.text.startswith("I'm not sure") and a.probability < 0.35


def test_index_cache_on_mtime(corpus):
    b = bot(corpus)
    b.chunks()
    assert b.index_builds == 1 and (corpus / ".jev_chat_index.json").is_file()
    b.chunks()
    b2 = bot(corpus)
    b2.chunks()
    assert b.index_builds == 1 and b2.index_builds == 0  # memory + disk hit
    p = corpus / "a.md"
    st = p.stat()
    os.utime(p, (st.st_atime, st.st_mtime + 10))
    b2.chunks()
    assert b2.index_builds == 1


def test_http_round_trip(corpus, monkeypatch):
    monkeypatch.setattr(jev_client, "decide", fake(intent="greeting"))
    srv = make_server(bot(corpus), port=0)
    assert srv.server_address[0] == "127.0.0.1"
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        port = srv.server_address[1]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/ask", method="POST",
                                     data=json.dumps({"question": "hi"}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        assert data["kind"] == "greeting" and {"text", "source", "probability", "alternatives",
                                              "cost", "latency_ms"} <= set(data)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
            assert b"/ask" in r.read()
    finally:
        srv.shutdown()
        srv.server_close()
