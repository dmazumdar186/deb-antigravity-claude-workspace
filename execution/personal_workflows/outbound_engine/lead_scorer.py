"""Deterministic lead scorer (SPEC G1/G3 support).

score = w_icp_fit * icp_fit + w_signal * signal_strength + w_deliv * deliverability

All inputs are deterministic (no LLM, no network) so the score is reproducible
and auditable. Only leads at or above `scoring.min_score_to_queue` reach the
review sheet. Scoring is COMPLEMENTARY to the acceptance gate: the gate is a
hard yes/no on correctness/compliance; the score prioritises the survivors.
"""
from __future__ import annotations

SIGNAL_STRENGTH = {
    "hiring": 1.0,   # actively paying a human to do the manual work -> strongest buyer
    "intent": 1.0,   # explicit automation request (Upwork/Fiverr)
    "stack": 0.6,    # uses Zapier/Make/Airtable -> automation-ready
    "growth": 0.5,   # recent funding -> budget + growing pains
}

DELIVERABILITY = {
    "valid": 1.0,
    "unknown": 0.5,
    "risky": 0.3,
    "catch_all": 0.3,
    "invalid": 0.0,
    "disposable": 0.0,
}


def _icp_fit(prospect: dict, icp: dict) -> float:
    """Fraction of ICP criteria met (title, size, geo, industry)."""
    title = str(prospect.get("title", "")).lower()
    targets = [t.lower() for t in icp.get("titles_target", [])]
    title_ok = any(t == title or t in title for t in targets)

    lo, hi = (icp.get("employee_range") or [0, 10**9])
    emp = prospect.get("employees")
    size_ok = isinstance(emp, (int, float)) and lo <= emp <= hi

    geo = str(prospect.get("geo", "")).upper()
    geo_ok = geo in [g.upper() for g in icp.get("geos_include", [])]

    industry = str(prospect.get("industry", "")).lower()
    inds = [i.lower() for i in icp.get("industries_include", [])]
    industry_ok = any(i in industry or industry in i for i in inds) if industry else False

    checks = [title_ok, size_ok, geo_ok, industry_ok]
    return sum(1 for c in checks if c) / len(checks)


def score_lead(row: dict, config: dict) -> float:
    """Return a 0.0-1.0 priority score for one drafted lead row."""
    icp = config.get("icp", {})
    weights = config.get("scoring", {}).get("weights", {})
    w_fit = weights.get("icp_fit", 0.4)
    w_sig = weights.get("signal_strength", 0.4)
    w_del = weights.get("deliverability_confidence", 0.2)

    fit = _icp_fit(row.get("prospect", {}), icp)
    sig = SIGNAL_STRENGTH.get(str(row.get("signal", {}).get("type", "")).lower(), 0.3)
    deliv = DELIVERABILITY.get(str(row.get("verification", "unknown")).lower(), 0.5)

    total_w = (w_fit + w_sig + w_del) or 1.0
    score = (w_fit * fit + w_sig * sig + w_del * deliv) / total_w
    return round(max(0.0, min(1.0, score)), 3)


def passes_threshold(row: dict, config: dict) -> bool:
    thresh = config.get("scoring", {}).get("min_score_to_queue", 0.6)
    return score_lead(row, config) >= thresh
