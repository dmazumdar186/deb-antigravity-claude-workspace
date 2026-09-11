"""
Source plugin: free people-discovery via Serper (Google) web search.

description: builds `"<term>" "<location>" site:linkedin.com/in`-shaped
    queries from a SourceQuery (plus a chartership variant and a
    "Chartered Engineer" variant per term x location), runs them through
    Serper's free web-search API, and maps each organic result into a
    ProviderRecord + RawDocument pair per RADAR_CONTRACTS.md section A.
inputs: SourceQuery (role_id, niche, terms, locations, limit, cursor); env
    var SERPER_API_KEY (via core.config.secret / sources.licensed_common.
    require_key).
outputs: SourceResult (documents, provider_records, cost_eur=0.0, fetched,
    error). No files written; no disk cache -- a live SERP is exactly as
    time-sensitive as the licensed providers' own live queries (see
    sources/licensed_common.py's module docstring on why those are not
    cached), so this plugin does not cache either even though it costs
    nothing to re-run.

DISCOVERY ONLY -- never a LinkedIn fetch
-----------------------------------------
This plugin registers "serper_people" as `text_source = "provider_field"`:
every claim it can support comes from the Serper RESULT (title + snippet),
never from opening the LinkedIn page itself. sources/company_bios.py's
module docstring states the same rule for the discovery use of LinkedIn on
Role 1 ("LinkedIn is used here for DISCOVERY of names only; evidence comes
from the company's own pages" -- SPEC.md section 6) and RADAR_CONTRACTS.md
section A's I8 invariant is the same shape applied to this provider: a
Serper title/snippet gives a name, a title, an employer guess and a rough
location -- never chartership, Eurocode competence or project history, and
this module never calls `fetch`/`fetch_raw`/urlopen against a
linkedin.com/* URL to try to get more. `grep -n "linkedin.com" sources/
serper_people.py` should show query strings and the one profile-URL regex
only, never a fetch call.

Free-plan constraints (verified 2026-09-10, same finding as
sources/linkedin_lookup.py and sources/oral_hearing_web.py):
  - POST https://google.serper.dev/search, header X-API-KEY, JSON body.
  - `num` capped at 10 on the free plan -- always requested as exactly 10
    here, never a caller-supplied value.
  - No pagination on the free plan (no `page`/cursor param that does
    anything) -- `next_cursor` is always None; only page 1 of each query is
    read.
  - `gl`/`hl` ("ie"/"en") bias results toward the Irish Google index, same
    as any other Serper caller in this package could add but none needed
    yet (their queries are already site:-restricted enough not to need it).

Parsing a Serper organic result
--------------------------------
Serper gives no structured person fields, only the two strings Google shows
in a snippet:
  - `title` is usually `"Name - Title - Company | LinkedIn"` or the en-dash
    form `"Name - Title at Company"`; sometimes just `"Name | LinkedIn"`
    with no title/company at all.
  - `snippet` sometimes carries a `"Location: <place>"` fragment, or a bare
    place name, or an experience/years fragment this module does not use
    (job_history / years is a PDL-shaped, licensed-record field this free
    result cannot support).
`_parse_title` and `_parse_location` below are heuristic string splitting,
not NLP -- a title/snippet shaped differently than the patterns seen in the
Serper results collected for this build passes through with whatever it can
recover (full_name always required; a Serper result with no readable name at
all is dropped rather than emitted as a blank record).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date
from typing import Optional

from ..core.config import CONFIG
from ..core.contracts import ProviderRecord, RawDocument, SourceQuery, SourceResult
from .base import throttle
from .licensed_common import raw_hash, require_key

SEARCH_URL = "https://google.serper.dev/search"

# Only a genuine profile page counts as a de-dup key / external_id -- the
# same guard sources/linkedin_lookup.py uses so a company page, a search
# results page, or a slide deck that happens to rank never becomes a
# "person" record.
_PROFILE_RE = re.compile(r"^https?://([a-z]{2}\.)?linkedin\.com/in/[^/?#]+", re.I)

# Irish counties (Republic + Northern Ireland, since a candidate's LinkedIn
# location line does not respect the border) for bare-token location
# parsing. Not exhaustive of every place name Ireland has, but the token an
# Irish LinkedIn snippet actually uses is almost always the county.
_IE_COUNTIES = [
    "Dublin", "Cork", "Galway", "Limerick", "Waterford", "Kildare", "Meath",
    "Wicklow", "Kilkenny", "Louth", "Kerry", "Clare", "Mayo", "Donegal",
    "Wexford", "Laois", "Offaly", "Tipperary", "Sligo", "Leitrim",
    "Roscommon", "Longford", "Westmeath", "Carlow", "Cavan", "Monaghan",
    "Fermanagh", "Tyrone", "Derry", "Antrim", "Down", "Armagh",
]
_COUNTY_RE = re.compile(r"\bCounty\s+([A-Z][A-Za-z]+)\b")
_CITY_IRELAND_RE = re.compile(r"\b([A-Z][A-Za-z]+),\s*Ireland\b")
_BARE_COUNTY_RE = {c: re.compile(r"\b" + re.escape(c) + r"\b") for c in _IE_COUNTIES}
_IRELAND_RE = re.compile(r"\bIreland\b")


def _parse_location(snippet: str) -> tuple[Optional[str], Optional[str]]:
    """(city, country) parsed out of a Serper snippet.

    "Cork" -> ("Cork", "IE"); "County Kerry" -> ("Kerry", "IE");
    "Dublin, Ireland" -> ("Dublin", "IE"); "Ireland" alone (no place named)
    -> (None, "IE"); nothing Irish -> (None, None).
    """
    if not snippet:
        return None, None
    m = _COUNTY_RE.search(snippet)
    if m and m.group(1) in _IE_COUNTIES:
        return m.group(1), "IE"
    m = _CITY_IRELAND_RE.search(snippet)
    if m:
        return m.group(1), "IE"
    for county, pattern in _BARE_COUNTY_RE.items():
        if pattern.search(snippet):
            return county, "IE"
    if _IRELAND_RE.search(snippet):
        return None, "IE"
    return None, None


_DASH_SPLIT_RE = re.compile(r"\s+[-–—]\s+")  # hyphen, en-dash, em-dash
_TRAILING_LINKEDIN_RE = re.compile(r"\s*\|\s*LinkedIn\s*$", re.I)
_TITLE_AT_EMPLOYER_RE = re.compile(r"^(.*?)\s+at\s+(.*)$", re.I)


def _parse_title(title: str) -> tuple[str, Optional[str], Optional[str]]:
    """(full_name, current_title, current_employer) out of a Serper title.

    "Name - Senior Structural Engineer - DBFL | LinkedIn" -> title/employer
    read off the second/third dash-separated segment; "Name - Associate
    Director at Arup" -> the one segment after the name is split on " at ";
    "Name | LinkedIn" -> title/employer both None.
    """
    t = _TRAILING_LINKEDIN_RE.sub("", title or "").strip()
    parts = [p.strip() for p in _DASH_SPLIT_RE.split(t) if p.strip()]
    if not parts:
        return "", None, None
    full_name = parts[0]
    if len(parts) >= 3:
        return full_name, parts[1], parts[2]
    if len(parts) == 2:
        m = _TITLE_AT_EMPLOYER_RE.match(parts[1])
        if m:
            return full_name, m.group(1).strip(), m.group(2).strip()
        return full_name, parts[1], None
    return full_name, None, None


def _clean_link(link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    link = link.split("?")[0].rstrip("/")
    if not _PROFILE_RE.match(link):
        return None
    return link


def _build_queries(term: str, location: str) -> list[str]:
    base = f'"{term}" "{location}" site:linkedin.com/in'
    chartership = f'"{term}" "{location}" ("CEng" OR "MIEI") site:linkedin.com/in'
    chartered_engineer = f'"{term}" "{location}" "Chartered Engineer" site:linkedin.com/in'
    return [base, chartership, chartered_engineer]


def _serper_search(query: str, api_key: str) -> tuple[int, list[dict]]:
    """One Serper query. Returns (http_status, organic_results).

    http_status 0 means the request never got an HTTP response at all
    (network/parse failure) -- treated the same as any other non-200 by the
    caller. Never raises: a search outage degrades this provider's coverage,
    it must not kill the run (same contract as sources/oral_hearing_web.py's
    serper_search).
    """
    try:
        req = urllib.request.Request(
            SEARCH_URL,
            data=json.dumps({"q": query, "num": 10, "gl": "ie", "hl": "en"}).encode("utf-8"),
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=CONFIG.request_timeout_s) as resp:
            status = resp.getcode() or 200
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return status, (data.get("organic") or [])
    except urllib.error.HTTPError as exc:
        print("[serper_people] HTTP " + str(exc.code) + " for query: " + query[:80])
        return exc.code, []
    except Exception as exc:
        print("[serper_people] search failed for " + query[:80] + ": " + repr(exc)[:120])
        return 0, []


def _to_record(item: dict, link: str) -> Optional[ProviderRecord]:
    title = item.get("title") or ""
    snippet = item.get("snippet") or ""
    full_name, current_title, current_employer = _parse_title(title)
    if not full_name:
        return None
    city, country = _parse_location(snippet)
    return ProviderRecord(
        provider="serper_people",
        external_id=link,
        full_name=full_name,
        current_title=current_title,
        current_employer=current_employer,
        city=city,
        region=None,
        country=country,
        job_history=[],
        skills=[],
        linkedin_url=link,
        fetched_at=date.today(),
        raw_hash=raw_hash({"title": title, "snippet": snippet, "link": link}),
    )


def _to_document(item: dict, link: str) -> RawDocument:
    title = item.get("title") or ""
    snippet = item.get("snippet") or ""
    # Exact shape the quote validator (layers/validator.py) checks a claim's
    # evidence_quote against -- never reorder/relabel these three lines.
    content_text = f"title: {title}\nsnippet: {snippet}\nurl: {link}"
    return RawDocument(
        doc_id=raw_hash({"title": title, "snippet": snippet, "url": link}),
        url=link,
        # "search_snippet" (core/contracts.py's SourceType, appended
        # 2026-09-11) rather than "linkedin_snippet": this is a Serper
        # result, not a LinkedIn fetch (see the DISCOVERY ONLY section above)
        # -- generic to any search-engine-result source, which is what
        # layers/extract.py's snippet-specific extraction instructions key
        # off of.
        source_type="search_snippet",
        fetched_at=date.today(),
        content_text=content_text,
        http_status=200,
        title=title or None,
    )


class SerperPeopleProvider:
    name = "serper_people"
    # Every claim this provider supports is a rendered field of the Serper
    # result itself (title/snippet), never the document's own text layer --
    # see the module docstring's "DISCOVERY ONLY" section.
    text_source = "provider_field"
    rate_limit_s = 1.0

    def fetch(self, query: SourceQuery) -> SourceResult:
        api_key = require_key("SERPER_API_KEY")

        terms = query.terms or [query.niche]
        locations = query.locations or [""]

        seen: set[str] = set()
        records: list[ProviderRecord] = []
        documents: list[RawDocument] = []
        queries_run = 0
        error_statuses: list[int] = []

        for term in terms:
            for location in locations:
                for q in _build_queries(term, location):
                    throttle(self.name, self.rate_limit_s)
                    queries_run += 1
                    status, organic = _serper_search(q, api_key)
                    if status != 200:
                        error_statuses.append(status)
                        continue
                    for item in organic:
                        link = _clean_link(item.get("link"))
                        if not link or link in seen:
                            continue
                        record = _to_record(item, link)
                        if record is None:
                            continue
                        seen.add(link)
                        records.append(record)
                        documents.append(_to_document(item, link))

        if not records and queries_run and len(error_statuses) == queries_run:
            # Every single query failed (e.g. an expired key returning 401
            # on all of them) -- distinguishable from "genuinely matched
            # nobody" (fetched=0, error=None), same rationale as
            # sources/pdl.py's non-200 handling.
            return SourceResult(
                provider=self.name, documents=[], provider_records=[],
                next_cursor=None, cost_eur=0.0, fetched=0,
                error="HTTP " + str(error_statuses[0]),
            )

        records = records[: query.limit]
        documents = documents[: query.limit]
        return SourceResult(
            provider=self.name,
            documents=documents,
            provider_records=records,
            next_cursor=None,
            cost_eur=0.0,
            fetched=len(records),
        )

    def cost_eur(self, result: SourceResult) -> float:
        # Serper's free plan: always zero, regardless of how many queries
        # this fetch() call made.
        return 0.0


# Registration hook -- same pattern as sources/pdl.py: registry.py
# deliberately does not import this module (it may not exist at
# registry-import time), so importing sources.serper_people at least once
# per process (run.py's --coverage-test path, or any caller that needs it)
# is what makes "serper_people" resolvable via sources.registry.get_provider.
from .registry import register_provider  # noqa: E402

register_provider(SerperPeopleProvider())
