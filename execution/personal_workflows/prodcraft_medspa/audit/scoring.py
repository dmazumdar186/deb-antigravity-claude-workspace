"""
scoring.py
description: Pure scoring function over stored audit signals. No I/O — CONTRACTS.md "Scoring" table exactly.
inputs: Imported by audit_site.py (fresh signals) and scoring.py's own --recompute CLI (stored signals).
outputs: score(signals) -> {"total", "bucket", "gaps", "score_version"}; CLI recomputes and diffs stored audits.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config, store  # noqa: E402

SCORE_VERSION = "1.0"

# Customer-safe, lost-booking-framed wording. Never "your site is bad" — always what
# it costs the business. stale_footer carries a {year} placeholder filled with the
# actual footer_year at score() time.
HUMAN_PHRASES: dict[str, str] = {
    "no_booking_widget": "clients can't book online without calling",
    "not_mobile_friendly": "the site is hard to use on a phone, where most people look you up",
    "poor_performance": "pages take several seconds to load on mobile",
    "dated_design": "the layout hides the booking step",
    "no_cta_above_fold": "there's no way to book from the first screen",
    "no_ssl": "browsers flag the site as not secure",
    "old_builder": "the site builder limits online booking options",
    "no_analytics": "there's no way to see where bookings are lost",
    "stale_footer": "the footer still says {year}",
    "no_website": "there's no website to book from",
}

_OLD_BUILDERS = {"wix", "godaddy"}


def _bucket(total: int) -> str:
    if total >= 45:
        return "qualified"
    if total >= 25:
        return "borderline"
    return "skip"


def score(signals: dict[str, Any]) -> dict:
    """Score a business's audit signals 0-100 (higher = worse site = better prospect).

    `signals` keys read (all optional / None-safe): has_website, booking_widget,
    is_mobile_friendly, psi_mobile, vision_dated_score, has_cta_above_fold, has_ssl,
    builder, theme_year, has_jquery_legacy, has_analytics, footer_year, current_year
    (defaults to today's UTC year; override in tests for boundary checks).
    """
    current_year = signals.get("current_year") or datetime.now(timezone.utc).year

    if signals.get("has_website") is False:
        gap = {
            "signal": "no_website",
            "points": 100,
            "human_phrase": HUMAN_PHRASES["no_website"],
        }
        return {
            "total": 100,
            "bucket": _bucket(100),
            "gaps": [gap],
            "score_version": SCORE_VERSION,
        }

    gaps: list[dict] = []

    if signals.get("booking_widget") is None:
        gaps.append(
            {
                "signal": "no_booking_widget",
                "points": 22,
                "human_phrase": HUMAN_PHRASES["no_booking_widget"],
            }
        )

    if signals.get("is_mobile_friendly") is False:
        gaps.append(
            {
                "signal": "not_mobile_friendly",
                "points": 15,
                "human_phrase": HUMAN_PHRASES["not_mobile_friendly"],
            }
        )

    psi_mobile = signals.get("psi_mobile")
    if psi_mobile is not None:
        if psi_mobile < 50:
            gaps.append(
                {
                    "signal": "poor_performance",
                    "points": 15,
                    "human_phrase": HUMAN_PHRASES["poor_performance"],
                }
            )
        elif psi_mobile < 70:
            gaps.append(
                {
                    "signal": "poor_performance",
                    "points": 10,
                    "human_phrase": HUMAN_PHRASES["poor_performance"],
                }
            )

    vision_dated_score = signals.get("vision_dated_score")
    if vision_dated_score is not None and vision_dated_score >= 7:
        gaps.append(
            {
                "signal": "dated_design",
                "points": 15,
                "human_phrase": HUMAN_PHRASES["dated_design"],
            }
        )

    if signals.get("has_cta_above_fold") is False:
        gaps.append(
            {
                "signal": "no_cta_above_fold",
                "points": 10,
                "human_phrase": HUMAN_PHRASES["no_cta_above_fold"],
            }
        )

    if signals.get("has_ssl") is False:
        gaps.append(
            {
                "signal": "no_ssl",
                "points": 8,
                "human_phrase": HUMAN_PHRASES["no_ssl"],
            }
        )

    builder = signals.get("builder")
    theme_year = signals.get("theme_year")
    is_old_wordpress = builder == "wordpress" and theme_year is not None and theme_year < 2018
    if builder in _OLD_BUILDERS or is_old_wordpress or signals.get("has_jquery_legacy") is True:
        gaps.append(
            {
                "signal": "old_builder",
                "points": 8,
                "human_phrase": HUMAN_PHRASES["old_builder"],
            }
        )

    if signals.get("has_analytics") is False:
        gaps.append(
            {
                "signal": "no_analytics",
                "points": 4,
                "human_phrase": HUMAN_PHRASES["no_analytics"],
            }
        )

    footer_year = signals.get("footer_year")
    if footer_year is not None and footer_year <= current_year - 2:
        gaps.append(
            {
                "signal": "stale_footer",
                "points": 3,
                "human_phrase": HUMAN_PHRASES["stale_footer"].format(year=footer_year),
            }
        )

    gaps.sort(key=lambda g: g["points"], reverse=True)
    total = sum(g["points"] for g in gaps)

    return {
        "total": total,
        "bucket": _bucket(total),
        "gaps": gaps,
        "score_version": SCORE_VERSION,
    }


def _signals_from_audit_row(row: dict) -> dict:
    keys = (
        "has_website",
        "booking_widget",
        "is_mobile_friendly",
        "psi_mobile",
        "vision_dated_score",
        "has_cta_above_fold",
        "has_ssl",
        "builder",
        "theme_year",
        "has_jquery_legacy",
        "has_analytics",
        "footer_year",
    )
    return {k: row.get(k) for k in keys}


def main() -> None:
    """description: Recompute total_score/bucket/gaps for the latest audit of each business in a metro.
    inputs: --recompute --metro X [--store {local,supabase}] [--store-root PATH]
    outputs: stdout stat line; stored audit rows patched where the recomputed score differs.
    """
    parser = argparse.ArgumentParser(description="Recompute audit scores from stored signals (pure function proof)")
    parser.add_argument("--recompute", action="store_true", required=True)
    parser.add_argument("--metro", required=True)
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = args.store or settings.store_kind
    st = store.get_store(kind=store_kind, root=args.store_root)

    businesses = st.find_businesses(metro=args.metro)
    diff_count = 0
    checked = 0
    for business in businesses:
        latest = st.latest_audit(business["id"])
        if not latest:
            continue
        checked += 1
        signals = _signals_from_audit_row(latest)
        recomputed = score(signals)
        if (
            recomputed["total"] != latest.get("total_score")
            or recomputed["bucket"] != latest.get("bucket")
            or recomputed["gaps"] != latest.get("gaps")
        ):
            # The Store contract has no generic audit patcher (audits are append-only via
            # insert_audit) — this CLI's job is to prove score() is a pure function of the
            # stored signal columns, so it counts and reports diffs rather than writing.
            diff_count += 1

    print(
        f'{{"script": "scoring", "metro": "{args.metro}", "checked": {checked}, "diffs": {diff_count}}}'
    )


if __name__ == "__main__":
    main()
