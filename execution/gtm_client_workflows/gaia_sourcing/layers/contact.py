"""
L9 -- contact enrichment with honest status labels (SPEC.md I5, section 10).

PRIOR ART PASS (2026-08-19, per ~/.claude/rules/prior-art-first.md)
------------------------------------------------------------------
- Public API exists? Yes, paid: Prospeo. The endpoints named in SPEC.md
  section 10 (Dropcontact, Hunter) were not provisioned; Prospeo was.
- IMPORTANT CONTRACT FINDING, verified live 2026-08-19: the endpoints in
  every third-party tutorial (`/email-finder`, `/domain-search`) are
  DEPRECATED and return HTTP 400 `{"error_code":"DEPRECATED"}`. The current
  endpoint is POST https://api.prospeo.io/enrich-person.
- Second contract finding: a miss returns **HTTP 400** with
  `{"error":true,"error_code":"NO_MATCH"}`, not a 200 with an empty body.
  A client that treats 4xx as a hard error therefore reads every miss as an
  outage. Handled explicitly below.
- Third: emails come back UNMASKED (`"eoghan@fin.ai"`, not `"eoghan@***"`)
  with `verification_method: "SMTP"`. Verified against a live call.
- Recommended architecture: Prospeo enrich-person by LinkedIn URL when we
  have one, else by name + employer domain; then deterministic pattern
  inference as a clearly-labelled last resort.

THE HONESTY RULE (I5)
---------------------
`verified` / `catch_all` / `pattern_guess` / `none` are never collapsed.
An unrecognised upstream status degrades DOWNWARD to `pattern_guess`, never
upward to `verified`. If Gaia sends on this data and bounces at 5%+, we have
handed the client a domain-reputation liability -- which is exactly the kind
of thing an MD remembers.

CHANNEL RECOMMENDATION (I8)
---------------------------
Default is LinkedIn, always. Emailing a senior engineer at their current
employer's address about leaving that employer is an unforced error --
corporate mail is monitored. Work email is a third-choice channel and is
labelled as such on the card.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import urlparse

from ..core.config import secret
from ..core.contracts import ContactRecord, EmailStatus, Person

PROSPEO_ENRICH = "https://api.prospeo.io/enrich-person"
PROSPEO_ACCOUNT = "https://api.prospeo.io/account-information"

# Upstream status -> our label. Anything NOT in this table degrades to
# "pattern_guess": we would rather understate deliverability than hand Gaia
# a bounce. Deliberately conservative, per I5.
_STATUS_MAP: dict[str, EmailStatus] = {
    "VERIFIED": "verified",
    "VALID": "verified",
    "ACCEPT_ALL": "catch_all",
    "CATCH_ALL": "catch_all",
    "RISKY": "catch_all",
    "UNKNOWN": "pattern_guess",
    "GUESS": "pattern_guess",
    "PATTERN": "pattern_guess",
    "UNVERIFIED": "pattern_guess",
}

# Known employer -> mail domain, for the pattern-inference fallback. Only
# firms whose domain we have actually fetched from during this run appear
# here; guessing a domain we have never resolved would compound one guess
# with another.
_EMPLOYER_DOMAINS = {
    "roughan & o'donovan": "rod.ie",
    "punch consulting engineers": "punchconsulting.com",
    "dbfl consulting engineers": "dbfl.ie",
    "waterman moylan": "watermanmoylan.ie",
    "malachy walsh & partners": "mwp.ie",
    "nicholas o'dwyer": "nodwyer.com",
    "byrne looby": "byrnelooby.com",
    "garland consultancy": "garland.ie",
    "fehily timoney": "ftco.ie",
    "barrett mahony": "bmce.ie",
    "cora consulting engineers": "cora.ie",
    "rps group ireland": "rpsgroup.com",
    "arup ireland": "arup.com",
    "jacobs ireland": "jacobs.com",
    "jacobs": "jacobs.com",
    "o'connor sutton cronin": "ocsc.ie",
    "casey o'donnell": "caseyodonnell.ie",
    "clifton scannell emerson": "cseassociates.ie",
    "kavanagh mansfield": "kmce.ie",
}

_RUN_STATS = {"calls": 0, "hits": 0, "no_match": 0, "errors": 0, "credits_used": 0}


def run_stats() -> dict:
    return dict(_RUN_STATS)


def _post(url: str, body: dict, timeout: int = 60) -> tuple[Optional[dict], str]:
    """POST to Prospeo. Returns (payload, status_label).

    status_label is one of "ok", "no_match", "error". A miss arrives as an
    HTTP 400 carrying error_code NO_MATCH -- that is a normal, uncharged
    outcome and must not be logged as a failure.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-KEY": secret("PROSPEO_API_KEY")},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace")), "ok"
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            payload = {}
        code = str(payload.get("error_code", ""))
        if code == "NO_MATCH":
            return None, "no_match"
        print("[contact] prospeo HTTP " + str(exc.code) + " " + code)
        return None, "error"
    except Exception as exc:
        print("[contact] prospeo call failed: " + repr(exc)[:120])
        return None, "error"


def account_credits() -> Optional[int]:
    payload, status = _post(PROSPEO_ACCOUNT, {})
    if status != "ok" or not payload:
        return None
    return (payload.get("response") or {}).get("remaining_credits")


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in re.split(r"\s+", full_name.strip()) if p]
    if len(parts) < 2:
        return full_name.strip(), ""
    return parts[0], parts[-1]


