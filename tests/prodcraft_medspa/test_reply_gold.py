"""Gap pass (after round 4): reply-classifier gold set.

`fixtures/replies_gold.jsonl` holds 28 realistic med-spa replies (plain voice, no real names) with
the label `prompts/classify_reply.md` should produce. Two tests:

1. The deterministic keyword classifier `scan_replies._mock_classify` (what `--mock` and the
   six-tier suite exercise) must agree with the gold labels on >= 90% of rows, and must never
   call a bare "no" `neutral` (CONTRACTS.md: a bare no is negative or remove).
2. The live classifier (`llm.call` with `mock=False`, model `scan_replies.CLASSIFY_MODEL`) runs the
   same set and appends one JSON line {agreement, prompt_sha256, model_id, ...} to
   `.tmp/prodcraft_medspa/replies_gold_live.jsonl`. Skipped without ANTHROPIC_API_KEY; the
   threshold is the same 90%.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution.personal_workflows.prodcraft_medspa.common import llm
from execution.personal_workflows.prodcraft_medspa.outreach import scan_replies

PKG = Path(__file__).resolve().parents[2] / "execution" / "personal_workflows" / "prodcraft_medspa"
GOLD_PATH = PKG / "fixtures" / "replies_gold.jsonl"
PROMPT_PATH = PKG / "prompts" / "classify_reply.md"
LABELS = {"positive", "neutral", "negative", "remove", "bounce", "ooo"}
THRESHOLD = 0.90


def _load_gold() -> list[dict]:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 28, f"gold set must hold 28 rows, found {len(rows)}"
    assert len({r["id"] for r in rows}) == 28
    for r in rows:
        assert r["expected_sentiment"] in LABELS, r
        assert r["reply_text"].strip()
    return rows


def _is_bare_no_row(row: dict) -> bool:
    first = next((ln for ln in row["reply_text"].splitlines() if ln.strip()), "")
    return bool(re.fullmatch(r"(no|nope|no thanks|no thank you)\W*", first.strip(), flags=re.IGNORECASE))


def test_gold_set_shape_and_coverage():
    rows = _load_gold()
    by_label = {label: [r for r in rows if r["expected_sentiment"] == label] for label in LABELS}
    for label, subset in by_label.items():
        assert len(subset) >= 2, f"gold set needs >= 2 rows per label, {label} has {len(subset)}"
    bare = [r for r in rows if _is_bare_no_row(r)]
    assert len(bare) >= 2, "gold set must contain bare-no replies"
    assert all(r["expected_sentiment"] in ("negative", "remove") for r in bare)
    assert not any("—" in r["reply_text"] for r in rows)


def test_keyword_classifier_agrees_with_gold_at_90_percent():
    rows = _load_gold()
    misses = []
    for r in rows:
        got = scan_replies._mock_classify(r["reply_text"], r.get("from", ""))  # noqa: SLF001
        if got["sentiment"] != r["expected_sentiment"]:
            misses.append((r["id"], r["expected_sentiment"], got["sentiment"]))
        if _is_bare_no_row(r):
            assert got["sentiment"] in ("negative", "remove"), f"bare no classified {got['sentiment']}: {r['id']}"
    agreement = 1 - len(misses) / len(rows)
    assert agreement >= THRESHOLD, f"keyword agreement {agreement:.3f} < {THRESHOLD}; misses={misses}"


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="live classifier needs ANTHROPIC_API_KEY")
def test_live_classifier_agrees_with_gold_and_records_evidence():
    rows = _load_gold()
    our_last_email = "Hi, I noticed a few things on your site and built a quick preview. Reply 'no' and it comes down."
    misses = []
    model_id = None
    prompt_sha256 = None
    for r in rows:
        env = llm.call(
            "classify_reply",
            PROMPT_PATH,
            {"reply_text": r["reply_text"], "our_last_email": our_last_email},
            model=scan_replies.CLASSIFY_MODEL,
            mock=False,
        )
        model_id = env["model_id"]
        prompt_sha256 = prompt_sha256 or env["prompt_sha256"]
        got = json.loads(env["text"])["sentiment"]
        if got != r["expected_sentiment"]:
            misses.append((r["id"], r["expected_sentiment"], got))
        if _is_bare_no_row(r):
            assert got in ("negative", "remove"), f"live classifier called a bare no {got!r}: {r['id']}"
    agreement = 1 - len(misses) / len(rows)
    out = Path(".tmp/prodcraft_medspa")
    out.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agreement": round(agreement, 4),
        "n": len(rows),
        "misses": misses,
        "prompt_file_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        "first_rendered_prompt_sha256": prompt_sha256,
        "model_id": model_id,
    }
    with (out / "replies_gold_live.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    assert model_id == "claude-fable-5-1"
    assert agreement >= THRESHOLD, f"live agreement {agreement:.3f} < {THRESHOLD}; misses={misses}"


@pytest.mark.parametrize(
    "text,expect_remove",
    [
        ("Nope, but stop by anytime", False),
        ("Please don't remove it, let's talk", False),
        ("stop emailing me", True),
        ("remove me", True),
        ("Unsubscribe", True),
        ("take it down", True),
        ("Do not take it down, I like it", False),
        ("Not asking to delete anything, just curious who built it", False),
    ],
)
def test_remove_negation_guard(text, expect_remove):
    """Final audit: negated or idiomatic remove words fall through to the other rules."""
    got = scan_replies._mock_classify(text)  # noqa: SLF001
    assert (got["sentiment"] == "remove") is expect_remove, (text, got)
    assert got["remove_request"] is expect_remove


def test_negated_remove_with_call_ask_is_positive():
    got = scan_replies._mock_classify("Please don't remove it, let's talk")  # noqa: SLF001
    assert got["sentiment"] == "positive" and got["wants_call"] is True


def test_prompt_rule_1_carries_negation_guard():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert "Negation guard" in text and "stop by" in text and "don't remove it" in text
