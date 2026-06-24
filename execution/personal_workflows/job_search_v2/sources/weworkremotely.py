"""
description: WeWorkRemotely source adapter. Hits the public RSS feeds for the
    product and programming categories, parses each entry as a SourceJob. No
    auth, no rate limit beyond polite use.
inputs:
  - CLI: --max-jobs, --fixture
  - env: none
outputs:
  - stdout: JSON-lines of SourceJob records
  - .tmp/job_search_v2/weworkremotely_<uuid>.jsonl when run standalone

Endpoints:
  - https://weworkremotely.com/categories/remote-product-jobs.rss
  - https://weworkremotely.com/categories/remote-programming-jobs.rss
  - https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("weworkremotely")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"

FEEDS = [
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]

HEADERS = {
    "User-Agent": "job_search_v2 aggregator (https://github.com/dmazumdar186/deb-antigravity-claude-workspace; contact debanjan186@gmail.com)",
    "Accept": "application/rss+xml,application/xml,text/xml",
}

RELEVANT_TITLE_SUBSTRS = (
    "product manager", "product owner", "head of product",
    "senior pm", "principal pm",
    "ai engineer", "ml engineer", "machine learning",
    "ai automation", "automation engineer",
    "ai consultant", "ai strategy",
    "ai mobile", "mobile ai",
    "ai process",
    "ai product",
    "rpa",
    # WeWorkRemotely often prefixes titles with the company name: e.g.
    # "Acme: Senior Product Manager". The "product manager" substring catches
    # those without us needing prefix logic.
)


def _strip_html(html: str) -> str:
    """Rough HTML-to-text. RSS descriptions are short and we only feed the
    snippet to the ranker; perfect parsing isn't worth a new dependency."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


# Role/seniority words that, if they appear in the pre-colon segment, mean the
# colon is INSIDE the job title (e.g. "Sr. Product Manager: AI Focus"), not the
# WWR "Company: Role" separator. In that case we must NOT treat the pre-colon
# text as the company (audit 2026-06-24).
_TITLE_WORDS_IN_PRECOLON = (
    "manager", "engineer", "developer", "lead", "head", "director", "senior",
    "sr.", "sr ", "principal", "staff", "consultant", "owner", "product",
    "designer", "architect", "specialist", "analyst", "officer", "vp",
)


def _parse_title(raw_title: str) -> tuple[str, str]:
    """WWR titles often shape as 'CompanyName: Role Title'. Split when present.
    Returns (company, title). Falls back to ('Unknown', raw_title) if no colon,
    or if the pre-colon segment looks like part of the role title rather than a
    company name (contains a role/seniority word, or is implausibly long)."""
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


def _entry_to_source_job(item: ET.Element) -> SourceJob | None:
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

    if not any(s in title.lower() for s in RELEVANT_TITLE_SUBSTRS):
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
            contract_type_raw="Permanent",  # WWR full-time roles dominate the feed
        )
    except ValueError as exc:
        logger.warning("weworkremotely: skip item (validation): %s", exc)
        return None


def _parse_feed(xml_text: str) -> list[SourceJob]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("weworkremotely: RSS parse failed: %s", exc)
        return []
    out: list[SourceJob] = []
    for item in root.iter("item"):
        sj = _entry_to_source_job(item)
        if sj is not None:
            out.append(sj)
    return out


def fetch(max_jobs: int = 200) -> list[SourceJob]:
    """Pull all relevant WWR feeds, dedupe by URL, return list[SourceJob]."""
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
            items = _parse_feed(resp.text)
            new = 0
            for sj in items:
                if str(sj.url) in seen_urls:
                    continue
                seen_urls.add(str(sj.url))
                out.append(sj)
                new += 1
                if len(out) >= max_jobs:
                    break
            logger.info("weworkremotely: feed %s → %d items, %d new", feed_url, len(items), new)
            if len(out) >= max_jobs:
                break
    return out


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    if not fixture_path.exists():
        return []
    return _parse_feed(fixture_path.read_text(encoding="utf-8"))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="WeWorkRemotely RSS source adapter.")
    parser.add_argument("--max-jobs", type=int, default=200)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture)
    else:
        jobs = fetch(max_jobs=args.max_jobs)

    out_path = args.out or (TMP_DIR / f"weworkremotely_{uuid.uuid4().hex[:8]}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for job in jobs:
            line = job.model_dump_json()
            f.write(line + "\n")
            try:
                sys.stdout.write(line + "\n")
            except UnicodeEncodeError:
                sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    logger.info("weworkremotely: wrote %d to %s", len(jobs), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