def _employer_domain(employer: Optional[str]) -> Optional[str]:
    if not employer:
        return None
    low = employer.strip().lower()
    if low in _EMPLOYER_DOMAINS:
        return _EMPLOYER_DOMAINS[low]
    for name, dom in _EMPLOYER_DOMAINS.items():
        if name in low or low in name:
            return dom
    return None


def enrich(person: Person, employer_domain: Optional[str] = None) -> ContactRecord:
    """Look up one person. Never raises -- a failed lookup yields status 'none'."""
    domain = employer_domain or _employer_domain(person.current_employer)
    first, last = _split_name(person.full_name)

    data: dict = {}
    if person.linkedin_url:
        data["linkedin_url"] = str(person.linkedin_url)
    else:
        if not first or not last:
            return _no_contact(person, "Name could not be split into first/last.")
        data["first_name"] = first
        data["last_name"] = last
        if person.current_employer:
            data["company_name"] = person.current_employer
        if domain:
            data["company_website"] = domain
        if not (data.get("company_name") or data.get("company_website")):
            return _no_contact(
                person, "No employer known, so no lookup key beyond a bare name."
            )

    _RUN_STATS["calls"] += 1
    payload, status = _post(
        PROSPEO_ENRICH,
        {"only_verified_email": False, "enrich_mobile": False, "data": data},
    )
    time.sleep(0.3)  # courtesy spacing; Prospeo does not publish a hard RPS

    if status == "no_match":
        _RUN_STATS["no_match"] += 1
        return _pattern_fallback(person, domain)
    if status != "ok" or not payload:
        _RUN_STATS["errors"] += 1
        return _pattern_fallback(person, domain)

    p = payload.get("person") or {}
    email_block = p.get("email") or {}
    email = (email_block.get("email") or "").strip() or None
    revealed = bool(email_block.get("revealed"))
    upstream = str(email_block.get("status", "")).upper()

    # A masked address ("eoghan.*****@intercom.com") is not an address. It is
    # reported as no-email rather than shipped as something a consultant will
    # try to send to.
    if email and (not revealed or "*" in email):
        email = None

    if not email:
        return _pattern_fallback(person, domain)

    _RUN_STATS["hits"] += 1
    _RUN_STATS["credits_used"] += 0 if payload.get("free_enrichment") else 1
    label: EmailStatus = _STATUS_MAP.get(upstream, "pattern_guess")
    method = email_block.get("verification_method") or "unspecified"

    linkedin = p.get("linkedin_url") or (
        str(person.linkedin_url) if person.linkedin_url else None
    )
    return ContactRecord(
        person_id=person.person_id,
        email=email,
        email_status=label,
        email_provider=(
            "Prospeo (" + str(method) + ")"
            if label == "verified"
            else "Prospeo (" + str(upstream or "unspecified") + ")"
        ),
        linkedin_url=linkedin,
        linkedin_live=False,  # set by L12, never asserted here
        recommended_first_channel="linkedin" if linkedin else _fallback_channel(label),
        channel_rationale=_rationale(label, bool(linkedin)),
    )


def _fallback_channel(label: EmailStatus) -> str:
    return "work_email" if label in ("verified", "catch_all") else "phone"


def _rationale(label: EmailStatus, has_linkedin: bool) -> str:
    if has_linkedin:
        base = (
            "LinkedIn first. Approaching a senior engineer at their current "
            "employer's mailbox about leaving that employer is monitored mail "
            "and poor tradecraft (I8)."
        )
    else:
        base = "No LinkedIn profile resolved, so email is the only route found."
    tail = {
        "verified": " Work email is SMTP-confirmed and is a reasonable second touch.",
        "catch_all": (
            " The employer runs a catch-all mail server, so the address is "
            "plausible but NOT confirmed deliverable. Treat a non-reply as "
            "uninformative."
        ),
        "pattern_guess": (
            " The address is inferred from the employer's naming pattern and is "
            "unconfirmed. Do not use it for a first touch."
        ),
        "none": " No address was found. LinkedIn or phone only.",
    }[label]
    return base + tail


def _no_contact(person: Person, why: str) -> ContactRecord:
    return ContactRecord(
        person_id=person.person_id,
        email=None,
        email_status="none",
        linkedin_url=str(person.linkedin_url) if person.linkedin_url else None,
        recommended_first_channel="linkedin",
        channel_rationale="No email route found. " + why,
    )


# Deterministic pattern inference -- the explicitly-labelled last resort.
# firstname.lastname@ is the dominant convention at Irish engineering
# consultancies. It is a GUESS, it is labelled a guess on the card, and I8
# means nobody should be sending to it as a first touch anyway.
def _pattern_fallback(person: Person, domain: Optional[str]) -> ContactRecord:
    if not domain:
        return _no_contact(person, "No confirmed employer domain to infer from.")
    first, last = _split_name(person.full_name)
    if not first or not last:
        return _no_contact(person, "Name could not be split into first/last.")
    local = _slug(first) + "." + _slug(last)
    if not local.strip("."):
        return _no_contact(person, "Name did not reduce to an ASCII local part.")
    guess = local + "@" + domain
    return ContactRecord(
        person_id=person.person_id,
        email=guess,
        email_status="pattern_guess",
        email_provider="pattern inference (firstname.lastname@" + domain + ")",
        linkedin_url=str(person.linkedin_url) if person.linkedin_url else None,
        recommended_first_channel="linkedin",
        channel_rationale=_rationale("pattern_guess", bool(person.linkedin_url)),
    )


def _slug(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", s.lower())


def domain_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    net = urlparse(str(url)).netloc.lower()
    return net[4:] if net.startswith("www.") else net or None
