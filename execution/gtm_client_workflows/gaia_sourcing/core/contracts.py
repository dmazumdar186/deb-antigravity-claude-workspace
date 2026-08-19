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
    "chartered", "located_ie", "discipline", "seniority_years", "not_client"
]


class HardGate(BaseModel):
    """A binary, deterministically-checkable requirement."""

    gate_id: str
    description: str
    check: GateCheck
    params: dict = Field(default_factory=dict)


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
