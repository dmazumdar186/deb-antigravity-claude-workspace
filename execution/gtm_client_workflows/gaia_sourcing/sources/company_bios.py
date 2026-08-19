"""
Source plugin: named engineer bios on Irish consultancy websites.

This is the primary source for Role 1 (Senior Structural Engineer). Irish
consultancies publish "our people" / "meet the team" / project pages with
named bios that state chartership, discipline and project history -- far
richer than a LinkedIn search snippet, and fetchable without auth.

SPEC.md section 6 note on LinkedIn: a Serper result gives a page title and
~160 characters of meta description ("John Murphy - Senior Structural
Engineer at RPS Group - Dublin, Ireland | 500+ connections"). You cannot
establish Eurocode competence, chartership or BCAR experience from that.
LinkedIn is used here for DISCOVERY of names only; evidence comes from the
company's own pages.

OFF-LIMITS: TOBIN and AtkinsRealis are the client. Sourcing from the client
is a fireable offence in recruitment, so they are excluded at the firm list
AND re-checked deterministically in the not_client gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

from ..core.cache import fetch, fetch_raw
from ..core.contracts import RawDocument
from .acp import name_from_text
from .oral_hearing_web import serper_search


@dataclass
class Firm:
    slug: str
    name: str
    domain: str
    # Where the people pages tend to live on this site.
    people_paths: list[str] = field(default_factory=list)


# Irish structural / civil consultancies with an Ireland presence.
# TOBIN and AtkinsRealis are deliberately ABSENT -- they are the client.
FIRMS: list[Firm] = [
    Firm("rod", "Roughan & O'Donovan", "rod.ie", ["/about/our-people", "/people"]),
    Firm("punch", "PUNCH Consulting Engineers", "punchconsulting.com", ["/our-team", "/people"]),
    Firm("dbfl", "DBFL Consulting Engineers", "dbfl.ie", ["/our-team", "/about-us"]),
    Firm("waterman_moylan", "Waterman Moylan", "watermanmoylan.ie", ["/our-team", "/people"]),
    Firm("mwp", "Malachy Walsh & Partners", "mwp.ie", ["/our-team", "/people"]),
    Firm("nodwyer", "Nicholas O'Dwyer", "nodwyer.com", ["/our-team", "/people"]),
    Firm("byrne_looby", "Byrne Looby", "byrnelooby.com", ["/our-team", "/people"]),
    Firm("garland", "Garland Consultancy", "garland.ie", ["/our-team", "/people"]),
    Firm("fehily", "Fehily Timoney", "ftco.ie", ["/our-team", "/people"]),
    Firm("barrett_mahony", "Barrett Mahony", "bmce.ie", ["/our-team", "/people"]),
    Firm("cora", "CORA Consulting Engineers", "cora.ie", ["/our-team", "/people"]),
    Firm("rps", "RPS Group Ireland", "rpsgroup.com", ["/our-people"]),
    Firm("arup_ie", "Arup Ireland", "arup.com", ["/our-firm/people"]),
    Firm("jacobs_ie", "Jacobs Ireland", "jacobs.com", ["/about/people"]),
    Firm("oconnor_sutton", "O'Connor Sutton Cronin", "ocsc.ie", ["/our-team", "/people"]),
    Firm("casey_odonnell", "Casey O'Donnell", "caseyodonnell.ie", ["/team"]),
    Firm("clifton_scannell", "Clifton Scannell Emerson", "cseassociates.ie", ["/our-team"]),
    Firm("kmce", "Kavanagh Mansfield", "kmce.ie", ["/team"]),
]

# Firms that must never be sourced from. Checked here AND in gates.not_client.
OFF_LIMITS_FIRMS = ["tobin", "atkinsrealis", "atkins realis", "atkinsréalis"]

_STRUCTURAL_QUERY_TERMS = [
    "senior structural engineer",
    "chartered structural engineer",
    "structural engineer CEng MIEI",
    "associate structural engineer",
]


@dataclass
class BioDoc:
    url: str
    firm: Optional[str]
    person_hint: Optional[str]
    title: str = ""


# A bio page is a page that names a person and states a professional grade.
_BIO_SIGNAL_RE = re.compile(
    r"(ceng|miei|fiei|chartered engineer|chartered structural|"
    r"b\.?eng|m\.?eng|bsc\s*\(eng\)|associate director|senior engineer|"
    r"technical director|structural engineer)",
    re.I,
)

_PERSON_PAGE_RE = re.compile(
    r"/(our-people|people|our-team|team|staff|profile|profiles|"
    r"meet-the-team|directors|leadership)/[a-z0-9][a-z0-9\-]{3,}",
    re.I,
)


def discover_via_search(
    firms: Iterable[Firm] = FIRMS, per_firm: int = 10
) -> list[BioDoc]:
    """Find named engineer bio pages using site-restricted search."""
    out: list[BioDoc] = []
    seen: set[str] = set()
    for firm in firms:
        for term in _STRUCTURAL_QUERY_TERMS[:2]:
            q = 'site:' + firm.domain + ' "' + term + '"'
            for item in serper_search(q, num=per_firm):
                link = item.get("link", "")
                if not link or link in seen:
                    continue
                if any(o in link.lower() for o in OFF_LIMITS_FIRMS):
                    continue
                seen.add(link)
                blob = item.get("title", "") + " " + item.get("snippet", "")
                if not _BIO_SIGNAL_RE.search(blob):
                    continue
                out.append(
                    BioDoc(url=link, firm=firm.name, person_hint=None,
                           title=item.get("title", ""))
                )
    return out


_HREF_RE = re.compile(rb'href\s*=\s*["\']([^"\']+)["\']', re.I)


# Link text / href shapes that indicate a people-index page. Used to DISCOVER
# the index rather than guess its path: hardcoded paths matched only 1 of 18
# firms on the first run, because every CMS names this page differently
# (/team, /our-people, /about/people, /who-we-are, /expertise/our-team...).
_INDEX_HREF_RE = re.compile(
    r"/(our-people|our-team|the-team|meet-the-team|people|team|staff|"
    r"who-we-are|our-experts|leadership|directors|management)"
    r"(/|$|\?)",
    re.I,
)


def find_people_indexes(firm: Firm, limit: int = 6) -> list[str]:
    """Discover a firm's people-index URLs from its homepage navigation."""
    found: list[str] = []
    seen: set[str] = set()
    for base in ("https://www." + firm.domain, "https://" + firm.domain):
        raw = fetch_raw(base)
        if raw is None:
            continue
        for m in _HREF_RE.finditer(raw):
            href = m.group(1).decode("utf-8", errors="replace")
            if not _INDEX_HREF_RE.search(href):
                continue
            url = urljoin(base, href)
            if firm.domain not in urlparse(url).netloc or url in seen:
                continue
            seen.add(url)
            found.append(url)
            if len(found) >= limit:
                return found
        if found:
            return found
    return found


