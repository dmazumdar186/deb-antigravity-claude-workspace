"""
L5 -- evidence extraction.

The model's only job is to COPY quotes out of supplied documents and label
them. It is explicitly instructed that emitting nothing is correct behaviour
when a fact is unsupported, because the alternative -- a fluent invention --
is the default failure mode of an LLM asked to profile a person.

Everything emitted here is checked by L6 (validator.py) against the source
text. Nothing in this module is trusted.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..core.contracts import Claim, Person, RawDocument
from ..core.providers import ROLE_EXTRACT, call_role

SYSTEM = """You extract evidenced claims about ONE engineer from public documents.

You are part of a recruitment sourcing pipeline for an Irish recruitment
agency. Every claim you emit is checked, character by character, against the
source document by a separate deterministic program. A claim whose quote is
not found verbatim in the source is silently discarded, and a high discard
rate means you have failed at this task.

RULES

1. evidence_quote must be copied EXACTLY from the supplied document text.
   This is a copy operation, not a writing task. Do not fix spelling, do not
   expand abbreviations, do not join sentences that are apart in the source,
   do not paraphrase, do not translate. Copy a contiguous run of characters.

2. If a fact is not supported by a quote, DO NOT emit a claim for it.
   Emitting nothing is correct and is what a careful analyst does. You are
   not being scored on how many claims you produce.

3. confidence:
   - "direct"   the quote states the fact plainly about this person.
   - "inferred" the quote supports it only indirectly.
   Inferred claims are never shown to the client as fact. When in doubt,
   choose "inferred". Choosing "direct" for a weak quote is the single most
   damaging error you can make here.

4. Only make claims about the named subject. These documents contain many
   people (colleagues, objectors, other witnesses, the inspector). If a quote
   describes someone else, do not attribute it to the subject.

5. Keep each quote between 12 and 400 characters. Prefer the shortest span
   that fully supports the assertion.

DIMENSIONS
  chartership       Engineers Ireland CEng/MIEI/FIEI status or equivalent
  years_experience  stated years of professional experience
  technical_skill   named software, codes, standards (Eurocode, Tekla, ...)
  sector            discipline: structural, transport, highways, rail, ...
  employer          current or past employer, and job title
  location          where they are based or work
  project           a named scheme or project they worked on
  education         degrees and institutions
  statutory_process EIAR, EIS, CPO, oral hearing, railway order, An Bord
                    Pleanala / An Coimisiun Pleanala evidence
