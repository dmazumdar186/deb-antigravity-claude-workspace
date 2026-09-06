"""
description: Hellowork source adapter for job_digest, using the public web search plus
    per-job schema.org JSON-LD JobPosting extraction (no auth, no SPA scraping — every
    job page reliably embeds a standards-compliant <script type="application/ld+json">
    blob). Adapted from the operator's internal job pipeline, generalized off profile.keywords.
inputs:
  - profile: Profile — one search query per profile.keywords entry
  - country: registry.Country | None — ignored; this source is only wired for FR in
    registry.py, so it is always called for a France-scoped profile
  - dry: bool — when True, returns SourceJob rows from fixtures/hellowork.jsonl,
    no network
outputs:
  - list[SourceJob]

Pipeline: search page → offer IDs (regex) → per-offer detail page (parallel) →
JobPosting JSON-LD → SourceJob.
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from .. import registry
from ..contracts import JobSource, SourceJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.sources.hellowork")

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

SEARCH_URL = "https://www.hellowork.com/fr-fr/emploi/recherche.html"
DETAIL_URL_FMT = "https://www.hellowork.com/fr-fr/emplois/{job_id}.html"

NATIONAL_LOCATION = "france"
MAX_LOCATIONS = 3  # bounds request count to <= MAX_LOCATIONS x len(keywords)
DEFAULT_POSTED_WITHIN_HOURS = 48
MAX_PAGES_PER_KEYWORD = 3
DETAIL_MAX_WORKERS = 2
DETAIL_TIMEOUT = 20.0
DETAIL_RETRIES = 2
DETAIL_PER_REQ_SLEEP = (0.5, 1.0)
SEARCH_DELAY_MIN = 0.7
SEARCH_DELAY_MAX = 1.4
SEARCH_TIMEOUT = 20.0
BACKOFF_BASE = 1.0
DESC_MAX_CHARS = 2000

HEADERS = {
    "User-Agent": "job-digest/0.1 (+https://github.com/)",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

OFFER_ID_RE = re.compile(r"/fr-fr/emplois/(\d+)\.html")
LD_JSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
WS_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")


class HelloworkBlockedError(RuntimeError):
    """Raised when Hellowork returns a 403 / captcha / WAF block."""


def _strip_html(s: Optional[str]) -> str:
    if not s:
        return ""
    text = TAG_RE.sub(" ", s)
    import html as html_lib
    text = html_lib.unescape(text)
    return WS_RE.sub(" ", text).strip()


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def _fold_for_url(s: str) -> str:
    """Lowercase + strip diacritics + collapse whitespace to '-', the shape
    Hellowork's own `l=` search param expects (e.g. 'Île-de-France' -> 'ile-de-france')."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower().strip()
    return re.sub(r"\s+", "-", s)


def _locations_for_profile(profile: Profile) -> list[str]:
    """Derive Hellowork search locations from the profile instead of the old
    hardcoded Paris/Île-de-France default.

    Only cities attributable to France (via registry.country_for_city) are
    used — a profile city belonging to another selected country (Berlin for
    a FR+DE profile) must not narrow the France-only Hellowork search to it.
    With no attributable city, fall back to a single national search rather
    than guessing a location. Bounded to MAX_LOCATIONS so the request count
    stays <= MAX_LOCATIONS x len(keywords).
    """
    locations: list[str] = []
    for city in profile.locations.cities:
        owner = registry.country_for_city(city)
        if owner is None or owner.iso2 != "FR":
            continue
        folded = _fold_for_url(city)
        if folded and folded not in locations:
            locations.append(folded)
        if len(locations) >= MAX_LOCATIONS:
            break
    return locations or [NATIONAL_LOCATION]


def _search_page(client: httpx.Client, keyword: str, location: str, page: int) -> Optional[str]:
    params = {"k": keyword, "l": location, "p": str(page)}
    for attempt in range(3):
        try:
            resp = client.get(SEARCH_URL, params=params, timeout=SEARCH_TIMEOUT)
        except httpx.HTTPError as exc:
            if attempt == 2:
                logger.warning("hellowork: search transient failure (%s) keyword=%r loc=%r p=%d",
                                exc, keyword, location, page)
                return None
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 403:
            raise HelloworkBlockedError(f"hellowork search 403 — keyword={keyword!r} loc={location!r}")
        if resp.status_code in (429, 503):
            time.sleep(BACKOFF_BASE * (attempt + 1) * 2)
            continue
        if resp.status_code != 200 or len(resp.text) < 1000:
            return None
        return resp.text
    return None


