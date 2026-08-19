"""
L11 -- outreach drafting (SPEC.md section 12, I6, I7).

Two rules dominate this module and both are enforced in code, not in the
prompt:

  I6  The GDPR Art. 14 notice and the opt-out line are INJECTED verbatim from
      core/config.py. An LLM asked to include legal text will paraphrase it,
      and a paraphrased Art. 14 notice is a non-compliant Art. 14 notice.
      `assemble()` concatenates the constants; the model never sees a
      requirement to write them and cannot overwrite them.

  I7  Every draft is written to be sent BY GAIA, from a Gaia consultant's
      name and Gaia's domain. Prodcraft never contacts a candidate. The
      system prompt says so and the post-check strips any Prodcraft
      self-reference the model invents.

Register note: Irish market, direct and warm. "I'd love to connect regarding
an exciting opportunity" is the exact phrasing to avoid -- it reads as a
template to everyone who has ever received one.
"""

from __future__ import annotations

import re
from typing import Optional

from ..core.config import GDPR_ART14_NOTICE, OPT_OUT_LINE, PRIVACY_NOTICE_URL
from ..core.contracts import JobSpec, OutreachSequence, Person, ValidatedClaim
from ..core.providers import ROLE_MESSAGE, call_role

SYSTEM = """You draft candidate outreach for Gaia Talent, an Irish recruitment
agency. The messages are sent by a named Gaia consultant, from Gaia's own
domain. You are not the sender and you never refer to yourself, to Prodcraft,
to a tool, or to a system.

VOICE
Irish market register: direct, warm, specific, unhurried. Write the way a
senior consultant who knows engineering writes to a chartered engineer they
respect. Short sentences. No exclamation marks.

BANNED PHRASINGS -- these mark a message as automated on sight:
  "exciting opportunity", "I'd love to connect", "I came across your profile",
  "hope this email finds you well", "reaching out", "perfect fit",
  "specially selected", "rock star", "ninja", any use of "leverage" as a verb.

RULES

1. Reference something SPECIFIC and EVIDENCED about this person, drawn from
   the claims supplied. Name the scheme, the code, the grade -- the concrete
   thing. Generic personalisation is worse than none, because it reads as
   automated while pretending not to be.
2. If the only evidence is a job title, the message says less. Write the
   shorter, honest message rather than padding with invented flattery.
3. Never state or imply a salary figure. Never claim the candidate was
   "specially selected". Never oversell the role.
4. Do not mention where their contact details came from, and do not include
   any privacy or opt-out wording. Separate compliant text is appended
   afterwards and yours would duplicate or contradict it.
5. The LinkedIn note must be under 280 characters including spaces. LinkedIn
   truncates hard and a cut-off first line is worse than a short one.
6. The follow-up is a single short nudge sent about a week later. It must add
   one new piece of information rather than repeating the first message.
"""

TOOL = {
    "name": "emit_outreach",
    "description": "Draft the outreach sequence for one candidate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "linkedin_note": {
                "type": "string",
                "description": "Connection note, under 280 characters.",
            },
            "email_subject": {
                "type": "string",
                "description": "Under 80 characters. Specific, not clickbait.",
            },
            "email_body": {
                "type": "string",
                "description": (
                    "The body only. No greeting block beyond the salutation, "
                    "no signature, no privacy wording."
                ),
            },
            "follow_up": {
                "type": "string",
                "description": "Short nudge, sent about a week later.",
            },
        },
        "required": ["linkedin_note", "email_subject", "email_body", "follow_up"],
    },
}

RUN_COST: list[dict] = []

# Phrasings that mark a draft as machine-written. Checked after generation
# because a banned-word list in a prompt is a suggestion, not a guarantee.
_BANNED_RE = re.compile(
    r"(exciting opportunity|i'?d love to connect|i came across your profile|"
    r"hope this (?:email )?finds you well|perfect fit|specially selected|"
    r"reaching out to you|rock ?star|ninja)",
    re.I,
)

# Any self-reference the model invents is removed: I7 means these messages
# come from Gaia, and a candidate must never see the tooling vendor's name.
_PRODCRAFT_RE = re.compile(r"\bprod\s?craft\b[^.]*\.", re.I)


