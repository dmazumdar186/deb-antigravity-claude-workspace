"""Pull Malt recommendations from a logged-in Chrome session.

Reads Chrome's cookie jar (browser_cookie3 handles DPAPI / App-Bound Encryption on Windows),
hits the Malt profile URL with realistic browser headers, and extracts recommendations from
the embedded Next.js `__NEXT_DATA__` JSON (falls back to HTML scrape if missing).

Output: JSON matching the shape of src/content/recommendations.en.json.

Usage:
    py execution/personal_workflows/portfolio_site/scripts/fetch_malt_recs.py \
        --url https://www.malt.fr/profile/debanjanmazumdar \
        --out execution/personal_workflows/portfolio_site/src/content/recommendations.en.json \
        [--dump .tmp/malt_response.html]  # save raw HTML for debug
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import browser_cookie3
import requests

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def load_cookies(domain: str = "malt.fr") -> requests.cookies.RequestsCookieJar:
    """Grab Chrome cookies for the domain. Returns empty jar if none found."""
    try:
        cj = browser_cookie3.chrome(domain_name=domain)
    except Exception as e:
        print(f"WARN: browser_cookie3.chrome failed: {e}", file=sys.stderr)
        print("Trying browser_cookie3.load (all browsers)...", file=sys.stderr)
        cj = browser_cookie3.load(domain_name=domain)
    rcj = requests.cookies.RequestsCookieJar()
    for c in cj:
        rcj.set_cookie(c)
    print(f"INFO: loaded {len(rcj)} cookies for *.{domain}", file=sys.stderr)
    return rcj


def fetch(url: str, cookies: requests.cookies.RequestsCookieJar) -> str:
    r = requests.get(url, headers=HEADERS, cookies=cookies, timeout=30, allow_redirects=True)
    print(f"INFO: GET {url} -> HTTP {r.status_code} ({len(r.content)} bytes)", file=sys.stderr)
    if r.status_code >= 400:
        raise SystemExit(f"FAIL: Malt returned HTTP {r.status_code}")
    return r.text


def extract_next_data(html: str) -> dict | None:
    """Pull the Next.js __NEXT_DATA__ JSON blob from HTML."""
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"WARN: __NEXT_DATA__ JSON parse failed: {e}", file=sys.stderr)
        return None


def find_recommendations(data: Any, _depth: int = 0) -> list[dict]:
    """Walk the Next.js props tree looking for an array of recommendation-shaped objects.

    Malt's profile API returns recommendations under various nested paths
    (profile.recommendations, props.pageProps.profile.recommendations, etc).
    We don't hardcode the path — we just walk and pattern-match the shape.
    """
    found: list[dict] = []
    if _depth > 30:
        return found

    if isinstance(data, list):
        # Heuristic: a list of dicts where each has a comment/text field and an author/from field
        sample = data[:5]
        if (
            sample
            and all(isinstance(x, dict) for x in sample)
            and any(
                any(k in x for k in ("comment", "text", "content", "body", "review"))
                for x in sample
            )
            and any(
                any(k in x for k in ("author", "from", "client", "by", "reviewer", "writer"))
                for x in sample
            )
        ):
            return data
        for item in data:
            found.extend(find_recommendations(item, _depth + 1))
    elif isinstance(data, dict):
        for k, v in data.items():
            if (
                k.lower() in ("recommendations", "reviews", "testimonials", "recos")
                and isinstance(v, list)
                and v
            ):
                if found:
                    found.extend(v)
                else:
                    found = list(v)
            else:
                found.extend(find_recommendations(v, _depth + 1))
    return found


def normalize_rec(raw: dict) -> dict:
    """Reshape a Malt rec dict into the site's recommendations.en.json schema."""
    quote = (
        raw.get("comment")
        or raw.get("text")
        or raw.get("content")
        or raw.get("body")
        or raw.get("review")
        or ""
    ).strip()
    author = (
        raw.get("author")
        or raw.get("from")
        or raw.get("client")
        or raw.get("by")
        or raw.get("reviewer")
        or raw.get("writer")
        or {}
    )
    if isinstance(author, str):
        author = {"name": author}
    name = (
        author.get("fullName")
        or author.get("name")
        or author.get("displayName")
        or (f"{author.get('firstName', '')} {author.get('lastName', '')}").strip()
        or "—"
    )
    role = (
        author.get("jobTitle")
        or author.get("title")
        or author.get("position")
        or author.get("role")
        or "—"
    )
    company = (
        author.get("company")
        or author.get("organization")
        or author.get("employer")
        or "—"
    )
    if isinstance(company, dict):
        company = company.get("name", "—")
    linkedin = (
        author.get("linkedInUrl")
        or author.get("linkedin")
        or author.get("linkedinUrl")
        or "#"
    )
    return {
        "_status": "imported_from_malt",
        "quote": quote,
        "name": name,
        "role": role,
        "company": company,
        "linkedin_url": linkedin,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="Malt profile URL")
    p.add_argument("--out", required=True, help="Where to write recommendations.en.json")
    p.add_argument("--dump", default=None, help="Optional: save raw HTML to this path for debug")
    p.add_argument("--max", type=int, default=5, help="Max recommendations to keep")
    args = p.parse_args()

    cookies = load_cookies("malt.fr")
    if len(cookies) == 0:
        print("FAIL: zero Malt cookies found in Chrome. Are you logged in to malt.fr in Chrome?", file=sys.stderr)
        return 2

    html = fetch(args.url, cookies)

    if args.dump:
        dump_path = Path(args.dump)
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(html, encoding="utf-8")
        print(f"INFO: dumped raw HTML -> {dump_path}", file=sys.stderr)

    nd = extract_next_data(html)
    if not nd:
        print("FAIL: no __NEXT_DATA__ block found. Run with --dump to inspect raw HTML.", file=sys.stderr)
        return 3

    raw_recs = find_recommendations(nd)
    print(f"INFO: found {len(raw_recs)} candidate recommendation objects in __NEXT_DATA__", file=sys.stderr)
    if not raw_recs:
        print("FAIL: no recommendation-shaped objects in __NEXT_DATA__.", file=sys.stderr)
        print("Run with --dump and grep the HTML for known recommender names to verify shape.", file=sys.stderr)
        return 4

    normalized = [normalize_rec(r) for r in raw_recs if (r.get("comment") or r.get("text") or r.get("content") or r.get("body") or r.get("review"))]
    normalized = [r for r in normalized if r["quote"]][: args.max]
    if not normalized:
        print("FAIL: zero non-empty recommendations after normalization", file=sys.stderr)
        return 5

    out_data = {
        "section_eyebrow": "What people who've worked with me say",
        "section_title": "Verified on Malt. Click through and check.",
        "section_intro": "Real engagements, real names, real outcomes — every recommendation is on the public Malt profile.",
        "_data_source_note": f"Imported from {args.url} via fetch_malt_recs.py",
        "quotes": normalized,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: wrote {len(normalized)} recommendation(s) -> {out_path}", file=sys.stderr)
    for i, r in enumerate(normalized, 1):
        print(f"  [{i}] {r['name']} ({r['role']}): \"{r['quote'][:70]}...\"", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
