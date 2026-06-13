"""Per-source fetchers for anthropic_watch.

Each fetcher returns a list of dicts:
    {"url": str, "title": str, "source": str, "published": str|None, "raw_excerpt": str}

Failures are soft: a source that errors logs a WARN line and returns [].
Empty results log WARN explicitly so the operator can disambiguate scrape-failure
from no-new-items.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Callable

log = logging.getLogger("anthropic_watch.fetch")

# All Firecrawl scrapes are routed through the MCP-installed CLI / REST API via
# `requests`. We do NOT call the MCP tool directly here — this script runs
# standalone via `py run.py`, not inside a Claude session. Use the REST API.

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v2/scrape"


def _firecrawl_scrape(url: str, wait_for_ms: int = 0) -> str:
    """POST to Firecrawl /v2/scrape and return markdown. Raises on HTTP error."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY not set in environment")

    payload: dict = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    if wait_for_ms:
        payload["waitFor"] = wait_for_ms

    req = urllib.request.Request(
        FIRECRAWL_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("success"):
        raise RuntimeError(f"firecrawl scrape failed: {body!r}")
    return body.get("data", {}).get("markdown", "")


def _log_count(source: str, items: list) -> list:
    if not items:
        log.warning("%s returned 0 items", source)
    else:
        log.info("%s fetched %d items", source, len(items))
    return items


# ---------------------------------------------------------------------------
# Source: Anthropic news (JS-rendered Next.js — needs waitFor)
# ---------------------------------------------------------------------------

def fetch_anthropic_news() -> list[dict]:
    source = "anthropic.com/news"
    try:
        md = _firecrawl_scrape("https://www.anthropic.com/news", wait_for_ms=2000)
    except Exception as err:
        log.warning("%s scrape failed: %s", source, err)
        return _log_count(source, [])

    # Anthropic's news page renders as a markdown list of articles. Each article
    # link looks like `[Title](https://www.anthropic.com/news/slug)`.
    pattern = re.compile(r"\[([^\]]{8,200})\]\((https://www\.anthropic\.com/news/[a-z0-9\-]+)\)")
    seen: set[str] = set()
    items: list[dict] = []
    for match in pattern.finditer(md):
        title, url = match.group(1).strip(), match.group(2).strip()
        if url in seen:
            continue
        seen.add(url)
        items.append({
            "url": url,
            "title": title,
            "source": source,
            "published": None,
            "raw_excerpt": title,
        })
    return _log_count(source, items)


# ---------------------------------------------------------------------------
# Source: docs.claude.com release notes + model deprecations
# ---------------------------------------------------------------------------

DOCS_MAX_ENTRIES = 15  # cap docs pages to most-recent N headings — they're top-down chronological


def _fetch_docs_page(url: str, source_label: str) -> list[dict]:
    try:
        md = _firecrawl_scrape(url, wait_for_ms=1500)
    except Exception as err:
        log.warning("%s scrape failed: %s", source_label, err)
        return _log_count(source_label, [])

    # Treat H2 headings as version entries (release-notes pages use H2 per version).
    # H3s are usually sub-sections within a version — noise for our purposes.
    heading_pat = re.compile(r"^##\s+(.+?)$", re.MULTILINE)
    items: list[dict] = []
    seen: set[str] = set()
    for match in heading_pat.finditer(md):
        title = match.group(1).strip()
        if len(title) < 4:
            continue
        if title.lower() in {"overview", "introduction", "contents", "table of contents", "on this page"}:
            continue
        anchor = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
        item_url = f"{url}#{anchor}"
        if item_url in seen:
            continue
        seen.add(item_url)
        items.append({
            "url": item_url,
            "title": title,
            "source": source_label,
            "published": None,
            "raw_excerpt": title,
        })
        if len(items) >= DOCS_MAX_ENTRIES:
            break
    return _log_count(source_label, items)


def fetch_docs_claude_code_release_notes() -> list[dict]:
    return _fetch_docs_page(
        "https://docs.claude.com/en/release-notes/claude-code",
        "docs.claude.com/claude-code",
    )


def fetch_docs_api_release_notes() -> list[dict]:
    return _fetch_docs_page(
        "https://docs.claude.com/en/release-notes/api",
        "docs.claude.com/api",
    )


def fetch_docs_model_deprecations() -> list[dict]:
    return _fetch_docs_page(
        "https://docs.claude.com/en/docs/about-claude/model-deprecations",
        "docs.claude.com/deprecations",
    )


# ---------------------------------------------------------------------------
# Source: npm registry for @anthropic-ai/claude-code
# ---------------------------------------------------------------------------

def fetch_npm_claude_code() -> list[dict]:
    source = "npm/@anthropic-ai/claude-code"
    try:
        with urllib.request.urlopen(
            "https://registry.npmjs.org/@anthropic-ai/claude-code",
            timeout=30,
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as err:
        log.warning("%s fetch failed: %s", source, err)
        return _log_count(source, [])

    versions = data.get("versions", {})
    times = data.get("time", {})
    # Take the 5 most recently published versions.
    sorted_versions = sorted(
        ((v, times.get(v)) for v in versions if v in times),
        key=lambda x: x[1] or "",
        reverse=True,
    )[:5]

    items: list[dict] = []
    for version, published in sorted_versions:
        items.append({
            "url": f"https://www.npmjs.com/package/@anthropic-ai/claude-code/v/{version}",
            "title": f"claude-code {version}",
            "source": source,
            "published": published,
            "raw_excerpt": f"npm release: @anthropic-ai/claude-code@{version} ({published})",
        })
    return _log_count(source, items)


# ---------------------------------------------------------------------------
# Source: GitHub releases (gh CLI primary, urllib fallback per skeptic #5)
# ---------------------------------------------------------------------------

def _fetch_github_releases(repo: str) -> list[dict]:
    source = f"github/{repo}"
    # Try gh first.
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/releases?per_page=5"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            releases = json.loads(result.stdout)
        else:
            raise RuntimeError(f"gh returned {result.returncode}: {result.stderr[:200]}")
    except (FileNotFoundError, RuntimeError, json.JSONDecodeError) as err:
        log.info("%s: falling back to urllib (gh failed: %s)", source, err)
        try:
            with urllib.request.urlopen(
                f"https://api.github.com/repos/{repo}/releases?per_page=5",
                timeout=30,
            ) as resp:
                releases = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as err2:
            log.warning("%s urllib fallback failed: %s", source, err2)
            return _log_count(source, [])

    items: list[dict] = []
    for rel in releases:
        name = rel.get("name") or rel.get("tag_name") or "untitled"
        body = rel.get("body", "") or ""
        items.append({
            "url": rel.get("html_url", ""),
            "title": f"{repo} {name}",
            "source": source,
            "published": rel.get("published_at"),
            "raw_excerpt": body[:1500],
        })
    return _log_count(source, items)


def fetch_github_claude_code() -> list[dict]:
    return _fetch_github_releases("anthropics/claude-code")


def fetch_github_sdk_python() -> list[dict]:
    return _fetch_github_releases("anthropics/anthropic-sdk-python")


def fetch_github_sdk_typescript() -> list[dict]:
    return _fetch_github_releases("anthropics/anthropic-sdk-typescript")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_FETCHERS: dict[str, Callable[[], list[dict]]] = {
    "anthropic-news": fetch_anthropic_news,
    "docs-claude-code": fetch_docs_claude_code_release_notes,
    "docs-api": fetch_docs_api_release_notes,
    "docs-deprecations": fetch_docs_model_deprecations,
    "npm-claude-code": fetch_npm_claude_code,
    "github-claude-code": fetch_github_claude_code,
    "github-sdk-python": fetch_github_sdk_python,
    "github-sdk-typescript": fetch_github_sdk_typescript,
}


def fetch_all(only: str | None = None) -> dict[str, list[dict]]:
    """Run all fetchers (or one, if --source given). Returns {source_name: items}."""
    results: dict[str, list[dict]] = {}
    for name, fn in ALL_FETCHERS.items():
        if only and name != only:
            continue
        try:
            results[name] = fn()
        except Exception as err:
            # Catch-all so one broken source doesn't kill the run.
            # Safe: we log and return empty; the operator sees WARN in stderr.
            log.warning("fetcher %s raised %s: %s", name, type(err).__name__, err)
            results[name] = []
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    only = sys.argv[1] if len(sys.argv) > 1 else None
    all_items = fetch_all(only=only)
    total = sum(len(items) for items in all_items.values())
    print(json.dumps(all_items, indent=2, default=str), file=sys.stdout)
    print(f"\ntotal items: {total}", file=sys.stderr)
