"""
description: Health Score calculator for job_search_v2. Produces a single
    0-100 score with a confidence label (HIGH / MEDIUM / LOW) and a
    transparent breakdown of every component dimension. Surfaces in the
    Summary tab so the operator sees system state in one glance.
inputs:
    - pipeline_stats dict produced by run.py main()
    - per_tab_totals dict (Sheet row counts per role tab)
outputs:
    - dict with: overall_score (0-100), confidence (HIGH/MEDIUM/LOW),
      confidence_score (0-1), dimensions (list of {name, value, weight,
      contribution, status, notes})

Math is transparent — every dimension publishes its raw measure, its weight,
and its contribution. Confidence is sample-size + freshness based, not a
made-up vibes number. Documented below.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("notifier.health_score")

# Targets / SLAs — calibrated to the operator's stated expectations.
#
# Design principle (2026-06-24): health measures OUTCOME quality — "are the
# jobs that reach my sheet good?" — NOT filter pass-rates. A high rejection
# rate is the filters WORKING, not a problem. So we measure strong-match yield,
# volume of GOOD jobs, source diversity, freshness, delivery, and whether the
# relevance guard is active — never "what % of raw scrapes survived".
TARGET_STRONG_MATCHES = 5      # want >=5 tier-A/B jobs reaching the sheet per day
TARGET_AB_RATIO = 0.40         # >=40% of ranked (post-filter) jobs should be A or B
TARGET_SOURCES = 3             # need at least 3 sources contributing
TARGET_FRESHNESS_HOURS = 25.0  # last run should be within 25h

# Weights — sum to 1.0. Outcome-focused.
WEIGHTS = {
    "match_quality": 0.35,      # A/B ratio among post-filter ranked jobs
    "strong_volume": 0.25,      # count of strong (A/B) matches reaching the sheet
    "relevance_guard": 0.15,    # is the relevance + language gate active & producing clean output?
    "coverage": 0.15,           # sources contributing
    "freshness": 0.05,          # last-run age
    "delivery": 0.05,           # email + sheet write succeeded
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def calculate_health(pipeline_stats: dict, per_tab_totals: dict | None = None) -> dict:
    """Compute the health score from pipeline_stats. Pure function."""
    dimensions: list[dict] = []

    # --- Dimension 1: match_quality (A/B ratio among POST-FILTER ranked jobs) ---
    # These are jobs that already passed relevance + language + location +
    # contract gates, so this measures: of the jobs genuinely worth ranking,
    # how many are strong fits?
    ranker = pipeline_stats.get("ranker", {}) or {}
    by_tier = ranker.get("by_tier", {}) or {}
    total_ranked = sum(by_tier.values()) or 1
    ab = by_tier.get("A", 0) + by_tier.get("B", 0)
    ab_ratio = ab / total_ranked
    match_value = _clamp01(ab_ratio / TARGET_AB_RATIO)
    dimensions.append({
        "name": "match_quality",
        "raw": f"{ab}/{total_ranked} strong (A+B) ({ab_ratio:.0%})",
        "target": f"≥{TARGET_AB_RATIO:.0%}",
        "value": round(match_value, 3),
        "weight": WEIGHTS["match_quality"],
        "contribution": round(match_value * WEIGHTS["match_quality"] * 100, 1),
        "status": "OK" if ab_ratio >= TARGET_AB_RATIO else ("WARN" if ab_ratio >= TARGET_AB_RATIO * 0.5 else "FAIL"),
        "notes": "Of the relevant jobs that reached ranking, how many are strong A/B fits.",
    })

    # --- Dimension 2: strong_volume (count of A/B matches reaching the sheet) ---
    strong_count = ab
    strong_value = _clamp01(strong_count / TARGET_STRONG_MATCHES)
    dimensions.append({
        "name": "strong_volume",
        "raw": f"{strong_count} strong matches today",
        "target": f"≥{TARGET_STRONG_MATCHES}/day",
        "value": round(strong_value, 3),
        "weight": WEIGHTS["strong_volume"],
        "contribution": round(strong_value * WEIGHTS["strong_volume"] * 100, 1),
        "status": "OK" if strong_count >= TARGET_STRONG_MATCHES else ("WARN" if strong_count >= 2 else "FAIL"),
        "notes": "How many genuinely good (A/B) jobs the system surfaced. This is the number that matters most.",
    })

    # --- Dimension 3: relevance_guard (is the junk filter active & producing clean output?) ---
    # A high rejection count is GOOD — it means the gate is catching off-target
    # roles. We score this OK whenever the gate ran and produced a non-empty,
    # relevant result set. We do NOT penalise low survival rates.
    title = pipeline_stats.get("title_filter", {}) or {}
    tf_reasons = title.get("by_reason", {}) or {}
    lang = pipeline_stats.get("language_filter", {}) or {}
    gate_ran = ("not_relevant" in tf_reasons) or (title.get("rejected", 0) > 0) or (title.get("kept", 0) > 0)
    lang_ran = lang.get("requested", 0) > 0 or lang.get("kept", 0) > 0
    junk_blocked = tf_reasons.get("not_relevant", 0) + lang.get("rejected", 0)
    guard_value = 1.0 if (gate_ran and lang_ran) else (0.5 if gate_ran else 0.0)
    dimensions.append({
        "name": "relevance_guard",
        "raw": f"gate active, blocked {junk_blocked} off-target/non-EN-FR this run",
        "target": "active",
        "value": round(guard_value, 3),
        "weight": WEIGHTS["relevance_guard"],
        "contribution": round(guard_value * WEIGHTS["relevance_guard"] * 100, 1),
        "status": "OK" if guard_value >= 1.0 else ("WARN" if guard_value > 0 else "FAIL"),
        "notes": "Confirms the relevance + EN/FR gates ran. A high block count means they're protecting your sheet, not a problem.",
    })

    # --- Dimension 4: coverage (sources contributing) ---
    per_source = pipeline_stats.get("per_source", {}) or {}
    contributing = sum(1 for n in per_source.values() if n > 0)
    coverage_value = _clamp01(contributing / TARGET_SOURCES)
    dimensions.append({
        "name": "coverage",
        "raw": f"{contributing}/{len(per_source)} sources contributed",
        "target": f"≥{TARGET_SOURCES}",
        "value": round(coverage_value, 3),
        "weight": WEIGHTS["coverage"],
        "contribution": round(coverage_value * WEIGHTS["coverage"] * 100, 1),
        "status": "OK" if contributing >= TARGET_SOURCES else ("WARN" if contributing >= 2 else "FAIL"),
        "notes": "Number of sources returning ≥1 job this run. Below target = pipeline depending on too-few channels.",
    })

    # --- Dimension 6: freshness (hours since run completed) ---
    # Pipeline is running NOW, so freshness ≈ 0 for the run that just executed.
    # We compute based on run_id timestamp if available.
    run_id = pipeline_stats.get("run_id", "")
    age_h = 0.0
    if run_id:
        try:
            ts_str = run_id.split("-", 1)[0]  # e.g. "20260624T141939"
            run_ts = datetime.strptime(ts_str, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - run_ts).total_seconds() / 3600.0
        except (ValueError, IndexError):
            age_h = 0.0
    freshness_value = _clamp01(1.0 - max(0.0, age_h - 1.0) / TARGET_FRESHNESS_HOURS)
    dimensions.append({
        "name": "freshness",
        "raw": f"{age_h:.1f}h since this run",
        "target": f"<{TARGET_FRESHNESS_HOURS:.0f}h",
        "value": round(freshness_value, 3),
        "weight": WEIGHTS["freshness"],
        "contribution": round(freshness_value * WEIGHTS["freshness"] * 100, 1),
        "status": "OK" if age_h < TARGET_FRESHNESS_HOURS else "FAIL",
        "notes": "Hours since this run's start. Cron should refresh daily.",
    })

    # --- Dimension 7: delivery (sheet_ok + summary_ok + (email or lock-skip)) ---
    sheet_ok = bool(pipeline_stats.get("sheet_ok", False))
    summary_ok = bool(pipeline_stats.get("summary_ok", False))
    top_ok = bool(pipeline_stats.get("top_matches_ok", False))
    email_sent = bool(pipeline_stats.get("email_sent", False))
    email_lock = str(pipeline_stats.get("email_lock", ""))
    email_state_ok = email_sent or ("email lock" in email_lock.lower())
    delivery_passes = sum([sheet_ok, summary_ok, top_ok, email_state_ok])
    delivery_value = _clamp01(delivery_passes / 4)
    dimensions.append({
        "name": "delivery",
        "raw": f"{delivery_passes}/4 (sheet={sheet_ok}, summary={summary_ok}, top={top_ok}, email_state={email_state_ok})",
        "target": "4/4",
        "value": round(delivery_value, 3),
        "weight": WEIGHTS["delivery"],
        "contribution": round(delivery_value * WEIGHTS["delivery"] * 100, 1),
        "status": "OK" if delivery_passes == 4 else ("WARN" if delivery_passes >= 3 else "FAIL"),
        "notes": "Did the last run successfully write the sheet + dashboards AND either send email or block via lock?",
    })

    overall = round(sum(d["contribution"] for d in dimensions), 1)

    # --- Confidence: based on sample size + freshness + source coverage. ---
    # HIGH if all three are good. MEDIUM if 2/3. LOW if ≤1.
    sample_ok = total_ranked >= 50
    fresh_ok = age_h < TARGET_FRESHNESS_HOURS
    coverage_ok = contributing >= TARGET_SOURCES
    confidence_signals = sum([sample_ok, fresh_ok, coverage_ok])
    if confidence_signals == 3:
        confidence_label = "HIGH"
        confidence_score = 0.95
    elif confidence_signals == 2:
        confidence_label = "MEDIUM"
        confidence_score = 0.7
    elif confidence_signals == 1:
        confidence_label = "LOW"
        confidence_score = 0.4
    else:
        confidence_label = "VERY LOW"
        confidence_score = 0.15

    return {
        "overall_score": overall,
        "confidence": confidence_label,
        "confidence_score": confidence_score,
        "confidence_components": {
            "sample_size_ok": sample_ok,
            "freshness_ok": fresh_ok,
            "coverage_ok": coverage_ok,
            "passing": f"{confidence_signals}/3",
        },
        "dimensions": dimensions,
        "math": "overall = sum(dim.value * dim.weight) * 100. confidence = HIGH if all 3 of (sample≥50, fresh<25h, sources≥3) else MEDIUM if 2/3 else LOW.",
    }


def render_for_sheet(health: dict) -> list[list[str]]:
    """Render the health report as a list of rows suitable for Summary tab."""
    rows: list[list[str]] = []
    rows.append([f"HEALTH SCORE: {health['overall_score']:.1f} / 100",
                 f"confidence={health['confidence']} ({health['confidence_score']:.2f})"])
    cc = health.get("confidence_components", {})
    rows.append([
        f"confidence: sample_ok={cc.get('sample_size_ok')} fresh_ok={cc.get('freshness_ok')} coverage_ok={cc.get('coverage_ok')} ({cc.get('passing')})",
        "",
    ])
    rows.append(["math:", health.get("math", "")])
    rows.append(["", ""])
    rows.append(["DIMENSION", "STATUS  |  raw  |  value × weight = contribution  |  target  |  notes"])
    for d in health["dimensions"]:
        line = (
            f"[{d['status']}] raw={d['raw']} | value={d['value']:.3f} × "
            f"weight={d['weight']:.2f} = {d['contribution']:.1f}pts | "
            f"target={d['target']} | {d['notes']}"
        )
        rows.append([d["name"], line])
    return rows
