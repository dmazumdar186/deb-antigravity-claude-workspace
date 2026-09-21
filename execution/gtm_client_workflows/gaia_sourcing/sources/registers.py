"""
Shared helpers for the chartership-register plugins (engineers_ireland.py,
istructe.py, ice.py) plus the claim emitter that turns a register page into
a Claim.

Deterministic only -- no LLM, no network. The register plugins each fetch a
RawDocument; this module decides, from the document's own text, whether the
requested person is actually named in it (both forename and surname on the
same line/fragment) before anything downstream is allowed to call that a
chartership claim.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from ..core.contracts import Claim, Person, RawDocument

# How far either side of a forename hit to look for the matching surname when
# the surrounding text has no clean line boundary (rendered markdown from
# fetch_rendered can collapse a directory row onto one enormous "line" with
# no newline in it at all). Wide enough to span a "Name ... Grade ...
# Location" row, narrow enough that it can't wander into a neighbouring
# person's row on a densely packed listing.
_WINDOW = 200

# A line longer than this is not a usable line boundary -- it means the
# surrounding text has no real newline structure (one long blob), so the
# character window below is the only option. Below this length, the line
# itself is authoritative: if the surname isn't on the SAME line as the
# forename, that occurrence is not a match. Without this, a short document
# listing two different people on adjacent lines (Jane Testperson / John
# Otherperson) had the character window bridge across the line break and
# wrongly report Jane Testperson's line as containing "Otherperson" too.
_MAX_LINE = 600


def path_allowed_by_robots(path: str, disallowed_prefixes: list[str]) -> bool:
    """True unless `path` sits under one of the verified robots.txt Disallow
    prefixes for this site's `User-agent: *` group. Deliberately a prefix
    check, not a full robots.txt parser -- each register plugin hardcodes
    the disallow list it verified live, and this is all that list needs."""
    return not any(path.startswith(p) for p in disallowed_prefixes)


def fragment_with_both_names(text: str, forename: str, surname: str) -> str | None:
    """The tightest fragment of `text` that contains both name parts
    together, or None if they never co-occur. Prefers the enclosing line;
    falls back to a character window when the text has no useful line
    breaks around the match.
    """
    if not forename or not surname:
        return None
    low = text.lower()
    f_low, s_low = forename.lower(), surname.lower()
    start = 0
    while True:
        idx = low.find(f_low, start)
        if idx == -1:
            return None

        line_start = text.rfind("\n", 0, idx) + 1
        line_end = text.find("\n", idx)
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end].strip()

        if len(line) <= _MAX_LINE:
            # A real line boundary exists -- it is authoritative. The
            # surname must be on THIS line, or this occurrence is not a
            # match (never bridge across a line break to borrow a
            # neighbour's surname).
            if s_low in line.lower() and len(line) >= 12:
                return line[:400]
        else:
            # No usable line structure (one long blob) -- fall back to a
            # bounded character window around this occurrence.
            lo = max(0, idx - _WINDOW)
            hi = min(len(text), idx + len(forename) + _WINDOW)
            window = text[lo:hi].strip()
            if s_low in window.lower() and len(window) >= 12:
                return window[:400]

        start = idx + 1


def claims_from_register_doc(doc: RawDocument, person: Person) -> list[Claim]:
    """A chartership Claim, verbatim-quoted from `doc`, only when both the
    person's forename and surname appear together in it. Otherwise []
    -- never a claim built from a partial or coincidental name match, per
    RADAR_CONTRACTS.md's "no claim ships without a verbatim quote" rule
    (I1/I2 in HANDOFF.md section 5).
    """
    parts = [p for p in person.full_name.split() if p]
    if len(parts) < 2:
        return []
    forename, surname = parts[0], parts[-1]
    quote = fragment_with_both_names(doc.content_text, forename, surname)
    if not quote:
        return []

    host = urlparse(str(doc.url)).netloc
    claim_id = hashlib.sha256(
        (doc.doc_id + "|" + person.person_id + "|chartership").encode("utf-8")
    ).hexdigest()[:24]

    return [
        Claim(
            claim_id=claim_id,
            subject_person_id=person.person_id,
            dimension="chartership",
            assertion=f"{person.full_name} appears in the {host} chartership register",
            evidence_quote=quote,
            source_doc_id=doc.doc_id,
            source_url=doc.url,
            confidence="direct",
        )
    ]
