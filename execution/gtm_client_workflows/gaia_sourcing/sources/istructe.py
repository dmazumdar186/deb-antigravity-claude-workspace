"""
Source plugin: IStructE members directory ("find an engineer") --
chartership evidence (Chartered Member/Fellow, CEng, MIStructE/FIStructE).

PRIOR ART / LIVE INSPECTION PASS (2026-09-10)
----------------------------------------------
robots.txt (https://www.istructe.org/robots.txt): a long Disallow list, but
every entry is a specific admin/account/CPD-course/committee page (e.g.
`/my-account/`, `/checkout/`, `/staff-portal/`, `/treasurers-area/`,
`/resources/training/...`). `/find-an-engineer/members-directory/` is not
disallowed -- it is ALLOWED by robots.txt.

What actually happens on a plain HTTP GET, verified live: the site is behind
Cloudflare, and every request from a non-browser client returned HTTP 403
with `cf-mitigated: challenge` (a Cloudflare bot-challenge page, not a
robots.txt block) -- confirmed on the directory URL itself, on the same URL
with a `?search=` / `?searchterm=` query string, and on `/wp-json/` (a
common exposed-API probe). None of those attempts got past the challenge.
This is a bot-detection wall, separate from and stricter than robots.txt: a
plain `core.cache.fetch()` GET cannot reach this page at all, regardless of
robots.txt's answer, which is why this plugin routes only through
`core.cache.fetch_rendered` (Firecrawl) per RADAR_CONTRACTS.md's instruction
for JS-gated sources. Whether Firecrawl's render defeats the same
Cloudflare challenge was not verified in this build (no FIRECRAWL_API_KEY
was available in this sandbox) -- `fetch_rendered` already degrades to None
on any failure, so this plugin inherits that degrade-not-raise behaviour
without needing its own fallback logic.

No login is attempted, no account is used, and no query-string search
pattern is assumed here: since the base directory page itself could not be
reached to inspect its markup or its search form, this plugin does not
invent a "?name=" URL shape. `lookup_person` fetches the directory landing
page (rendered) and checks whether the requested person's forename and
surname both appear together in its own text -- honest about being
best-effort until the page can actually be inspected past the challenge.
"""

from __future__ import annotations

from typing import Optional

from ..core.cache import fetch_rendered
from ..core.contracts import RawDocument, SourceQuery, SourceResult
from .base import TextSource, throttle
from .registers import fragment_with_both_names, path_allowed_by_robots

NAME = "istructe"
DIRECTORY_URL = "https://www.istructe.org/find-an-engineer/members-directory/"
DIRECTORY_PATH = "/find-an-engineer/members-directory/"

# Verified live 2026-09-10 against https://www.istructe.org/robots.txt,
# `User-agent: *` group -- the full Disallow list, trimmed to prefixes.
DISALLOWED_PREFIXES = [
    "/my-account/", "/checkout/", "/staff-portal/",
    "/test-pages/get-involved-(1)/", "/treasurers-area/", "/brand/",
    "/resources/concrete-magazine/", "/resources/guidance/regional-group-handbook/",
    "/resources/training/", "/resources/concrete-magazine/issues/",
    "/pri-reviewers/", "/about-us/how-we-are-structured/board-files/",
    "/get-involved/working-groups/", "/forms/committees-and-panels/",
    "/example-pages/test-login-download/", "/forms/homeexams/",
    "/get-involved/supported-organisations/ser-audit-pool-scotland/",
    "/engineering-with-purpose-aligning-our-values/pledge-form/",
    "/training-and-development/", "/CMSPages/", "/webtest/files/",
    "/IStructEWebServices.asmx",
]

class IStructEProvider:
    name = NAME
    text_source: TextSource = "text_layer"
    rate_limit_s = 2.5  # Cloudflare-fronted; stay well clear of the 2.0s floor

    def fetch(self, query: SourceQuery) -> SourceResult:
        if not path_allowed_by_robots(DIRECTORY_PATH, DISALLOWED_PREFIXES):
            print(f"[{NAME}] blocked_by_robots=True path={DIRECTORY_PATH}")
            return SourceResult(provider=NAME, documents=[], fetched=0)

        doc = None
        name_terms = [t for t in query.terms if len(t.split()) >= 2]
        for term in name_terms:
            found = lookup_person(term)
            if found is not None:
                doc = found
                break
        if doc is None and not name_terms:
            doc = _fetch_directory()
        docs = [doc] if doc is not None else []
        return SourceResult(provider=NAME, documents=docs, fetched=len(docs))

    def cost_eur(self, result: SourceResult) -> float:
        return 0.0  # Firecrawl render cost is metered at the cache layer, not per-plugin


def _fetch_directory() -> Optional[RawDocument]:
    throttle(NAME, 2.5)
    return fetch_rendered(DIRECTORY_URL, source_type="professional_body")


def lookup_person(full_name: str, employer: Optional[str] = None) -> Optional[RawDocument]:
    """See module docstring: the directory could not be inspected past its
    Cloudflare challenge, so this checks the rendered landing page's own text
    for the person's forename and surname together, and returns None (never
    fabricates a match) when they are not both present."""
    parts = full_name.split()
    if len(parts) < 2:
        return None
    doc = _fetch_directory()
    if doc is None:
        print(f"[{NAME}] directory unreachable for lookup_person({full_name!r})")
        return None
    fragment = fragment_with_both_names(doc.content_text, parts[0], parts[-1])
    if fragment is None:
        return None
    return doc
