"""
fit_weights.py
description: Reads audits + outreach from the store, computes per-signal reply rate (touch-1
    replied / sent) and a point-biserial correlation between each audit signal and touch-1 reply
    outcome, plus a template-variant reply-rate table. Prints tables and writes
    .tmp/prodcraft_medspa/fit_weights.json. Never changes scoring weights (audit/scoring.py stays
    hand-owned) — this is the measurement Karpathy's panel finding #2 asked for
    (docs/audits/prodcraft_medspa_panel_pass_2026-09-10.md).
inputs: CLI: [--mock] [--store {local,supabase}] [--store-root P] [--min-sent 50]
    [--metro NAME] [--mode {full,degraded,all}] [--report-telegram]. Env: store vars,
    TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (for --report-telegram).
outputs: stdout table(s) + JSON stat line; .tmp/prodcraft_medspa/fit_weights.json (per-signal
    reply rates + point-biserial r, template-variant table, metro/mode/queue_pick stamped);
    refuses (prints why, writes nothing) when sent < --min-sent. --report-telegram posts (or,
    under --mock, prints) a compact summary via common.notify.weekly_report, including the
    round-4 "sends vs cap (7d)" line from outreach/send.py's sends_vs_cap (also on the
    not-enough-data path).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common import notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.outreach import send as send_mod  # noqa: E402

# No U+2014 (em-dash) in any Telegram-bound line (workspace Telegram formatting convention);
# build_telegram_lines() uses plain hyphens only. Guarded by test_round2_fixlearn.py.

# Signal name -> function(audit_row) -> bool | None (None = can't evaluate, excluded from that signal).
# Mirrors CONTRACTS.md's scoring table read-only (audit/scoring.py is the source of truth; no
# import-order dependency on that package). Two deliberate simplifications for a binary
# correlation signal: `poor_performance` folds the 15/10-point tiers into one `psi_mobile < 70`
# indicator, and `no_booking_widget` treats "" / "null" like None (defensive against string-typed
# rows from Supabase). Everything else is the exact fail condition.
def _bool_signal(field: str):
    """A `field is False`-style boolean signal that treats `None` (never measured — PSI/vision
    skipped, an older audit row predating a column, etc.) as *unknown*, excluded from that
    signal's fit, rather than folding it into the "false" (signal-not-present) group. Folding
    None into False was the round-2 audit finding: a business we never even checked for mobile-
    friendliness was silently counted as "is mobile friendly", biasing the correlation."""

    def fn(a: dict) -> bool | None:
        val = a.get(field)
        if val is None:
            return None
        return val is False

    return fn


SIGNALS: dict[str, Any] = {
    "no_website": _bool_signal("has_website"),
    "no_booking_widget": lambda a: a.get("booking_widget") in (None, "", "null"),
    "not_mobile_friendly": _bool_signal("is_mobile_friendly"),
    "poor_performance": lambda a: isinstance(a.get("psi_mobile"), (int, float)) and a["psi_mobile"] < 70,
    "dated_design": lambda a: isinstance(a.get("vision_dated_score"), (int, float)) and a["vision_dated_score"] >= 7,
    "no_cta_above_fold": _bool_signal("has_cta_above_fold"),
    "no_ssl": _bool_signal("has_ssl"),
    "old_builder": lambda a: (
        a.get("builder") in ("wix", "godaddy")
        or (a.get("builder") == "wordpress" and isinstance(a.get("theme_year"), (int, float)) and a["theme_year"] < 2018)
        or bool(a.get("has_jquery_legacy"))
    ),
    "no_analytics": _bool_signal("has_analytics"),
}


def _all_rows(store: Any, table: str) -> list[dict]:
    """Full-table read via the Store Protocol's generic list_rows()."""
    return store.list_rows(table)


