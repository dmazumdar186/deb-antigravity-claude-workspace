"""Score and profile a SaaS customer base for churn risk with Jev (TypeSafe via OpenRouter).

description: Reads a customer export (tenure, plan, MRR, usage, tickets, NPS, payment status,
             cancel notes) and puts each customer in a health group (healthy, needs_attention,
             at_risk, churning, insufficient_data) with a 90-day churn probability, an
             expansion probability and a primary reason, in ONE Jev call per customer.
             Code-side: priority = churn_90d x MRR (revenue at risk), sorted descending;
             low-confidence rows flagged `review`. Emits a "reach out this week" list.
             Directive: directives/gtm_icp_filters/jev_customer_health.md
inputs: --input CSV or JSON list of customers (flexible columns: id/email/name, plan, mrr,
        tenure_days|signup_date, last_login_days|last_active, logins_30d, feature_usage,
        support_tickets_30d, nps, payment_failed, cancel_intent|notes; unknown columns
        passed through); --min-confidence (0.55); --workers (8); --limit; --dry-run;
        --validate labels.csv (id,health); --top (20); --sheet-id/--tab (optional).
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: --output JSON (default <input>.health.json) with summary + rows sorted by priority;
         optional --csv-out, --md reach-out list; stdout summary (counts per group, MRR at
         risk, expansion candidates, cost, wall time); ledger row in .tmp/jev_ledger.jsonl
         (caller "jev_customer_health"); optional Google Sheet append.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

HEALTH_GROUPS: dict[str, str] = {
    "healthy": "engaged, using the product regularly, no billing or cancel signals",
    "needs_attention": "some warning signs (dropping usage, a few tickets, lukewarm NPS) but not yet at risk",
    "at_risk": "strong churn signals: low or falling usage, support pain, billing trouble or talk of cancelling",
    "churning": "has already cancelled, asked to cancel, or is clearly on the way out",
    "insufficient_data": "too little information to judge this customer's health",
}
REASONS: dict[str, str] = {
    "low_usage": "rarely logs in or barely uses core features",
    "support_pain": "many support tickets, unresolved problems or frustration with the product",
    "billing_issue": "failed payment, card declined or invoice dispute",
    "explicit_cancel_intent": "said or noted they want to cancel, downgrade or leave",
    "price_sensitivity": "complains about price or asks for a discount",
    "champion_left": "the main user or internal champion left the company",
    "none": "no notable risk driver",
}
DEFAULT_MIN_CONFIDENCE = 0.55
EXPANSION_THRESHOLD = 0.5
MAX_TEXT_CHARS = 2_000

# canonical field -> accepted source column names (lower-cased)
ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "customer_id", "account_id"),
    "email": ("email", "contact_email"),
    "name": ("name", "company", "customer", "account_name"),
    "plan": ("plan", "tier", "subscription"),
    "mrr": ("mrr", "monthly_revenue", "revenue"),
    "tenure_days": ("tenure_days", "tenure"),
    "signup_date": ("signup_date", "created_at", "start_date"),
    "last_login_days": ("last_login_days", "days_since_login"),
    "last_active": ("last_active", "last_login", "last_seen"),
    "logins_30d": ("logins_30d", "logins"),
    "feature_usage": ("feature_usage", "usage"),
    "support_tickets_30d": ("support_tickets_30d", "tickets_30d", "tickets"),
    "nps": ("nps", "nps_score"),
    "payment_failed": ("payment_failed", "failed_payment"),
    "cancel_intent": ("cancel_intent", "cancellation"),
    "notes": ("notes", "note", "comments"),
}
_NUMERIC = ("mrr", "tenure_days", "last_login_days", "logins_30d", "support_tickets_30d", "nps")


# ---- inputs ------------------------------------------------------------------------------

def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def _bool(v: Any) -> bool | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "t"):
        return True
    if s in ("0", "false", "no", "n", "f"):
        return False
    return None


def _days_since(v: Any, today: date) -> int | None:
    if not v:
        return None
    s = str(v).strip()[:10]
    try:
        return (today - datetime.strptime(s, "%Y-%m-%d").date()).days
    except ValueError:
        return None


def normalize(raw: dict[str, Any], idx: int, today: date | None = None) -> dict[str, Any]:
    """Map flexible source columns to canonical fields; pass unknown non-empty columns through."""
    today = today or date.today()
    lower = {str(k).strip().lower(): v for k, v in raw.items() if k is not None}
    used: set[str] = set()
    out: dict[str, Any] = {}
    for canon, names in ALIASES.items():
        for n in names:
            if n in lower and lower[n] not in (None, ""):
                out[canon] = lower[n]
                used.add(n)
                break
        for n in names:
            used.add(n)
    for k in _NUMERIC:
        if k in out:
            num = _num(out[k])
            if num is None:
                out.pop(k)
            else:
                out[k] = int(num) if num.is_integer() and k != "mrr" else num
    if "feature_usage" in out and _num(out["feature_usage"]) is not None:
        out["feature_usage"] = _num(out["feature_usage"])
    if "payment_failed" in out:
        b = _bool(out["payment_failed"])
        if b is None:
            out.pop("payment_failed")
        else:
            out["payment_failed"] = b
    if "tenure_days" not in out and "signup_date" in out:
        d = _days_since(out["signup_date"], today)
        if d is not None:
            out["tenure_days"] = d
    if "last_login_days" not in out and "last_active" in out:
        d = _days_since(out["last_active"], today)
        if d is not None:
            out["last_login_days"] = d
    for k in ("cancel_intent", "notes"):
        if k in out:
            out[k] = str(out[k])[:MAX_TEXT_CHARS]
    for k, v in lower.items():
        if k not in used and v not in (None, ""):
            out[k] = v
    out["id"] = str(out.get("id") or out.get("email") or out.get("name") or idx + 1)
    return out


def load_customers(path: Path, today: date | None = None) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8", newline="") as fh:
            rows: Any = [dict(r) for r in csv.DictReader(fh)]
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rows = data.get("customers", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("input must be a JSON list or CSV")
    return [normalize(r, i, today) for i, r in enumerate(rows) if isinstance(r, dict)]


# ---- questions ---------------------------------------------------------------------------

def build_questions() -> dict[str, dict[str, Any]]:
    return {
        "health": jev_client.choice(
            "Which health group does this SaaS customer belong in, given tenure, plan, usage, "
            "support, NPS, billing and any cancellation notes?", HEALTH_GROUPS),
        "churn_90d": jev_client.noul(
            "Is this customer likely to cancel within the next 90 days?",
            true="likely to cancel or not renew within 90 days",
            false="likely to still be a paying customer in 90 days",
        ),
        "expansion": jev_client.noul(
            "Does this customer show signals of upgrading or expanding (more seats, higher plan, "
            "hitting limits, asking about premium features)?",
            true="shows upgrade or expansion signals",
            false="no upgrade or expansion signals",
        ),
        "reason": jev_client.choice(
            "What is the primary driver of this customer's risk (choose none if healthy)?", REASONS),
    }


def customer_state(c: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in c.items() if v not in (None, "")}


# ---- scoring -----------------------------------------------------------------------------

def priority(churn: float | None, mrr: Any) -> float:
    """Revenue at risk = churn probability x MRR (0 when either is missing)."""
    m = _num(mrr)
    if churn is None or m is None:
        return 0.0
    return round(float(churn) * m, 2)


def score_row(c: dict[str, Any], res: jev_client.JevResult, min_confidence: float) -> dict[str, Any]:
    row: dict[str, Any] = {"id": c["id"], "name": c.get("name", ""), "email": c.get("email", ""),
                           "plan": c.get("plan", ""), "mrr": _num(c.get("mrr")) or 0.0}
    if not res.ok:
        row.update({"health": "", "confidence": 0.0, "probabilities": {}, "churn_90d": None,
                    "expansion": None, "reason": "", "priority": 0.0, "review": True,
                    "cost_usd": res.cost_usd, "error": res.error or "no answers"})
        return row
    health = res.choice("health")
    conf = res.confidence("health")
    probs = res.probabilities("health")
    if not conf and probs:
        conf = probs.get(health, 0.0)
    churn = res.noul("churn_90d")
    row.update({
        "health": health,
        "confidence": round(conf, 4),
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "churn_90d": round(churn, 4),
        "expansion": round(res.noul("expansion"), 4),
        "reason": res.choice("reason"),
        "priority": priority(churn, row["mrr"]),
        "review": conf < min_confidence,
        "cost_usd": res.cost_usd,
        "error": None,
    })
    return row


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (-float(r.get("priority") or 0), -float(r.get("churn_90d") or 0)))


def score_customers(customers: list[dict[str, Any]], *, min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                    workers: int = 8) -> list[dict[str, Any]]:
    results = jev_client.decide_many([customer_state(c) for c in customers], build_questions(),
                                     workers=workers)
    return sort_rows([score_row(c, r, min_confidence) for c, r in zip(customers, results)])


# ---- validation --------------------------------------------------------------------------

def load_labels(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8", newline="") as fh:
        return {str(r["id"]).strip(): str(r["health"]).strip()
                for r in csv.DictReader(fh) if r.get("id")}


def validate(rows: list[dict[str, Any]], labels: dict[str, str]) -> dict[str, Any]:
    scored = correct = 0
    mismatches: list[dict[str, Any]] = []
    for r in rows:
        truth = labels.get(str(r["id"]))
        if truth is None:
            continue
        scored += 1
        if r.get("health") == truth:
            correct += 1
        else:
            mismatches.append({"id": r["id"], "expected": truth, "got": r.get("health", ""),
                               "confidence": r.get("confidence", 0.0)})
    return {"scored": scored, "correct": correct,
            "accuracy": (correct / scored) if scored else 0.0, "mismatches": mismatches}


# ---- summary / io ------------------------------------------------------------------------

def summarize(rows: list[dict[str, Any]], wall_s: float) -> dict[str, Any]:
    by_health: dict[str, int] = {}
    for r in rows:
        k = r.get("health") or "(error)"
        by_health[k] = by_health.get(k, 0) + 1
    return {"count": len(rows), "by_health": by_health,
            "mrr_at_risk": round(sum(float(r.get("priority") or 0) for r in rows), 2),
            "expansion_candidates": [r["id"] for r in rows
                                     if (r.get("expansion") or 0) >= EXPANSION_THRESHOLD],
            "review": sum(1 for r in rows if r.get("review")),
            "errors": sum(1 for r in rows if r.get("error")),
            "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in rows), 6),
            "wall_s": round(wall_s, 2)}


def print_summary(s: dict[str, Any]) -> None:
    print(f"Scored {s['count']} customers in {s['wall_s']} s for ${s['cost_usd']:.5f} "
          f"({s['errors']} errors, {s['review']} flagged review)")
    print("  by health:   " + ", ".join(f"{k}={v}" for k, v in sorted(s["by_health"].items())))
    print(f"  MRR at risk: ${s['mrr_at_risk']:,.2f}")
    print(f"  expansion:   {', '.join(s['expansion_candidates']) or '(none)'}")


def reach_out_lines(rows: list[dict[str, Any]], top: int = 20) -> list[str]:
    """Rows already sorted by priority; healthy customers are left off the list."""
    lines = []
    for r in rows:
        if len(lines) >= top:
            break
        if r.get("error") or r.get("health") == "healthy":
            continue
        who = r.get("name") or r.get("email") or r["id"]
        flag = " (review)" if r.get("review") else ""
        lines.append(f"{len(lines) + 1}. **{who}** [{r['id']}] — {r.get('health')}{flag}, "
                     f"churn {float(r.get('churn_90d') or 0):.0%}, ${r['priority']:,.2f}/mo at risk, "
                     f"reason: {r.get('reason') or 'n/a'}")
    return lines


def write_md(rows: list[dict[str, Any]], path: Path, top: int, summary: dict[str, Any]) -> None:
    body = [f"# Reach out this week ({date.today().isoformat()})", "",
            f"MRR at risk: ${summary['mrr_at_risk']:,.2f} across {summary['count']} customers.", ""]
    body += reach_out_lines(rows, top) or ["(nobody at risk)"]
    exp = summary["expansion_candidates"]
    if exp:
        body += ["", "## Expansion candidates", "", ", ".join(exp)]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body) + "\n")


CSV_COLS = ["id", "name", "email", "plan", "mrr", "health", "confidence", "churn_90d",
            "expansion", "reason", "priority", "review", "cost_usd", "error"]


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def append_sheet(rows: list[dict[str, Any]], sheet_id: str, tab: str) -> str:
    """Append rows to a Google Sheet tab. Returns a status string; never raises."""
    try:
        from execution.google.google_sheets_writer import get_client
        client = get_client()
        sh = client.open_by_key(sheet_id)
        try:
            ws = sh.worksheet(tab)
        except Exception:  # noqa: BLE001 -- gspread WorksheetNotFound; create the tab
            ws = sh.add_worksheet(title=tab, rows=1000, cols=len(CSV_COLS) + 1)
            ws.append_row(["scored_at"] + CSV_COLS)
        stamp = datetime.now().isoformat(timespec="seconds")
        ws.append_rows([[stamp] + ["" if r.get(c) is None else str(r.get(c)) for c in CSV_COLS]
                        for r in rows], value_input_option="USER_ENTERED")
        return f"appended {len(rows)} rows to {tab}"
    except ImportError as exc:
        return f"skipped (gspread unavailable: {exc})"
    except Exception as exc:  # noqa: BLE001 -- creds/API failures must not kill the run
        return f"skipped ({exc.__class__.__name__}: {exc})"


# ---- CLI ---------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True)
    ap.add_argument("--output")
    ap.add_argument("--csv-out")
    ap.add_argument("--md", help="write the 'reach out this week' markdown list here")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="normalize + build questions, call nothing")
    ap.add_argument("--validate", help="CSV of id,health ground truth")
    ap.add_argument("--sheet-id")
    ap.add_argument("--tab", default="customer_health")
    args = ap.parse_args(argv)

    inp = Path(args.input)
    try:
        customers = load_customers(inp)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.limit > 0:
        customers = customers[: args.limit]
    out_path = Path(args.output) if args.output else inp.with_suffix(inp.suffix + ".health.json")

    if args.dry_run:
        print(json.dumps({"customers": len(customers), "sample_state": customers[:2],
                          "questions": build_questions(), "min_confidence": args.min_confidence,
                          "output": str(out_path)}, indent=2, default=str))
        return 0
    if not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    rows = score_customers(customers, min_confidence=args.min_confidence, workers=args.workers)
    summary = summarize(rows, time.perf_counter() - t0)

    payload: dict[str, Any] = {"summary": summary, "min_confidence": args.min_confidence, "rows": rows}
    if args.validate:
        try:
            payload["validation"] = validate(rows, load_labels(Path(args.validate)))
        except (OSError, KeyError, ValueError) as exc:
            print(f"error: validate: {exc}", file=sys.stderr)
            return 2
    os.makedirs(out_path.parent or Path("."), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    if args.csv_out:
        write_csv(rows, Path(args.csv_out))
    if args.md:
        write_md(rows, Path(args.md), args.top, summary)

    print_summary(summary)
    print("  reach out this week:")
    for line in reach_out_lines(rows, args.top):
        print(f"    {line}")
    if "validation" in payload:
        v = payload["validation"]
        print(f"  validation:  {v['correct']}/{v['scored']} correct = {v['accuracy']:.1%}")
        for m in v["mismatches"]:
            print(f"    id={m['id']} expected={m['expected']} got={m['got']} conf={m['confidence']}")
    if args.sheet_id:
        print(f"  sheet: {append_sheet(rows, args.sheet_id, args.tab)}")
    print(f"  wrote {out_path}")
    jev_client.append_ledger({"caller": "jev_customer_health", "n": summary["count"],
                              "cost_usd": summary["cost_usd"], "wall_s": summary["wall_s"],
                              "errors": summary["errors"], "mrr_at_risk": summary["mrr_at_risk"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
