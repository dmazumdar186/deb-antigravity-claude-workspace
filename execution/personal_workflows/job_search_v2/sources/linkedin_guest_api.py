"""
description: LinkedIn jobs-guest (public unauthenticated) API source adapter. Hits the
    same endpoint LinkedIn serves to logged-out browsers — no OAuth, no login, no Gmail
    middleman. Replaces the brittle Gmail-alert-parsing approach in linkedin_gmail.py.
inputs:
  - CLI: --keywords (comma-separated; default = PM Paris set), --geo-id (default IDF),
         --max-pages-per-keyword, --posted-within-hours, --fixture
  - env: none (the jobs-guest API needs no credentials)
outputs:
  - stdout: JSON-lines of SourceJob records
  - .tmp/job_search_v2/linkedin_guest_api_<run_id>.jsonl (when run standalone)

Architecture cribbed (MIT) from sivad259-alt/job-scanner:
    https://github.com/sivad259-alt/job-scanner — jobscanner/linkedin_jobs/
Adapted to: our SourceJob contract, PM-Paris keyword set, IDF geoId default.

Why this exists: the prior `linkedin_gmail.py` requires user-side Gmail label + filter +
alert subscription + IMAP App Password, and produces ~4 jobs/day at best because
LinkedIn alerts are throttled. The jobs-guest API returns fresh search results directly
and supports many keyword variants per run, so volume scales with the keyword set.

Endpoints (public, no auth):
  - Search: linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
  - Detail: linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}
    (Detail fetch is NOT used in this MVP — the search cards carry enough for ranking.
    Add later if the ranker needs full JD text.)

Anti-bot posture: gentle. Self-throttle 1-2s/page; back off on 429/999; hard-stop on
block markers (captcha/checkpoint/verify) so we don't hammer a credential-rotated state.
"""

from __future__ import annotations

import argparse
import logging
import random
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("linkedin_guest_api")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL_FMT = "https://www.linkedin.com/jobs/view/{job_id}"  # canonical public page

# LinkedIn geoIds (looked up on linkedin.com/jobs and stable for years):
#   France                = 105015875
#   Paris (city)          = 104196728
#   Île-de-France (region)= 104246759   <-- default; broader than Paris alone, fits a PM
DEFAULT_GEO_ID = "104246759"

# PM keywords across FR / DE / BE / CH. English + French cover most posts even outside
# France; the German, Dutch, and Italian variants pick up jobs the English search
# would miss in DE / CH-Deutschschweiz / BE-Flanders / CH-Ticino respectively. Each
# entry is a separate search request; cross-keyword overlap dedups by jobId for free.
DEFAULT_KEYWORDS = [
    # --- AI tabs FIRST so they reach LinkedIn before the per-region block
    # threshold (~25 calls/region on 2026-06-24's run). Keyword reordering done
    # 2026-06-24 evening — previously the AI keywords were at the bottom and the
    # CH-region block triggered after the PM block, leaving AI tabs empty. ---
    "AI automation engineer",
    "AI automation specialist",
    "AI automation consultant",
    "AI engineer",
    "AI consultant",
    "AI strategy consultant",
    "AI transformation consultant",
    "AI solutions consultant",
    "AI process automation",
    "process automation engineer",
    "process intelligence",
    "AI mobile developer",
    "mobile AI engineer",
    "automation product manager",
    # --- PM core (English, global) ---
    "product manager",
    "senior product manager",
    "lead product manager",
    "principal product manager",
    "head of product",
    "AI product manager",
    "product owner",
    # --- PM core (French) ---
    "chef de produit",
    "responsable produit",
    # --- PM core (German) ---
    "produktmanager",
    "senior produktmanager",
    "leiter produktmanagement",
    # --- PM core (Dutch) ---
    "productmanager",
    "product eigenaar",
    # --- PM core (Italian) ---
    "responsabile di prodotto",
]

# 48h window matches sivad259's pattern and gives the dedup layer enough new variety
# to make the daily digest interesting. f_TPR=r<seconds>.
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
    "Accept-Language": "en-US,en;q=0.9,fr-FR;q=0.8",
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
    """Fetch one search-results page. Returns HTML or None for empty/transient.

    Raises LinkedInBlockedError on a hard block (captcha/checkpoint) so the caller
    stops instead of hammering.
    """
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
            raise LinkedInBlockedError(
                "LinkedIn block marker in response (captcha/checkpoint/verify)."
            )
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
        posted_iso = ""
        if time_el:
            posted_iso = time_el.get("datetime") or ""
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
            description_snippet="",  # search cards don't carry JD text; ranker uses title+company
            posted_at=posted_at,
            contract_type_raw="",
        )
    except (KeyError, ValueError) as exc:
        logger.warning("linkedin_guest_api: skip card (parse error): %s", exc)
        return None


