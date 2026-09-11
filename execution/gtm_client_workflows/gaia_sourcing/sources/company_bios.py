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
    # Domains and people-paths verified live 2026-08-19. The first version of
    # this list was assembled from firm names and guessed .ie domains; eight of
    # them did not resolve at all (cseassociates.ie, watermanmoylan.ie,
    # garland.ie, ftco.ie, bmce.ie, caseyodonnell.ie, kmce.ie) and one
    # (byrnelooby.com) now redirects to its acquirer Ayesa, whose site carries
    # no per-engineer bios. Guessing a domain from a firm name is not sourcing.
    Firm("rod", "Roughan & O'Donovan", "rod.ie", ["/people", "/about/our-people"]),
    Firm("punch", "PUNCH Consulting Engineers", "punchconsulting.com", ["/our-team", "/people"]),
    Firm("dbfl", "DBFL Consulting Engineers", "dbfl.ie", ["/about-us/our-team/", "/our-team"]),
    Firm("oconnor_sutton", "O'Connor Sutton Cronin", "ocsc.ie", ["/people/"]),
    Firm("mwp", "Malachy Walsh & Partners", "mwp.ie", ["/our-team", "/people"]),
    Firm("nodwyer", "Nicholas O'Dwyer", "nodwyer.com", ["/our-team", "/people"]),
    # Corrected: the firm trades as bmce.ie in print but publishes at
    # barrettmahony.com, where the team index is split by office.
    Firm("barrett_mahony", "Barrett Mahony Consulting Engineers", "barrettmahony.com",
         ["/practice/team/all", "/practice/team/dublin"]),
    # Cork-domiciled, which matters for Role 2's Cork location.
    Firm("horganlynch", "Horganlynch", "horganlynch.ie", ["/our-people"]),
    Firm("kilgallen", "Kilgallen & Partners", "kilgallen.ie", ["/team"]),
    Firm("tjoc", "TJ O'Connor & Associates", "tjoc.ie", ["/team", "/our-team", "/people"]),
    Firm("cora", "CORA Consulting Engineers", "cora.ie", ["/about"]),
    Firm("downes", "Downes Associates", "downesassociates.ie", ["/team", "/about"]),
    Firm("axis", "Axis Engineering", "axiseng.ie", ["/team", "/about"]),
    # Global firms with an Ireland presence. Their people pages list worldwide
    # staff, so run.py gives them no default location -- each person must
    # evidence Ireland or fail the located_ie gate.
    Firm("rps", "RPS Group Ireland", "rpsgroup.com", ["/our-people"]),
    Firm("arup_ie", "Arup Ireland", "arup.com", ["/our-firm/people"]),
    Firm("jacobs_ie", "Jacobs Ireland", "jacobs.com", ["/about/people"]),
    Firm("mottmac_ie", "Mott MacDonald Ireland", "mottmac.com", ["/our-people"]),
    # -------------------------------------------------------------------
    # Widened 2026-09-11 from the ACEI (Association of Consulting Engineers
    # of Ireland) 2026 Annual Review & Directory of Members
    # (https://www.acei.ie/wp-content/uploads/2026/06/ACEI_2026-p1-176-complete-v2.pdf,
    # linked from https://www.acei.ie -> "2026 ACEI Directory & Review"),
    # cross-checked against ACEI's "Find a Consulting Engineer" page
    # (https://www.acei.ie/what-is-a-consulting-engineer/find-a-consulting-engineer/,
    # JS-rendered, no static member list -- could not be read directly) and
    # Engineers Ireland's Corporate Partners page
    # (https://www.engineersireland.ie/Businesses/Engage-with-our-community/Corporate-Partner/Our-Partners,
    # 301-redirects and is also JS-rendered -- could not be read directly).
    # Selected every ACEI member whose listed "Engineering Activities" names
    # Civil, Structural, or Transport/Highway/Road work and whose directory
    # entry states 8+ total employees (large enough to plausibly carry a
    # Senior Engineer -> Associate grade ladder), domain resolution checked
    # with plain `requests` (15s timeout). TOBIN and AtkinsRealis (also ACEI
    # members) are excluded as the client. Six ACEI-listed domains that
    # resolved but failed TLS/HTTP verification during this pass are
    # deliberately OMITTED rather than guessed past, per the domain-guessing
    # lesson above: maloneoregan.ie (TLS reset), dkp.ie (self-signed cert),
    # ffaeng.com (cert does not cover the www host), jjc.ie (HTTP 500),
    # cspringle.com (10-person firm, no people path found), tetratech.com
    # (global domain for RPS's post-acquisition brand, 403-blocked, and RPS
    # Ireland is already covered above via rpsgroup.com). people_paths below
    # are the best candidate paths; several returned 200 directly (checked),
    # the rest are unverified guesses for find_people_indexes() to confirm
    # via homepage-nav discovery, since a handful of hosts (ameygroup.ie,
    # bjsconsultants.com, hughmunro.ie, roadplan.ie) return 403/406 to a
    # plain requests fetch and need find_people_indexes'/fetch's real
    # browser-like headers to get past the block.
    Firm("bdp", "BDP", "bdp.com", ["/our-people"]),
    Firm("ors", "ORS", "ors.ie", ["/people", "/our-people"]),
    Firm("egis", "Egis Ireland", "egis-group.com", ["/our-people"]),
    Firm("ryanhanley", "Ryan Hanley", "ryanhanley.ie", ["/our-team", "/team"]),
    Firm("csea", "Clifton Scannell Emerson Associates", "csea.ie", ["/our-people"]),
    Firm("fehilytimoney", "Fehily Timoney & Company", "fehilytimoney.ie", ["/our-team"]),
    Firm("jodireland", "Jennings O'Donovan & Partners", "jodireland.com",
         ["/our-team", "/team", "/people"]),
    Firm("garland", "Garland", "garlandconsultancy.com", ["/team", "/our-team"]),
    Firm("amey", "Amey Infrastructure Ireland", "ameygroup.ie",
         ["/our-people", "/people", "/about-us/our-people"]),
    Firm("csconsulting", "CS Consulting Group", "csconsulting.ie", ["/our-team"]),
    Firm("cundall", "Cundall", "cundall.com", ["/people"]),
    Firm("hhp", "Hayes Higgins Partnership", "hhp.ie", ["/our-team", "/team", "/people"]),
    Firm("eireng", "EirEng Consulting Engineers", "eireng.ie", ["/our-team"]),
    Firm("gdaly", "GDCL Consulting Engineers", "gdalyconsulting.com",
         ["/our-team", "/team", "/people"]),
    Firm("c3", "Clandillon Civil Consulting", "c3.ie", ["/team", "/our-team", "/people"]),
    Firm("hanleypepper", "Hanley Pepper", "hanleypepper.ie",
         ["/our-team", "/team", "/people"]),
    Firm("omc", "OMC Group", "omcgroup.ie", ["/team"]),
    Firm("doba", "Donnachadh O'Brien & Associates", "doba.ie",
         ["/our-team", "/team", "/people"]),
    Firm("mea", "MEA Consulting Engineers", "mea.ie", ["/our-team", "/team", "/people"]),
    Firm("muir", "Muir Associates", "muir.ie", ["/our-team", "/team", "/people"]),
    Firm("sds_design", "SDS Design Engineers", "structuraldesign.ie",
         ["/team", "/our-team", "/people"]),
    Firm("engenuiti", "Engenuiti", "engenuiti.ie", ["/our-team", "/team", "/people"]),
    Firm("joda", "JODA Engineering Consultants", "joda.ie",
         ["/our-team", "/team", "/people"]),
    Firm("dfk", "Doherty Finegan Kelly", "dfk.ie", ["/about-us/our-team"]),
    Firm("mpa", "Martin Peters Associates", "mpa.ie", ["/team"]),
    Firm("mma", "MMA Consulting Engineers", "mhl.ie", ["/people"]),
    Firm("wdg", "Walsh Design Group", "wdg.ie", ["/our-team", "/team", "/people"]),
    Firm("kmp", "Kavanagh Mansfield & Partners", "kmp.ie",
         ["/our-team", "/team", "/people"]),
    Firm("langan", "Langan Consulting Engineers", "langaneng.ie", ["/about-us/our-team"]),
    Firm("molonymillar", "Molony & Millar", "molonymillar.ie", ["/team"]),
    Firm("chh", "CHH Consulting Engineers", "chh.ie", ["/our-team", "/team", "/people"]),
    Firm("sweco_ie", "Sweco Ireland", "sweco.ie", ["/our-people", "/people"]),
    Firm("bjs", "BJS Consultants", "bjsconsultants.com",
         ["/our-team", "/team", "/people"]),
    Firm("civic", "CIVIC Consulting Engineers", "team-civic.com", ["/team"]),
    Firm("hughmunro", "Hugh Munro & Co", "hughmunro.ie",
         ["/our-team", "/team", "/people"]),
    Firm("mce", "MCE Consulting Engineers", "mceeng.ie",
         ["/our-team", "/team", "/people"]),
    Firm("mtw", "MTW Consultants", "mtw.ie", ["/our-team", "/team", "/people"]),
    Firm("poga", "POGA Consulting Engineers", "poga.ie",
         ["/our-team", "/team", "/people"]),
    Firm("furey", "Furey Consulting Engineers", "fureyconsulting.ie", ["/team"]),
    Firm("mcullen", "Malachi Cullen Consulting Engineers", "mcullen.ie",
         ["/our-team", "/team", "/people"]),
    Firm("roadplan", "Roadplan Consulting", "roadplan.ie",
         ["/our-team", "/team", "/people"]),
    Firm("pmce", "PMCE Ltd", "pmceconsultants.com", ["/our-team", "/team", "/people"]),
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
