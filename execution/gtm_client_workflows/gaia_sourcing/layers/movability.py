"""
L10 -- movability assessment (SPEC.md section 11).

"A movability field that always returns a confident answer is a movability
field nobody believes."

So `unknown` is the default, not the fallback. The model is only permitted to
return high/medium/low when it can name an evidenced signal, and a
deterministic post-check downgrades any assessment whose rationale cites no
signal at all. For most publicly-sourced engineers the honest answer really
is `unknown`, and a card that says so is worth more than one that guesses.

Deterministic signals computed here (not asked of the model):
  - geographic friction between the candidate's evidenced base and the role's
    location, which is the single most actionable movability fact for a Cork
    role filled from Dublin.
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.contracts import JobSpec, MovabilitySignal, Person, ValidatedClaim
from ..core.providers import ROLE_JUDGE, call_role

SYSTEM = """You assess how movable an engineer is, from public evidence only.

This is a judgement a recruiter makes before spending an hour on a call, so it
must be honest rather than encouraging.

RULES

1. "unknown" is the correct answer whenever the evidence does not support a
   view. Use it freely. It is not a failure.
2. Every signal you list must be traceable to the supplied claims. Do not
   speculate about someone's private circumstances, family, or intentions.
3. Never infer movability from age, gender, nationality, or anything about a
   person's protected characteristics.
4. Weigh: tenure in the current role (a recent promotion or a new joiner is
   hard to move; four-plus years static is more approachable), employer
   trajectory, completion of chartership (which often precedes a move), and
   geographic friction relative to the role's location.
5. The rationale is shown to the client. Two sentences at most, plain, no
   salesmanship.
"""

TOOL = {
    "name": "emit_movability",
    "description": "Assess how movable this candidate is, from evidence only.",
    "input_schema": {
        "type": "object",
        "properties": {
            "assessment": {
                "type": "string",
                "enum": ["high", "medium", "low", "unknown"],
            },
            "signals": {
                "type": "array",
                "description": "Evidenced signals behind the assessment.",
                "items": {"type": "string"},
            },
            "tenure_months_current": {
                "type": "integer",
                "description": (
                    "Months in the current role if the evidence states or "
                    "dates it. Use 0 when unknown."
                ),
            },
            "rationale": {"type": "string"},
        },
        "required": ["assessment", "signals", "rationale"],
    },
}

RUN_COST: list[dict] = []

_CITY_RE = re.compile(
    r"\b(dublin|cork|limerick|galway|waterford|sligo|athlone|kilkenny|"
    r"ennis|tralee|wexford|drogheda|dundalk)\b",
    re.I,
)


def geographic_friction(
    person: Person, claims: list[ValidatedClaim], spec: JobSpec
) -> Optional[str]:
    """Deterministic note when the candidate's base differs from the role's.

    Not an exclusion -- the located_ie gate already decided that. This is the
    thing a consultant needs to raise in the first call, so it is computed in
    code rather than left to the model to remember.
    """
    role_cities: set[str] = set()
    for loc in spec.locations:
        for m in _CITY_RE.finditer(loc):
            role_cities.add(m.group(0).lower())
    if not role_cities:
        return None

    blob = " ".join(
        [person.location or "", person.current_title or ""]
        + [c.assertion + " " + c.evidence_quote for c in claims if c.dimension == "location"]
    )
    found = {m.group(0).lower() for m in _CITY_RE.finditer(blob)}
    if not found:
        return None
    if found & role_cities:
        return None
    return (
        "Evidenced base is "
        + "/".join(sorted(c.capitalize() for c in found))
        + "; the role is in "
        + "/".join(sorted(c.capitalize() for c in role_cities))
        + ". Confirm willingness to relocate or commute."
    )


def assess(
    person: Person, claims: list[ValidatedClaim], spec: JobSpec
) -> MovabilitySignal:
    """Assess one candidate. Any failure yields `unknown`, never a guess."""
    friction = geographic_friction(person, claims, spec)

    lines = [
        "ROLE LOCATION: " + ", ".join(spec.locations),
        "CANDIDATE: " + person.full_name,
        "TITLE: " + (person.current_title or "not stated"),
        "EMPLOYER: " + (person.current_employer or "not stated"),
        "",
        "EVIDENCED CLAIMS:",
    ]
    for c in claims:
        lines.append(
            "  - [" + c.dimension + "] " + c.assertion
            + " || quote: \"" + c.evidence_quote.strip()[:220] + "\""
        )
    if friction:
        lines.append("")
        lines.append("DETERMINISTIC GEOGRAPHIC NOTE: " + friction)
    lines.append("")
    lines.append("Assess movability. Answer 'unknown' unless the evidence supports more.")

    try:
        out, meta = call_role(
            role=ROLE_JUDGE, system=SYSTEM, user="\n".join(lines), tool=TOOL,
            max_tokens=900,
        )
        RUN_COST.append(meta)
    except Exception as exc:
        print("[movability] " + person.person_id + " failed: " + repr(exc)[:120])
        out = None

    if not out:
        return MovabilitySignal(
            person_id=person.person_id,
            assessment="unknown",
            signals=[friction] if friction else [],
            rationale=(
                "Movability was not assessed for this candidate; treat it as "
                "unknown." + (" " + friction if friction else "")
            ),
        )

    signals = [s.strip() for s in (out.get("signals") or []) if s.strip()]
    if friction and friction not in signals:
        signals.append(friction)

    assessment = str(out.get("assessment", "unknown")).lower()
    if assessment not in ("high", "medium", "low", "unknown"):
        assessment = "unknown"
    # A confident assessment with nothing behind it is exactly the failure
    # mode section 11 warns about. Downgraded here rather than shipped.
    if assessment != "unknown" and not signals:
        assessment = "unknown"

    tenure = out.get("tenure_months_current")
    if not isinstance(tenure, int) or tenure <= 0:
        tenure = None

    rationale = (out.get("rationale") or "").strip()
    if friction and friction not in rationale:
        rationale = (rationale + " " + friction).strip()

    return MovabilitySignal(
        person_id=person.person_id,
        tenure_months_current=tenure,
        signals=signals,
        assessment=assessment,
        rationale=rationale or "No evidenced basis for a movability view.",
    )