"""

TOOL = {
    "name": "emit_claims",
    "description": "Emit the evidenced claims found about the subject.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject_confirmed_name": {
                "type": "string",
                "description": (
                    "The subject's full name exactly as written in the document. "
                    "Empty string if the document is not about this person."
                ),
            },
            "current_title": {"type": "string"},
            "current_employer": {"type": "string"},
            "location": {"type": "string"},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimension": {
                            "type": "string",
                            "enum": [
                                "chartership", "years_experience", "technical_skill",
                                "sector", "employer", "location", "project",
                                "education", "statutory_process",
                            ],
                        },
                        "assertion": {"type": "string"},
                        "evidence_quote": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["direct", "inferred"]},
                    },
                    "required": ["dimension", "assertion", "evidence_quote", "confidence"],
                },
            },
        },
        "required": ["subject_confirmed_name", "claims"],
    },
}

# Documents run to 180k chars. The qualifications section is always at the
# front; the tail is scheme detail. Head-weighted truncation keeps the part
# that carries gate-relevant evidence while bounding cost.
_HEAD = 22000
_TAIL = 6000

# Per-call cost/usage metadata for the whole run. Appended by every
# extraction so the operator gets a real EUR figure, not an estimate.
RUN_COST: list[dict] = []

# "Regional Director (Belfast Office)" / "(Cork Office)" -- an explicit office
# in the job title overrides any firm-level location default.
_OFFICE_RE = re.compile(r"\(([^)]*office[^)]*)\)", re.I)


def _window(text: str) -> str:
    if len(text) <= _HEAD + _TAIL:
        return text
    return text[:_HEAD] + "\n\n[... middle of document omitted ...]\n\n" + text[-_TAIL:]


def _claim_id(person_id: str, doc_id: str, quote: str) -> str:
    h = hashlib.sha256((person_id + doc_id + quote).encode("utf-8")).hexdigest()
    return "clm_" + h[:16]


def extract_from_document(
    person: Person, doc: RawDocument, tracker_label: str = "L5"
) -> tuple[list[Claim], Optional[dict]]:
    """Extract claims about `person` from one document.

    Returns (claims, profile_hints). profile_hints carries the model's read of
    title/employer/location, used only to populate the Person record -- every
    hint that matters is separately claimed and validated.
    """
    # An unnamed subject is normal, not an error: many briefs of evidence
    # carry the author's name only in a signature block or a header that
    # neither the URL nor a "my name is" regex reaches. The model reads the
    # document and tells us who wrote it.
    unknown = person.full_name.strip().upper() in ("", "UNKNOWN")
    if unknown:
        subject_line = (
            "SUBJECT: UNKNOWN -- identify the AUTHOR of this statement of "
            "evidence (the person whose qualifications and experience it "
            "sets out, not the scheme promoter, not the inspector, and not "
            "anyone merely mentioned in passing). Put that person's name in "
            "subject_confirmed_name. If the document has no single personal "
            "author, return an empty subject_confirmed_name."
        )
        closing = "Extract evidenced claims about that author only."
    else:
        subject_line = "SUBJECT: " + person.full_name
        closing = "Extract evidenced claims about " + person.full_name + " only."

    user = (
        subject_line + "\n\n"
        "SOURCE DOCUMENT (" + doc.source_type + ")\n"
        "URL: " + str(doc.url) + "\n"
        "--- BEGIN DOCUMENT ---\n"
        + _window(doc.content_text)
        + "\n--- END DOCUMENT ---\n\n"
        + closing
    )

    out, meta = call_role(
        role=ROLE_EXTRACT,
        system=SYSTEM,
        user=user,
        tool=TOOL,
    )
    RUN_COST.append(meta)
    if not out:
        return [], None

    confirmed = (out.get("subject_confirmed_name") or "").strip()
    if not confirmed:
        return [], None

    claims: list[Claim] = []
    for raw in out.get("claims", []):
        quote = (raw.get("evidence_quote") or "").strip()
        assertion = (raw.get("assertion") or "").strip()
        if len(quote) < 12 or not assertion:
            continue
        try:
            claims.append(
                Claim(
                    claim_id=_claim_id(person.person_id, doc.doc_id, quote),
                    subject_person_id=person.person_id,
                    dimension=raw["dimension"],
                    assertion=assertion[:280],
                    evidence_quote=quote[:400],
                    source_doc_id=doc.doc_id,
                    source_url=doc.url,
                    confidence=raw.get("confidence", "inferred"),
                )
            )
        except Exception:
            # A malformed item is dropped, never repaired. Repairing an
            # LLM's structural error is how invented data enters a pipeline.
            continue

    hints = {
        "confirmed_name": confirmed,
        "current_title": (out.get("current_title") or "").strip() or None,
        "current_employer": (out.get("current_employer") or "").strip() or None,
        "location": (out.get("location") or "").strip() or None,
    }
    return claims, hints


def name_matches(a: str, b: str) -> bool:
    """Loose name comparison for confirming a document is about the subject."""

    def toks(s: str) -> set[str]:
        s = re.sub(r"\b(dr|mr|mrs|ms|prof|professor)\b\.?", " ", s.lower())
        return {t for t in re.split(r"[^a-z]+", s) if len(t) > 1}

    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return False
    return len(ta & tb) >= min(2, min(len(ta), len(tb)))


# ---------------------------------------------------------------------------
# Directory extraction (Role 1)
# ---------------------------------------------------------------------------
# A rendered "our people" page is one document describing MANY engineers,
# so the one-document-one-subject shape above does not fit. This variant
# returns a person-keyed claim set from a single page. Every quote is still
# validated against that same page by L6, so the multi-subject shape does
# not weaken the evidence guarantee.

DIRECTORY_TOOL = {
    "name": "emit_people",
    "description": "Emit each named engineer found in this staff directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "people": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "full_name": {"type": "string"},
                        "job_title": {"type": "string"},
                        "claims": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dimension": {
                                        "type": "string",
                                        "enum": [
                                            "chartership", "years_experience",
                                            "technical_skill", "sector", "employer",
                                            "location", "project", "education",
                                            "statutory_process",
                                        ],
                                    },
                                    "assertion": {"type": "string"},
                                    "evidence_quote": {"type": "string"},
                                    "confidence": {
                                        "type": "string",
                                        "enum": ["direct", "inferred"],
                                    },
                                },
                                "required": [
                                    "dimension", "assertion",
                                    "evidence_quote", "confidence",
                                ],
                            },
                        },
                    },
                    "required": ["full_name", "claims"],
                },
            }
        },
        "required": ["people"],
    },
}

DIRECTORY_SYSTEM = SYSTEM + """

