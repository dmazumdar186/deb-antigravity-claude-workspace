"""Validate Jev against a labelled set (use case 8) — accuracy, confusion, mismatches, sweep.

description: Loads a question spec + labelled CSV/JSON, runs Jev without the labels, prints a
             markdown report (accuracy, per-class P/R/F1, confusion matrix, top 20 mismatches,
             threshold sweep, rule-based "what to fix"). Directive: directives/infrastructure/jev_validate.md.
inputs: --spec spec.json {"state_fields": [...], "question": {type, instructions, criteria},
        "question_name": optional, "label_field": "label", "id_field": "id"}; --data labelled.csv|json;
        --threshold; --sweep; --output report.md; --json out.json; --limit; --workers; --dry-run.
outputs: markdown report on stdout (+ optional files); ledger row caller=jev_validate in
         .tmp/jev_ledger.jsonl. Exit 0 ok, 1 bad input, 2 no API key.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client, jev_eval  # noqa: E402


def load_spec(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    q = spec.get("question")
    if not isinstance(q, dict) or q.get("type") not in ("choice", "noul", "score"):
        raise ValueError("spec.question must have type choice|noul|score")
    if not isinstance(spec.get("state_fields"), list) or not spec["state_fields"]:
        raise ValueError("spec.state_fields must be a non-empty list")
    spec.setdefault("label_field", "label")
    spec.setdefault("id_field", "id")
    spec.setdefault("question_name", "answer")
    return spec


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8", newline="") as fh:
            return [dict(r) for r in csv.DictReader(fh)]
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = data.get("rows", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("JSON data must be a list (or {rows: [...]})")
    return [r for r in rows if isinstance(r, dict)]


def build(spec: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[list, list, list]:
    states, labels, ids = [], [], []
    for i, r in enumerate(rows):
        lab = r.get(spec["label_field"])
        if lab is None or str(lab).strip() == "":
            continue
        states.append({f: r[f] for f in spec["state_fields"] if r.get(f) not in (None, "")})
        labels.append(lab)
        ids.append(str(r.get(spec["id_field"]) or i + 1))
    return states, labels, ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--output")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        spec = load_spec(Path(a.spec))
        states, labels, ids = build(spec, load_rows(Path(a.data)))
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if a.limit:
        states, labels, ids = states[:a.limit], labels[:a.limit], ids[:a.limit]
    if not states:
        print("error: no labelled rows", file=sys.stderr)
        return 1
    kind = spec["question"]["type"]
    questions = {spec["question_name"]: spec["question"]}
    if a.dry_run:
        print(json.dumps({"n": len(states), "kind": kind, "questions": questions,
                          "first_state": states[0], "labels": sorted({str(x) for x in labels})}, indent=2))
        return 0
    if not jev_client.available():
        print("error: no OpenRouter key (OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    res = jev_eval.evaluate(states, labels, questions, question_name=spec["question_name"], kind=kind,
                            threshold=a.threshold, workers=a.workers, ids=ids,
                            decide_many=jev_client.decide_many)
    sweep = jev_eval.threshold_sweep(res) if a.sweep and kind != "score" else None
    report = jev_eval.format_report(res, sweep)
    print(report)
    if a.output:
        Path(a.output).write_text(report, encoding="utf-8")
    if a.json_out:
        Path(a.json_out).write_text(json.dumps({**res, "sweep": sweep}, indent=2), encoding="utf-8")
    jev_client.append_ledger({"caller": "jev_validate", "n": res["n"], "accuracy": res["accuracy"],
                              "cost_usd": res["cost_usd"], "input_tokens": res["input_tokens"],
                              "errors": res["errors"], "wall_s": res["wall_s"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
