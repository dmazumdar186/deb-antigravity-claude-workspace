"""Offline tests for execution/modules/jev_eval.py and execution/infrastructure/jev_validate.py."""
from __future__ import annotations

import csv
import json

import pytest

from execution.infrastructure import jev_validate as cli
from execution.modules import jev_client, jev_eval
from execution.modules.jev_client import JevResult


def _c(cat: str, conf: float) -> JevResult:
    return JevResult(answers={"q": {"choice": cat, "confidence": conf}}, cost_usd=0.001, input_tokens=10)


# expected: a a a b b c ; got: a a b b c c
LABELS = ["a", "a", "a", "b", "b", "c"]
RESULTS = [_c("a", .9), _c("a", .8), _c("b", .55), _c("b", .95), _c("c", .6), _c("c", .7)]
Q = {"q": jev_client.choice("pick", {"a": "A", "b": "B", "c": "C"})}


def _fake(results):
    def run(states, questions, workers=8):
        assert all("label" not in s for s in states if isinstance(s, dict))
        return list(results)
    return run


@pytest.fixture
def res():
    return jev_eval.evaluate([{"t": str(i)} for i in range(6)], LABELS, Q, question_name="q",
                             decide_many=_fake(RESULTS))


def test_metrics(res):
    assert res["accuracy"] == pytest.approx(4 / 6, abs=1e-3)
    pc = res["per_class"]
    assert pc["a"] == {"precision": 1.0, "recall": pytest.approx(.6667, abs=1e-3),
                       "f1": pytest.approx(.8, abs=1e-3), "support": 3}
    assert pc["b"]["precision"] == .5 and pc["b"]["recall"] == .5
    assert pc["c"]["precision"] == .5 and pc["c"]["recall"] == 1.0
    assert res["confusion"] == {"a": {"a": 2, "b": 1}, "b": {"b": 1, "c": 1}, "c": {"c": 1}}
    assert res["cost_usd"] == pytest.approx(.006)
    assert res["mean_conf_wrong"] == pytest.approx(.575)
    json.dumps(res)


def test_mismatches(res):
    mm = res["mismatches"]
    assert [(m["id"], m["expected"], m["got"]) for m in mm] == [("5", "b", "c"), ("3", "a", "b")]


def test_sweep_monotonic(res):
    sw = jev_eval.threshold_sweep(res)
    cov = [r["coverage"] for r in sw]
    assert cov == sorted(cov, reverse=True)
    assert sw[0]["coverage"] == 1.0
    row = next(r for r in sw if r["threshold"] == .8)
    assert row["covered"] == 3 and row["accuracy_on_covered"] == 1.0


def test_noul_and_errors():
    rs = [JevResult(answers={"q": {"noul": .9}}), JevResult(answers={"q": {"noul": .2}}),
          JevResult(error="boom")]
    r = jev_eval.evaluate(["x", "y", "z"], ["yes", "true", "no"], {"q": jev_client.noul("?", "t", "f")},
                          question_name="q", kind="noul", decide_many=_fake(rs))
    assert r["correct"] == 1 and r["errors"] == 1
    assert r["items"][1]["confidence"] == pytest.approx(.8)


def test_format_report(res):
    md = jev_eval.format_report(res, jev_eval.threshold_sweep(res))
    for s in ("Confusion matrix", "| expected \\ got |", "Top mismatches", "Threshold sweep",
              "What to fix", "accuracy: 66.7%"):
        assert s in md


def test_cli_end_to_end(tmp_path, monkeypatch, capsys):
    data = tmp_path / "d.csv"
    with open(data, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "text", "label"])
        w.writeheader()
        for i, lab in enumerate(LABELS):
            w.writerow({"id": f"r{i}", "text": f"t{i}", "label": lab})
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"state_fields": ["text"], "question_name": "q", "question": Q["q"]}),
                    encoding="utf-8")
    monkeypatch.setattr(jev_client, "available", lambda: True)
    monkeypatch.setattr(jev_client, "decide_many", _fake(RESULTS))
    monkeypatch.setattr(jev_client, "append_ledger", lambda e: None)
    out = tmp_path / "r.md"
    js = tmp_path / "r.json"
    rc = cli.main(["--spec", str(spec), "--data", str(data), "--sweep", "--threshold", "0.6",
                   "--output", str(out), "--json", str(js)])
    assert rc == 0
    assert "Threshold sweep" in capsys.readouterr().out
    assert json.loads(js.read_text(encoding="utf-8"))["mismatches"][0]["id"] == "r4"
    assert out.exists()
    assert cli.main(["--spec", str(spec), "--data", str(data), "--dry-run"]) == 0
