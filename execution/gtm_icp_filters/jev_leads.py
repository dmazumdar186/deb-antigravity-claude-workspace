"""Qualify, enrich-check and route B2B leads with Jev (TypeSafe decisions via OpenRouter).

description: One script, seven lead-pipeline scenarios, ONE Jev call per row each:
             qualify (ICP fit, reach-out, persona, timing -> go/hold/skip), signals (funding,
             hiring, job change -> contact/watch/none), hygiene (clean/fix/drop), suppress
             (customer/competitor/partner -> suppress/allow), replies (cold-email reply intent),
             inbound (form-fill routing) and diff (what changed since a snapshot -> contact/ignore).
             Decision rules are deterministic code over Jev's typed answers; low-confidence rows
             are flagged jev_review. Directive: directives/gtm_icp_filters/jev_leads.md
inputs: <scenario> --input CSV|JSON list of dicts; --icp profile JSON
        (execution/gtm_icp_filters/icp_profiles/_template.json); --output (default
        .tmp/jev_leads_<scenario>.json); --csv-out; --md; --min-confidence (0.6); --workers (8);
        --limit; --dry-run; --validate labels.csv (id,label) [--validate-question NAME];
        --snapshot prev.csv|json (diff only); --only-pass (csv-out keeps go/contact/sales).
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: JSON {summary, rows, validation}; optional CSV (input cols + jev_*) and markdown top-25
         table; stdout summary; ledger row in .tmp/jev_ledger.jsonl (caller "jev_leads").
         Exit 0 ok, 1 bad input, 2 missing OpenRouter key (unless --dry-run).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.modules import jev_client  # noqa: E402
from execution.modules.jev_client import choice, noul, score  # noqa: E402

SCENARIOS = ("qualify", "signals", "hygiene", "suppress", "replies", "inbound", "diff")
DEFAULT_MIN_CONFIDENCE = 0.6
MAX_FIELD_CHARS = 1200
PASS_DECISIONS = {"go", "contact", "sales"}
DEFAULT_PERSONAS = {
    "economic_buyer": "senior leader who owns the budget for this purchase",
    "champion": "hands-on manager who would push for the purchase internally",
    "user": "individual contributor who would use the product day to day",
}
CONTEXT_FIELDS = {
    "qualify": ("offer", "icp", "personas", "exclusions", "timing"),
    "signals": ("icp", "signals"),
    "hygiene": (),
    "suppress": ("customers", "competitors", "exclusions"),
    "replies": ("offer",),
    "inbound": ("offer", "icp", "competitors"),
    "diff": ("offer", "icp", "personas"),
}
ID_KEYS = ("id", "email", "lead_id")


# ---- inputs ------------------------------------------------------------------------------

def load_rows(path: Path) -> list[dict[str, Any]]:
    """CSV or JSON list of dicts (a dict with a 'leads'/'rows' list is accepted too)."""
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return [dict(r) for r in csv.DictReader(fh)]
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("leads") or data.get("rows") or []
    if not isinstance(data, list):
        raise ValueError("input must be a JSON list or CSV")
    return [r for r in data if isinstance(r, dict)]


def load_icp(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("ICP profile must be a JSON object")
    return data


def row_id(row: dict[str, Any], idx: int) -> str:
    for k in ID_KEYS:
        v = row.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return str(idx)


def _clean_fields(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k is None or v is None or str(k).startswith("_") or str(k).startswith("jev_"):
            continue
        s = v if isinstance(v, (int, float, bool)) else str(v).strip()
        if s == "":
            continue
        out[str(k)] = s[:MAX_FIELD_CHARS] if isinstance(s, str) else s
    return out


def fingerprint(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(k) or "").strip().lower() for k in ("name", "company", "title"))


def _person_key(row: dict[str, Any]) -> str:
    """Stable identity across snapshots: email, id, linkedin, else name."""
    for k in ("email", "id", "linkedin", "linkedin_url", "name"):
        v = str(row.get(k) or "").strip().lower()
        if v:
            return f"{k}:{v}"
    return ""


def diff_rows(rows: list[dict[str, Any]], snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep new rows and rows whose fingerprint changed; attach the old row under `_old`."""
    prev = {_person_key(r): r for r in snapshot if _person_key(r)}
    out = []
    for r in rows:
        old = prev.get(_person_key(r))
        if old is None:
            out.append({**r, "_old": None, "_diff": "new"})
        elif fingerprint(old) != fingerprint(r):
            out.append({**r, "_old": old, "_diff": "changed"})
    return out


