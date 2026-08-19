"""
L7 -- hard gates.

SPEC.md I3 and section 8: gates are deterministic Python. Never an LLM
judgement, never a weighted score component. A candidate cannot "compensate"
for not being chartered by being good at Tekla.

Gates run against VALIDATED claims only (L6 output). A claim that was dropped
for failing its quote check cannot satisfy a gate -- that is the whole point
of the layering.
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.contracts import GateResult, JobSpec, Person, ValidatedClaim

# ---------------------------------------------------------------------------
# Chartership
# ---------------------------------------------------------------------------

# Post-nominals and phrasings that evidence Engineers Ireland chartership.
# Word-boundary anchored: "ceng" must not match inside "licensing".
_CHARTERED_PATTERNS = [
    r"\bceng\b",
    r"\bc\.eng\b",
    r"\bmiei\b",
    r"\bfiei\b",
    r"\bchartered engineer\b",
    r"\bchartered member of the institution of engineers of ireland\b",
    r"\bchartered member and fellow of the institution of engineers of ireland\b",
    r"\bchartered with engineers ireland\b",
    # Fellow is Engineers Ireland's SENIOR grade, above Chartered Engineer,
    # and the gate's own description already names FIEI as qualifying. The
    # abbreviation matched and the spelled-out form did not, so a witness who
    # wrote "I am a Fellow member of Engineers Ireland" failed a gate that his
    # own evidence cleared twice over -- costing the transport role a Fellow
    # of both Engineers Ireland and the IStructE, at an Irish consultancy.
    #
    # Bound to Engineers Ireland specifically. "Fellow of the Institution of
    # Structural Engineers" is IStructE and must keep failing to the non-IE
    # branch below, and "Fellow of the Association of Consulting Engineers of
    # Ireland" is a trade body, not a chartership.
    r"\bfellow\b[^.]{0,40}\bengineers ireland\b",
    r"\bfellow\b[^.]{0,40}\binstitution of engineers of ireland\b",
]
_CHARTERED_RE = re.compile("|".join(_CHARTERED_PATTERNS), re.I)

# UK/other-jurisdiction chartership is NOT Engineers Ireland chartership.
# Flagged rather than silently accepted -- the adversarial pass reads this.
_NON_IE_CHARTER_RE = re.compile(
    r"\b(mice|fice|mistructe|fistructe|imeche|"
    r"institution of civil engineers|institution of structural engineers)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

_IE_TOKENS = [
    "ireland", "republic of ireland", "eire",
    "dublin", "cork", "limerick", "galway", "waterford", "kilkenny",
    "athlone", "sligo", "ennis", "tralee", "kildare", "meath", "louth",
    "wexford", "carlow", "clare", "kerry", "mayo", "donegal", "westmeath",
    "tipperary", "offaly", "laois", "longford", "roscommon", "leitrim",
    "cavan", "monaghan", "wicklow",
]
_IE_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _IE_TOKENS) + r")\b", re.I)

# Northern Ireland is a different chartership/contract regime and is NOT the
# Republic. Explicitly separated per SPEC.md section 14 adversarial fixtures.
_NI_TOKENS = [
    "northern ireland", "belfast", "derry", "londonderry", "antrim",
    "armagh", "fermanagh", "tyrone", "lisburn", "newry",
]
_NI_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _NI_TOKENS) + r")\b", re.I)

# Irish statutory bodies and semi-states. Evidence of advising these places
# a witness in the Republic even when no location is stated.
_IRISH_BODY_RE = re.compile(
    r"\b(transport infrastructure ireland|\btii\b|iarnrod eireann|iarnrod|"
    r"coras iompair eireann|\bcie\b|national transport authority|\bnta\b|"
    r"an bord pleanala|an coimisiun pleanala|office of public works|\bopw\b|"
    r"uisce eireann|irish water|esb networks|county council|city council|"
    r"engineers ireland)\b",
    re.I,
)

_NON_IE_RE = re.compile(
    r"\b(united kingdom|england|scotland|wales|london|manchester|birmingham|"
    r"leeds|glasgow|edinburgh|bristol|qatar|dubai|uae|australia|canada|"
    r"united states|new zealand)\b",
    re.I,
)


def _strip_ni(text: str) -> str:
    """Blank out Northern Ireland phrases before testing for Republic tokens."""
    return _NI_RE.sub(" ", text)


def _claims_by_dim(claims: list[ValidatedClaim], *dims: str) -> list[ValidatedClaim]:
    return [c for c in claims if c.dimension in dims]


def _direct(claims: list[ValidatedClaim]) -> list[ValidatedClaim]:
    return [c for c in claims if c.confidence == "direct"]


# ---------------------------------------------------------------------------
# Individual gate checks
# ---------------------------------------------------------------------------


def check_chartered(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    for c in _direct(_claims_by_dim(claims, "chartership")):
        blob = c.assertion + " " + c.evidence_quote
        if _CHARTERED_RE.search(blob):
            return GateResult(gate_id="chartered", passed=True, basis=c.claim_id)
    # Non-IE chartership found but no Engineers Ireland evidence.
    for c in _claims_by_dim(claims, "chartership"):
        if _NON_IE_CHARTER_RE.search(c.assertion + " " + c.evidence_quote):
            return GateResult(
                gate_id="chartered",
                passed=False,
                basis=c.claim_id,
                note=(
                    "Chartership evidenced with a non-Irish institution only; "
                    "no Engineers Ireland CEng/MIEI evidence found."
                ),
            )
    return GateResult(
        gate_id="chartered",
        passed=False,
        note="No public evidence of Engineers Ireland chartership found.",
    )


def check_located_ie(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    loc_claims = _direct(_claims_by_dim(claims, "location"))
    haystacks = [(c.claim_id, c.assertion + " " + c.evidence_quote) for c in loc_claims]
    if person.location:
        haystacks.append(("person.location", person.location))

    # Northern Ireland excludes only when NO Republic evidence exists anywhere
    # in the claim set. A witness who has "co-ordinated EIARs in a number of
    # jurisdictions including Ireland, Northern Ireland and Scotland" is not
    # Belfast-based -- treating that mention as disqualifying was a false
    # negative that excluded five qualified Jacobs engineers on the first run.
    # NI phrases are stripped before the Republic test because "Northern
    # Ireland" contains the substring "Ireland" -- without this, a Belfast
    # address reads as Republic evidence and the NI exclusion never fires.
    any_republic = any(_IE_RE.search(_strip_ni(b)) for _, b in haystacks)
    if not any_republic:
        for cid, blob in haystacks:
            if _NI_RE.search(blob):
                return GateResult(
                    gate_id="located_ie",
                    passed=False,
                    basis=cid,
                    note=(
                        "Located in Northern Ireland -- different chartership and "
                        "contract regime to the Republic. Confirm before proceeding."
                    ),
                )
    for cid, blob in haystacks:
        if _IE_RE.search(_strip_ni(blob)):
            note = None
            if _NI_RE.search(blob) or _NON_IE_RE.search(blob):
                note = (
                    "Ireland evidenced alongside other jurisdictions -- confirm "
                    "current base in the first call."
                )
            return GateResult(
                gate_id="located_ie", passed=True, basis=cid, note=note
            )

    # Fall back to Irish-scheme / Irish-client evidence. Witness statements
    # rarely say "I live in Dublin"; they evidence location by the schemes
    # and bodies they work for. Recorded with a note so the card stays honest.
    for c in _direct(_claims_by_dim(claims, "project", "employer", "statutory_process")):
        blob = c.assertion + " " + c.evidence_quote
        if _IE_RE.search(blob) or _IRISH_BODY_RE.search(blob):
            return GateResult(
                gate_id="located_ie",
                passed=True,
                basis=c.claim_id,
                note=(
                    "Ireland-based inferred from Irish scheme/client evidence, "
                    "not from a stated location. Confirm in the first call."
                ),
            )
    for cid, blob in haystacks:
        if _NON_IE_RE.search(blob):
            return GateResult(
                gate_id="located_ie",
                passed=False,
                basis=cid,
                note="Evidence places this candidate outside Ireland.",
            )
    return GateResult(
        gate_id="located_ie",
        passed=False,
        note="No public evidence of an Ireland-based location found.",
    )


def check_discipline(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    include = [t.lower() for t in params.get("include", [])]
    exclude = [t.lower() for t in params.get("exclude", [])]
    blobs = [
        (c.claim_id, (c.assertion + " " + c.evidence_quote).lower())
        for c in _direct(_claims_by_dim(claims, "sector", "employer", "project"))
    ]
    if person.current_title:
        blobs.append(("person.title", person.current_title.lower()))

    for cid, blob in blobs:
        for term in exclude:
            if term in blob:
                return GateResult(
                    gate_id="discipline",
                    passed=False,
                    basis=cid,
                    note="Evidence indicates an excluded discipline: " + term,
                )
    for cid, blob in blobs:
        for term in include:
            if term in blob:
                return GateResult(gate_id="discipline", passed=True, basis=cid)
    return GateResult(
        gate_id="discipline",
        passed=False,
        note="No public evidence placing this candidate in the target discipline.",
    )


_YEARS_RE = re.compile(
    # \b on both sides of the digits: without it, "2024" yields a spurious
    # "24 years" match and a four-digit year satisfies a seniority gate.
    r"\b(\d{1,2})\b\s*\+?\s*years?"
    r"(?:\s*(?:of\s+)?(?:post[- ]?graduate\s+)?"
    r"(?:professional\s+|relevant\s+|industry\s+)?experience)?",
    re.I,
)


_WORD_NUM = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
_WORD_YEARS_RE = re.compile(
    r"\b(twenty|thirty|forty|fifty)(?:[\s-]+(one|two|three|four|five|six|"
    r"seven|eight|nine))?\s+years?\b|\b(ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen)\s+years?\b",
    re.I,
)


def _extract_word_years(text: str) -> Optional[int]:
    best = None
    for m in _WORD_YEARS_RE.finditer(text):
        if m.group(1):
            val = _TENS[m.group(1).lower()]
            if m.group(2):
                val += _WORD_NUM[m.group(2).lower()]
        elif m.group(3):
            val = _WORD_NUM[m.group(3).lower()]
        else:
            continue
        if best is None or val > best:
            best = val
    return best


def extract_years(text: str) -> Optional[int]:
    """Largest plausible 'N years experience' figure in the text.

    Bounded at 60 so a stray four-digit year or a scheme name containing
    digits cannot satisfy a seniority gate.
    """
    best: Optional[int] = None
    for m in _YEARS_RE.finditer(text):
        try:
            n = int(m.group(1))
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 60 and (best is None or n > best):
            best = n
    worded = _extract_word_years(text)
    if worded is not None and (best is None or worded > best):
        best = worded
    return best


# Grades that cannot be reached inside 8 years at an engineering consultancy.
# Deliberately excludes "Senior Engineer", which is reachable at ~5 years.
_SENIOR_GRADE_RE = re.compile(
    r"\b(technical director|regional director|managing director|"
    r"associate director|director of|structural director|civil director|"
    r"principal engineer|practice leader|head of structures|"
    r"head of engineering|partner)\b",
    re.I,
)


def _senior_grade(
    person: Person, claims: list[ValidatedClaim]
) -> Optional[tuple[str, str]]:
    """Return (matched_grade, basis) when a senior grade is evidenced."""
    if person.current_title:
        m = _SENIOR_GRADE_RE.search(person.current_title)
        if m:
            return m.group(0), "person.title"
    for c in _direct(_claims_by_dim(claims, "employer")):
        m = _SENIOR_GRADE_RE.search(c.assertion + " " + c.evidence_quote)
        if m:
            return m.group(0), c.claim_id
    return None


def check_seniority(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    minimum = int(params.get("min_years", 8))
    evidenced: list[tuple[int, str]] = []
    for c in _direct(_claims_by_dim(claims, "years_experience")):
        years = extract_years(c.evidence_quote)
        if years is None:
            years = extract_years(c.assertion)
        if years is not None:
            evidenced.append((years, c.claim_id))

    if not evidenced:
        # Staff-directory bios state a GRADE, not a number of years. A
        # Director or Associate Director at an engineering consultancy is
        # necessarily well past 8 years, but that is an inference, so it
        # passes only when the role opts in AND the card carries the note.
        if params.get("allow_grade_inference"):
            grade = _senior_grade(person, claims)
            if grade:
                return GateResult(
                    gate_id="seniority",
                    passed=True,
                    basis=grade[1],
                    note=(
                        "Seniority inferred from grade (" + grade[0] + "); "
                        "years of experience not stated publicly. Confirm in "
                        "the first call."
                    ),
                )
        return GateResult(
            gate_id="seniority",
            passed=False,
            note="No public evidence of " + str(minimum) + "+ years' experience found.",
        )

    best_years, best_cid = max(evidenced, key=lambda t: t[0])
    if best_years >= minimum:
        return GateResult(gate_id="seniority", passed=True, basis=best_cid)
    return GateResult(
        gate_id="seniority",
        passed=False,
        basis=best_cid,
        note=(
            "Evidenced at " + str(best_years) + " years' experience, below the "
            + str(minimum) + "-year threshold."
        ),
    )


def check_not_client(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    """Client-conflict gate. Sourcing from the client is disqualifying."""
    off = [t.lower() for t in params.get("off_limits", [])]
    blobs = [
        (c.claim_id, (c.assertion + " " + c.evidence_quote).lower())
        for c in _claims_by_dim(claims, "employer")
    ]
    if person.current_employer:
        blobs.append(("person.employer", person.current_employer.lower()))

    for cid, blob in blobs:
        for term in off:
            if term in blob:
                return GateResult(
                    gate_id="not_client",
                    passed=False,
                    basis=cid,
                    note="Currently at client organisation -- off-limits: " + term,
                )
    return GateResult(gate_id="not_client", passed=True)


_CHECKS = {
    "chartered": check_chartered,
    "located_ie": check_located_ie,
    "discipline": check_discipline,
    "seniority_years": check_seniority,
    "not_client": check_not_client,
}


def run_gates(
    person: Person, claims: list[ValidatedClaim], spec: JobSpec
) -> list[GateResult]:
    results: list[GateResult] = []
    for gate in spec.hard_gates:
        fn = _CHECKS.get(gate.check)
        if fn is None:
            raise ValueError("Unknown gate check: " + str(gate.check))
        res = fn(person, claims, gate.params)
        res.gate_id = gate.gate_id
        results.append(res)
    return results


def all_passed(results: list[GateResult]) -> bool:
    return all(r.passed for r in results)


def failed_gates(results: list[GateResult]) -> list[GateResult]:
    return [r for r in results if not r.passed]


# ---------------------------------------------------------------------------
# Tiering (SPEC.md section 8). Tiers, never floats.
# ---------------------------------------------------------------------------


def assign_tier(
    claims: list[ValidatedClaim], gate_results: list[GateResult], spec: JobSpec
) -> str:
    """A / B / C for gate-passing candidates, EXCLUDED otherwise.

    A -- all gates + >=2 direct claims on the role's primary signal
    B -- all gates + exactly 1 direct claim on the primary signal
    C -- all gates, primary signal unevidenced (gap stated on the card)
    """
    if not all_passed(gate_results):
        return "EXCLUDED"
    primary = _direct(_claims_by_dim(claims, spec.primary_signal_dimension))
    if len(primary) >= 2:
        return "A"
    if len(primary) == 1:
        return "B"
    return "C"
