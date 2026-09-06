"""
description: LinkedIn jobs-guest (public, unauthenticated) API source adapter for job_digest.
    Hits the same endpoint LinkedIn serves to logged-out browsers — no OAuth, no login,
    no personal credentials. Adapted from the operator's internal job pipeline and
    adapted to the profile-driven, per-country job_digest contract.
inputs:
  - profile: Profile — keywords come from profile.keywords (never hardcoded titles)
  - country: registry.Country — required; country.linkedin_geo_id selects the geo scope
  - dry: bool — when True, returns SourceJob rows from fixtures/linkedin_guest_api.jsonl,
    no network
outputs:
  - list[SourceJob]

Endpoints (public, no auth):
  - Search: linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
  - Detail: linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}

Anti-bot posture: gentle. Self-throttle 1-2s/search-page; back off on 429/999; hard-stop
on block markers (captcha/checkpoint/verify) so a friend's free-tier runner never hammers
a credential-rotated state. max_pages_per_keyword is capped at 3 and total cards per
country at 300 to protect the free-tier runtime (see directives/personal_workflows/job_digest.md).
"""

from __future__ import annotations

import logging
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .. import registry
from ..contracts import JobSource, SourceJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.sources.linkedin_guest_api")

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL_FMT = "https://www.linkedin.com/jobs/view/{job_id}"
DETAIL_API_URL_FMT = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

# Protective caps for a friend's free-tier GitHub Actions runner.
MAX_PAGES_PER_KEYWORD = 3
MAX_CARDS_PER_COUNTRY = 300

DEFAULT_POSTED_WITHIN_HOURS = 48

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.linkedin.com/jobs/search",
}

PAGE_STEP = 25
PAGINATION_CAP = 975
MAX_EMPTY_STREAK = 2
RETRIES_PER_OFFSET = 3
EMPTY_PAGE_BYTES = 100
BLOCK_MIN_BYTES = 1024
BLOCK_MARKERS = ("captcha", "unusual activity", "/checkpoint/", "please verify")
BACKOFF_BASE = 1.0
SEARCH_DELAY_MIN = 1.0
SEARCH_DELAY_MAX = 2.0

DETAIL_MAX_WORKERS = 2
DETAIL_RETRIES = 2
DETAIL_TIMEOUT = 15.0
DETAIL_PER_REQ_SLEEP = (0.5, 1.0)
DETAIL_DESC_MAX_CHARS = 2000

URN_RE = re.compile(r"urn:li:jobPosting:(\d+)")


class LinkedInBlockedError(RuntimeError):
    """Raised when LinkedIn returns a captcha/checkpoint/verify marker."""


def _looks_blocked(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in BLOCK_MARKERS)


def _fetch_search_page(
    client: httpx.Client,
    keywords: str,
    geo_id: str,
    start: int,
    f_tpr: str,
    is_first_page: bool,
) -> Optional[str]:
    params = {"keywords": keywords, "geoId": geo_id, "f_TPR": f_tpr, "start": start}
    last_text = ""
    for attempt in range(RETRIES_PER_OFFSET):
        try:
            resp = client.get(SEARCH_URL, params=params, timeout=20.0)
        except httpx.HTTPError:
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue

        last_text = resp.text or ""
        size = len(last_text.encode("utf-8"))

        if resp.status_code in (429, 999):
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if _looks_blocked(last_text):
            raise LinkedInBlockedError("LinkedIn block marker in response (captcha/checkpoint/verify).")
        if resp.status_code == 200 and size >= EMPTY_PAGE_BYTES:
            return last_text
        time.sleep(BACKOFF_BASE * (attempt + 1))

    if is_first_page and len(last_text.encode("utf-8")) < BLOCK_MIN_BYTES:
        raise LinkedInBlockedError(
            f"Page-1 search returned a persistently tiny response (<{BLOCK_MIN_BYTES} bytes) "
            "after retries; suspected block or endpoint change."
        )
    return None


