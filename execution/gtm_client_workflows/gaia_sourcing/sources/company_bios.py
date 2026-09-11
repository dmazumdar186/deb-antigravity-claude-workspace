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

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests

from ..core.cache import CACHE_DIR, fetch, fetch_raw, url_key
from ..core.config import CONFIG, secret
from ..core.contracts import RawDocument
from .acp import name_from_text
from .base import throttle
from .oral_hearing_web import serper_search


@dataclass
class Firm:
    slug: str
    name: str
    domain: str
    # Where the people pages tend to live on this site.
    people_paths: list[str] = field(default_factory=list)
    # Country the firm is domiciled/headquartered in -- "IE" (indigenous
    # Irish consultancy), "UK", or "INTL" (any other multinational, e.g.
    # US/French/Swedish-owned). Drives run.py's default_location for a
    # person whose directory entry states no office of its own: an
    # IE-domiciled firm's staff directory lists Irish staff by default; a
    # UK/INTL firm's does not, and each person there must evidence Ireland
    # individually or fail the located_ie gate (2026-09-11 widening,
    # RADAR scope update: 250/471 Role 1 people failed located_ie because
    # only the original 16 firms carried a default location at all).
    #
    # Set from firm-specific knowledge where confidently known (see the
    # per-firm comments below); otherwise the deterministic fallback is
    # applied: domicile "IE" only when the domain is .ie AND the firm is an
    # ACEI member (every firm in this list is), else "INTL" with an empty
    # office_cities. An attempt to read city-level detail off ACEI's own
    # 2026 directory PDF (acei.ie) failed this session -- the file exceeds
    # WebFetch's 10MB fetch limit -- so most of the 42 2026-09-11 firms
    # carry the fallback rather than a verified office list; a person from
    # one of those still gets Person.location = "Ireland" (the "several
    # offices" branch), which is enough to pass located_ie's Republic-wide
    # check even though it will not name a specific city.
    domicile: str = "INTL"
    # Known office-city names in Ireland (e.g. ["Dublin"], ["Cork"]).
    # Empty for a domicile != "IE" firm, and also for an IE firm whose exact
    # office count is not confidently known (treated as "several" -- see
    # run.py's _default_location_for_firm).
    office_cities: list[str] = field(default_factory=list)
    # 2026-09-11 adversarial-audit fix: True when this firm ALSO has offices
    # outside the Republic (Northern Ireland or Great Britain) even though it
    # is domiciled "IE" -- O'Connor Sutton Cronin (Dublin/Cork/Galway AND
    # Belfast/Birmingham/London) is the exhibit. A multi-country firm's
    # staff-directory default location is VOID (None): a person there with no
    # stated office could just as easily be in Belfast as in Dublin, so
    # run.py's _default_location_for_firm must never hand them a bare
    # "Ireland" default -- each person must evidence Ireland individually.
    multi_country: bool = False


