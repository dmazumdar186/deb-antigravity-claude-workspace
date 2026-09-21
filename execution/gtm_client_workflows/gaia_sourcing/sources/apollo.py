"""
Source plugin: Apollo.io People Search + People Enrichment.

description: fetches Irish engineers matching a SourceQuery from Apollo's
    People Search API (`mixed_people/search`) and maps each match into a
    ProviderRecord + RawDocument pair per RADAR_CONTRACTS.md §A.
inputs: SourceQuery (role_id, niche, terms, locations, limit, cursor); env
    var APOLLO_API_KEY (via core.config.secret).
outputs: SourceResult (documents, provider_records, next_cursor, cost_eur,
    fetched). No disk cache (see sources/licensed_common.py docstring).

DOCS READ (WebFetch, 2026-09-10):
  - https://docs.apollo.io/reference/people-enrichment
  - https://docs.apollo.io/reference/rate-limits
  - https://docs.apollo.io/reference/authentication
  - https://docs.apollo.io/docs/create-api-key

VERIFIED from the docs above:
  - Base URL: https://api.apollo.io/api/v1
  - Auth header: `x-api-key: <APOLLO_API_KEY>` on every request (OAuth
    Bearer is an alternative Apollo also accepts, not used here).
  - Enrichment endpoint (used for reference/future single-person lookups,
    NOT called by fetch() below): POST /people/match. Needs at least one
    identifier: name (or first_name+last_name), email/hashed_email,
    domain/organization_name, Apollo id, or linkedin_url. Response's
    `employment_history[]` entries carry `organization_name`, `title`,
    `start_date`, `end_date`, `current` -- confirmed dated job history
    fields exist on this endpoint.
  - Rate limits (per team, per endpoint, across minute/hour/day windows):
    Free plan search endpoints 50/min, 200/hr, 600/day; enrichment
    endpoints 50/min (20 for bulk), 200/hr (100 bulk), 600/day. Basic+ tiers
    raise search to 200/min, 6,000/hr, 50,000/day and enrichment to
    1,000/min uncapped hourly/daily. SourceProvider.rate_limit_s uses the
    Free-plan floor (50/min -> 1.2s between calls) since the account's plan
    is not knowable from code.
  - API key location: Apollo dashboard -> Settings -> Integrations ->
    API Keys ("Launch Apollo and click Settings > Integrations > API
    Keys"). Docs state plan-gating exists ("Access to Apollo API depends on
    your Apollo plan") without naming which tier -- see KEY_INSTRUCTIONS.md.

The People SEARCH endpoint itself (`POST /v1/mixed_people/search`) is
documented across Apollo's public API reference but the specific reference
page (docs.apollo.io/reference/people-search and
.../reference/search-for-people) both 404'd for this fetcher on 2026-09-10 --
Apollo's docs are a versioned Stoplight/GitBook-style site whose route
naming does not match either guess. The endpoint path, parameter names
(`q_organization_domains`, `person_titles`, `person_locations`, `page`,
`per_page`) and `contacts`/`people` response shape are taken from Apollo's
long-published and still-current public API surface (same
`api.apollo.io/api/v1` base, same `x-api-key` auth confirmed above) rather
than from a freshly-fetched reference page for this exact endpoint --
flagged ASSUMED below per the same standard integrations/recruit_crm.py
used for shapes that would not resolve.

ASSUMED (endpoint exists and is stable, but this exact reference page did
  not resolve for direct citation on 2026-09-10):
  - Endpoint: POST /v1/mixed_people/search.
  - Location filter for Ireland: `person_locations: ["Ireland"]` (Apollo's
    location filter accepts free-text "City, Region, Country" style
    strings; a bare country name is Apollo's documented shorthand for
    country-level filtering elsewhere in their search filters).
  - Title/keyword filter: `person_titles: [...]` for exact title phrases,
    `q_keywords` for the niche terms as a free-text fallback.
  - Pagination: `page` (1-based) + `per_page`; Apollo's search responses
    also include `pagination.total_pages` used to derive `next_cursor`.
  - Credit cost of a plain search hit (no email/phone reveal): 0 -- Apollo's
    pricing page states credits are consumed "whenever you export a contact
    outside of Apollo" or reveal an email/phone, not for a bare search
    match. `fetch()` never reveals a personal email or phone, so cost_eur
    is 0.0 for this provider's search path; treat any candidate this
    plugin surfaces as needing a paid People Enrichment call before an
    email/phone is usable, and account for that at the point it happens
    (contact stage / layers/contact.py), not here.

UNVERIFIED:
  - The exact USD price of Apollo credits by plan (needed only if a future
    change starts calling /people/match's reveal_personal_emails path from
    here) -- www.apollo.io/pricing did not render a pricing table to the
    fetcher.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from ..core.contracts import JobStint, ProviderRecord, RawDocument, SourceQuery, SourceResult
from .licensed_common import _post_json, parse_date, raw_hash, render_content_text, require_key
from .base import SourceProvider, throttle  # noqa: F401  (Protocol; import documents the contract)

BASE_URL = "https://api.apollo.io/api/v1"
SEARCH_URL = BASE_URL + "/mixed_people/search"  # ASSUMED path, see module docstring

# A bare search hit costs 0 credits per Apollo's documented export/reveal
# billing model (see module docstring "ASSUMED" section).
_SEARCH_COST_EUR_PER_RECORD = 0.0


def _build_body(query: SourceQuery) -> dict[str, Any]:
    body: dict[str, Any] = {
        "person_locations": query.locations or ["Ireland"],
        "page": 1,
        "per_page": max(1, min(query.limit, 100)),
    }
    if query.terms:
        body["person_titles"] = query.terms
        body["q_keywords"] = " ".join(query.terms)
    if query.cursor:
        try:
            body["page"] = int(query.cursor)
        except (TypeError, ValueError):
            pass
    return body


def _map_employment(raw_history: list[dict]) -> list[JobStint]:
    out: list[JobStint] = []
    for e in raw_history or []:
        title = e.get("title")
        employer = e.get("organization_name")
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
    org = item.get("organization") or {}
    external_id = str(item.get("id") or "")
    full_name = item.get("name") or " ".join(
        p for p in (item.get("first_name"), item.get("last_name")) if p
    )
    return ProviderRecord(
        provider="apollo",
        external_id=external_id,
        full_name=full_name,
        current_title=item.get("title"),
        current_employer=org.get("name") or item.get("organization_name"),
        city=item.get("city"),
        region=item.get("state"),
        country=item.get("country"),
        job_history=_map_employment(item.get("employment_history") or []),
        skills=list(item.get("skills") or []),
        linkedin_url=item.get("linkedin_url"),
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
        content_text=text or (record.full_name or "apollo record"),
        http_status=200,
        title=record.full_name,
    )


class ApolloProvider:
    name = "apollo"
    text_source = "provider_field"
    rate_limit_s = 1.2  # Free-plan floor: 50 req/min -> 60/50 = 1.2s between calls

    def fetch(self, query: SourceQuery) -> SourceResult:
        api_key = require_key("APOLLO_API_KEY")
        body = _build_body(query)

        throttle(self.name, self.rate_limit_s)
        status, payload = _post_json(
            SEARCH_URL,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json_body=body,
        )
        if status != 200:
            return SourceResult(provider=self.name, documents=[], provider_records=[],
                                 next_cursor=None, cost_eur=0.0, fetched=0,
                                 error="HTTP " + str(status))

        items = payload.get("people") or payload.get("contacts") or []
        records = [_to_record(it) for it in items]
        docs = [_to_document(rec, it) for rec, it in zip(records, items)]

        pagination = payload.get("pagination") or {}
        page = int(body.get("page") or 1)
        total_pages = pagination.get("total_pages")
        next_cursor: Optional[str] = (
            str(page + 1) if total_pages and page < int(total_pages) else None
        )

        result = SourceResult(
            provider=self.name,
            documents=docs,
            provider_records=records,
            next_cursor=next_cursor,
            cost_eur=0.0,
            fetched=len(records),
        )
        result.cost_eur = self.cost_eur(result)
        return result

    def cost_eur(self, result: SourceResult) -> float:
        return result.fetched * _SEARCH_COST_EUR_PER_RECORD


# Registration hook -- see sources/pdl.py's matching comment for why this
# self-registration on import exists.
from .registry import register_provider  # noqa: E402

register_provider(ApolloProvider())
