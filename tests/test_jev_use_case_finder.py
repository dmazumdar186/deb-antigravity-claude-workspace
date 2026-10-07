"""Offline tests for execution/infrastructure/jev_use_case_finder.py (Jev is monkeypatched)."""
from __future__ import annotations

from execution.infrastructure import jev_use_case_finder as f
from execution.modules import jev_client
from execution.modules.jev_client import JevResult


def test_bundled_catalog_loads():
    cat, src = f.load_catalog(None, live=False)
    assert src == "bundled" and len(cat) >= 40
    for uc in cat:
        assert {"id", "title", "category", "description", "inputs", "effort"} <= set(uc)
        assert uc["effort"] in (1, 2, 3)


def test_built_flags_from_jev_md(tmp_path):
    md = tmp_path / "jev.md"
    md.write_text("| # | Use case | Status |\n|---|---|---|\n| 1 | A | ✅ x |\n| 2 | B | todo |\n| 19 | C | ✅ y |\n",
                  encoding="utf-8")
    built = f.built_numbers(md)
    assert built == {1, 19}
    assert f.is_built({"id": "rn01_x"}, built) and not f.is_built({"id": "rn02_x"}, built)
    assert not f.is_built({"id": "hf01_x"}, built)
    assert len(f.built_numbers()) == 19  # live directive: all 19 built


def test_rank_math_exclusion_quick_wins(monkeypatch):
    cat = [{"id": "rn01_a", "title": "A", "category": "x", "description": "d", "inputs": [], "effort": 1},
           {"id": "hf01_b", "title": "B", "category": "x", "description": "d", "inputs": [], "effort": 1},
           {"id": "hf02_c", "title": "C", "category": "x", "description": "d", "inputs": ["logs"], "effort": 2}]
    vals = {"A": (3, 1.0), "B": (2, 0.9), "C": (3, 0.2)}

    def fake_many(states, questions, **kw):
        assert set(questions) == {"fit", "data_ready", "already_built", "impact"}
        out = []
        for s in states:
            fit, dr = vals[s["use_case"]["title"]]
            out.append(JevResult(answers={"fit": {"score": fit}, "data_ready": {"noul": dr},
                                          "already_built": {"noul": 0.1}, "impact": {"choice": "saves_time"}}))
        return out

    monkeypatch.setattr(jev_client, "decide_many", fake_many)
    monkeypatch.setattr(jev_client, "append_ledger", lambda e, *a, **k: None)
    rows = f.rank(cat, "profile", {1})
    assert [r["title"] for r in rows] == ["B", "C"]  # A built -> excluded
    assert rows[0]["rank"] == f.rank_value(2, 0.9) == 3.8 and rows[1]["rank"] == 3.6
    assert len(f.rank(cat, "profile", {1}, include_built=True)) == 3
    assert f.is_quick_win(rows[0]) and not f.is_quick_win(rows[1])
    md = f.render_rank(rows, 8, "bundled")
    assert "| 1 |" in md and "Quick wins" in md and "**B**" in md
    assert "Needs data first" in md and "logs" in md


def test_split_and_batching():
    text = "# Head\n\n- short one\n- Ran the classifier over every row to decide which leads to keep today\n\n" \
           "A paragraph that is long enough to count as one full step here.\n"
    steps = f.split_steps(text)
    assert len(steps) == 2 and all(len(s.split()) >= 8 for s in steps)
    assert [len(b) for b in f.batches(list(range(45)))] == [20, 20, 5]
    assert len(f.step_questions(20)) <= 40


def test_find_steps_and_render(monkeypatch):
    calls = []

    def fake_decide(state, questions, **kw):
        calls.append(len(questions))
        ans = {}
        for s in state["steps"]:
            i = s["i"]
            ans[f"s{i}_jev"] = {"noul": 0.9 if i % 2 == 0 else 0.3}
            ans[f"s{i}_prim"] = {"choice": "classify" if i % 4 == 0 else "not_a_jev_step"}
        return JevResult(answers=ans)

    monkeypatch.setattr(jev_client, "decide", fake_decide)
    monkeypatch.setattr(jev_client, "append_ledger", lambda e, *a, **k: None)
    steps = [{"source": f"h{i % 2}.md", "text": f"step {i}"} for i in range(25)]
    found = f.find_steps(steps)
    assert calls == [40, 10]
    assert all(x["primitive"] == "classify" and x["prob"] >= 0.7 for x in found)
    md = f.render_steps(found, 25)
    assert "## h0.md" in md and "[classify, p=0.90]" in md