def touch1_outcomes(store: Any, *, metro: str | None = None, mode: str = "all") -> list[tuple[dict, dict, bool]]:
    """Return [(audit_row, outreach_row, replied_bool), ...] for every touch-1 outreach row that
    was sent, joined to its business's latest matching audit.

    `metro`: None (default) = all metros; else only outreach whose business.metro matches exactly.
    `mode`: "all" (default here -- keeps this function's own behavior unchanged for existing
    callers) applies no mode filter; "full" restricts to audits whose stored `mode` column is
    "full"; "degraded" the mirror. An audit row predating this column (mode is absent/None)
    matches only "all", never "full" or "degraded" -- we don't know what it measured, so it's
    excluded from a mode-specific fit rather than silently counted as either. main()'s CLI passes
    `--mode` explicitly and defaults ITS OWN flag to "full" (CONTRACTS.md) -- that CLI-level
    default is deliberately stricter than this function's own default.
    """
    if mode not in ("full", "degraded", "all"):
        raise ValueError(f"mode must be one of full/degraded/all, got {mode!r}")

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
    out: list[tuple[dict, dict, bool]] = []
    for row in outreach:
        if row.get("touch") != 1:
            continue
        if row.get("status") not in sent_states and not row.get("sent_at"):
            continue
        if row.get("test_recipient"):
            # operator dry-run rows (sent to the operator's own inbox) are not prospect outcomes
            continue
        business = businesses.get(row.get("business_id"))
        if metro is not None and (business or {}).get("metro") != metro:
            continue
        audit = None
        if row.get("audit_id"):
            audit = audits_by_id.get(row["audit_id"])
        if audit is None:
            audit = latest_audit_by_business.get(row.get("business_id"))
        if audit is None:
            continue
        if mode != "all" and audit.get("mode") != mode:
            continue
        replied = bool(row.get("replied_at")) or row.get("status") in ("replied", "call_booked", "closed_won")
        out.append((audit, row, replied))
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


def compute_signal_table(rows: list[tuple[dict, dict, bool]] | list[tuple[dict, bool]]) -> dict[str, Any]:
    """Accepts either the current (audit, outreach, replied) triples from touch1_outcomes(), or
    the older (audit, replied) pairs some callers may still hold — only `audit` and `replied` are
    used here (the outreach row is template_variant_table()'s input, not this function's)."""
    rows = [(r[0], r[-1]) for r in rows]
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


def template_variant_table(rows: list[tuple[dict, dict, bool]]) -> dict[str, Any]:
    """Reply-rate table keyed by outreach.template_variant ("a"/"b"/"c" for touch 1). A row with
    no template_variant (older sends, predating variants) is grouped under "unknown" rather than
    dropped, so it stays visible instead of silently vanishing from the sample count."""
    by_variant: dict[str, list[bool]] = {}
    for _audit, outreach_row, replied in rows:
        variant = outreach_row.get("template_variant") or "unknown"
        by_variant.setdefault(variant, []).append(replied)
    table: dict[str, Any] = {}
    for variant, outcomes in sorted(by_variant.items()):
        n = len(outcomes)
        table[variant] = {"n": n, "reply_rate": (sum(outcomes) / n) if n else None}
    return table


def queue_pick_effective_table(rows: list[tuple[dict, dict, bool]]) -> dict[str, Any]:
    """item 16 (round-3, Sutskever lens): reply rate grouped by outreach.queue_pick_effective
    ("random"/"score" — what actually governed each row's touch-1 enqueue; may differ from the
    raw config.queue_pick while phase0 hasn't passed). A row predating this column (older sends)
    groups under "unknown" rather than dropped, mirroring template_variant_table()'s pattern."""
    by_pick: dict[str, list[bool]] = {}
    for _audit, outreach_row, replied in rows:
        pick = outreach_row.get("queue_pick_effective") or "unknown"
        by_pick.setdefault(pick, []).append(replied)
    table: dict[str, Any] = {}
    for pick, outcomes in sorted(by_pick.items()):
        n = len(outcomes)
        table[pick] = {"n": n, "reply_rate": (sum(outcomes) / n) if n else None}
    return table


