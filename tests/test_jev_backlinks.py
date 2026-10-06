"""Offline tests for execution/rag/jev_backlinks.py (Jev is monkeypatched)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from execution.rag import jev_backlinks as b
from execution.modules import jev_client
from execution.modules.jev_client import JevResult


def _site(tmp_path: Path) -> Path:
    (tmp_path / "blog").mkdir()
    (tmp_path / "blog" / "seo_basics.md").write_text(
        "---\ntitle: SEO Basics Guide\n---\n## Keyword research\nbody", encoding="utf-8")
    (tmp_path / "blog" / "seo_links.md").write_text("# SEO Link Building\n## Keyword links\nx", encoding="utf-8")
    (tmp_path / "cooking_pasta.md").write_text("plain pasta notes", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.md").write_text("# SEO junk", encoding="utf-8")
    return tmp_path


def test_profiles_and_exclude(tmp_path):
    root = _site(tmp_path)
    pages = b.find_pages(root, ["md"], b.DEFAULT_EXCLUDE)
    assert len(pages) == 3
    titles = {b.profile(p, root)["title"] for p in pages}
    assert titles == {"SEO Basics Guide", "SEO Link Building", "cooking pasta"}


def test_jaccard_shortlist():
    profs = [{"path": "a.md", "title": "seo guide", "headings": []},
             {"path": "b.md", "title": "seo links guide", "headings": []},
             {"path": "c.md", "title": "pasta", "headings": []}]
    sl = b.shortlist(profs, 12)
    assert sl[0] == [1] and sl[2] == []
    assert all(i not in s for i, s in enumerate(sl))


def test_select_links_symmetric_self_max():
    profs = [{"path": f"{i}.md", "title": str(i)} for i in range(8)]
    sl = [[0, 1, 2, 3, 4, 5, 6, 7]] + [[0]] * 7
    r0 = JevResult(answers={f"rel_{q}": {"noul": 0.9 - q * 0.01} for q in range(8)})
    rb = JevResult(answers={"rel_0": {"noul": 0.8}})
    links = b.select_links(profs, sl, [r0] + [rb] * 7, 0.6, 5)
    assert len(links[0]) == 5 and all(j != 0 for j, _ in links[0])
    assert links[1] == [(0, 0.8)]  # B->A kept alongside A->B
    fail = b.select_links(profs, [[1]], [JevResult(error="x")], 0.6, 5)
    assert fail == [[]]


def test_apply_idempotent_and_report(tmp_path, monkeypatch):
    root = _site(tmp_path)
    monkeypatch.setattr(jev_client, "decide",
                        lambda s, q, **k: JevResult(answers={n: {"noul": 0.9} for n in q}, cost_usd=1e-5))
    assert b.main(["--dir", str(root)]) == 0
    rep = json.loads((root / b.REPORT_NAME).read_text(encoding="utf-8"))
    assert rep["summary"]["links_kept"] == 2 and rep["summary"]["mutual_links"] == 2
    b.main(["--dir", str(root), "--apply", "--dry-run"])
    assert b.START not in (root / "blog" / "seo_links.md").read_text(encoding="utf-8")
    b.main(["--dir", str(root), "--apply"])
    b.main(["--dir", str(root), "--apply"])
    txt = (root / "blog" / "seo_links.md").read_text(encoding="utf-8")
    assert txt.count(b.START) == 1 and "](seo_basics.md)" in txt
    assert b.START not in (root / "cooking_pasta.md").read_text(encoding="utf-8")


def test_render_relpath():
    blk = b.render_block("a/x.md", [{"path": "b/y.md", "title": "Y"}])
    assert "[Y](../b/y.md)" in blk


def test_path_safety(tmp_path):
    with pytest.raises(ValueError):
        b.safe_path(tmp_path, tmp_path / ".." / "evil.md")