def _job_id_from_card(card) -> Optional[str]:
    urn = card.get("data-entity-urn") or ""
    m = URN_RE.search(urn)
    if m:
        return m.group(1)
    nested = card.select_one("[data-entity-urn]")
    if nested:
        m = URN_RE.search(nested.get("data-entity-urn") or "")
        if m:
            return m.group(1)
    link = card.select_one("a.base-card__full-link")
    if link and link.get("href"):
        m = re.search(r"-(\d+)\?", link["href"]) or re.search(r"/view/[^/]*?(\d+)(?:\?|$)", link["href"])
        if m:
            return m.group(1)
    return None


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.base-card") or soup.find_all("li")
    out: list[dict] = []
    for card in cards:
        job_id = _job_id_from_card(card)
        if not job_id:
            continue
        title = _text(card.select_one("h3.base-search-card__title"))
        company = _text(card.select_one("h4.base-search-card__subtitle"))
        location = _text(card.select_one("span.job-search-card__location"))
        link_el = card.select_one("a.base-card__full-link")
        apply_url = (link_el.get("href") or "").split("?")[0] if link_el else ""
        time_el = card.select_one("time")
        posted_iso = time_el.get("datetime") or "" if time_el else ""
        out.append({
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "apply_url": apply_url or DETAIL_URL_FMT.format(job_id=job_id),
            "posted_iso": posted_iso,
        })
    return out


def _card_to_source_job(card: dict) -> SourceJob | None:
    try:
        posted_at = None
        if card["posted_iso"]:
            try:
                posted_at = datetime.fromisoformat(card["posted_iso"])
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
            except ValueError:
                posted_at = None
        return SourceJob(
            source=JobSource.LINKEDIN_GUEST_API,
            source_id=card["job_id"],
            url=card["apply_url"],
            title=card["title"],
            company=card["company"] or "Unknown",
            location_raw=card["location"],
            description_snippet=card.get("description_snippet", "")[:DETAIL_DESC_MAX_CHARS],
            posted_at=posted_at,
            contract_type_raw="",
        )
    except (KeyError, ValueError) as exc:
        logger.warning("linkedin_guest_api: skip card (parse error): %s", exc)
        return None


def _fetch_job_detail(client: httpx.Client, job_id: str) -> str:
    url = DETAIL_API_URL_FMT.format(job_id=job_id)
    for attempt in range(DETAIL_RETRIES + 1):
        try:
            resp = client.get(url, timeout=DETAIL_TIMEOUT)
        except httpx.HTTPError as exc:
            if attempt == DETAIL_RETRIES:
                logger.debug("linkedin detail %s: %s — soft-fail", job_id, exc)
                return ""
            time.sleep(BACKOFF_BASE * (attempt + 1))
            continue
        if resp.status_code in (429, 999, 503):
            time.sleep(BACKOFF_BASE * (attempt + 1) * 2)
            continue
        if resp.status_code != 200 or len(resp.text) < 500:
            return ""
        text = resp.text
        if _looks_blocked(text):
            logger.warning("linkedin detail %s: block marker — stop further detail fetches", job_id)
            raise LinkedInBlockedError("detail-endpoint block marker")
        soup = BeautifulSoup(text, "html.parser")
        block = (soup.select_one(".show-more-less-html__markup")
                 or soup.select_one(".description__text")
                 or soup.select_one("section.description"))
        if not block:
            return ""
        return block.get_text(" ", strip=True)[:DETAIL_DESC_MAX_CHARS]
    return ""