def print_table(result: dict[str, Any]) -> None:
    # item 9 (round-3 minor): overall_reply_rate can be None (e.g. n_touch1_sent == 0 slipping
    # past the --min-sent gate in an edge case) — formatting None with :.3f raises TypeError and
    # would crash a script whose whole job is to report, not to fail.
    overall = result.get("overall_reply_rate")
    overall_display = "n/a" if overall is None else f"{overall:.3f}"
    print(f"touch-1 sent: {result['n_touch1_sent']}, overall reply rate: {overall_display}")
    print(f"{'signal':<22} {'n_true':>7} {'reply%_true':>12} {'n_false':>8} {'reply%_false':>13} {'point_biserial_r':>18}")
    for name, row in result["signals"].items():
        rt = "n/a" if row["reply_rate_true"] is None else f"{row['reply_rate_true'] * 100:.1f}%"
        rf = "n/a" if row["reply_rate_false"] is None else f"{row['reply_rate_false'] * 100:.1f}%"
        r = "n/a" if row["point_biserial_r"] is None else f"{row['point_biserial_r']:.3f}"
        print(f"{name:<22} {row['n_true']:>7} {rt:>12} {row['n_false']:>8} {rf:>13} {r:>18}")


def print_variant_table(table: dict[str, Any]) -> None:
    print(f"\n{'template_variant':<18} {'n':>6} {'reply_rate':>12}")
    for variant, row in table.items():
        rr = "n/a" if row["reply_rate"] is None else f"{row['reply_rate'] * 100:.1f}%"
        print(f"{variant:<18} {row['n']:>6} {rr:>12}")


def _utc_today() -> date:
    """Round-4 item C: the sends window is bucketed by UTC day (send._sent_today_count), so the
    default `today` must be the UTC calendar date, not the runner's local one."""
    return datetime.now(timezone.utc).date()


def sends_vs_cap_line(store: Any, *, mock: bool = False, today: Any = None) -> str:
    """Round-4 weekly number: trailing-7-day sends vs the effective (warmup-ramped) cap, computed
    by outreach/send.py's `sends_vs_cap` (same counter and cap function send.py enforces)."""
    summary = send_mod.sends_vs_cap(store, today or _utc_today(), mock=mock)
    return send_mod.format_sends_vs_cap(summary)


UNDER_SEND_RATIO = 0.5
UNDER_SEND_DEDUPE_KEY = "under_send_7d"


def under_send_alert(store: Any, *, mock: bool = False, today: Any = None) -> str | None:
    """Round-4 item E (Saraev/Hassabis): the weekly report's sends-vs-cap line is informational;
    a pipeline quietly sending well under its cap for a week is an error condition and must
    reach the error channel in the fixed `service / environment / error / count` shape:
    `prodcraft_medspa / <env> / under_send_7d / sent=S cap=C / 1`. Fires only once
    `config.live_send_confirmed` is true (pre-live, a 0/35 week is by design), only when the
    7-day cap is > 0 and 7-day sends are below UNDER_SEND_RATIO of it, and at most once per UTC
    day per store via notify.once_per_day (`config.notify_dedupe["under_send_7d"]`).
    Returns the alert line when the condition holds (whether or not it was deduped), else None.
    """
    if not bool(store.get_config("live_send_confirmed", False)):
        return None
    today = today or _utc_today()
    summary = send_mod.sends_vs_cap(store, today, mock=mock)
    sent, cap = int(summary["sent"]), int(summary["cap"])
    if cap <= 0 or sent >= UNDER_SEND_RATIO * cap:
        return None
    error_text = f"{UNDER_SEND_DEDUPE_KEY} / sent={sent} cap={cap}"
    notify.once_per_day(store, UNDER_SEND_DEDUPE_KEY, "prodcraft_medspa", error_text, today)
    env = os.environ.get("PRODCRAFT_ENV") or "local"
    return f"prodcraft_medspa / {env} / {error_text} / 1"