def crawl_people_index(firm: Firm, limit: int = 60) -> list[BioDoc]:
    """Follow a firm's people-index page to individual profile pages."""
    out: list[BioDoc] = []
    seen: set[str] = set()
    base = "https://www." + firm.domain
    index_urls = [base + p for p in firm.people_paths] + find_people_indexes(firm)
    for index_url in index_urls:
        raw = fetch_raw(index_url)
        if raw is None:
            continue
        for m in _HREF_RE.finditer(raw):
            href = m.group(1).decode("utf-8", errors="replace")
            if not _PERSON_PAGE_RE.search(href):
                continue
            url = urljoin(index_url, href)
            # Stay on the firm's own domain: people-index pages link out to
            # LinkedIn, awards bodies and news sites, none of which are bios.
            if firm.domain not in urlparse(url).netloc:
                continue
            low = url.lower()
            # Careers pages are job adverts, not people. The first search-based
            # run returned mostly "senior-structural-engineer" VACANCY pages,
            # which would have entered the pipeline as fake candidates.
            if any(k in low for k in ("/career", "/job", "/vacanc", "/recruit")):
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append(BioDoc(url=url, firm=firm.name, person_hint=None))
            if len(out) >= limit:
                return out
    return out


# On a bio page the name is usually the <h1>/<title>, not inside prose,
# so name_from_text ("my name is ...") rarely fires. Fall back to the URL
# slug, which these CMSes derive from the person's name.
_SLUG_NAME_RE = re.compile(r"/([a-z]+(?:-[a-z]+){1,3})/?$", re.I)
_SLUG_STOP = {
    "our", "people", "team", "staff", "profile", "profiles", "about",
    "contact", "services", "projects", "news", "careers", "index",
    "meet", "the", "directors", "leadership", "engineering", "structural",
}


def _name_from_slug(url: str) -> Optional[str]:
    m = _SLUG_NAME_RE.search(urlparse(url).path)
    if not m:
        return None
    parts = [p for p in m.group(1).split("-") if p]
    if len(parts) < 2 or len(parts) > 4:
        return None
    if any(p.lower() in _SLUG_STOP for p in parts):
        return None
    return " ".join(p.capitalize() for p in parts)


def looks_like_bio(text: str) -> bool:
    """Deterministic gate: does this page read like one person's profile?"""
    if len(text) < 200:
        return False
    if not _BIO_SIGNAL_RE.search(text[:6000]):
        return False
    # A people-INDEX page lists many names and many grades; a profile page
    # concentrates on one. Reject pages with too many distinct grade hits.
    hits = len(_BIO_SIGNAL_RE.findall(text[:20000]))
    return hits <= 40


def harvest(docs: list[BioDoc]) -> list[tuple[BioDoc, RawDocument]]:
    out: list[tuple[BioDoc, RawDocument]] = []
    for d in docs:
        rd = fetch(d.url, source_type="company_bio")
        if rd is None or not rd.content_text.strip():
            continue
        if not looks_like_bio(rd.content_text):
            continue
        d.person_hint = (
            name_from_text(rd.content_text)
            or _name_from_slug(d.url)
            or _name_from_title(rd.title or d.title)
        )
        if not d.person_hint:
            continue
        out.append((d, rd))
    return out


_TITLE_NAME_RE = re.compile(r"^([A-Z][a-z'`\-]+(?:\s+(?:Mac|Mc|O')?[A-Z][a-z'`\-]+){1,2})")


def _name_from_title(title: str) -> Optional[str]:
    if not title:
        return None
    m = _TITLE_NAME_RE.match(title.strip())
    return m.group(1) if m else None
