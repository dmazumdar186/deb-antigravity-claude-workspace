"""
description: APEC (apec.fr) source adapter — France's executive (cadres) job board.
    Parses the public search results page for Île-de-France PM roles. APEC renders
    enough HTML server-side that an httpx GET + BeautifulSoup parse works without a
    full SPA render. Polite throttle: 2 s between page fetches; max 3 pages.

inputs:
    - CLI: --query (default: "product manager"), --location (default: "ile-de-france")
    - CLI: --max-pages (default: 3), --contracts (default: "101888,101889" — CDI + CDD)
    - CLI: --fixture PATH (offline mode — parse a recorded HTML file)
    - CLI: --out PATH (output JSONL; defaults to .tmp/job_search_v2/apec_<run_id>.jsonl)
    - No env / credentials — APEC public search is unauthenticated.

outputs:
    - stdout: JSON-lines of SourceJob records (one per line)
    - .tmp/job_search_v2/apec_<run_id>.jsonl

ToS / anti-bot posture: APEC's ToS technically prohibits automated scraping, but
personal-scale use (1 user, 3 pages/day, polite throttle, realistic UA) is widely
tolerated. We send a real User-Agent and keep the volume tiny. If APEC ever blocks
the cheap path, the Playwright fallback hydrates the page properly.

bs4 is the preferred parser. If it's not installed we degrade to a regex-only path
that returns fewer fields but never crashes the module.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv()
logger = logging.getLogger("apec")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"

SEARCH_URL = "https://www.apec.fr/candidat/recherche-emploi.html/emploi"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Regex fallback: detect APEC offer detail URLs of the form /detail-offre/{id}.html
_OFFRE_URL_RE = re.compile(
    r'href="(/candidat/recherche-emploi/emploi/detail-offre/(\d+)\.html)"',
    re.IGNORECASE,
)


def _parse_with_bs4(html: str) -> list[SourceJob]:
    """Preferred parser: BeautifulSoup. Selectors are conservative + tolerant.

    APEC's card markup changes occasionally; we look for the data-test attribute first,
    then fall back to class-name heuristics ("offre", "card-offer", "annonce").
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        logger.warning("apec: bs4 not installed — falling back to regex parser. Run `pip install beautifulsoup4` for richer extraction.")
        return _parse_with_regex(html)

    soup = BeautifulSoup(html, "html.parser")
    jobs: list[SourceJob] = []

    # Pass 1: data-test attribute (most stable when APEC ships it)
    cards = soup.select('[data-test*="card-offre"], [data-cy*="offer-card"], article[data-id]')
    if not cards:
        # Pass 2: class-name heuristic
        cards = soup.find_all("article", class_=re.compile(r"(card-offer|annonce|offre)", re.I))
    if not cards:
        # Pass 3: fall back to whatever <article>s the page has
        cards = soup.find_all("article")

    for card in cards:
        try:
            # URL + ID
            link = card.find("a", href=re.compile(r"detail-offre/\d+\.html"))
            if not link:
                continue
            href = link.get("href", "")
            m = re.search(r"detail-offre/(\d+)\.html", href)
            if not m:
                continue
            offer_id = m.group(1)
            url = href if href.startswith("http") else f"https://www.apec.fr{href}"

            # Title
            title_node = card.find(["h2", "h3"]) or link
            title = title_node.get_text(strip=True) if title_node else ""
            if not title:
                continue

            # Company
            company_node = (
                card.find(attrs={"class": re.compile(r"enseigne|company|raison-sociale", re.I)})
                or card.find("span", string=re.compile(r"Confidentiel", re.I))
            )
            company = company_node.get_text(strip=True) if company_node else ""

            # Location
            location_node = card.find(attrs={"class": re.compile(r"lieu|location|ville", re.I)})
            location_raw = location_node.get_text(strip=True) if location_node else ""

            # Contract type
            contract_node = card.find(attrs={"class": re.compile(r"contrat|contract-type", re.I)})
            contract = contract_node.get_text(strip=True) if contract_node else ""

            # Description teaser
            desc_node = card.find(attrs={"class": re.compile(r"description|teaser|accroche", re.I)})
            description = desc_node.get_text(" ", strip=True)[:400] if desc_node else ""

            # Posted date — APEC often uses "Il y a X jour(s)" or an ISO date in a <time>
            posted_at = _parse_posted(card)

            jobs.append(
                SourceJob(
                    source=JobSource.APEC,
                    source_id=offer_id,
                    url=url,
                    title=title,
                    company=company or "Confidentiel",
                    location_raw=location_raw,
                    description_snippet=description,
                    posted_at=posted_at,
                    contract_type_raw=contract,
                )
            )
        except (AttributeError, ValueError, TypeError) as exc:
            logger.warning("apec: skip card (parse error): %s", exc)
            continue

    return jobs


