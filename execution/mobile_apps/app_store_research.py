"""
app_store_research.py
description: Firecrawl wrapper for App Store Optimization (ASO) research. Searches the App Store or Play Store for a keyword (or a single competitor+store pair), scrapes the top-10 listings via Firecrawl's REST API with markdown format, parses out app name + rating + description, and returns the result as JSON on stdout. Supports parallel fan-out via ThreadPoolExecutor for multi-competitor batch runs.
inputs: CLI: --query "<keyword>", --store <appstore|playstore>, --limit <int> (default 10), --max-workers <int> (default 8); OR --competitors-file <csv_path> --stores ios android for batch mode; env: FIRECRAWL_API_KEY
outputs: JSON array of {name, rating, description, url} to stdout (single-query mode), or JSON {results: [...], scraped_count, skipped_count} (batch mode)
usage:
    # Single query:
    py execution/mobile_apps/app_store_research.py --query "meditation timer" --store appstore
    py execution/mobile_apps/app_store_research.py --query "habit tracker" --store playstore --limit 5

    # Batch (competitors CSV with columns: name, ios_id (optional), android_id (optional)):
    py execution/mobile_apps/app_store_research.py --competitors-file competitors.csv --stores ios android

    # Dynamic Workflow fan-out (per-cell, called by aso-research workflow):
    py execution/mobile_apps/app_store_research.py --query "Headspace" --store appstore --single
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("app_store_research")

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"
APPSTORE_DIRECT_SEARCH = "https://apps.apple.com/us/search?term={q}"
PLAYSTORE_SEARCH = "https://play.google.com/store/search?q={q}&c=apps"

# Loose regexes to extract app name + rating from the scraped markdown.
RATING_RE = re.compile(r"(\d\.\d)\s*(?:out of 5|★|stars?)", re.IGNORECASE)

# Normalize store aliases from CLI to internal keys.
_STORE_ALIAS = {
    "appstore": "appstore",
    "ios": "appstore",
    "playstore": "playstore",
    "android": "playstore",
}


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
    resp = requests.post(
        f"{FIRECRAWL_BASE}/scrape", headers=headers, json=body, timeout=60
    )
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


def _research_one(
    api_key: str, competitor: str, store: str, limit: int
) -> dict:
    """Scrape one (competitor, store) cell. Returns a result dict or raises."""
    store_key = _STORE_ALIAS.get(store, store)
    url = search_url(store_key, competitor)
    log.info("Scraping [%s / %s] -> %s", competitor, store_key, url)
    scrape = firecrawl_scrape(api_key, url)
    data = scrape.get("data", scrape)
    markdown = data.get("markdown") or ""
    if not markdown:
        raise RuntimeError(f"Firecrawl returned empty markdown for {url}")
    listings = parse_listings(markdown, store_key, limit)
    return {
        "competitor": competitor,
        "store": store_key,
        "count": len(listings),
        "results": listings,
    }


def run_batch(
    api_key: str,
    competitors: list[str],
    stores: list[str],
    limit: int,
    max_workers: int,
) -> dict:
    """Fan-out per (competitor, store) via ThreadPoolExecutor.

    Uses a threading.Lock on the shared results list (rule 2 hardening).
    Each cell is isolated — failure logs + skips, never halts the batch.
    """
    cells = [(c, s) for c in competitors for s in stores]
    results: list[dict] = []
    skipped: list[dict] = []
    _lock = threading.Lock()

    def _worker(competitor: str, store: str) -> None:
        try:
            cell_result = _research_one(api_key, competitor, store, limit)
            with _lock:
                results.append(cell_result)
        except Exception as exc:  # noqa: BLE001 — per-cell isolation; we log and skip
            log.warning(
                "SKIP [%s / %s]: %s", competitor, store, exc
            )
            with _lock:
                skipped.append({
                    "competitor": competitor,
                    "store": store,
                    "reason": str(exc),
                })

    log.info(
        "Batch: %d competitors × %d stores = %d cells (max_workers=%d)",
        len(competitors), len(stores), len(cells), max_workers,
    )
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_worker, c, s): (c, s) for c, s in cells
        }
        for fut in as_completed(futures):
            # Exceptions are handled inside _worker; surface unexpected ones.
            exc = fut.exception()
            if exc is not None:
                log.error("Unexpected future error: %s", exc)

    return {
        "scraped_count": len(results),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ASO research — scrape App Store / Play Store for competitor data."
    )

    # Single-query mode (original + per-cell dynamic workflow invocation).
    parser.add_argument("--query", help="Search keyword (single-query mode).")
    parser.add_argument(
        "--store",
        choices=list(_STORE_ALIAS.keys()),
        help="Store to query: appstore/ios or playstore/android.",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Per-cell mode: run one (--query, --store) pair. Used by the aso-research Dynamic Workflow.",
    )

    # Batch mode.
    parser.add_argument(
        "--competitors-file",
        help="CSV with columns: name[, ios_id, android_id]. Triggers batch mode.",
    )
    parser.add_argument(
        "--stores",
        nargs="+",
        choices=list(_STORE_ALIAS.keys()),
        default=["appstore", "playstore"],
        help="Stores to query in batch mode (default: both). Aliases: ios=appstore, android=playstore.",
    )

    # Shared flags.
    parser.add_argument(
        "--limit", type=int, default=10, help="Top-N results per cell (default 10)."
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Parallel Firecrawl workers in batch mode (default 8; Firecrawl rate-limits).",
    )

    args = parser.parse_args()

    api_key = require_env("FIRECRAWL_API_KEY")

    # ── Batch mode (--competitors-file) ──────────────────────────────────────
    if args.competitors_file:
        csv_path = Path(args.competitors_file).resolve()
        if not csv_path.is_file():
            print(f"ERROR: --competitors-file not found: {csv_path}", file=sys.stderr)
            return 1
        competitors: list[str] = []
        with open(csv_path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                name = (row.get("name") or "").strip()
                if name:
                    competitors.append(name)
        if not competitors:
            print("ERROR: no competitor names found in CSV.", file=sys.stderr)
            return 1
        # Normalize store aliases.
        stores = [_STORE_ALIAS.get(s, s) for s in args.stores]
        stores = list(dict.fromkeys(stores))  # dedupe, preserve order
        batch_result = run_batch(
            api_key, competitors, stores, args.limit, args.max_workers
        )
        print(json.dumps(batch_result, indent=2, ensure_ascii=False))
        return 0 if batch_result["skipped_count"] == 0 else 2

    # ── Single-query / per-cell mode (--query + --store) ─────────────────────
    if not args.query or not args.store:
        parser.error(
            "Either --competitors-file (batch) or both --query and --store (single) are required."
        )

    store_key = _STORE_ALIAS.get(args.store, args.store)
    try:
        result = _research_one(api_key, args.query, store_key, args.limit)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
