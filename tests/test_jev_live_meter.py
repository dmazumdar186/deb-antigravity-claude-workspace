"""Offline tests for execution/voice_agents/jev_live_meter.py (jev_client.decide monkeypatched)."""
from __future__ import annotations

import io
import threading
import time
from pathlib import Path

from execution.modules import jev_client
from execution.voice_agents import jev_live_meter as m


def _fake(kind: str, claim: float = 3.0, owner: float = 0.0, delay: float = 0.0):
    def fn(state, questions, **_kw):
        time.sleep(delay)
        return jev_client.JevResult(answers={"kind": {"choice": kind, "confidence": 0.9},
                                             "owner_mentioned": {"noul": owner},
                                             "needs_followup": {"noul": 0.0},
                                             "claim_confidence": {"score": claim}},
                                    cost_usd=0.0001, latency_ms=100)
    return fn


def test_split_sentences_and_long_runon():
    assert m.split_sentences("We agreed. Send it Friday! Is that ok?") == [
        "We agreed.", "Send it Friday!", "Is that ok?"]
    assert len(m.split_sentences(" ".join(["word"] * 90), max_words=40)) == 3


def test_parse_line_timestamp_speaker():
    u = m.parse_line("[01:05] Tom: We decided to go.")
    assert u == {"start": 65.0, "speaker": "Tom", "text": "We decided to go."}
    u = m.parse_line("just text here")
    assert u["start"] is None and u["speaker"] == "" and u["text"] == "just text here"
    assert m.parse_line("   ") is None


def test_load_srt(tmp_path: Path):
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:02,000 --> 00:00:04,000\nAnn: Hello there.\n", encoding="utf-8")
    assert m.load_utterances(p) == [{"start": 2.0, "speaker": "Ann", "text": "Hello there."}]


def test_check_rule_and_classify(monkeypatch):
    monkeypatch.setattr(jev_client, "decide", _fake("factual_claim", claim=1.0))
    assert m.classify_sentence("Everyone loves it.", [])["check"] is True
    monkeypatch.setattr(jev_client, "decide", _fake("factual_claim", claim=2.0))
    assert m.classify_sentence("Syncs every 15 min.", [])["check"] is False
    monkeypatch.setattr(jev_client, "decide", _fake("question", claim=0.0))
    assert m.classify_sentence("Why?", [])["check"] is False


def test_bucketing_and_recap_sections():
    rows = [{"t": 1, "speaker": "A", "text": "Go with Growth.", "kind": "decision"},
            {"t": 2, "speaker": "B", "text": "Dev books call.", "kind": "action_item", "owner": True},
            {"t": 3, "speaker": "B", "text": "Migration may slip.", "kind": "risk_or_blocker"},
            {"t": 4, "speaker": "A", "text": "Salesforce?", "kind": "question"},
            {"t": 5, "speaker": "A", "text": "Huge gains.", "kind": "factual_claim", "check": True},
            {"t": 6, "speaker": "A", "text": "Hi.", "kind": "small_talk"}]
    assert [m.bucket_for(r) for r in rows] == ["Decisions", "Action items", "Risks", "Open questions",
                                               "Claims to verify", None]
    md = m.recap_markdown(rows)
    for s in m.SECTIONS:
        assert f"## {s}" in md
    assert "(owner named)" in md and "Hi." not in md


def test_order_preserved_under_slow_call():
    calls = {"n": 0}
    lock = threading.Lock()

    def fn(state, questions, **_kw):
        with lock:
            calls["n"] += 1
            first = calls["n"] == 1
        time.sleep(0.3 if first else 0.0)  # first sentence is slow
        return _fake("decision")(state, questions)

    out = io.StringIO()
    meter = m.Meter(out=out, color=False, workers=4, decide=fn)
    meter.feed({"start": 0, "speaker": "A", "text": "One. Two. Three."})
    stats = meter.close()
    assert [r["text"] for r in meter.rows] == ["One.", "Two.", "Three."]
    assert stats["sentences"] == 3 and stats["p50_ms"] == 100
    assert out.getvalue().index("One.") < out.getvalue().index("Three.")


def test_small_talk_hidden_and_check_marker():
    out = io.StringIO()
    meter = m.Meter(out=out, color=False, decide=_fake("small_talk"))
    meter.feed({"start": 0, "text": "Hi there."})
    meter.close()
    assert out.getvalue() == ""
    out = io.StringIO()
    meter = m.Meter(out=out, color=False, decide=_fake("factual_claim", claim=0.0))
    meter.feed({"start": 61, "text": "It pays for itself."})
    meter.close()
    assert "[01:01] FACTUAL_CLAIM(0.90) [check] It pays for itself." in out.getvalue()


def test_watch_tail_growing_file(tmp_path: Path):
    p = tmp_path / "captions.txt"
    stop = threading.Event()

    def writer():
        for i in range(3):
            time.sleep(0.15)
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(f"[00:0{i}] A: line {i}.\n")

    t = threading.Thread(target=writer)
    t.start()
    got = list(m.tail_lines(p, stop, poll_s=0.05, idle_exit_s=0.6))
    t.join()
    assert got == ["[00:00] A: line 0.", "[00:01] A: line 1.", "[00:02] A: line 2."]


def test_cli_dry_run(tmp_path: Path, capsys):
    p = tmp_path / "t.txt"
    p.write_text("[00:01] A: Hello. We decided.\n", encoding="utf-8")
    assert m.main(["--transcript", str(p), "--dry-run", "--no-color", "--recap", str(tmp_path / "r.md")]) == 0
    assert "2 sentences" in capsys.readouterr().out and (tmp_path / "r.md").is_file()
