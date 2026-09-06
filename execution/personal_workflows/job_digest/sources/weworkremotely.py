"""
description: WeWorkRemotely source adapter for job_digest. Hits the public RSS feed,
    parses each entry as a SourceJob, keeps rows matching profile.keywords. Ported from
    the operator's internal job pipeline, generalized off profile.keywords instead of a hardcoded
    PM-only title list.
inputs:
  - profile: Profile — profile.keywords are matched against each entry's title
  - country: registry.Country | None — ignored; WeWorkRemotely is a global remote feed
  - dry: bool — when True, returns SourceJob rows from fixtures/weworkremotely.jsonl,
    no network
outputs:
  - list[SourceJob]

Endpoint: https://weworkremotely.com/categories/remote-product-jobs.rss
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from .. import registry
from ..contracts import JobSource, SourceJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.sources.weworkremotely")

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

FEEDS = [
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
]

HEADERS = {
    "User-Agent": "job-digest/0.1 (+https://github.com/)",
    "Accept": "application/rss+xml,application/xml,text/xml",
}

MAX_JOBS = 200

# Role/seniority words that, if present in a "Company: Role" pre-colon segment,
# mean the colon is INSIDE the job title, not the WWR company/role separator.
_TITLE_WORDS_IN_PRECOLON = (
    "manager", "engineer", "developer", "lead", "head", "director", "senior",
    "sr.", "sr ", "principal", "staff", "consultant", "owner", "product",
    "designer", "architect", "specialist", "analyst", "officer", "vp",
)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


def _parse_title(raw_title: str) -> tuple[str, str]:
    """WWR titles often shape as 'CompanyName: Role Title'. Split when present."""
    if ":" in raw_title:
        a, b = raw_title.split(":", 1)
        company = a.strip()
        title = b.strip()
        company_low = company.lower()
        looks_like_title = (
            len(company) > 40
            or any(w in company_low for w in _TITLE_WORDS_IN_PRECOLON)
            or not title
        )
        if not looks_like_title:
            return company, title
    return "Unknown", raw_title.strip()


def _entry_to_source_job(item: ET.Element, keywords_lower: list[str]) -> SourceJob | None:
    title_el = item.find("title")
    link_el = item.find("link")
    guid_el = item.find("guid")
    desc_el = item.find("description")
    pubdate_el = item.find("pubDate")
    region_el = item.find("region")

    title_raw = (title_el.text or "").strip() if title_el is not None else ""
    if not title_raw:
        return None
    company, title = _parse_title(title_raw)

    if not any(kw in title.lower() for kw in keywords_lower):
        return None

    url = (link_el.text or "").strip() if link_el is not None else ""
    if not url:
        return None

    source_id = (guid_el.text or url or "").strip() if guid_el is not None else url
    if not source_id:
        return None

    posted_at = None
    if pubdate_el is not None and pubdate_el.text:
        try:
            dt = parsedate_to_datetime(pubdate_el.text.strip())
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            posted_at = dt
        except (TypeError, ValueError):
            posted_at = None

    description = _strip_html((desc_el.text or "") if desc_el is not None else "")
    location = (region_el.text or "Remote").strip() if region_el is not None else "Remote"

    try:
        return SourceJob(
            source=JobSource.WEWORKREMOTELY,
            source_id=source_id,
            url=url,
            title=title,
            company=company or "Unknown",
            location_raw=location,
            description_snippet=description,
            posted_at=posted_at,
            contract_type_raw="Permanent",
        )
    except ValueError as exc:
        logger.warning("weworkremotely: skip item (validation): %s", exc)
        return None


def _parse_feed(xml_text: str, keywords_lower: list[str]) -> list[SourceJob]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("weworkremotely: RSS parse failed: %s", exc)
        return []
    out: list[SourceJob] = []
    for item in root.iter("item"):
        sj = _entry_to_source_job(item, keywords_lower)
        if sj is not None:
            out.append(sj)
    return out


def fetch(profile: Profile, country: "registry.Country | None", *, dry: bool = False) -> list[SourceJob]:
    """Pull the WeWorkRemotely product feed, dedupe by URL, keep profile.keywords matches."""
    if dry:
        return _load_fixture()

    keywords_lower = [k.lower() for k in profile.keywords]
    out: list[SourceJob] = []
    seen_urls: set[str] = set()
    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        for feed_url in FEEDS:
            try:
                resp = client.get(feed_url)
            except httpx.HTTPError as exc:
                logger.warning("weworkremotely: feed %s HTTP error: %s", feed_url, exc)
                continue
            if resp.status_code != 200:
                logger.warning("weworkremotely: feed %s status %d", feed_url, resp.status_code)
                continue
            items = _parse_feed(resp.text, keywords_lower)
            new = 0
            for sj in items:
                if str(sj.url) in seen_urls:
                    continue
                seen_urls.add(str(sj.url))
                out.append(sj)
                new += 1
                if len(out) >= MAX_JOBS:
                    break
            logger.info("weworkremotely: feed %s → %d items, %d new", feed_url, len(items), new)
            if len(out) >= MAX_JOBS:
                break
    return out


def _load_fixture() -> list[SourceJob]:
    path = _FIXTURES_DIR / "weworkremotely.jsonl"
    if not path.exists():
        logger.warning("weworkremotely: dry-mode fixture missing at %s — returning []", path)
        return []
    out: list[SourceJob] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SourceJob.model_validate_json(line))
    return out
