"""
Source plugin: People Data Labs (PDL) Person Search + Person Enrichment.

description: fetches Irish engineers matching a SourceQuery from PDL's
    Person Search API and maps each match into a ProviderRecord + RawDocument
    pair per RADAR_CONTRACTS.md §A.
inputs: SourceQuery (role_id, niche, terms, locations, limit, cursor); env
    var PDL_API_KEY (via core.config.secret).
outputs: SourceResult (documents, provider_records, next_cursor, cost_eur,
    fetched). No files written; no disk cache (see sources/licensed_common.py
    module docstring for why licensed-provider responses are not cached).

DOCS READ (WebFetch, 2026-09-10):
  - https://docs.peopledatalabs.com/docs/reference-person-search-api
  - https://docs.peopledatalabs.com/docs/input-parameters-person-search-api
  - https://docs.peopledatalabs.com/docs/quickstart-person-search-api
  - https://docs.peopledatalabs.com/docs/reference-person-enrichment-api
  - https://docs.peopledatalabs.com/docs/fields (Person Schema field names)

VERIFIED from the docs above:
  - Base URL: https://api.peopledatalabs.com
  - Search endpoint: POST /v5/person/search  (also documented as callable
    via GET with a raw body in their curl example; POST is used here for
    consistency with Crustdata/Apollo and because the reference page states
    POST as the method).
  - Enrich endpoint: GET/POST /v5/person/enrich (used here as POST, body
    holding the identifying params -- PDL's own quickstart curl passes a
    JSON body on a GET request, which `requests` supports but is unusual;
    POST is functionally identical for this API and clearer to read).
  - Auth header: `X-Api-Key: <PDL_API_KEY>` (also accepted as `api_key` body
    param -- header form used here so the key is never itself part of a
    logged/cached request body).
  - Person Search required param: one of `query` (Elasticsearch v7.7 DSL) or
    `sql`. This module uses `query`.
  - Location/country filter for Ireland: term-match on `location_country`
    (lowercased, e.g. "ireland"); county/region filter via `location_region`
    (also lowercased, e.g. "county dublin", "dublin"). Both are Person Schema
    fields per /docs/fields.
  - Pagination: response includes `scroll_token`; pass it back as
    `scroll_token` on the next request to continue. `size` is 1-100 per
    request (default 1); `from`-based offset pagination is deprecated and
    capped at 9999, not used here.
  - Rate limit: "current default rate limit is 10 requests per minute" per
    the reference page -- SourceProvider.rate_limit_s is set to 6.0s
    accordingly (60s / 10 = 6s between calls).
  - Job history: Person Schema's flattened `job_title` / `job_company_name`
    describe the CURRENT role only; full history lives in the nested
    `experience` array, each entry carrying `company.name`, `title.name`,
    `start_date`, `end_date` -- mapped to ProviderRecord.job_history below.
  - Enrichment required params: one of `profile`/`email`/`phone`/
    `email_hash`/`lid`/`pdl_id`, OR (`first_name`+`last_name` or `name`) PLUS
    one of (`locality`/`region`/`company`/`school`/`location`/`postal_code`).
    Not used by `fetch()` (search-only per the coverage-test contract) but
    documented here for a future enrich-by-linkedin_url path.

UNVERIFIED (WebFetch on the marketing/pricing pages returned only the page
  title -- likely client-rendered; https://docs.peopledatalabs.com/docs/pricing
  redirects to https://www.peopledatalabs.com/pricing, which did not render
  numeric pricing to the fetcher):
  - Exact USD-per-record price for Search and per-match price for Enrichment.
    The reference page confirms Search is "charged per record retrieved from
    the data array" and Enrichment is "charged per successful match (200
    responses only)" but states no number. PDL's publicly-cited standard-tier
    range (industry reporting, not the docs themselves) is roughly
    $0.01-0.05/record for Search and $0.05-0.20/match for Enrichment
    depending on plan and volume. This module uses the LOW end of that range
    as a conservative placeholder -- it will under-count real spend if the
    account's actual contracted rate is higher. Replace
    `_SEARCH_COST_USD_PER_RECORD` below with the account's real per-record
    rate from its PDL invoice/plan page before trusting cost_eur for budget
    decisions.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from ..core.contracts import JobStint, ProviderRecord, RawDocument, SourceQuery, SourceResult
from .licensed_common import _post_json, parse_date, raw_hash, render_content_text, require_key
from .base import SourceProvider  # noqa: F401  (Protocol; import documents the contract)

BASE_URL = "https://api.peopledatalabs.com"
SEARCH_URL = BASE_URL + "/v5/person/search"

# UNVERIFIED placeholder -- see module docstring "UNVERIFIED" section.
_SEARCH_COST_USD_PER_RECORD = 0.01


def _location_query(locations: list[str]) -> Optional[dict]:
    if not locations:
        return None
    return {
        "bool": {
            "should": [
                {"term": {"location_region": loc.strip().lower()}} for loc in locations
            ],
            "minimum_should_match": 1,
        }
    }


def _build_query(query: SourceQuery) -> dict:
    must: list[dict] = [{"term": {"location_country": "ireland"}}]
    loc_q = _location_query(query.locations)
    if loc_q:
        must.append(loc_q)
    should = [{"match_phrase": {"job_title": t}} for t in query.terms]
    body: dict[str, Any] = {
        "bool": {
            "must": must,
            "should": should,
            "minimum_should_match": 1 if should else 0,
        }
    }
    return body


def _map_experience(raw_exp: list[dict]) -> list[JobStint]:
    out: list[JobStint] = []
    for e in raw_exp or []:
        title = ((e.get("title") or {}).get("name")) if isinstance(e.get("title"), dict) else e.get("title")
        company = ((e.get("company") or {}).get("name")) if isinstance(e.get("company"), dict) else e.get("company")
        if not title and not company:
            continue
        out.append(
            JobStint(
                title=title,
                employer=company,
                start=parse_date(e.get("start_date")),
                end=parse_date(e.get("end_date")),
            )
        )
    return out


def _linkedin_url(item: dict) -> Optional[str]:
    url = item.get("linkedin_url")
    if not url:
        return None
    url = str(url)
    if not url.startswith("http"):
        url = "https://" + url.lstrip("/")
    return url


def _to_record(item: dict) -> ProviderRecord:
    external_id = str(item.get("id") or "")
    job_history = _map_experience(item.get("experience") or [])
    return ProviderRecord(
        provider="pdl",
        external_id=external_id,
        full_name=item.get("full_name") or "",
        current_title=item.get("job_title"),
        current_employer=item.get("job_company_name"),
        city=item.get("location_locality"),
        region=item.get("location_region"),
        country=item.get("location_country"),
        job_history=job_history,
        skills=list(item.get("skills") or []),
        linkedin_url=_linkedin_url(item),
        fetched_at=date.today(),
        raw_hash=raw_hash(item),
    )


def _to_document(record: ProviderRecord, item: dict) -> RawDocument:
    url = SEARCH_URL + ("?id=" + record.external_id if record.external_id else "")
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
        content_text=text or (record.full_name or "pdl record"),
        http_status=200,
        title=record.full_name,
    )


class PDLProvider:
    name = "pdl"
    text_source = "provider_field"
    rate_limit_s = 6.0  # 10 req/min documented default -> 6s between calls

    def fetch(self, query: SourceQuery) -> SourceResult:
        api_key = require_key("PDL_API_KEY")
        body: dict[str, Any] = {
            "query": _build_query(query),
            "size": max(1, min(query.limit, 100)),
        }
        if query.cursor:
            body["scroll_token"] = query.cursor

        status, payload = _post_json(
            SEARCH_URL,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            json_body=body,
        )
        if status != 200:
            return SourceResult(provider=self.name, documents=[], provider_records=[],
                                 next_cursor=None, cost_eur=0.0, fetched=0)

        items = payload.get("data") or []
        records = [_to_record(it) for it in items]
        docs = [_to_document(rec, it) for rec, it in zip(records, items)]
        result = SourceResult(
            provider=self.name,
            documents=docs,
            provider_records=records,
            next_cursor=payload.get("scroll_token"),
            cost_eur=0.0,
            fetched=len(records),
        )
        result.cost_eur = self.cost_eur(result)
        return result

    def cost_eur(self, result: SourceResult) -> float:
        from ..core.config import USD_TO_EUR

        return result.fetched * _SEARCH_COST_USD_PER_RECORD * USD_TO_EUR


# Registration hook named in sources/registry.py's docstring: importing this
# module registers "pdl" so run.py --coverage-test pdl / registry.get_provider
# can find it. registry.py deliberately does not import this module itself
# (it may not exist at registry-import time), so something must import
# sources.pdl at least once per process -- run.py's --coverage-test path does
# this lazily; see run.py's _load_licensed_provider.
from .registry import register_provider  # noqa: E402

register_provider(PDLProvider())
