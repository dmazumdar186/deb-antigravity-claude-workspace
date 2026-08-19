"""
L12 -- link liveness and name match (SPEC.md I4).

"He clicks two links in the first minute. A 404 ends the evaluation."

Two independent checks, both deterministic:

  1. LIVENESS   the URL returns 200 right now.
  2. NAME MATCH the page the URL returns actually mentions the candidate.

The second check is the one that matters and the one most pipelines skip.
A staff-directory URL can return 200 long after the person has left the firm,
because the CMS serves a generic "our people" page instead of a 404. A link
that is alive but no longer about the candidate is worse than a dead link:
it looks verified.

Evidence-source URLs are checked as well as profile URLs, because every claim
on a card carries a clickable source and Keith will click those too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..core.cache import fetch, head_ok


# Statuses that mean "this server refuses robots", NOT "this page is gone".
#
# LinkedIn answers any non-browser client with 999 -- it is their standard
# anti-automation response and says nothing whatever about the profile, which
# opens perfectly in a browser. Several Irish consultancy sites answer a bare
# HEAD with 403 for the same reason; horganlynch.ie does, and this pipeline
# had already rendered that exact page successfully through Firecrawl.
#
# Reporting either as a dead link is worse than not checking at all. The
# 2026-08-19 dossier told the client "1 source link(s) did not return 200" on
# eight of eleven cards -- including the only Tier A candidate -- and in every
# case the link was the candidate's live LinkedIn profile. A reader who clicks
# one, finds it works, and sees the dossier claim otherwise has just been given
# a reason to distrust every other check on the page.
_BOT_BLOCKED_STATUSES = {999, 403, 429, 401}


@dataclass
class LinkCheck:
    url: str
    # True = confirmed live. False = confirmed gone. None = could not be
    # determined, which is a different fact and is reported as such.
    alive: Optional[bool]
    http_status: int
    name_matched: Optional[bool] = None  # None when no name was supplied
    note: str = ""

    @property
    def unverifiable(self) -> bool:
        return self.alive is None


@dataclass
class LinkReport:
    person_id: str
    checks: list[LinkCheck] = field(default_factory=list)

    @property
    def all_alive(self) -> bool:
        """True only if every link was CONFIRMED live.

        An unverifiable link makes this False, because "all links checked and
        live" is a claim, and we cannot make it about a link we could not
        reach. It does not make the link dead -- see `dead` below.
        """
        return all(c.alive is True for c in self.checks)

    @property
    def dead(self) -> list[LinkCheck]:
        """Links confirmed gone. Bot-blocked links are NOT in here."""
        return [c for c in self.checks if c.alive is False]

    @property
    def unverifiable(self) -> list[LinkCheck]:
        return [c for c in self.checks if c.alive is None]

    @property
    def name_mismatches(self) -> list[LinkCheck]:
        return [c for c in self.checks if c.name_matched is False]


# Irish surname prefixes. These attach or detach freely in published text --
# the same person is "O'Brien", "O Brien" and "OBrien" across three pages of
# the same site -- so the surname is compared with the prefix optional.
_PREFIX_RE = re.compile(r"^(o|mac|mc|ni|nic|de|van|von)[''`]?", re.I)


def _name_tokens(name: str) -> list[str]:
    """Surname-first significant tokens from a person's name.

    Titles and initials are dropped. Tokens shorter than 3 characters are
    dropped because "Ni" or "Mc" alone match far too much text -- but they
    are re-attached to the following token first, so "O Brien" survives as
    "obrien" rather than being reduced to "brien".
    """
    cleaned = re.sub(r"\b(dr|mr|mrs|ms|prof|professor)\b\.?", " ", name.lower())
    raw = [p for p in re.split(r"[^a-z''`]+", cleaned) if p]

    joined: list[str] = []
    skip = False
    for i, part in enumerate(raw):
        if skip:
            skip = False
            continue
        bare = part.replace("'", "").replace("’", "").replace("`", "")
        # A standalone prefix binds to the next token: ["o", "brien"] -> "obrien".
        if bare in ("o", "mac", "mc", "ni", "nic", "de", "van", "von") and i + 1 < len(raw):
            nxt = raw[i + 1].replace("'", "").replace("’", "").replace("`", "")
            joined.append(bare + nxt)
            skip = True
        else:
            joined.append(bare)
    return [p for p in joined if len(p) >= 3]


def _token_variants(token: str) -> list[str]:
    """A token plus its prefix-stripped form, so O'Brien matches Brien."""
    out = [token]
    m = _PREFIX_RE.match(token)
    if m and len(token) - len(m.group(0)) >= 3:
        out.append(token[len(m.group(0)):])
    return out


