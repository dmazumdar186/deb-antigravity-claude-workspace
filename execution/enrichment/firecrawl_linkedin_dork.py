"""
description: Find LinkedIn profile URLs of product/HR contacts at a company using Firecrawl Google dorks (no direct LinkedIn scraping).
inputs:
  CLI: --company <name> (repeatable), --output <path> (optional)
  env: FIRECRAWL_API_KEY
outputs:
  stdout: JSON dict mapping company_name -> list of contact dicts
  file:   optional JSON file at --output path

Notes:
  - Uses Firecrawl /search with site:linkedin.com/in Google dorks — does NOT hit LinkedIn directly.
  - Results are deduplicated by linkedin_url across all dorks for a given company.
  - Priority order for top-5 selection: cpo > vp_product > head_of_product > senior_pm > hr.
  - Adds a 1.0s inter-company sleep in bulk mode to be polite to Firecrawl rate limits.
  - Full-name and title extraction is heuristic (LinkedIn title format varies); falls back gracefully.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Project path bootstrap
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import (  # noqa: E402
    now_iso,
    retry_with_backoff,
    save_json,
    setup_logging,
)

logger = setup_logging("firecrawl_linkedin_dork")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Dork definitions: (seniority_label, query_template)
# {company} placeholder is replaced at runtime with a quoted company name.
_DORKS: list[tuple[str, str]] = [
    ("cpo",             'site:linkedin.com/in "Chief Product Officer" {company_quoted}'),
    ("vp_product",      'site:linkedin.com/in "VP Product" {company_quoted}'),
    ("head_of_product", 'site:linkedin.com/in "Head of Product" {company_quoted}'),
    ("senior_pm",       'site:linkedin.com/in "Senior Product Manager" {company_quoted}'),
    ("hr",              'site:linkedin.com/in ("HR" OR "Talent Acquisition") {company_quoted}'),
]

# Priority order for deduped top-N selection
_SENIORITY_PRIORITY = ["cpo", "vp_product", "head_of_product", "senior_pm", "hr"]

_LINKEDIN_IN_RE = re.compile(
    r"^https?://(www\.)?linkedin\.com/in/[^/?#]+/?($|[?#])", re.IGNORECASE
)

_SEARCH_LIMIT_PER_DORK = 2


# ---------------------------------------------------------------------------
# Firecrawl client (lazy init)
# ---------------------------------------------------------------------------

def _get_firecrawl_app():
    """Return a FirecrawlApp instance, or None if FIRECRAWL_API_KEY is absent."""
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        logger.warning(
            "firecrawl_linkedin_dork: FIRECRAWL_API_KEY not set — cannot perform searches"
        )
        return None
    try:
        from firecrawl import FirecrawlApp
        return FirecrawlApp(api_key=api_key)
    except ImportError:
        logger.warning(
            "firecrawl_linkedin_dork: firecrawl package not installed — run: pip install firecrawl-py"
        )
        return None


# ---------------------------------------------------------------------------
# Dork string builder
# ---------------------------------------------------------------------------

def _build_dork(template: str, company_name: str) -> str:
    """Insert a properly quoted company name into a dork template.

    Escapes any embedded double-quotes in the company name with backslash.
    """
    escaped = company_name.replace('"', '\\"')
    company_quoted = f'"{escaped}"'
    return template.format(company_quoted=company_quoted)


# ---------------------------------------------------------------------------
# LinkedIn URL validation
# ---------------------------------------------------------------------------

def _is_valid_linkedin_in_url(url: str) -> bool:
    return bool(_LINKEDIN_IN_RE.match(url))


# ---------------------------------------------------------------------------
# Title / name parsing
# ---------------------------------------------------------------------------

def _parse_title_field(raw_title: str, fallback_seniority: str) -> tuple[str, str | None]:
    """Parse a LinkedIn search result title into (full_name, job_title).

    LinkedIn titles typically look like one of:
        "Jane Doe - Chief Product Officer at AcmeCo - LinkedIn"
        "Jane Doe | Chief Product Officer | AcmeCo"
        "Jane Doe – VP Product at AcmeCo"

    Strategy:
        1. Strip trailing " - LinkedIn" or " | LinkedIn".
        2. Split on " - " or " | " (whichever appears first).
        3. Segment[0] → full_name (strip).
        4. Segment[1] → job_title if it exists (strip).
        5. Fall back to seniority label if parsing yields nothing useful.
    """
    if not raw_title:
        return ("", None)

    # Normalise separators for LinkedIn variants
    cleaned = re.sub(r"\s*[–—]\s*", " - ", raw_title)  # em/en dash → " - "
    # Strip trailing "- LinkedIn" or "| LinkedIn"
    cleaned = re.sub(r"[\s\-|]+LinkedIn\s*$", "", cleaned, flags=re.IGNORECASE).strip()

    # Determine primary separator
    sep = None
    pos_dash = cleaned.find(" - ")
    pos_pipe = cleaned.find(" | ")
    if pos_dash >= 0 and pos_pipe >= 0:
        sep = " - " if pos_dash <= pos_pipe else " | "
    elif pos_dash >= 0:
        sep = " - "
    elif pos_pipe >= 0:
        sep = " | "

    if sep is None:
        # No separator found; treat the whole string as the name
        return (cleaned.strip(), None)

    segments = [s.strip() for s in cleaned.split(sep)]
    full_name = segments[0] if segments else ""
    job_title: str | None = segments[1] if len(segments) > 1 else None

    # If job_title looks like a company name only (e.g., no spaces), keep as-is;
    # if it's empty, fall back to seniority label.
    if not job_title:
        job_title = fallback_seniority

    return (full_name, job_title)


# ---------------------------------------------------------------------------
# Single dork search (decorated for retry)
# ---------------------------------------------------------------------------

@retry_with_backoff(max_retries=3)
def _run_search(app, dork_query: str) -> list[dict]:
    """Call Firecrawl search and return the data list.

    Raises on Firecrawl SDK errors so retry_with_backoff can handle transient failures.
    The Firecrawl SDK may raise requests.HTTPError or a Firecrawl-specific exception.
    """
    result = app.search(dork_query, limit=_SEARCH_LIMIT_PER_DORK)
    return result.get("data", []) if isinstance(result, dict) else []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_contacts_for_company(company_name: str, *, max_total: int = 5) -> list[dict]:
    """Find up to max_total LinkedIn contacts for a company using Google dorks via Firecrawl.

    Returns a list of dicts:
        {'full_name': str, 'title': str|None, 'seniority': str,
         'linkedin_url': str, 'source': 'firecrawl_dork'}

    Returns [] if FIRECRAWL_API_KEY is missing or all searches fail.
    """
    app = _get_firecrawl_app()
    if app is None:
        return []

    # Collect results grouped by seniority, deduplicated by URL
    seen_urls: set[str] = set()
    by_seniority: dict[str, list[dict]] = {s: [] for s in _SENIORITY_PRIORITY}

    for seniority, template in _DORKS:
        dork_query = _build_dork(template, company_name)
        logger.debug("firecrawl_dork: searching [%s] for %r", seniority, company_name)

        try:
            items = _run_search(app, dork_query)
        except Exception as exc:
            logger.warning(
                "firecrawl_dork: search failed for company=%r seniority=%s — %s",
                company_name, seniority, exc,
            )
            continue

        for item in items:
            url = (item.get("url") or "").strip()
            if not _is_valid_linkedin_in_url(url):
                continue
            # Normalise URL to bare profile path for dedup
            dedup_key = url.rstrip("/").split("?")[0].split("#")[0].lower()
            if dedup_key in seen_urls:
                continue
            seen_urls.add(dedup_key)

            raw_title = item.get("title") or ""
            full_name, job_title = _parse_title_field(raw_title, seniority)

            by_seniority[seniority].append({
                "full_name": full_name,
                "title": job_title,
                "seniority": seniority,
                "linkedin_url": url,
                "source": "firecrawl_dork",
            })

    # Merge in priority order, cap at max_total
    contacts: list[dict] = []
    for seniority in _SENIORITY_PRIORITY:
        for contact in by_seniority[seniority]:
            if len(contacts) >= max_total:
                break
            contacts.append(contact)
        if len(contacts) >= max_total:
            break

    logger.info(
        "firecrawl_dork: found %d contact(s) for %r", len(contacts), company_name
    )
    return contacts


def find_contacts_bulk(
    company_names: list[str],
    *,
    max_total_per_company: int = 5,
) -> dict[str, list[dict]]:
    """Batch wrapper for find_contacts_for_company.

    Sleeps 1.0s between companies to respect Firecrawl rate limits.
    Returns a dict keyed by company_name.
    """
    results: dict[str, list[dict]] = {}
    for idx, company_name in enumerate(company_names):
        if idx > 0:
            time.sleep(1.0)
        results[company_name] = find_contacts_for_company(
            company_name, max_total=max_total_per_company
        )
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Find LinkedIn contacts for French companies using Firecrawl Google dorks. "
            "Targets: CPO, VP Product, Head of Product, Senior PM, HR/Talent."
        )
    )
    parser.add_argument(
        "--company",
        dest="companies",
        action="append",
        required=True,
        metavar="COMPANY_NAME",
        help="Company name to search contacts for. Repeat --company for multiple.",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default=None,
        metavar="PATH",
        help="Optional path to write results as JSON.",
    )
    parser.add_argument(
        "--max",
        dest="max_total",
        type=int,
        default=5,
        metavar="N",
        help="Max contacts per company (default: 5).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    results = find_contacts_bulk(args.companies, max_total_per_company=args.max_total)

    output_payload = {
        "run_at": now_iso(),
        "results": results,
    }

    json_str = json.dumps(output_payload, indent=2, ensure_ascii=False, default=str)
    print(json_str)

    if args.output:
        save_json(output_payload, Path(args.output))
        logger.info("firecrawl_dork: results written to %s", args.output)


if __name__ == "__main__":
    main()
