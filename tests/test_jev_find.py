"""Offline tests for execution/rag/jev_find.py (Jev is monkeypatched)."""
from __future__ import annotations

import json

from execution.rag import jev_find as f
from execution.modules import jev_client
from execution.modules.jev_client import JevResult


def _words(n: int, w: str = "word") -> str:
    return " ".join([w] * n)


def test_chunker_merges_caps_and_tracks():
    text = ("# Intro\n\n" + _words(10, "a") + "\n\n" + _words(35, "b") + "\n\n"
            "## Big\n\n" + _words(300, "c") + "\n")
    ch = f.chunk_text(text, "x.md")
    assert ch[0]["heading"] == "Intro" and ch[0]["line_start"] == 3 and ch[0]["line_end"] == 5
    assert len(ch[0]["text"].split()) == 45
    assert all(len(c["text"].split()) <= f.MAX_WORDS + f.MIN_WORDS for c in ch)
    big = [c for c in ch if c["heading"] == "Big"]
    assert len(big) >= 2 and big[0]["line_start"] == 9
    assert all(c["file"] == "x.md" for c in ch)


def test_front_matter_skipped():
    ch = f.chunk_text("---\ntitle: t\n---\n\n" + _words(50) + "\n")
    assert len(ch) == 1 and "title" not in ch[0]["text"]


def test_html_stripping_keeps_headings():
    html = ("<html><head><style>x{}</style><script>alert(1)</script></head><body>"
            "<h2>Pricing</h2><p>It costs <b>ten</b> dollars.</p><p>Second para.</p></body></html>")
    t = f.html_to_text(html)
    assert "alert" not in t and "x{}" not in t
    assert "## Pricing" in t and "It costs ten dollars." in t
    ch = f.chunk_text(t)
    assert ch[0]["heading"] == "Pricing"


def test_batch_plan_and_questions():
    b = f.plan_batches(60)
    assert [len(x) for x in b] == [25, 25, 10]
    chunks = [{"file": "", "heading": "", "text": _words(100), "line_start": 1, "line_end": 1}] * 25
    q = f.batch_questions(chunks, b[0])
    assert "none" in q["best"]["criteria"] and len(q["best"]["criteria"]) == 26
    assert all(len(v) <= f.PREVIEW_CHARS for v in q["best"]["criteria"].values())
    assert q["any"]["type"] == "noul"


def _fake(target: int, abstain: set[int] | None = None):
    abstain = abstain or set()
    calls: list[dict] = []

    def decide(state, questions, **_):
        calls.append(questions)
        if "any" in questions:
            opts = [k for k in questions["best"]["criteria"] if k != "none"]
            ids = [int(k) for k in opts]
            if target in ids:
                return JevResult(answers={"best": {"choice": str(target), "probabilities": {str(target): 0.9}},
                                          "any": {"noul": 0.95}}, cost_usd=0.001)
            if ids[0] in abstain:
                return JevResult(answers={"best": {"choice": opts[0]}, "any": {"noul": 0.05}})
            return JevResult(answers={"best": {"choice": opts[0], "probabilities": {opts[0]: 0.4}},
                                      "any": {"noul": 0.6}})
        if "best" in questions:
            keys = list(questions["best"]["criteria"])
            probs = {k: (0.8 if k == str(target) else 0.2 / len(keys)) for k in keys}
            return JevResult(answers={"best": {"choice": str(target), "probabilities": probs}})
        return JevResult(answers={"sent": {"choice": "1"}})
    return decide, calls


def _chunks(n: int):
    return [{"file": f"f{i % 3}.md", "heading": "", "line_start": i, "line_end": i,
             "text": f"Chunk {i} first sentence. Chunk {i} second sentence."} for i in range(n)]


def test_two_stage_ranking_topk(monkeypatch):
    dec, calls = _fake(target=37, abstain={50})
    monkeypatch.setattr(jev_client, "decide", dec)
    res = f.find("q", _chunks(60), top=2, workers=2)
    hits = res["hits"]
    assert hits[0]["chunk"] == 37 and hits[0]["probability"] == 0.8
    assert len(hits) == 2 and hits[0]["probability"] >= hits[1]["probability"]
    assert hits[0]["sentence"] == "Chunk 37 second sentence."
    s = res["summary"]
    assert s["batches"] == 3 and s["calls"] == 5  # 3 batches + stage 2 + sentence
    assert ">> Chunk 37 second sentence." in f.render(hits[0])


def test_per_file_and_fail_open(monkeypatch):
    dec, _ = _fake(target=37)
    monkeypatch.setattr(jev_client, "decide", dec)
    res = f.find("q", _chunks(60), top=5, per_file=True)
    assert len({h["file"] for h in res["hits"]}) == len(res["hits"])
    monkeypatch.setattr(jev_client, "decide", lambda *a, **k: JevResult(error="boom"))
    res = f.find("q", _chunks(30))
    assert res["hits"] == [] and res["summary"]["errors"]


def test_dry_run(tmp_path, capsys):
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.md").write_text("# A\n\n" + _words(80) + "\n", encoding="utf-8")
    (d / "b.txt").write_text(_words(10), encoding="utf-8")
    assert f.main(["--dir", str(d), "--ext", "md", "--query", "x", "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["chunks"] == 1 and plan["batches"] == 1 and plan["files"] == 1


def test_safe_path(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        f.safe_path(tmp_path / "sub", tmp_path / "other.md")