def _token_in(text: str, token: str) -> bool:
    """Whole-word match on any variant of the token, apostrophes ignored."""
    return any(
        re.search(r"\b" + re.escape(v) + r"\b", text) for v in _token_variants(token)
    )


def page_mentions_name(text: str, full_name: str) -> bool:
    """True if the page text plausibly refers to this person.

    Requires the SURNAME plus at least one other name token, both as whole
    words. Surname alone is too weak -- "Murphy" appears on most Irish
    company pages. Requiring the exact full string is too strict, because
    pages write "Sean O'Brien", "Seán Ó Briain" and "S. O'Brien" for the
    same person.
    """
    tokens = _name_tokens(full_name)
    if len(tokens) < 2:
        return False
    # Apostrophes are stripped from the page too, so "O'Brien" in the source
    # reduces to "obrien" and meets the name's own normalised form.
    low = re.sub(r"[''`]", "", text.lower())
    if not _token_in(low, tokens[-1]):
        return False
    return any(_token_in(low, t) for t in tokens[:-1])


def check_url(url: str, full_name: Optional[str] = None) -> LinkCheck:
    """Liveness + optional name match for one URL."""
    alive, status = head_ok(url)
    if not alive:
        if status in _BOT_BLOCKED_STATUSES:
            return LinkCheck(
                url=url, alive=None, http_status=status,
                note=(
                    "This site refuses automated requests (HTTP " + str(status)
                    + "), so the link could not be checked from here. That is "
                    "not evidence the page is missing -- open it in a browser."
                ),
            )
        return LinkCheck(
            url=url, alive=False, http_status=status,
            note="URL did not return 200 (" + str(status) + ")",
        )

    if not full_name:
        return LinkCheck(url=url, alive=True, http_status=status)

    doc = fetch(url)
    if doc is None or not doc.content_text.strip():
        # Alive per HEAD but the body could not be read (PDF-in-a-viewer,
        # JS-only page). Recorded as unknown rather than silently "matched" --
        # asserting a match we did not perform is the failure this layer
        # exists to prevent.
        return LinkCheck(
            url=url, alive=True, http_status=status, name_matched=None,
            note="Live, but page text was not readable for a name check.",
        )

    matched = page_mentions_name(doc.content_text, full_name)
    return LinkCheck(
        url=url, alive=True, http_status=status, name_matched=matched,
        note="" if matched else (
            "Live, but the page no longer mentions this person by name -- "
            "they may have moved on. Confirm before using this link."
        ),
    )


def check_person(
    person_id: str,
    full_name: str,
    profile_url: Optional[str],
    evidence_urls: list[str],
) -> LinkReport:
    """Check a candidate's profile URL and every evidence URL on their card."""
    report = LinkReport(person_id=person_id)
    seen: set[str] = set()

    if profile_url:
        seen.add(profile_url)
        report.checks.append(check_url(profile_url, full_name))

    for url in evidence_urls:
        if url in seen:
            continue
        seen.add(url)
        # Evidence documents are checked for liveness only. A witness
        # statement PDF names its author, but an ACP case bundle may serve
        # the same URL for several people, so a name check there produces
        # false alarms rather than signal.
        report.checks.append(check_url(url, None))

    return report
