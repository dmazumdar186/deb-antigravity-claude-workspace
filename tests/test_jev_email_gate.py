"""Offline tests for execution/google/jev_email_gate.py (Jev is monkeypatched)."""
from __future__ import annotations

import json

from execution.google import jev_email_gate as g
from execution.modules import jev_client
from execution.modules.jev_client import JevResult


def _res(bucket: str, conf: float = 0.9, scam: float = 0.05, human: float = 0.8) -> JevResult:
    return JevResult(answers={
        "bucket": {"choice": bucket, "confidence": conf, "probabilities": {bucket: conf}},
        "reply_urgency": {"score": 2.0},
        "is_scam": {"noul": scam},
        "human_sent": {"noul": human},
    }, cost_usd=0.0001)


FETCH_SHAPE = [
    {"id": "a", "subject": "Can we meet?", "from": "Ann <ann@x.com>", "date": "d", "snippet": "Are you free Tue?"},
    {"id": "b", "subject": "Weekly digest", "from": "news@y.com", "date": "d", "snippet": "Top stories " * 40},
    {"id": "c", "subject": "Wire transfer", "from": "ceo@x-co.com", "date": "d", "snippet": "Send $5k now"},
    {"id": "d", "subject": "hmm", "from": "z@z.com", "date": "d", "snippet": "?"},
]


def test_load_both_shapes(tmp_path):
    p1 = tmp_path / "f.json"
    p1.write_text(json.dumps(FETCH_SHAPE))
    e = g.load_emails(p1)
    assert e[0]["body"] == "Are you free Tue?" and e[0]["id"] == "a"
    p2 = tmp_path / "flat.json"
    p2.write_text(json.dumps([{"id": 7, "from": "a", "subject": "s", "body": "hello", "date": ""}]))
    e2 = g.load_emails(p2)
    assert e2[0]["id"] == "7" and e2[0]["body"] == "hello"


def test_routing_rules():
    assert g.route("needs_reply", 0.9, 0.1, 0.9) == "agent"
    assert g.route("newsletter_or_notification", 0.9, 0.1, 0.1) == "archive_or_skip"
    assert g.route("personal", 0.9, 0.8, 0.9) == "human"           # targeted phishing
    assert g.route("scam_or_spam", 0.9, 0.9, 0.1) == "archive_or_skip"  # bulk spam
    assert g.route("needs_reply", 0.4, 0.1, 0.9) == "human"         # low confidence
    assert g.route("", 0.0, 0.0, 0.0, error="boom") == "human"      # fail open -> human


def test_end_to_end(tmp_path, monkeypatch, capsys):
    inp = tmp_path / "emails.json"
    inp.write_text(json.dumps(FETCH_SHAPE))
    fake = {"a": _res("needs_reply"), "b": _res("newsletter_or_notification", human=0.05),
            "c": _res("customer_or_client", scam=0.9, human=0.9), "d": _res("needs_reply", conf=0.3)}

    def _dm(states, questions, workers=8):
        subjects = {e["subject"]: e["id"] for e in FETCH_SHAPE}
        return [fake[subjects[s["subject"]]] for s in states]

    monkeypatch.setattr(jev_client, "decide_many", _dm)
    monkeypatch.setattr(jev_client, "available", lambda: True)
    monkeypatch.setattr(jev_client, "append_ledger", lambda e: None)
    q, lab, out = tmp_path / "q.json", tmp_path / "l.json", tmp_path / "o.json"
    assert g.main(["--input", str(inp), "--agent-queue", str(q), "--labels-out", str(lab),
                   "--output", str(out), "--csv-out", str(tmp_path / "o.csv")]) == 0
    queue = json.loads(q.read_text())
    assert [e["id"] for e in queue] == ["a"]
    labels = json.loads(lab.read_text())
    assert labels["Jev/Needs Reply"] == ["a", "d"]
    assert labels["Jev/Newsletter"] == ["b"]
    assert labels["Jev/Spam"] == ["c"]
    assert sorted(labels["Jev/Review"]) == ["c", "d"]
    assert all(isinstance(v, list) for v in labels.values())
    s = json.loads(out.read_text())["summary"]
    assert s["routes"] == {"agent": 1, "archive_or_skip": 1, "human": 2}
    assert s["to_agent"] == 1 and s["scam_flags"] == 1
    assert s["agent_share_bytes_pct"] < 25
    assert abs(s["projected_cost_1700_usd"] - 0.17) < 1e-9


def test_savings_math():
    emails = [{"x": "a" * 100}, {"x": "b" * 300}]
    s = g.summarize(emails, [], [emails[0]], 1.0)
    assert s["input_bytes"] == g._bytes(emails)
    assert 0 < s["agent_share_bytes_pct"] < 50
