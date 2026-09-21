"""
Shared plumbing for the licensed-data source plugins (pdl.py, crustdata.py,
apollo.py).

description: helpers common to all three paid people-data providers --
    config/secret lookup, the one sanctioned direct-`requests` POST helper,
    ProviderRecord/RawDocument construction, and cost bookkeeping.
inputs: none directly; consumed by sources/pdl.py, sources/crustdata.py,
    sources/apollo.py.
outputs: none directly (library module).

RADAR_CONTRACTS.md §A rule: "All HTTP goes through core/cache.py (fetch,
fetch_raw, fetch_rendered, head_ok) or core/providers.call_role." Every
function there is built for GET-and-cache-as-text (fetch/fetch_raw) or a
Firecrawl-specific render (fetch_rendered) -- none of them can POST an
arbitrary JSON body with a provider-specific auth header and return parsed
JSON, which is what all three of PDL /v5/person/search, Crustdata
/person/search + /person/enrich, and Apollo /people/match require.

`_post_json` below is the ONE SANCTIONED EXCEPTION named in RADAR_CONTRACTS.md
§A ("if a POST helper is missing, implement `_post_json` in
licensed_common.py using `requests` with timeout and note it in the docstring
... and add it to the grep allowlist comment"). It is the single place in
sources/pdl.py, sources/crustdata.py and sources/apollo.py that touches
`requests` directly.

GREP ALLOWLIST: `grep -rn "requests\.\(get\|post\)" over layers/ sources/
integrations/ eval/` will show exactly one NEW hit versus the pre-existing
sources/acp.py:305 and sources/linkedin_lookup.py:55 (both already-sanctioned
Serper/case-search POSTs) -- the `requests.post` call inside `_post_json`
below. That is expected and intentional, not a violation to fix.

These three providers are licensed commercial APIs, so unlike core/cache's
disk cache (keyed by URL, built for free/public GET fetches of the same
page), responses here are NOT cached to disk: the same search query against a
live database can return different candidates day to day (new hires, new
LinkedIn imports), and re-hitting a paid endpoint is a cost decision that
belongs to the caller (run.py's --coverage-test), not a silent cache layer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Optional

import requests

from ..core.config import CONFIG


class ProviderNotConfigured(RuntimeError):
    """Raised when a licensed provider's API key is absent.

    Per RADAR_CONTRACTS.md §A: "no key -> provider raises a clear
    ProviderNotConfigured, never a silent empty result." A SourceResult with
    fetched=0 and no error is indistinguishable from "the query genuinely
    matched nobody," which would silently zero out a coverage test and read
    as a bad niche/query rather than a missing credential.
    """


def require_key(name: str) -> str:
    """Fetch a secret via core.config.secret, translating absence into
    ProviderNotConfigured rather than core.config's generic RuntimeError --
    callers (run.py --coverage-test) match on this specific type.
    """
    from ..core.config import secret

    val = secret(name, required=False)
    if not val:
        raise ProviderNotConfigured(
            f"{name} is not set. See deliverables/gaia_2026-09-10/"
            f"KEY_INSTRUCTIONS.md for how to obtain and configure it."
        )
    return val


def _post_json(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout: Optional[int] = None,
) -> tuple[int, dict]:
    """The one sanctioned direct-`requests` call in sources/*. See module
    docstring. Returns (http_status, parsed_json_or_empty_dict). Never
    raises on a network/parse failure -- mirrors core/cache.fetch's
    "degrade the run, don't kill it" contract -- callers treat status 0 as
    a hard failure.

    Every non-200 response, and every network/parse exception, is logged --
    URL and status only, NEVER `headers` (an `Authorization`/`x-api-key`
    entry lives in there for all three licensed providers).
    """
    try:
        resp = requests.post(
            url,
            headers=headers,
            data=json.dumps(json_body),
            timeout=timeout or CONFIG.request_timeout_s,
        )
    except Exception as exc:
        print("[licensed_common] POST " + url + " failed: " + repr(exc)[:160])
        return 0, {}
    if resp.status_code != 200:
        print("[licensed_common] POST " + url + " -> HTTP " + str(resp.status_code))
    try:
        payload = resp.json() if resp.content else {}
    except Exception as exc:
        print("[licensed_common] POST " + url + ": could not parse JSON body: "
              + repr(exc)[:160])
        payload = {}
    return resp.status_code, payload


def raw_hash(payload: dict) -> str:
    """sha256 of the provider's raw JSON, for ProviderRecord.raw_hash audit."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def render_content_text(fields: list[tuple[str, Any]]) -> str:
    """Render provider fields as "field: value" lines -- exactly the text
    the quote validator (layers/validator.py) checks a claim's evidence_quote
    against, per RADAR_CONTRACTS.md §A: "evidence_quote = the provider field
    rendered as `\"<field>: <value>\"`". One line per non-empty field, in the
    order supplied, so a claim's evidence_quote is a verbatim single line
    (or an exact substring of one) of this text.
    """
    lines = []
    for name, value in fields:
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value if v not in (None, ""))
            if not value:
                continue
        lines.append(f"{name}: {value}")
    return "\n".join(lines)


def parse_date(value: Any) -> Optional[date]:
    """Best-effort parse of a provider date field into a date.

    Providers hand back dates in every shape: "2019-03", "2019-03-15",
    "2019", or a full ISO datetime. A JobStint's start/end are Optional
    per RADAR_CONTRACTS.md §A precisely because this is often partial --
    never fail the whole record over one unparsable date field.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt_len, parser in (
        (10, lambda t: date.fromisoformat(t[:10])),
        (7, lambda t: date.fromisoformat(t[:7] + "-01")),
        (4, lambda t: date(int(t[:4]), 1, 1)),
    ):
        if len(s) >= fmt_len:
            try:
                return parser(s)
            except (ValueError, TypeError):
                continue
    return None
