"""
L1 -- the two requisitions as JobSpec objects.

DELIBERATE DEVIATION FROM SPEC.md section 15 block B, recorded here so it is
auditable rather than silent.

The spec calls for an LLM requisition parser whose gate definitions are then
hand-checked. With two known roles, the parse step adds a failure mode
(a model quietly widening `discipline.include` or dropping an exclusion)
without adding information, and the hand-check it prescribes produces exactly
the artifact below. Writing the specs directly IS the hand-checked output.

The parser earns its place at ten requisitions, not at two. If this becomes a
product for Gaia, L1 gets built and this file becomes its golden fixture --
the test being that the parser reproduces these two specs from the JD text.

Every gate here is deterministic (I3). Nothing in this file is an LLM
judgement, a weight, or a score.

2026-09-10 -- client feedback on the delivered run: "A lot of the candidates
were too senior and some were not based in Ireland." Root cause was that
check_seniority (layers/gates.py) is a FLOOR only -- with grade inference on
(Role 1), a Director/Associate Director title alone passed it, because
nothing enforced a CEILING -- and check_located_ie fell back to accepting
Irish-scheme/employer evidence as residence evidence with only a soft note,
so an out-of-Ireland engineer who had worked an Irish scheme also passed.
Both roles below now also carry a `seniority_band` / `location_rule` (see
core/contracts.py) and a matching `seniority_ceiling` hard gate, plus
`located_ie` params tightened via LocationRule. The numbers are PLACEHOLDERS
PENDING KEITH MOLONY CALL 2026-09-10 -- override them per-run with
`run.py --max-grade / --max-years / --min-years / --counties /
--strict-location`.
"""

from __future__ import annotations

import re
import unicodedata

from .core.contracts import HardGate, JobSpec, LocationRule, SeniorityBand

# Off-limits everywhere: TOBIN is an AtkinsRealis company and both are the
# client. Sourcing from the client is a fireable offence in recruitment.
# Spelt several ways because the accent and the spacing both vary in the wild.
OFF_LIMITS = [
    "tobin",
    "atkinsrealis",
    "atkinsréalis",
    "atkins realis",
    "atkins réalis",
    "atkins",
]

# Title-based seniority-FLOOR acceptance (client feedback 2026-09-11): 21
# Role 1 people failed ONLY the 8-year floor with titles like "Senior
# Structural Engineer" / "Lead / Senior Structural Engineer" / "Civil /
# Structural Associate" -- the brief's own target grade, stated with no
# years on a directory page. Role 1's staff-directory sourcing has no years
# figure to read; Role 2's witness statements open with a mandatory
# qualifications section that states years explicitly, so this stays off
# there -- a title-only inference is not needed where the evidence is
# richer. See layers/gates.py check_seniority's accept_titles_for_floor
# handling. Overridable per-run with run.py --accept-senior-titles/
# --no-accept-senior-titles (both roles).
ACCEPT_TITLES_FOR_FLOOR_DEFAULT = ["senior", "lead", "associate", "principal"]

# Disciplines that must never satisfy the Role 1 gate. Drawn from the first
# real run, where the staff-directory sweep surfaced exactly these: RTPI town
# planners, Chartered Environmentalists, archaeologists, acousticians, M&E
# engineers and finance staff all sit on the same "our people" pages as the
# structural engineers.
_NON_ENGINEERING_EXCLUSIONS = [
    "rtpi",
    "town planner",
    "town planning",
    "chartered environmentalist",
    "archaeolog",
    "acoustic",
    "ecolog",
    "arboricultur",
    "quantity surveyor",
    "financial controller",
    "human resources",
    "marketing manager",
    "bid manager",
    "health and safety officer",
    "mechanical and electrical",
    "m&e engineer",
    "building services",
    "hvac",
]

