"""Jev validation-set evaluation — measure how often Jev matches known answers.

description: Runs one Jev question over a labelled set (answers hidden from Jev), then computes
             accuracy, per-class precision/recall/F1, a confusion matrix, the mismatch list,
             mean confidence of correct vs wrong answers, and a confidence-threshold sweep
             (coverage vs accuracy-on-covered) so the operator can pick a --min-confidence.
             Directive: directives/infrastructure/jev_validate.md (use case 8).
inputs: states (list of str|dict, no labels inside), labels (list of expected answers),
        questions (Decisions-API dict, one entry named `question_name`), kind choice|noul|score,
        optional threshold (choice/noul: below it the item counts as "abstained").
outputs: JSON-serializable dict (see `evaluate`); `format_report` renders markdown.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Sequence

from execution.modules import jev_client

DEFAULT_SWEEP = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
ERROR_LABEL = "<error>"


def _norm(v: Any) -> str:
    s = str(v).strip().lower()
    if s in ("1", "yes", "y", "t"):
        return "true"
    if s in ("0", "no", "n", "f"):
        return "false"
    return s


def _extract(res: Any, name: str, kind: str) -> tuple[str, float, Any]:
    """Return (predicted label, confidence 0-1, raw value) for one JevResult."""
    if kind == "noul":
        p = res.noul(name, -1.0)
        if p < 0:
            return ERROR_LABEL, 0.0, None
        return ("true" if p >= 0.5 else "false"), max(p, 1.0 - p), round(p, 4)
    if kind == "score":
        s = res.score(name, -1.0)
        if s < 0:
            return ERROR_LABEL, 0.0, None
        return str(int(round(s))), 1.0, round(s, 4)
    c = res.choice(name, "")
    if not c:
        return ERROR_LABEL, 0.0, None
    return c.strip().lower(), res.confidence(name, 0.0), round(res.confidence(name, 0.0), 4)


def score_items(items: list[dict[str, Any]], kind: str = "choice",
                threshold: float | None = None) -> dict[str, Any]:
    """Metrics from per-item dicts {id, expected, got, confidence, raw, error}. Pure."""
    classes = sorted({i["expected"] for i in items} | {i["got"] for i in items if i["got"] != ERROR_LABEL})
    confusion: dict[str, dict[str, int]] = {e: {} for e in sorted({i["expected"] for i in items})}
    for i in items:
        row = confusion.setdefault(i["expected"], {})
        row[i["got"]] = row.get(i["got"], 0) + 1
    per_class: dict[str, dict[str, float]] = {}
    for c in classes:
        tp = sum(1 for i in items if i["expected"] == c and i["got"] == c)
        fp = sum(1 for i in items if i["expected"] != c and i["got"] == c)
        fn = sum(1 for i in items if i["expected"] == c and i["got"] != c)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        per_class[c] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
                        "support": tp + fn}
    n = len(items)
    correct = [i for i in items if i["correct"]]
    wrong = [i for i in items if not i["correct"] and i["got"] != ERROR_LABEL]

    def _mean(xs: list[dict[str, Any]]) -> float | None:
        return round(sum(x["confidence"] for x in xs) / len(xs), 4) if xs else None

    out: dict[str, Any] = {
        "kind": kind, "n": n, "correct": len(correct),
        "accuracy": round(len(correct) / n, 4) if n else 0.0,
        "per_class": per_class, "confusion": confusion,
        "mismatches": sorted(
            [{k: i[k] for k in ("id", "expected", "got", "confidence", "raw", "error")}
             for i in items if not i["correct"]],
            key=lambda m: -m["confidence"]),
        "mean_conf_correct": _mean(correct), "mean_conf_wrong": _mean(wrong),
        "errors": sum(1 for i in items if i["got"] == ERROR_LABEL),
        "threshold": threshold, "items": items,
    }
    if kind == "score":
        diffs = [abs(float(i["raw"]) - float(i["expected"])) for i in items
                 if i["raw"] is not None and _is_num(i["expected"])]
        out["mae"] = round(sum(diffs) / len(diffs), 4) if diffs else None
    if threshold is not None and kind != "score":
        cov = [i for i in items if i["confidence"] >= threshold]
        out["at_threshold"] = _sweep_row(items, threshold, cov)
    return out


def _is_num(v: Any) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def evaluate(states: Sequence[str | dict[str, Any]], labels: Sequence[Any],
             questions: dict[str, dict[str, Any]], *, question_name: str,
             kind: str = "choice", threshold: float | None = None, workers: int = 8,
             ids: Sequence[Any] | None = None,
             decide_many: Callable[..., list[Any]] | None = None) -> dict[str, Any]:
    """Run Jev over `states` (labels never sent) and score against `labels`."""
    if kind not in ("choice", "noul", "score"):
        raise ValueError(f"unknown kind {kind!r}")
    if len(states) != len(labels):
        raise ValueError("states and labels differ in length")
    if question_name not in questions:
        raise ValueError(f"question {question_name!r} not in questions")
    run = decide_many or jev_client.decide_many
    t0 = time.perf_counter()
    results = run(list(states), questions, workers=workers)
    wall = round(time.perf_counter() - t0, 3)
    ids = list(ids) if ids is not None else [str(i + 1) for i in range(len(states))]
    items = []
    for i, (res, lab) in enumerate(zip(results, labels)):
        got, conf, raw = _extract(res, question_name, kind)
        exp = _norm(lab)
        if kind == "score" and _is_num(exp):
            exp = str(int(round(float(exp))))
        items.append({"id": str(ids[i]), "expected": exp, "got": got, "confidence": round(conf, 4),
                      "raw": raw, "correct": got == exp, "error": getattr(res, "error", None)})
    out = score_items(items, kind, threshold)
    out.update({"question": question_name, "wall_s": wall,
                "cost_usd": round(sum(float(getattr(r, "cost_usd", 0.0) or 0.0) for r in results), 6),
                "input_tokens": sum(int(getattr(r, "input_tokens", 0) or 0) for r in results)})
    return out


def _sweep_row(items: list[dict[str, Any]], t: float, covered: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(items)
    ok = sum(1 for i in covered if i["correct"])
    return {"threshold": t, "covered": len(covered),
            "coverage": round(len(covered) / n, 4) if n else 0.0,
            "accuracy_on_covered": round(ok / len(covered), 4) if covered else None}


def threshold_sweep(results: dict[str, Any], thresholds: Sequence[float] | None = None) -> list[dict[str, Any]]:
    """Coverage (share auto-handled) vs accuracy on the covered share at each threshold."""
    items = results.get("items", [])
    return [_sweep_row(items, t, [i for i in items if i["confidence"] >= t])
            for t in sorted(thresholds or DEFAULT_SWEEP)]


def suggestions(results: dict[str, Any], sweep: list[dict[str, Any]] | None = None) -> list[str]:
    """Rule-based 'what to fix' hints."""
    tips: list[str] = []
    for c, m in results.get("per_class", {}).items():
        if m["support"] and m["recall"] < 0.7:
            tips.append(f"Class `{c}` recall {m['recall']:.2f} < 0.70: Jev misses it — tighten/expand its "
                        "description and add concrete examples to its criteria.")
        predicted = sum(1 for i in results.get("items", []) if i["got"] == c)
        if predicted and m["precision"] < 0.7:
            tips.append(f"Class `{c}` precision {m['precision']:.2f} < 0.70: other items are pulled into it — "
                        "narrow its description or say what it is NOT.")
    pairs: dict[tuple[str, str], int] = {}
    for mm in results.get("mismatches", []):
        if mm["got"] != ERROR_LABEL:
            pairs[(mm["expected"], mm["got"])] = pairs.get((mm["expected"], mm["got"]), 0) + 1
    for (e, g), k in sorted(pairs.items(), key=lambda x: -x[1]):
        if k >= 2:
            tips.append(f"`{e}` confused as `{g}` {k}x: add a disambiguating line to both descriptions.")
    hi = [m for m in results.get("mismatches", []) if m["confidence"] > 0.8]
    if hi and len(hi) >= max(2, 0.25 * len(results.get("mismatches", []))):
        tips.append(f"{len(hi)} mismatches at confidence > 0.8: labels or descriptions conflict — "
                    "re-check those labels before editing criteria.")
    if results.get("errors"):
        tips.append(f"{results['errors']} API errors: check key/timeouts and re-run before trusting numbers.")
    if sweep:
        good = [r for r in sweep if r["accuracy_on_covered"] is not None and r["accuracy_on_covered"] >= 0.95]
        if good:
            tips.append(f"Lowest threshold with >=95% accuracy on covered: {good[0]['threshold']} "
                        f"(coverage {good[0]['coverage']:.0%}) — candidate --min-confidence.")
        else:
            tips.append("No threshold reaches 95% accuracy on covered items: fix criteria before automating.")
    if not tips:
        tips.append("No rule fired; spot-check the mismatches anyway.")
    return tips


def format_report(result: dict[str, Any], sweep: list[dict[str, Any]] | None = None,
                  max_mismatches: int = 20) -> str:
    """Markdown report: summary, per-class, confusion matrix, mismatches, sweep, what to fix."""
    L = [f"# Jev validation — `{result.get('question', '')}` ({result.get('kind')})", "",
         f"- Items: {result['n']}  correct: {result['correct']}  **accuracy: {result['accuracy']:.1%}**",
         f"- Mean confidence correct / wrong: {result.get('mean_conf_correct')} / {result.get('mean_conf_wrong')}",
         f"- Errors: {result.get('errors', 0)}  cost: ${result.get('cost_usd', 0):.6f}  wall: {result.get('wall_s', 0)}s"]
    if result.get("mae") is not None:
        L.append(f"- Mean absolute error (score): {result['mae']}")
    if result.get("at_threshold"):
        a = result["at_threshold"]
        L.append(f"- At threshold {a['threshold']}: coverage {a['coverage']:.0%}, accuracy on covered "
                 f"{a['accuracy_on_covered']}")
    L += ["", "## Per class", "", "| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
    for c, m in result["per_class"].items():
        L.append(f"| {c} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} | {m['support']} |")
    cols = sorted({g for row in result["confusion"].values() for g in row} | set(result["confusion"]))
    L += ["", "## Confusion matrix (rows = expected, cols = got)", "",
          "| expected \\ got | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for e, row in result["confusion"].items():
        L.append(f"| {e} | " + " | ".join(str(row.get(c, 0) or "") for c in cols) + " |")
    mm = result["mismatches"][:max_mismatches]
    L += ["", f"## Top mismatches ({len(result['mismatches'])} total, by confidence)", ""]
    if mm:
        L += ["| id | expected | got | confidence |", "|---|---|---|---|"]
        L += [f"| {m['id']} | {m['expected']} | {m['got']} | {m['confidence']:.2f} |" for m in mm]
    else:
        L.append("None.")
    if sweep:
        L += ["", "## Threshold sweep", "", "| threshold | coverage | covered | accuracy on covered |",
              "|---|---|---|---|"]
        for r in sweep:
            acc = "-" if r["accuracy_on_covered"] is None else f"{r['accuracy_on_covered']:.1%}"
            L.append(f"| {r['threshold']:.2f} | {r['coverage']:.0%} | {r['covered']} | {acc} |")
    L += ["", "## What to fix", ""] + [f"- {t}" for t in suggestions(result, sweep)]
    return "\n".join(L) + "\n"
