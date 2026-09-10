"""
Source plugin: Engineers Ireland "Find a member" / chartership evidence.

PRIOR ART / LIVE INSPECTION PASS (2026-09-10)
----------------------------------------------
robots.txt (https://www.engineersireland.ie/robots.txt), `User-agent: *`
group -- the only group that applies to us (the Googlebot/BingBot/Slurp
groups are irrelevant to a plugin that does not identify as those crawlers):
Disallow covers /admin/, /App_Browsers/, /App_Code/, /App_Data/,
/App_GlobalResources/, /bin/, /Components/, /Config/, /contest/, /controls/,
/DesktopModules/, /Documentation/, /HttpModules/, /images/, /Install/, /js/,
/Portals/, /Providers/, /Resources/*, /Activity-Feed/userId/. NONE of that
covers /Professionals/Membership/Members/Find-a-member or
/Professionals/Communities-Groups/Find-a-member -- both are ALLOWED by
robots.txt. (No PetalBot/MJ12bot/AhrefsBot identity is used here either, so
their blanket `Disallow: /` groups don't apply to us.)

What the search actually is, verified live:
- `GET /Professionals/Membership/Members/Find-a-member/Search-members`
  returns 200 and a full page (145KB), but the visible "Search members" form
  is an ASP.NET WebForms postback (`__EVENTTARGET`/`__EVENTARGUMENT`/
  `__VIEWSTATE`/`__VIEWSTATEGENERATOR`/`__EVENTVALIDATION` hidden fields,
  `__doPostBack()` in an inline script) wrapped in an Angular shell
  (`ng-app="eil"`). There is no GET query-string form of the search: a
  postback needs a `__VIEWSTATE` token minted for that exact page load, so
  building a URL by hand cannot reach it -- it would need a stateful
  fetch-the-form / parse-the-token / POST-the-token round trip that
  `core/cache.py`'s single-shot `fetch()`/`fetch_rendered()` do not do, and
  building that round trip ourselves would cross from "fetching a page" into
  "operating the member portal like a logged-out user would", which is the
  scraping behaviour this plugin is built not to do.
- No static, publicly-browsable per-member register exists elsewhere on the
  site: `/Professionals/Membership/Registered-professional-titles/*` are
  explanatory pages about what "Chartered Engineer" etc. means, not a list of
  who holds it.
- Probing the page's own bundled JS resources
  (`/DependencyHandler.axd/<hash>/604/js`) to look for an underlying search
  API returned, on four of five hashes, a "Web Application Firewall Alert"
  page rather than the script -- the site's WAF fired on that request
  pattern. A follow-up GET to a plausible related path
  (`/Professionals/Communities-Groups/Find-a-member/Specialist-Registers-and-
  Panels`) returned the same WAF alert page (HTTP 404 body, WAF content).
  Inspection stopped at that point rather than retrying or working around it.

CONCLUSION: this plugin never attempts the live member search. `fetch()` and
`lookup_person()` only read the static, robots-allowed "Find a member"
landing page (`/Professionals/Membership/Members/Find-a-member`, plain GET,
verified 200) through `core.cache.fetch`, and check whether the requested
person's forename and surname both appear together in that page's own text
(they will not, for essentially every real query, because the landing page
does not list individual members) -- so this source is honest about being
near-zero-yield for `lookup_person` today, rather than silently faking a
search. If Engineers Ireland ever publishes a GET-able or JSON member search,
this module is the place to wire it in; nothing here should be read as "the
register was scraped".

`blocked_by_robots` is always False for the path this plugin fetches (it is
robots-allowed); the constant and check exist so the plugin degrades the same
way sibling register plugins do if this ever changes, or if `lookup_person`
is pointed at a path Engineers Ireland later disallows.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Optional

from ..core.cache import fetch
from ..core.contracts import RawDocument, SourceQuery, SourceResult
from .base import TextSource
from .registers import fragment_with_both_names, path_allowed_by_robots

NAME = "engineers_ireland"
BASE = "https://www.engineersireland.ie"
LANDING_PATH = "/Professionals/Membership/Members/Find-a-member"
LANDING_URL = BASE + LANDING_PATH

# Verified live 2026-09-10 against https://www.engineersireland.ie/robots.txt,
# `User-agent: *` group. Kept as prefixes (not a full parser) because that is
# all this plugin ever needs to check against.
DISALLOWED_PREFIXES = [
    "/admin/", "/App_Browsers/", "/App_Code/", "/App_Data/",
    "/App_GlobalResources/", "/bin/", "/Components/", "/Config/",
    "/contest/", "/controls/", "/DesktopModules/", "/Documentation/",
    "/HttpModules/", "/images/", "/Install/", "/js/", "/Portals/",
    "/Providers/", "/Resources/", "/Activity-Feed/userId/",
]

_last_hit = 0.0


def _throttle(rate_limit_s: float) -> None:
    global _last_hit
    wait = rate_limit_s - (time.monotonic() - _last_hit)
    if wait > 0:
        time.sleep(wait)
    _last_hit = time.monotonic()


class EngineersIrelandProvider:
    name = NAME
    text_source: TextSource = "text_layer"
    # WAF-sensitive site (see module docstring); kept well above the 2.0s
    # floor RADAR_CONTRACTS.md requires.
    rate_limit_s = 3.0

    def fetch(self, query: SourceQuery) -> SourceResult:
        if not path_allowed_by_robots(LANDING_PATH, DISALLOWED_PREFIXES):
            print(f"[{NAME}] blocked_by_robots=True path={LANDING_PATH}")
            return SourceResult(provider=NAME, documents=[], fetched=0)

        doc = None
        name_terms = [t for t in query.terms if len(t.split()) >= 2]
        for term in name_terms:
            found = lookup_person(term)
            if found is not None:
                doc = found
                break
        if doc is None and not name_terms:
            doc = _fetch_landing()
        docs = [doc] if doc is not None else []
        return SourceResult(provider=NAME, documents=docs, fetched=len(docs))

    def cost_eur(self, result: SourceResult) -> float:
        return 0.0  # public page, no paid quota


def _fetch_landing() -> Optional[RawDocument]:
    _throttle(3.0)
    return fetch(LANDING_URL, source_type="engineers_ireland_register")


def lookup_person(full_name: str, employer: Optional[str] = None) -> Optional[RawDocument]:
    """Best-effort, honest lookup. See module docstring: there is no live
    search this plugin will drive, so this only checks whether the person's
    forename and surname both appear together in the static landing page's
    own text. Returns None (never fabricates) when they do not -- which, for
    almost any real name, is the expected outcome today.
    """
    parts = full_name.split()
    if len(parts) < 2:
        return None
    doc = _fetch_landing()
    if doc is None:
        print(f"[{NAME}] landing page unreachable for lookup_person({full_name!r})")
        return None
    fragment = fragment_with_both_names(doc.content_text, parts[0], parts[-1])
    if fragment is None:
        return None
    return doc
