"""
Pydantic contracts for the Gaia sourcing pipeline (SPEC.md section 5).

Design note, per SPEC.md section 5 "Critical implementation note":
these models validate STRUCTURE ONLY. Business rules (is this candidate
chartered? are they in Ireland?) live in layers/gates.py. A record with
chartered=False is structurally valid and describes an unqualified
candidate -- it is not a schema error.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl

# --------------------------------------------------------------------------
# L1 -- requisition
# --------------------------------------------------------------------------

def as_list(value) -> list:
    """Coerce a model's "array" field into an actual list.

    A schema that says "array of strings" does not stop a model returning the
    whole field as one JSON-encoded string, and a string is iterable -- so
    `for item in value` walks CHARACTERS. Two cards in the delivered dossier
    rendered their open-questions section as one bullet per character, 1651
    and 1885 of them, and every space was dropped along the way because a lone
    space fails an `if text` check. The text was not merely mangled, it was
    unrecoverable from the stored output.

    Every place that iterates a model-supplied list goes through here, because
    the guard is only worth anything if it is not the one place someone forgot.
    """
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return [value]          # ordinary prose: one item, not one per letter
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, str):
            return [parsed]         # a JSON-encoded string decodes to its text
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


GateCheck = Literal[
    "chartered", "located_ie", "discipline", "seniority_years", "not_client",
    "seniority_ceiling",
]


class HardGate(BaseModel):
    """A binary, deterministically-checkable requirement."""

    gate_id: str
    description: str
    check: GateCheck
    params: dict = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Brief-level knobs (client feedback 2026-09-10: candidates too senior / not
# based in Ireland). These are structural containers only -- validated
# STRUCTURE ONLY per the module docstring. The actual ceiling/strictness
# logic lives in layers/gates.py:check_seniority_ceiling / check_located_ie.
# --------------------------------------------------------------------------


class SeniorityBand(BaseModel):
    """Floor AND ceiling for a role, set by the client on a call."""

    min_years: Optional[int] = None
    max_years: Optional[int] = None
    max_grade: Optional[
        Literal[
            "senior_engineer", "principal_or_associate", "associate_director",
            "director",
        ]
    ] = None
    exclude_title_patterns: list[str] = Field(default_factory=list)


class LocationRule(BaseModel):
    """Location strictness for a role, set by the client on a call."""

    require_direct_evidence: bool = True
    counties: list[str] = Field(default_factory=list)  # empty = any ROI
    allow_relocation_signal: bool = False
    treat_unknown_as: Literal["fail", "pass_with_note"] = "fail"


class JobSpec(BaseModel):
    role_id: str
    title: str
    client: str
    end_client: Optional[str] = None  # e.g. AtkinsRealis behind TOBIN
    locations: list[str]
    hard_gates: list[HardGate]
    ranked_signals: list[str] = Field(default_factory=list)
    disqualifiers: list[str] = Field(default_factory=list)
    target_count: int  # 10 or 5 -- enforced at render
    # The dimension that drives A/B/C tiering for this role.
    primary_signal_dimension: Literal["technical_skill", "statutory_process"]
    # Employers that are off-limits (client conflict). Lowercased substrings.
    off_limits_employers: list[str] = Field(default_factory=list)
    # Brief-level ceiling/location knobs (optional -- existing JobSpecs
    # without them keep their old behaviour; the enforcement lives in the
    # hard_gates list, these fields are the documented, settable source of
    # truth for what those gates' params were derived from).
    seniority_band: Optional[SeniorityBand] = None
    location_rule: Optional[LocationRule] = None


# --------------------------------------------------------------------------
# L3 -- raw source documents
# --------------------------------------------------------------------------

SourceType = Literal[
    "linkedin_snippet",
    "company_bio",
    "engineers_ireland_register",
    "acp_witness_statement",
    "acp_inspector_report",
    "conference_paper",
    "news",
    "professional_body",
    "other",
]


class RawDocument(BaseModel):
    doc_id: str  # sha256 of content
    url: HttpUrl
    source_type: SourceType
    fetched_at: date
    content_text: str  # normalised plain text
    http_status: int
    title: Optional[str] = None
    # Where content_text came from. "text_layer" is the document's own text
    # and is what L6's character-by-character check was designed around.
    # "ocr" means the source was an image-only scan and the text is a model's
    # transcription of it -- a weaker guarantee, surfaced on the card rather
    # than quietly folded in with the rest. Defaulted so every document
    # written before this field existed still loads.
    text_source: Literal["text_layer", "ocr"] = "text_layer"


# --------------------------------------------------------------------------
# L4 -- entity resolution
# --------------------------------------------------------------------------


class Person(BaseModel):
    person_id: str  # deterministic slug
    full_name: str
    current_title: Optional[str] = None
    current_employer: Optional[str] = None
    location: Optional[str] = None
    doc_ids: list[str] = Field(default_factory=list)
    linkedin_url: Optional[HttpUrl] = None


# --------------------------------------------------------------------------
# L5 / L6 -- claims and validation
# --------------------------------------------------------------------------

ClaimDimension = Literal[
    "chartership",
    "years_experience",
    "technical_skill",
    "sector",
    "employer",
    "location",
    "project",
    "education",
    "statutory_process",
]


class Claim(BaseModel):
    """Every assertion about a candidate. No exceptions."""

    claim_id: str
    subject_person_id: str
    dimension: ClaimDimension
    assertion: str = Field(..., max_length=280)
    evidence_quote: str = Field(..., min_length=12, max_length=400)
    source_doc_id: str
    source_url: HttpUrl
    # "inferred" NEVER renders as fact -- it renders under Unknowns.
    confidence: Literal["direct", "inferred"]


class ValidatedClaim(Claim):
    quote_verified: bool  # set by L6; must be True to render


# --------------------------------------------------------------------------
# L7 -- gates
# --------------------------------------------------------------------------


class GateResult(BaseModel):
    gate_id: str
    passed: bool
    basis: Optional[str] = None  # claim_id or deterministic lookup ref
    note: Optional[str] = None  # shown verbatim on Tier C cards


# --------------------------------------------------------------------------
# L8 -- evaluation
# --------------------------------------------------------------------------


class Evaluation(BaseModel):
    person_id: str
    role_id: str
    tier: Literal["A", "B", "C", "EXCLUDED"]
    gates: list[GateResult]
    strengths: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    adversarial_findings: list[str] = Field(default_factory=list)
    exclusion_reason: Optional[str] = None


# --------------------------------------------------------------------------
# L9 -- contact
# --------------------------------------------------------------------------

EmailStatus = Literal["verified", "catch_all", "pattern_guess", "none"]


class ContactRecord(BaseModel):
    person_id: str
    email: Optional[EmailStr] = None
    email_status: EmailStatus = "none"
    email_provider: Optional[str] = None
    linkedin_url: Optional[HttpUrl] = None
    linkedin_live: bool = False
    recommended_first_channel: Literal[
        "linkedin", "personal_email", "work_email", "phone"
    ] = "linkedin"
    channel_rationale: str = ""
    # 2026-09-10 -- RADAR_CONTRACTS.md section E "Stale evidence". Set by
    # layers/contact.py from the newest employer-dimension document's
    # fetched_at; None means there was no dated document to judge against.
    # `stale` is the deterministic threshold check (age > CONFIG.max_
    # evidence_age_days) -- computed once at contact time so every downstream
    # consumer (CRM sync, render) reads the same verdict instead of
    # re-deriving it from the raw age and risking two different thresholds.
    evidence_age_days: Optional[int] = None
    stale: bool = False


# --------------------------------------------------------------------------
# L10 -- movability
# --------------------------------------------------------------------------


class MovabilitySignal(BaseModel):
    person_id: str
    tenure_months_current: Optional[int] = None
    signals: list[str] = Field(default_factory=list)
    assessment: Literal["high", "medium", "low", "unknown"] = "unknown"
    rationale: str = ""


# --------------------------------------------------------------------------
# L11 -- outreach
# --------------------------------------------------------------------------


class OutreachSequence(BaseModel):
    linkedin_note: str = Field(..., max_length=300)
    email_subject: str = Field(..., max_length=90)
    email_body: str
    follow_up: str
    gdpr_notice: str  # injected, never LLM-generated
    opt_out_line: str  # injected, never LLM-generated


# --------------------------------------------------------------------------
# Final render unit
# --------------------------------------------------------------------------


class CandidateCard(BaseModel):
    person_id: str
    full_name: str
    current_title: str
    current_employer: str
    location: str
    role_id: str
    tier: Literal["A", "B", "C"]
    claims: list[ValidatedClaim]  # only quote_verified=True
    evaluation: Evaluation
    contact: ContactRecord
    movability: MovabilitySignal
    outreach: Optional[OutreachSequence] = None


class ReplyVerdict(BaseModel):
    """Output of layers/replies.py -- classification only, never a reply draft.

    `next_action` is derived from `label` by a fixed dict in replies.py (I3:
    deterministic code decides, the LLM only supplies a label + evidence when
    the rules genuinely cannot). `opt_out` is set ONLY by the deterministic
    opt-out rule (unsubscribe / remove-me phrasing) -- the LLM path never sets
    it, so a model's "not_interested" verdict can never be silently upgraded
    into an opt-out, and a rule-detected opt-out can never be downgraded by a
    model second-guessing it.
    """

    label: Literal[
        "interested", "not_now", "not_interested", "question",
        "out_of_office", "bounce", "unclear",
    ]
    next_action: Literal[
        "book_call", "snooze_90d", "close", "consultant_answers",
        "retry_later", "human_review",
    ]
    basis: Literal["rule", "llm"]
    evidence: str  # the phrase that decided it
    confidence: Literal["high", "low"]
    opt_out: bool = False


class PoolMapRow(BaseModel):
    reason: str
    count: int


class PoolMap(BaseModel):
    role_id: str
    profiles_assessed: int
    passed_screen: int
    evidence_validated: int
    passed_all_gates: int
    delivered: int
    exclusions: list[PoolMapRow] = Field(default_factory=list)
    # Client-side engineers (TII / NTA / local authority) surfaced separately
    # per SPEC.md section 2.3 -- deliberately NOT part of the 15.
    client_side_sidebar: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Source providers -- RADAR_CONTRACTS.md section A (2026-09-10).
#
# Appended, never edited in place: two parallel builds share this file
# (this one owns sources/base.py + the three chartership-register plugins;
# another owns the licensed providers pdl/crustdata/apollo) and both import
# these exact shapes. Structure only, per the module docstring above --
# whether a ProviderRecord or SourceResult describes a real match is a
# gates.py/registers.py question, not a schema one.
# --------------------------------------------------------------------------


class SourceQuery(BaseModel):
    role_id: str
    niche: str  # "structural" | "transport" | ...
    terms: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    limit: int = 100
    cursor: Optional[str] = None


class JobStint(BaseModel):
    """One entry in a ProviderRecord's job_history. Licensed-data only --
    dates are Optional because a provider's employment record frequently
    gives a title/employer with no start or end date at all."""

    title: Optional[str] = None
    employer: Optional[str] = None
    start: Optional[date] = None
    end: Optional[date] = None


class ProviderRecord(BaseModel):
    """A structured record from a licensed data provider (PDL, Crustdata,
    Apollo, ...). Never produced by the free register plugins in
    sources/engineers_ireland.py etc. -- those emit RawDocuments only, because
    their evidence is a quotable page of text, not a licensed structured
    field. See RADAR_CONTRACTS.md section A for how a ProviderRecord becomes
    a claim (confidence="direct", text_source="provider_field")."""

    provider: str
    external_id: str
    full_name: str
    current_title: Optional[str] = None
    current_employer: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    job_history: list[JobStint] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    fetched_at: date
    raw_hash: str  # sha256 of the provider JSON, for audit


class SourceResult(BaseModel):
    provider: str
    documents: list[RawDocument] = Field(default_factory=list)
    provider_records: list[ProviderRecord] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    cost_eur: float = 0.0
    fetched: int = 0


# --------------------------------------------------------------------------
# Identity resolution -- RADAR_CONTRACTS.md section B (2026-09-10).
# Appended, never edited in place -- see the note on the block above this
# one; other agents append their own models elsewhere in this same window.
# --------------------------------------------------------------------------


class RawPersonRecord(BaseModel):
    """One sighting of a person from one source, before clustering.

    Structure only (module docstring above): a record with no employer or no
    register_number is a person the source simply didn't state that field
    for, not a schema error. `doc_ids` lets a cluster's members trace back to
    the evidence documents that named them.
    """

    source: str
    source_ref: str
    full_name: str
    employer: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    register_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    doc_ids: list[str] = Field(default_factory=list)


class PersonCluster(BaseModel):
    """The output of layers/identity.py::resolve_identity -- one real person,
    possibly sighted under several RawPersonRecords. `basis` lists every
    merge rule that contributed a link inside this cluster (e.g.
    ["name+employer", "linkedin_url"] for a three-way chain); `confidence` is
    the strongest basis present ("exact" > "strong" > "weak")."""

    person_id: str  # deterministic slug of canonical name + employer token
    members: list[RawPersonRecord]
    basis: list[str] = Field(default_factory=list)
    confidence: Literal["exact", "strong", "weak"]


# --------------------------------------------------------------------------
# ICP sample check -- RADAR_CONTRACTS.md section D (2026-09-10).
# --------------------------------------------------------------------------


class IcpSample(BaseModel):
    person_id: str
    passed: bool
    failed_gates: list[str] = Field(default_factory=list)


class IcpVerdict(BaseModel):
    batch_id: str
    sampled: int
    matched: int
    threshold: int
    verdict: Literal["PASS", "RETRY"]
    filter_delta: str
    samples: list[IcpSample] = Field(default_factory=list)
