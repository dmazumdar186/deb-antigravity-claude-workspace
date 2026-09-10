"""
fit_weights.py
description: Reads audits + outreach from the store, computes per-signal reply rate (touch-1
    replied / sent) and a point-biserial correlation between each audit signal and touch-1 reply
    outcome. Prints a table and writes .tmp/prodcraft_medspa/fit_weights.json. Never changes
    scoring weights (audit/scoring.py stays hand-owned) — this is the measurement Karpathy's panel
    finding #2 asked for (docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md).
inputs: CLI: [--mock] [--store {local,supabase}] [--store-root P] [--min-sent 50]. Env: store vars.
outputs: stdout table + JSON stat line; .tmp/prodcraft_medspa/fit_weights.json (per-signal reply
    rates + point-biserial r); refuses (prints why, writes nothing) when sent < --min-sent.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common.store import (  # noqa: E402
    LocalStore,
    SupabaseStore,
    get_store,
)

# Signal name -> function(audit_row) -> bool | None (None = can't evaluate, excluded from that signal).
# Exact fail conditions per CONTRACTS.md's scoring table (audit/scoring.py is the source of truth;
# this mirrors it read-only so fit_weights has no import-order dependency on that package).
SIGNALS: dict[str, Any] = {
    "no_website": lambda a: a.get("has_website") is False,
    "no_booking_widget": lambda a: a.get("booking_widget") in (None, "", "null"),
    "not_mobile_friendly": lambda a: a.get("is_mobile_friendly") is False,
    "poor_performance": lambda a: isinstance(a.get("psi_mobile"), (int, float)) and a["psi_mobile"] < 70,
    "dated_design": lambda a: isinstance(a.get("vision_dated_score"), (int, float)) and a["vision_dated_score"] >= 7,
    "no_cta_above_fold": lambda a: a.get("has_cta_above_fold") is False,
    "no_ssl": lambda a: a.get("has_ssl") is False,
    "old_builder": lambda a: (
        a.get("builder") in ("wix", "godaddy")
        or (a.get("builder") == "wordpress" and isinstance(a.get("theme_year"), (int, float)) and a["theme_year"] < 2018)
        or bool(a.get("has_jquery_legacy"))
    ),
    "no_analytics": lambda a: a.get("has_analytics") is False,
}


def _all_rows(store: Any, table: str) -> list[dict]:
    """Best-effort full-table read across either Store implementation (see run_metro.py's
    _all_previews for the same pattern/rationale — no generic "list table" method in the Store
    Protocol)."""
    if isinstance(store, LocalStore):
        return store._read(table)  # noqa: SLF001
    if isinstance(store, SupabaseStore):
        resp = store._request("GET", table, headers=store._headers())  # noqa: SLF001
        return resp.json()
    return []


def touch1_outcomes(store: Any) -> list[tuple[dict, bool]]:
    """Return [(audit_row, replied_bool), ...] for every touch-1 outreach row that was sent."""
    outreach = _all_rows(store, "outreach")
    businesses = {b["id"]: b for b in _all_rows(store, "businesses")}
    audits = _all_rows(store, "audits")
    latest_audit_by_business: dict[str, dict] = {}
    for a in audits:
        bid = a.get("business_id")
        existing = latest_audit_by_business.get(bid)
        if existing is None or (a.get("audited_at") or "") > (existing.get("audited_at") or ""):
            latest_audit_by_business[bid] = a
    audits_by_id = {a["id"]: a for a in audits if a.get("id")}

    sent_states = {"sent", "replied", "call_booked", "closed_won", "closed_lost", "dnc"}
    out: list[tuple[dict, bool]] = []
    for row in outreach:
        if row.get("touch") != 1:
            continue
        if row.get("status") not in sent_states and not row.get("sent_at"):
            continue
        audit = None
        if row.get("audit_id"):
            audit = audits_by_id.get(row["audit_id"])
        if audit is None:
            audit = latest_audit_by_business.get(row.get("business_id"))
        if audit is None:
            continue
        replied = bool(row.get("replied_at")) or row.get("status") in ("replied", "call_booked", "closed_won")
        out.append((audit, replied))
    return out


def point_biserial(signal_values: list[bool], outcomes: list[bool]) -> float | None:
    """Point-biserial r between a binary grouping variable (signal) and a binary outcome (reply).

    Standard formula: r_pb = (M1 - M0) / s_n * sqrt(n1*n0 / n^2), where M1/M0 are the outcome
    means in the signal-true/signal-false groups and s_n is the population std dev of the outcome.
    Returns None when either group is empty or the outcome has zero variance (undefined r).
    """
    n = len(outcomes)
    if n == 0:
        return None
    group1 = [o for s, o in zip(signal_values, outcomes) if s]
    group0 = [o for s, o in zip(signal_values, outcomes) if not s]
    n1, n0 = len(group1), len(group0)
    if n1 == 0 or n0 == 0:
        return None
    mean_all = sum(outcomes) / n
    variance = sum((o - mean_all) ** 2 for o in outcomes) / n
    if variance == 0:
        return None
    s_n = math.sqrt(variance)
    m1 = sum(group1) / n1
    m0 = sum(group0) / n0
    return ((m1 - m0) / s_n) * math.sqrt((n1 * n0) / (n**2))


def compute_signal_table(rows: list[tuple[dict, bool]]) -> dict[str, Any]:
    outcomes = [replied for _, replied in rows]
    table: dict[str, Any] = {}
    for name, fn in SIGNALS.items():
        signal_values: list[bool] = []
        paired_outcomes: list[bool] = []
        for audit, replied in rows:
            val = fn(audit)
            if val is None:
                continue
            signal_values.append(bool(val))
            paired_outcomes.append(replied)

        n_true = sum(1 for v in signal_values if v)
        n_false = sum(1 for v in signal_values if not v)
        replied_true = sum(1 for v, o in zip(signal_values, paired_outcomes) if v and o)
        replied_false = sum(1 for v, o in zip(signal_values, paired_outcomes) if not v and o)

        table[name] = {
            "n_true": n_true,
            "reply_rate_true": (replied_true / n_true) if n_true else None,
            "n_false": n_false,
            "reply_rate_false": (replied_false / n_false) if n_false else None,
            "point_biserial_r": point_biserial(signal_values, paired_outcomes) if signal_values else None,
        }
    return {"n_touch1_sent": len(rows), "overall_reply_rate": (sum(outcomes) / len(outcomes)) if outcomes else None, "signals": table}


def print_table(result: dict[str, Any]) -> None:
    print(f"touch-1 sent: {result['n_touch1_sent']}, overall reply rate: {result['overall_reply_rate']:.3f}")
    print(f"{'signal':<22} {'n_true':>7} {'reply%_true':>12} {'n_false':>8} {'reply%_false':>13} {'point_biserial_r':>18}")
    for name, row in result["signals"].items():
        rt = "n/a" if row["reply_rate_true"] is None else f"{row['reply_rate_true'] * 100:.1f}%"
        rf = "n/a" if row["reply_rate_false"] is None else f"{row['reply_rate_false'] * 100:.1f}%"
        r = "n/a" if row["point_biserial_r"] is None else f"{row['point_biserial_r']:.3f}"
        print(f"{name:<22} {row['n_true']:>7} {rt:>12} {row['n_false']:>8} {rf:>13} {r:>18}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    parser.add_argument("--min-sent", dest="min_sent", type=int, default=50)
    args = parser.parse_args()

    store = get_store(kind=args.store, root=args.store_root) if args.store_root else get_store(kind=args.store)
    rows = touch1_outcomes(store)

    if len(rows) < args.min_sent:
        reason = f"only {len(rows)} touch-1 sends found, need >= {args.min_sent} — refusing to fit (too few sends for a stable correlation)"
        print(reason)
        print(json.dumps({"script": "fit_weights", "in": len(rows), "out": 0, "dropped": {"insufficient_sends": len(rows)}, "refused": True, "reason": reason}))
        return

    result = compute_signal_table(rows)
    print_table(result)

    out_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "fit_weights.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_path}")

    print(json.dumps({"script": "fit_weights", "in": len(rows), "out": len(result["signals"]), "dropped": {}, "refused": False}))


if __name__ == "__main__":
    main()
