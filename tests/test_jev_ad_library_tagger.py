"""Offline tests for execution/custom_scrapers/jev_ad_library_tagger.py.

Covers input-shape normalisation (Apify nested vs flat vs CSV), the tagging merge with a
monkeypatched `decide_many`, CSV columns and low-confidence counting. No network.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.custom_scrapers import jev_ad_library_tagger as tagger  # noqa: E402
from execution.modules.jev_client import JevResult  # noqa: E402

APIFY_ITEM = {
    "ad_archive_id": "123",
    "page_name": "Acme",
    "start_date": "2026-09-01",
    "publisher_platform": ["facebook", "instagram"],
    "snapshot": {
        "body": {"text": "Tired of slow mornings? 40% off this week only."},
        "title": "Acme Coffee",
        "cta_text": "Shop now",
        "link_url": "https://acme.example/shop",
        "display_format": "VIDEO",
    },
}
FLAT_ITEM = {
    "id": "f1", "brand": "Bolt", "body": "Three tips to sleep better tonight.",
    "headline": "Sleep guide", "cta": "Learn more", "link": "https://bolt.example",
    "media_type": "IMAGE", "platforms": "facebook",
}


def _result(fmt="ugc_testimonial", conf=0.9, hook=2.0, offer=0.8, error=None) -> JevResult:
    if error:
        return JevResult(error=error)
    return JevResult(answers={
        "format": {"choice": fmt, "confidence": conf},
        "cta_type": {"choice": "shop_now", "confidence": 0.95},
        "funnel_stage": {"choice": "conversion", "confidence": conf},
        "hook_strength": {"score": hook, "confidence": 0.8},
        "has_offer": {"noul": offer},
    }, cost_usd=0.0001, input_tokens=120, model="typesafe/jev-1.13")


def test_normalize_apify_nested():
    ad = tagger.normalize_ad(APIFY_ITEM)
    assert ad["id"] == "123"
    assert ad["brand"] == "Acme"
    assert ad["body"].startswith("Tired of slow mornings")
    assert ad["headline"] == "Acme Coffee"
    assert ad["cta"] == "Shop now"
    assert ad["link"] == "https://acme.example/shop"
    assert ad["media_type"] == "VIDEO"
    assert ad["platforms"] == "facebook, instagram"
    assert ad["start_date"] == "2026-09-01"


def test_normalize_flat_and_defaults():
    ad = tagger.normalize_ad(FLAT_ITEM)
    assert ad["brand"] == "Bolt" and ad["body"].startswith("Three tips")
    empty = tagger.normalize_ad({}, index=4)
    assert empty["id"] == "ad_5"
    assert all(isinstance(v, str) for v in empty.values())


def test_normalize_carousel_cards_fallback():
    item = {"page_name": "C", "snapshot": {"cards": [{"body": "one"}, {"body": "two"}]}}
    assert tagger.normalize_ad(item)["body"] == "one | two"


def test_load_ads_json_and_csv(tmp_path: Path):
    jp = tmp_path / "ads.json"
    jp.write_text(json.dumps({"items": [APIFY_ITEM, FLAT_ITEM]}), encoding="utf-8")
    ads = tagger.load_ads(jp)
    assert [a["brand"] for a in ads] == ["Acme", "Bolt"]

    cp = tmp_path / "ads.csv"
    with open(cp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(FLAT_ITEM))
        w.writeheader()
        w.writerow(FLAT_ITEM)
    ads = tagger.load_ads(cp)
    assert len(ads) == 1 and ads[0]["headline"] == "Sleep guide"


def test_apply_tags_and_low_confidence():
    ads = [tagger.normalize_ad(APIFY_ITEM), tagger.normalize_ad(FLAT_ITEM), tagger.normalize_ad(FLAT_ITEM, 2)]
    results = [_result(conf=0.9), _result(conf=0.4, offer=0.2), _result(error="HTTP 500")]
    tagged = tagger.apply_tags(ads, results, tagger.build_questions(), 0.55)
    assert tagged[0]["tags"] == {
        "format": "ugc_testimonial", "cta_type": "shop_now", "funnel_stage": "conversion",
        "hook_strength": 2, "has_offer": True,
    }
    assert tagged[0]["low_confidence"] is False
    assert tagged[1]["tags"]["has_offer"] is False
    assert tagged[1]["low_confidence"] is True  # 0.4 < 0.55
    assert tagged[2]["jev_error"] == "HTTP 500" and tagged[2]["low_confidence"] is True
    summary = tagger.summarize(tagged, 0.0002, 1.2, 0.55)
    assert summary["low_confidence"] == 2
    assert summary["jev_errors"] == 1
    assert summary["ads_tagged"] == 2
    assert summary["per_brand"] == {"Bolt": 2, "Acme": 1}


def test_main_end_to_end_with_monkeypatched_decide_many(tmp_path: Path, monkeypatch):
    inp = tmp_path / "ads.json"
    inp.write_text(json.dumps([APIFY_ITEM, FLAT_ITEM]), encoding="utf-8")
    calls: list[int] = []

    def fake_decide_many(states, questions, **kw):
        calls.append(len(states))
        assert set(questions) == set(tagger.TAG_NAMES)
        assert states[0]["brand"] == "Acme" and "id" not in states[0]
        return [_result(conf=0.9), _result(conf=0.3)]

    monkeypatch.setattr(tagger.jev_client, "decide_many", fake_decide_many)
    monkeypatch.setattr(tagger.jev_client, "available", lambda: True)
    monkeypatch.setattr(tagger.jev_client, "append_ledger", lambda entry, path=None: None)
    rc = tagger.main(["--input", str(inp), "--min-confidence", "0.55"])
    assert rc == 0 and calls == [2]

    out = Path(str(inp) + ".tagged.json")
    assert out.exists()
    tagged = json.loads(out.read_text(encoding="utf-8"))
    assert len(tagged) == 2 and tagged[1]["low_confidence"] is True

    with open(out.with_suffix(".csv"), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == tagger.CSV_COLUMNS
    for name in tagger.TAG_NAMES:
        assert name in rows[0] and f"{name}_confidence" in rows[0]
    assert rows[0]["brand"] == "Acme"
    assert len(rows[0]["body_preview"]) <= tagger.BODY_PREVIEW_CHARS
    assert rows[0]["has_offer"] == "1" and rows[1]["low_confidence"] == "1"


def test_dry_run_makes_no_calls(tmp_path: Path, monkeypatch):
    inp = tmp_path / "ads.json"
    inp.write_text(json.dumps([FLAT_ITEM]), encoding="utf-8")

    def boom(*a, **k):
        raise AssertionError("network call in dry-run")

    monkeypatch.setattr(tagger.jev_client, "decide_many", boom)
    assert tagger.main(["--input", str(inp), "--dry-run"]) == 0
    assert Path(str(inp) + ".tagged.json").exists()


def test_fetch_apify_without_token_exits_2(monkeypatch, capsys):
    monkeypatch.delenv(tagger.APIFY_TOKEN_VAR, raising=False)
    assert tagger.main(["--fetch-apify", "acme coffee"]) == 2
    assert tagger.APIFY_TOKEN_VAR in capsys.readouterr().err


def test_body_preview_is_truncated():
    row = tagger.apply_tags([tagger.normalize_ad({"brand": "X", "body": "word " * 100})],
                            [_result()], tagger.build_questions(), 0.55)[0]
    assert len(tagger.to_csv_row(row)["body_preview"]) == tagger.BODY_PREVIEW_CHARS


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