ROLE1 = JobSpec(
    role_id="role1_senior_structural_engineer",
    title="Senior Structural Engineer",
    client="Gaia Talent Ltd",
    end_client="TOBIN / AtkinsRealis",
    locations=["Limerick", "Galway", "Dublin", "Ireland"],
    primary_signal_dimension="technical_skill",
    target_count=10,
    off_limits_employers=OFF_LIMITS,
    # PENDING KEITH MOLONY CALL 2026-09-10 -- placeholders, override per-run
    # with run.py --max-grade/--max-years/--min-years/--counties.
    seniority_band=SeniorityBand(
        min_years=8, max_years=18, max_grade="principal_or_associate",
    ),
    location_rule=LocationRule(
        require_direct_evidence=True, counties=[],  # any ROI
    ),
    ranked_signals=[
        "Eurocode design experience",
        "Tekla Structural Designer / Robot / ETABS",
        "BCAR (Building Control Amendment Regulations) assigned-certifier work",
        "Reinforced concrete and structural steel design",
        "Named project delivery in Ireland",
    ],
    disqualifiers=[
        "Currently at TOBIN or AtkinsRealis",
        "Based outside the Republic of Ireland",
        "Non-structural discipline",
    ],
    hard_gates=[
        HardGate(
            gate_id="chartered",
            description=(
                "Chartered with Engineers Ireland (CEng MIEI / FIEI), evidenced "
                "in a public source"
            ),
            check="chartered",
        ),
        HardGate(
            gate_id="located_ie",
            description=(
                "Based in the Republic of Ireland, commutable to Limerick, "
                "Galway or Dublin -- direct residence evidence required, "
                "not Irish-scheme work alone"
            ),
            check="located_ie",
            params={"require_direct_evidence": True, "counties": []},
        ),
        HardGate(
            gate_id="discipline",
            description="Structural engineering, or civil with a structural focus",
            check="discipline",
            params={
                "include": [
                    "structural",
                    "structures",
                    "structural engineer",
                    "civil and structural",
                    "civil & structural",
                    "bridge",
                    "reinforced concrete",
                    "structural design",
                ],
                "exclude": _NON_ENGINEERING_EXCLUSIONS,
            },
        ),
        HardGate(
            gate_id="seniority",
            description=(
                "At least 8 years' professional experience (the JD asks 12-18; "
                "the gate sits at 8 and the rest drives tiering)"
            ),
            check="seniority_years",
            # Staff-directory bios state a GRADE, not a year count. A Technical
            # Director at an engineering consultancy is necessarily past 8
            # years, but that is an inference, so it passes only with the note
            # printed on the card.
            params={
                "min_years": 8, "allow_grade_inference": True,
                "accept_titles_for_floor": list(ACCEPT_TITLES_FOR_FLOOR_DEFAULT),
            },
        ),
        HardGate(
            gate_id="seniority_ceiling",
            description=(
                "No higher than Principal / Associate grade, no more than 18 "
                "years evidenced -- PENDING KEITH MOLONY CALL 2026-09-10"
            ),
            check="seniority_ceiling",
            params={"max_grade": "principal_or_associate", "max_years": 18},
        ),
        HardGate(
            gate_id="employer_sector",
            description=(
                "Employer reads as an engineering consultancy -- structural "
                "discipline words alone (e.g. 'Senior Structural Engineer at "
                "Nokia') are not enough"
            ),
            check="employer_sector",
            params={"extra_pass_patterns": [], "off_limits": OFF_LIMITS},
        ),
        HardGate(
            gate_id="not_client",
            description="Not currently employed by TOBIN or AtkinsRealis",
            check="not_client",
            params={"off_limits": OFF_LIMITS},
        ),
    ],
)

ROLE2 = JobSpec(
    role_id="role2_transport_major_projects_manager",
    title="Transport Major Projects Manager",
    client="Gaia Talent Ltd",
    end_client="AtkinsRealis",
    locations=["Cork", "Ireland"],
    primary_signal_dimension="statutory_process",
    target_count=5,
    off_limits_employers=OFF_LIMITS,
    # PENDING KEITH MOLONY CALL 2026-09-10 -- placeholders, override per-run
    # with run.py --max-grade/--max-years/--min-years/--counties. The Cork
    # brief has a stated relocation clause, so treat_unknown_as is lenient
    # ONLY here -- Role 1 has no such clause and stays strict.
    seniority_band=SeniorityBand(
        min_years=10, max_years=25, max_grade="associate_director",
    ),
    location_rule=LocationRule(
        require_direct_evidence=True, counties=["Cork"],
        allow_relocation_signal=True, treat_unknown_as="pass_with_note",
    ),
    ranked_signals=[
        "Oral Hearing evidence given to An Bord Pleanala / An Coimisiun Pleanala",
        "EIAR / EIS preparation on a major scheme",
        "CPO / compulsory purchase order documentation",
        "Railway Order or Road Order promotion",
        "Named major transport scheme delivery",
    ],
    disqualifiers=[
        "Currently at TOBIN or AtkinsRealis",
        "Based outside the Republic of Ireland with no relocation signal",
        "Non-transport discipline",
    ],
    hard_gates=[
        HardGate(
            gate_id="chartered",
            description=(
                "Chartered with Engineers Ireland (CEng MIEI / FIEI), evidenced "
                "in a public source"
            ),
            check="chartered",
        ),
        HardGate(
            gate_id="located_ie",
            description=(
                "Based in the Republic of Ireland; Cork-commutable or "
                "relocatable, flagged either way -- direct residence evidence "
                "required, not Irish-scheme work alone; a relocation/return-"
                "to-Ireland signal counts per the brief's Cork clause"
            ),
            check="located_ie",
            params={
                "require_direct_evidence": True,
                "counties": ["Cork"],
                "allow_relocation_signal": True,
                "treat_unknown_as": "pass_with_note",
            },
        ),
        HardGate(
            gate_id="discipline",
            description="Transport, transportation, highways, rail or major infrastructure",
            check="discipline",
            params={
                "include": [
                    "transport",
                    "transportation",
                    "highway",
                    "roads",
                    "road scheme",
                    "rail",
                    "railway",
                    "light rail",
                    "major projects",
                    "major infrastructure",
                    "motorway",
                    "traffic",
                    "civil engineering",
                ],
                "exclude": _NON_ENGINEERING_EXCLUSIONS,
            },
        ),
        HardGate(
            gate_id="seniority",
            description="At least 10 years' professional experience",
            check="seniority_years",
            # Witness statements open with a mandatory qualifications section
            # that states years explicitly, so grade inference is not needed
            # here and is deliberately left off -- a stricter gate on the role
            # where the evidence is richer.
            params={
                "min_years": 10, "allow_grade_inference": False,
                # Left off deliberately -- witness statements state years
                # explicitly, so a title-only inference is not needed here.
                "accept_titles_for_floor": [],
            },
        ),
        HardGate(
            gate_id="seniority_ceiling",
            description=(
                "No higher than Associate Director, no more than 25 years "
                "evidenced -- PENDING KEITH MOLONY CALL 2026-09-10"
            ),
            check="seniority_ceiling",
            params={"max_grade": "associate_director", "max_years": 25},
        ),
        HardGate(
            gate_id="employer_sector",
            description=(
                "Employer reads as an engineering consultancy or a "
                "client-side transport statutory body (TII etc.) -- "
                "discipline words alone are not enough"
            ),
            check="employer_sector",
            params={
                "extra_pass_patterns": [], "off_limits": OFF_LIMITS,
                "allow_client_side_firms_role2": True,
            },
        ),
        HardGate(
            gate_id="not_client",
            description="Not currently employed by AtkinsRealis or TOBIN",
            check="not_client",
            params={"off_limits": OFF_LIMITS},
        ),
    ],
)