def fetch(
    keywords: Optional[list[str]] = None,
    geo_id: str = DEFAULT_GEO_ID,
    posted_within_hours: int = DEFAULT_POSTED_WITHIN_HOURS,
    max_pages_per_keyword: int = 4,
) -> list[SourceJob]:
    """Run a search per keyword, merge by jobId, return list[SourceJob].

    Per-keyword pagination stops early on a streak of empty pages so a low-volume
    keyword doesn't waste requests. A LinkedInBlockedError aborts the whole run
    immediately (don't hammer a credential-rotated state).
    """
    keywords = keywords or DEFAULT_KEYWORDS
    f_tpr = f"r{posted_within_hours * 3600}"
    seen_ids: set[str] = set()
    out: list[SourceJob] = []

    with httpx.Client(headers=HEADERS) as client:
        for kw in keywords:
            empty_streak = 0
            for page_idx in range(max_pages_per_keyword):
                start = page_idx * PAGE_STEP
                if start > PAGINATION_CAP:
                    break
                try:
                    html = _fetch_search_page(
                        client, kw, geo_id, start, f_tpr,
                        is_first_page=(page_idx == 0),
                    )
                except LinkedInBlockedError as exc:
                    logger.error("linkedin_guest_api: BLOCKED on keyword=%r start=%d — %s", kw, start, exc)
                    return out
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
                added = 0
                for card in cards:
                    jid = card["job_id"]
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    sj = _card_to_source_job(card)
                    if sj is not None:
                        out.append(sj)
                        added += 1
                logger.info("linkedin_guest_api: keyword=%r start=%d → %d cards, %d new", kw, start, len(cards), added)
                time.sleep(random.uniform(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX))
    return out


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: read a recorded search-results HTML page (one keyword's worth).

    Fixture shape: a single HTML file from one /seeMoreJobPostings/search response.
    Used by the parser test (renamed from front_door — per 2026-06-18 tightening,
    fixture tests live under parser_/unit_ names, not front_door_).
    """
    if not fixture_path.exists():
        return []
    html = fixture_path.read_text(encoding="utf-8")
    out: list[SourceJob] = []
    for card in _parse_cards(html):
        sj = _card_to_source_job(card)
        if sj is not None:
            out.append(sj)
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="LinkedIn jobs-guest API source adapter.")
    parser.add_argument("--keywords", default="", help="Comma-separated keyword list. Empty = use DEFAULT_KEYWORDS.")
    parser.add_argument("--geo-id", default=DEFAULT_GEO_ID, help=f"LinkedIn geoId (default {DEFAULT_GEO_ID}=IDF).")
    parser.add_argument("--posted-within-hours", type=int, default=DEFAULT_POSTED_WITHIN_HOURS)
    parser.add_argument("--max-pages-per-keyword", type=int, default=4)
    parser.add_argument("--fixture", type=Path, help="Read from an HTML fixture instead of live.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture)
        logger.info("linkedin_guest_api: %d jobs from fixture", len(jobs))
    else:
        kw_list = [k.strip() for k in args.keywords.split(",") if k.strip()] or None
        try:
            jobs = fetch(
                keywords=kw_list,
                geo_id=args.geo_id,
                posted_within_hours=args.posted_within_hours,
                max_pages_per_keyword=args.max_pages_per_keyword,
            )
        except LinkedInBlockedError as exc:
            logger.error("linkedin_guest_api: aborted — %s", exc)
            return 1
        logger.info("linkedin_guest_api: %d jobs from live API", len(jobs))

    out_path = args.out or (TMP_DIR / f"linkedin_guest_api_{uuid.uuid4().hex[:8]}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for job in jobs:
            line = job.model_dump_json()
            f.write(line + "\n")
            try:
                sys.stdout.write(line + "\n")
            except UnicodeEncodeError:
                sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    logger.info("linkedin_guest_api: wrote %d to %s", len(jobs), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