THIS DOCUMENT IS A STAFF DIRECTORY listing many engineers. Emit one entry per
NAMED individual. The same copy-exactly rule applies to every quote: each
evidence_quote must appear verbatim in this page.

Skip anyone whose entry carries no professional detail beyond a name. A name
with no grade, discipline or experience attached is not a candidate, and an
entry you cannot evidence should be omitted rather than padded.
"""


def _chunks(text: str, size: int, overlap: int = 800) -> list[str]:
    """Split a page into overlapping windows.

    Overlap matters: a directory entry split across a boundary would
    otherwise lose either its name or its qualifications. Dedup downstream
    handles the person appearing in two adjacent chunks.
    """
    if len(text) <= size:
        return [text]
    out: list[str] = []
    start = 0
    while start < len(text):
        out.append(text[start:start + size])
        start += size - overlap
    return out


def extract_directory(
    doc: RawDocument,
    employer: Optional[str] = None,
    max_chars: int = 60000,
    chunk_size: int = 10000,
    default_location: Optional[str] = None,
) -> list[tuple[Person, list[Claim]]]:
    """Extract every evidenced person from one rendered staff-directory page.

    Chunked because this environment enforces a hard 60-second ceiling on a
    single outbound request: a 60k-character directory page reliably died at
    60.2s, while the same request over 8k characters returned in 12s. Chunking
    keeps every call comfortably inside the ceiling AND improves recall, since
    the model is not asked to hold 60k characters of directory in one pass.
    """
    body = doc.content_text[:max_chars]
    merged: dict[str, dict] = {}

    for part in _chunks(body, chunk_size):
        user = (
            "SOURCE: staff directory page (one section of a larger page)\n"
            "URL: " + str(doc.url) + "\n"
            + ("EMPLOYER: " + employer + "\n" if employer else "")
            + "--- BEGIN PAGE SECTION ---\n" + part + "\n--- END PAGE SECTION ---\n\n"
            "Emit every named engineer in THIS SECTION that has at least one "
            "evidenced professional detail."
        )
        try:
            out, meta = call_role(
                role=ROLE_EXTRACT,
                system=DIRECTORY_SYSTEM,
                user=user,
                tool=DIRECTORY_TOOL,
                max_tokens=8000,
            )
        except Exception as exc:
            # One bad chunk must not lose the whole directory.
            print("[extract_directory] chunk failed: " + repr(exc)[:120])
            continue
        RUN_COST.append(meta)
        if not out:
            continue
        for entry in out.get("people", []) or []:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("full_name") or "").strip()
            if not name:
                continue
            slot = merged.setdefault(
                name.lower(), {"full_name": name, "job_title": "", "claims": []}
            )
            if not slot["job_title"]:
                slot["job_title"] = entry.get("job_title") or ""
            slot["claims"].extend(entry.get("claims") or [])

    results: list[tuple[Person, list[Claim]]] = []
    for entry in merged.values():
        name = (entry.get("full_name") or "").strip()
        if len(name.split()) < 2:
            continue
        pid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        title = (entry.get("job_title") or "").strip() or None
        # A firm's own staff directory places its people at that firm's
        # country unless the entry says otherwise. The per-person title still
        # wins -- "Regional Director (Belfast Office)" must still fail the
        # located_ie gate, so the title is checked before the firm default.
        person = Person(
            person_id=pid,
            full_name=name,
            current_title=title,
            current_employer=employer,
            location=(title if title and _OFFICE_RE.search(title) else default_location),
            doc_ids=[doc.doc_id],
        )
        claims: list[Claim] = []
        seen_ids: set[str] = set()
        for raw in entry.get("claims", []):
            if not isinstance(raw, dict):
                continue
            quote = (raw.get("evidence_quote") or "").strip()
            assertion = (raw.get("assertion") or "").strip()
            if len(quote) < 12 or not assertion:
                continue
            cid = _claim_id(pid, doc.doc_id, quote)
            # Overlapping chunks re-emit the same quote; claim_id is a hash of
            # (person, doc, quote) so the duplicate collapses here rather than
            # inflating the evidence count on the card.
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            try:
                claims.append(
                    Claim(
                        claim_id=cid,
                        subject_person_id=pid,
                        dimension=raw["dimension"],
                        assertion=assertion[:280],
                        evidence_quote=quote[:400],
                        source_doc_id=doc.doc_id,
                        source_url=doc.url,
                        confidence=raw.get("confidence", "inferred"),
                    )
                )
            except Exception:
                continue  # malformed item dropped, never repaired
        if claims:
            results.append((person, claims))
    return results
