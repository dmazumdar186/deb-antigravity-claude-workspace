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
from ..sources.company_bios import FIRMS

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

# County/city -> commuter-town map for the `counties` LocationRule param
# (client feedback 2026-09-10: "some were not based in Ireland" -- a brief
# that names a specific county needs its evidence to actually name that
# county, not just the Republic in general). Hand-maintained, not exhaustive
# -- extend as new counties are targeted by a brief. Keys are lowercase
# county/city names as they would appear in `counties`; values are the towns
# that count as evidence of that county without naming it outright.
_COUNTY_TOWNS = {
    "cork": ["cork", "cobh", "midleton", "mallow", "carrigaline", "ballincollig"],
    "limerick": ["limerick", "shannon", "ennis"],
    "galway": ["galway", "oranmore", "tuam"],
    # Dublin's commuter belt -- Kildare/Meath/Wicklow towns routinely appear
    # in bios of people who work in Dublin.
    "dublin": ["dublin", "kildare", "meath", "wicklow"],
}

# Signals a candidate is not currently in Ireland but is moving there --
# the Cork-relocatable clause on Role 2 needs this distinguished from an
# ordinary out-of-Ireland exclusion.
_RELOCATION_RE = re.compile(r"relocat|willing to move|returning to ireland", re.I)


