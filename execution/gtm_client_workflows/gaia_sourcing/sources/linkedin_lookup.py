"""
Resolve a candidate's real LinkedIn profile URL.

Prospeo returns a profile URL for some people and not others. For the six it
missed, the card fell back to handing the reader a LinkedIn SEARCH -- honest,
but a search box is not a contact route, and the profiles turn out to be
findable in one query. `site:linkedin.com/in "Name" Employer` returned the
right person for every candidate tried by hand.

THE HAZARD, WHICH IS THE WHOLE DESIGN
-------------------------------------
Linking the wrong human is far worse than linking nothing. A consultant who
messages a stranger with the same name has burned the approach and embarrassed
the client, and the dossier's promise -- every line traceable to a source that
supports it -- is broken in the most visible way possible.

Rouslan Taskov is the live example: two LinkedIn profiles, both named Rouslan
Taskov, both saying Barrett Mahony Consulting Engineers, one Bulgarian and one
UK. There is no honest way to pick. So the rule is a UNIQUE winner or nothing:
a result must carry the surname AND a real token of the employer, and if two
results tie on that evidence the lookup returns None and the card keeps the
search link. Ambiguity resolves downward, the same way an unrecognised email
status does.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from ..core.config import CONFIG, secret

_PROFILE_RE = re.compile(r"^https?://([a-z]{2}\.)?linkedin\.com/in/[^/?#]+", re.I)

# Words that carry no identifying weight when matching an employer.
_STOPWORDS = {
    "consulting", "engineers", "engineering", "consultants", "group", "ltd",
    "limited", "and", "the", "of", "associates", "partners", "company", "plc",
    "international", "ireland", "uk", "services", "solutions", "design",
}


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.split(r"[^a-z0-9]+", (text or "").lower())
        if len(t) > 2 and t not in _STOPWORDS
    }


def _serper(query: str, num: int = 5) -> list[dict]:
    import requests

    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": secret("SERPER_API_KEY"),
                     "Content-Type": "application/json"},
            data=json.dumps({"q": query, "num": num}),
            timeout=CONFIG.request_timeout_s,
        )
        if r.status_code != 200:
            return []
        return r.json().get("organic") or []
    except Exception as exc:
        # A search outage degrades this to the search-link fallback, which is
        # exactly what the card did before this module existed.
        print("[linkedin_lookup] search failed: " + repr(exc)[:110])
        return []


def _score(item: dict, full_name: str, employer: str) -> Optional[int]:
    """How well a result evidences that it is THIS person. None = not a match."""
    link = (item.get("link") or "").strip()
    if not _PROFILE_RE.match(link):
        return None
    title = item.get("title") or ""
    blob = (title + " " + link).lower()

    parts = [p for p in re.split(r"\s+", full_name.strip()) if len(p) > 1]
    if not parts:
        return None
    surname = parts[-1].lower()
    forename = parts[0].lower()
    # The surname is mandatory. A first-name-only match is a different person.
    if surname not in blob:
        return None

    score = 0
    if forename in blob:
        score += 2
    emp_tokens = _tokens(employer)
    if emp_tokens:
        overlap = len(emp_tokens & _tokens(title))
        if not overlap:
            # No employer evidence at all. Could be anyone with this name.
            return None
        score += 3 * overlap
    # An Irish profile for an Irish role is weak corroboration, not proof.
    if link.lower().startswith("https://ie.linkedin.com"):
        score += 1
    return score


def resolve(full_name: str, employer: Optional[str]) -> Optional[str]:
    """The person's profile URL, or None when it cannot be established.

    None is a real answer here and is returned freely. The caller falls back
    to a search link, which is worse UX and better than a wrong human.
    """
    if not full_name or not employer:
        return None

    results = _serper('site:linkedin.com/in "' + full_name + '" ' + employer)
    scored: list[tuple[int, str]] = []
    for item in results:
        s = _score(item, full_name, employer)
        if s is not None:
            scored.append((s, (item.get("link") or "").split("?")[0]))
    if not scored:
        return None

    scored.sort(key=lambda x: -x[0])
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        # Two profiles with equal evidence. Rouslan Taskov has exactly this:
        # same name, same firm, two countries. Guessing is not available.
        print("[linkedin_lookup] ambiguous for " + full_name + ": "
              + ", ".join(u for _, u in scored[:2]) + " -- keeping the search link")
        return None
    return scored[0][1]
