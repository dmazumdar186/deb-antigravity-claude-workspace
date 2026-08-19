"""
L8 -- the blind adversarial second pass (SPEC.md section 9).

"If Pass 2 sees Pass 1's reasoning, you get sycophantic agreement and the
whole exercise is theatre."

So this module is deliberately built so that it CANNOT see pass 1's output.
The prompt receives:
  - the role brief
  - the candidate's validated claims (quote + assertion only)
  - excerpts of the raw source text

and never receives: the tier, the gate results, the strengths, or any
justification produced earlier in the pipeline. `build_user_prompt` is a
pure function of those three inputs, and the test suite asserts that no
tier letter or gate verdict appears in the string it produces.

The model does NOT set the tier. It reports findings, and a deterministic
rule here decides whether a finding is severe enough to demote. Letting an
LLM write the tier field would violate I3 by the back door.
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.contracts import (
    Evaluation,
    GateResult,
    JobSpec,
    Person,
    RawDocument,
    ValidatedClaim,
    as_list,
)
from ..core.providers import ROLE_JUDGE, call_role

SYSTEM = """You are a sceptical senior recruiter reviewing a shortlisted engineer.

Your brief is to find every reason this person is WRONG for this role. You are
the second opinion, and you are deliberately not told what the first opinion
concluded. Assume the first pass was too generous, because it usually is.

Hunt specifically for:
  - GEOGRAPHY: UK-based, Northern Ireland rather than the Republic (different
    chartership and contract regimes), or an Irish scheme worked remotely from
    another country.
  - DISCIPLINE DRIFT: bridges when the role wants buildings, water when the
    role wants transport, "civil" used as a catch-all.
  - SENIORITY INFLATION: a grade that sounds senior at a small firm, a title
    that does not match the evidenced years.
  - RECENT PROMOTION or a very short tenure, which makes someone hard to move.
  - EMPLOYER CONFLICT: any tie to the hiring client.
  - TECHNICALLY-TRUE-BUT-MISLEADING claims: a quote that supports the words of
    an assertion while the surrounding context changes its meaning. Read the
    source excerpts for context the claim omits.
  - STALENESS: evidence that describes work from a decade ago presented as
    current capability.

RULES

1. Ground every finding in the supplied material. If you cannot point to
   something in the claims or the excerpts, do not raise it.
2. Do NOT invent facts to justify a concern. "No evidence either way" is an
   unknown, not a finding.
3. Findings are shown verbatim to the client, so write them as a colleague
   would: one plain sentence, specific, no hedging padding.
4. Unknowns are things the material genuinely does not settle. They become
   screening questions for the recruiter's first call, so make them
   answerable in a phone conversation.
5. If the candidate genuinely looks sound, return few findings. Manufacturing
   objections to appear rigorous is as damaging as missing real ones.