def _county_matches(blob: str, counties: list[str]) -> bool:
    """True when blob names one of `counties` (or a known commuter town).

    Empty `counties` means "any Republic of Ireland location" -- always True.
    """
    if not counties:
        return True
    low = blob.lower()
    for county in counties:
        terms = _COUNTY_TOWNS.get(county.lower(), [county.lower()])
        if any(re.search(r"\b" + re.escape(t) + r"\b", low) for t in terms):
            return True
    return False


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
    """Republic-of-Ireland residence gate.

    `params` are the brief-level LocationRule knobs (client feedback
    2026-09-10: "some were not based in Ireland"). All default to the
    ORIGINAL behaviour -- an empty/absent `params` dict (every existing
    JobSpec) is unaffected:
      require_direct_evidence (default False) -- when True, the Irish
        scheme/employer fallback below can never pass the gate outright; it
        fails with a fixed note unless treat_unknown_as=="pass_with_note".
      counties (default [], any ROI) -- when non-empty, direct evidence must
        name one of these counties/cities (see _COUNTY_TOWNS) to pass.
      allow_relocation_signal (default False) -- a "relocating"/"returning to
        Ireland" claim can pass the gate on its own when set.
      treat_unknown_as (default "fail") -- only consulted when
        require_direct_evidence is True and the only evidence is the
        scheme/employer fallback.
    """
    require_direct = bool(params.get("require_direct_evidence", False))
    counties = [c.lower() for c in params.get("counties", [])]
    allow_relocation = bool(params.get("allow_relocation_signal", False))
    treat_unknown_as = params.get("treat_unknown_as", "fail")

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

    # Direct residence evidence. When `counties` is set, a Republic-wide hit
    # ("based in Ireland") is not enough -- it must name one of the target
    # counties/towns. A match on the wrong county is remembered rather than
    # discarded so the eventual failure note is specific, not generic.
    county_reject_cid: Optional[str] = None
    for cid, blob in haystacks:
        if _IE_RE.search(_strip_ni(blob)):
            if not _county_matches(blob, counties):
                if county_reject_cid is None:
                    county_reject_cid = cid
                continue
            note = None
            if _NI_RE.search(blob) or _NON_IE_RE.search(blob):
                note = (
                    "Ireland evidenced alongside other jurisdictions -- confirm "
                    "current base in the first call."
                )
            return GateResult(
                gate_id="located_ie", passed=True, basis=cid, note=note
            )

    # Relocation / return-to-Ireland signal, opt-in per role (the Cork-
    # relocatable clause). Checked across every claim, not just location
    # ones -- a movability-style statement can land in any dimension.
    if allow_relocation:
        for c in claims:
            blob = c.assertion + " " + c.evidence_quote
            if _RELOCATION_RE.search(blob):
                return GateResult(
                    gate_id="located_ie",
                    passed=True,
                    basis=c.claim_id,
                    note=(
                        "Relocation / return-to-Ireland signal evidenced -- "
                        "confirm current base and timeline in the first call."
                    ),
                )

    # Fall back to Irish-scheme / Irish-client evidence. Witness statements
    # rarely say "I live in Dublin"; they evidence location by the schemes
    # and bodies they work for. Recorded with a note so the card stays honest.
    scheme_hit: Optional[ValidatedClaim] = None
    for c in _direct(_claims_by_dim(claims, "project", "employer", "statutory_process")):
        blob = c.assertion + " " + c.evidence_quote
        if _IE_RE.search(blob) or _IRISH_BODY_RE.search(blob):
            if not _county_matches(blob, counties):
                continue
            scheme_hit = c
            break

    if scheme_hit is not None:
        note = (
            "Ireland-based inferred from Irish scheme/client evidence, "
            "not from a stated location. Confirm in the first call."
        )
        if require_direct:
            # Client feedback 2026-09-10: this exact fallback -- a Jacobs
            # UK-office engineer whose only Irish evidence was the road
            # scheme they worked on -- is what put people outside Ireland
            # into the shortlist. Never a silent pass when the role opts in.
            if treat_unknown_as == "pass_with_note":
                return GateResult(
                    gate_id="located_ie", passed=True, basis=scheme_hit.claim_id,
                    note=note,
                )
            return GateResult(
                gate_id="located_ie",
                passed=False,
                basis=scheme_hit.claim_id,
                note="no direct residence evidence; Irish scheme work only",
            )
        return GateResult(
            gate_id="located_ie", passed=True, basis=scheme_hit.claim_id, note=note
        )

    if county_reject_cid is not None:
        return GateResult(
            gate_id="located_ie",
            passed=False,
            basis=county_reject_cid,
            note=(
                "Located in the Republic of Ireland but not in the target "
                "county/counties (" + ", ".join(params.get("counties", [])) + "); "
                "confirm relocation."
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


# RADAR_CONTRACTS.md section C: a years figure only counts toward a person's
# seniority when the sentence it comes from is actually ABOUT them. "ABC
# Consulting has provided structural engineering since 1985" states the
# FIRM's history, not the witness's -- and "since 1985" reads as decades to
# extract_years' word-number sibling in some phrasings, so an unguarded gate
# will credit a person with a firm's whole trading history.
_PERSON_SUBJECT_RE = re.compile(r"\b(i|my|me|he|she|his|her|him)\b", re.I)


def _years_subject_is_person(quote: str, person: Person) -> bool:
    """True when `quote` names the person as its subject: a first- or
    third-person pronoun (I/my/me/he/she/his/her/him), or the person's own
    name (in whole or by any name token longer than one letter). A sentence
    naming only a firm or practice matches neither and returns False.
    """
    text = " " + re.sub(r"[^a-z' ]+", " ", quote.lower()) + " "
    if _PERSON_SUBJECT_RE.search(text):
        return True
    for tok in re.split(r"[^A-Za-z']+", person.full_name):
        if len(tok) > 1 and re.search(r"\b" + re.escape(tok.lower()) + r"\b", text):
            return True
    return False


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


def _grade_corroborated(person: Person, claims: list[ValidatedClaim]) -> bool:
    """RADAR_CONTRACTS.md section C: with `require_corroboration=True`, a
    title-only grade inference needs either (a) a years claim -- any direct
    years_experience claim, whether or not it parsed to a number, since the
    point is a second kind of evidence exists at all -- or (b) a second,
    independent source (a different doc_id, or the title itself) that also
    evidences a senior grade.

    RawPersonRecord/ValidatedClaim carry no per-source "this is the same
    document as the title" marker, so independence is counted as: does the
    person's title match AND does at least one employer-dimension claim also
    match -- two distinct places the grade was stated, neither one alone.
    """
    if _direct(_claims_by_dim(claims, "years_experience")):
        return True
    sources = 0
    if person.current_title and _SENIOR_GRADE_RE.search(person.current_title):
        sources += 1
    if any(
        _SENIOR_GRADE_RE.search(c.assertion + " " + c.evidence_quote)
        for c in _direct(_claims_by_dim(claims, "employer"))
    ):
        sources += 1
    return sources >= 2


def check_seniority(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    minimum = int(params.get("min_years", 8))
    require_subject = bool(params.get("require_subject_is_person", False))
    evidenced: list[tuple[int, str]] = []
    for c in _direct(_claims_by_dim(claims, "years_experience")):
        if require_subject and not (
            _years_subject_is_person(c.evidence_quote, person)
            or _years_subject_is_person(c.assertion, person)
        ):
            continue
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
                if params.get("require_corroboration") and not _grade_corroborated(person, claims):
                    return GateResult(
                        gate_id="seniority",
                        passed=True,
                        basis=grade[1],
                        note="grade from one title only; confirm",
                    )
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
        # Title-based floor acceptance (client feedback 2026-09-11: 21 Role 1
        # people failed ONLY the 8-year floor with titles like "Senior
        # Structural Engineer" -- the brief's target grade, stated with no
        # years on a directory page. _SENIOR_GRADE_RE / allow_grade_inference
        # above does not catch these -- it is deliberately restricted to
        # grades unreachable inside 8 years (Director and up), and "Senior
        # Engineer" is reachable at ~5. This is a separate, opt-in mechanism:
        # a brief-supplied list of regex fragments (e.g. "senior", "lead",
        # "associate", "principal") that, matched against the title alone,
        # are taken as evidence of the floor -- never invented silently, the
        # card always carries the confirm-on-first-call note.
        accept_titles = params.get("accept_titles_for_floor") or []
        if accept_titles:
            try:
                accept_re = re.compile("|".join(accept_titles), re.I)
            except re.error:
                accept_re = None
            if accept_re is not None:
                title = person.current_title or ""
                m = accept_re.search(title)
                basis = "person.title"
                if not m:
                    for c in _direct(_claims_by_dim(claims, "employer")):
                        blob = c.assertion + " " + c.evidence_quote
                        m = accept_re.search(blob)
                        if m:
                            basis = c.claim_id
                            break
                if m:
                    return GateResult(
                        gate_id="seniority",
                        passed=True,
                        basis=basis,
                        note=(
                            "years not stated; " + m.group(0).lower()
                            + " title accepted for the floor -- confirm years "
                            "on first call"
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


# ---------------------------------------------------------------------------
# Seniority CEILING (client feedback 2026-09-10: "a lot of the candidates
# were too senior"). check_seniority above is a FLOOR only -- with grade
# inference on, a title alone can pass it, and nothing stopped a Director
# from clearing the gate. This is the ceiling half.
# ---------------------------------------------------------------------------

# Deterministic grade ladder, lowest to highest. "senior_engineer" is
# reachable at ~5 years and is deliberately its own rung below
# "principal_or_associate" -- see check_seniority's _SENIOR_GRADE_RE comment
# for the equivalent floor-side reasoning.
_GRADE_ORDER = [
    "graduate", "engineer", "senior_engineer", "principal_or_associate",
    "associate_director", "director",
]

# Checked top-down (director first) so the most senior matching rung wins
# and "Associate Director" -- which contains the substring "director" -- is
# claimed by its own rung before the generic director pattern gets to it.
# "graduate" is checked before the bare "engineer" catch-all so "Graduate
# Structural Engineer" lands on "graduate", not "engineer".
#
# A bare, unqualified "Director" ALWAYS maps to the top rung "director" here
# (via the negative-lookbehind alternative in the director pattern), and a
# bare, unqualified "Associate" ALWAYS maps to "principal_or_associate", NEVER
# to "associate_director" -- "Associate Director" only matches when both
# words are present, checked one rung higher. Firms are not consistent about
# what "Associate" means, so this ladder deliberately does not try to be
# firm-aware; FIRM_LADDER_NOTES below records the cases known to differ from
# the ladder's plain reading, for a human to weigh when a card is reviewed --
# it is NOT consulted by _grade_of, because folding firm-specific exceptions
# into the deterministic gate is exactly the kind of judgement call I3
# reserves for a person, not a regex.
FIRM_LADDER_NOTES = {
    # O'Connor Sutton Cronin and DBFL both use "Associate" as a grade BELOW
    # Associate Director (an OCSC/DBFL "Associate" is closer to Principal
    # Engineer than to Associate Director). The ladder's plain reading --
    # bare "Associate" -> principal_or_associate -- already gets this right;
    # the risk this note guards against is the OPPOSITE mistake, a future
    # change that special-cases "Associate" upward toward "director" on the
    # assumption that an "Associate" is always one step below a Director.
    "ocsc": "Associate is below Associate Director here; maps to principal_or_associate.",
    "o'connor sutton cronin": (
        "Associate is below Associate Director here; maps to principal_or_associate."
    ),
    "dbfl": "Associate is below Associate Director here; maps to principal_or_associate.",
}
_GRADE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("director", re.compile(
        # "director of X" is covered by the bare-director alternative, so an
        # "Associate Director of Highways" stays on the associate_director rung.
        r"\b(technical director|regional director|managing director|"
        r"executive director|head of|partner|practice leader|chief)\b"
        r"|(?<!associate\s)\bdirector\b",
        re.I,
    )),
    ("associate_director", re.compile(r"\bassociate director\b", re.I)),
    ("principal_or_associate", re.compile(
        r"\b(principal engineer|principal|associate)\b", re.I
    )),
    # "Senior Structural Engineer", "Senior Civil / Structural Engineer" --
    # the discipline words sit between "senior" and "engineer".
    ("senior_engineer", re.compile(r"\bsenior\b[^,;|]{0,40}?\bengineer\b", re.I)),
    ("graduate", re.compile(r"\bgraduate\b", re.I)),
    ("engineer", re.compile(r"\bengineer\b", re.I)),
]


def _grade_of(
    person: Person, claims: list[ValidatedClaim]
) -> Optional[tuple[str, str]]:
    """Return (grade, basis) for the most senior grade evidenced, or None.

    Reads person.current_title first (the normal case for a staff-directory
    candidate), then falls back to direct employer-dimension claims, which is
    where a title phrase most often turns up in prose ("Senior Associate
    Director of Highways in Jacobs").
    """
    texts: list[tuple[str, str]] = []
    if person.current_title:
        texts.append((person.current_title, "person.title"))
    for c in _direct(_claims_by_dim(claims, "employer")):
        texts.append((c.assertion + " " + c.evidence_quote, c.claim_id))
    for text, basis in texts:
        for grade, pattern in _GRADE_PATTERNS:
            if pattern.search(text):
                return grade, basis
    return None


def check_seniority_ceiling(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    """Fail candidates above the brief's ceiling. Never invents a grade.

    params:
      max_grade -- one of _GRADE_ORDER; None means no ceiling.
      max_years -- int; None means no ceiling.
      exclude_title_patterns -- list of regexes checked against the title.
    An absent/empty params dict means no ceiling at all -- every candidate
    passes -- so this gate is a no-op unless a role explicitly opts in.
    """
    max_grade = params.get("max_grade")
    max_years = params.get("max_years")
    exclude_patterns = params.get("exclude_title_patterns") or []

    title = person.current_title or ""
    for pattern in exclude_patterns:
        try:
            hit = re.search(pattern, title, re.I)
        except re.error:
            continue  # a malformed pattern in a brief must not crash the gate
        if hit:
            return GateResult(
                gate_id="seniority_ceiling",
                passed=False,
                basis="person.title",
                note="Title '" + title + "' matches excluded pattern '" + pattern + "'",
            )

    grade_info = _grade_of(person, claims)
    if max_grade is not None and grade_info is not None:
        grade, basis = grade_info
        if _GRADE_ORDER.index(grade) > _GRADE_ORDER.index(max_grade):
            return GateResult(
                gate_id="seniority_ceiling",
                passed=False,
                basis=basis,
                note=(
                    "Title '" + title + "' is above the brief ceiling ("
                    + max_grade + ")"
                ),
            )

    require_subject = bool(params.get("require_subject_is_person", False))
    evidenced: list[tuple[int, str]] = []
    for c in _direct(_claims_by_dim(claims, "years_experience")):
        if require_subject and not (
            _years_subject_is_person(c.evidence_quote, person)
            or _years_subject_is_person(c.assertion, person)
        ):
            continue
        years = extract_years(c.evidence_quote)
        if years is None:
            years = extract_years(c.assertion)
        if years is not None:
            evidenced.append((years, c.claim_id))
    best_years = max(evidenced, key=lambda t: t[0]) if evidenced else None
    if max_years is not None and best_years is not None and best_years[0] > max_years:
        return GateResult(
            gate_id="seniority_ceiling",
            passed=False,
            basis=best_years[1],
            note=(
                "Evidenced at " + str(best_years[0]) + " years' experience, "
                "above the " + str(max_years) + "-year ceiling."
            ),
        )

    if (
        grade_info is None and best_years is None
        and (max_grade is not None or max_years is not None)
    ):
        # Neither a grade nor a year figure is evidenced. Passing silently
        # would be an invented clean bill; passing loud is honest and cheap.
        return GateResult(
            gate_id="seniority_ceiling",
            passed=True,
            note="grade not evidenced; confirm on first call",
        )

    basis = grade_info[1] if grade_info else (best_years[1] if best_years else None)
    return GateResult(gate_id="seniority_ceiling", passed=True, basis=basis)


# ---------------------------------------------------------------------------
# Delivery composition guard.
#
# The gates above decide who passes; this decides whether what actually
# SHIPPED matches the brief -- a check that runs on the flattened
# CandidateCard-shaped output (or a plain dict/CSV row with the same field
# names), not on claims, because that is what the client actually reads.
# A person could theoretically clear the per-candidate gates on evidence that
# never made it onto the card and still show up as a violation here, or vice
# versa -- that asymmetry is intentional: this is the last honest look at the
# deliverable itself, independent of how gating got there. It exists because
# the 2026-08-20 run's own delivered CSV -- every one of the 10 Role 1 rows
# titled Director or Associate Director -- is exactly the client's complaint,
# and nothing before render time would have said so out loud.
# ---------------------------------------------------------------------------


def _field(rec, name: str):
    """Read `name` off a dict OR an attribute-bearing object (CandidateCard)."""
    if isinstance(rec, dict):
        return rec.get(name)
    return getattr(rec, name, None)


def _grade_from_title(title: str) -> Optional[str]:
    for grade, pattern in _GRADE_PATTERNS:
        if pattern.search(title or ""):
            return grade
    return None


def _location_country(location: str) -> str:
    """Coarse bucket for a free-text location string -- reporting only.

    Not a gate: check_located_ie is the authority on pass/fail and reads the
    full claim set, not just this one string.
    """
    if not location:
        return "unknown"
    if _NI_RE.search(location) and not _IE_RE.search(_strip_ni(location)):
        return "northern_ireland"
    if _IE_RE.search(_strip_ni(location)):
        return "ireland"
    if _NON_IE_RE.search(location):
        return "outside_ireland"
    return "unknown"


def composition_report(cards, spec: JobSpec) -> dict:
    """Counts per grade / location-country / email_status for `cards`.

    `cards` is any iterable of CandidateCard-shaped records (dict or object)
    exposing current_title, location and email_status -- e.g. the rendered
    CandidateCard list, or rows straight off candidates.csv.
    """
    by_grade: dict[str, int] = {}
    by_location: dict[str, int] = {}
    by_email_status: dict[str, int] = {}
    cards = list(cards)
    for rec in cards:
        grade = _grade_from_title(_field(rec, "current_title") or "") or "unknown"
        by_grade[grade] = by_grade.get(grade, 0) + 1

        country = _location_country(_field(rec, "location") or "")
        by_location[country] = by_location.get(country, 0) + 1

        status = _field(rec, "email_status") or "none"
        by_email_status[status] = by_email_status.get(status, 0) + 1

    return {
        "role_id": spec.role_id,
        "total": len(cards),
        "by_grade": by_grade,
        "by_location_country": by_location,
        "by_email_status": by_email_status,
    }


def composition_violations(cards, spec: JobSpec) -> list[str]:
    """Delivered cards whose grade/location contradict the brief's bands.

    Empty when spec has no seniority_band/location_rule -- a role that never
    opted into ceiling/strictness has nothing for this to check.
    """
    violations: list[str] = []
    band = spec.seniority_band
    loc_rule = spec.location_rule
    employer_gate = next(
        (g for g in spec.hard_gates if g.check == "employer_sector"), None
    )

    for rec in cards:
        name = _field(rec, "full_name") or _field(rec, "person_id") or "<unknown>"
        title = _field(rec, "current_title") or ""

        if band is not None and band.max_grade is not None:
            grade = _grade_from_title(title)
            if grade is not None and (
                _GRADE_ORDER.index(grade) > _GRADE_ORDER.index(band.max_grade)
            ):
                violations.append(
                    str(name) + " (" + title + ") is grade '" + grade
                    + "', above the brief ceiling '" + band.max_grade + "'"
                )

        if loc_rule is not None:
            location = _field(rec, "location") or ""
            country = _location_country(location)
            if country in ("northern_ireland", "outside_ireland", "unknown"):
                violations.append(
                    str(name) + " location '" + location + "' does not evidence "
                    "Republic of Ireland residence"
                )
            elif loc_rule.counties:
                counties = [c.lower() for c in loc_rule.counties]
                if not _county_matches(location, counties):
                    violations.append(
                        str(name) + " location '" + location + "' is outside "
                        "the target county/counties (" + ", ".join(loc_rule.counties)
                        + ")"
                    )

        if employer_gate is not None:
            employer = _field(rec, "current_employer")
            passed, note = employer_reads_as_consultancy(
                employer, [], employer_gate.params
            )
            if not passed:
                violations.append(str(name) + " -- " + (note or (
                    "employer '" + str(employer) + "' does not read as an "
                    "engineering consultancy; confirm"
                )))

    return violations


# ---------------------------------------------------------------------------
# Employer sector -- "does this read as an engineering consultancy at all?"
#
# 2026-09-11 client feedback exhibit: a delivered Role 1 card was "Senior
# Structural Engineer at Nokia" -- it passed check_discipline on the word
# "structural" (Nokia has structural/RF engineers too), but the brief is a
# consultancy role and Nokia is a telecoms multinational, not an engineering
# consultancy. Deterministic, never an LLM judgement: FIRMS membership, a
# consultancy-shaped employer string, a brief-supplied allowlist regex, or a
# direct claim stating a consultancy context are all that can pass it.
#
# The logic is factored into `employer_reads_as_consultancy` so the gate
# (check_employer_sector) and the delivery composition guard
# (composition_violations) can never drift apart on what counts.
# ---------------------------------------------------------------------------

_CONSULTANCY_SHAPE_RE = re.compile(
    r"engineer|consult|design|structur|civil|partners|associates|\bllp\b|group",
    re.I,
)

# Common firm names that read as engineering consultancies even though they
# do not obviously match the shape pattern above (e.g. "AECOM" contains none
# of those substrings). TII is a client-side statutory body, not a
# consultancy -- it counts as a legitimate Role 2 employer (transport policy/
# delivery work), never as a legitimate Role 1 (structural consultancy)
# employer, so it is gated behind `allow_client_side_firms_role2` rather than
# always-on.
_COMMON_CONSULTANCY_FIRMS = ["arup", "jacobs", "aecom", "atkins", "wsp", "mott", "rps"]
_ROLE2_ONLY_FIRMS = ["tii"]

_CONSULTANCY_CONTEXT_RE = re.compile(
    r"\bconsultanc(?:y|ies)\b|\bconsulting engineers\b", re.I
)


def _firm_token_matches(employer_low: str) -> bool:
    """True when `employer_low` names a firm from sources.company_bios.FIRMS
    (by full name or by the leading token of its domain, e.g. "ocsc" from
    "ocsc.ie")."""
    for firm in FIRMS:
        if firm.name.lower() in employer_low:
            return True
        domain_token = firm.domain.split(".")[0].lower()
        if domain_token and re.search(r"\b" + re.escape(domain_token) + r"\b", employer_low):
            return True
    return False


def employer_reads_as_consultancy(
    employer: Optional[str], claims: list[ValidatedClaim], params: dict
) -> tuple[bool, Optional[str]]:
    """Shared pass/fail logic behind check_employer_sector AND
    composition_violations -- one place decides what "reads as an
    engineering consultancy" means, so the gate and the after-the-fact
    delivery check can never disagree.

    Returns (passed, note). note is None on a clean, unremarkable pass.

    params:
      extra_pass_patterns -- list[str], brief-supplied regex fragments
        checked against the employer string (role's own escape hatch,
        e.g. a named boutique not in FIRMS).
      off_limits -- list[str], substrings that fail regardless of shape
        (Atkins/AtkinsRealis/TOBIN are consultancies in general but are
        this client, off-limits everywhere -- see roles.OFF_LIMITS).
      allow_client_side_firms_role2 -- bool, Role 2 only: TII and similar
        client-side transport bodies count as a legitimate employer here.
    """
    off_limits = [t.lower() for t in (params.get("off_limits") or [])]
    extra_patterns = params.get("extra_pass_patterns") or []
    allow_role2_firms = bool(params.get("allow_client_side_firms_role2"))

    employer_low = (employer or "").strip().lower()
    if not employer_low:
        return True, "employer not stated"

    for term in off_limits:
        if term and term in employer_low:
            return False, (
                "employer '" + (employer or "") + "' does not read as an "
                "engineering consultancy; confirm"
            )

    if _firm_token_matches(employer_low):
        return True, None

    if _CONSULTANCY_SHAPE_RE.search(employer_low):
        return True, None

    common_firms = list(_COMMON_CONSULTANCY_FIRMS)
    if allow_role2_firms:
        common_firms += _ROLE2_ONLY_FIRMS
    if any(re.search(r"\b" + re.escape(f) + r"\b", employer_low) for f in common_firms):
        return True, None

    for pat in extra_patterns:
        try:
            if re.search(pat, employer_low, re.I):
                return True, None
        except re.error:
            continue  # a malformed brief-supplied pattern must not crash the gate

    for c in _direct(_claims_by_dim(claims, "employer")):
        blob = (c.assertion + " " + c.evidence_quote).lower()
        if _CONSULTANCY_CONTEXT_RE.search(blob):
            return True, None

    return False, (
        "employer '" + (employer or "") + "' does not read as an engineering "
        "consultancy; confirm"
    )


def check_employer_sector(
    person: Person, claims: list[ValidatedClaim], params: dict
) -> GateResult:
    employer = person.current_employer
    passed, note = employer_reads_as_consultancy(employer, claims, params)
    basis = "person.employer" if employer else None
    return GateResult(
        gate_id="employer_sector", passed=passed, basis=basis, note=note
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
    "seniority_ceiling": check_seniority_ceiling,
    "employer_sector": check_employer_sector,
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