def _extract_offer_ids(html: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for jid in OFFER_ID_RE.findall(html or ""):
        if jid not in seen:
            seen.add(jid)
            out.append(jid)
    return out


def _parse_job_posting_ld(html: str) -> dict | None:
    if not html:
        return None
    for blob in LD_JSON_RE.findall(html):
        try:
            d = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            return d
        if isinstance(d, dict) and isinstance(d.get("@graph"), list):
            for node in d["@graph"]:
                if isinstance(node, dict) and node.get("@type") == "JobPosting":
                    return node
    return None


def _ld_to_source_job(job_id: str, ld: dict) -> SourceJob | None:
    try:
        title = (ld.get("title") or "").strip()
        hiring = ld.get("hiringOrganization") or {}
        company = ((hiring.get("name") if isinstance(hiring, dict) else "") or "").strip()
        if not title or not company:
            return None
        loc = ld.get("jobLocation")
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        if not isinstance(loc, dict):
            loc = {}
        addr = loc.get("address") if isinstance(loc.get("address"), dict) else {}
        city = (addr.get("addressLocality") or "").strip()
        region = (addr.get("addressRegion") or "").strip()
        country = (addr.get("addressCountry") or "").strip()
        location_raw = ", ".join(p for p in (city, region, country) if p)

        description = _strip_html(ld.get("description") or "")[:DESC_MAX_CHARS]
        emp_type_raw = ld.get("employmentType") or ""
        if isinstance(emp_type_raw, list):
            emp_type_raw = emp_type_raw[0] if emp_type_raw else ""
        contract_type_raw = str(emp_type_raw).strip().upper()
        posted_at = _parse_iso(ld.get("datePosted") or "")

        return SourceJob(
            source=JobSource.HELLOWORK,
            source_id=job_id,
            url=DETAIL_URL_FMT.format(job_id=job_id),
            title=title,
            company=company,
            location_raw=location_raw,
            description_snippet=description,
            posted_at=posted_at,
            contract_type_raw=contract_type_raw,
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("hellowork: ld→SourceJob failed for %s: %s", job_id, exc)
        return None


def _fetch_job_detail(client: httpx.Client, job_id: str) -> Optional[SourceJob]:
    url = DETAIL_URL_FMT.format(job_id=job_id)
    for attempt in range(DETAIL_RETRIES + 1):
        try:
            resp = client.get(url, timeout=DETAIL_TIMEOUT)
        except httpx.HTTPError as exc:
            if attempt == DETAIL_RETRIES:
                logger.debug("hellowork detail %s: %s — soft-fail", job_id, exc)
                return None
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code == 403:
            raise HelloworkBlockedError(f"hellowork detail 403 — job_id={job_id}")
        if resp.status_code in (429, 503):
            time.sleep(BACKOFF_BASE * (attempt + 1) * 2)
            continue
        if resp.status_code != 200 or len(resp.text) < 1000:
            return None
        ld = _parse_job_posting_ld(resp.text)
        if ld is None:
            return None
        return _ld_to_source_job(job_id, ld)
    return None


def _enrich_in_parallel(client: httpx.Client, job_ids: list[str], *, max_workers: int = DETAIL_MAX_WORKERS) -> list[SourceJob]:
    if not job_ids:
        return []
    out: list[SourceJob] = []
    blocked = False
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_job_detail, client, jid): jid for jid in job_ids}
        for fut in as_completed(futures):
            jid = futures[fut]
            try:
                sj = fut.result()
            except HelloworkBlockedError:
                blocked = True
                logger.warning("hellowork: blocked during detail enrichment — stopping early")
                break
            except httpx.HTTPError as exc:
                # per-job soft-fail: one bad detail page must not sink the run
                logger.debug("hellowork detail %s: %s — soft-fail", jid, exc)
                continue
            if sj is not None:
                out.append(sj)
            time.sleep(random.uniform(*DETAIL_PER_REQ_SLEEP))
    if blocked:
        logger.warning("hellowork: partial detail set retained (%d/%d).", len(out), len(job_ids))
    return out


def _finalize_by_age(jobs: list[SourceJob], posted_within_hours: int) -> list[SourceJob]:
    if posted_within_hours <= 0:
        return jobs
    cutoff = datetime.now(timezone.utc).timestamp() - posted_within_hours * 3600
    out: list[SourceJob] = []
    for sj in jobs:
        if sj.posted_at is None or sj.posted_at.timestamp() >= cutoff:
            out.append(sj)
    return out


def _fetch_live(keywords: list[str], locations: list[str]) -> list[SourceJob]:
    seen_ids: set[str] = set()

    with httpx.Client(headers=HEADERS) as client:
        for kw in keywords:
            for loc in locations:
                for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
                    try:
                        html = _search_page(client, kw, loc, page)
                    except HelloworkBlockedError as exc:
                        logger.error("hellowork: search blocked — %s", exc)
                        return _finalize_by_age(
                            _enrich_in_parallel(client, list(seen_ids)), DEFAULT_POSTED_WITHIN_HOURS,
                        )
                    if html is None:
                        break
                    page_ids = _extract_offer_ids(html)
                    new_ids = [i for i in page_ids if i not in seen_ids]
                    seen_ids.update(new_ids)
                    logger.info("hellowork: search kw=%r loc=%r page=%d → %d hits, %d new",
                                kw, loc, page, len(page_ids), len(new_ids))
                    if not new_ids:
                        break
                    time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))

        if not seen_ids:
            return []

        logger.info("hellowork: detail enrichment for %d unique ids", len(seen_ids))
        try:
            jobs = _enrich_in_parallel(client, list(seen_ids))
        except HelloworkBlockedError as exc:
            logger.error("hellowork: detail blocked — %s", exc)
            return []

    return _finalize_by_age(jobs, DEFAULT_POSTED_WITHIN_HOURS)


def fetch(profile: Profile, country: "registry.Country | None", *, dry: bool = False) -> list[SourceJob]:
    """Search Hellowork using the profile's keywords across its France-attributed
    cities (or a single national search when the profile has none)."""
    if dry:
        return _load_fixture()
    return _fetch_live(profile.keywords, _locations_for_profile(profile))


def _load_fixture() -> list[SourceJob]:
    path = _FIXTURES_DIR / "hellowork.jsonl"
    if not path.exists():
        logger.warning("hellowork: dry-mode fixture missing at %s — returning []", path)
        return []
    out: list[SourceJob] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SourceJob.model_validate_json(line))
    return out
