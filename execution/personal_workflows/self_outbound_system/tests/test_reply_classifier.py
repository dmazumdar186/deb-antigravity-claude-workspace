"""
test_reply_classifier.py
description: Tests for reply_classifier.py's deterministic layer: rule precedence (stop > auto-reply metadata > hot > decline > positive > OOO body), quoted-thread stripping, tightened OOO / phone patterns, the opt-out suppression hook, and per-class precision / recall on the labelled EN+FR fixture (tests/fixtures/reply_labelled.json).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
import suppression_writer as sw
from reply_classifier import apply_opt_out, classify, strip_quoted

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "reply_labelled.json"
CLASSES = ("hot", "positive", "neutral", "negative", "auto_reply_or_OOO")
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
# Cases that must be exactly right: compliance (stop) and the panel's adversarial set.
HARD_CASES = [c for c in CASES if c["note"].startswith(("adversarial", "stop"))]


def _run(case: dict) -> dict:
    return classify(case["body"], dry_run=True,
                    subject=case.get("subject"), headers=case.get("headers"))


# --- precedence (panel finding 1) -----------------------------------------

def test_stop_beats_ooo():
    r = classify("I'm out of office until Monday, please remove me", dry_run=True)
    assert r["class"] == "negative" and r["opt_out"] is True


def test_stop_beats_auto_reply_headers():
    r = classify("Please unsubscribe me.", dry_run=True,
                 subject="Automatic reply: hi", headers={"Auto-Submitted": "auto-replied"})
    assert r["class"] == "negative" and r["opt_out"] is True


def test_hot_beats_ooo_wording():
    r = classify("Interested, I will be back Tuesday, can we jump on a call", dry_run=True)
    assert r["class"] == "hot"


def test_auto_reply_header_beats_urgent_phone():
    r = classify("Away. For urgent matters call me on +44 20 7946 0958.", dry_run=True,
                 headers={"X-Autoreply": "yes"})
    assert r["class"] == "auto_reply_or_OOO"


def test_auto_submitted_no_is_not_auto_reply():
    r = classify("Thanks, will forward.", dry_run=True, headers={"Auto-Submitted": "no"})
    assert r["class"] == "neutral"


@pytest.mark.parametrize("body", [
    "Not interested, thanks.",
    "We're not currently interested.",
    "Pas vraiment intéressé pour l'instant.",
    "Je ne suis pas du tout intéressée.",
])
def test_decline_is_negative_without_opt_out(body: str):
    r = classify(body, dry_run=True)
    assert r["class"] == "negative" and r["opt_out"] is False, r


# --- quoted-thread stripping (finding 2) ----------------------------------

@pytest.mark.parametrize("body", [
    "Thanks!\n\nOn Mon, 3 Nov 2026 at 10:00, Deb <d@x.example> wrote:\n> To unsubscribe click here",
    "Thanks!\n\nOn Mon, 3 Nov 2026 at 10:00, Deb\n<d@x.example> wrote:\n> To unsubscribe click here",
    "Merci\n\nLe lun. 3 nov. 2026 à 10:00, Deb <d@x.example> a écrit :\n> Pour vous désinscrire",
    "Thanks\n\n-----Original Message-----\nFrom: Deb\nunsubscribe",
    "Thanks\n\nFrom: Deb <d@x.example>\nSent: Monday\nTo: you\nremove me",
    "Thanks\n\n________________________________\nDe : Deb\nEnvoyé : lundi\ndésinscrire",
    "Thanks<div class=\"gmail_quote\">unsubscribe</div>",
    "Thanks<blockquote type=\"cite\">unsubscribe</blockquote>",
])
def test_quoted_footer_does_not_trigger_stop(body: str):
    assert strip_quoted(body).startswith(("Thanks", "Merci"))
    r = classify(body, dry_run=True)
    assert r["class"] != "negative", r


def test_interleaved_reply_below_quote_is_kept():
    body = "On Mon, Deb <d@x.example> wrote:\n> Would a call help?\nPlease remove me."
    assert strip_quoted(body) == "Please remove me."
    assert classify(body, dry_run=True)["opt_out"] is True


# --- tightened patterns (finding 3) ---------------------------------------

@pytest.mark.parametrize("body", [
    "Absent a clear budget we cannot commit this quarter.",
    "We will return to this topic after the board meeting.",
    "I will be back with feedback from the team.",
])
def test_buyer_wording_is_not_ooo(body: str):
    assert classify(body, dry_run=True)["class"] != "auto_reply_or_OOO"


@pytest.mark.parametrize("body", [
    "Order 2026-4471-8890-1123 has shipped.",
    "Invoice 00012345678 attached for reference.",
    "Our office is at 75008 Paris, 12 34 56 78 is the building code.",
])
def test_numbers_without_call_context_are_not_hot(body: str):
    assert classify(body, dry_run=True)["class"] != "hot"


# --- suppression hook (finding 4) -----------------------------------------

@pytest.fixture
def isolated_suppression(tmp_path, monkeypatch):
    supp = tmp_path / "suppression.json"
    supp.write_text(json.dumps({"emails": [], "domains": [], "history": []}), encoding="utf-8")
    monkeypatch.setattr(sw, "SUPPRESSION_FILE", supp)
    monkeypatch.setattr(sw, "LOCK_FILE", tmp_path / ".suppression.lock")
    return supp


def test_stop_reply_suppresses_sender_idempotently(isolated_suppression):
    r = classify("I'm out of office until Monday, please remove me", dry_run=True)
    first = apply_opt_out(r, "Claire@Acme.example")
    second = apply_opt_out(r, "claire@acme.example")
    state = json.loads(isolated_suppression.read_text(encoding="utf-8"))
    assert state["emails"] == ["claire@acme.example"]
    assert first["added_to_emails"] is True and second["already_present"] is True
    assert all(h["source"] == "reply_classifier" and h["reason"] == "negative_reply"
               for h in state["history"])


@pytest.mark.parametrize("body", ["Not interested, thanks.", "Interested, call me at +33 6 12 34 56 78"])
def test_non_stop_reply_does_not_suppress(isolated_suppression, body: str):
    assert apply_opt_out(classify(body, dry_run=True), "x@acme.example") is None
    assert json.loads(isolated_suppression.read_text(encoding="utf-8"))["emails"] == []


def test_opt_out_dry_run_writes_nothing(isolated_suppression):
    r = classify("unsubscribe", dry_run=True)
    assert apply_opt_out(r, "x@acme.example", dry_run=True)["dry_run"] is True
    assert json.loads(isolated_suppression.read_text(encoding="utf-8"))["emails"] == []


# --- calibration / labelled fixture (finding 5) ---------------------------

def test_result_shape_uses_rule_confidence():
    r = classify("unsubscribe", dry_run=True)
    assert "confidence" not in r
    assert {"class", "rule", "rule_confidence", "opt_out"} <= r.keys()


def test_empty_body_returns_neutral():
    r = classify("", dry_run=True)
    assert r["class"] == "neutral" and r["rule_confidence"] == 0.0


def test_fixture_size_and_languages():
    assert len(CASES) >= 40
    langs = Counter(c["lang"] for c in CASES)
    assert langs["en"] and langs["fr"]
    assert {c["label"] for c in CASES} == set(CLASSES)


@pytest.mark.parametrize("case", HARD_CASES, ids=[c["id"] for c in HARD_CASES])
def test_hard_cases_exact(case: dict):
    r = _run(case)
    assert r["class"] == case["label"], f"{case['id']} {case['note']}: got {r['class']} ({r['rule']})"


def test_labelled_fixture_precision_recall(capsys):
    """Per-class precision / recall of the dry-run rule layer. Prints the table
    (run with -s to see it). Floors are regression guards on a dev set that was
    written alongside the rules, not production estimates."""
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    for case in CASES:
        pred, gold = _run(case)["class"], case["label"]
        if pred == gold:
            tp[gold] += 1
        else:
            fp[pred] += 1
            fn[gold] += 1
    rows = {}
    lines = [f"{'class':<18} {'n':>3} {'prec':>6} {'recall':>6}"]
    for cls in CLASSES:
        p = tp[cls] / (tp[cls] + fp[cls]) if tp[cls] + fp[cls] else 0.0
        r = tp[cls] / (tp[cls] + fn[cls]) if tp[cls] + fn[cls] else 0.0
        rows[cls] = (p, r)
        lines.append(f"{cls:<18} {tp[cls] + fn[cls]:>3} {p:>6.2f} {r:>6.2f}")
    acc = sum(tp.values()) / len(CASES)
    lines.append(f"accuracy {acc:.2f} on {len(CASES)} cases")
    with capsys.disabled():
        print("\nreply_classifier dry-run precision/recall\n" + "\n".join(lines))

    # Compliance: a stop/decline is never missed and nothing else is called negative.
    assert rows["negative"] == (1.0, 1.0)
    for cls in ("hot", "auto_reply_or_OOO"):
        assert rows[cls][0] >= 0.9 and rows[cls][1] >= 0.9, (cls, rows[cls])
    assert rows["positive"][0] >= 0.9 and rows["positive"][1] >= 0.75, rows["positive"]