# ---- questions / state -------------------------------------------------------------------

def build_questions(scenario: str, icp: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if scenario == "qualify":
        personas = dict(icp.get("personas") or DEFAULT_PERSONAS)
        personas["none"] = "this person matches none of the buyer personas"
        return {
            "icp_fit": score("How well does this lead match the ideal customer profile in the context?",
                             ["no_fit", "weak_fit", "good_fit", "strong_fit"]),
            "reach_out": noul("Should we contact this lead now, given the ICP, offer, exclusions and timing?",
                              true="a good prospect we should contact now",
                              false="excluded, off-ICP, bad timing or otherwise not worth contacting now"),
            "persona": choice("Which buyer persona does this person fit?", personas),
            "timing_ok": noul("Is now a reasonable time to reach out, per the timing guidance?",
                              true="nothing suggests now is a bad time",
                              false="a timing rule says wait (holiday, fundraise, just churned ...)"),
            "enough_context": noul("Are there enough facts about this lead to write a personalised first line?",
                                   true="specific facts about the person or company are present",
                                   false="only generic fields; a personalised line would be guesswork"),
        }
    if scenario == "signals":
        sig = icp.get("signals") or {}
        return {
            "funding_recent": noul("Did the company raise funding recently?",
                                   true=sig.get("funding", "raised a round in the last 6 months"),
                                   false="no recent funding mentioned"),
            "hiring_outbound": noul("Is the company hiring for outbound / prospect-facing roles?",
                                    true=sig.get("hiring", "hiring SDRs, AEs or sales development leaders"),
                                    false="no such hiring, or only non-prospecting roles"),
            "job_change": noul("Did this person recently change job into the buying function?",
                               true=sig.get("job_change", "new, more senior buying-function role in last 90 days"),
                               false="no recent relevant job change"),
            "promotion_same_company": noul("Was this person recently promoted within the same company?",
                                           true="recent promotion at the same company",
                                           false="no recent promotion mentioned"),
            "signal_strength": score("Overall, how strong are the buying signals for contacting this lead now?",
                                     ["none", "weak", "moderate", "strong"]),
        }
    if scenario == "hygiene":
        return {
            "first_name_clean": noul("Is the first name a clean, correctly-cased human first name?",
                                     true="a usable first name as-is",
                                     false="missing, an initial, all caps, emoji, title or junk"),
            "company_name_clean": noul("Is the company name clean enough to use in an email?",
                                       true="usable as-is (no Inc/LLC clutter, no junk)",
                                       false="missing, legal suffixes, all caps, a URL or junk"),
            "title_is_person_title": noul("Is the title a real job title held by a person?",
                                          true="a real job title",
                                          false="missing, a company tagline, a sentence or junk"),
            "email_looks_work": noul("Does the email look like a work address at the company?",
                                     true="a work domain matching the company",
                                     false="missing, free-mail, role inbox or mismatched domain"),
            "row_usable": noul("Is this row usable for outreach at all?",
                               true="enough valid data to contact a real person",
                               false="junk, test or empty row"),
        }
    if scenario == "suppress":
        return {
            "relation": choice("What is this lead's relationship to us, given the customer list and competitor description?", {
                "customer": "an existing customer on the list (or the same company)",
                "competitor": "a competitor or works for one",
                "partner": "a partner, reseller or integration partner",
                "vendor": "a vendor or supplier of ours",
                "bad_actor": "abusive, fraudulent or previously asked never to be contacted",
                "none": "no special relationship; a normal prospect",
            }),
            "do_not_contact": noul("Should we never contact this lead (suppression list or exclusions)?",
                                   true="matches a customer, competitor, exclusion or do-not-contact rule",
                                   false="fine to contact"),
        }
    if scenario == "replies":
        return {
            "intent": choice("What is the intent of this reply to our cold email?", {
                "interested": "positive, wants to learn more",
                "meeting_requested": "asks for or agrees to a call/meeting",
                "question": "asks a question before deciding",
                "not_now": "maybe later, bad timing",
                "not_interested": "declines",
                "unsubscribe": "asks to be removed or stop emailing",
                "wrong_person": "not the right contact, may refer someone",
                "out_of_office": "auto-reply: away or on leave",
                "bounce": "delivery failure or mailbox does not exist",
                "competitor": "sender is a competitor or pitching their own offer",
                "none": "none of the above or unreadable",
            }),
            "sentiment": score("What is the sentiment of this reply?", ["negative", "neutral", "positive"]),
            "needs_human": noul("Does this reply need a human to answer?",
                                true="a person should read and respond",
                                false="can be handled automatically or ignored"),
            "unsubscribe": noul("Does the sender ask to stop receiving emails?",
                                true="asks to unsubscribe or stop", false="no opt-out request"),
        }
    if scenario == "inbound":
        return {
            "real_buyer": noul("Is this inbound from a real potential buyer of our offer?",
                               true="a genuine prospect with a plausible need",
                               false="student, job seeker, vendor pitch, spam or tyre-kicker"),
            "spam": noul("Is this spam or junk?", true="spam, bot or junk", false="a real message"),
            "competitor": noul("Is this from a competitor?", true="a competitor or their agent", false="not a competitor"),
            "urgency": score("How urgent is this inbound?", ["low", "medium", "high"]),
            "budget_signal": noul("Does the message signal budget or buying authority?",
                                  true="mentions budget, timeline, team size or decision power",
                                  false="no budget or authority signal"),
            "route": choice("Where should this inbound go?", {
                "sales": "a qualified buyer; route to sales now",
                "nurture": "real but early or small; add to nurture",
                "ignore": "spam, competitor, job seeker or irrelevant",
                "none": "cannot tell",
            }),
        }
    if scenario == "diff":
        return {
            "change_type": choice("Comparing the old and new snapshot of this person, what changed?", {
                "new_company": "moved to a different company",
                "promotion_same_company": "more senior title at the same company",
                "lateral_move": "different title at a similar level",
                "left_buying_function": "moved out of the role that buys our offer",
                "none": "no meaningful change or a brand-new record",
            }),
            "now_worth_contacting": noul("Given the change and our ICP, is this person now worth contacting?",
                                         true="the change makes outreach timely and relevant",
                                         false="not worth contacting because of this change"),
        }
    raise ValueError(f"unknown scenario: {scenario}")


def row_state(row: dict[str, Any], scenario: str, icp: dict[str, Any]) -> dict[str, Any]:
    ctx = {k: icp[k] for k in CONTEXT_FIELDS[scenario] if icp.get(k)}
    state: dict[str, Any] = {}
    if ctx:
        state["context"] = ctx
    if scenario == "diff":
        old = row.get("_old")
        state["lead"] = {"new": _clean_fields(row), "old": _clean_fields(old) if old else None}
    else:
        state["lead"] = _clean_fields(row)
    return state


# ---- decisions ---------------------------------------------------------------------------

def _choice_conf(res: jev_client.JevResult, q: str) -> float:
    c = res.confidence(q)
    if not c:
        c = res.probabilities(q).get(res.choice(q), 0.0)
    return c


def decide_row(res: jev_client.JevResult, scenario: str, qs: dict[str, dict[str, Any]],
               minc: float) -> dict[str, Any]:
    """Return jev_* columns for one row."""
    out: dict[str, Any] = {}
    if not res.ok:
        for q in qs:
            out[f"jev_{q}"] = None
            if qs[q]["type"] == "choice":
                out[f"jev_{q}_conf"] = 0.0
        out.update({"jev_decision": "error", "jev_confidence": 0.0, "jev_review": True,
                    "jev_error": res.error or "no answers"})
        return out
    confs = []
    for q, spec in qs.items():
        t = spec["type"]
        if t == "choice":
            c = _choice_conf(res, q)
            confs.append(c)
            out[f"jev_{q}"] = res.choice(q)
            out[f"jev_{q}_conf"] = round(c, 4)
        elif t == "noul":
            out[f"jev_{q}"] = round(res.noul(q), 4)
        else:
            out[f"jev_{q}"] = round(res.score(q), 4)
    conf = min(confs) if confs else 1.0
    g = lambda q: out[f"jev_{q}"]  # noqa: E731
    miss = conf < minc
    if scenario == "qualify":
        if g("reach_out") >= minc and g("icp_fit") >= 2 and g("persona") != "none" \
                and out["jev_persona_conf"] >= minc:
            d = "go"
        elif g("reach_out") < 0.3 or g("icp_fit") < 1:
            d = "skip"
        else:
            d = "hold"
    elif scenario == "signals":
        nouls = [g(q) for q in ("funding_recent", "hiring_outbound", "job_change", "promotion_same_company")]
        s = g("signal_strength")
        if s >= 2 and any(v >= minc for v in nouls):
            d = "contact"
        elif 1 <= s < 2:
            d = "watch"
        else:
            d = "none"
    elif scenario == "hygiene":
        flags = [g(q) for q in ("first_name_clean", "company_name_clean", "title_is_person_title",
                                "email_looks_work")]
        if g("row_usable") < 0.5:
            d = "drop"
        elif any(v < minc for v in flags):
            d = "fix"
        else:
            d = "clean"
    elif scenario == "suppress":
        rel_hit = g("relation") in {"customer", "competitor", "bad_actor"} and out["jev_relation_conf"] >= minc
        d = "suppress" if g("do_not_contact") >= minc or rel_hit else "allow"
    elif scenario == "replies":
        d = "review" if out["jev_intent_conf"] < minc else g("intent")
    elif scenario == "inbound":
        d = "review" if out["jev_route_conf"] < minc else g("route")
    else:  # diff
        d = "contact" if g("now_worth_contacting") >= minc else "ignore"
    out.update({"jev_decision": d, "jev_confidence": round(conf, 4),
                "jev_review": miss or d == "review", "jev_error": ""})
    return out


def apply_results(rows: list[dict[str, Any]], results: list[jev_client.JevResult], scenario: str,
                  minc: float, icp: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    qs = build_questions(scenario, icp or {})
    out = []
    for i, (row, res) in enumerate(zip(rows, results)):
        base = {k: v for k, v in row.items() if k not in ("_old",)}
        if row.get("_old"):
            base["_old_fingerprint"] = fingerprint(row["_old"])
        base.setdefault("id", row_id(row, i))
        base.update(decide_row(res, scenario, qs, minc))
        base["jev_cost_usd"] = res.cost_usd
        out.append(base)
    return out


def fake_results(n: int, qs: dict[str, dict[str, Any]]) -> list[jev_client.JevResult]:
    """Deterministic offline answers for --dry-run (first non-none option, high noul, top score)."""
    answers: dict[str, Any] = {}
    for q, spec in qs.items():
        if spec["type"] == "choice":
            opt = next((k for k in spec["criteria"] if k != "none"), "none")
            answers[q] = {"choice": opt, "confidence": 0.9, "probabilities": {opt: 0.9}}
        elif spec["type"] == "noul":
            answers[q] = {"noul": 0.8}
        else:
            answers[q] = {"score": float(len(spec["criteria"]) - 1)}
    return [jev_client.JevResult(answers=dict(answers), model="dry-run") for _ in range(n)]


# ---- validation / io ---------------------------------------------------------------------

def validate(rows: list[dict[str, Any]], labels_path: Path, question: str = "decision") -> dict[str, Any]:
    with open(labels_path, encoding="utf-8-sig", newline="") as fh:
        labels = {str(r["id"]).strip(): str(r["label"]).strip() for r in csv.DictReader(fh) if r.get("id")}
    col = f"jev_{question}"
    scored = correct = 0
    mismatches = []
    for i, r in enumerate(rows):
        truth = labels.get(str(r.get("id")))
        if truth is None:
            truth = labels.get(str(i))
        if truth is None:
            continue
        scored += 1
        got = str(r.get(col) if r.get(col) is not None else "")
        if got == truth:
            correct += 1
        else:
            mismatches.append({"id": r.get("id"), "expected": truth, "got": got,
                               "confidence": r.get("jev_confidence")})
    return {"question": question, "scored": scored, "correct": correct,
            "accuracy": round(correct / scored, 4) if scored else 0.0, "mismatches": mismatches}


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols and not k.startswith("_"):
                cols.append(k)
    cols = [c for c in cols if not c.startswith("jev_")] + [c for c in cols if c.startswith("jev_")]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_md(rows: list[dict[str, Any]], path: Path, scenario: str) -> None:
    lines = [f"# jev_leads: {scenario}", "", "| id | name | company | decision | confidence | review |",
             "|---|---|---|---|---|---|"]
    for r in rows[:25]:
        lines.append(f"| {r.get('id', '')} | {r.get('name', '')} | {r.get('company', '')} | "
                     f"{r.get('jev_decision')} | {r.get('jev_confidence')} | {r.get('jev_review')} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---- CLI ---------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scenario", choices=SCENARIOS)
    ap.add_argument("--input", required=True)
    ap.add_argument("--icp")
    ap.add_argument("--output")
    ap.add_argument("--csv-out")
    ap.add_argument("--md")
    ap.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--validate", help="CSV id,label")
    ap.add_argument("--validate-question", default="decision")
    ap.add_argument("--snapshot", help="previous export (diff only)")
    ap.add_argument("--only-pass", action="store_true", help="csv-out keeps decision in go/contact/sales")
    args = ap.parse_args(argv)
    s = args.scenario

    try:
        rows = load_rows(Path(args.input))
        icp = load_icp(Path(args.icp) if args.icp else None)
        if s == "diff":
            if not args.snapshot:
                raise ValueError("diff needs --snapshot")
            rows = diff_rows(rows, load_rows(Path(args.snapshot)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.limit > 0:
        rows = rows[: args.limit]
    for i, r in enumerate(rows):
        r.setdefault("id", row_id(r, i))

    if not args.dry_run and not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    qs = build_questions(s, icp)
    states = [row_state(r, s, icp) for r in rows]
    t0 = time.perf_counter()
    if args.dry_run:
        print(json.dumps({"scenario": s, "rows": len(rows), "first_state": states[0] if states else None,
                          "questions": qs}, indent=2, ensure_ascii=False, default=str))
        results = fake_results(len(rows), qs)
    else:
        results = jev_client.decide_many(states, qs, workers=args.workers) if states else []
    wall = round(time.perf_counter() - t0, 2)
    out_rows = apply_results(rows, results, s, args.min_confidence, icp)

    errors = sum(1 for r in out_rows if r["jev_error"])
    cost = round(sum(float(r.get("jev_cost_usd") or 0) for r in out_rows), 6)
    model = next((res.model for res in results if res.model), "")
    summary = {"scenario": s, "rows": len(out_rows),
               "decisions": dict(Counter(r["jev_decision"] for r in out_rows)),
               "cost_usd": cost, "wall_s": wall, "errors": errors, "model": model,
               "review": sum(1 for r in out_rows if r["jev_review"]), "dry_run": args.dry_run}
    validation = None
    if args.validate:
        try:
            validation = validate(out_rows, Path(args.validate), args.validate_question)
        except (OSError, KeyError) as exc:
            print(f"error: validate: {exc}", file=sys.stderr)
            return 1

    out_path = Path(args.output) if args.output else WORKSPACE / ".tmp" / f"jev_leads_{s}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": summary, "rows": out_rows, "validation": validation},
                                   indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if args.csv_out:
        keep = [r for r in out_rows if r["jev_decision"] in PASS_DECISIONS] if args.only_pass else out_rows
        write_csv(keep, Path(args.csv_out))
    if args.md:
        write_md(out_rows, Path(args.md), s)

    print(f"{s}: {len(out_rows)} rows in {wall} s for ${cost:.5f} ({errors} errors, "
          f"{summary['review']} review)")
    print("  decisions: " + ", ".join(f"{k}={v}" for k, v in sorted(summary["decisions"].items())))
    if validation:
        print(f"  validation ({validation['question']}): {validation['correct']}/{validation['scored']} "
              f"= {validation['accuracy']:.1%}")
        for m in validation["mismatches"]:
            print(f"    id={m['id']} expected={m['expected']} got={m['got']}")
    print(f"  wrote {out_path}")
    if not args.dry_run:
        jev_client.append_ledger({"caller": "jev_leads", "scenario": s, "items": len(out_rows),
                                  "cost_usd": cost, "wall_s": wall, "errors": errors},
                                 path=WORKSPACE / ".tmp" / "jev_ledger.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
