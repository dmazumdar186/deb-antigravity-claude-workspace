"""
description: Welcome to the Jungle (WTTJ) source adapter for job_digest, using their
    public Algolia search backend (the same one WTTJ's own SPA calls — no browser, no
    consent-modal dance). Adapted from the operator's internal job pipeline and generalized off
    profile.keywords and country.iso2.
inputs:
  - profile: Profile — one Algolia query per profile.keywords entry
  - country: registry.Country — required; country.iso2 scopes the Algolia facet filter
  - dry: bool — when True, returns SourceJob rows from fixtures/wttj_algolia.jsonl,
    no network
outputs:
  - list[SourceJob]

The Algolia application id + search-only API key below are the PUBLIC,
referer-restricted credentials WTTJ serves to every anonymous browser load — not
account secrets. If WTTJ rotates them, re-harvest from a live page load (watch a
request to *-dsn.algolia.net, copy the x-algolia-api-key header).
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from .. import registry
from ..contracts import JobSource, SourceJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.sources.wttj_algolia")

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

ALGOLIA_APP_ID = "CSEKHVMS53"
ALGOLIA_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
ALGOLIA_INDEX = "wk_cms_jobs_production_published_at_desc"
ALGOLIA_QUERY_URL = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"

JOB_PAGE_URL_FMT = "https://www.welcometothejungle.com/en/companies/{org}/jobs/{slug}"

DEFAULT_POSTED_WITHIN_HOURS = 48
HITS_PER_PAGE = 100
MAX_PAGES = 3
RETRIES = 3
BACKOFF_BASE = 1.0
SEARCH_DELAY_MIN = 0.5
SEARCH_DELAY_MAX = 1.0
TIMEOUT = 20

HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "Content-Type": "application/json",
    "Referer": "https://www.welcometothejungle.com/",
    "User-Agent": "job-digest/0.1 (+https://github.com/)",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


class WttjAlgoliaBlockedError(RuntimeError):
    """Raised on Algolia 403 (key/referer rotated)."""


def _strip_html(s: Optional[str]) -> str:
    if not s:
        return ""
    text = _TAG_RE.sub(" ", s)
    text = html_lib.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(.*)", s)
        if not m:
            return None
        try:
            d = datetime.fromisoformat(m.group(1) + (m.group(2) or ""))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _age_hours(published_at: str) -> float | None:
    d = _parse_iso(published_at)
    if d is None:
        return None
    return (datetime.now(timezone.utc) - d).total_seconds() / 3600.0


def _hit_to_source_job(hit: dict) -> SourceJob | None:
    try:
        org = hit.get("organization") or {}
        object_id = str(hit.get("objectID", "")).strip()
        if not object_id:
            return None
        title = (hit.get("name") or "").strip()
        company = (org.get("name") or "Unknown").strip()
        if not title or not company:
            return None
        org_slug = org.get("slug") or ""
        slug = hit.get("slug") or ""
        if not org_slug or not slug:
            return None
        url = JOB_PAGE_URL_FMT.format(org=org_slug, slug=slug)

        offices = hit.get("offices") or []
        office = (hit.get("office") or {}) or (offices[0] if offices else {})
        loc_parts = [office.get("city"), office.get("country") or "France"]
        location_raw = ", ".join(p for p in loc_parts if p)

        raw_profile = hit.get("profile") or ""
        description = _strip_html(raw_profile)[:2000]

        return SourceJob(
            source=JobSource.WTTJ_ALGOLIA,
            source_id=object_id,
            url=url,
            title=title,
            company=company,
            location_raw=location_raw,
            description_snippet=description,
            posted_at=_parse_iso(hit.get("published_at") or ""),
            contract_type_raw=(hit.get("contract_type") or "").upper(),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("wttj_algolia: skip hit (parse error): %s", exc)
        return None


def _search_page(client: httpx.Client, keyword: str, page: int, country_code: str) -> Optional[dict]:
    body = json.dumps({
        "query": keyword,
        "hitsPerPage": HITS_PER_PAGE,
        "page": page,
        "facetFilters": [[f"offices.country_code:{country_code}"]],
        "attributesToRetrieve": ["*"],
    })
    for attempt in range(RETRIES):
        try:
            resp = client.post(ALGOLIA_QUERY_URL, content=body, timeout=TIMEOUT)
        except httpx.HTTPError:
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 403:
            raise WttjAlgoliaBlockedError(
                f"Algolia 403 for index {ALGOLIA_INDEX} — referer/key rejected; may have rotated."
            )
        if resp.status_code == 429:
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return None
        time.sleep(BACKOFF_BASE * (attempt + 1))
    return None


def _fetch_live(keywords: list[str], country_code: str) -> list[SourceJob]:
    seen_ids: set[str] = set()
    out: list[SourceJob] = []

    with httpx.Client(headers=HEADERS) as client:
        for kw in keywords:
            for page_idx in range(MAX_PAGES):
                try:
                    blob = _search_page(client, kw, page_idx, country_code)
                except WttjAlgoliaBlockedError as exc:
                    logger.error("wttj_algolia: BLOCKED — %s", exc)
                    return out
                if blob is None:
                    break
                hits = blob.get("hits") or []
                if not hits:
                    break
                added = 0
                hit_too_old = False
                for hit in hits:
                    age = _age_hours(hit.get("published_at") or "")
                    if age is not None and age > DEFAULT_POSTED_WITHIN_HOURS:
                        hit_too_old = True
                        continue
                    object_id = str(hit.get("objectID", ""))
                    if not object_id or object_id in seen_ids:
                        continue
                    sj = _hit_to_source_job(hit)
                    if sj is None:
                        continue
                    seen_ids.add(object_id)
                    out.append(sj)
                    added += 1
                logger.info("wttj_algolia: keyword=%r page=%d → %d hits, %d kept (cumul %d)",
                            kw, page_idx, len(hits), added, len(out))
                if hit_too_old:
                    break
                time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))
    return out


def fetch(profile: Profile, country: "registry.Country | None", *, dry: bool = False) -> list[SourceJob]:
    """Fetch WTTJ Algolia jobs for one country, using the profile's keywords."""
    if dry:
        return _load_fixture()
    if country is None:
        raise ValueError("wttj_algolia.fetch requires a country (iso2-scoped source)")
    return _fetch_live(profile.keywords, country.iso2)


def _load_fixture() -> list[SourceJob]:
    path = _FIXTURES_DIR / "wttj_algolia.jsonl"
    if not path.exists():
        logger.warning("wttj_algolia: dry-mode fixture missing at %s — returning []", path)
        return []
    out: list[SourceJob] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SourceJob.model_validate_json(line))
    return out