ROLES = {ROLE1.role_id: ROLE1, ROLE2.role_id: ROLE2}

# Client-side bodies. Engineers here have exactly the EIAR/CPO/Oral Hearing
# experience AtkinsRealis wants and sit outside the consultancy pool a boolean
# search covers -- but they are a different placement conversation, so they go
# in a clearly-labelled sidebar and NEVER in the 15 (SPEC.md section 2.3).
CLIENT_SIDE_BODIES = [
    "transport infrastructure ireland",
    "tii",
    "national transport authority",
    "nta",
    "iarnrod eireann",
    "irish rail",
    "coras iompair eireann",
    "cie",
    "county council",
    "city council",
    "city and county council",
    "office of public works",
    "opw",
    "uisce eireann",
    "irish water",
    "esb",
    "an coimisiun pleanala",
    "an bord pleanala",
    "department of transport",
]


# Stems that survive any mangling of an Irish-language body name. The full
# names above are matched after normalisation, but normalisation cannot repair
# a character that was already lost: a PDF extracted through a cp1252
# misread turns "Iarnrod Eireann" into "Iarnr<FFFD>d <FFFD>ireann", and
# stripping the replacement characters leaves "iarnrd ireann", which matches
# neither the accented nor the unaccented spelling.
#
# This is not cosmetic. On the 2026-08-19 run it put a Programme Manager at
# Iarnrod Eireann -- the national rail operator, unambiguously client-side --
# into the delivered shortlist instead of the sidebar, which is precisely the
# error SPEC 2.3 exists to prevent.
_CLIENT_SIDE_STEMS = [
    "iarnr",      # Iarnrod / Iarnrod / Iarnr?d Eireann
    "coimisi",    # An Coimisiun / Coimisiun Pleanala
    "uisce",      # Uisce Eireann
    "coras iompair",
]


def _normalise(text: str) -> str:
    """Lowercase, drop accents, drop replacement characters.

    "Iarnrod Eireann", "Iarnrod Eireann" and "Iarnr<FFFD>d <FFFD>ireann" must
    all reduce to something the stem list can match.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(
        ch for ch in decomposed
        if not unicodedata.combining(ch) and ch != "�"
    )


# Short acronyms need word boundaries: a bare "cie" substring matches
# "agencies" and "societies", and "tii" matches any typo'd double-i. Long
# names are safe as plain substrings.
_CLIENT_SIDE_RE = re.compile(
    "|".join(
        [
            (r"\b" + re.escape(b) + r"\b") if len(b) <= 4 else re.escape(b)
            for b in CLIENT_SIDE_BODIES
        ]
        + [r"\b" + re.escape(s) for s in _CLIENT_SIDE_STEMS]
    ),
    re.I,
)


def is_client_side(employer: str | None) -> bool:
    if not employer:
        return False
    return bool(_CLIENT_SIDE_RE.search(_normalise(employer)))
