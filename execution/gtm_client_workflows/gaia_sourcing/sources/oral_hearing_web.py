"""
Source plugin: oral-hearing evidence published on scheme and authority sites.

WHY THIS EXISTS (discovered 2026-08-19 during the prior-art pass)
-----------------------------------------------------------------
Serper's Google index does NOT reach the deep /publicaccess/ tree on
pleanala.ie -- a site-restricted query for "Witness Statement of" returns
zero organic results, even though the documents are there and fetchable.
The acp.py plugin gets them by parsing case pages directly, which works but
only for cases we already know about.

The broader query surfaced the answer: major Irish infrastructure consents
run their own public consent websites, and they publish the entire oral
hearing bundle, including every witness's brief of evidence. Examples found:

    ringaskiddyrrc.ie/wp-content/uploads/Witness_statement_Fergal_Callaghan.pdf
    dublinportmp2foreshoreconsent.ie/.../ABP_OralHearing_Dec2019.pdf
    galway.ie/sites/default/files/.../Brief of Evidence - General.pdf
    metrolinkro.ie

So this plugin discovers evidence PDFs across the open web, restricted to
Irish scheme/authority domains, and feeds them through the same text
evidence gate as acp.py. It complements rather than replaces that plugin:
acp.py gives depth on known cases, this gives breadth across schemes.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Optional

from ..core.cache import fetch
from ..core.config import CONFIG, secret
from ..core.contracts import RawDocument
from .acp import looks_like_evidence_document, name_from_text

# Domains that indicate an Irish scheme, authority or statutory body.
# A .pdf on one of these is plausibly Irish oral-hearing evidence; a .pdf on
# a random UK consultancy blog is not.
_IE_DOMAIN_RE = re.compile(
    r"(\.ie/|\.ie$|pleanala|metrolink|ringaskiddy|dublinport|"
    r"galway|corkcity|limerick|waterford|kildare|meath|fingal|"
    r"tii\.ie|nationaltransport|irishrail|iarnrod|uisce|esb)",
    re.I,
)

# Filename/URL shapes that indicate a personal statement of evidence.
_EVIDENCE_URL_RE = re.compile(
    r"(witness[_%\s-]*statement|brief[_%\s-]*of[_%\s-]*evidence|"
    r"statement[_%\s-]*of[_%\s-]*evidence|oral[_%\s-]*hearing|"
    r"proof[_%\s-]*of[_%\s-]*evidence)",
    re.I,
)

SEARCH_QUERIES = [
    'pleanala.ie "Witness Statement of"',
    '"brief of evidence" oral hearing chartered engineer Ireland pdf',
    '"witness statement" "oral hearing" EIAR Ireland road scheme pdf',
    '"brief of evidence" "An Bord Pleanala" chartered engineer CPO',
    '"statement of evidence" "oral hearing" Ireland railway order engineer',
    '"brief of evidence" "compulsory purchase order" Ireland engineer pdf',
    'Ireland "oral hearing" "brief of evidence" transportation engineer EIAR',
    '"proof of evidence" OR "brief of evidence" Ireland motorway scheme engineer',
]


@dataclass
class WebDoc:
    url: str
    title: str
    person_hint: Optional[str] = None


def serper_search(query: str, num: int = 20) -> list[dict]:
    """One Serper query. Returns organic results, or [] on any failure."""
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=json.dumps({"q": query, "num": num}).encode("utf-8"),
            headers={
                "X-API-KEY": secret("SERPER_API_KEY"),
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=CONFIG.request_timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return data.get("organic", []) or []
    except Exception as exc:
        # Search failure degrades coverage; it must not kill the run. Logged
        # so a silently-empty source is distinguishable from a genuinely
        # empty result set.
        print("[oral_hearing_web] serper failed for " + query[:48] + ": " + repr(exc)[:90])
        return []


def discover(queries: Iterable[str] = SEARCH_QUERIES) -> list[WebDoc]:
    """Find candidate evidence PDFs across Irish scheme/authority domains."""
    seen: set[str] = set()
    out: list[WebDoc] = []
    for q in queries:
        for item in serper_search(q):
            link = item.get("link", "")
            if not link or link in seen:
                continue
            if ".pdf" not in link.lower():
                continue
            if not _IE_DOMAIN_RE.search(link):
                continue
            if not (_EVIDENCE_URL_RE.search(link) or _EVIDENCE_URL_RE.search(
                item.get("title", "") + " " + item.get("snippet", "")
            )):
                continue
            seen.add(link)
            out.append(WebDoc(url=link, title=item.get("title", "")))
    return out


def harvest(docs: Optional[list[WebDoc]] = None) -> list[tuple[WebDoc, RawDocument]]:
    """Download + apply the same text evidence gate used for ACP documents."""
    docs = docs if docs is not None else discover()
    out: list[tuple[WebDoc, RawDocument]] = []
    for d in docs:
        rd = fetch(d.url, source_type="acp_witness_statement")
        if rd is None or not rd.content_text.strip():
            continue
        if not looks_like_evidence_document(rd.content_text):
            continue
        d.person_hint = name_from_text(rd.content_text) or _name_from_url(d.url)
        if not d.person_hint:
            continue
        out.append((d, rd))
    return out


_URL_NAME_RE = re.compile(
    r"(?:witness[_%\s-]*statement|brief[_%\s-]*of[_%\s-]*evidence)[_%\s-]*"
    r"(?:of[_%\s-]*)?([A-Za-z]+[_%\s-]+[A-Za-z]+)",
    re.I,
)


def _name_from_url(url: str) -> Optional[str]:
    m = _URL_NAME_RE.search(urllib.parse.unquote(url))
    if not m:
        return None
    parts = re.split(r"[_%\s-]+", m.group(1))
    parts = [p.capitalize() for p in parts if p.isalpha() and len(p) > 1]
    return " ".join(parts) if len(parts) >= 2 else None
