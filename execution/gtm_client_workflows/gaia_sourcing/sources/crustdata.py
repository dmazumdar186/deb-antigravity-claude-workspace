"""
Source plugin: Crustdata Person Search + Person Enrichment.

description: fetches Irish engineers matching a SourceQuery from Crustdata's
    Person Search API and maps each match into a ProviderRecord + RawDocument
    pair per RADAR_CONTRACTS.md §A.
inputs: SourceQuery (role_id, niche, terms, locations, limit, cursor); env
    var CRUSTDATA_API_KEY (via core.config.secret).
outputs: SourceResult (documents, provider_records, next_cursor, cost_eur,
    fetched). No disk cache (see sources/licensed_common.py docstring).

DOCS READ (WebFetch, 2026-09-10):
  - https://docs.crustdata.com/ (top-level nav)
  - https://docs.crustdata.com/person-docs/search/introduction  (fetched
    twice -- the second fetch returned the page's literal example request/
    response JSON verbatim, which is what the mapping below is built from;
    trust that over the first fetch's paraphrase where the two disagree)
  - https://docs.crustdata.com/person-docs/enrichment/reference

VERIFIED from the docs above:
  - Base URL: https://api.crustdata.com
  - Auth headers (every request): `Authorization: Bearer <CRUSTDATA_API_KEY>`,
    `x-api-version: 2025-11-01`, `content-type: application/json`.
  - Search endpoint: POST /person/search. Required: a `filters` object
    shaped `{"op": "and"|"or", "conditions": [{"field", "type", "value"}]}`
    -- confirmed by the page's own example request, which filters
    `experience.employment_details.title` (.)-contains "Co-Founder" AND
    `basic_profile.location.full_location` (.)-contains "San Francisco".
    Optional: `limit`.
  - Response shape (verbatim example, person "Dipesh Garg", CEO at
    Truelancer -- the docs' own sample, not an invented name):
      {"profiles": [{"crustdata_person_id": 1279,
        "basic_profile": {"name", "headline",
          "location": {"raw","city","state","country","continent"}},
        "social_handles": {"professional_network_identifier":
          {"profile_url": "https://www.linkedin.com/in/..."}},
        "experience": {"employment_details": {
          "current": [{"name": <employer>, "title": <title>}],
          "past": [{"name": <employer>, "title": <title>}]}}}],
       "next_cursor": "...", "total_count": 95577}
    Note the example's `current`/`past` entries carry only `name`/`title`,
    no start_date/end_date -- job_history below reads dates defensively
    (`start_date`/`end_date` if present, per the enrichment reference's
    mention of dated employment_details) but a search-endpoint record may
    legitimately produce a JobStint with both dates None, which
    RADAR_CONTRACTS.md §A's JobStint explicitly allows.
  - There is no separate `title` field on `basic_profile` in the verified
    shape -- only `headline` (a combined "<title> at <employer>" string).
    current_title is read from the first `current` employment entry's
    `title`, falling back to `headline` only if that is absent.
  - Ireland location filter: `basic_profile.location.country` with the same
    `{"field","type","value"}` shape, type `"="` for an exact country match
    (the page's own text, separately from the JSON example, states country
    filtering uses `=`; the JSON example only demonstrates the `(.)`
    contains-type operator on a free-text city filter).
  - Pagination: cursor-based. Response carries `next_cursor`; pass it back
    on the next request. `next_cursor: null` (or absent) means no more
    pages. `total_count` gives the full match count.
  - Search cost: documented as "0.03 credits per result returned" -- i.e.
    per profile in `profiles`, not per query issued.
  - Enrichment endpoint: POST /person/enrich. Required:
    `professional_network_profile_urls` (array, max 25 LinkedIn profile
    URLs per call). Not used by `fetch()` (search-only per the
    coverage-test contract) but documented here for a future
    enrich-by-linkedin_url path.
  - Enrichment cost: "base enrich costs 1 credit per profile" (a
    `social_posts` add-on adds a further flat 5 credits/profile; not used
    here).

UNVERIFIED (WebFetch to marketing/pricing pages returned no rendered
  content -- likely client-side rendered React pages the fetcher's markdown
  conversion cannot see past):
  - USD value of one Crustdata credit (needed to turn "0.03 credits/result"
    into a EUR figure). https://docs.crustdata.com/docs/pricing and
    https://crustdata.com/pricing both failed to render pricing text to the
    fetcher. `_CREDIT_USD` below is a placeholder ($0.01/credit, i.e.
    $0.0003/search-result) -- replace it with the account's actual
    credit-purchase rate from its Crustdata billing page before trusting
    cost_eur for budget decisions.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..core.config import USD_TO_EUR
from ..core.contracts import JobStint, ProviderRecord, RawDocument, SourceQuery, SourceResult
from .licensed_common import _post_json, parse_date, raw_hash, render_content_text, require_key
from .base import SourceProvider, throttle  # noqa: F401  (Protocol; import documents the contract)

BASE_URL = "https://api.crustdata.com"
SEARCH_URL = BASE_URL + "/person/search"
API_VERSION = "2025-11-01"

# UNVERIFIED placeholders -- see module docstring "UNVERIFIED" section.
_CREDIT_USD = 0.01
_SEARCH_CREDITS_PER_RESULT = 0.03


def _build_filters(query: SourceQuery) -> dict:
    conditions: list[dict] = [
        {"field": "basic_profile.location.country", "type": "=", "value": "Ireland"},
    ]
    for loc in query.locations:
        conditions.append(
            {"field": "basic_profile.location.full_location", "type": "(.)", "value": loc}
        )
    for term in query.terms:
        conditions.append(
            {"field": "experience.employment_details.title", "type": "(.)", "value": term}
        )
    return {"op": "and", "conditions": conditions}


def _map_employment(entries: list[dict]) -> list[JobStint]:
    """Map one of `experience.employment_details.current`/`past` -- each
    entry verified as `{"name": <employer>, "title": <title>}`, with no
    guaranteed start_date/end_date on the search endpoint (see module
    docstring). Read defensively: dates are Optional on JobStint precisely
    for records like this.
    """
    out: list[JobStint] = []
    for e in entries or []:
        title = e.get("title")
        employer = e.get("name") or e.get("company") or e.get("company_name")
        if not title and not employer:
            continue
        out.append(
            JobStint(
                title=title,
                employer=employer,
                start=parse_date(e.get("start_date")),
                end=parse_date(e.get("end_date")),
            )
        )
    return out


def _to_record(item: dict) -> ProviderRecord:
    profile = item.get("basic_profile") or {}
    loc = profile.get("location") or {}
    employment = (item.get("experience") or {}).get("employment_details") or {}
    current = employment.get("current") or []
    past = employment.get("past") or []
    job_history = _map_employment(current) + _map_employment(past)

    linkedin_url = (
        (item.get("social_handles") or {}).get("professional_network_identifier") or {}
    ).get("profile_url")

    return ProviderRecord(
        provider="crustdata",
        external_id=str(item.get("crustdata_person_id") or ""),
        full_name=profile.get("name") or "",
        current_title=(current[0].get("title") if current else None) or profile.get("headline"),
        current_employer=current[0].get("name") if current else None,
        city=loc.get("city"),
        region=loc.get("state"),
        country=loc.get("country"),
        job_history=job_history,
        skills=list(profile.get("skills") or item.get("skills") or []),
        linkedin_url=linkedin_url,
        fetched_at=date.today(),
        raw_hash=raw_hash(item),
    )


def _to_document(record: ProviderRecord, item: dict) -> RawDocument:
    url = record.linkedin_url or (SEARCH_URL + ("?id=" + record.external_id if record.external_id else ""))
    if not str(url).startswith("http"):
        url = "https://" + str(url).lstrip("/")
    text = render_content_text(
        [
            ("full_name", record.full_name),
            ("current_title", record.current_title),
            ("current_employer", record.current_employer),
            ("city", record.city),
            ("region", record.region),
            ("country", record.country),
            ("linkedin_url", record.linkedin_url),
            ("skills", record.skills),
        ]
        + [
            (f"job_history[{i}]", f"{js.title} at {js.employer} ({js.start or '?'} - {js.end or 'present'})")
            for i, js in enumerate(record.job_history)
        ]
    )
    return RawDocument(
        doc_id=raw_hash(item),
        url=url,
        source_type="other",
        fetched_at=date.today(),
        content_text=text or (record.full_name or "crustdata record"),
        http_status=200,
        title=record.full_name,
    )


class CrustdataProvider:
    name = "crustdata"
    text_source = "provider_field"
    rate_limit_s = 1.0  # no documented per-second cap found; conservative default

    def _headers(self) -> dict[str, str]:
        api_key = require_key("CRUSTDATA_API_KEY")
        return {
            "Authorization": "Bearer " + api_key,
            "x-api-version": API_VERSION,
            "content-type": "application/json",
        }

    def fetch(self, query: SourceQuery) -> SourceResult:
        headers = self._headers()
        body: dict[str, Any] = {
            "filters": _build_filters(query),
            "limit": max(1, min(query.limit, 100)),
        }
        if query.cursor:
            body["cursor"] = query.cursor

        throttle(self.name, self.rate_limit_s)
        status, payload = _post_json(SEARCH_URL, headers=headers, json_body=body)
        if status != 200:
            return SourceResult(provider=self.name, documents=[], provider_records=[],
                                 next_cursor=None, cost_eur=0.0, fetched=0,
                                 error="HTTP " + str(status))

        items = payload.get("profiles") or []
        records = [_to_record(it) for it in items]
        docs = [_to_document(rec, it) for rec, it in zip(records, items)]
        result = SourceResult(
            provider=self.name,
            documents=docs,
            provider_records=records,
            next_cursor=payload.get("next_cursor"),
            cost_eur=0.0,
            fetched=len(records),
        )
        result.cost_eur = self.cost_eur(result)
        return result

    def cost_eur(self, result: SourceResult) -> float:
        return result.fetched * _SEARCH_CREDITS_PER_RESULT * _CREDIT_USD * USD_TO_EUR


# Registration hook -- see sources/pdl.py's matching comment for why this
# self-registration on import exists.
from .registry import register_provider  # noqa: E402

register_provider(CrustdataProvider())
