"""
eval/scorecard.py -- the six numbers (RADAR_CONTRACTS.md section F).

  composition_violations   -- gates.composition_violations() over the exact
                               delivered cards, both roles combined.
  quote_drop_rate           -- validate.json["stats"]["drop_rate"].
  grade_precision           -- fraction of LABELLED persons where
                               gates._grade_from_title(extract.json's
                               current_title) agrees with the human label's
                               `grade`. "n/a (no labels)" when there are none.
  residence_precision       -- same idea for gates._location_country vs the
                               human label's `location_country`.
  delivered_over_pool       -- delivered / profiles_assessed, both roles
                               combined, from poolmap.json.
  cost_per_delivered_card   -- core.providers.spend_eur() / delivered.

No LLM call (RADAR_CONTRACTS.md top rule) -- every number here is either a
file read or a call into the SAME deterministic functions gates.py already
uses to decide who ships, so the scorecard can never disagree with the
pipeline about what a "grade" or a "location" is.

Deliberately dishonest otherwise: `grade_precision` and `residence_precision`
print "n/a (no labels)" rather than 100% when `eval/labels.jsonl` is empty.
A scorecard that reports perfect precision because nobody has checked yet is
worse than no scorecard -- it looks like evidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..layers import gates
from ..roles import ROLE1, ROLE2
from .labels import Label, load_labels

# ---------------------------------------------------------------------------
# Ship-threshold constants
# ---------------------------------------------------------------------------

SHIP_MAX_COMPOSITION_VIOLATIONS = 0
SHIP_MIN_GRADE_PRECISION = 0.90

# The labelling prompt asks a human for the finer IE/NI/UK/other/unknown
# split (RADAR_CONTRACTS.md section F); gates._location_country's
# deterministic bucket is coarser -- it only ever has to answer "does this
# evidence Republic of Ireland residence" for the located_ie gate, so UK and
# "other" both collapse to outside_ireland on the extractor side. Comparing
# in the EXTRACTOR's bucket (mapping the label DOWN to it) means a label of
# "UK" and one of "other" both correctly agree with an extractor answer of
# "outside_ireland" -- the extractor was never asked to tell them apart.
LABEL_TO_EXTRACTOR_COUNTRY = {
    "IE": "ireland",
    "NI": "northern_ireland",
    "UK": "outside_ireland",
    "other": "outside_ireland",
    "unknown": "unknown",
}

_ROLES = (ROLE1, ROLE2)


def _read_stage(run_dir: Path, stage: str) -> dict:
    p = run_dir / (stage + ".json")
    if not p.exists():
        raise FileNotFoundError(
            "scorecard needs " + stage + ".json in " + str(run_dir)
            + " -- run that stage first"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _grade_precision(persons: dict, labels: list[Label]) -> Optional[float]:
    pairs = [
        (persons[lbl.person_id].get("current_title") or "", lbl.grade)
        for lbl in labels
        if lbl.person_id in persons and lbl.grade != "unknown"
    ]
    if not pairs:
        return None
    correct = 0
    for title, label_grade in pairs:
        extracted = gates._grade_from_title(title) or "unknown"
        if extracted == label_grade:
            correct += 1
    return correct / len(pairs)


def _residence_precision(persons: dict, labels: list[Label]) -> Optional[float]:
    pairs = [
        (persons[lbl.person_id].get("location") or "", lbl.location_country)
        for lbl in labels
        if lbl.person_id in persons and lbl.location_country != "unknown"
    ]
    if not pairs:
        return None
    correct = 0
    for location, label_country in pairs:
        extracted = gates._location_country(location)
        expected = LABEL_TO_EXTRACTOR_COUNTRY[label_country]
        if extracted == expected:
            correct += 1
    return correct / len(pairs)


def compute_scorecard(
    run_dir: Path,
    labels_path: Optional[Path] = None,
    spend_eur: Optional[float] = None,
) -> dict:
    """Compute the six numbers for the run directory `run_dir`.

    `labels_path` overrides eval/labels.jsonl (tests use this). `spend_eur`
    overrides a live read of core.providers.spend_eur() (tests use this too,
    since that tracker is an in-process global that resets per process --
    when this stage runs as the tail of `--stage all` it reflects that
    process's real spend; run standalone it reads 0.0, same caveat as
    run.py's own "LLM spend this run" line).
    """
    extract = _read_stage(run_dir, "extract")
    validate = _read_stage(run_dir, "validate")
    gate_out = _read_stage(run_dir, "gate")
    poolmap = _read_stage(run_dir, "poolmap")
    delivery = (
        json.loads((run_dir / "delivery.json").read_text(encoding="utf-8"))
        if (run_dir / "delivery.json").exists()
        else None
    )

    persons: dict = extract.get("persons", {})

    # -- composition_violations ----------------------------------------------
    violations: list[str] = []
    if delivery is not None:
        for spec in _ROLES:
            cards = [
                {
                    "full_name": persons[pid].get("full_name", pid),
                    "current_title": persons[pid].get("current_title"),
                    "location": persons[pid].get("location"),
                }
                for pid in delivery.get(spec.role_id, [])
                if pid in persons
            ]
            violations.extend(gates.composition_violations(cards, spec))

    # -- quote_drop_rate -------------------------------------------------------
    drop_rate = validate.get("stats", {}).get("drop_rate")

    # -- delivered_over_pool ---------------------------------------------------
    total_delivered = sum(m.get("delivered", 0) for m in poolmap.values())
    total_assessed = sum(m.get("profiles_assessed", 0) for m in poolmap.values())
    delivered_over_pool = (total_delivered / total_assessed) if total_assessed else 0.0

    # -- cost_per_delivered_card -----------------------------------------------
    if spend_eur is None:
        from ..core.providers import spend_eur as _live_spend_eur

        spend_eur = _live_spend_eur()
    cost_per_delivered_card = (spend_eur / total_delivered) if total_delivered else None

    # -- labels-derived precision -----------------------------------------------
    labels = load_labels(labels_path) if labels_path is not None else load_labels()
    grade_precision = _grade_precision(persons, labels)
    residence_precision = _residence_precision(persons, labels)

    result = {
        "campaign_run_dir": str(run_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_labels": len(labels),
        "composition_violations": len(violations),
        "composition_violations_detail": violations,
        "quote_drop_rate": drop_rate,
        "grade_precision": grade_precision,
        "residence_precision": residence_precision,
        "delivered_over_pool": delivered_over_pool,
        "delivered": total_delivered,
        "profiles_assessed": total_assessed,
        "spend_eur": spend_eur,
        "cost_per_delivered_card": cost_per_delivered_card,
    }
    ok, reasons = ship_ok(result)
    result["ship_ok"] = ok
    result["ship_reasons"] = reasons
    # Kept unused-import-free: gate_out is read to satisfy RADAR_CONTRACTS.md
    # section F's "reads gate.json" and to fail loudly (via _read_stage) when
    # the gate stage has not run -- scorecard.json should never describe a
    # pool nobody has actually gated.
    del gate_out
    return result


def ship_ok(scorecard: dict) -> tuple[bool, list[str]]:
    """Whether `scorecard` clears the ship thresholds, and why not if not.

    A missing grade_precision (no labels yet) is advisory, not a ship
    blocker -- labelling is a periodic QA sample, not something every run
    can be expected to have fresh. It is surfaced in the printed table
    ("n/a (no labels)") instead, so nobody mistakes silence for a pass.
    """
    reasons: list[str] = []
    violations = scorecard.get("composition_violations", 0)
    if violations > SHIP_MAX_COMPOSITION_VIOLATIONS:
        reasons.append(
            "composition_violations: " + str(violations) + " > "
            + str(SHIP_MAX_COMPOSITION_VIOLATIONS)
        )
    grade_precision = scorecard.get("grade_precision")
    if grade_precision is not None and grade_precision < SHIP_MIN_GRADE_PRECISION:
        reasons.append(
            "grade_precision: " + format(grade_precision, ".2f") + " < "
            + format(SHIP_MIN_GRADE_PRECISION, ".2f")
        )
    return (len(reasons) == 0, reasons)


def _fmt_pct(x: Optional[float]) -> str:
    return "n/a (no labels)" if x is None else format(x * 100, ".1f") + "%"


def _fmt_eur(x: Optional[float]) -> str:
    return "n/a (nobody delivered)" if x is None else "EUR " + format(x, ".2f")


def render_table(sc: dict) -> list[str]:
    """The scorecard as a list of print-ready lines (run.py logs them)."""
    lines = [
        "scorecard -- " + sc["campaign_run_dir"],
        "  composition_violations : " + str(sc["composition_violations"])
        + (" (threshold " + str(SHIP_MAX_COMPOSITION_VIOLATIONS) + ")"),
        "  quote_drop_rate        : "
        + (format(sc["quote_drop_rate"] * 100, ".1f") + "%"
           if sc["quote_drop_rate"] is not None else "n/a"),
        "  grade_precision        : " + _fmt_pct(sc["grade_precision"])
        + " (threshold " + format(SHIP_MIN_GRADE_PRECISION * 100, ".0f") + "%, n="
        + str(sc["n_labels"]) + " labels)",
        "  residence_precision    : " + _fmt_pct(sc["residence_precision"]),
        "  delivered_over_pool    : " + format(sc["delivered_over_pool"] * 100, ".1f")
        + "% (" + str(sc["delivered"]) + " of " + str(sc["profiles_assessed"]) + ")",
        "  cost_per_delivered_card: " + _fmt_eur(sc["cost_per_delivered_card"])
        + " (run spend EUR " + format(sc["spend_eur"], ".2f") + ")",
        "  SHIP: " + ("OK" if sc["ship_ok"] else "BLOCKED"),
    ]
    for reason in sc["ship_reasons"]:
        lines.append("    - " + reason)
    if sc["composition_violations_detail"]:
        lines.append("  composition violations:")
        for v in sc["composition_violations_detail"]:
            lines.append("    - " + v)
    return lines
