"""Offline tests for execution/lead_sourcing/jev_comment_buyers.py. No network."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.lead_sourcing import jev_comment_buyers as jcb  # noqa: E402
from execution.modules.jev_client import JevResult  # noqa: E402

TIKTOK = {"cid": "t1", "text": "how do I order", "user": {"uniqueId": "ann"}, "diggCount": 4,
          "createTimeISO": "2026-10-01T00:00:00Z", "videoWebUrl": "https://tiktok.com/v/1"}
INSTA = {"id": "i1", "text": "price?", "ownerUsername": "bob", "likesCount": 2,
         "timestamp": "2026-10-02", "postUrl": "https://instagram.com/p/x"}
YOUTUBE = {"comment": "broken on arrival", "author": "@cy", "voteCount": "7",
           "publishedTimeText": "2 days ago", "pageUrl": "https://youtube.com/watch?v=1"}
FLAT = {"id": "f1", "author": "dee", "text": "love it", "likes": 1, "url": "u", "post": "p"}


def _res(intent, temp, reply, conf=0.9, objection="none"):
    return JevResult(answers={
        "intent": {"choice": intent, "confidence": conf},
        "buy_temperature": {"score": temp, "confidence": conf},
        "needs_reply": {"noul": reply},
        "objection": {"choice": objection, "confidence": conf},
    })


def test_normalize_shapes():
    t = jcb.normalize_comment(TIKTOK)
    assert (t["author"], t["likes"], t["post"], t["platform"]) == ("ann", 4, "https://tiktok.com/v/1", "tiktok")
    i = jcb.normalize_comment(INSTA)
    assert (i["author"], i["likes"], i["created"], i["platform"]) == ("bob", 2, "2026-10-02", "instagram")
    y = jcb.normalize_comment(YOUTUBE, 4)
    assert (y["text"], y["author"], y["likes"], y["id"], y["platform"]) == (
        "broken on arrival", "@cy", 7, "c_5", "youtube")
    f = jcb.normalize_comment(FLAT)
    assert (f["author"], f["url"], f["post"], f["platform"]) == ("dee", "u", "p", "flat")


def test_priority_math():
    assert jcb.priority(1.0, 0) == 1.0
    assert jcb.priority(0.5, 10) == round(0.5 * (1 + math.log1p(10) / 4), 4)
    assert jcb.priority(0.0, 1000) == 0.0


def test_apply_results_order_hot_review():
    comments = [jcb.normalize_comment(x, n) for n, x in enumerate([FLAT, YOUTUBE, TIKTOK])]
    results = [_res("praise", 1, 0.2), _res("complaint", 2, 0.9, conf=0.4), _res("ready_to_buy", 3, 0.95)]
    rows = jcb.apply_results(comments, results, 0.55)
    assert [r["author"] for r in rows] == ["ann", "@cy", "dee"]
    assert rows[0]["hot_lead"] and rows[0]["reply_type"] == "DM with checkout link"
    assert rows[1]["hot_lead"] and rows[1]["review"] and rows[1]["reply_type"] == "resolve complaint"
    assert not rows[2]["hot_lead"] and rows[2]["reply_type"] == "thank"
    md = jcb.render_md(rows, 2)
    assert md.index("ann") < md.index("@cy") and "dee" not in md


def test_error_row_flagged():
    rows = jcb.apply_results([jcb.normalize_comment(FLAT)], [JevResult(error="boom")], 0.55)
    assert rows[0]["review"] and rows[0]["priority"] == 0.0 and not rows[0]["hot_lead"]


def test_main_with_monkeypatched_decide_many(tmp_path, monkeypatch):
    src = tmp_path / "c.json"
    src.write_text(json.dumps([INSTA, TIKTOK]), encoding="utf-8")
    monkeypatch.setattr(jcb.jev_client, "available", lambda: True)
    monkeypatch.setattr(jcb.jev_client, "decide_many",
                        lambda states, q, workers=8: [_res("price_or_availability_question", 2, 0.8),
                                                      _res("ready_to_buy", 3, 0.9)])
    monkeypatch.setattr(jcb.jev_client, "append_ledger", lambda e: None)
    md = tmp_path / "o.md"
    assert jcb.main(["--input", str(src), "--md", str(md), "--csv-out", str(tmp_path / "o.csv")]) == 0
    rows = json.loads((tmp_path / "c.json.buyers.json").read_text(encoding="utf-8"))
    assert rows[0]["author"] == "ann" and rows[0]["rank"] == 1
    assert "answer price/availability" in md.read_text(encoding="utf-8")


def test_fetch_apify_without_token_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    assert jcb.main(["--fetch-apify", "clockworks/tiktok-comments-scraper", "--post-urls", "https://x"]) == 2
    assert "APIFY_API_TOKEN" in capsys.readouterr().err