def _evidence_digest(claims: list[ValidatedClaim], limit: int = 8) -> str:
    """The specific, evidenced material the message may reference."""
    priority = {
        "project": 0, "statutory_process": 1, "technical_skill": 2,
        "chartership": 3, "employer": 4, "sector": 5, "years_experience": 6,
        "education": 7, "location": 8,
    }
    direct = sorted(
        [c for c in claims if c.confidence == "direct"],
        key=lambda c: priority.get(c.dimension, 9),
    )
    return "\n".join(
        "  - [" + c.dimension + "] " + c.assertion for c in direct[:limit]
    )


def draft(
    person: Person,
    claims: list[ValidatedClaim],
    spec: JobSpec,
    consultant_name: str = "the Gaia Talent team",
) -> Optional[OutreachSequence]:
    """Draft one sequence. Returns None if the model produced nothing usable."""
    user = (
        "SENDER: " + consultant_name + ", Gaia Talent (Ireland)\n"
        "ROLE: " + spec.title + "\n"
        "ROLE LOCATION: " + ", ".join(spec.locations) + "\n"
        "CLIENT: a major infrastructure consultancy (do not name it in the "
        "message -- naming the end client in a first touch is poor practice)\n\n"
        "CANDIDATE: " + person.full_name + "\n"
        "TITLE: " + (person.current_title or "not stated") + "\n"
        "EMPLOYER: " + (person.current_employer or "not stated") + "\n\n"
        "EVIDENCED, SPECIFIC THINGS YOU MAY REFERENCE (nothing else is known "
        "about this person, so do not imply anything beyond this list):\n"
        + (_evidence_digest(claims) or "  - (nothing beyond the title above)")
        + "\n\nDraft the sequence."
    )

    try:
        out, meta = call_role(
            role=ROLE_MESSAGE, system=SYSTEM, user=user, tool=TOOL, max_tokens=1600
        )
        RUN_COST.append(meta)
    except Exception as exc:
        print("[messages] " + person.person_id + " failed: " + repr(exc)[:120])
        return None
    if not out:
        return None

    note = _clean(out.get("linkedin_note", ""))
    subject = _clean(out.get("email_subject", ""))
    body = _clean(out.get("email_body", ""))
    follow = _clean(out.get("follow_up", ""))
    if not (note and subject and body):
        return None

    return assemble(note, subject, body, follow)


def _clean(text: str) -> str:
    text = _PRODCRAFT_RE.sub("", text or "").strip()
    text = _BANNED_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def assemble(
    linkedin_note: str, email_subject: str, email_body: str, follow_up: str
) -> OutreachSequence:
    """Attach the legal strings verbatim.

    The notice and opt-out are concatenated from module constants. There is no
    code path by which model output reaches these two fields, which is what
    makes I6 an invariant rather than an instruction.
    """
    return OutreachSequence(
        linkedin_note=linkedin_note[:300],
        email_subject=email_subject[:90],
        email_body=(
            email_body.rstrip()
            + "\n\n--\n"
            + GDPR_ART14_NOTICE
            + "\n\n"
            + OPT_OUT_LINE
        ),
        follow_up=follow_up,
        gdpr_notice=GDPR_ART14_NOTICE,
        opt_out_line=OPT_OUT_LINE,
    )


def compliance_ok(seq: OutreachSequence) -> tuple[bool, list[str]]:
    """Verify I6 on a finished sequence. Used as a hard gate before render."""
    problems: list[str] = []
    if GDPR_ART14_NOTICE not in seq.email_body:
        problems.append("Art. 14 notice missing from the email body.")
    if OPT_OUT_LINE not in seq.email_body:
        problems.append("Opt-out line missing from the email body.")
    if seq.gdpr_notice != GDPR_ART14_NOTICE:
        problems.append("Art. 14 notice was altered rather than injected verbatim.")
    if seq.opt_out_line != OPT_OUT_LINE:
        problems.append("Opt-out line was altered rather than injected verbatim.")
    if PRIVACY_NOTICE_URL not in seq.email_body:
        problems.append("Privacy-notice URL missing from the email body.")
    if _BANNED_RE.search(seq.email_body + " " + seq.linkedin_note):
        problems.append("Banned template phrasing survived into the draft.")
    if len(seq.linkedin_note) > 300:
        problems.append("LinkedIn note exceeds 300 characters.")
    return (not problems), problems


DRAFT_DISCLAIMER = (
    "These are drafts -- edit to your consultant's voice before sending. The "
    "system's job is to remove the blank page, not to replace your judgement."
)