def build_telegram_lines(
    result: dict[str, Any],
    variant_table: dict[str, Any],
    metro: str | None,
    mode: str,
    queue_pick: Any,
    sends_line: str | None = None,
) -> list[str]:
    """Up to 6 content lines (weekly_report() appends the trailing env/timestamp line itself).
    Never contains U+2014 — plain hyphens/"vs" only. `sends_line` (round-4) is the
    sends-vs-cap line; it is the 6th and last content line when given."""
    n = result["n_touch1_sent"]
    overall = result["overall_reply_rate"]
    overall_pct = "n/a" if overall is None else f"{overall * 100:.1f}%"
    scope = f"{metro or 'all metros'} / {mode}"

    ranked = sorted(
        (
            (name, row["point_biserial_r"])
            for name, row in result["signals"].items()
            if row["point_biserial_r"] is not None
        ),
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    top_signals = ", ".join(f"{name} r={r:.2f}" for name, r in ranked[:2]) or "no signal has enough data yet"

    best_variant = None
    best_rate = None
    for variant, row in variant_table.items():
        if variant == "unknown" or row["reply_rate"] is None:
            continue
        if best_rate is None or row["reply_rate"] > best_rate:
            best_rate = row["reply_rate"]
            best_variant = variant
    variant_line = (
        f"best template variant: {best_variant} ({best_rate * 100:.1f}%)"
        if best_variant is not None
        else "not enough per-variant data yet"
    )

    lines = [
        f"ProdCraft weekly fit: {scope}",
        f"touch-1 sent: {n}, reply rate: {overall_pct}",
        f"top signals: {top_signals}",
        variant_line,
        f"queue_pick: {queue_pick!r}",
    ]
    if sends_line:
        lines.append(sends_line)
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", dest="store_root", default=None)
    parser.add_argument("--min-sent", dest="min_sent", type=int, default=50)
    parser.add_argument("--metro", default=None, help="filter to one metro; default all metros")
    parser.add_argument("--mode", choices=["full", "degraded", "all"], default="full")
    parser.add_argument(
        "--report-telegram", action="store_true",
        help="post a compact summary via common.notify.weekly_report (prints instead, under --mock)",
    )
    args = parser.parse_args()

    # Round-4 item B: this is the Monday cron entrypoint; any failure must page the error
    # channel (same wrapper shape as outreach/send.py and outreach/scan_replies.py main()).
    try:
        _run(args)
    except Exception as exc:  # noqa: BLE001 — top-level failure must reach the error channel
        notify.error("prodcraft_medspa.fit_weights", f"{type(exc).__name__}: {exc}")
        raise


def _run(args: argparse.Namespace) -> None:
    store = get_store(kind=args.store, root=args.store_root) if args.store_root else get_store(kind=args.store)
    rows = touch1_outcomes(store, metro=args.metro, mode=args.mode)
    queue_pick = store.get_config("queue_pick")

    if len(rows) < args.min_sent:
        reason = f"only {len(rows)} touch-1 sends found, need >= {args.min_sent} — refusing to fit (too few sends for a stable correlation)"
        print(reason)
        print(json.dumps({"script": "fit_weights", "in": len(rows), "out": 0, "dropped": {"insufficient_sends": len(rows)}, "refused": True, "reason": reason}))
        if args.report_telegram:
            not_enough_line = f"not enough data yet: {len(rows)}/{args.min_sent} sends"
            lines = [not_enough_line, sends_vs_cap_line(store, mock=args.mock)]
            if args.mock:
                for line in lines:
                    print(line)
            else:
                notify.weekly_report(lines)
            under_send_alert(store, mock=args.mock)
        return

    result = compute_signal_table(rows)
    print_table(result)
    variant_table = template_variant_table(rows)
    print_variant_table(variant_table)

    result["metro"] = args.metro or "all"
    result["mode"] = args.mode
    result["queue_pick"] = queue_pick
    result["template_variants"] = variant_table
    result["queue_pick_effective"] = queue_pick_effective_table(rows)

    out_path = REPO_ROOT / ".tmp" / "prodcraft_medspa" / "fit_weights.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_path}")

    if args.report_telegram:
        lines = build_telegram_lines(
            result, variant_table, args.metro, args.mode, queue_pick,
            sends_line=sends_vs_cap_line(store, mock=args.mock),
        )
        if args.mock:
            for line in lines:
                print(line)
        else:
            notify.weekly_report(lines)
        under_send_alert(store, mock=args.mock)

    print(json.dumps({"script": "fit_weights", "in": len(rows), "out": len(result["signals"]), "dropped": {}, "refused": False}))


if __name__ == "__main__":
    main()