def _enrich_with_jd(client: httpx.Client, cards: list[dict], *, max_workers: int = DETAIL_MAX_WORKERS) -> tuple[int, int]:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if not cards:
        return 0, 0
    attempted = 0
    enriched = 0
    blocked = False
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_job_detail, client, c["job_id"]): c for c in cards}
        for fut in as_completed(futures):
            card = futures[fut]
            attempted += 1
            try:
                desc = fut.result()
            except LinkedInBlockedError:
                blocked = True
                for other in futures:
                    other.cancel()
                break
            except (httpx.HTTPError, ValueError) as exc:
                # per-job soft-fail: one bad detail page must not sink the run
                logger.debug("linkedin detail %s: %s — soft-fail", card["job_id"], exc)
                desc = ""
            card["description_snippet"] = desc or ""
            if desc:
                enriched += 1
            time.sleep(random.uniform(*DETAIL_PER_REQ_SLEEP))
    if blocked:
        logger.warning(
            "linkedin_guest_api: detail enrichment hit a block marker; cancelled in-flight "
            "futures; partial enrichment retained (%d/%d).", enriched, len(cards),
        )
    return enriched, attempted


def _cards_to_source_jobs(cards: list[dict]) -> list[SourceJob]:
    out: list[SourceJob] = []
    for card in cards:
        sj = _card_to_source_job(card)
        if sj is not None:
            out.append(sj)
    return out


def _fetch_live(keywords: list[str], geo_id: str, posted_within_hours: int) -> list[SourceJob]:
    f_tpr = f"r{posted_within_hours * 3600}"
    seen_ids: set[str] = set()
    cards_by_id: dict[str, dict] = {}

    with httpx.Client(headers=HEADERS) as client:
        for kw in keywords:
            if len(cards_by_id) >= MAX_CARDS_PER_COUNTRY:
                break
            empty_streak = 0
            for page_idx in range(MAX_PAGES_PER_KEYWORD):
                start = page_idx * PAGE_STEP
                if start > PAGINATION_CAP:
                    break
                try:
                    html = _fetch_search_page(client, kw, geo_id, start, f_tpr, is_first_page=(page_idx == 0))
                except LinkedInBlockedError as exc:
                    logger.error("linkedin_guest_api: BLOCKED on keyword=%r start=%d — %s", kw, start, exc)
                    return _cards_to_source_jobs(list(cards_by_id.values()))
                if html is None:
                    empty_streak += 1
                    if empty_streak >= MAX_EMPTY_STREAK:
                        break
                    continue
                empty_streak = 0
                cards = _parse_cards(html)
                if not cards:
                    empty_streak += 1
                    if empty_streak >= MAX_EMPTY_STREAK:
                        break
                    continue
                for card in cards:
                    jid = card["job_id"]
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    cards_by_id[jid] = card
                    if len(cards_by_id) >= MAX_CARDS_PER_COUNTRY:
                        break
                logger.info("linkedin_guest_api: keyword=%r start=%d → %d cards (cumul %d)",
                            kw, start, len(cards), len(cards_by_id))
                if len(cards_by_id) >= MAX_CARDS_PER_COUNTRY:
                    break
                time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))

        all_cards = list(cards_by_id.values())
        if all_cards:
            enriched, attempted = _enrich_with_jd(client, all_cards)
            logger.info("linkedin_guest_api: enriched %d/%d cards with JD text", enriched, attempted)

    return _cards_to_source_jobs(all_cards)


def fetch(profile: Profile, country: "registry.Country | None", *, dry: bool = False) -> list[SourceJob]:
    """Fetch LinkedIn guest-API jobs for one country, using the profile's keywords.

    country is required for this source (LinkedIn scopes by geoId). Passing None
    raises — sources/__init__.py's fan-out only calls this per selected country.
    """
    if dry:
        return _load_fixture()
    if country is None:
        raise ValueError("linkedin_guest_api.fetch requires a country (geoId-scoped source)")
    return _fetch_live(profile.keywords, country.linkedin_geo_id, DEFAULT_POSTED_WITHIN_HOURS)


def _load_fixture() -> list[SourceJob]:
    path = _FIXTURES_DIR / "linkedin_guest_api.jsonl"
    if not path.exists():
        logger.warning("linkedin_guest_api: dry-mode fixture missing at %s — returning []", path)
        return []
    out: list[SourceJob] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SourceJob.model_validate_json(line))
    return out
