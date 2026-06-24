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
TARGET_DAILY_JOBS = 20         # net-new jobs/day floor for "volume" dimension
TARGET_TIER_A_RATIO = 0.10     # 10% of ranked jobs should be tier A (good rubric)
TARGET_LANG_COMPLIANCE = 0.95  # 95% of jobs surviving filters should be EN/FR
TARGET_TITLE_QUALITY = 0.85    # 85%+ of titles should be PM/AI-relevant (low reject rate)
TARGET_SOURCES = 3             # need at least 3 sources contributing
TARGET_FRESHNESS_HOURS = 25.0  # last run should be within 25h

# Weights — sum to 1.0. Adjusted per operator's signals about what matters most.
WEIGHTS = {
    "match_quality": 0.30,      # tier-A ratio — DOES it find good fits?
    "language_compliance": 0.20, # EN/FR-only — operator's hard constraint
    "title_quality": 0.15,      # are titles relevant or junk?
    "volume": 0.15,             # jobs/day floor
    "coverage": 0.10,           # sources contributing
    "freshness": 0.05,          # last-run age
    "delivery": 0.05,           # email + sheet write succeeded
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def calculate_health(pipeline_stats: dict, per_tab_totals: dict | None = None) -> dict:
    """Compute the health score from pipeline_stats. Pure function."""
    dimensions: list[dict] = []

    # --- Dimension 1: match_quality (tier-A ratio) ---
    ranker = pipeline_stats.get("ranker", {}) or {}
    by_tier = ranker.get("by_tier", {}) or {}
    total_ranked = sum(by_tier.values()) or 1
    tier_a = by_tier.get("A", 0)
    tier_a_ratio = tier_a / total_ranked
    match_value = _clamp01(tier_a_ratio / TARGET_TIER_A_RATIO)
    dimensions.append({
        "name": "match_quality",
        "raw": f"{tier_a}/{total_ranked} tier-A ({tier_a_ratio:.1%})",
        "target": f"≥{TARGET_TIER_A_RATIO:.0%}",
        "value": round(match_value, 3),
        "weight": WEIGHTS["match_quality"],
        "contribution": round(match_value * WEIGHTS["match_quality"] * 100, 1),
        "status": "OK" if match_value >= 1.0 else ("WARN" if match_value >= 0.5 else "FAIL"),
        "notes": "Fraction of ranked jobs tagged tier A. Measures whether the rubric is hitting real fits.",
    })

    # --- Dimension 2: language_compliance (EN/FR ratio at the language stage) ---
    lang = pipeline_stats.get("language_filter", {}) or {}
    lang_in = lang.get("requested", 0)
    lang_kept = lang.get("kept", 0)
    if lang_in:
        lang_ratio = lang_kept / lang_in
    else:
        lang_ratio = 1.0
    lang_value = _clamp01(lang_ratio / TARGET_LANG_COMPLIANCE)
    dimensions.append({
        "name": "language_compliance",
        "raw": f"{lang_kept}/{lang_in} EN/FR ({lang_ratio:.1%})",
        "target": f"≥{TARGET_LANG_COMPLIANCE:.0%}",
        "value": round(lang_value, 3),
        "weight": WEIGHTS["language_compliance"],
        "contribution": round(lang_value * WEIGHTS["language_compliance"] * 100, 1),
        "status": "OK" if lang_ratio >= TARGET_LANG_COMPLIANCE else ("WARN" if lang_ratio >= 0.8 else "FAIL"),
        "notes": "Share of post-contract jobs that pass the EN/FR language gate. High values = sources mostly serve English/French.",
    })

    # --- Dimension 3: title_quality (1 - title_filter rejection rate) ---
    title = pipeline_stats.get("title_filter", {}) or {}
    title_in = title.get("requested", 0)
    title_kept = title.get("kept", 0)
    if title_in:
        title_ratio = title_kept / title_in
    else:
        title_ratio = 1.0
    title_value = _clamp01(title_ratio / TARGET_TITLE_QUALITY)
    dimensions.append({
        "name": "title_quality",
        "raw": f"{title_kept}/{title_in} kept ({title_ratio:.1%})",
        "target": f"≥{TARGET_TITLE_QUALITY:.0%}",
        "value": round(title_value, 3),
        "weight": WEIGHTS["title_quality"],
        "contribution": round(title_value * WEIGHTS["title_quality"] * 100, 1),
        "status": "OK" if title_ratio >= TARGET_TITLE_QUALITY else ("WARN" if title_ratio >= 0.7 else "FAIL"),
        "notes": "Share of normalized jobs passing the title filter. Low values = keyword searches return too much project-manager/alternance/junior noise.",
    })

    # --- Dimension 4: volume ---
    new_jobs = pipeline_stats.get("after_dedup_new", 0)
    volume_value = _clamp01(new_jobs / TARGET_DAILY_JOBS)
    dimensions.append({
        "name": "volume",
        "raw": f"{new_jobs} net-new jobs",
        "target": f"≥{TARGET_DAILY_JOBS}/day",
        "value": round(volume_value, 3),
        "weight": WEIGHTS["volume"],
        "contribution": round(volume_value * WEIGHTS["volume"] * 100, 1),
        "status": "OK" if new_jobs >= TARGET_DAILY_JOBS else ("WARN" if new_jobs >= TARGET_DAILY_JOBS // 2 else "FAIL"),
        "notes": "Net-new (post-dedup) jobs found this run. Measures pipeline throughput.",
    })

    # --- Dimension 5: coverage (sources contributing) ---
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