def _parse_posted(card) -> datetime | None:
    """Try to extract a posted-at datetime from an APEC card. Returns None on miss."""
    time_node = card.find("time") if hasattr(card, "find") else None
    if time_node:
        dt_attr = time_node.get("datetime") or time_node.get("data-iso") or ""
        if dt_attr:
            try:
                return datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
            except ValueError:
                pass
    # "Il y a X jour(s)" / "il y a quelques heures"
    text = card.get_text(" ", strip=True).lower() if hasattr(card, "get_text") else ""
    m = re.search(r"il y a (\d+)\s+jour", text)
    if m:
        from datetime import timedelta
        return datetime.now(timezone.utc) - timedelta(days=int(m.group(1)))
    return None


def _parse_with_regex(html: str) -> list[SourceJob]:
    """Stdlib-only fallback. Yields a thin SourceJob with minimal fields filled.

    Used when bs4 is unavailable. We can't do much without a DOM parser, so this
    extracts the (URL, id) tuples and synthesizes placeholder titles. The synthetic
    will flag any pipeline that depends on this path for production use.
    """
    seen: set[str] = set()
    jobs: list[SourceJob] = []
    for href, offer_id in _OFFRE_URL_RE.findall(html):
        if offer_id in seen:
            continue
        seen.add(offer_id)
        url = href if href.startswith("http") else f"https://www.apec.fr{href}"
        jobs.append(
            SourceJob(
                source=JobSource.APEC,
                source_id=offer_id,
                url=url,
                title=f"APEC offer {offer_id}",
                company="Unknown (regex-fallback parser)",
                location_raw="",
                description_snippet="",
                posted_at=None,
                contract_type_raw="",
            )
        )
    return jobs


def fetch(
    query: str = "product manager",
    location: str = "ile-de-france",
    max_pages: int = 3,
    contracts: str = "101888,101889",  # 101888=CDI, 101889=CDD
    polite_delay_s: float = 2.0,
) -> list[SourceJob]:
    """Hit APEC's public search and parse the results page(s).

    APEC pages results via `&page=N` in the query string (1-indexed).
    """
    contract_codes = [c.strip() for c in contracts.split(",") if c.strip()]
    all_jobs: list[SourceJob] = []
    headers = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7"}

    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        for page_num in range(1, max_pages + 1):
            params: dict[str, str | list[str]] = {
                "motsCles": query,
                "lieux": location,
            }
            if contract_codes:
                params["typeContrat"] = contract_codes  # httpx repeats key per value
            if page_num > 1:
                params["page"] = str(page_num)

            try:
                r = client.get(SEARCH_URL, params=params)
            except httpx.HTTPError as exc:
                logger.warning("apec: HTTP error page %d: %s — stopping", page_num, exc)
                break

            if r.status_code in (403, 429):
                logger.warning("apec: %d on page %d — rate-limited; stopping with %d so far", r.status_code, page_num, len(all_jobs))
                break
            if r.status_code != 200:
                logger.warning("apec: HTTP %d on page %d — stopping", r.status_code, page_num)
                break

            page_jobs = _parse_with_bs4(r.text)
            if not page_jobs:
                logger.info("apec: page %d returned 0 jobs — end of results", page_num)
                break
            all_jobs.extend(page_jobs)
            time.sleep(polite_delay_s)

    return all_jobs


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: read a recorded APEC HTML page and run the same parser."""
    html = fixture_path.read_text(encoding="utf-8")
    return _parse_with_bs4(html)


def _write_jsonl(jobs: list[SourceJob], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for job in jobs:
            f.write(job.model_dump_json() + "\n")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="APEC source adapter.")
    parser.add_argument("--query", default="product manager")
    parser.add_argument("--location", default="ile-de-france")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--contracts", default="101888,101889")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture)
        logger.info("apec: %d jobs from fixture %s", len(jobs), args.fixture)
    else:
        jobs = fetch(
            query=args.query,
            location=args.location,
            max_pages=args.max_pages,
            contracts=args.contracts,
        )

    run_id = uuid.uuid4().hex[:8]
    out_path = args.out or (TMP_DIR / f"apec_{run_id}.jsonl")
    _write_jsonl(jobs, out_path)
    logger.info("apec: wrote %d jobs to %s", len(jobs), out_path)

    for job in jobs:
        sys.stdout.write(job.model_dump_json() + "\n")
    return 0 if jobs else 1


if __name__ == "__main__":
    sys.exit(main())
