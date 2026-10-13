#!/usr/bin/env python3
"""
jev_recruitment_icp_filter.py
description: Flag every lead row as on-target (recruitment / staffing / HR company or consultancy) or off-target
             with Jev (typed decisions, no text generation). Adds `icp_category`, `icp_on_target`,
             `icp_confidence`, `icp_reason`. Splits each input CSV into `{name}.csv` (on-target) and
             `{name}__off_target.csv` (flagged rows, kept for review) so launch files hold only the ICP.
inputs:  --input one or more CSVs (Apollo-style columns); --outdir; --threshold (noul cut, default 0.5);
         env OPENROUTER_API_KEY (cloud alias OPENROUTER_API_TOEKN)
outputs: {outdir}/{stem}.csv, {outdir}/{stem}__off_target.csv, {outdir}/icp_summary.json, ledger row
usage:   python3 execution/gtm_icp_filters/jev_recruitment_icp_filter.py --input .tmp/x/final/san_diego.csv --outdir .tmp/x/icp
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from execution.modules import jev_client as jev  # noqa: E402

CATEGORIES = {
    "staffing_recruiting": "A staffing agency, recruitment firm, executive search firm, RPO or talent-acquisition "
                           "service that places or sources candidates for client companies.",
    "hr_consulting": "An HR / people-operations consultancy, fractional HR, PEO, HR outsourcing, compensation, "
                     "benefits or workforce consulting firm serving other businesses.",
    "hr_tech": "A software product (SaaS / platform) sold to recruiters or HR teams: ATS, sourcing tools, "
               "assessments, payroll or HR software. The company sells software, not a service.",
    "other_consulting": "A consultancy whose core service is NOT HR or recruiting (IT, management, marketing, "
                        "finance, strategy, engineering services).",
    "other": "Anything else: VC, healthcare provider, events, media, research, education, operating company "
             "that merely has an HR department, personal coaching, unrelated business.",
}

QUESTIONS = {
    "category": jev.choice("What kind of company is this?", CATEGORIES),
    "on_target": jev.noul(
        "Is this company a recruitment, staffing, executive search, HR consulting or HR outsourcing firm "
        "(a services business whose clients pay it to find people or run HR)?",
        "true when the company's own business is placing candidates or delivering HR services to clients, "
        "including IT staffing firms tagged as Information Technology",
        "false when it is a software product, a VC, an operating company with an internal HR team, a coach, "
        "an unrelated consultancy or any non-HR business",
    ),
}

STATE_FIELDS = ["Company Name", "Industry", "Keywords", "Company Short Description", "Company SEO Description",
                "Headline", "Title"]


def state_for(r: dict) -> dict:
    s = {}
    for f in STATE_FIELDS:
        v = (r.get(f) or "").strip()
        if v:
            s[f.lower().replace(" ", "_")] = v[:1200]
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="classify only the first N rows per file (testing)")
    args = ap.parse_args()
    for alias in ("OPENROUTER_API_TOKEN", "OPENROUTER_API_TOEKN"):
        if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get(alias):
            os.environ["OPENROUTER_API_KEY"] = os.environ[alias]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    summary = {"threshold": args.threshold, "files": {}, "cost_usd": 0.0, "jev_errors": 0}
    cache: dict[str, jev.JevResult] = {}  # one Jev call per company, reused across rows

    for path in args.input:
        p = Path(path)
        with open(p, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        if args.limit:
            rows = rows[: args.limit]

        # unique companies (by name + description) → one Jev call each
        keys, states = [], []
        for r in rows:
            k = (r.get("Company Name") or "").strip().lower()
            if k not in cache and k not in keys:
                keys.append(k)
                states.append(state_for(r))
        results = jev.decide_many(states, QUESTIONS, workers=args.workers) if states else []
        for k, res in zip(keys, results):
            cache[k] = res
            summary["cost_usd"] += res.cost_usd
            if res.error:
                summary["jev_errors"] += 1

        on, off = [], []
        for r in rows:
            res = cache[(r.get("Company Name") or "").strip().lower()]
            if res.error:
                # fail open: rely on the scraper's own Industry tag so no row is silently dropped
                ind = (r.get("Industry") or "").lower()
                r["icp_category"] = "jev_error"
                r["icp_confidence"] = ""
                target = "staffing" in ind or "recruit" in ind or "human resources" in ind
                r["icp_reason"] = f"jev error, industry fallback: {r.get('Industry')}"
            else:
                cat = res.choice("category")
                p_true = res.noul("on_target")
                r["icp_category"] = cat
                r["icp_confidence"] = f"{p_true:.2f}"
                target = p_true >= args.threshold and cat in ("staffing_recruiting", "hr_consulting")
                r["icp_reason"] = f"{cat} (p_on_target={p_true:.2f}, choice_conf={res.confidence('category'):.2f})"
            r["icp_on_target"] = "yes" if target else "no"
            (on if target else off).append(r)

        out_fields = fields + [c for c in ("icp_category", "icp_on_target", "icp_confidence", "icp_reason")
                               if c not in fields]
        for suffix, rs in (("", on), ("__off_target", off)):
            op = outdir / f"{p.stem}{suffix}.csv"
            with open(op, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
                w.writeheader()
                w.writerows(rs)
        summary["files"][p.name] = {
            "rows": len(rows), "on_target": len(on), "off_target": len(off),
            "categories": dict(Counter(r["icp_category"] for r in rows)),
            "off_target_industries": dict(Counter(r.get("Industry") for r in off).most_common(10)),
        }

    (outdir / "icp_summary.json").write_text(json.dumps(summary, indent=2))
    jev.append_ledger({"script": "jev_recruitment_icp_filter", "cost_usd": summary["cost_usd"],
                       "companies": len(cache), "errors": summary["jev_errors"]})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