"""

TOOL = {
    "name": "emit_critique",
    "description": "Report the reasons this candidate may be wrong for the role.",
    "input_schema": {
        "type": "object",
        "properties": {
            "adversarial_findings": {
                "type": "array",
                "description": (
                    "Concrete concerns grounded in the supplied material. "
                    "One plain sentence each. Empty list if there are none."
                ),
                "items": {"type": "string"},
            },
            "unknowns": {
                "type": "array",
                "description": (
                    "What the material does not settle. Phrased so a recruiter "
                    "can resolve it in a first call."
                ),
                "items": {"type": "string"},
            },
            "strengths": {
                "type": "array",
                "description": (
                    "Evidenced reasons this person fits, each traceable to a "
                    "supplied claim. Keep to at most four."
                ),
                "items": {"type": "string"},
            },
            "severity": {
                "type": "string",
                "enum": ["none", "minor", "material", "disqualifying"],
                "description": (
                    "Worst single finding. 'material' means a recruiter should "
                    "qualify it before presenting. 'disqualifying' means the "
                    "person does not meet the role at all."
                ),
            },
        },
        "required": ["adversarial_findings", "unknowns", "strengths", "severity"],
    },
}

RUN_COST: list[dict] = []

_EXCERPT_PER_DOC = 6000
_MAX_DOCS = 3


def build_user_prompt(
    person: Person,
    claims: list[ValidatedClaim],
    spec: JobSpec,
    corpus: dict[str, RawDocument],
) -> str:
    """Assemble the blind prompt.

    Pure function of (person, claims, role, sources). Nothing derived from
    L7 or from an earlier evaluation is reachable from here -- that is what
    makes the pass blind, and it is asserted in the test suite.
    """
    lines = [
        "ROLE: " + spec.title,
        "LOCATIONS THIS ROLE MUST BE SERVED FROM: " + ", ".join(spec.locations),
        "REQUIRED: " + "; ".join(g.description for g in spec.hard_gates),
        "PRIMARY TECHNICAL SIGNAL: " + spec.primary_signal_dimension,
        "",
        "CANDIDATE: " + person.full_name,
        "STATED TITLE: " + (person.current_title or "not stated"),
        "STATED EMPLOYER: " + (person.current_employer or "not stated"),
        "",
        "CLAIMS MADE ABOUT THIS PERSON (each already verified to appear "
        "verbatim in its source):",
    ]
    for c in claims:
        lines.append(
            "  - [" + c.dimension + "/" + c.confidence + "] " + c.assertion
            + "\n      quote: \"" + c.evidence_quote.strip() + "\""
        )

    doc_ids: list[str] = []
    for c in claims:
        if c.source_doc_id not in doc_ids:
            doc_ids.append(c.source_doc_id)

    lines.append("")
    lines.append("SOURCE EXCERPTS (for context the claims may have omitted):")
    for did in doc_ids[:_MAX_DOCS]:
        doc = corpus.get(did)
        if doc is None:
            continue
        lines.append("--- " + str(doc.url) + " ---")
        lines.append(doc.content_text[:_EXCERPT_PER_DOC])
    lines.append("")
    lines.append(
        "Report every reason this person may be wrong for this role, plus what "
        "the material leaves unresolved."
    )
    return "\n".join(lines)


# A finding that trips one of these is treated as material even when the model
# labels it minor. The model's own severity is advisory; demotion is decided
# by deterministic rules so tiering stays reproducible (I3).
_MATERIAL_RE = re.compile(
    r"\b(northern ireland|belfast|united kingdom|uk-based|based in the uk|"
    r"england|scotland|wales|not chartered|no evidence of chartership|"
    r"different discipline|wrong discipline|outside ireland|"
    r"recently promoted|joined (?:only )?(?:this|last) year)\b",
    re.I,
)


def _demote(tier: str) -> str:
    return {"A": "B", "B": "C", "C": "C"}.get(tier, tier)


def _lines(items) -> list[str]:
    """Coerce a findings/unknowns/strengths list to clean strings.

    The schema asks for strings and the model occasionally returns objects
    ({"finding": "...", "severity": "..."}) instead. Left unguarded, one such
    item raised AttributeError and cost that candidate their entire second
    opinion -- the card then had to say REVIEW INCOMPLETE over a formatting
    detail. A dict is flattened to its text values rather than dropped,
    because unlike a claim, a finding carries no evidence contract to break:
    the worst case is a slightly clumsy sentence on the card, and the best
    case is a real objection that would otherwise have been lost.
    """
    # The CONTAINER's type is checked before the items'. This guard existed
    # for items and not for the list itself, and the gap shipped: two cards in
    # the delivered dossier rendered their "Not verified / open questions"
    # section as ONE BULLET PER CHARACTER -- 1651 and 1885 of them -- because
    # the model returned the whole field as a JSON-encoded string rather than
    # an array, and iterating a str yields characters.
    #
    # Every space was dropped too, since a single space fails the `if text`
    # test below, so the text was not merely mangled but unrecoverable from
    # the stored output. A schema says "array of strings"; a string is also
    # iterable, and that is the entire bug.
    out: list[str] = []
    for item in as_list(items):
        if item is None:
            continue
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = " ".join(str(v) for v in item.values() if isinstance(v, (str, int, float)))
        else:
            text = str(item)
        text = text.strip()
        if text:
            out.append(text)
    return out


def critique(
    person: Person,
    claims: list[ValidatedClaim],
    spec: JobSpec,
    corpus: dict[str, RawDocument],
    gate_results: list[GateResult],
    tier: str,
) -> Evaluation:
    """Run the blind critique and fold it into an Evaluation.

    `gate_results` and `tier` arrive here ONLY to be written into the output
    record and to apply the deterministic demotion rule. They are not passed
    to the model -- see build_user_prompt.
    """
    user = build_user_prompt(person, claims, spec, corpus)

    try:
        out, meta = call_role(
            role=ROLE_JUDGE, system=SYSTEM, user=user, tool=TOOL, max_tokens=2000
        )
        RUN_COST.append(meta)
    except Exception as exc:
        # An adversarial pass that failed is NOT an adversarial pass that
        # found nothing. The card must say so rather than imply a clean review.
        print("[adversarial] " + person.person_id + " failed: " + repr(exc)[:120])
        return Evaluation(
            person_id=person.person_id,
            role_id=spec.role_id,
            tier=tier,
            gates=gate_results,
            strengths=[],
            unknowns=["Adversarial review did not complete for this candidate."],
            adversarial_findings=[
                "REVIEW INCOMPLETE -- the second-opinion pass errored, so this "
                "card has had one pass only. Treat its confidence accordingly."
            ],
        )

    if not out:
        return Evaluation(
            person_id=person.person_id, role_id=spec.role_id, tier=tier,
            gates=gate_results, strengths=[],
            unknowns=["Adversarial review returned no structured result."],
            adversarial_findings=[
                "REVIEW INCOMPLETE -- the second-opinion pass returned nothing "
                "parseable. This card has had one pass only."
            ],
        )

    findings = _lines(out.get("adversarial_findings"))
    unknowns = _lines(out.get("unknowns"))
    strengths = _lines(out.get("strengths"))[:4]
    severity = str(out.get("severity", "none")).lower()

    material = severity in ("material", "disqualifying") or any(
        _MATERIAL_RE.search(f) for f in findings
    )
    final_tier = _demote(tier) if material else tier

    return Evaluation(
        person_id=person.person_id,
        role_id=spec.role_id,
        tier=final_tier,
        gates=gate_results,
        strengths=strengths,
        unknowns=unknowns,
        adversarial_findings=findings,
    )


def unverified_lines(
    claims: list[ValidatedClaim], spec: JobSpec, gate_results: list[GateResult]
) -> list[str]:
    """Deterministic 'Not Verified' lines (SPEC.md section 13).

    Generated from what the evidence set actually lacks, not from the model's
    opinion, so the section cannot quietly shrink when a model feels
    confident. Merged with the LLM's unknowns at render time.
    """
    dims = {c.dimension for c in claims if c.confidence == "direct"}
    out: list[str] = []

    if "chartership" not in dims:
        out.append("Engineers Ireland chartership not evidenced in a public source.")
    if "years_experience" not in dims:
        out.append(
            "Years of experience not stated publicly -- seniority is read from "
            "grade and role history."
        )
    if spec.primary_signal_dimension not in dims:
        label = (
            "Eurocode / Tekla / Robot proficiency"
            if spec.primary_signal_dimension == "technical_skill"
            else "EIAR / CPO / Oral Hearing involvement"
        )
        out.append("No public evidence of " + label + ".")
    if "location" not in dims:
        out.append(
            "Current place of residence not stated publicly -- location is "
            "inferred from employer and scheme evidence."
        )

    out.append(
        "No evidence found regarding notice period, salary expectation or "
        "current job-search intent."
    )

    for g in gate_results:
        if not g.passed and g.note:
            out.append(g.note)
        elif g.passed and g.note:
            out.append(g.note)
    return out


def inferred_claim_lines(claims: list[ValidatedClaim]) -> list[str]:
    """Inferred claims render here as 'possible, unconfirmed' -- never as fact."""
    return [
        "Possible, unconfirmed: " + c.assertion
        for c in claims
        if c.confidence == "inferred"
    ]
