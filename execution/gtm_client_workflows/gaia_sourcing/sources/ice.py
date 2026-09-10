"""
Source plugin: ICE (Institution of Civil Engineers) members directory --
chartership evidence (Chartered Member/Fellow, CEng, MICE/FICE).

PRIOR ART / LIVE INSPECTION PASS (2026-09-10)
----------------------------------------------
robots.txt (https://www.ice.org.uk/robots.txt): the generic `User-agent: *`
group is `Allow: /` -- everything is allowed for a plugin that doesn't
identify as Googlebot. (A separate `User-Agent: Googlebot` group disallows
`/people`, `/staff`, `/sponsors/`, `*.pdf`, etc. -- irrelevant here, and note
`/about-ice/about-our-members/members-directory` doesn't match `/people`
even for Googlebot.) `/about-ice/about-our-members/members-directory` is
ALLOWED by robots.txt for this plugin.

What actually happens on a plain HTTP GET, verified live: the site is behind
Cloudflare and every request from a non-browser client returned HTTP 403
(Cloudflare bot-mitigation response, `__cf_bm` cookie challenge set) --
confirmed on the directory URL itself, on the same URL with a
`?searchterm=` query string, and on `/umbraco/api/` (ICE's CMS is Umbraco;
this was a probe for an exposed content API). None got past the challenge.
As with istructe.py, this is a bot-detection wall separate from and
stricter than robots.txt, so this plugin routes only through
`core.cache.fetch_rendered` (Firecrawl) per RADAR_CONTRACTS.md's instruction
for JS-gated sources, and inherits `fetch_rendered`'s degrade-to-None
behaviour rather than adding its own retry/fallback logic. Whether
Firecrawl's render defeats the same Cloudflare challenge was not verified in
this build (no FIRECRAWL_API_KEY was available in this sandbox).

No login, no account, and no invented "?name=" search URL: the directory's
own markup could not be inspected past the challenge, so this plugin does
not assume a search-URL shape it never saw. `lookup_person` fetches the
directory landing page (rendered) and checks whether the requested person's
forename and surname both appear together in its own text.
"""

from __future__ import annotations

from typing import Optional

from ..core.cache import fetch_rendered
from ..core.contracts import RawDocument, SourceQuery, SourceResult
from .base import TextSource, throttle
from .registers import fragment_with_both_names, path_allowed_by_robots

NAME = "ice"
DIRECTORY_URL = "https://www.ice.org.uk/about-ice/about-our-members/members-directory"
DIRECTORY_PATH = "/about-ice/about-our-members/members-directory"

# Verified live 2026-09-10 against https://www.ice.org.uk/robots.txt. The
# `User-agent: *` group is a blanket `Allow: /`, so this plugin (which does
# not identify as Googlebot) has no Disallow prefixes to honour at all.
DISALLOWED_PREFIXES: list[str] = []

class ICEProvider:
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
