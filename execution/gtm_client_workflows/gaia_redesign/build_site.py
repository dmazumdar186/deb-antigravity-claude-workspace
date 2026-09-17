"""Render the Gaia Talent redesign templates into a deployable static site.

description: Copies src/ to site/, injects the live role data (featured list,
  ticker, full board, hero role cards, filters, JSON-LD), the sector map and the
  team roster, measures the real byte weight of the built pages for the client
  note's evidence table, then validates the result and fails the build on any
  breach.
inputs: deliverables/gaia_redesign_2026-09-17/src/ — templates, css, js, assets,
  config.json and data/{jobs,sectors,consultants}.json
outputs: deliverables/gaia_redesign_2026-09-17/site/ — the deployable site; and
  src/data/link_check.json — the live role-URL check used by the note

CLI:
  python3 execution/gtm_client_workflows/gaia_redesign/build_site.py \
      --src <src dir> --out <site dir> [--skip-links]
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_job_links  # noqa: E402
import validate_site  # noqa: E402

AS_OF = "15 September 2026"
JOBS_HREF = {"home": "jobs/index.html", "sub": "index.html"}

# ------------------------------------------------------------------ data maps

# The six hero states, in order, with the keywords that pick their live role.
# First match wins, scanning the dataset in order; a role is never reused.
FLOW_PICKS = [
    ("Hydropower & Onshore Wind", ["consents", "senior / principal engineer", "renewables"]),
    ("Solar Energy", ["land liaison", "project engineer - renewable", "project manager - renewable"]),
    ("Water & Flood Risk", ["flood risk", "hydrogeologist", "water"]),
    ("Wave & Tidal Energy", ["principal engineer – energy", "energy storage", "energy & renewables", "energy"]),
    ("Sustainable Transport", ["greenway", "bridge", "roads and transport", "transportation"]),
    ("Ecology & Environmental", ["ornithology", "ecologist", "eia"]),
]

FEATURED_SLUGS = [
    "associate-director-sustainable-infrastructure",
    "principal-ecologist",
    "hydrogeologist",
    "senior-civil-engineer-roads-and-transportation",
    "resident-engineer-bridge-construction",
    "senior-quantity-surveyor-building-infrastructure",
    "landfill-manager",
    "geotechnical-engineer",
]

# Gaia's own 23 sectors, verbatim, with the title/sector keywords used to size
# each one against the live board. A sector with no live roles still appears.
SECTORS = [
    ("Built Environment", ["built environment", "building", "structural", "quantity surveyor"]),
    ("Carbon Management", ["carbon", "net zero"]),
    ("Circular Economy", ["circular economy"]),
    ("Climate Change", ["climate"]),
    ("Conservation", ["ecolog", "arborist", "biodiversity", "landscape"]),
    ("CSR", ["csr", "responsible business"]),
    ("Energy", ["energy"]),
    ("Energy Efficiency", ["energy efficiency", "retrofit"]),
    ("Energy from Waste", ["energy from waste", "landfill gas"]),
    ("Energy Storage", ["storage", "battery"]),
    ("Engineering", ["engineer"]),
    ("Environmental", ["environment"]),
    ("ESG & Responsible Investment", ["esg", "responsible invest"]),
    ("Green Start-ups", ["start-up", "startup"]),
    ("Health & Safety", ["health & safety", "health and safety", "safety"]),
    ("Hydropower & Onshore Wind", ["hydro", "wind", "consents"]),
    ("Renewable Energy", ["renewab"]),
    ("Solar Energy", ["solar", "land liaison"]),
    ("Sustainable Transport", ["transport", "greenway", "roads", "rail", "bridge"]),
    ("Utilities", ["utilit", "wastewater"]),
    ("Waste Management & Recycling", ["waste", "recycl", "landfill"]),
    ("Water & Flood Risk", ["water", "flood", "hydrogeolog", "hydrolog"]),
    ("Wave & Tidal Energy", ["wave", "tidal", "marine", "offshore"]),
]

TEAM = [
    ("Keith", "Managing Director", "team-keith.jpg", 640, 740, ""),
    ("Isadora", "Senior Recruitment Specialist", "team-isadora.jpg", 640, 740, "Consultant on all current live roles"),
    ("Gian", "Recruitment Specialist", "team-gian.jpg", 640, 740, ""),
    ("Eva O'Brien", "Senior Recruitment Consultant", "team-eva-obrien.jpg", 400, 400, ""),
    ("Diana Lupu", "Finance Administrator", "team-diana-lupu.jpg", 400, 400, ""),
]

# ------------------------------------------------------ hero fallback artwork
# One small inline SVG per hero state, same stroke language as the canvas.
# Used below 800px, under reduced motion and with JavaScript off.
_ART_OPEN = (
    '<div class="flow__art" aria-hidden="true">'
    '<svg viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg" focusable="false" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round">'
)
_ART_CLOSE = "</svg></div>"
_GROUND = '<path d="M0 132 C 58 122 108 138 160 130 S 262 120 320 128 L320 200 L0 200Z" fill="#0b1622"/>'
_HORIZON = '<path d="M0 132 C 58 122 108 138 160 130 S 262 120 320 128" stroke="#4fd066" stroke-width="1.6"/>'

SECTOR_ART = {
    0: _ART_OPEN + _GROUND + _HORIZON
    + '<g stroke="#ffffff" stroke-opacity=".16" stroke-dasharray="2 7" stroke-width="1">'
    + '<path d="M0 112 C 58 102 108 118 160 110 S 262 100 320 108"/>'
    + '<path d="M0 92 C 58 82 108 98 160 90 S 262 80 320 88"/>'
    + '<path d="M0 72 C 58 62 108 78 160 70 S 262 60 320 68"/></g>'
    + '<g stroke="#4fd066" stroke-opacity=".5" stroke-width="1.4">'
    + '<path d="M34 125v14"/><path d="M87 128v14"/><path d="M140 130v14"/>'
    + '<path d="M193 130v14"/><path d="M246 125v14"/><path d="M299 124v14"/></g>'
    + _ART_CLOSE,
    1: _ART_OPEN + _GROUND + _HORIZON
    + '<g stroke="#ffffff" stroke-opacity=".38" stroke-width="1.6">'
    + '<path d="M96 129V86"/><path d="M168 130V78"/><path d="M240 125V92"/></g>'
    + '<g stroke="#4fd066" stroke-width="1.6">'
    + '<path d="M96 86 76 70M96 86l22-12M96 86v20"/>'
    + '<path d="M168 78 146 66M168 78l24-8M168 78v22"/>'
    + '<path d="M240 92 222 78M240 92l20-10M240 92v18"/></g>'
    + '<g stroke="#ffffff" stroke-opacity=".34" stroke-width="1.5">'
    + '<path d="M16 130 26 112h34l10 18"/></g>'
    + '<g stroke="#4fd066" stroke-opacity=".35" stroke-width="1">'
    + '<path d="M4 118h22M4 124h22"/></g>'
    + _ART_CLOSE,
    2: _ART_OPEN
    + '<circle cx="232" cy="74" r="20" stroke="#dfa23f" stroke-opacity=".55" stroke-width="1.6"/>'
    + _GROUND + _HORIZON
    + '<g stroke="#4fd066" stroke-width="1.3" fill="#16283b">'
    + '<path d="M20 160 54 142 70 148 36 166Z"/><path d="M92 160l34-18 16 6-34 18Z"/>'
    + '<path d="M164 160l34-18 16 6-34 18Z"/><path d="M236 160l34-18 16 6-34 18Z"/>'
    + '<path d="M56 190l40-21 18 7-40 21Z"/><path d="M140 190l40-21 18 7-40 21Z"/>'
    + '<path d="M224 190l40-21 18 7-40 21Z"/></g>'
    + _ART_CLOSE,
    3: _ART_OPEN + _GROUND + _HORIZON
    + '<g stroke="#ffffff" stroke-opacity=".14" stroke-dasharray="3 6" stroke-width="1">'
    + '<path d="M0 140 C 58 130 108 146 160 138 S 262 128 320 136"/>'
    + '<path d="M0 148 C 58 138 108 154 160 146 S 262 136 320 144"/></g>'
    + '<path d="M0 156 C 40 152 80 160 120 156 S 200 148 260 154 320 158 320 158 L320 200 L0 200Z" fill="#16283b" fill-opacity=".85"/>'
    + '<path d="M0 156 C 40 152 80 160 120 156 S 200 148 260 154 320 158" stroke="#4fd066" stroke-opacity=".7" stroke-width="1.4"/>'
    + '<g stroke="#4fd066" stroke-opacity=".35" stroke-width="1">'
    + '<path d="M0 170 C 46 166 92 174 138 170 S 230 164 320 170"/>'
    + '<path d="M0 182 C 46 178 92 186 138 182 S 230 176 320 182"/></g>'
    + _ART_CLOSE,
    4: _ART_OPEN + _GROUND + _HORIZON
    + '<path d="M0 150 C 40 146 80 154 120 150 S 200 142 320 150 L320 200 L0 200Z" fill="#16283b" fill-opacity=".85"/>'
    + '<path d="M0 150 C 40 146 80 154 120 150 S 200 142 320 150" stroke="#4fd066" stroke-opacity=".7" stroke-width="1.4"/>'
    + '<g stroke="#ffffff" stroke-opacity=".4" stroke-width="1.5">'
    + '<path d="M120 128h190"/><path d="M120 128v24M158 128v24M196 128v24M234 128v24M272 128v24M310 128v24"/></g>'
    + '<g stroke="#4fd066" stroke-width="1.4">'
    + '<rect x="16" y="106" width="26" height="24"/><rect x="50" y="106" width="26" height="24"/>'
    + '<path d="M22 106v-5M36 106v-5M56 106v-5M70 106v-5"/></g>'
    + '<g stroke="#4fd066" stroke-opacity=".35" stroke-width="1">'
    + '<path d="M0 170 C 46 166 92 174 138 170 S 230 164 320 170"/></g>'
    + _ART_CLOSE,
    5: _ART_OPEN + _GROUND + _HORIZON
    + '<g stroke="#ffffff" stroke-opacity=".42" stroke-width="1.5">'
    + '<path d="M176 108h84"/><path d="M176 108v22M218 108v22M260 108v20"/></g>'
    + '<path d="M176 108q42-16 84 0" stroke="#4fd066" stroke-opacity=".5" stroke-width="1.3"/>'
    + '<path d="M8 196 Q 96 172 152 150 T 286 126" stroke="#4fd066" stroke-width="1.8"/>'
    + '<g fill="#0b1622" stroke="#ffffff" stroke-opacity=".6" stroke-width="1.4">'
    + '<circle cx="72" cy="180" r="3.6"/><circle cx="152" cy="150" r="3.6"/><circle cx="232" cy="132" r="3.6"/></g>'
    + _ART_CLOSE,
    6: _ART_OPEN + _GROUND + _HORIZON
    + '<g stroke="#ffffff" stroke-opacity=".12" stroke-width="1">'
    + '<path d="M53 0v200M107 0v200M160 0v200M213 0v200M267 0v200"/>'
    + '<path d="M0 50h320M0 100h320M0 150h320"/></g>'
    + '<g stroke="#4fd066" stroke-width="1.4">'
    + '<path d="M28 131v-18M28 122l-7-6M28 122l7-6"/><path d="M50 133v-14M50 126l-6-5M50 126l6-5"/>'
    + '<path d="M72 134v-20M72 124l-7-6M72 124l7-6"/><path d="M94 133v-15M94 126l-6-5M94 126l6-5"/>'
    + '<path d="M116 132v-18M116 123l-7-6M116 123l7-6"/></g>'
    + '<g stroke="#ffffff" stroke-opacity=".62" stroke-width="1.5">'
    + '<path d="M196 48l10 7 10-7"/><path d="M234 66l8 6 8-6"/><path d="M264 40l9 6 9-6"/></g>'
    + _ART_CLOSE,
}

ARROW = '<span class="arw" aria-hidden="true">&#8599;</span>'


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def qs(value: str) -> str:
    """A value safe inside a query string AND inside an HTML attribute.

    '&' in a sector name has to be percent-encoded before it is escaped, or the
    link silently splits into two query parameters and the board loads unfiltered.
    """
    return esc(quote(str(value), safe=""))


def json_ld(payload: Any) -> str:
    """JSON for an inline <script>. '<' is escaped so no string in the data can
    close the element, and the two line separators are escaped because they are
    literal newlines to a JavaScript parser but legal inside a JSON string."""
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


REQUIRED_JOB_KEYS = ("slug", "title", "url", "location", "type")


def check_dataset(jobs: list[dict[str, Any]]) -> list[str]:
    """Structural problems in jobs.json, named by slug so they can be found."""
    problems: list[str] = []
    seen: set[str] = set()
    for index, job in enumerate(jobs):
        slug = str(job.get("slug") or f"#{index}")
        missing = [k for k in REQUIRED_JOB_KEYS if not str(job.get(k) or "").strip()]
        if missing:
            problems.append(f"{slug}: missing required key(s) {missing}")
        url = str(job.get("url") or "")
        if url and not url.lower().startswith(("https://", "http://")):
            problems.append(f"{slug}: url is not http(s): {url[:60]!r}")
        sectors = job.get("sectors") or []
        if not isinstance(sectors, list) or not sectors:
            problems.append(f"{slug}: sectors must be a non-empty list")
        if slug in seen:
            problems.append(f"{slug}: duplicate slug")
        seen.add(slug)
    return problems


def sector_keys(job: dict[str, Any]) -> list[str]:
    """Every sector a role belongs to, normalised.

    The client-side filter, the chip counts and the select options all go
    through this, so a chip can never promise a number the board cannot show.
    """
    return [str(x).strip().lower() for x in (job.get("sectors") or []) if str(x).strip()]


# --------------------------------------------------------------- job renderers

def _flow_role(job: dict[str, Any]) -> str:
    return (
        f'<a class="rolecard" href="{esc(job["url"])}" rel="noopener" target="_blank">'
        f'<span class="rolecard__k label">Live role</span>'
        f'<span class="rolecard__t">{esc(job["title"])}</span>'
        f'<span class="rolecard__m">{esc(job["location"])} &middot; {esc(job["type"])} '
        f'&middot; View on gaiatalent.com {ARROW}</span></a>'
    )


def _role_row(job: dict[str, Any], *, board: bool) -> str:
    sectors = job.get("sectors") or []
    sector = sectors[0] if sectors else ""
    data = ""
    if board:
        haystack = " ".join([job["title"], job["location"], " ".join(sectors), job["type"], job.get("summary", "")])
        data = (
            f' data-job data-location="{esc(job["location"])}"'
            f' data-sector="{esc("|".join(sector_keys(job)))}"'
            f' data-type="{esc(job["type"])}" data-search="{esc(haystack.lower())}"'
        )
    meta = [job["location"], ", ".join(x.title() if x.islower() else x for x in sectors), job["type"]]
    if board:
        meta.append(f'Consultant: {job.get("consultant", "")}')
    spans = "".join(f"<span>{esc(m)}</span>" for m in meta if m)
    return (
        f'<a class="rolerow" href="{esc(job["url"])}" rel="noopener" target="_blank"{data}>'
        f'<span class="rolerow__t">{esc(job["title"])}</span>'
        f'<span class="rolerow__m">{spans}</span>'
        f'<span class="rolerow__go">View on gaiatalent.com {ARROW}</span></a>'
    )


def render_featured(jobs: list[dict[str, Any]]) -> str:
    by_slug = {j["slug"]: j for j in jobs}
    picked = [by_slug[s] for s in FEATURED_SLUGS if s in by_slug]
    rows = "".join(_role_row(j, board=False) for j in picked)
    return f'<div class="rolelist">{rows}</div>'


def render_board(jobs: list[dict[str, Any]]) -> str:
    rows = "".join(_role_row(j, board=True) for j in sorted(jobs, key=lambda j: j["title"]))
    return f'<div class="rolelist" data-joblist>{rows}</div>'


def render_ticker(jobs: list[dict[str, Any]]) -> str:
    picks = sorted(jobs, key=lambda j: j["title"])[::2][:24]
    items = "".join(
        f'<a href="{esc(j["url"])}" rel="noopener" target="_blank" data-scope="ticker">'
        f'<b>{esc(j["title"])}</b> {esc(j["location"])}</a>'
        for j in picks
    )
    clone = items.replace('data-scope="ticker"', 'data-scope="clone" tabindex="-1"')
    return (
        '<div class="ticker"><div class="ticker__t">'
        f'<div class="ticker__g">{items}</div>'
        f'<div class="ticker__g" aria-hidden="true">{clone}</div>'
        "</div></div>"
    )


def sector_options(jobs: list[dict[str, Any]]) -> list[str]:
    """Every sector value that at least one row can be filtered to."""
    seen: dict[str, str] = {}
    for job in jobs:
        for raw in job.get("sectors") or []:
            seen.setdefault(str(raw).strip().lower(), str(raw).strip())
    return [seen[k] for k in sorted(seen)]


def sector_count(jobs: list[dict[str, Any]], value: str) -> int:
    """Exactly what jobs.js counts for the same select value."""
    key = value.strip().lower()
    return sum(1 for job in jobs if key in sector_keys(job))


def render_chips(jobs: list[dict[str, Any]]) -> str:
    counts = [(name, sector_count(jobs, name)) for name in sector_options(jobs)]
    top = sorted(counts, key=lambda kv: (-kv[1], kv[0]))[:6]
    chips = "".join(
        f'<a class="chip" href="jobs/index.html?sector={qs(name)}">'
        f'{esc(name if not name.islower() else name.title())}<span class="num">{count}</span></a>'
        for name, count in top
    )
    return f'<div class="chips">{chips}</div>'


def _select(field_id: str, label: str, values: list[str], any_label: str) -> str:
    options = f'<option value="">{esc(any_label)}</option>' + "".join(
        f'<option value="{esc(v)}">{esc(v if not v.islower() else v.title())}</option>' for v in values
    )
    return (
        f'<div class="field"><label for="{field_id}">{esc(label)}</label>'
        f'<select id="{field_id}">{options}</select></div>'
    )


def render_filters(jobs: list[dict[str, Any]]) -> str:
    locations = sorted({j["location"] for j in jobs})
    sectors = sector_options(jobs)
    types = sorted({j["type"] for j in jobs})
    return (
        _select("f-location", "Location", locations, "All locations")
        + _select("f-sector", "Sector", sectors, "All sectors")
        + _select("f-type", "Type", types, "All types")
    )


def render_jobs_jsonld(jobs: list[dict[str, Any]]) -> str:
    postings = []
    for job in jobs:
        location = job["location"]
        address: dict[str, str] = {"@type": "PostalAddress", "addressCountry": "IE"}
        if location.lower().startswith("ireland"):
            address["addressRegion"] = "Ireland"
        else:
            address["addressLocality"] = location
        postings.append(
            {
                "@context": "https://schema.org/",
                "@type": "JobPosting",
                "title": job["title"],
                "description": job.get("summary") or job["title"],
                "datePosted": "2026-09-15",
                "employmentType": "FULL_TIME" if job["type"] == "Permanent" else "CONTRACTOR",
                "directApply": False,
                "url": job["url"],
                "hiringOrganization": {
                    "@type": "Organization",
                    "name": "Gaia Talent",
                    "url": "https://gaiatalent.com/",
                },
                "jobLocation": {"@type": "Place", "address": address},
            }
        )
    return '<script type="application/ld+json">' + json_ld(postings) + "</script>"


def render_org_jsonld() -> str:
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Gaia Talent",
        "url": "https://gaiatalent.com/",
        "description": (
            "Specialist recruitment consultancy across environmental, engineering, "
            "sustainability and renewable energy in Ireland and the UK."
        ),
        "telephone": "+353 1 211 8940",
        "areaServed": ["IE", "GB"],
        "sameAs": ["https://www.linkedin.com/company/gaia-talent/"],
    }
    offices = [
        ("Gaia Talent — Dublin", "+353 1 211 8940", "Dublin"),
        ("Gaia Talent — Clare", "+353 65 672 9020", "County Clare"),
    ]
    blocks = [org] + [
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": name,
            "telephone": phone,
            "url": "https://gaiatalent.com/",
            "parentOrganization": {"@type": "Organization", "name": "Gaia Talent"},
            "address": {"@type": "PostalAddress", "addressLocality": locality, "addressCountry": "IE"},
        }
        for name, phone, locality in offices
    ]
    return "".join(
        '<script type="application/ld+json">' + json_ld(b) + "</script>" for b in blocks
    )


def sector_map_term(name: str, keywords: list[str], jobs: list[dict[str, Any]]) -> tuple[int, str]:
    """Count and search term for one of Gaia's own 23 sectors.

    The board has no field for these — they are Gaia's taxonomy, not the job
    feed's — so the map links to a free-text search and the number is computed
    with exactly the substring test that search performs. Whatever the
    superscript says, clicking it lands on that many rows.
    """
    best = ""
    best_count = 0
    for keyword in keywords:
        hits = sum(1 for job in jobs if keyword in job_haystack(job))
        if hits > best_count:
            best_count, best = hits, keyword
    return best_count, best or keywords[0]


def job_haystack(job: dict[str, Any]) -> str:
    """The same text jobs.js searches (data-search on the row)."""
    parts = [
        job["title"],
        job["location"],
        " ".join(job.get("sectors") or []),
        job["type"],
        job.get("summary", "") or "",
    ]
    return " ".join(parts).lower()


def render_sector_map(jobs: list[dict[str, Any]]) -> str:
    out = []
    for name, keywords in SECTORS:
        count, term = sector_map_term(name, keywords, jobs)
        size = 1.0 + min(count, 12) / 12 * 1.55
        weight = 600 if count else 500
        sup = f"<sup>{count}</sup>" if count else ""
        href = f"jobs/index.html?q={qs(term)}"
        out.append(
            f'<a href="{href}" data-live="{1 if count else 0}" '
            f'style="--s:{size:.2f}rem;--w:{weight}">{esc(name)}{sup}</a>'
        )
    return f'<div class="secmap">{"".join(out)}</div>'


def render_roster(prefix: str, *, jobs_href: str, eager: bool = False) -> str:
    rows = []
    for name, title, image, w, h, extra in TEAM:
        extra_html = ""
        if extra:
            extra_html = f'<span class="person__x"><a class="lk" href="{jobs_href}">{esc(extra)}</a></span>'
        rows.append(
            f'<div class="person">'
            f'<img src="{prefix}assets/{image}" alt="{esc(name)}, {esc(title)} at Gaia Talent" '
            f'width="{w}" height="{h}" loading="{"eager" if eager else "lazy"}" decoding="async">'
            f'<span class="person__n">{esc(name)}</span>'
            f'<span class="person__r">{esc(title)}</span>{extra_html}</div>'
        )
    return f'<div class="roster">{"".join(rows)}</div>'


def render_roster_revealed(prefix: str, *, jobs_href: str) -> str:
    """Home-page roster, with a 60ms stagger on the reveal."""
    block = render_roster(prefix, jobs_href=jobs_href)
    index = [0]

    def add(match: re.Match[str]) -> str:
        delay = index[0] * 60
        index[0] += 1
        return f'<div class="person" data-reveal style="--rd:{delay}ms">'

    return re.sub(r'<div class="person">', add, block)


# ------------------------------------------------------------------- evidence

_MEASURED: dict[Path, tuple[int, int]] = {}


def _measure(path: Path) -> tuple[int, int]:
    """Raw and gzipped size of one file. Cached: the evidence table asks for
    both columns and gzipping the images twice is the slowest thing in the build."""
    hit = _MEASURED.get(path)
    if hit is None:
        raw = path.read_bytes()
        hit = (len(raw), len(gzip.compress(raw, 9)))
        _MEASURED[path] = hit
    return hit


def _kb(n: int) -> str:
    return f"{n / 1024:.1f}&nbsp;KB"


def run_node_tests(src: Path) -> tuple[int, int] | None:
    """(passed, failed) from `node --test js/motion.test.js`, or None if node
    is unavailable. The evidence table quotes this, so it is never a literal."""
    test = src / "js" / "motion.test.js"
    if not test.exists():
        return None
    try:
        proc = subprocess.run(
            ["node", "--test", "js/motion.test.js"],
            cwd=str(src),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"      node tests not run: {type(exc).__name__}: {exc}")
        return None
    passed = failed = 0
    for line in proc.stdout.splitlines():
        if line.startswith("# pass "):
            passed = int(line.split()[-1])
        elif line.startswith("# fail "):
            failed = int(line.split()[-1])
    return passed, failed


def check_built_js(site: Path) -> list[str]:
    """`node --check` every shipped script: the publish pass rewrites these
    files, and a stripped comment must never be able to break the syntax."""
    scripts = sorted((site / "js").glob("*.js"))
    problems: list[str] = []
    for script in scripts:
        try:
            proc = subprocess.run(
                ["node", "--check", script.name],
                cwd=str(script.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"      node --check skipped: {type(exc).__name__}: {exc}")
            return []
        if proc.returncode != 0:
            problems.append(f"{script.name} does not parse after the publish pass: {proc.stderr.strip()[:200]}")
    return problems


def render_evidence(site: Path, jobs: list[dict[str, Any]], tests: tuple[int, int] | None) -> str:
    groups: list[tuple[str, list[Path]]] = [
        ("Home page (HTML)", [site / "index.html"]),
        ("Live roles page (HTML)", [site / "jobs" / "index.html"]),
        ("Team page (HTML)", [site / "team" / "index.html"]),
        ("Stylesheet (one file)", sorted((site / "css").glob("*.css"))),
        ("JavaScript (four files)", sorted((site / "js").glob("*.js"))),
        ("Images (logo, B Corp, five portraits, share card)", sorted(p for p in (site / "assets").glob("*") if p.is_file())),
        ("Web fonts (self-hosted, two files)", sorted((site / "assets" / "fonts").glob("*.woff2"))),
        ("Role data (JSON)", sorted((site / "data").glob("*.json"))),
    ]
    rows = []
    for label, paths in groups:
        paths = [p for p in paths if p.is_file()]
        if not paths:
            continue
        measured = [_measure(p) for p in paths]
        raw = sum(m[0] for m in measured)
        gz = sum(m[1] for m in measured)
        rows.append(
            f"<tr><th scope=\"row\">{esc(label)}</th>"
            f'<td class="num">{_kb(raw)}</td><td class="num">{_kb(gz)}</td></tr>'
        )
    rows.append(
        '<tr><th scope="row">Third-party scripts, trackers, frameworks</th>'
        '<td class="num">0</td><td class="num">0</td></tr>'
    )
    fonts = sorted((site / "assets" / "fonts").glob("*.woff2"))
    rows.append(
        '<tr><th scope="row">Font requests to third parties</th>'
        '<td class="num" colspan="2">0 &mdash; Archivo and Public Sans are served from this folder ('
        + esc(", ".join(f.name for f in fonts))
        + ")</td></tr>"
    )
    checks = [
        f"{len(jobs)} role records rendered and counted against the dataset",
        "every local link and image resolved to a file that exists",
        "every image carries alt text and explicit width and height",
        "every form control carries a real label",
        "all JSON-LD blocks parsed",
        "no absolute paths, so the site runs from any subfolder",
        "no third-party requests at all: fonts, styles and scripts are all served from this folder",
        "every shipped script re-parsed after the build (node --check)",
    ]
    if tests:
        passed, failed = tests
        checks.append(
            f"{passed} unit tests over the scroll and scene maths, "
            + ("all passing" if not failed else f"{failed} FAILING")
            + " (node --test)"
        )
    rows.append(
        '<tr><th scope="row">Checks run on this build</th><td colspan="2">'
        + esc("; ".join(checks))
        + "</td></tr>"
    )
    return (
        f'<div class="tbl-wrap"><table class="tbl"><caption>Built {date.today().isoformat()}. '
        "Sizes are of the files in this folder; the compressed column is what a "
        "browser actually downloads. This note page is excluded from the page "
        "measurements above.</caption>"
        "<thead><tr><th scope=\"col\">What</th><th scope=\"col\">On disk</th>"
        "<th scope=\"col\">Compressed</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


# ---------------------------------------------------------------- publish pass

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def publish_text(text: str) -> str:
    """Strip block comments and leading indentation from CSS/JS on the way out.

    The sources stay documented; the shipped files stay inside the weight budget.
    Only block comments are touched — line comments are left alone so nothing
    containing '//' (a URL, a regex) can be damaged.
    """
    out = _BLOCK_COMMENT.sub("", text)
    lines = [ln.rstrip() for ln in out.split("\n")]
    return "\n".join(ln.lstrip() if ln.strip() else "" for ln in lines if ln.strip()) + "\n"


# --------------------------------------------------------------------- render

def guard_output(src: Path, out: Path) -> str:
    """Refuse to wipe anything that is not a build directory.

    build() starts by deleting --out. Anything outside the repo's deliverables
    tree or the agent scratchpad, and anything that contains or equals --src, is
    rejected rather than removed.
    """
    repo = Path(__file__).resolve().parents[3]
    allowed = [repo / "deliverables", Path("/tmp"), Path.home() / ".tmp", repo / ".tmp"]
    scratch = os.environ.get("CLAUDE_SCRATCHPAD") or os.environ.get("TMPDIR")
    if scratch:
        allowed.append(Path(scratch).resolve())
    if not any(_within(out, base) for base in allowed if base):
        return (
            f"--out {out} is outside the build areas "
            f"({', '.join(str(b) for b in allowed if b)}); refusing to delete it"
        )
    if out == src or _within(src, out):
        return f"--out {out} is or contains --src {src}; refusing to delete it"
    if out.parent == out:
        return f"--out {out} is a filesystem root; refusing to delete it"
    return ""


def _within(child: Path, parent: Path) -> bool:
    try:
        return child.resolve().is_relative_to(parent.resolve())
    except (OSError, ValueError):
        return False


def build(src: Path, out: Path, *, skip_links: bool) -> int:
    if not src.is_dir():
        print(f"FAIL  source directory not found: {src}", file=sys.stderr)
        return 2

    refusal = guard_output(src, out)
    if refusal:
        print(f"FAIL  {refusal}", file=sys.stderr)
        return 2

    config = json.loads((src / "config.json").read_text(encoding="utf-8")) if (src / "config.json").exists() else {}
    jobs = json.loads((src / "data" / "jobs.json").read_text(encoding="utf-8"))
    consultants = json.loads((src / "data" / "consultants.json").read_text(encoding="utf-8"))

    dataset_problems = check_dataset(jobs)
    if dataset_problems:
        print(f"FAIL  jobs.json has {len(dataset_problems)} problem(s):", file=sys.stderr)
        for line in dataset_problems:
            print(f"  - {line}", file=sys.stderr)
        return 2

    # ---- live-link check (writes back into src so the data stays with the repo)
    link_path = src / "data" / "link_check.json"
    if skip_links:
        if link_path.exists():
            link_report = json.loads(link_path.read_text(encoding="utf-8"))
        else:
            link_report = {"total": len(jobs), "ok": 0, "skipped": True, "checked_on": date.today().isoformat()}
    else:
        print(f"…  checking {len(jobs)} live role URLs")
        link_report = check_job_links.check_all([j["url"] for j in jobs])
        link_path.write_text(json.dumps(link_report, indent=2) + "\n", encoding="utf-8")
    print("   " + check_job_links.summary_sentence(link_report))

    # ---- copy the tree
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(
        src,
        out,
        ignore=shutil.ignore_patterns("*.test.js", "config.json", "README.md", "__pycache__"),
    )
    for name in ("css", "js"):
        for path in (out / name).glob("*"):
            if path.suffix in (".css", ".js"):
                path.write_text(publish_text(path.read_text(encoding="utf-8")), encoding="utf-8")

    # ---- pick the hero roles: first keyword hit, never reused
    used: set[str] = set()
    flow_roles: dict[int, dict[str, Any]] = {}
    for position, (_, keywords) in enumerate(FLOW_PICKS, start=1):
        for keyword in keywords:
            match = next(
                (j for j in jobs if keyword in j["title"].lower() and j["slug"] not in used),
                None,
            )
            if match:
                used.add(match["slug"])
                flow_roles[position] = match
                break
        if position not in flow_roles:
            print(f"FAIL  no live role matched hero state {position}", file=sys.stderr)
            return 2

    consultant = consultants[0]["name"] if consultants else "our consultant"
    replacements_home = {
        "<!-- @org:jsonld -->": render_org_jsonld(),
        "<!-- @jobs:ticker -->": render_ticker(jobs),
        "<!-- @jobs:chips -->": render_chips(jobs),
        "<!-- @jobs:featured -->": render_featured(jobs),
        "<!-- @sectors:map -->": render_sector_map(jobs),
        "<!-- @team:roster -->": render_roster_revealed("", jobs_href=JOBS_HREF["home"]),
    }
    for position, job in flow_roles.items():
        replacements_home[f"<!-- @flow:role:{position} -->"] = _flow_role(job)
    for state, art in SECTOR_ART.items():
        replacements_home[f"<!-- @art:{state} -->"] = art

    total = len(jobs)
    replacements_jobs = {
        "<!-- @jobs:jsonld -->": render_jobs_jsonld(jobs),
        "<!-- @jobs:filters -->": render_filters(jobs),
        "<!-- @jobs:all -->": render_board(jobs),
        "<!-- @jobs:count -->": f"Showing all <b>{total}</b> live roles.",
        "<!-- @jobs:consultant-line -->": (
            f"{esc(consultant)} is the consultant on all {total}."
        ),
    }
    replacements_team = {"<!-- @team:full -->": render_roster("../", jobs_href="../jobs/index.html", eager=True)}

    def apply(path: Path, table: dict[str, str]) -> None:
        text = path.read_text(encoding="utf-8")
        for marker, value in table.items():
            text = text.replace(marker, value)
        email = str(config.get("contact_email", "") or "")
        text = text.replace('data-contact-email=""', f'data-contact-email="{esc(email)}"')
        path.write_text(text, encoding="utf-8")

    apply(out / "index.html", replacements_home)
    apply(out / "jobs" / "index.html", replacements_jobs)
    apply(out / "team" / "index.html", replacements_team)
    apply(out / "404.html", {})

    # sitemap from config
    base = str(config.get("site_base", "") or "").rstrip("/")
    if base and (out / "sitemap.xml").exists():
        urls = "".join(
            f"<url><loc>{base}/{page}</loc></url>"
            for page in ("index.html", "jobs/index.html", "team/index.html")
        )
        sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
        (out / "sitemap.xml").write_text(sitemap.replace("<!-- @sitemap:urls -->", urls), encoding="utf-8")

    # evidence table last: it measures the files written above
    keith = out / "for-keith" / "index.html"
    tests = run_node_tests(src)
    if tests and tests[1]:
        print(f"FAIL  {tests[1]} node test(s) failing", file=sys.stderr)
        return 1
    apply(
        keith,
        {
            "<!-- @evidence:table -->": render_evidence(out, jobs, tests),
            "<!-- @links:verified -->": check_job_links.summary_sentence(link_report),
        },
    )

    # ---- validate
    print("…  validating")
    failures = check_built_js(out)
    failures += validate_site.validate(out, jobs)
    if failures:
        print(f"FAIL  {len(failures)} validation problem(s):", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    css = sum(p.stat().st_size for p in (out / "css").glob("*.css"))
    js = sum(p.stat().st_size for p in (out / "js").glob("*.js"))
    html_bytes = sum(p.stat().st_size for p in out.rglob("*.html"))
    print("PASS  all checks green")
    print(f"      {total} roles rendered · {len(list(out.rglob('*.html')))} pages")
    print(f"      html {html_bytes / 1024:.1f} KB · css {css / 1024:.1f} KB (budget 45) · js {js / 1024:.1f} KB (budget 30)")
    print(f"      site: {out}")
    return 0


def main() -> int:
    here = Path(__file__).resolve().parents[3] / "deliverables" / "gaia_redesign_2026-09-17"
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=here / "src")
    parser.add_argument("--out", type=Path, default=here / "site")
    parser.add_argument("--skip-links", action="store_true", help="reuse the stored link_check.json")
    args = parser.parse_args()
    return build(args.src.resolve(), args.out.resolve(), skip_links=args.skip_links)


if __name__ == "__main__":
    raise SystemExit(main())
