"""Acceptance gate contract test for the outbound engine.

Covers SPEC rows G1 (on-ICP), G4 (specific/on-voice/limits), G5 (nothing wrong
ships), G7 (compliance: unsubscribe + non-Canada). Written BEFORE the gate code
(test-first): the gate is audited against THIS test, not against itself.

Corpus (tests/fixtures/outbound_corpus.json) is the independent oracle. Each
`must_reject` row violates exactly one rule so the gate's reason is assertable.
The synthetic seed corpus MUST be augmented with the operator's real v0 flagged
examples after v0 validation (plan: corpus-optimism caveat).

Run: `py tests/acceptance_outbound.py`  (exit 0 = pass, exit 1 = fail)
Also importable by pytest (test_* functions).
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_ENGINE = os.path.join(_ROOT, "execution", "personal_workflows", "outbound_engine")
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)

from acceptance_gate import check_row, run_gate  # noqa: E402  (built after this test)
from lead_scorer import score_lead  # noqa: E402

CORPUS_PATH = os.path.join(_HERE, "fixtures", "outbound_corpus.json")

# id -> the ONE reason code that row must be rejected for.
EXPECTED_REJECT_REASON = {
    "reject_offtarget_title": "icp_fit",
    "reject_canada_geo": "geo_exclude",
    "reject_ca_domain": "geo_exclude",
    "reject_generic_hook": "hook_specificity",
    "reject_too_long": "max_body_words",
    "reject_too_many_links": "max_links",
    "reject_spam_word": "spam_words",
    "reject_missing_unsub": "unsubscribe",
    "reject_unverified_email": "deliverability",
}


def _load():
    with open(CORPUS_PATH, encoding="utf-8") as fh:
        corpus = json.load(fh)
    gate_cfg = corpus["config"]
    scorer_cfg = {
        "icp": gate_cfg["icp"],
        "geo_exclude": gate_cfg["geo_exclude"],
        "scoring": {
            "weights": {"icp_fit": 0.4, "signal_strength": 0.4, "deliverability_confidence": 0.2},
            "min_score_to_queue": 0.6,
        },
    }
    return corpus, gate_cfg, scorer_cfg


def test_must_keep_all_pass():
    corpus, gate_cfg, _ = _load()
    for row in corpus["must_keep"]:
        res = check_row(row, gate_cfg)
        assert res.ok, f"{row['id']} should PASS but failed: {res.reasons}"


def test_must_reject_all_fail_with_expected_reason():
    corpus, gate_cfg, _ = _load()
    for row in corpus["must_reject"]:
        res = check_row(row, gate_cfg)
        assert not res.ok, f"{row['id']} should be REJECTED but passed"
        expected = EXPECTED_REJECT_REASON[row["id"]]
        assert expected in res.reasons, (
            f"{row['id']} rejected for {res.reasons}, expected reason '{expected}'"
        )


def test_run_gate_hard_fails_on_dirty_batch():
    corpus, gate_cfg, _ = _load()
    batch = corpus["must_keep"] + corpus["must_reject"]
    report = run_gate(batch, gate_cfg)
    assert report["failed"] == len(corpus["must_reject"]), report
    assert report["passed"] == len(corpus["must_keep"]), report
    assert report["ok"] is False  # dirty batch -> gate is not clean


def test_run_gate_clean_batch_ok():
    corpus, gate_cfg, _ = _load()
    report = run_gate(corpus["must_keep"], gate_cfg)
    assert report["ok"] is True and report["failed"] == 0, report


def test_scores_in_range_and_keeps_above_threshold():
    corpus, _, scorer_cfg = _load()
    thresh = scorer_cfg["scoring"]["min_score_to_queue"]
    for row in corpus["must_keep"] + corpus["must_reject"]:
        s = score_lead(row, scorer_cfg)
        assert 0.0 <= s <= 1.0, f"{row['id']} score out of range: {s}"
    for row in corpus["must_keep"]:
        assert score_lead(row, scorer_cfg) >= thresh, f"{row['id']} keep scored below threshold"


ALL_TESTS = [
    test_must_keep_all_pass,
    test_must_reject_all_fail_with_expected_reason,
    test_run_gate_hard_fails_on_dirty_batch,
    test_run_gate_clean_batch_ok,
    test_scores_in_range_and_keeps_above_threshold,
]


def main():
    failures = []
    for t in ALL_TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures.append((t.__name__, str(e)))
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001 - surface any error, incl. missing module
            failures.append((t.__name__, repr(e)))
            print(f"ERROR {t.__name__}: {e!r}")
    print("-" * 60)
    if failures:
        print(f"ACCEPTANCE GATE: {len(failures)}/{len(ALL_TESTS)} failed")
        return 1
    print(f"ACCEPTANCE GATE: all {len(ALL_TESTS)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