# Irish structural / civil consultancies with an Ireland presence.
# TOBIN and AtkinsRealis are deliberately ABSENT -- they are the client.
FIRMS: list[Firm] = [
    # Domains and people-paths verified live 2026-08-19. The first version of
    # this list was assembled from firm names and guessed .ie domains; eight of
    # them did not resolve at all (cseassociates.ie, watermanmoylan.ie,
    # garland.ie, ftco.ie, bmce.ie, caseyodonnell.ie, kmce.ie) and one
    # (byrnelooby.com) now redirects to its acquirer Ayesa, whose site carries
    # no per-engineer bios. Guessing a domain from a firm name is not sourcing.
    Firm("rod", "Roughan & O'Donovan", "rod.ie", ["/people", "/about/our-people"], domicile='IE', office_cities=[]),
    Firm("punch", "PUNCH Consulting Engineers", "punchconsulting.com", ["/our-team", "/people"], domicile='IE', office_cities=[]),
    Firm("dbfl", "DBFL Consulting Engineers", "dbfl.ie", ["/about-us/our-team/", "/our-team"], domicile='IE', office_cities=['Dublin']),
    # 2026-09-11 adversarial-audit fix: OCSC also has Belfast, Birmingham and
    # London offices -- domicile stays "IE" (Dublin-headquartered, ACEI
    # member) but multi_country=True voids its default location, since a
    # staff-directory entry with no stated office is not necessarily Irish.
    Firm("oconnor_sutton", "O'Connor Sutton Cronin", "ocsc.ie", ["/people/"], domicile='IE',
         office_cities=['Dublin', 'Cork', 'Galway'], multi_country=True),
    Firm("mwp", "Malachy Walsh & Partners", "mwp.ie", ["/our-team", "/people"], domicile='IE', office_cities=[]),
    Firm("nodwyer", "Nicholas O'Dwyer", "nodwyer.com", ["/our-team", "/people"], domicile='IE', office_cities=[]),
    # Corrected: the firm trades as bmce.ie in print but publishes at
    # barrettmahony.com, where the team index is split by office.
    Firm("barrett_mahony", "Barrett Mahony Consulting Engineers", "barrettmahony.com",
         ["/practice/team/all", "/practice/team/dublin"], domicile='IE', office_cities=[]),
    # Cork-domiciled, which matters for Role 2's Cork location.
    Firm("horganlynch", "Horganlynch", "horganlynch.ie", ["/our-people"], domicile='IE', office_cities=['Cork']),
    Firm("kilgallen", "Kilgallen & Partners", "kilgallen.ie", ["/team"], domicile='IE', office_cities=['Dublin']),
    Firm("tjoc", "TJ O'Connor & Associates", "tjoc.ie", ["/team", "/our-team", "/people"], domicile='IE', office_cities=['Dublin']),
    Firm("cora", "CORA Consulting Engineers", "cora.ie", ["/about"], domicile='IE', office_cities=['Dublin']),
    Firm("downes", "Downes Associates", "downesassociates.ie", ["/team", "/about"], domicile='IE', office_cities=['Dublin']),
    Firm("axis", "Axis Engineering", "axiseng.ie", ["/team", "/about"], domicile='IE', office_cities=['Dublin']),
    # Global firms with an Ireland presence. Their people pages list worldwide
    # staff, so run.py gives them no default location -- each person must
    # evidence Ireland or fail the located_ie gate.
    Firm("rps", "RPS Group Ireland", "rpsgroup.com", ["/our-people"], domicile='INTL', office_cities=[]),
    Firm("arup_ie", "Arup Ireland", "arup.com", ["/our-firm/people"], domicile='UK', office_cities=[]),
    Firm("jacobs_ie", "Jacobs Ireland", "jacobs.com", ["/about/people"], domicile='INTL', office_cities=[]),
    Firm("mottmac_ie", "Mott MacDonald Ireland", "mottmac.com", ["/our-people"], domicile='UK', office_cities=[]),
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
    Firm("bdp", "BDP", "bdp.com", ["/our-people"], domicile='UK', office_cities=[]),
    Firm("ors", "ORS", "ors.ie", ["/people", "/our-people"], domicile='IE', office_cities=['Dublin']),
    Firm("egis", "Egis Ireland", "egis-group.com", ["/our-people"], domicile='INTL', office_cities=[]),
    Firm("ryanhanley", "Ryan Hanley", "ryanhanley.ie", ["/our-team", "/team"], domicile='IE', office_cities=[]),
    Firm("csea", "Clifton Scannell Emerson Associates", "csea.ie", ["/our-people"], domicile='IE', office_cities=[]),
    Firm("fehilytimoney", "Fehily Timoney & Company", "fehilytimoney.ie", ["/our-team"], domicile='IE', office_cities=[]),
    Firm("jodireland", "Jennings O'Donovan & Partners", "jodireland.com",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=['Sligo']),
    Firm("garland", "Garland", "garlandconsultancy.com", ["/team", "/our-team"], domicile='IE', office_cities=[]),
    Firm("amey", "Amey Infrastructure Ireland", "ameygroup.ie",
         ["/our-people", "/people", "/about-us/our-people"], domicile='UK', office_cities=[]),
    # office_cities verified 2026-09-11 from the cached /our-team footer:
    # "DUBLIN HQ: 19-22 Dame Street, Dublin 2" -- the only office listed.
    Firm("csconsulting", "CS Consulting Group", "csconsulting.ie", ["/our-team"], domicile='IE', office_cities=['Dublin']),
    Firm("cundall", "Cundall", "cundall.com", ["/people"], domicile='UK', office_cities=[]),
    Firm("hhp", "Hayes Higgins Partnership", "hhp.ie", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("eireng", "EirEng Consulting Engineers", "eireng.ie", ["/our-team"], domicile='IE', office_cities=[]),
    Firm("gdaly", "GDCL Consulting Engineers", "gdalyconsulting.com",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("c3", "Clandillon Civil Consulting", "c3.ie", ["/team", "/our-team", "/people"], domicile='IE', office_cities=[]),
    Firm("hanleypepper", "Hanley Pepper", "hanleypepper.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("omc", "OMC Group", "omcgroup.ie", ["/team"], domicile='IE', office_cities=[]),
    Firm("doba", "Donnachadh O'Brien & Associates", "doba.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("mea", "MEA Consulting Engineers", "mea.ie", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("muir", "Muir Associates", "muir.ie", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("sds_design", "SDS Design Engineers", "structuraldesign.ie",
         ["/team", "/our-team", "/people"], domicile='IE', office_cities=[]),
    Firm("engenuiti", "Engenuiti", "engenuiti.ie", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("joda", "JODA Engineering Consultants", "joda.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("dfk", "Doherty Finegan Kelly", "dfk.ie", ["/about-us/our-team"], domicile='IE', office_cities=[]),
    Firm("mpa", "Martin Peters Associates", "mpa.ie", ["/team"], domicile='IE', office_cities=[]),
    # 2026-09-11 adversarial-audit fix (item 7): the firm at mhl.ie trades as
    # "MHL & Associates", not "MMA Consulting Engineers" -- the name/domain
    # pairing was wrong (a different firm's name attached to this domain).
    # Slug kept stable ("mma") so nothing downstream keyed on the slug breaks.
    Firm("mma", "MHL & Associates", "mhl.ie", ["/people"], domicile='IE', office_cities=[]),
    Firm("wdg", "Walsh Design Group", "wdg.ie", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("kmp", "Kavanagh Mansfield & Partners", "kmp.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("langan", "Langan Consulting Engineers", "langaneng.ie", ["/about-us/our-team"], domicile='IE', office_cities=[]),
    Firm("molonymillar", "Molony & Millar", "molonymillar.ie", ["/team"], domicile='IE', office_cities=[]),
    Firm("chh", "CHH Consulting Engineers", "chh.ie", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("sweco_ie", "Sweco Ireland", "sweco.ie", ["/our-people", "/people"], domicile='INTL', office_cities=[]),
    Firm("bjs", "BJS Consultants", "bjsconsultants.com",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("civic", "CIVIC Consulting Engineers", "team-civic.com", ["/team"], domicile='IE', office_cities=[]),
    Firm("hughmunro", "Hugh Munro & Co", "hughmunro.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=['Cavan']),
    Firm("mce", "MCE Consulting Engineers", "mceeng.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("mtw", "MTW Consultants", "mtw.ie", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("poga", "POGA Consulting Engineers", "poga.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("furey", "Furey Consulting Engineers", "fureyconsulting.ie", ["/team"], domicile='IE', office_cities=[]),
    Firm("mcullen", "Malachi Cullen Consulting Engineers", "mcullen.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("roadplan", "Roadplan Consulting", "roadplan.ie",
         ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
    Firm("pmce", "PMCE Ltd", "pmceconsultants.com", ["/our-team", "/team", "/people"], domicile='IE', office_cities=[]),
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


# Path shape a discovered link must carry to count as a people page, shared
# by the Serper and Firecrawl-map fallbacks below. Deliberately looser than
# _INDEX_HREF_RE (which anchors on a leading path segment out of homepage
# nav markup): a search/map result's path can put the matching word anywhere
# ("/about/who-we-are/", "/company/leadership-team").
_PEOPLE_PATH_RE = re.compile(
    r"(team|people|staff|leadership|who-we-are|about)", re.I
)


def _filter_people_links(links: Iterable[str], domain: str) -> list[str]:
    out: list[str] = []
    for link in links:
        if not link:
            continue
        parsed = urlparse(link)
        if domain not in parsed.netloc:
            continue
        if not _PEOPLE_PATH_RE.search(parsed.path):
            continue
        out.append(link)
    return out


_SERPER_SEARCH_URL = "https://google.serper.dev/search"


def _serper_site_people_search(domain: str) -> list[dict]:
    """A Serper site: search for a firm's people page.

    Homepage-nav discovery (find_people_indexes) only sees links that are
    plain <a href> markup on the homepage; several CMSes hide the team link
    behind a JS-rendered mega-menu or bury it two levels deep, which is why
    the 2026-09-11 58-firm harvest_r1 run found nothing for most new firms.
    A site-restricted search catches those. Returns [] (never raises) when
    SERPER_API_KEY is absent or the request fails -- discovery must degrade
    a firm's harvest, never kill it, same contract as every other Serper
    caller in this package.
    """
    api_key = secret("SERPER_API_KEY", required=False)
    if not api_key:
        print("[company_bios] SERPER_API_KEY absent: skipping Serper people-page "
              "search for " + domain)
        return []
    query = ('site:' + domain
             + ' (team OR people OR "our people" OR staff OR leadership)')
    throttle("company_bios_serper", 1.0)
    try:
        req = urllib.request.Request(
            _SERPER_SEARCH_URL,
            data=json.dumps({"q": query, "num": 10, "gl": "ie"}).encode("utf-8"),
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=CONFIG.request_timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return data.get("organic", []) or []
    except Exception as exc:
        print("[company_bios] Serper site search failed for " + domain + ": "
              + repr(exc)[:120])
        return []


_FIRECRAWL_MAP_URL = "https://api.firecrawl.dev/v2/map"


def _firecrawl_map(domain: str) -> list[str]:
    """Last-resort discovery: Firecrawl v2 /map enumerates a site's URLs
    ordered by relevance to a search term, without fetching any page content
    (cheaper than a render -- one credit regardless of site size, verified
    against https://docs.firecrawl.dev/api-reference/endpoint/map 2026-09-11:
    request {"url": ..., "search": ...}, response
    {"success": bool, "links": [{"url": ..., "title": ..., "description": ...}]}).

    Cached under run/_httpcache under a synthetic key -- map is a POST with a
    JSON body, not a GET on a stable URL, so it cannot share core.cache.fetch's
    cache slot -- so a firm is never mapped more than once even across reruns.
    A cached empty result (no key, or the call failed) is intentional: without
    it, a firm with no reachable people page would re-spend a Firecrawl credit
    on every run.
    """
    api_key = secret("FIRECRAWL_API_KEY", required=False)
    if not api_key:
        return []
    base = "https://www." + domain
    meta_p = CACHE_DIR / (url_key("MAP::" + base + "::people team staff") + ".map.json")
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("[company_bios] unreadable map cache for " + domain + ": "
                  + repr(exc)[:80])
            return []
        return meta.get("links", [])

    urls: list[str] = []
    try:
        resp = requests.post(
            _FIRECRAWL_MAP_URL,
            json={"url": base, "search": "people team staff"},
            headers={"Authorization": "Bearer " + api_key},
            timeout=60,
        )
        payload = resp.json() if resp.status_code == 200 else {}
        for item in payload.get("links") or []:
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
            elif isinstance(item, str):
                urls.append(item)
    except Exception as exc:
        # Logged, not swallowed (python-hardening rule 5) -- and still cached
        # as an empty result below so a flaky Firecrawl call does not get
        # retried (and re-billed) on every subsequent run.
        print("[company_bios] Firecrawl map failed for " + domain + ": "
              + repr(exc)[:120])

    with open(meta_p, "w", encoding="utf-8") as fh:
        json.dump({"ok": True, "links": urls}, fh)
    return urls


def discover_people_urls(firm: Firm, limit: int = 4) -> list[str]:
    """Discover a firm's people-page URL(s), widest/cheapest funnel first.

    Order, de-duped, first-found-wins: homepage-nav discovery
    (find_people_indexes) -> a Serper site-restricted search -> a Firecrawl
    v2 map (last resort -- it spends a Firecrawl credit even when it finds
    nothing) -> the hardcoded guessed people_paths, kept as the final
    fallback rather than dropped, since a handful of firms' guessed paths
    are correct and nav discovery alone missed them.

    Built 2026-09-11: a 58-firm harvest_r1 run yielded pages from only 7
    firms because homepage-nav discovery found nothing for most of the new
    firms and 108 guessed team URLs 404'd.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def _add_all(candidates: Iterable[str]) -> None:
        for u in candidates:
            if u and u not in seen:
                seen.add(u)
                urls.append(u)

    _add_all(find_people_indexes(firm, limit=limit))
    if len(urls) >= limit:
        return urls[:limit]

    serper_links = _filter_people_links(
        (item.get("link", "") for item in _serper_site_people_search(firm.domain)),
        firm.domain,
    )
    _add_all(serper_links)
    if len(urls) >= limit:
        return urls[:limit]

    map_links = _filter_people_links(_firecrawl_map(firm.domain), firm.domain)
    _add_all(map_links)
    if len(urls) >= limit:
        return urls[:limit]

    guessed = ["https://www." + firm.domain + p for p in firm.people_paths]
    _add_all(guessed)

    return urls[:limit]


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
