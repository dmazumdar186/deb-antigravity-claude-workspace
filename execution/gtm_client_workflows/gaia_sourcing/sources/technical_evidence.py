"""
Source plugin: per-candidate technical evidence for Role 1.

WHY THIS EXISTS (measured 2026-08-19)
-------------------------------------
Role 1's primary signal is `technical_skill` -- Eurocode design, Tekla /
Robot / ETABS, BCAR assigned-certifier work. Tier A requires two DIRECT
claims on that signal.

Across all sixteen Firecrawl-rendered staff-directory pages harvested for
this campaign, the counts were:

    eurocode   0        tekla      0        etabs      0
    robot      0        BCAR       0        assigned certifier   1

Meanwhile the same pages carried 30 occurrences of "CEng" and 32 of "MIEI"
on ocsc.ie alone. Staff directories evidence CHARTERSHIP and GRADE richly
and technical competence not at all: a firm's "our people" page says
"Brian is an Associate Director with 18 years' experience across commercial
and residential projects", never "Brian designed the transfer structure to
EN 1992-1-1".

So the directory alone caps every Role 1 candidate at Tier C, and no amount
of re-reading it changes that. The gap is a SOURCE gap, not a tiering
problem, and the correct fix is another source rather than a lower bar.

This plugin closes it by searching, per already-gate-passing candidate, the
places where an Irish structural engineer's technical work IS attributed to
them by name:

  - Engineers Ireland / Engineers Journal articles (bylined, and the byline
    routinely carries the grade: "Author: Colin Short, Chartered Civil
    Engineer Dip Eng, CEng").
  - ACEI and IStructE award citations, which name the design engineer.
  - Conference proceedings (CERI, Bridge Engineering Ireland).
  - The firm's own project and news pages, which name the engineer far more
    often than the people page does.

It runs only against candidates that already passed every hard gate, so the
search budget is spent on the twenty-odd people who might ship rather than
on the whole pool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..core.cache import fetch, fetch_rendered
from ..core.contracts import RawDocument
from .oral_hearing_web import serper_search

# Domains where a named Irish engineer's technical work is actually published.
# Not a filter on the search -- a filter on what is worth fetching afterwards.
_WORTH_FETCHING = re.compile(
    r"(engineersireland\.ie|engineersjournal\.ie|acei\.ie|istructe\.org|"
    r"ice\.org\.uk|arrow\.tudublin\.ie|researchrepository\.ucd\.ie|"
    r"aran\.library\.nuigalway\.ie|cora\.ucc\.ie|tara\.tcd\.ie|"
    r"constructionnews\.ie|irishconstructionnews\.com|buildingsireland\.ie|"
    r"engineering\.ie|structuralawards)",
    re.I,
)

# Terms that make a page worth extracting from. If none appear, the page
# cannot supply the primary signal and fetching it further is wasted budget.
_TECHNICAL_RE = re.compile(
    r"(eurocode|en\s?199[0-9]|tekla|etabs|robot structural|staad|"
    r"bcar|assigned certifier|reinforced concrete|post[- ]?tension|"
    r"structural steel|transfer (?:slab|structure)|"
    r"finite element|composite deck|prestress)",
    re.I,
)


@dataclass
class TechDoc:
    url: str
    person_id: str
    full_name: str
    title: str = ""


def _queries(full_name: str, employer: Optional[str]) -> list[str]:
    """Two queries per candidate. More is not better here.

    A name-plus-firm query finds the firm's own project and news pages; a
    name-plus-technical-term query finds bylined articles and award
    citations. Both are quoted on the name, because an unquoted Irish name
    returns the whole country.
    """
    q = ['"' + full_name + '"']
    out = []
    if employer:
        out.append(q[0] + ' "' + employer + '" (project OR structural OR design)')
    out.append(
        q[0] + " engineer (Eurocode OR Tekla OR \"structural design\" OR BCAR "
        "OR \"assigned certifier\") Ireland"
    )
    return out


def discover_for(
    person_id: str, full_name: str, employer: Optional[str], per_query: int = 8
) -> list[TechDoc]:
    """Search for pages that attribute technical work to this named person."""
    out: list[TechDoc] = []
    seen: set[str] = set()
    surname = full_name.split()[-1].lower()

    for query in _queries(full_name, employer):
        for item in serper_search(query, num=per_query):
            link = item.get("link", "")
            if not link or link in seen:
                continue
            blob = (item.get("title", "") + " " + item.get("snippet", "")).lower()
            # The snippet must mention the surname AND a technical term, or
            # the page is about someone else or about nothing useful. This is
            # the cheap gate; the expensive gate is the fetch below.
            if surname not in blob:
                continue
            if not (_TECHNICAL_RE.search(blob) or _WORTH_FETCHING.search(link)):
                continue
            # LinkedIn snippets cannot evidence competence -- 160 characters of
            # meta description is a job title, not a design code. Excluded here
            # rather than fetched and discarded.
            if "linkedin.com" in link.lower():
                continue
            seen.add(link)
            out.append(
                TechDoc(url=link, person_id=person_id, full_name=full_name,
                        title=item.get("title", ""))
            )
    return out


def harvest(docs: list[TechDoc], rendered: bool = False) -> list[tuple[TechDoc, RawDocument]]:
    """Fetch and gate. Only pages that name the person AND carry a technical
    term survive -- a page about the firm is not evidence about the person."""
    out: list[tuple[TechDoc, RawDocument]] = []
    for d in docs:
        rd = fetch_rendered(d.url) if rendered else fetch(d.url, source_type="other")
        if rd is None or len(rd.content_text) < 300:
            continue
        text = rd.content_text
        if not _TECHNICAL_RE.search(text):
            continue
        # The person's surname must appear in the page BODY, not just the
        # search snippet, or the claim would be attributed to someone the
        # document never mentions.
        parts = [p for p in re.split(r"[^A-Za-z']+", d.full_name) if len(p) >= 3]
        if not parts:
            continue
        if not re.search(r"\b" + re.escape(parts[-1]) + r"\b", text, re.I):
            continue
        out.append((d, rd))
    return out
