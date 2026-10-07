"""Offline tests for execution/image_generation/jev_image_search.py."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from execution.image_generation import jev_image_search as jis
from execution.modules import jev_client


def _png(path: Path, prompt: str | None = None, color=(200, 50, 50)) -> None:
    info = PngImagePlugin.PngInfo()
    if prompt:
        info.add_text("prompt", prompt)
    Image.new("RGB", (32, 24), color).save(path, pnginfo=info)


@pytest.fixture()
def gallery(tmp_path: Path) -> Path:
    _png(tmp_path / "img_001.png", "Claude the AI assistant chatting with a developer")
    _png(tmp_path / "img_002.png", "a sunset over the ocean, orange sky")
    _png(tmp_path / "img_003.png", "Claude AI logo on a laptop screen")
    _png(tmp_path / "img_004.png")
    (tmp_path / "img_004.txt").write_text("a cat wearing sunglasses", encoding="utf-8")
    _png(tmp_path / "img_005.png")
    (tmp_path / "img_005.txt").write_text("mountain lake in winter", encoding="utf-8")
    _png(tmp_path / "claude_banner.png")
    return tmp_path


def test_index_sources(gallery: Path) -> None:
    s = jis.build_index(gallery)
    assert s["total"] == 6 and s["indexed"] == 6
    imgs = jis.load_index(gallery)["images"]
    assert imgs["img_001.png"]["source"] == "png_text"
    assert "Claude" in imgs["img_001.png"]["metadata"]
    assert imgs["img_004.png"] == imgs["img_004.png"] | {"source": "sidecar",
                                                          "metadata": "a cat wearing sunglasses"}
    assert imgs["claude_banner.png"]["source"] == "filename"
    assert imgs["claude_banner.png"]["metadata"] == "claude banner"
    assert imgs["img_002.png"]["dims"] == [32, 24]


def test_log_and_exif_sources(tmp_path: Path) -> None:
    _png(tmp_path / "a.png")
    (tmp_path / "prompts.jsonl").write_text(json.dumps({"file": "a.png", "prompt": "red robot"}))
    im = Image.new("RGB", (8, 8))
    exif = Image.Exif()
    exif[0x010E] = "exif described dog"
    im.save(tmp_path / "b.jpg", exif=exif)
    jis.build_index(tmp_path)
    imgs = jis.load_index(tmp_path)["images"]
    assert imgs["a.png"]["metadata"] == "red robot" and imgs["a.png"]["source"] == "log"
    assert imgs["b.jpg"]["metadata"] == "exif described dog"


def test_incremental_skip(gallery: Path) -> None:
    jis.build_index(gallery)
    s = jis.build_index(gallery)
    assert s["skipped"] == 6 and s["indexed"] == 0
    p = gallery / "img_002.png"
    _png(p, "changed prompt now much longer than before", color=(1, 2, 3))
    os.utime(p, (1, 1))
    s = jis.build_index(gallery)
    assert s["indexed"] == 1


def test_path_safety(gallery: Path, tmp_path_factory) -> None:
    outside = tmp_path_factory.mktemp("outside")
    _png(outside / "evil.png", "secret")
    try:
        (gallery / "link.png").symlink_to(outside / "evil.png")
    except OSError:
        pytest.skip("symlinks unsupported")
    jis.build_index(gallery)
    assert "link.png" not in jis.load_index(gallery)["images"]
    with pytest.raises(ValueError):
        jis.safe_path(gallery, gallery / ".." / "x.png")


def test_search_ranking(gallery: Path, monkeypatch) -> None:
    jis.build_index(gallery)
    images = list(jis.load_index(gallery)["images"].values())

    def fake(state, questions, **kw):
        ids = [int(k) for k in questions["best"]["criteria"] if k.isdigit()]
        claude = [i for i in ids if "claude" in pool[i]["metadata"].lower()
                  and "AI" in pool[i]["metadata"]]
        probs = {str(i): (0.6 if pool[i]["path"] == "img_001.png" else 0.3) if i in claude
                 else 0.1 / max(1, len(ids)) for i in ids}
        best = max(probs, key=probs.get) if claude else "none"
        return jev_client.JevResult(answers={
            "best": {"choice": best, "confidence": probs.get(best, 0.9), "probabilities": probs},
            "any": {"noul": 0.9 if claude else 0.05}}, cost_usd=0.001)

    pool = images
    monkeypatch.setattr(jev_client, "decide", fake)
    monkeypatch.setattr(jis.jev_client, "decide", fake)
    res = jis.search("claude", images, top=3)
    assert res["hits"] and res["hits"][0]["path"] in ("img_001.png", "img_003.png")
    assert res["summary"]["calls"] >= 1
    # many images -> two stages
    many = images * 10
    pool = many  # noqa: F841 - read by fake via closure
    res = jis.search("claude", many, top=3)
    assert res["summary"]["batches"] == 3 and res["summary"]["calls"] == 4
    assert res["hits"][0]["path"] == "img_001.png"


def test_filename_baseline(gallery: Path) -> None:
    jis.build_index(gallery)
    images = list(jis.load_index(gallery)["images"].values())
    assert [i["path"] for i in jis.filename_matches(images, "claude")] == ["claude_banner.png"]


def test_html_output(gallery: Path) -> None:
    jis.build_index(gallery)
    images = list(jis.load_index(gallery)["images"].values())
    out = gallery / "out" / "results.html"
    out.parent.mkdir()
    jis.write_html(out, gallery, "claude <x>", [dict(images[0], probability=0.5)])
    doc = out.read_text()
    assert '<img src="../' in doc and "p=0.50" in doc and "&lt;x&gt;" in doc
    assert "http" not in doc


def test_caption_paths(gallery: Path, monkeypatch) -> None:
    jis.build_index(gallery)
    monkeypatch.setattr(jev_client, "api_key", lambda: "k")

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "A red square."}}],
                    "usage": {"cost": 0.0001}}

    calls = []

    def post(url, json=None, timeout=None, headers=None):
        calls.append(json)
        assert json["messages"][0]["content"][1]["image_url"]["url"].startswith(
            "data:image/jpeg;base64,")
        return R()

    s = jis.build_index(gallery, do_caption=True, caption_limit=5, post=post)
    assert s["captioned"] == 1 and len(calls) == 1  # only the filename-only image
    assert jis.load_index(gallery)["images"]["claude_banner.png"]["source"] == "caption"

    def boom(*a, **k):
        raise TimeoutError("slow")
    s = jis.build_index(gallery, caption_all=True, caption_limit=2, post=boom)
    assert s["captioned"] == 0 and len(s["caption_errors"]) == 2


def test_cli(gallery: Path, capsys) -> None:
    assert jis.main(["index", "--dir", str(gallery)]) == 0
    assert jis.main(["search", "--dir", str(gallery), "--query", "claude",
                     "--filename-only"]) == 0
    assert "filename matches: 1" in capsys.readouterr().out
