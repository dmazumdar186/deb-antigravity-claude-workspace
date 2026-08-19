"""
Source plugin: An Coimisiun Pleanala (formerly An Bord Pleanala).

PRIOR ART PASS (2026-08-19, per ~/.claude/rules/prior-art-first.md)
------------------------------------------------------------------
- Public API exists? Effectively yes. No auth, no login, no scraping
  workaround needed. Case pages at /en-ie/case/{n} expose document links
  directly in the HTML. Inspector reports sit at a deterministic path:
  /anbordpleanala/media/abp/cases/reports/{first3}/r{case}.pdf
  The pre-2016 archive exposes /api/documents/Report/{first3}/R{case}A.pdf.
  Directory browsing under /publicaccess/ returns 403, but the case page
  lists every document, so enumeration is unnecessary.
- Best existing open-source approach: none found. No public repo scrapes
  ACP witness statements; this is unworked ground.
- Why we crib / not crib: nothing to crib. But the source is far richer
  than SPEC.md section 6 anticipated -- see below.
- Recommended architecture: case page -> regex hrefs -> download the
  "Oral Hearing Documents" PDFs -> PyMuPDF text -> L5 extraction.

WHY THIS IS THE HIGHEST-VALUE SOURCE IN THE BUILD
-------------------------------------------------
Oral hearing witness statements open with a mandatory qualifications
section (required by s.39(1)(a) of the Transport (Railway Infrastructure)
Act 2001 and by ACP practice). A single free public PDF therefore
evidences every Role 2 hard gate at once, in quotable prose. Verbatim
from ABP-310286 (Iarnrod Eireann, Cork line level crossings):

    "I have over 26 years post graduate experience and I am a Senior
     Associate Director of Highways in Jacobs. ... I am a Chartered
     Member and Fellow of the Institution of Engineers of Ireland
     (Engineers Ireland) ... A number of these projects included the
     preparation of the roads order documentation (EIAR and CPO)."

That one paragraph carries chartership, seniority, employer, title,
discipline AND the EIAR/CPO statutory-process signal. And the author is,
by construction, a person who gave evidence at an oral hearing -- the
exact requirement Role 2 is gated on.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import unquote, urljoin

from ..core.cache import fetch, fetch_raw
from ..core.config import CONFIG, secret
from ..core.contracts import RawDocument

BASE = "https://www.pleanala.ie"

# Link shapes on a case page.
_HREF_RE = re.compile(rb'href\s*=\s*["\']([^"\']+)["\']', re.I)

# Documents worth pulling. Witness statements are the prize; briefs of
# evidence and opening statements carry the same qualifications section.
_WITNESS_HINTS = [
    "witness statement",
    "brief of evidence",
    "statement of evidence",
    "evidence of",
    "opening statement",
]
# Folder shapes that indicate oral-hearing material. ACP is not consistent:
# MetroLink files them under "Oral Hearing Documents (...)", the Cork line
# case under "OH submission from applicant". Both must match or the richest
# consultancy-authored statements are missed.
_ORAL_HEARING_HINTS = [
    "oral hearing", "oral_hearing", "oralhearing",
    "oh submission", "oh submissions", "/oh ", " oh/",
]

# Document-type phrases that the person-name fallback must never return.
# Without this, "Ruadhan MacEoin - Witness Statement.pdf" yields a candidate
# named "Witness Statement".
_NOT_A_NAME = {
    "witness statement", "brief of evidence", "statement of evidence",
    "opening statement", "oral hearing", "railway order", "railway works",
    "an bord", "bord pleanala", "module", "final", "draft", "appendix",
}

# Filenames that are documents ABOUT the process, not about a person.
_NOISE_HINTS = [
    "agenda", "timetable", "schedule of errata", "draft railway order",
    "list of", "index", "attendance sheet", "programme", "errata",
    "schedule of updates", "notice", "transcript",
]


@dataclass
class ACPDoc:
    case_no: str
    url: str
    filename: str
    party: Optional[str]
    person_hint: Optional[str]


def _decode_name(url: str) -> str:
    return unquote(url.rsplit("/", 1)[-1]).replace("%20", " ")


def _is_person_document(name: str) -> bool:
    low = name.lower()
    if not any(h in low for h in _WITNESS_HINTS):
        return False
    if any(n in low for n in _NOISE_HINTS):
        return False
    return low.endswith(".pdf")


# "No.02 - TII - Witness Statement of Aidan Foley.pdf"
_PERSON_RE = re.compile(
    r"(?:witness statement of|statement of evidence of|brief of evidence of|evidence of)\s+"
    r"([A-Z][A-Za-z'`\-]+(?:\s+[A-Z][A-Za-z'`\-]+){1,3})",
    re.I,
)
# "... - Gerry Healy - 25.9.22.pdf"  /  "No.09 - TII - Schedule ..."
_PARTY_RE = re.compile(r"^No\.?\s*\d+\s*[-–]\s*([^-–]+?)\s*[-–]", re.I)


# Tokens that prove a capitalised phrase is a document title or an
# organisation, not a person. "Buildings Desk Study" and "Documents Received"
# both match a Firstname-Lastname shape otherwise.
_NAME_STOP_WORDS = {
    # document nouns
    "report", "reports", "study", "statement", "statements", "plan", "plans",
    "overview", "drawing", "drawings", "note", "notes", "presentation",
    "submission", "submissions", "received", "documents", "document",
    "review", "assessment", "estimate", "addendum", "appendix", "narrative",
    "summary", "figures", "projections", "sequencing", "clearance", "letter",
    "map", "maps", "photomontage", "photomontages", "slides", "options",
    "locations", "location", "update", "updated", "combined", "agreement",
    "mitigation", "monitoring", "interface", "benefits", "facilities",
    "forecasts", "impact", "impacts", "works", "order", "module", "history",
    "details", "comments", "issues", "concerns", "background", "withdrawn",
    "attachment", "response", "rebuttal", "legal", "site", "sites", "lands",
    "boundary", "parking", "cycle", "desk", "flow", "trigger", "action",
    "hearing", "evidence", "witness", "brief", "opening", "coordination",
    # organisation / entity nouns
    "ltd", "limited", "plc", "gmbh", "unlimited", "company", "companies",
    "council", "association", "associates", "group", "hospital", "hotel",
    "properties", "property", "investments", "securities", "campaign",
    "coalition", "college", "heritage", "airport", "club", "residents",
    "management", "mgmt", "real", "estate", "assurance", "life", "theatre",
    "taisce", "commuter", "cycling", "metro", "metrolink", "rail", "railway",
    "construction", "development", "architectural", "conservation", "area",
    "internal", "memo", "stakeholder", "communications", "preferred", "route",
    "design", "tunnel", "lining", "support", "enhanced", "buildings",
    "population", "educational", "jobs", "biodiversity", "arboricultural",
    "hostile", "vehicle", "vertical", "deviation", "noise", "dust",
    "vibrator", "vibration", "cultural", "planning", "referencing",
    "traffic", "transport", "eia", "eiar", "nis", "lvia", "oh",
}


def _looks_like_name(text: str) -> bool:
    low = text.lower().strip()
    if low in _NOT_A_NAME:
        return False
    if any(bad in low for bad in _NOT_A_NAME):
        return False
    tokens = re.split(r"[\s\-']+", low)
    if any(t in _NAME_STOP_WORDS for t in tokens if t):
        return False
    # Two to four capitalised words, allowing O'Brien / Mac-Eoin / Ni Chuinn.
    return bool(
        re.fullmatch(
            r"[A-Z][A-Za-z'`À-ſ\-]+(?:\s+(?:de|van|Mac|Mc|O')?"
            r"[A-Z][A-Za-z'`À-ſ\-]+){1,3}",
            text.strip(),
        )
    )


def _person_from_filename(name: str) -> Optional[str]:
    m = _PERSON_RE.search(name)
    if m:
        cand = " ".join(m.group(1).split())
        if _looks_like_name(cand):
            return cand
    # Fallback: "... - Firstname Lastname - 25.9.22.pdf" or leading
    # "Ruadhan MacEoin - Witness Statement.pdf".
    stem = re.sub(r"\.pdf$", "", name, flags=re.I)
    stem = re.sub(r"^No\.?\s*\d+\s*[-–]\s*", "", stem, flags=re.I)
    parts = [p.strip() for p in re.split(r"[-–]", stem) if p.strip()]
    for p in parts:
        # Drop trailing dates like "25.9.22" and qualifiers like "Final".
        if re.search(r"\d", p):
            continue
        if _looks_like_name(p):
            return p
    return None


def _party_from_filename(name: str) -> Optional[str]:
    m = _PARTY_RE.search(name)
    return m.group(1).strip() if m else None


def case_documents(case_no: str) -> list[ACPDoc]:
    """List every downloadable document link on a case page."""
    raw = fetch_raw(BASE + "/en-ie/case/" + str(case_no))
    if raw is None:
        return []
    out: list[ACPDoc] = []
    seen: set[str] = set()
    for m in _HREF_RE.finditer(raw):
        href = m.group(1).decode("utf-8", errors="replace")
        if ".pdf" not in href.lower():
            continue
        if "/publicaccess/" not in href and "/media/abp/cases/" not in href:
            continue
        url = urljoin(BASE, href)
        if url in seen:
            continue
        seen.add(url)
        name = _decode_name(url)
        out.append(
            ACPDoc(
                case_no=str(case_no),
                url=url,
                filename=name,
                party=_party_from_filename(name),
                person_hint=_person_from_filename(name),
            )
        )
    return out


def witness_statements(case_no: str) -> list[ACPDoc]:
    """Person-authored oral-hearing documents for a case."""
    docs = case_documents(case_no)
    keep: list[ACPDoc] = []
    for d in docs:
        url_low = unquote(d.url).lower()
        name_low = d.filename.lower()
        if any(n in name_low for n in _NOISE_HINTS):
            continue
        in_oh_folder = any(h in url_low for h in _ORAL_HEARING_HINTS)
        titled_as_evidence = _is_person_document(d.filename)
        # Inside an oral-hearing folder, a resolvable personal name is enough:
        # ACP does not consistently title these "Witness Statement".
        if in_oh_folder and d.person_hint:
            keep.append(d)
        elif titled_as_evidence and d.person_hint:
            keep.append(d)
    return keep


def inspector_report_url(case_no: str) -> str:
    c = str(case_no)
    return BASE + "/anbordpleanala/media/abp/cases/reports/" + c[:3] + "/r" + c + ".pdf"


# ---------------------------------------------------------------------------
# Case discovery
# ---------------------------------------------------------------------------

# Seed set: major Irish transport / infrastructure consents that ran oral
# hearings with an EIAR. These are the schemes whose witness lists ARE the
# population of Irish engineers with Oral Hearing + EIAR/CPO evidence.
SEED_CASES: list[str] = [
    "314724",  # MetroLink (Estuary to Charlemont) railway order
    "310286",  # Cork line level crossings railway order
    "313730",  # (control: no oral hearing -- exercises the empty path)
    "308839",
    "319657",
    "320440",
    "322991",
]


def discover_cases_serper(queries: Iterable[str], per_query: int = 20) -> list[str]:
    """Find ACP case numbers via Serper site-restricted search.

    Google has indexed the /publicaccess/ tree, which is how these documents
    are discoverable at all -- directory listing is 403.
    """
    import requests

    key = secret("SERPER_API_KEY")
    found: set[str] = set()
    for q in queries:
        try:
            r = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                data=json.dumps({"q": q, "num": per_query}),
                timeout=CONFIG.request_timeout_s,
            )
            if r.status_code != 200:
                continue
            payload = r.json()
        except Exception:
            continue
        for item in payload.get("organic", []):
            link = item.get("link", "")
            m = re.search(r"/Case%20Documentation/(\d{6})/", link) or re.search(
                r"/cases/reports/\d{3}/r(\d{6})", link
            )
            if m:
                found.add(m.group(1))
    return sorted(found)


DISCOVERY_QUERIES = [
    'site:pleanala.ie "Witness Statement of" "Oral Hearing"',
    'site:pleanala.ie "Brief of Evidence" "Chartered" engineer',
    'site:pleanala.ie "Oral Hearing" "EIAR" road scheme evidence',
    'site:pleanala.ie "Oral Hearing" "Statement of Evidence" transport',
    'site:pleanala.ie "Brief of Evidence" CPO compulsory purchase engineer',
]


def fetch_documents(docs: list[ACPDoc]) -> list[RawDocument]:
    """Download + text-extract, through the cache. Failures degrade silently."""
    out: list[RawDocument] = []
    for d in docs:
        rd = fetch(d.url, source_type="acp_witness_statement")
        if rd is not None and rd.content_text.strip():
            out.append(rd)
    return out


# ---------------------------------------------------------------------------
# Text-level evidence gate
# ---------------------------------------------------------------------------
# Filenames are an unreliable prefilter: ACP mixes person-authored statements
# with technical appendices in the same folder. The document TEXT is reliable,
# because a statement of evidence opens with a mandatory qualifications
# section written in the first person. This gate is deterministic -- no LLM.

_FIRST_PERSON_QUAL_RE = re.compile(
    r"(my name is"
    r"|i am employed as"
    r"|i am a chartered"
    r"|i am a director"
    r"|i hold a (?:bachelor|master|degree|b\.?eng|b\.?e\b|m\.?eng|msc)"
    r"|qualifications and (?:role|experience)"
    r"|i graduated"
    r"|years(?:'|’)? (?:post[- ]?graduate )?experience"
    r"|i confirm that i have"
    r"|brief of evidence of"
    r"|statement of evidence"
    r")",
    re.I,
)

_PERSON_NAME_IN_TEXT_RE = re.compile(
    r"my name is\s+([A-Z][A-Za-z'`\-]+(?:\s+(?:Mac|Mc|O')?[A-Z][A-Za-z'`\-]+){1,3})"
)


def looks_like_evidence_document(text: str) -> bool:
    """True if the text reads like a personal statement of evidence.

    Requires at least two independent first-person qualification signals so a
    single stray phrase in a technical appendix does not qualify.
    """
    if len(text) < 400:
        return False
    hits = {m.group(1).lower()[:18] for m in _FIRST_PERSON_QUAL_RE.finditer(text[:12000])}
    return len(hits) >= 2


def name_from_text(text: str) -> Optional[str]:
    """Authoritative name, taken from the document's own words."""
    m = _PERSON_NAME_IN_TEXT_RE.search(text[:8000])
    return " ".join(m.group(1).split()) if m else None


def harvest(case_no: str, verify_text: bool = True) -> list[tuple[ACPDoc, RawDocument]]:
    """Full pipeline for one case: discover -> download -> text-gate.

    Returns only documents that survive the text-level evidence gate, so
    downstream layers never see a technical appendix masquerading as a person.
    """
    out: list[tuple[ACPDoc, RawDocument]] = []
    for d in witness_statements(case_no):
        rd = fetch(d.url, source_type="acp_witness_statement")
        if rd is None or not rd.content_text.strip():
            continue
        if verify_text and not looks_like_evidence_document(rd.content_text):
            continue
        better = name_from_text(rd.content_text)
        if better:
            d.person_hint = better
        out.append((d, rd))
    return out
