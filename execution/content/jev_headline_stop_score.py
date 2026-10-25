"""
description: Score LinkedIn card headlines with Jev on the panel's four scroll-stop questions (stop 0-4 scale, self_relevance, curiosity, generic nouls, mechanism choice) for the reader "founder / CEO / CSO / head of GTM scrolling LinkedIn on a phone". Reads the messages JSON; scores `headline` and, when present, `headline_original`, so before/after sits in one file. Never writes copy.
inputs: --repeats N (average over N calls, default 1); --messages <json with weeks[]> (default execution/content/prodcraft_50_week_messages.json); --weeks 1-10 (optional subset); --out <json path> (default stdout); --candidates <json {week: [headline,...]}> optional extra variants to score; --target "self_relevance>=0.6,generic<=0.4,stop>=3.0" pass rule; env OPENROUTER_API_KEY or OPENROUTER_API_TOEKN
outputs: <out> json {reader, questions, baseline[], weeks[{week, headline, scores, pass, original: {headline, scores}}], candidates{week: [...]}, summary}; one ledger row in .tmp/jev_ledger.jsonl (caller jev_headline_stop_score)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from execution.content.linkedin_weekly_cards import parse_weeks  # noqa: E402
from execution.modules import jev_client as jev  # noqa: E402

LEDGER = ROOT / ".tmp" / "jev_ledger.jsonl"
READER = "founder / CEO / CSO / head of GTM scrolling LinkedIn on a phone"
STOP_LEVELS = ["almost never stops anyone", "stops a few specialists", "stops the named reader sometimes",
               "stops the named reader often", "stops the named reader reliably and provokes a reaction"]
MECHANISMS = {
    "recognition": "the reader recognises a specific failure or situation they own",
    "curiosity": "an open loop or unanswered question pulls the reader in",
    "authority": "a credential, number or artefact signals the author knows",
    "contrarian": "it challenges an assumption the reader holds",
    "none": "no clear mechanism; it reads as a generic statement",
}
QUESTIONS = {
    "stop": jev.score(f"On a phone feed, how reliably does this headline stop the reader ({READER})?", STOP_LEVELS),
    "self_relevance": jev.noul("Does the reader immediately see that this is about a problem THEY personally own?",
                               "true when the reader (founder / CEO / CSO / head of GTM) sees their own team, deal, workflow or decision in the first words",
                               "false when it is about someone else's job, a general topic, or needs translation to apply to them"),
    "curiosity": jev.noul("Does it create an open loop?",
                          "true when the reader needs the post to close a gap the headline opened",
                          "false when the headline is complete on its own and nothing is left to find out"),
    "generic": jev.noul("Would this be at home in a generic AI-consultant feed?",
                        "true when it could be posted by any AI consultant without changing a word",
                        "false when it carries a specific situation, artefact, number or voice that a generic feed would not"),
    "mechanism": jev.choice("Which mechanism, if any, makes this headline stop the reader?", MECHANISMS),
}
DEFAULT_TARGET = "self_relevance>=0.6,generic<=0.4,stop>=3.0"


def parse_target(spec: str) -> list[tuple[str, str, float]]:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        for op in (">=", "<="):
            if op in part:
                k, v = part.split(op)
                out.append((k.strip(), op, float(v)))
                break
        else:
            raise argparse.ArgumentTypeError(f"--target: '{part}' needs >= or <=")
    return out


def passes(scores: dict, target: list[tuple[str, str, float]]) -> bool:
    return all((scores[k] >= v) if op == ">=" else (scores[k] <= v) for k, op, v in target)


def score_headlines(items: list[dict], repeats: int = 1) -> tuple[list[dict | None], float, str | None]:
    """items: [{week, headline}] -> parallel list of score dicts (None on Jev failure). repeats>1 averages the
    numeric answers over that many independent calls (Jev varies by ~0.1-0.2 call to call); mechanism = modal choice."""
    states = [{"reader": READER, "headline": it["headline"], "surface": "LinkedIn image post, headline is the first text in the image"} for it in items]
    results = jev.decide_many(states * max(1, repeats), QUESTIONS, workers=8)
    out, cost, err = [], 0.0, None
    n = len(items)
    for i in range(n):
        runs = [r for r in results[i::n] if not r.error and r.answers]
        cost += sum(r.cost_usd for r in results[i::n])
        if not runs:
            out.append(None)
            err = results[i].error or "empty answers"
            continue
        mech = max({r.choice("mechanism") for r in runs}, key=lambda m: sum(r.choice("mechanism") == m for r in runs))
        avg = lambda f: round(sum(f(r) for r in runs) / len(runs), 2)  # noqa: E731
        out.append({"stop": avg(lambda r: r.score("stop")), "self_relevance": avg(lambda r: r.noul("self_relevance")),
                    "curiosity": avg(lambda r: r.noul("curiosity")), "generic": avg(lambda r: r.noul("generic")),
                    "mechanism": mech, "mechanism_confidence": avg(lambda r: r.confidence("mechanism")), "runs": len(runs)})
    return out, cost, err


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--messages", default=str(ROOT / "execution/content/prodcraft_50_week_messages.json"))
    ap.add_argument("--weeks", default="", type=parse_weeks)
    ap.add_argument("--out", default="")
    ap.add_argument("--candidates", default="", help="json {week: [headline, ...]} extra variants to score")
    ap.add_argument("--target", default=DEFAULT_TARGET, type=parse_target)
    ap.add_argument("--repeats", type=int, default=1, help="average each headline over N Jev calls (3 recommended for a recorded run)")
    a = ap.parse_args()
    weeks = json.loads(Path(a.messages).read_text(encoding="utf-8"))["weeks"]
    if a.weeks:
        weeks = [w for w in weeks if w["week"] in a.weeks]
    cands = {int(k): v for k, v in json.loads(Path(a.candidates).read_text(encoding="utf-8")).items()} if a.candidates else {}

    items: list[dict] = []
    for w in weeks:
        items.append({"week": w["week"], "headline": w["headline"], "kind": "current"})
        if w.get("headline_original") and w["headline_original"] != w["headline"]:
            items.append({"week": w["week"], "headline": w["headline_original"], "kind": "original"})
        for c in cands.get(w["week"], []):
            items.append({"week": w["week"], "headline": c, "kind": "candidate"})
    scores, cost, err = score_headlines(items, a.repeats)
    jev.append_ledger({"caller": "jev_headline_stop_score", "cost_usd": round(cost, 6), "items": len(items) * a.repeats, "error": err}, LEDGER)

    rows, cand_out = [], {}
    for w in weeks:
        mine = [(it, s) for it, s in zip(items, scores) if it["week"] == w["week"]]
        cur = next(s for it, s in mine if it["kind"] == "current")
        orig = next((s for it, s in mine if it["kind"] == "original"), None)
        row = {"week": w["week"], "headline": w["headline"], "scores": cur, "pass": bool(cur and passes(cur, a.target))}
        if orig is not None or w.get("headline_original"):
            row["original"] = {"headline": w.get("headline_original", w["headline"]), "scores": orig if orig is not None else cur}
        rows.append(row)
        cl = [{"headline": it["headline"], "scores": s, "pass": bool(s and passes(s, a.target))} for it, s in mine if it["kind"] == "candidate"]
        if cl:
            cand_out[str(w["week"])] = sorted(cl, key=lambda x: -(x["scores"] or {}).get("self_relevance", 0))
    scored = [r for r in rows if r["scores"]]

    def rng(key: str, which: str = "scores") -> list[float] | None:
        vals = [r[which][key] if which == "scores" else r["original"]["scores"][key] for r in scored if which == "scores" or r.get("original")]
        return [min(vals), max(vals)] if vals else None

    summary = {"weeks": len(rows), "pass": sum(r["pass"] for r in rows), "target": a.target,
               "stop_range": rng("stop"), "self_relevance_range": rng("self_relevance"), "generic_range": rng("generic"),
               "original_stop_range": rng("stop", "original"), "original_self_relevance_range": rng("self_relevance", "original"),
               "original_generic_range": rng("generic", "original"), "jev_cost_usd": round(cost, 6), "jev_error": err}
    doc = {"reader": READER, "stop_levels": STOP_LEVELS, "weeks": rows, "candidates": cand_out, "summary": summary}
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
        print(json.dumps(summary, indent=2))
    else:
        print(text)
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
