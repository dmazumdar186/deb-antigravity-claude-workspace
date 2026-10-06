"""Offline tests for execution/video/jev_clip_finder.py (Jev is monkeypatched)."""
from __future__ import annotations

import json

from execution.modules import jev_client
from execution.modules.jev_client import JevResult
from execution.video import jev_clip_finder as cf

SRT = """1
00:00:01,000 --> 00:00:04,500
Hello <i>there</i> everyone.

2
00:01:05,250 --> 00:01:09,000
Second line here.
"""
VTT = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hi there.

00:00:04.000 --> 00:00:06.000
Hi there.

01:00:00.000 --> 01:00:02.000
Late cue.
"""


def _segs(n=20, dur=5.0):
    return [{"start": i * dur, "end": (i + 1) * dur,
             "text": f"Sentence number {i} has quite a few words in it here."} for i in range(n)]


def test_parse_srt():
    s = cf.parse_cues(SRT)
    assert s[0] == {"start": 1.0, "end": 4.5, "text": "Hello there everyone."}
    assert s[1]["start"] == 65.25


def test_parse_vtt_dedupes_and_hours():
    s = cf.parse_cues(VTT)
    assert len(s) == 2 and s[0]["end"] == 6.0 and s[1]["start"] == 3600.0


def test_parse_json_and_plain(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps([{"start": 2, "end": 4, "text": "b"}, {"start": 0, "end": 2, "text": "a"}]),
                 encoding="utf-8")
    assert [x["text"] for x in cf.load_transcript(p)] == ["a", "b"]
    q = tmp_path / "t.txt"
    q.write_text("[00:00] Intro words. [01:30] Next bit.", encoding="utf-8")
    s = cf.load_transcript(q)
    assert s[1]["start"] == 90 and s[0]["end"] == 90


def test_windowing():
    w = cf.build_windows(_segs(), window=30, stride=15, min_words=20)
    assert w and w[0]["start"] == 0 and w[0]["end"] == 30
    assert w[1]["start"] == 15
    assert all(c["end"] - c["start"] <= 45 for c in w)
    assert cf.build_windows(_segs(), min_words=10_000) == []


def test_window_extends_to_sentence_end():
    segs = _segs(10)
    segs[5]["text"] = "this one trails off without"
    w = cf.build_windows(segs, window=30, stride=100, min_words=1)
    assert w[0]["end"] == 35


def test_composite_and_weights():
    assert cf.composite(3, 3, 1.0) == 1.0
    assert cf.composite(0, 0, 0.0) == 0.0
    assert cf.composite(3, 0, 0.0) == 0.4
    assert cf.parse_weights("1,1,0") == (0.5, 0.5, 0.0)


def test_dedupe_overlap():
    clips = [{"start": 0, "end": 30, "score": 0.5}, {"start": 10, "end": 40, "score": 0.9},
             {"start": 20, "end": 50, "score": 0.7}]
    assert [c["score"] for c in cf.dedupe(clips)] == [0.9]  # 20/30 overlap dropped
    clips[2]["start"], clips[2]["end"] = 25, 55  # exactly 50% -> dropped (>= rule)
    assert [c["score"] for c in cf.dedupe(clips)] == [0.9]
    clips[2]["start"], clips[2]["end"] = 26, 56  # under 50% -> kept
    assert [c["score"] for c in cf.dedupe(clips)] == [0.9, 0.7]


def test_markdown():
    md = cf.to_markdown([{"start": 65, "end": 95, "clip_type": "story", "score": 0.875, "text": "x" * 200}])
    assert "01:05–01:35" in md and "story" in md and "0.88" in md and "x" * 121 not in md


def test_main_end_to_end(tmp_path, monkeypatch):
    p = tmp_path / "in.json"
    p.write_text(json.dumps(_segs()), encoding="utf-8")

    def fake(states, questions, **kw):
        assert set(questions) == {"hook", "self_contained", "value", "clip_type"}
        return [JevResult(answers={"hook": {"score": i % 4}, "value": {"score": 3},
                                   "self_contained": {"noul": 1.0}, "clip_type": {"choice": "story"}},
                          cost_usd=1e-5) if i != 1 else JevResult(error="boom")
                for i in range(len(states))]

    monkeypatch.setattr(jev_client, "decide_many", fake)
    monkeypatch.setattr(jev_client, "available", lambda: True)
    monkeypatch.setattr(jev_client, "append_ledger", lambda e, **k: None)
    md, csvp = tmp_path / "s.md", tmp_path / "s.csv"
    assert cf.main(["--transcript", str(p), "--top", "3", "--md", str(md), "--csv-out", str(csvp)]) == 0
    data = json.loads((tmp_path / "in.json.clips.json").read_text(encoding="utf-8"))
    assert 1 <= len(data["clips"]) <= 3 and data["errors"] == 1
    assert data["clips"][0]["score"] == 1.0
    assert md.read_text(encoding="utf-8").startswith("# Clip shortlist")
    assert csvp.read_text(encoding="utf-8").startswith("rank,")


def test_youtube_failure_exits_2(monkeypatch):
    monkeypatch.setattr(cf.shutil, "which", lambda _: None)
    assert cf.main(["--youtube", "https://youtu.be/x"]) == 2
