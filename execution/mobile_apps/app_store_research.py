"""
app_store_research.py
description: Thin Firecrawl wrapper for App Store Optimization (ASO) research. Searches the App Store or Play Store for a keyword, scrapes the top-10 listings via Firecrawl's REST API with markdown format, parses out app name + rating + description, and returns the result as JSON on stdout.
inputs: CLI: --query "<keyword>", --store <appstore|playstore>, --limit <int> (default 10); env: FIRECRAWL_API_KEY
outputs: JSON array of {name, rating, description, url} to stdout
usage:
    py execution/mobile_apps/app_store_research.py --query "meditation timer" --store appstore
    py execution/mobile_apps/app_store_research.py --query "habit tracker" --store playstore --limit 5
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"
APPSTORE_SEARCH_URL = "https://www.apple.com/us/search/{q}?src=globalnav"  # neutral entry; we use App Store search
APPSTORE_DIRECT_SEARCH = "https://apps.apple.com/us/search?term={q}"
PLAYSTORE_SEARCH = "https://play.google.com/store/search?q={q}&c=apps"

# Loose regexes to extract app name + rating from the scraped markdown.
RATING_RE = re.compile(r"(\d\.\d)\s*(?:out of 5|★|stars?)", re.IGNORECASE)


def require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise SystemExit(
            f"ERROR: {key} not set. Add it to .env "
            "(get one from https://firecrawl.dev/)"
        )
    return val


def firecrawl_scrape(api_key: str, url: str) -> dict:
    """Call POST /v1/scrape with markdown format. Returns parsed JSON body."""
    if requests is None:
        raise SystemExit("ERROR: `requests` not installed. Run: pip install requests")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
    }
    resp = requests.post(f"{FIRECRAWL_BASE}/scrape", headers=headers,
                         json=body, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Firecrawl scrape {url} -> {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()


def search_url(store: str, query: str) -> str:
    q = quote_plus(query)
    if store == "appstore":
        return APPSTORE_DIRECT_SEARCH.format(q=q)
    if store == "playstore":
        return PLAYSTORE_SEARCH.format(q=q)
    raise ValueError(f"unknown store: {store}")


def parse_listings(markdown: str, store: str, limit: int) -> list[dict]:
    """Heuristically pull out listing entries from a search-page markdown blob.

    The exact structure varies by store and Firecrawl-version, so we do a
    permissive markdown link scan ([Title](url)) and filter to plausible app
    pages, then look for a nearby rating substring.
    """
    listings: list[dict] = []
    seen: set[str] = set()
    link_re = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        for m in link_re.finditer(line):
            title = m.group(1).strip()
            url = m.group(2).strip()
            if url in seen:
                continue
            if store == "appstore" and "/app/" not in url:
                continue
            if store == "playstore" and "/store/apps/details" not in url:
                continue
            # Scan +/- 3 lines for rating context.
            window = "\n".join(lines[max(0, i - 1): i + 4])
            rating_match = RATING_RE.search(window)
            rating = rating_match.group(1) if rating_match else None
            # Short description = next non-empty line after the link.
            desc = ""
            for nxt in lines[i + 1: i + 6]:
                nxt = nxt.strip()
                if nxt and not nxt.startswith(("#", "!", "[", "-")):
                    desc = nxt
                    break
            listings.append({
                "name": title,
                "rating": rating,
                "description": desc,
                "url": url,
            })
            seen.add(url)
            if len(listings) >= limit:
                return listings
    return listings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--query", required=True, help="Search keyword.")
    parser.add_argument("--store", required=True, choices=["appstore", "playstore"])
    parser.add_argument("--limit", type=int, default=10, help="Top-N results (default 10).")
    args = parser.parse_args()

    api_key = require_env("FIRECRAWL_API_KEY")
    url = search_url(args.store, args.query)
    print(f"app_store_research: scraping {url}", file=sys.stderr)

    try:
        scrape = firecrawl_scrape(api_key, url)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    data = scrape.get("data", scrape)
    markdown = data.get("markdown") or ""
    if not markdown:
        print("ERROR: Firecrawl returned empty markdown.", file=sys.stderr)
        return 1

    listings = parse_listings(markdown, args.store, args.limit)
    print(json.dumps({
        "query": args.query,
        "store": args.store,
        "count": len(listings),
        "results": listings,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
