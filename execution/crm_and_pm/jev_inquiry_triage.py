"""Triage customer inquiries with Jev (TypeSafe decision model via OpenRouter).

description: Tags each inquiry with a category, an urgency level and a needs-human
             probability in ONE Jev call per inquiry, then routes it to `human` or
             `automation` using a confidence threshold. Also validates predictions
             against a ground-truth CSV so the operator can tune descriptions/threshold.
             Directive: directives/crm_and_pm/jev_inquiry_triage.md
inputs: --input JSON list of {id, subject?, body, from?, channel?} or CSV with those headers;
        --categories "key=desc,key2=desc2" (or bare keys); --min-confidence (default 0.6);
        --workers; --limit; --dry-run; --validate labels.csv (id,category ground truth).
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: --output JSON (default <input>.triage.json) with one row per inquiry:
         category, confidence, probabilities, urgency (score+label), needs_human, route,
         cost_usd, error; optional --csv-out; summary on stdout; ledger row in
         .tmp/jev_ledger.jsonl (caller "jev_inquiry_triage").
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

DEFAULT_CATEGORIES: dict[str, str] = {
    "billing": "invoices, charges, refunds, subscription or payment problems",
    "bug": "something is broken, errors, crashes, unexpected behaviour in the product",
    "question": "how-to or informational question about using the product",
    "feature_request": "asks for new functionality or an improvement that does not exist yet",
    "complaint": "dissatisfied or angry about service, people or experience; not a bug report",
    "spam": "unsolicited marketing, scams, irrelevant or automated junk",
}
URGENCY_LEVELS = ["can wait", "this week", "blocking right now"]
DEFAULT_MIN_CONFIDENCE = 0.6
NEEDS_HUMAN_THRESHOLD = 0.5
MAX_BODY_CHARS = 6_000


# ---- inputs ------------------------------------------------------------------------------

def parse_categories(spec: str | None) -> dict[str, str]:
    """"a=desc,b" -> {a: desc, b: default-or-key}. Empty/None -> DEFAULT_CATEGORIES."""
    if not spec or not spec.strip():
        return dict(DEFAULT_CATEGORIES)
    out: dict[str, str] = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        key, _, desc = part.partition("=")
        key = key.strip()
        out[key] = desc.strip() or DEFAULT_CATEGORIES.get(key, key.replace("_", " "))
    if not out:
        raise ValueError("no categories parsed")
    return out


def load_inquiries(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8", newline="") as fh:
            rows = [dict(r) for r in csv.DictReader(fh)]
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rows = data.get("inquiries", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("input must be a JSON list or CSV")
    out = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        out.append({
            "id": str(r.get("id") or i + 1),
            "subject": str(r.get("subject") or ""),
            "body": str(r.get("body") or "")[:MAX_BODY_CHARS],
            "from": str(r.get("from") or ""),
            "channel": str(r.get("channel") or ""),
        })
    return out


# ---- questions ---------------------------------------------------------------------------

def build_questions(categories: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        "category": jev_client.choice(
            "Which category best describes this customer inquiry?", categories),
        "urgency": jev_client.score(
            "How urgent is this inquiry for the customer?", URGENCY_LEVELS),
        "needs_human": jev_client.noul(
            "Does this inquiry need a real person rather than an automated reply?",
            true="requires a real person: angry customer, legal/refund dispute, ambiguous or multi-issue",
            false="an automation or canned reply can handle it",
        ),
    }


def inquiry_state(inq: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in inq.items() if v}


# ---- routing -----------------------------------------------------------------------------

def urgency_label(score_val: float) -> str:
    idx = min(len(URGENCY_LEVELS) - 1, max(0, int(round(score_val))))
    return URGENCY_LEVELS[idx]


def decide_route(category: str, confidence: float, needs_human: float,
                 min_confidence: float, spam_key: str = "spam") -> str:
    """`human` when unsure, when Jev says a person is needed, or on a low-confidence spam tag."""
    if confidence < min_confidence:
        return "human"
    if needs_human >= NEEDS_HUMAN_THRESHOLD:
        return "human"
    if category == spam_key and confidence < max(min_confidence, 0.8):
        return "human"
    return "automation"


def triage_row(inq: dict[str, Any], res: jev_client.JevResult, min_confidence: float) -> dict[str, Any]:
    row: dict[str, Any] = {"id": inq["id"], "subject": inq.get("subject", "")}
    if not res.ok:
        row.update({"category": "", "confidence": 0.0, "probabilities": {}, "urgency": None,
                    "urgency_label": "", "needs_human": None, "route": "human",
                    "cost_usd": res.cost_usd, "error": res.error or "no answers"})
        return row
    cat = res.choice("category")
    conf = res.confidence("category")
    probs = res.probabilities("category")
    if not conf and probs:
        conf = probs.get(cat, 0.0)
    urg = res.score("urgency")
    nh = res.noul("needs_human")
    row.update({
        "category": cat,
        "confidence": round(conf, 4),
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "urgency": round(urg, 3),
        "urgency_label": urgency_label(urg),
        "needs_human": round(nh, 4),
        "route": decide_route(cat, conf, nh, min_confidence),
        "cost_usd": res.cost_usd,
        "error": None,
    })
    return row


def triage(inquiries: list[dict[str, Any]], categories: dict[str, str], *,
           min_confidence: float = DEFAULT_MIN_CONFIDENCE, workers: int = 8) -> list[dict[str, Any]]:
    questions = build_questions(categories)
    results = jev_client.decide_many([inquiry_state(i) for i in inquiries], questions, workers=workers)
    return [triage_row(i, r, min_confidence) for i, r in zip(inquiries, results)]


# ---- validation --------------------------------------------------------------------------

def load_labels(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8", newline="") as fh:
        return {str(r["id"]).strip(): str(r["category"]).strip()
                for r in csv.DictReader(fh) if r.get("id")}


def validate(rows: list[dict[str, Any]], labels: dict[str, str]) -> dict[str, Any]:
    """Accuracy over rows that have a label, plus the list of mismatches."""
    scored = 0
    correct = 0
    mismatches: list[dict[str, Any]] = []
    for r in rows:
        truth = labels.get(str(r["id"]))
        if truth is None:
            continue
        scored += 1
        if r.get("category") == truth:
            correct += 1
        else:
            mismatches.append({"id": r["id"], "expected": truth, "got": r.get("category", ""),
                               "confidence": r.get("confidence", 0.0)})
    return {"scored": scored, "correct": correct,
            "accuracy": (correct / scored) if scored else 0.0, "mismatches": mismatches}


# ---- summary / io ------------------------------------------------------------------------

def summarize(rows: list[dict[str, Any]], wall_s: float) -> dict[str, Any]:
    by_cat: dict[str, int] = {}
    by_route: dict[str, int] = {}
    for r in rows:
        by_cat[r.get("category") or "(error)"] = by_cat.get(r.get("category") or "(error)", 0) + 1
        by_route[r["route"]] = by_route.get(r["route"], 0) + 1
    return {"count": len(rows), "by_category": by_cat, "by_route": by_route,
            "errors": sum(1 for r in rows if r.get("error")),
            "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in rows), 6),
            "wall_s": round(wall_s, 2)}


def print_summary(s: dict[str, Any]) -> None:
    print(f"Triaged {s['count']} inquiries in {s['wall_s']} s for ${s['cost_usd']:.4f} "
          f"({s['errors']} errors)")
    print("  by category: " + ", ".join(f"{k}={v}" for k, v in sorted(s["by_category"].items())))
    print("  by route:    " + ", ".join(f"{k}={v}" for k, v in sorted(s["by_route"].items())))


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    cols = ["id", "subject", "category", "confidence", "urgency", "urgency_label",
            "needs_human", "route", "cost_usd", "error"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ---- CLI ---------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    ap.add_argument("--csv-out")
    ap.add_argument("--categories", default=None,
                    help='comma list, optionally key=description (default: six built-ins)')
    ap.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="build questions, call nothing")
    ap.add_argument("--validate", help="CSV of id,category ground truth")
    args = ap.parse_args(argv)

    inp = Path(args.input)
    try:
        inquiries = load_inquiries(inp)
        categories = parse_categories(args.categories)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.limit > 0:
        inquiries = inquiries[: args.limit]
    out_path = Path(args.output) if args.output else inp.with_suffix(inp.suffix + ".triage.json")

    if args.dry_run:
        print(json.dumps({"inquiries": len(inquiries), "categories": categories,
                          "questions": build_questions(categories),
                          "min_confidence": args.min_confidence, "output": str(out_path)}, indent=2))
        return 0
    if not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    rows = triage(inquiries, categories, min_confidence=args.min_confidence, workers=args.workers)
    wall = time.perf_counter() - t0
    summary = summarize(rows, wall)

    payload: dict[str, Any] = {"summary": summary, "min_confidence": args.min_confidence,
                               "categories": categories, "rows": rows}
    if args.validate:
        try:
            v = validate(rows, load_labels(Path(args.validate)))
        except (OSError, KeyError, ValueError) as exc:
            print(f"error: validate: {exc}", file=sys.stderr)
            return 2
        payload["validation"] = v
    os.makedirs(out_path.parent or Path("."), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    if args.csv_out:
        write_csv(rows, Path(args.csv_out))

    print_summary(summary)
    if "validation" in payload:
        v = payload["validation"]
        print(f"  validation:  {v['correct']}/{v['scored']} correct = {v['accuracy']:.1%}")
        for m in v["mismatches"]:
            print(f"    id={m['id']} expected={m['expected']} got={m['got']} conf={m['confidence']}")
    print(f"  wrote {out_path}")
    jev_client.append_ledger({"caller": "jev_inquiry_triage", "n": summary["count"],
                              "cost_usd": summary["cost_usd"], "wall_s": summary["wall_s"],
                              "errors": summary["errors"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
