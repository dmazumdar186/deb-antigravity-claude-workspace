"""Score the Gaia feed mapping (E1) and duplicate detection (E2) against hand-labelled sets.

description: Runs gaia_feed_sync's two decision steps over the labelled fixtures in
    tests/greenjobs_redesign/fixtures/gaia_eval/ and grades them deterministically: E1 per
    dimension (sector, region, job type) for the dictionary tier, the Jev tier on what the
    dictionary left, the Jev tier alone on every job, and the full pipeline; E2 precision and
    recall of the rule tier and rule+Jev pipeline, with Wilson 95% bounds (the positive set is
    below 300 pairs, so a point bar is not meaningful). Jev answers are cached in the fixture
    folder so a re-run is offline, free and reproducible; with no OpenRouter key and no cache
    the Jev tier is reported NOT RUN, never faked.
inputs: --fixtures DIR (default tests/greenjobs_redesign/fixtures/gaia_eval); --report PATH
    (default deliverables/greenjobs_migration_2026-11-06/build/feed/eval_report.md); --no-jev;
    --jev-cut 0.6; --dup-hi 0.8; --dup-lo 0.2. Env: OPENROUTER_API_KEY (optional).
outputs: the markdown report, the report path with .json (machine results), {fixtures}/jev_cache_eval.json
    (Jev answers, no secrets); ledger row in .tmp/jev_ledger.jsonl when Jev is called.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gaia_feed_sync as gfs  # noqa: E402

ROOT = gfs.ROOT
FIX = ROOT / "tests" / "greenjobs_redesign" / "fixtures" / "gaia_eval"
REPORT = (
    ROOT
    / "deliverables"
    / "greenjobs_migration_2026-11-06"
    / "build"
    / "feed"
    / "eval_report.md"
)
DIMS = ("sector", "region", "job_type")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def pct(k: int, n: int) -> str:
    return f"{k}/{n} = {100 * k / n:.1f}%" if n else "0/0 (n/a)"


def e1(fix: Path, jev: gfs.Jev, cut: float) -> dict[str, Any]:
    snap = json.loads(
        (fix / "gaia_snapshot_2026-11-20.json").read_text(encoding="utf-8")
    )
    gold = {
        r["source_id"]: r
        for r in json.loads((fix / "e1_labels.json").read_text(encoding="utf-8"))[
            "labels"
        ]
    }
    mapping, regions = gfs.load_mapping(), gfs.load_regions()
    out: dict[str, Any] = {"n": len(gold)}
    runs = {}
    for name, force in (("pipeline", False), ("jev_alone", True)):
        recs = gfs.normalise(snap, mapping)
        gfs.map_jobs(recs, mapping, regions, jev, cut, force_jev=force)
        runs[name] = {r["source_id"]: r["mapping"] for r in recs}
    for dim in DIMS:
        d: dict[str, Any] = {}
        pipe = runs["pipeline"]
        rows = [(sid, pipe[sid][dim], gold[sid][dim]) for sid in gold]
        det = [(m, g) for _s, m, g in rows if m["method"] == "dict"]
        jv = [(m, g) for _s, m, g in rows if m["method"] == "jev"]
        q = [(m, g) for _s, m, g in rows if m["method"] == "queue"]
        auto = det + jv
        d["dict"] = {"n": len(det), "correct": sum(m["value"] == g for m, g in det)}
        d["jev_on_rest"] = {
            "n": len(jv),
            "correct": sum(m["value"] == g for m, g in jv),
            "queued": len(q),
        }
        d["pipeline"] = {
            "auto": len(auto),
            "correct": sum(m["value"] == g for m, g in auto),
            "queued": len(q),
            "n": len(rows),
        }
        d["errors"] = sorted(
            [
                {"source_id": s, "method": m["method"], "got": m["value"], "gold": g}
                for s, m, g in rows
                if m["method"] != "queue" and m["value"] != g
            ],
            key=lambda x: x["source_id"],
        )
        ja = runs["jev_alone"]
        jrows = [(ja[s][dim], gold[s][dim]) for s in gold]
        answered = [(m, g) for m, g in jrows if m["method"] == "jev"]
        d["jev_alone"] = {
            "n": len(jrows),
            "answered": len(answered),
            "correct": sum(m["value"] == g for m, g in answered),
            "not_run": sum(
                1 for m, _g in jrows if m["method"] == "queue" and "jev_choice" not in m
            ),
        }
        # threshold sweep for the Jev tier alone (confidence of the top choice)
        sweep = []
        for t in (0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
            cov = [(m.get("value") or m.get("jev_value"), g) for m, g in jrows if (m["method"] == "jev" or "jev_choice" in m) and m["confidence"] >= t and (m.get("value") or m.get("jev_value")) is not None]
            sweep.append(
                {"cut": t, "covered": len(cov), "correct": sum(v == g for v, g in cov)}
            )
        d["jev_alone"]["sweep"] = sweep
        out[dim] = d
    return out


def e2(fix: Path, jev: gfs.Jev, hi: float, lo: float) -> dict[str, Any]:
    snap = json.loads(
        (fix / "gaia_snapshot_2026-11-20.json").read_text(encoding="utf-8")
    )
    board = {
        (b["site"], b["id"]): b
        for b in json.loads(
            (fix / "board_snapshot_2026-11-20.json").read_text(encoding="utf-8")
        )["jobs"]
    }
    doc = json.loads((fix / "e2_pairs.json").read_text(encoding="utf-8"))
    recs = {r["source_id"]: r for r in gfs.normalise(snap, gfs.load_mapping())}
    labelled = [p for p in doc["pairs"] if p["label"] is not None]
    items = [
        (recs[p["source_id"]], board[(p["board_site"], p["board_id"])])
        for p in labelled
    ]
    verdicts = gfs.judge_pairs(items, gfs.load_regions(), jev, hi, lo)
    res: dict[str, Any] = {
        "pairs": len(labelled),
        "positives": sum(p["label"] for p in labelled),
        "unsure_excluded": doc["counts"]["unsure_excluded"],
    }
    for tier in ("rule", "pipeline"):
        tp = fp = fn = tn = q = qpos = 0
        errs = []
        for p, v in zip(labelled, verdicts):
            verdict = v["verdict"]
            if tier == "rule" and v["method"] == "jev":
                verdict = "queue"  # rule tier alone: ambiguous pairs are not decided
            if verdict == "ambiguous":
                verdict = "queue"
            y = p["label"] == 1
            if verdict == "queue":
                q += 1
                qpos += y
                continue
            hit = verdict == "dup"
            tp += hit and y
            fp += hit and not y
            fn += (not hit) and y
            tn += (not hit) and not y
            if hit != y:
                errs.append(
                    {
                        "source_id": p["source_id"],
                        "board": f"{p['board_site']}:{p['board_id']}",
                        "feed_title": p["feed_title"],
                        "board_title": p["board_title"],
                        "label": int(y),
                        "verdict": verdict,
                        "method": v["method"],
                        "jev_noul": v.get("jev_noul"),
                    }
                )
        res[tier] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "queued": q,
            "queued_positive": qpos,
            "precision": [tp, tp + fp],
            "recall_auto": [tp, res["positives"]],
            "errors": errs,
        }
    res["jev_calls_on_pairs"] = sum(1 for v in verdicts if v["method"] == "jev")
    return res


def fmt_ratio(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{pct(k, n)} (Wilson 95%: {100 * lo:.1f}–{100 * hi:.1f}%)" if n else "n/a"


def report(
    r1: dict, r2: dict, jev_status: str, cut: float, hi: float, lo: float
) -> str:
    L = [
        "# Gaia feed sync: evals E1 (mapping) and E2 (duplicate detection)",
        "",
        "Generated by `execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_eval.py` from the fixtures in "
        "`tests/greenjobs_redesign/fixtures/gaia_eval/` (Gaia wp-json and GreenJobs snapshots of 2026-11-20). "
        "Graded by script, not by an LLM. Labelling rules are in `e1_labels.json` and `e2_pairs.json`.",
        "",
        f"Jev tier: {jev_status}. Confidence cut {cut}; duplicate noul cut dup ≥ {hi}, not ≤ {lo}, between = review queue.",
        "",
        "## E1: Gaia taxonomy → GreenJobs sector / region / job type",
        "",
        f"Labelled set: all {r1['n']} Gaia jobs in the snapshot (SYNTHESIS asks for 100; Gaia publishes only {r1['n']}, so this is the whole population). "
        "Hand-labelled by one labeller (Claude), who also wrote the dictionary: the dictionary-tier score is in-sample and optimistic. "
        "The Jev-alone row (dictionary switched off) is the less biased measure of the AI part.",
        "",
        "| Dimension | Dictionary tier: decided, correct | Jev on the rest: decided, correct (queued) | Pipeline auto-decided accuracy | Queued to review | Jev alone, every job (correct / answered above cut) |",
        "|---|---|---|---|---|---|",
    ]
    tot = {"auto": 0, "correct": 0, "n": 0, "dict": 0}
    for dim in DIMS:
        d = r1[dim]
        ja = d["jev_alone"]
        jcell = (
            "NOT RUN"
            if ja["not_run"] == ja["n"]
            else pct(ja["correct"], ja["answered"])
        )
        jr = d["jev_on_rest"]
        L.append(
            f"| {dim} | {d['dict']['n']}/{r1['n']} decided, {pct(d['dict']['correct'], d['dict']['n'])} | "
            f"{('NOT RUN' if jr['n'] == 0 and jr['queued'] and 'NOT' in jev_status else pct(jr['correct'], jr['n']))} ({jr['queued']} queued) | "
            f"{fmt_ratio(d['pipeline']['correct'], d['pipeline']['auto'])} | {d['pipeline']['queued']} | {jcell} |"
        )
        tot["auto"] += d["pipeline"]["auto"]
        tot["correct"] += d["pipeline"]["correct"]
        tot["n"] += d["pipeline"]["n"]
        tot["dict"] += d["dict"]["n"]
    L += [
        "",
        f"Deterministic share of decisions: {pct(tot['dict'], tot['n'])}. "
        f"Pipeline over all {tot['n']} decisions: {fmt_ratio(tot['correct'], tot['auto'])} exact on the auto-decided ones; "
        f"{tot['n'] - tot['auto']} queued for Rashieda.",
        "",
        f"Bar (SYNTHESIS E1): ≥95% exact, below the cut to the queue. **{'PASS' if tot['auto'] and tot['correct'] / tot['auto'] >= 0.95 else 'FAIL'}** on the point estimate; "
        f"the Wilson lower bound is {100 * wilson(tot['correct'], tot['auto'])[0]:.1f}%. Per dimension: "
        + "; ".join(
            f"{dim} {'PASS' if r1[dim]['pipeline']['auto'] and r1[dim]['pipeline']['correct'] / r1[dim]['pipeline']['auto'] >= 0.95 else 'FAIL'}"
            for dim in DIMS
        )
        + ". Where sector fails, the errors are Jev picks on jobs whose title and Gaia terms disagree; raising the sector cut "
        "(see the sweep) or queueing every sector conflict trades accuracy for queue size, and is the operator's call.",
        "",
        "Jev-alone threshold sweep (sector / region / job type: covered, correct):",
        "",
    ]
    for dim in DIMS:
        sw = r1[dim]["jev_alone"]["sweep"]
        L.append(
            f"- {dim}: "
            + "; ".join(f"cut {s['cut']}: {s['correct']}/{s['covered']}" for s in sw)
        )
    L += ["", "Pipeline errors (auto-decided, wrong vs label):", ""]
    for dim in DIMS:
        for e in r1[dim]["errors"]:
            L.append(
                f"- {dim} {e['source_id']} ({e['method']}): got '{e['got']}', label '{e['gold']}'"
            )
    p, rule = r2["pipeline"], r2["rule"]
    L += [
        "",
        "## E2: duplicate detection (feed job already on a GreenJobs board)",
        "",
        f"Labelled set: {r2['pairs']} pairs scored ({r2['positives']} same-vacancy, {r2['pairs'] - r2['positives']} not), "
        f"{r2['unsure_excluded']} unsure pairs excluded. Pairs: every Gaia job × board job with title similarity ≥ 0.3 or shared text, plus 300 random easy negatives, "
        f"from 83 Gaia jobs × 230 board jobs (145 .ie + 85 .co.uk). "
        f"**Fewer than 300 positive pairs exist**, so the 99% / 95% bars are judged on Wilson 95% lower bounds, not on point estimates.",
        "",
        "| Tier | Precision | Recall (auto, of all positives) | Queued (of which positive) | FP | FN |",
        "|---|---|---|---|---|---|",
        f"| Rule only (ambiguous → queue) | {fmt_ratio(*rule['precision'])} | {fmt_ratio(*rule['recall_auto'])} | {rule['queued']} ({rule['queued_positive']}) | {rule['fp']} | {rule['fn']} |",
        f"| Rule + Jev noul | {fmt_ratio(*p['precision'])} | {fmt_ratio(*p['recall_auto'])} | {p['queued']} ({p['queued_positive']}) | {p['fp']} | {p['fn']} |",
        "",
    ]
    prec_lb = wilson(*p["precision"])[0]
    rec_lb = wilson(*p["recall_auto"])[0]
    L += [
        f"Bar (SYNTHESIS E2): precision ≥99%, recall ≥95%. Precision lower bound {100 * prec_lb:.1f}%, recall lower bound {100 * rec_lb:.1f}%: "
        f"**{'PASS' if prec_lb >= 0.99 and rec_lb >= 0.95 else 'NOT MET on the lower bound'}**"
        f"{'' if prec_lb >= 0.99 else ' (with ' + str(p['precision'][1]) + ' predicted duplicates, even 0 errors cannot prove 99% at 95% confidence; about 300 clean predictions are needed)'}.",
        "",
        "Pipeline errors:",
        "",
    ]
    for e in p["errors"]:
        L.append(
            f"- {e['source_id']} × {e['board']}: '{e['feed_title']}' vs '{e['board_title']}', label {e['label']}, got {e['verdict']} via {e['method']}"
            + (f" (noul {e['jev_noul']})" if e["jev_noul"] is not None else "")
        )
    if not p["errors"]:
        L.append("- none")
    L += [
        "",
        "## Not covered",
        "",
        "- E3 (routing to the 8 sector sites) is not built here: it needs the sector-site mapping decided in the destination spike.",
        "- Labels come from one labeller. A second, blind labeller on the E1 sector column would show how much of the error is label ambiguity "
        "(seven jobs are flagged ambiguous in the rule).",
        "- In-sample caveat: the term dictionary, the title-keyword conflict rule, the copied-advert threshold (0.5) and the "
        "'one advert is one vacancy' constraint were set while reading this same data, so the deterministic numbers are optimistic. "
        "The Jev-alone column and next month's re-score on fresh Gaia jobs are the honest checks.",
        "",
    ]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score E1/E2 for the Gaia feed sync")
    ap.add_argument("--fixtures", type=Path, default=FIX)
    ap.add_argument("--report", type=Path, default=REPORT)
    ap.add_argument("--no-jev", action="store_true")
    ap.add_argument("--jev-cut", type=float, default=0.6)
    ap.add_argument("--dup-hi", type=float, default=0.8)
    ap.add_argument("--dup-lo", type=float, default=0.2)
    a = ap.parse_args(argv)
    jev = gfs.Jev(a.fixtures / "jev_cache_eval.json", not a.no_jev)
    if a.no_jev:
        jev.cache = {}
    r1 = e1(a.fixtures, jev, a.jev_cut)
    r2 = e2(a.fixtures, jev, a.dup_hi, a.dup_lo)
    if jev.enabled or (jev.cache and not a.no_jev):
        status = f"RUN (typesafe Jev via OpenRouter; {jev.calls} new calls, {jev.errors} errors, ${jev.cost:.4f} this run; answers cached in jev_cache_eval.json)"
    else:
        status = f"NOT RUN ({jev.reason}); only the deterministic tier is scored"
    if not a.no_jev:
        jev.save()
    gfs.write_if_changed(
        a.report, report(r1, r2, status, a.jev_cut, a.dup_hi, a.dup_lo)
    )
    gfs.write_if_changed(
        a.report.with_suffix(".json"),
        json.dumps({"e1": r1, "e2": r2, "jev": status}, indent=1, ensure_ascii=False)
        + "\n",
    )
    print(a.report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
