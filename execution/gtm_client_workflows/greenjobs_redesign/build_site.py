"""Render the GreenJobs (greenjobs.ie + greenjobs.co.uk) redesign into a static site.

description: Reads the scraped edition datasets, normalises them (canonical
  sector taxonomy from keywords, free-text regions resolved against the map's
  region table, dd/mm/yyyy dates, local logos with measured dimensions,
  sanitised employer descriptions), renders the two editions plus the root
  chooser from string templates in src/templates/, embeds the dataset where a
  page needs it, writes one page per job, sitemap, manifest and JSON-LD, runs
  `node --check` on every shipped script and `node --test` on the pure module,
  measures CSS/JS bytes against the budgets and calls validate_site before
  exiting non-zero on any breach.
inputs: --src <src dir> (templates, css, js, assets, data/{ie,uk}.json,
  data/regions_{ie,uk}.json, data/brief.md optional), --out <site dir>,
  --edition ie|uk|both, --data-fixture <json> (tests only: renders the fixture
  as both editions instead of the real files), --today YYYY-MM-DD (the build
  date; default = the dataset's "fetched" date, so a build is reproducible:
  every "ago" label, footer year, closing-date window and the closed-role
  drop are computed against it and exposed to the browser as data.today)
outputs: <out>/index.html chooser, <out>/{ie,uk}/… pages, <out>/{css,js,assets},
  <out>/.greenjobs-build marker; PASS/FAIL lines on stdout/stderr

CLI:
  python3 execution/gtm_client_workflows/greenjobs_redesign/build_site.py \
      --src deliverables/greenjobs_redesign_2026-09-22/src \
      --out deliverables/greenjobs_redesign_2026-09-22/site --edition both
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_site  # noqa: E402

MARKER = ".greenjobs-build"
OK_MARKER = ".greenjobs-build-ok"  # written only after validate passes; holds the sha256 of the site tree (deploy gate)
PROJECT = "greenjobs_redesign_2026-09-22"

EDITIONS = {
    "ie": {"domain": "greenjobs.ie", "lang": "en-IE", "currency": "EUR", "sym": "€", "unit": "county",
           "name": "Ireland", "short": "IE", "other": "uk", "elsewhere": "Elsewhere (UK & abroad)", "none": "Nationwide / remote",
           "outside_words": ["united kingdom", "uk", "england", "scotland", "wales", "northern ireland", "london"]},
    "uk": {"domain": "greenjobs.co.uk", "lang": "en-GB", "currency": "GBP", "sym": "£", "unit": "region",
           "name": "the UK", "short": "UK", "other": "ie", "elsewhere": "Ireland & abroad", "none": "UK-wide / remote",
           "outside_words": ["ireland", "dublin", "cork", "galway", "limerick"]},
}

# Canonical sector taxonomy. Order = priority; keywords are matched as whole
# words (case-insensitive) against the raw sector labels, title, summary and
# description. Colours: the warm-earth data set (sky, honey, sage, clay,
# terracotta and their deeper cuts); the third field says the swatch is dark
# enough to carry light text.
TAXONOMY: list[tuple[str, str, bool, list[str]]] = [
    ("Wind energy", "#5b95b8", False, ["wind", "offshore wind", "onshore wind", "turbine", "turbines"]),
    ("Solar energy", "#d99a1c", False, ["solar", "photovoltaic", "pv"]),
    ("Renewable energy & storage", "#6f8f6a", False, ["renewable", "renewables", "battery", "storage", "hydrogen", "hydro", "hydropower", "bioenergy", "biomass", "biogas", "anaerobic", "green energy", "clean energy", "alternative energy", "marine energy", "tidal", "wave"]),
    ("Water & flood", "#3f7ea6", True, ["water", "flood", "flooding", "drainage", "wastewater", "coastal", "hydrology", "hydrogeology", "hydrogeologist", "hydrologist", "sewer", "sewerage", "catchment"]),
    ("Waste & circular economy", "#b7774e", False, ["waste", "waste management", "recycling", "circular", "circular economy", "landfill", "resource management", "reuse", "lgv driver", "hgv driver", "refuse", "epa licensing", "epa licence", "waste licensing", "waste permitting", "waste compliance", "waste facility", "waste facilities"]),
    ("Ecology, nature recovery & biodiversity", "#5c7a57", True, ["ecology", "ecologist", "ecological", "conservation", "biodiversity", "habitat", "habitats", "wildlife", "species", "ornithologist", "ornithology", "botanist", "botany", "arboriculture", "arboriculturist", "arborist", "nature", "nature recovery", "rewilding", "peatland", "forestry", "woodland", "marine biology", "landscape restoration", "ecosystem", "ecosystems", "land restoration", "regenerative"]),
    # Keith 2026-09-28 (B1): engineering, infrastructure, HSE and climate roles were
    # landing in "Sustainability" or "Built environment". Each now has a home, placed
    # ahead of the umbrella sectors so a tie on score resolves to the specific one.
    ("Environmental engineering", "#8a6d3b", True, ["environmental engineer", "environmental engineers", "environmental engineering", "civil & environmental", "civil and environmental", "remediation", "contaminated land", "geo-environmental", "geoenvironmental", "geotechnical", "land reclamation", "site investigation"]),
    ("Sustainable infrastructure & transport", "#b08a3e", True, ["highway", "highways", "road", "roads", "rail", "railway", "railways", "metro", "metrolink", "transport", "transportation", "active travel", "cycling", "cycle", "greenway", "greenways", "bridge", "bridges", "civil engineer", "civil engineers", "civil engineering", "infrastructure", "pavement", "tunnel", "tunnelling", "maritime", "port", "ports", "coastal"]),
    ("Health, safety & environment", "#a34a3a", True, ["health & safety", "health and safety", "health, safety", "hse", "ehs", "safety", "cdm", "construction safety", "safety consultant", "safety advisor", "safety adviser", "occupational health"]),
    ("Climate & carbon", "#4f7362", True, ["climate", "climate change", "climate action", "carbon", "net zero", "net-zero", "decarbonisation", "decarbonization", "emissions", "greenhouse", "carbon accounting", "carbon footprint", "climate adaptation", "climate resilience"]),
    ("Environmental science & consulting", "#7f9c7a", False, ["environmental", "environment", "eia", "eiar", "impact assessment", "air quality", "acoustics", "noise", "geologist", "geology", "environmental scientist", "environmental consultant"]),
    ("Sustainability & ESG", "#a3653c", True, ["sustainability", "sustainable", "esg", "csrd", "responsible business", "corporate responsibility", "circularity"]),
    ("Built environment & energy efficiency", "#c65d3b", True, ["building", "buildings", "built environment", "energy efficiency", "retrofit", "breeam", "leed", "heat pump", "heat pumps", "insulation", "mechanical", "electrical", "hvac", "facilities", "architect", "architecture", "construction", "quantity surveyor", "surveyor"]),
    ("Energy networks & utilities", "#4a86ab", True, ["grid", "utility", "utilities", "transmission", "distribution", "substation", "energy network", "energy networks", "energy management", "energy manager", "power station", "electricity", "smart meter", "district heating"]),
    ("Policy, planning & advisory", "#9a8a6a", False, ["policy", "planning", "planner", "enforcement officer", "enforcement officers", "advisor", "adviser", "advisory", "regulation", "regulatory", "consents", "permitting", "compliance", "legal", "economist", "campaign", "communications", "fundraising", "education"]),
]
BUILT_ENV = "Built environment & energy efficiency"
PRIMARY_MIN = 2  # score a sector needs before a job carries it
# Secondary tags (R010/R087, 2026-09-28): a civil/highways role was carrying
# "Built environment", "Sustainability & ESG" or "Policy" on two stray body
# hits. A secondary now needs SECONDARY_MIN and at least a third of the
# primary's score, and a job carries at most MAX_SECONDARY of them.
SECONDARY_MIN = 3
SECONDARY_RATIO = 3  # secondary * SECONDARY_RATIO >= primary
MAX_SECONDARY = 2
# Scoring weights (panel 08, 2026-09-28): the raw site sector labels are the
# weakest signal (the IE site tags roles with up to nine labels, the UK site
# with none, and the two editions must agree), the title the strongest, and
# the employer name counts double so "Grundon Waste Management" reads as Waste.
SECTOR_W = {"raw": 0, "title": 3, "employer": 2, "summary": 2, "body": 1}  # raw labels break ties only

# Currency (Keith B2, 2026-09-28). Salaries are always shown in the currency the
# employer advertised. When that differs from the edition's currency a label
# "advertised in euros/sterling" plus an approximate equivalent is added, using this
# fixed rate. Comparisons (salary filter, medians, bands) annualise into the
# edition currency at the same rate. Mirrored in lib.js (FX).
FX_GBP_EUR = 1.17  # 1 GBP = 1.17 EUR, fixed 2026-09-28
CUR_NAME = {"EUR": "euros", "GBP": "sterling", "USD": "US dollars"}
CUR_SYM = {"EUR": "€", "GBP": "£", "USD": "$"}

# Location class (Keith B3). Derived from the location/region text only; the
# word "remote" may also come from title, summary or job type.
LOC_LABEL = {"ie": "Ireland", "uk": "UK", "ni": "Northern Ireland", "remote": "Remote", "cross": "Ireland & UK", "intl": "International", "unspecified": "Location not stated"}
# Which classes an edition's board carries (B5). Keith, 2026-09-28: "UK-only
# roles also appear prominently on the Irish board with salaries converted
# into euros. I would: retain salaries in their original advertised currency;
# clearly label UK, Ireland, remote and cross-border positions; allow users to
# exclude UK opportunities." So the IE board keeps everything (UK roles carry
# a "UK" badge, sterling figures come from the greenjobs.co.uk twin, see
# sterling_twins(), and the "Hide UK/abroad-only roles" toggle hides them);
# the UK board excludes Ireland-only and international roles outright.
EDITION_INCLUDES = {"ie": {"ie", "uk", "ni", "remote", "cross", "intl", "unspecified"}, "uk": {"uk", "ni", "remote", "cross", "unspecified"}}
# "Hide UK/abroad-only" / "Hide Ireland/abroad-only" toggle keeps these classes (B4).
EDITION_HOME = {"ie": ["ie", "cross", "remote"], "uk": ["uk", "ni", "cross", "remote"]}
EDITION_HOST = {"ie": "greenjobs.ie", "uk": "greenjobs.co.uk"}
STERLING_SOURCE = "greenjobs.co.uk listing"
UNVERIFIED_SOURCE = "greenjobs.ie listing (UK-located role)"  # visual N6 / R011: euro figures scraped from greenjobs.ie for a UK-only role with no sterling twin
UNVERIFIED_NOTE = "Salary as listed on greenjobs.ie; the advertiser may pay in sterling"


def salary_source_line(j: dict[str, Any]) -> str:
    """The visitor-facing 'Salary source' sentence for a role, or ''."""
    src = j.get("currency_source") or ""
    if src == UNVERIFIED_SOURCE:
        return UNVERIFIED_NOTE
    return f"Advertised in sterling on the {src}" if src else ""
UK_WORDS = ["united kingdom", "uk", "england", "scotland", "wales", "great britain", "britain", "london", "manchester", "birmingham", "leeds", "bristol", "glasgow", "edinburgh", "cardiff"]
# Northern Ireland place words: the full alias list of the "Northern Ireland"
# row in regions_uk.json (Enniskillen, Bangor NI, Co. Down …) when that file
# is readable at import, else this seed. Aliases that collide with a Welsh or
# English town (Bangor, Newport) are only accepted in their qualified form.
_NI_SEED = ["northern ireland", "belfast", "derry", "londonderry", "antrim", "armagh", "fermanagh", "tyrone", "lisburn", "newry", "co. down", "county down", "enniskillen", "bangor ni", "bangor co. down", "bangor, co. down"]
_NI_AMBIGUOUS = {"down", "ni", "bangor", "newport"}


def _load_ni_words() -> list[str]:
    path = Path(__file__).resolve().parents[3] / "deliverables" / PROJECT / "src" / "data" / "regions_uk.json"
    words = list(_NI_SEED)
    try:
        table = json.loads(path.read_text(encoding="utf-8"))
        for alias in table["regions"].get("Northern Ireland", []):
            w = alias.lower()
            if w not in _NI_AMBIGUOUS and w not in words:
                words.append(w)
    except (OSError, ValueError, KeyError):
        pass  # the seed list is enough; loc_class also receives ni_places from the src tree at build time
    return words


NI_WORDS = _load_ni_words()
FOREIGN_WORDS = ["switzerland", "zurich", "germany", "berlin", "france", "paris", "netherlands", "amsterdam", "belgium", "brussels", "spain", "italy", "denmark", "copenhagen", "norway", "sweden", "finland", "austria", "portugal", "poland", "usa", "united states", "canada", "australia", "new zealand", "india", "singapore", "europe", "worldwide", "international", "global", "ukraine", "kyiv"]
REMOTE_WORDS = ["remote", "home based", "home-based", "work from home", "working from home", "wfh"]

# Recruitment agencies (Keith D1). Rule: the named agencies plus any employer
# whose name contains a staffing word. "Consultancy" alone is not a staffing
# word (environmental consultancies are direct employers).
AGENCY_NAMES = {"gaia talent", "mattinson partnership", "chm recruit"}
AGENCY_DISPLAY = {"chm recruit": "CHM Recruit", "gaia talent": "Gaia Talent", "mattinson partnership": "Mattinson Partnership"}  # real casing when no live role carries the name (visual 25)
AGENCY_WORDS = ["recruit", "recruitment", "recruiters", "talent", "staffing", "resourcing", "headhunt", "personnel", "appointments", "search & selection"]  # "partnership" dropped 2026-09-28 (Mattinson is in AGENCY_NAMES)

WORKPLACE_LABEL = {"office": "Office-based", "hybrid": "Hybrid", "remote": "Remote", "site": "Site-based", "unspecified": "Not stated"}
LEVEL_ORDER = ["Graduate/Early career", "Mid-level", "Senior/Principal", "Director/Associate"]  # level_of() labels, facet order
# One "Contract" facet (visual 31, 2026-09-28): the scraped job type folds into
# these tags (Home Based -> workplace=remote via REMOTE_WORDS); the URL param
# `type` stays as an alias in lib.js normaliseState().
CONTRACT_LABEL = {"permanent": "Permanent", "contract": "Contract", "fixed-term": "Fixed-term", "full-time": "Full-time", "part-time": "Part-time", "volunteer": "Volunteer"}

NAV = [("jobs/index.html", "Jobs"), ("sectors/index.html", "Sectors"), ("insights/index.html", "Salary explorer"),
       ("compass/index.html", "Career compass"), ("employers/index.html", "Employers")]
PAGES_FOR_SITEMAP = ["index.html", "jobs/index.html", "sectors/index.html", "insights/index.html", "compass/index.html", "employers/index.html", "guides/index.html", "guides/salary-guide/index.html"]
# Pages that exist at the same path in both editions get hreflang pairs (G1).
SHARED_PATHS = set(PAGES_FOR_SITEMAP)

# Every page path that exists in both editions gets an hreflang pair; landing
# slugs differ per edition and job ids differ, so those carry a canonical only.
PAIRED_PATHS = SHARED_PATHS | {"dashboard/index.html", "for-keith/index.html"}

# SEO landing pages (G2): slug per edition, heading, and a predicate over the
# normalised job. A page with no matching live role is not built.
RENEWABLE_SECTORS = {"Wind energy", "Solar energy", "Renewable energy & storage"}
SUSTAINABILITY_SECTORS = {"Sustainability & ESG", "Climate & carbon"}
ECOLOGY_SECTOR = "Ecology, nature recovery & biodiversity"
LANDINGS: dict[str, list[dict[str, Any]]] = {
    "ie": [
        {"slug": "ecology-jobs-ireland", "h1": "Ecology jobs in Ireland", "kind": "sector", "sectors": {ECOLOGY_SECTOR}, "topic": "ecology, nature recovery and biodiversity"},
        {"slug": "environmental-jobs-dublin", "h1": "Environmental jobs in Dublin", "kind": "region", "region": "Dublin", "topic": "environmental"},
        {"slug": "renewable-energy-jobs-ireland", "h1": "Renewable energy jobs in Ireland", "kind": "sector", "sectors": RENEWABLE_SECTORS, "topic": "renewable energy"},
        {"slug": "sustainability-jobs-ireland", "h1": "Sustainability jobs in Ireland", "kind": "sector", "sectors": SUSTAINABILITY_SECTORS, "topic": "sustainability, climate and carbon"},
    ],
    "uk": [
        {"slug": "ecology-jobs-uk", "h1": "Ecology jobs in the UK", "kind": "sector", "sectors": {ECOLOGY_SECTOR}, "topic": "ecology, nature recovery and biodiversity"},
        {"slug": "environmental-jobs-london", "h1": "Environmental jobs in London", "kind": "region", "region": "London", "topic": "environmental"},
        {"slug": "renewable-energy-jobs-uk", "h1": "Renewable energy jobs in the UK", "kind": "sector", "sectors": RENEWABLE_SECTORS, "topic": "renewable energy"},
        {"slug": "sustainability-jobs-uk", "h1": "Sustainability jobs in the UK", "kind": "sector", "sectors": SUSTAINABILITY_SECTORS, "topic": "sustainability, climate and carbon"},
    ],
}
# Landing pages exist under an edition-specific slug; these are the hreflang
# twins (R055). Every other paired path is the same path in both editions.
# A landing page named "… in Ireland" / "… in Dublin" lists only the roles the board's "Hide UK/abroad-only"
# toggle keeps (IE: ie/cross/remote; UK: uk/ni/cross/remote); a London role never sits under "Ecology jobs in Ireland" (round 4).
LANDING_LOC = {k: set(v) for k, v in EDITION_HOME.items()}  # the board's "only" toggle set, so "Open these N roles" shows the same N
LANDING_PAIRS = {"ecology-jobs-ireland": "ecology-jobs-uk", "renewable-energy-jobs-ireland": "renewable-energy-jobs-uk",
                 "sustainability-jobs-ireland": "sustainability-jobs-uk", "environmental-jobs-dublin": "environmental-jobs-london"}


def paired_paths(paths_by_ed: dict[str, set[str]]) -> dict[str, dict[str, str]]:
    """{edition: {own path: twin path in the other edition}} for every path
    built in both editions, plus the landing slug pairs when both twins are built."""
    if len(paths_by_ed) != 2:
        return {k: {} for k in paths_by_ed}
    ie, uk = paths_by_ed["ie"], paths_by_ed["uk"]
    out: dict[str, dict[str, str]] = {"ie": {p: p for p in ie & uk}, "uk": {p: p for p in ie & uk}}
    for ie_slug, uk_slug in LANDING_PAIRS.items():
        a, b = f"{ie_slug}/index.html", f"{uk_slug}/index.html"
        if a in ie and b in uk:
            out["ie"][a] = b
            out["uk"][b] = a
    return out


MULTI_COUNT_NOTE = "A role advertised in several {units} or sectors is counted in each, so totals can exceed the number of live roles."

_MEASURED: dict[Path, tuple[int, int]] = {}


# ------------------------------------------------------------------ helpers

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def qs(value: str) -> str:
    return esc(quote(str(value), safe=""))


def json_ld(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def json_embed(payload: Any) -> str:
    """JSON inside a <script type=application/json>: only `<` needs neutralising."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "x"


def parse_date(raw: Any) -> str:
    """dd/mm/yyyy, yyyy-mm-dd or ISO datetime -> yyyy-mm-dd; '' when unknown."""
    if not raw:
        return ""
    s = str(raw).strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return ""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    return ""


def strip_tags(markup: str) -> str:
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", markup or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


_ATTR = re.compile(r"""\s+([a-zA-Z:-]+)(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?""")


def sanitise_html(markup: str, base_url: str) -> str:
    """Employer-authored HTML: keep structure, drop scripts, media, event
    handlers, styles and every attribute except a safe absolute href."""
    out = re.sub(r"<(script|style|iframe|object|embed|form|input|button|svg|video|audio)\b.*?</\1\s*>", " ", markup or "", flags=re.S | re.I)
    out = re.sub(r"<(img|iframe|input|source|link|meta|br\s*/?)\b[^>]*>", lambda m: "<br>" if m.group(1).lower().startswith("br") else " ", out, flags=re.I)
    out = re.sub(r"<!--.*?-->", " ", out, flags=re.S)

    def clean_tag(m: re.Match[str]) -> str:
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        if tag not in {"p", "br", "ul", "ol", "li", "b", "strong", "i", "em", "u", "h1", "h2", "h3", "h4", "h5", "h6",
                       "a", "div", "span", "table", "thead", "tbody", "tr", "td", "th", "blockquote", "hr", "sup", "sub"}:
            return " "
        if tag in {"h1", "h2"}:
            tag = "h3"
        if closing:
            return f"</{tag}>"
        keep = ""
        if tag == "a":
            href = ""
            for am in _ATTR.finditer(attrs):
                if am.group(1).lower() == "href":
                    raw = am.group(0).split("=", 1)[1].strip().strip("\"'") if "=" in am.group(0) else ""
                    href = raw
            if href and not re.match(r"^\s*(javascript|data|vbscript|file):", href, re.I):
                href = urljoin(base_url, html.unescape(href))
                if href.startswith(("http://", "https://", "mailto:", "tel:")):
                    keep = f' href="{esc(href)}" rel="noopener nofollow"'
        return f"<{tag}{keep}>"

    out = re.sub(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^>]*)?)\s*/?>", clean_tag, out)
    out = re.sub(r"(\s*<br>\s*){3,}", "<br><br>", out)
    out = re.sub(r"<p>\s*</p>", "", out)
    return re.sub(r"[ \t]+", " ", out).strip()


def image_size(path: Path) -> tuple[int, int]:
    """Intrinsic pixel size for png/gif/jpeg/svg; a sane default otherwise."""
    try:
        head = path.read_bytes()
    except OSError:
        return (200, 80)
    if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
        w, h = struct.unpack(">II", head[16:24])
        return (w, h)
    if head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
        w, h = struct.unpack("<HH", head[6:10])
        return (w, h)
    if head[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = struct.unpack(">H", head[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                return (w, h)
            i += 2 + seg
    if path.suffix.lower() == ".svg":
        text = head[:2000].decode("utf-8", "replace")
        vb = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"', text)
        if vb:
            return (max(1, int(float(vb.group(1)))), max(1, int(float(vb.group(2)))))
    return (200, 80)


def _measure(path: Path) -> tuple[int, int]:
    hit = _MEASURED.get(path)
    if hit is None:
        raw = path.read_bytes()
        hit = (len(raw), len(gzip.compress(raw, 9)))
        _MEASURED[path] = hit
    return hit


def _kb(n: int) -> str:
    return f"{n / 1024:.1f}&nbsp;KB"


# ------------------------------------------------------------------ normalisation

def _word_hits(text: str, words: list[str], phrase_weight: int = 1) -> int:
    """Number of keywords present as whole words. A multi-word keyword is a
    more specific signal ("environmental engineer" vs "environmental"), so
    callers may weight phrase hits higher."""
    hits = 0
    for w in words:
        if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text):
            hits += phrase_weight if " " in w else 1
    return hits


def assign_sectors(job: dict[str, Any]) -> list[str]:
    """Up to three canonical sectors, best first. Title, employer name and
    summary carry the weight (SECTOR_W); the raw site labels count once so
    the IE and UK copies of one advert land in the same sector."""
    raw = " ".join(job.get("sectors") or []).lower()
    title = str(job.get("title") or "").lower()
    employer = str(job.get("employer") or "").lower()
    summary = str(job.get("summary") or "").lower()
    body = strip_tags(str(job.get("description_html") or ""))[:3000].lower()
    scored: list[tuple[int, int, int, str]] = []
    raw_named: dict[str, int] = {}
    for pos, (name, _, _, words) in enumerate(TAXONOMY):
        raw_hits = _word_hits(raw, words)
        raw_named[name] = raw_hits
        score = (SECTOR_W["raw"] * raw_hits + SECTOR_W["title"] * _word_hits(title, words, 2) + SECTOR_W["employer"] * _word_hits(employer, words, 2)
                 + SECTOR_W["summary"] * _word_hits(summary, words, 2) + SECTOR_W["body"] * _word_hits(body, words))
        if score >= PRIMARY_MIN:
            scored.append((-score, -raw_hits, pos, name))
    scored.sort()
    if not scored:
        return ["Environmental science & consulting"]
    primary = -scored[0][0]
    # Round 4 (panel v2): a sector whose keyword sits in the TITLE stays a
    # secondary whatever the ratio ("Coastal Engineering PM" keeps Water,
    # "Solar PV Designer" keeps Renewable); the ratio guard only prunes
    # body-only hits.
    top = scored[0][3]

    def keep(name: str, score: int) -> bool:
        if _title_hit(name, title):
            return True  # the title names it
        if name in ENERGY_FAMILY and raw_named.get(name) and score >= SECONDARY_MIN:
            return True  # the source site's own energy label names it (IE adverts; the generic Sustainable/Policy labels stay ratio-gated)
        if top in ENERGY_FAMILY and name in ENERGY_FAMILY:
            return True  # wind / solar / renewable / networks roles overlap by nature
        return score >= SECONDARY_MIN and score * SECONDARY_RATIO >= primary and _secondary_ok(name, title, summary, body)
    return [top] + [name for neg, _, _, name in scored[1:] if keep(name, -neg)][:MAX_SECONDARY]


ENERGY_FAMILY = {"Wind energy", "Solar energy", "Renewable energy & storage", "Energy networks & utilities"}


def _title_hit(name: str, title: str) -> bool:
    words = next(w for n, _, _, w in TAXONOMY if n == name)
    return _word_hits(title, words) > 0


def _secondary_ok(name: str, title: str, summary: str, body: str) -> bool:
    """Built environment as a secondary needs a title hit or at least three
    distinct keywords in the description (summary + body); "an engineering and
    built environment consultancy" describes the employer, not the role (R010)."""
    if name != BUILT_ENV:
        return True
    words = next(w for n, _, _, w in TAXONOMY if n == name)
    return bool(_word_hits(title, words) or _word_hits(summary + " " + body, words) >= 3)


def _job_text(job: dict[str, Any], body_chars: int = 2500) -> str:
    return " ".join(str(job.get(k) or "") for k in ("title", "type", "summary")).lower() + " " + strip_tags(str(job.get("description_html") or ""))[:body_chars].lower()


_IRELAND_RE = re.compile(r"(?<![a-z])(?:republic of )?ireland(?![a-z])")
# "UK/Ireland", "UK & Ireland", "Ireland/UK", "remote from the UK or Ireland"
# in the title or summary name both islands, whatever the scraped region says (R012).
_CROSS_SEP = r"\s*(?:/|&|and|or|\+|,|-|–|—)\s*"  # "UK/Ireland", "UK, Ireland", "UK-Ireland", "Ireland – UK"
CROSS_RE = re.compile(r"(?<![a-z])(?:uk|united kingdom|britain|great britain)" + _CROSS_SEP + r"(?:the\s+)?(?:republic of\s+)?ireland(?![a-z])"
                      r"|(?<![a-z])(?:republic of\s+)?ireland" + _CROSS_SEP + r"(?:the\s+)?(?:uk|united kingdom|britain|great britain)(?![a-z])", re.I)
CROSS_SUMMARY_CHARS = 300  # only the title and the opening of the summary count: "offices in the UK and Ireland" is employer boilerplate


def cross_text(job: dict[str, Any]) -> str:
    return str(job.get("title") or "") + " | " + str(job.get("summary") or "")[:CROSS_SUMMARY_CHARS]


def loc_class(job: dict[str, Any], ie_places: list[str] | None = None, uk_places: list[str] | None = None, ed_key: str = "", ni_places: list[str] | None = None) -> str:
    """ie | uk | ni | remote | cross | intl | unspecified, from the location
    and region fields (plus 'remote' anywhere). Both islands named -> cross.
    Neither named -> remote if the role says so, else the scraped country;
    nothing at all -> unspecified (kept on both boards, labelled as such).

    On the IE edition the scraped region is the site's own facet ("Ireland" or
    "Ireland, United Kingdom" on nearly every advert), so it is not a UK
    signal there: a UK signal must come from the location text (panel 08)."""
    loc = str(job.get("location") or "").lower()
    reg = str(job.get("region") or "").lower()
    if CROSS_RE.search(cross_text(job)):
        return "cross"
    ni_words = NI_WORDS + [w for w in (ni_places or []) if w not in NI_WORDS]
    uk_words = UK_WORDS + list(uk_places or [])
    ie_words = ["dublin", "cork", "galway", "limerick", "waterford"] + list(ie_places or [])
    if ed_key == "ie":
        reg_for_uk = ""  # the IE facet string never names a UK place on purpose
        reg_for_ie = ""  # and a bare "Ireland" there says nothing about the advert
    else:
        reg_for_uk = reg_for_ie = reg
    has_ni = _word_hits(loc + " , " + reg, ni_words) > 0
    # NI phrases are blanked before the GB check so "Bangor, Co. Down" is not
    # also the Welsh Bangor (the ambiguous bare aliases live in _NI_AMBIGUOUS).
    uk_text = loc + " , " + reg_for_uk
    for w in sorted(ni_words, key=len, reverse=True):
        uk_text = re.sub(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", " ", uk_text)
    has_uk = _word_hits(uk_text, uk_words) > 0
    geo_ie = re.sub(r"northern\s+ireland", " ", loc + " , " + reg_for_ie)
    has_ie = bool(_IRELAND_RE.search(geo_ie)) or _word_hits(geo_ie, ie_words) > 0
    has_remote = _word_hits(loc + " " + reg + " " + _job_text(job, 0), REMOTE_WORDS) > 0
    country = str(job.get("country") or "").lower()
    foreign = _word_hits(loc + " , " + reg + " , " + country, FOREIGN_WORDS) > 0
    if has_ie and (has_uk or has_ni):
        return "cross"
    if has_ni and not has_uk:
        return "ni"
    if has_uk:
        return "uk"
    if has_ie:
        return "ie"
    if has_remote:
        return "remote"
    if foreign:
        return "intl"
    if not loc.strip() and not country.strip():
        return "unspecified"
    if "ireland" in country and "northern" not in country:
        return "ie"
    if _word_hits(country, ["united kingdom", "uk", "britain", "great britain", "england", "scotland", "wales"]):
        return "uk"
    return "intl"


def workplace_of(job: dict[str, Any]) -> str:
    """office | hybrid | remote | site | unspecified, from keywords in the text."""
    t = _NOT_OFFICE_RE.sub(" ", _job_text(job))
    if _word_hits(t, ["hybrid"]):
        return "hybrid"
    if _word_hits(t, REMOTE_WORDS + ["fully remote"]):
        return "remote"
    if _word_hits(t, SITE_WORDS):
        return "site"
    if _word_hits(t, OFFICE_WORDS) or _OFFICE_RE.search(t):
        return "office"
    return "unspecified"


# "Microsoft Office", "Office of …" and "head office" are not workplaces
# (panel 08: five roles incl. an EHS Site Manager read as office-based).
_NOT_OFFICE_RE = re.compile(r"\b(?:microsoft office|ms office|office of\b|head office|office 365|box office|office suite)", re.I)
# Round 4: bare "onsite" ("supplier onsite audit") and "reserve(s)" ("energy
# market reserves") are not workplace signals; "nature reserve" still is.
SITE_WORDS = ["site-based", "site based", "on-site", "on site", "site manager", "site managers", "nature reserve", "nature reserves", "patrol", "patrols", "resident engineer", "clerk of works", "field-based", "field based", "fieldwork", "field work"]
_OFFICE_RE = re.compile(r"\bbased (?:in|at|from) (?:our|the) (?:\w+[ -]){0,2}offices?\b")  # "based in our Cork office"
OFFICE_WORDS = ["office-based", "office based", "in the office", "in our office", "in office", "based in our office", "based at our office", "based in the office", "our offices in", "our office in"]  # bare "office" is not a signal


TYPE_CANON = {"full time": "Full-time", "full-time": "Full-time", "part time": "Part-time", "part-time": "Part-time", "fixed term": "Fixed-term", "fixed-term": "Fixed-term",
              "permanent": "Permanent", "contract": "Contract", "volunteer": "Volunteer", "home based": "Home Based", "home-based": "Home Based"}


def canon_type(raw: Any) -> str:
    """One spelling per scraped job type ("Full Time" -> "Full-time") so data, chips and CONTRACT_LABEL agree (round 4)."""
    t = str(raw or "").strip()
    return TYPE_CANON.get(t.lower(), t)


def contract_of(job: dict[str, Any]) -> list[str]:
    """Contract tags from the scraped type plus the text; a role can carry
    several. Round 4: on the permanent / contract / fixed-term axis the
    scraped type wins outright (a "Contract" advert whose body says
    "permanent" is Contract only); the text decides only when the type names
    none of them. Hours (part/full-time) and volunteer come from either."""
    typ = str(job.get("type") or "").lower()
    t = _job_text(job, 1500)
    tags: list[str] = []

    def add(tag: str) -> None:
        if tag not in tags:
            tags.append(tag)
    typed_perm = "permanent" in typ
    typed_ctr = any(w in typ for w in ("contract", "fixed term", "fixed-term", "temporary", "interim"))
    if typed_perm or (not typed_ctr and _word_hits(t, ["permanent"])):
        add("permanent")
    if "fixed term" in typ or "fixed-term" in typ or (not typed_perm and _word_hits(t, ["fixed term", "fixed-term", "maternity cover", "ftc"])):
        add("fixed-term")  # a refinement of Contract, so a "Contract" type still takes it from the text
    # "contractor" (an employer describing its business) is not a contract role (panel 08).
    if typed_ctr or (not typed_perm and (_word_hits(t, ["day rate", "freelance", "contract role", "contract position", "contract basis", "fixed-term contract", "fixed term contract", "temporary contract", "interim"])
                                        or re.search(r"\b\d+[- ](?:month|week|year)s?\s+(?:fixed[- ]term\s+)?contract\b", t))):
        add("contract")
    if _word_hits(t, ["part time", "part-time"]) or "part" in typ:
        add("part-time")
    if "full" in typ or _word_hits(t, ["full time", "full-time"]):
        add("full-time")
    if "volunteer" in typ:
        add("volunteer")
    return tags


def is_agency(employer: str) -> bool:
    name = str(employer or "").lower().strip()
    return name in AGENCY_NAMES or _word_hits(name, AGENCY_WORDS) > 0


def fx_convert(amount: float, from_cur: str, to_cur: str) -> float:
    if from_cur == to_cur:
        return amount
    if from_cur == "GBP" and to_cur == "EUR":
        return amount * FX_GBP_EUR
    if from_cur == "EUR" and to_cur == "GBP":
        return amount / FX_GBP_EUR
    return amount  # USD etc.: no fixed rate published, so no equivalent is shown


def load_region_table(src: Path, ed: str) -> dict[str, Any]:
    path = src / "data" / f"regions_{ed}.json"
    table = json.loads(path.read_text(encoding="utf-8"))
    index_path = src / "assets" / "maps" / "regions_index.json"
    if index_path.exists():
        on_map = set(json.loads(index_path.read_text(encoding="utf-8")).get(ed, []))
        missing = on_map - set(table["regions"])
        if missing:
            raise SystemExit(f"FAIL  regions_{ed}.json lacks map regions: {sorted(missing)}")
    return table


# A compass region followed by a nation is that nation: "South West Wales" is
# Wales, not the South West of England (panel 08).
_NATION_TAIL = r"(?!\s+(?:wales|scotland|ireland))"
# Words that mean "the whole edition": the role goes to the nationwide bucket
# rather than the "elsewhere" one ("United Kingdom (UK)" on the UK board).
HOME_WORDS = {"ie": ["ireland", "republic of ireland", "nationwide", "all ireland", "countrywide"],
              "uk": ["united kingdom", "uk", "uk-wide", "uk wide", "great britain", "nationwide", "countrywide"]}


def resolve_regions(job: dict[str, Any], table: dict[str, Any], ed: dict[str, Any]) -> list[str]:
    text = " , ".join(str(job.get(k) or "") for k in ("region", "location")).lower()
    found: list[str] = []
    for name, aliases in table["regions"].items():
        for alias in [name] + list(aliases):
            a = alias.lower()
            tail = "" if any(n in a for n in ("wales", "scotland", "ireland")) else _NATION_TAIL
            if re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])" + tail, text):
                if name not in found:
                    found.append(name)
                break
    if found:
        return found
    ed_key = "ie" if ed["short"] == "IE" else "uk"
    home_text = re.sub(r"northern\s+ireland", " ", text)
    if _word_hits(home_text, HOME_WORDS[ed_key]):
        return [ed["none"]]
    if _word_hits(text, ed["outside_words"]):
        return [ed["elsewhere"]]
    return [ed["none"]]


def social_links(src: Path, ed_key: str) -> list[str]:
    """This edition's own social profiles, read from the scraped social page."""
    path = src / "data" / f"pages_{ed_key}.json"
    if not path.exists():
        return []
    pages = json.loads(path.read_text(encoding="utf-8"))
    want = "greenjobsireland" if ed_key == "ie" else "greenjobsuk"
    out: list[str] = []
    for key, page in pages.items():
        if "social" not in key:
            continue
        for link in page.get("links") or []:
            url = link if isinstance(link, str) else str(link.get("href") or link.get("url") or "")
            if re.search(r"(facebook|linkedin|twitter|x)\.com", url, re.I) and want in url.lower().replace("irl", "ireland").replace("?ref=hl", ""):
                clean = url.split("?")[0]
                if clean not in out:
                    out.append(clean)
    return out[:3]


# The source site serves some adverts in the wrong encoding, so "£" arrives
# as U+FFFD (or "Â£"). Only a replacement character right before a figure
# (optionally spaced) or a "k" amount is repaired; "�Competitive" is left.
_GARBLED_POUND_RE = re.compile(r"(?:\ufffd|\u00c2\u00a3|\u00c2\ufffd)(?=\s?(?:\d|k\b))")


def repair_pounds(text: str) -> str:
    return _GARBLED_POUND_RE.sub("\u00a3", text or "")


def build_today(raw: dict[str, Any], today: date | None = None) -> date:
    """The build date: the --today flag, else the dataset's fetched date, else
    the wall clock (only when the dataset carries no date)."""
    if today:
        return today
    try:
        return date.fromisoformat(str(raw.get("fetched") or "")[:10])
    except ValueError:
        return date.today()


def days_until(iso: str, today: date) -> int | None:
    """Whole calendar days from `today` to an ISO date (negative = past), or
    None when unknown. The one closing-date rule, mirrored by lib.js daysUntil."""
    try:
        return (date.fromisoformat(iso) - today).days if iso else None
    except ValueError:
        return None


def is_closed(j: dict[str, Any], today: date) -> bool:
    """A role whose closing date is before the build date is closed."""
    d = days_until(j.get("closing") or "", today)
    return d is not None and d < 0


def closing_within(j: dict[str, Any], today: date, n: int = 7) -> bool:
    """Closing date within the next n days: 0..n inclusive (today counts)."""
    d = days_until(j.get("closing") or "", today)
    return d is not None and 0 <= d <= n


def new_this_week(j: dict[str, Any], today: date) -> bool:
    """Posted in the last 7 days: 0..6 days ago (today counts, day 7 does not)."""
    d = days_until(j.get("posted") or "", today)
    return d is not None and -6 <= d <= 0


def sterling_twins(src: Path) -> dict[str, dict[str, Any]]:
    """Index of the greenjobs.co.uk dataset (src/data/uk.json) for
    sterling_correction(): by id, by slug and by (title, employer), lower-cased.
    Empty when the file is absent (fixture builds)."""
    path = src / "data" / "uk.json"
    if not path.is_file():
        return {}
    try:
        jobs = json.loads(path.read_text(encoding="utf-8")).get("jobs") or []
    except (OSError, ValueError):
        return {}
    idx: dict[str, Any] = {}
    for j in jobs:
        if j.get("currency") != "GBP" or not isinstance(j.get("salary_min"), (int, float)) and not isinstance(j.get("salary_max"), (int, float)):
            continue
        for key in (f"id:{str(j.get('id') or '').strip()}", f"slug:{str(j.get('slug') or '').strip().lower()}",
                    f"te:{str(j.get('title') or '').strip().lower()}|{str(j.get('employer') or '').strip().lower()}"):
            if not key.endswith((":", "|")):
                idx.setdefault(key, []).append(j)  # slugs collide (3x senior-health-and-safety-consultant): keep every candidate
    return idx


def _pick_twin(cands: list[dict[str, Any]], j: dict[str, Any]) -> dict[str, Any] | None:
    """The candidate whose (salary_min, salary_max) equals the IE figures
    numerically (the source site relabels 1:1), nearest posted date first."""
    same = [t for t in cands if (t.get("salary_min"), t.get("salary_max")) == (j.get("salary_min"), j.get("salary_max"))]
    if not same:
        return None
    mine = parse_date(j.get("posted"))

    def gap(t: dict[str, Any]) -> int:
        theirs = parse_date(t.get("posted"))
        if not mine or not theirs:
            return 10 ** 6
        return abs((date.fromisoformat(mine) - date.fromisoformat(theirs)).days)
    return min(same, key=gap)


def sterling_correction(j: dict[str, Any], lc: str, twins: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Keith B2: a UK-only role on greenjobs.ie is scraped with its sterling
    figures relabelled as euros. Return the greenjobs.co.uk twin's advertised
    figures ({salary_min, salary_max, currency, salary_text}) when the IE job
    is loc_class uk, priced in EUR, and a twin exists by id, slug or
    title + employer with the same (salary_min, salary_max) numerically (the
    source relabels 1:1); where several share a slug the nearest posted date
    wins (round 4: IE 11495292 €55-60k -> UK 11495291 £55-60k, not the
    £62-67k namesake). None when no twin is found: the scraped euros stay."""
    if lc != "uk" or j.get("currency") != "EUR" or not twins:
        return None
    twin = None
    for key in (f"id:{str(j.get('id') or '').strip()}", f"slug:{str(j.get('slug') or '').strip().lower()}",
                f"te:{str(j.get('title') or '').strip().lower()}|{str(j.get('employer') or '').strip().lower()}"):
        twin = _pick_twin(twins.get(key) or [], j)
        if twin is not None:
            break
    if twin is None:
        return None
    return {"salary_min": twin.get("salary_min"), "salary_max": twin.get("salary_max"), "currency": "GBP",
            "salary_text": repair_pounds(str(twin.get("salary_text") or "")) or "", "period": twin.get("period") or j.get("period")}


def normalise(raw: dict[str, Any], ed_key: str, src: Path, logos_dir: Path, today: date | None = None) -> dict[str, Any]:
    ed = EDITIONS[ed_key]
    table = load_region_table(src, ed_key)
    ie_places, uk_places = place_words(src)
    ni_places = ni_place_words(src)
    today = build_today(raw, today)
    twins = sterling_twins(src) if ed_key == "ie" else {}
    jobs_out: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    closed: list[dict[str, str]] = []
    corrected: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for j in raw.get("jobs") or []:
        jid = str(j.get("id") or "").strip() or slugify(j.get("slug") or j.get("title") or "")
        if jid in seen_ids or not j.get("title") or not str(j.get("url") or "").startswith(("http://", "https://")):
            continue
        seen_ids.add(jid)
        j = {**j, "description_html": repair_pounds(str(j.get("description_html") or "")), "summary": repair_pounds(str(j.get("summary") or "")),
             "salary_text": repair_pounds(str(j.get("salary_text") or "")), "title": repair_pounds(str(j.get("title") or ""))}
        closing = parse_date(j.get("closing"))
        if is_closed({"closing": closing}, today):
            closed.append({"id": jid, "title": str(j["title"]).strip(), "closing": closing})
            continue
        sectors = assign_sectors(j)
        color = next(c for n, c, _, _ in TAXONOMY if n == sectors[0])
        logo = ""
        lw = lh = 0
        logo_url = str(j.get("logo_url") or "")
        if logo_url:
            cand = logos_dir / Path(logo_url.split("?")[0]).name
            if cand.is_file():
                logo = cand.name
                lw, lh = image_size(cand)
        desc = sanitise_html(str(j.get("description_html") or ""), str(j.get("url")))
        text = strip_tags(desc)
        lc = loc_class(j, ie_places, uk_places, ed_key, ni_places)
        if lc not in EDITION_INCLUDES[ed_key]:
            excluded.append({"id": jid, "title": str(j["title"]).strip(), "loc_class": lc, "location": str(j.get("location") or "")})
            continue
        fix = sterling_correction(j, lc, twins)
        currency_source = ""
        if fix:
            j = {**j, **fix}
            currency_source = STERLING_SOURCE
            corrected.append({"id": jid, "title": str(j["title"]).strip(), "salary_text": fix["salary_text"]})
        elif ed_key == "ie" and lc == "uk" and j.get("currency") == "EUR" and (isinstance(j.get("salary_min"), (int, float)) or isinstance(j.get("salary_max"), (int, float))):
            currency_source = UNVERIFIED_SOURCE  # never invent sterling: say where the figure came from
        jobs_out.append({
            "id": jid, "slug": slugify(j.get("slug") or j.get("title")), "title": str(j["title"]).strip(),
            "employer": str(j.get("employer") or "Confidential employer").strip(), "location": str(j.get("location") or ed["none"]).strip(),
            "regions": resolve_regions(j, table, ed), "type": canon_type(j.get("type")),
            "sal_min": j.get("salary_min") if isinstance(j.get("salary_min"), (int, float)) else None,
            "sal_max": j.get("salary_max") if isinstance(j.get("salary_max"), (int, float)) else None,
            "cur": j.get("currency") or None, "period": j.get("period") or None, "sal_text": str(j.get("salary_text") or "").strip(),
            "sectors": sectors, "color": color, "posted": parse_date(j.get("posted")), "closing": closing,
            "summary": str(j.get("summary") or "").strip() or text[:180], "text": text[:1500], "description_html": desc,
            "logo": logo, "lw": lw, "lh": lh, "url": str(j["url"]).strip(), "href": f"{jid}/index.html",
            "loc_class": lc, "workplace": workplace_of(j), "level": level_of(j["title"]), "contract": contract_of(j),
            "agency": is_agency(j.get("employer") or ""), "currency_source": currency_source,
        })
    jobs_out.sort(key=lambda x: (x["posted"], x["title"]), reverse=True)
    sector_counts = Counter(s for j in jobs_out for s in j["sectors"])
    sectors = [{"name": n, "n": sector_counts.get(n, 0), "color": c, "dark": d} for n, c, d, _ in TAXONOMY]
    sectors.sort(key=lambda s: (-s["n"], s["name"]))
    region_counts = Counter(r for j in jobs_out for r in j["regions"])
    # Every mapped region is listed, at 0 when empty (R072/R077: Northern
    # Ireland and East Midlands stay a location option on the UK edition).
    for name in table["regions"]:
        region_counts.setdefault(name, 0)
    regions = [{"name": n, "n": c, "on_map": n in table["regions"]} for n, c in sorted(region_counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    types = [{"name": n, "n": c} for n, c in Counter(j["type"] for j in jobs_out if j["type"]).most_common()]
    employers: dict[str, dict[str, Any]] = {}
    for e in raw.get("employers") or []:
        name = str(e.get("name") or "").strip()
        if name:
            employers[name] = {"name": name, "url": str(e.get("url") or ""), "logo": "", "lw": 0, "lh": 0}
    for j in jobs_out:
        rec = employers.setdefault(j["employer"], {"name": j["employer"], "url": "", "logo": "", "lw": 0, "lh": 0})
        if j["logo"] and not rec["logo"]:
            rec.update(logo=j["logo"], lw=j["lw"], lh=j["lh"])
    # Employers whose adverts carry no logo may still have one in the scraper's
    # manifest (assets/logos/logos.json, keyed by employer name) — visual 7.
    manifest = logo_manifest(logos_dir)
    for rec in employers.values():
        if not rec["logo"]:
            cand = manifest.get(rec["name"].lower())
            if cand and (logos_dir / cand).is_file():
                rec.update(logo=cand)
                rec["lw"], rec["lh"] = image_size(logos_dir / cand)
    return {
        "ed": ed_key, "site": str(raw.get("site") or ed["domain"]), "fetched": str(raw.get("fetched") or today.isoformat())[:10], "today": today.isoformat(),
        "jobs": jobs_out, "sectors": sectors, "regions": regions, "types": types,
        "employers": list(employers.values()), "about": str(raw.get("about") or "").strip(),
        "contact": raw.get("contact") or {}, "network_sites": raw.get("network_sites") or [],
        "region_table": table, "social": social_links(src, ed_key), "excluded": excluded, "closed": closed, "corrected": corrected,
    }


def logo_manifest(logos_dir: Path) -> dict[str, str]:
    """{employer name lower: file} from the scraper's logos.json; {} when absent."""
    path = logos_dir / "logos.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k).lower(): str(v.get("file") or "") for k, v in raw.items() if isinstance(v, dict) and v.get("file") and not str(k).startswith("site:")}


def place_words(src: Path) -> tuple[list[str], list[str]]:
    """(Irish place words, British place words) from the two region tables,
    for loc_class. Northern Ireland's aliases are left out of the British list
    (NI_WORDS covers them) and ambiguous short aliases are dropped."""
    def words(ed: str, skip: set[str]) -> list[str]:
        path = src / "data" / f"regions_{ed}.json"
        if not path.exists():
            return []
        table = json.loads(path.read_text(encoding="utf-8"))
        out: list[str] = []
        for name, aliases in table["regions"].items():
            if name in skip:
                continue
            for w in [name] + list(aliases):
                w = w.lower()
                if len(w) > 3 and w not in ("down", "country", "nationwide"):
                    out.append(w)
        return out
    return words("ie", set()), words("uk", {"Northern Ireland"})


def ni_place_words(src: Path) -> list[str]:
    """Northern Ireland aliases from the src region table (lower-case, the
    ambiguous short ones dropped), for loc_class."""
    path = src / "data" / "regions_uk.json"
    if not path.exists():
        return []
    table = json.loads(path.read_text(encoding="utf-8"))
    return [w.lower() for w in table["regions"].get("Northern Ireland", []) if w.lower() not in _NI_AMBIGUOUS]


def rnd(x: float, ndigits: int = 0) -> float:
    """Round half away from zero like JavaScript's Math.round (Python's
    round() is banker's: round(324.5) == 324, Math.round(324.5) == 325)."""
    q = Decimal(1).scaleb(-ndigits)
    v = float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))
    return int(v) if ndigits <= 0 else v


JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def check_dataset(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not data["jobs"]:
        problems.append("no usable jobs after normalisation")
    for j in data["jobs"]:
        if not JOB_ID_RE.match(j["id"]):
            problems.append(f"job id is not a safe path segment (^[A-Za-z0-9_-]+$): {j['id']!r}")
        if any(ch in j["title"] for ch in "<>"):
            problems.append(f"title contains angle brackets: {j['title']!r}")
        if "|" in " ".join(j["sectors"]):
            problems.append(f"sector contains '|': {j['sectors']}")
    return problems


# ------------------------------------------------------------------ brief.md facts

def read_brief(src: Path) -> dict[str, Any]:
    """brief.md is written by the research worker. Facts are its bullet lines;
    a heading containing 'fact' narrows the list. Nothing else is inferred."""
    path = src / "data" / "brief.md"
    if not path.exists():
        return {"facts": [], "b_corp": False, "employer_points": [], "text": "", "social": []}
    text = path.read_text(encoding="utf-8")
    facts: list[str] = []
    employer_points: list[str] = []
    section = ""
    for line in text.splitlines():
        if line.startswith("#"):
            section = line.lower()
            continue
        m = re.match(r"^\s*[-*]\s+(.+)", line)
        if not m:
            continue
        item = re.sub(r"\s+", " ", m.group(1)).strip()
        if "employer" in section or "advertis" in section:
            employer_points.append(item)
        elif "fact" in section or "why" in section or not section:
            facts.append(item)
    social = re.findall(r"https?://(?:www\.)?(?:linkedin\.com|twitter\.com|x\.com|facebook\.com|instagram\.com|bsky\.app)/[^\s)>\]]+", text)
    return {"facts": facts, "b_corp": bool(re.search(r"\bB[\s-]?Corp\b", text)), "employer_points": employer_points,
            "text": text, "social": sorted(set(social))}


def derived_facts(data: dict[str, Any]) -> list[tuple[str, str]]:
    facts: list[tuple[str, str]] = []
    n_sites = len(data["network_sites"])
    if n_sites:
        facts.append((f"One of {n_sites} specialist boards", "GreenJobs is part of a network of sites, each dedicated to one corner of the green economy — so a role posted here reaches the right readers."))
    m = re.search(r"\b(19|20)\d{2}\b", data["about"])
    if m:
        facts.append((f"Green recruitment since {m.group(0)}", "Wholly dedicated to environmental and renewable energy roles — not a general board with a green filter."))
    contact = data["contact"] or {}
    addr = str(contact.get("address") or "")
    if addr:
        town = "Ennis, Co. Clare" if "ennis" in addr.lower() else addr.split(",")[0]
        facts.append((f"Real people in {town}", "Phone and email support in local hours, for candidates and employers alike."))
    return facts[:3]


# ------------------------------------------------------------------ rendering primitives

def render(template: str, ctx: dict[str, str]) -> str:
    """{{key}} substitution. Values are already HTML. Unknown keys fail loudly."""
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in ctx:
            raise KeyError(f"template key {{{{{key}}}}} has no value")
        return ctx[key]
    return re.sub(r"\{\{([a-zA-Z0-9_:]+)\}\}", sub, template)


def sparkline_weeks(jobs: list[dict[str, Any]], today: date, weeks: int = 8) -> list[int]:
    counts = [0] * weeks
    for j in jobs:
        if not j["posted"]:
            continue
        try:
            d = date.fromisoformat(j["posted"])
        except ValueError:
            continue
        idx = weeks - 1 - (today - d).days // 7
        if 0 <= idx < weeks:
            counts[idx] += 1
    return counts


def sparkline_svg(vals: list[int], w: int = 120, h: int = 34) -> str:
    mx = max(vals) or 1
    n = len(vals)
    pad = 3
    pts = [((pad + i * (w - 2 * pad) / max(1, n - 1)), (h - pad - (v / mx) * (h - 2 * pad))) for i, v in enumerate(vals)]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" aria-hidden="true" focusable="false"><path class="fill" d="{line} L{lx:.1f},{h} L{pts[0][0]:.1f},{h}Z"/>'
            f'<path d="{line}" pathLength="1"/><circle cx="{lx:.1f}" cy="{ly:.1f}" r="3"/></svg>')


def salary_label(j: dict[str, Any], ed_cur: str = "") -> str:
    """Mirror of lib.js salaryLabel for server-rendered cards. Always in the
    advertised currency; with ed_cur given and different from the job's, the
    label gains "(advertised in euros, about £…)" at the fixed rate (B2)."""
    cur = j.get("cur") or ""
    sym = CUR_SYM.get(cur, "")

    def money(n: float, s: str = sym) -> str:
        if n >= 1000:
            return f"{s}{int(n / 1000)}k" if n % 1000 == 0 else f"{s}{rnd(n / 100) / 10:g}k"
        return f"{s}{n:g}"
    lo, hi = j.get("sal_min"), j.get("sal_max")
    if lo is None and hi is None:
        return ""
    per = {"year": "", "month": "/mo", "hour": "/hr", "day": "/day", "week": "/wk"}.get(j.get("period") or "year", "")
    prefix = "up to " if (hi is None and lo is not None and re.search(r"up to", j.get("sal_text") or "", re.I)) else ""

    def fmt(a: float | None, b: float | None, s: str) -> str:
        if a is not None and b is not None and a != b:
            return f"{money(a, s)}–{money(b, s).lstrip(s)}{per}"
        return f"{prefix}{money(a if a is not None else b, s)}{per}"  # type: ignore[arg-type]
    label = fmt(lo, hi, sym)
    if ed_cur and cur and cur != ed_cur and fx_convert(1, cur, ed_cur) != 1:
        eq_lo = rnd(fx_convert(lo, cur, ed_cur), -2) if lo is not None else None
        eq_hi = rnd(fx_convert(hi, cur, ed_cur), -2) if hi is not None else None
        label += f" (advertised in {CUR_NAME.get(cur, cur)}, about {fmt(eq_lo, eq_hi, CUR_SYM.get(ed_cur, ''))})"
    return label


def currency_note(j: dict[str, Any], ed_cur: str) -> str:
    """'Advertised in euros' when the advertised currency differs from the edition's, else ''."""
    cur = j.get("cur") or ""
    if not cur or cur == ed_cur or (j.get("sal_min") is None and j.get("sal_max") is None):
        return ""
    return f"Advertised in {CUR_NAME.get(cur, cur)}"


ANNUAL_MULT = {"year": 1, "month": 12, "week": 52, "day": 230, "hour": 1950}  # mirrors lib.js annual()
COMPARABLE_CURRENCIES = {"EUR", "GBP"}  # the only currencies with a fixed rate; anything else is shown but never compared


def median_salary(jobs: list[dict[str, Any]], sym: str, ed_cur: str = "") -> str:
    """Median of annualised range midpoints in the edition currency, formatted
    like lib.js money(); the same figure JavaScript recomputes, so the page is
    right before JS runs."""
    mids: list[float] = []
    for j in jobs:
        a = annual_mid(j, ed_cur)
        if a:
            mids.append(a[2])
    if not mids:
        return "n/a"
    mids.sort()
    k = len(mids) // 2
    med = mids[k] if len(mids) % 2 else (mids[k - 1] + mids[k]) / 2
    return money_k(med, sym)


def date_long(iso: str) -> str:
    """'2026-09-22' -> '22 September 2026'. Every date a visitor reads goes
    through here (visual N4); ISO stays only in datetime= attributes and JSON-LD."""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def snapshot_label(iso: str) -> str:
    """'2026-09-22' -> 'Snapshot of 22 September 2026'."""
    return f"Snapshot of {date_long(iso)}"


def ago(iso: str, today: date) -> str:
    if not iso:
        return ""
    try:
        d = (today - date.fromisoformat(iso)).days
    except ValueError:
        return ""
    if d <= 0:
        return "Today"
    if d == 1:
        return "Yesterday"
    if d < 7:
        return f"{d} days ago"
    if d < 30:
        return f"{rnd(d / 7)} wk ago"
    return f"{rnd(d / 30)} mo ago"


SAVE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg>'


def logo_img(j: dict[str, Any], root: str, cls: str = "role__logo") -> str:
    if j.get("logo"):
        return (f'<img class="{cls}" src="{root}assets/logos/{esc(j["logo"])}" alt="" width="{j["lw"] or 200}" height="{j["lh"] or 80}" loading="lazy" decoding="async">')
    initial = esc((j.get("employer") or "?")[:1])
    return f'<div class="{cls} role__logo--t" aria-hidden="true">{initial}</div>'


def loc_badge(j: dict[str, Any]) -> str:
    lc = j.get("loc_class") or ""
    return f'<span class="tag tag--loc" data-loc="{esc(lc)}">{esc(LOC_LABEL.get(lc, ""))}</span>' if lc in LOC_LABEL else ""


def role_card(j: dict[str, Any], root: str, jobs_dir: str, today: date, ed_cur: str = "") -> str:
    sal = salary_label(j, ed_cur)
    chips = (f'<span class="tag tag--sal">{esc(sal)}</span>' if sal else "") + (f'<span class="tag tag--type">{esc(j["type"])}</span>' if j["type"] else "") + loc_badge(j)
    return (f'<article class="role reveal">'
            f'<div class="role__top">{logo_img(j, root)}<button class="save" type="button" data-save="{esc(j["id"])}" data-title="{esc(j["title"])}" aria-pressed="false" aria-label="Save: {esc(j["title"])}">{SAVE_ICON}</button></div>'
            f'<h3><a href="{jobs_dir}{esc(j["href"])}">{esc(j["title"])}</a></h3>'
            f'<p class="role__emp"><span>{esc(j["employer"])}</span><span>{esc(j["location"])}</span></p>'
            f'<div class="role__meta">{chips}<time datetime="{esc(j["posted"])}">{esc(ago(j["posted"], today))}</time></div>'
            + (f'<p class="role__note">{esc(UNVERIFIED_NOTE)}.</p>' if j.get("currency_source") == UNVERIFIED_SOURCE else "") + '</article>')


LEVELS: list[tuple[str, re.Pattern[str]]] = [
    ("Director/Associate", re.compile(r"\b(director|associate director|head of|chief|partner|vice president|vp)\b", re.I)),
    ("Senior/Principal", re.compile(r"\b(senior|principal|lead(?!-free)|chartered)\b", re.I)),  # "lead-free" is a material, not a rank
    # "Assistant Project Manager" / "Assistant Director" are mid-level titles, not early-career ones.
    ("Graduate/Early career", re.compile(r"\b(graduate|junior|trainee|intern|internship|apprentice|entry[- ]level|assistant(?!(?:\s+\w+){0,2}\s+(?:manager|director|head|lead|engineer|ecologist|consultant)\b)|placement|student)\b", re.I)),
]


def contract_row(j: dict[str, Any]) -> str:
    """One facts-panel row for the pattern of employment (visual 24): the
    contract tags, with the scraped type folded in only when it adds a value
    the tags do not already say (e.g. 'Home Based')."""
    labels = [CONTRACT_LABEL[c] for c in j.get("contract") or []]
    typ = str(j.get("type") or "").strip()
    if typ and typ.lower().replace(" ", "-") not in {lb.lower() for lb in labels} and typ.lower() not in {"home based", "home-based"}:
        labels.append(typ)
    return ", ".join(labels)


def no_break_dash(title: str) -> str:
    """'Landscape Developer – UK & Ireland' keeps its dash but never wraps
    before it: the space before an en/em dash becomes a no-break space."""
    return re.sub(r" ([\u2013\u2014])", "\u00a0\\1", title)


def level_of(title: str) -> str:
    """Career level read from the title alone (a rule, labelled as such on the
    page): Director/Associate > Senior/Principal > Graduate/Early career, else Mid-level."""
    for name, pat in LEVELS:
        if pat.search(title):
            return name
    return "Mid-level"


def home_row(j: dict[str, Any], root: str, jobs_dir: str, today: date, ed_cur: str = "") -> str:
    """The jobs-page row (jobs.js row()) rendered at build time for the home
    listing, plus a career-level chip and the location badge (B3)."""
    sal = salary_label(j, ed_cur)
    lvl = level_of(j["title"])
    sec = f'<span class="tag"><i style="background:{esc(j["color"] or "")}"></i>{esc(j["sectors"][0])}</span>' if j["sectors"] else ""
    salc = (f'<span class="tag tag--sal">{esc(sal)}</span>' if sal else "") + loc_badge(j)
    return (f'<article class="row" data-id="{esc(j["id"])}">{logo_img(j, root)}'
            f'<div class="row__body"><h3><a href="{jobs_dir}{esc(j["href"])}">{esc(j["title"])}</a></h3>'
            f'<div class="row__meta"><span>{esc(j["employer"])}</span><span aria-hidden="true">·</span><span>{esc(j["location"])}</span>'
            f'<span class="tag tag--lvl" title="Career level">{esc(lvl)}</span>'
            f'{salc}{sec}</div></div>'
            f'<div class="row__r"><time datetime="{esc(j["posted"])}">{esc(ago(j["posted"], today))}</time><span>{esc(j["type"])}</span></div>'
            f'<button class="save" type="button" data-save="{esc(j["id"])}" data-title="{esc(j["title"])}" aria-pressed="false" aria-label="Save: {esc(j["title"])}">{SAVE_ICON}</button></article>')


def sector_stat(in_sector: list[dict[str, Any]], sym: str) -> str:
    """One real figure per sector tile: the median disclosed salary when at
    least three roles disclose one, otherwise how many disclose pay."""
    disclosed = sum(1 for j in in_sector if j["sal_min"] is not None or j["sal_max"] is not None)
    ed_cur = {"€": "EUR", "£": "GBP"}.get(sym, "")
    med = median_salary(in_sector, sym, ed_cur) if disclosed >= 3 else "n/a"
    if med != "n/a":
        return f"median disclosed {med}"
    if disclosed == 0:
        return "no disclosed salaries yet"
    return f"{disclosed} disclosed {'salary' if disclosed == 1 else 'salaries'}"


def sector_tiles(data: dict[str, Any], jobs_href: str, today: date, sym: str = "€") -> str:
    out = []
    live = [s for s in data["sectors"] if s["n"] > 0][:9]
    for i, s in enumerate(live):
        in_sector = [j for j in data["jobs"] if s["name"] in j["sectors"]]
        spark = sparkline_svg(sparkline_weeks(in_sector, today))
        out.append(
            f'<a class="sect reveal{" sect--lead" if i == 0 else ""}" href="{jobs_href}?sector={qs(s["name"])}" style="--sc:{s["color"]}">'
            f'<span class="arw" aria-hidden="true">&#8599;</span><h3>{esc(s["name"])}</h3>'
            f'<p class="n num">{s["n"]}<small>{"role" if s["n"] == 1 else "roles"} · {esc(sector_stat(in_sector, sym))}</small></p>'
            f'{spark}<span class="vh">Postings over the last eight weeks</span></a>')
    return "".join(out)


def plural(unit: str) -> str:
    """'county' -> 'counties', 'region' -> 'regions'."""
    return unit[:-1] + "ies" if unit.endswith("y") and unit[-2:-1] not in "aeiou" else unit + "s"


def employers_strip(data: dict[str, Any], root: str, cap: int | None = 12) -> dict[str, str]:
    """The home-page logo strip. Only employers with at least one live role in
    this edition may appear under "Employers hiring now"; when fewer than six
    have live roles the strip is retitled to the network and may include the
    featured recruiters honestly. `cap` limits the home strip; the employers
    page passes None so every live employer is listed. Returns html/title/sub;
    html is '' when empty."""
    live_names = {j["employer"] for j in data["jobs"]}
    live = sorted((e for e in data["employers"] if e["name"] in live_names), key=lambda e: (not e["logo"], e["name"]))
    if len(live) >= 6:
        mode, items = "hiring", live[:cap] if cap else live
        title, sub = "Employers hiring now", f"Organisations with live roles on {esc(data['site'])} this week."
    else:
        mode = "network"
        items = live  # never padded with names that have no live role (R041 / visual 7)
        n = len(live)
        title = "Employers on the GreenJobs network"
        # No employer count on IE (Keith A2 / visual N5); the UK edition may say it when n >= 10.
        sub = (f"{n} organisations with live roles on {esc(data['site'])} this week." if data.get("ed") == "uk" and n >= 10
               else f"Organisations with live roles on {esc(data['site'])} this week.")
    if not items:
        return {"html": "", "title": title, "sub": sub, "mode": mode}
    cells = []
    for i, e in enumerate(items):
        # The first eight tiles load eagerly so the strip never opens on blank boxes (visual N3);
        # an employer without a logo gets a monogram disc so text and logo tiles align (visual 7).
        inner = (f'<img src="{root}assets/logos/{esc(e["logo"])}" alt="{esc(e["name"])}" width="{e["lw"] or 200}" height="{e["lh"] or 80}" loading="{"eager" if i < 8 else "lazy"}" decoding="async">'
                 if e["logo"] else f'<span class="mono" aria-hidden="true">{esc(e["name"][:1].upper())}</span><span>{esc(e["name"])}</span>')
        url = e["url"] if str(e["url"]).startswith("http") else ""
        cells.append(f'<a class="emp" href="{esc(url)}" rel="noopener">{inner}</a>' if url else f'<div class="emp">{inner}</div>')
    track = "".join(cells)
    if len(items) < 6:
        # A short strip (the IE board has three live employers) is a static row: no duplicated
        # logos, no scrolling, no Pause button.
        return {"html": f'<div class="marq marq--static" data-strip="{mode}"><div class="marq__track">{track}</div></div>', "title": title, "sub": sub, "mode": mode}
    html_out = (f'<div class="marq" data-marq data-strip="{mode}"><div class="marq__track">{track}<span class="marq__dup" aria-hidden="true" style="display:contents">{track}</span></div></div>'
                f'<p style="text-align:right;margin-top:8px"><button class="btn btn--sm btn--ghost" type="button" data-marq-pause aria-pressed="false">Pause</button></p>')
    return {"html": html_out, "title": title, "sub": sub, "mode": mode}


# Three facts for the home page, each traceable to a row in src/data/brief.md
# (sections 1, 2/4 and 5). Used only when brief.md is present; otherwise the
# facts are derived from the dataset itself.
BRIEF_FACTS = [
    ("Specialist green job network since 2008", "A job board wholly dedicated to the environmental and renewable energy market, not a general board with a green filter."),
    ("One posting, the whole network", "Each job is shown across the relevant sites in the GreenJobs Network of Websites at no additional cost, so it reaches the readers who want it."),
    ("Alerts that do the searching", "Up to ten job alerts by email, a weekly jobs newsletter, saved roles and one-tap applications on any device."),
]


# B Corp: brief.md section 3 supports only the mark with its alt text. The
# explainer (Keith A3) describes what certification means; no date or score.
BCORP_ALT = "Certified B Corporation"
BCORP_NOTE = "B Corps are businesses independently certified for social and environmental performance, accountability and transparency."


def bcorp_line(brief: dict[str, Any] | None, root: str, where: str = "footer") -> str:
    """The B Corp mark plus its one-line explainer, or '' when brief.md does
    not carry the mark. `where` picks the wrapper class."""
    if not (brief and brief.get("b_corp") and brief.get("bcorp_size")):
        return ""
    w, h = brief["bcorp_size"]
    img = (f'<img class="bcorp" src="{root}assets/logos/b-corp-logo.svg" alt="{BCORP_ALT}" title="{BCORP_NOTE}" '
           f'width="{w}" height="{h}" loading="lazy">')
    return f'<p class="bcorp-line bcorp-line--{where}">{img}<span>{BCORP_NOTE}</span></p>'


def hero_facts(data: dict[str, Any], n_emp: int) -> str:
    """Credibility markers for the hero facts row (Keith A2). The IE edition
    never shows an employer count; the UK edition keeps it. Every number is
    read from the dataset or brief-derived data."""
    parts: list[str] = []
    if data["ed"] == "uk" and n_emp:
        parts.append(f'<span><b class="num">{n_emp}</b> employers hiring now</span>')
    m = re.search(r"\b(19|20)\d{2}\b", data.get("about") or "")
    if m:
        parts.append(f"<span>Specialist green job network since {m.group(0)}</span>")
    n_sites = len(data.get("network_sites") or [])
    if n_sites:
        parts.append(f'<span><b class="num">{n_sites}</b> specialist job sites</span>')
    n_sectors = sum(1 for s in data["sectors"] if s["n"])
    parts.append(f'<span>Roles across <b class="num">{n_sectors}</b> sectors</span>')
    return "".join(parts)


def network_inline(data: dict[str, Any]) -> str:
    return ", ".join(f'<a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}</a>' for s in data["network_sites"] if str(s.get("url", "")).startswith("http"))


def keith_changes(src: Path) -> str:
    """Render the working checklist (KEITH_CHANGES_CHECKLIST.md beside src/) as
    a status list for the evidence page. Parses '- [ ] / [x] / [~] / [-]'
    lines under '## ' headings; missing file -> ''."""
    path = src.parent / "KEITH_CHANGES_CHECKLIST.md"
    if not path.exists():
        return ""
    status = {" ": ("open", "Open"), "x": ("done", "Done"), "~": ("partial", "Partial"), "-": ("notdone", "Not done")}
    out: list[str] = []
    open_ul = False
    for line in path.read_text(encoding="utf-8").splitlines():
        h = re.match(r"^##\s+(.+)", line)
        if h:
            if open_ul:
                out.append("</ul>")
            out.append(f'<h3>{esc(h.group(1))}</h3><ul class="changes">')
            open_ul = True
            continue
        m = re.match(r"^\s*-\s+\[([ x~-])\]\s+(.+)", line)
        if m and open_ul:
            cls, label = status[m.group(1)]
            out.append(f'<li class="chg chg--{cls}"><b>{label}</b> {esc(m.group(2))}</li>')
    if open_ul:
        out.append("</ul>")
    return "".join(out)


def facts_block(brief: dict[str, Any], data: dict[str, Any]) -> str:
    items: list[tuple[str, str]] = list(BRIEF_FACTS) if brief.get("text") else []
    if len(items) < 3:
        for fact in derived_facts(data):
            if len(items) >= 3:
                break
            if fact[0] not in [i[0] for i in items]:
                items.append(fact)
    return "".join(f'<div class="fact reveal"><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for h, p in items[:3])


def map_svg(src: Path, ed: str, counts: dict[str, int] | None = None) -> str:
    """The edition map. When counts are given, every region carries data-n,
    data-lvl (0-3 colour ramp), a stagger index and its count numeral at build
    time, so the choropleth is coloured on first paint without JavaScript."""
    svg = (src / "assets" / "maps" / f"{ed}.svg").read_text(encoding="utf-8").strip()
    if counts is None:
        return svg
    mx = max(counts.values(), default=0)
    idx = {"i": 0}

    def region(m: re.Match[str]) -> str:
        attrs, body = m.group(1), m.group(2)
        name_m = re.search(r'data-region="([^"]*)"', attrs)
        n = counts.get(html.unescape(name_m.group(1)), 0) if name_m else 0
        lvl = "0" if n == 0 else "3" if n >= mx * 0.6 else "2" if n >= mx * 0.25 else "1"
        cx = re.search(r'data-cx="([^"]*)"', attrs)
        cy = re.search(r'data-cy="([^"]*)"', attrs)
        zero_cls = "" if n else ' class="is-zero"'
        label = f'<text x="{cx.group(1)}" y="{cy.group(1)}" dy="4"{zero_cls}>{n}</text>' if cx and cy else ""
        i = idx["i"]
        idx["i"] += 1
        if not n:  # zero-count regions take the muted is-zero fill instead of reading as holes (visual 12)
            attrs = attrs.replace('class="gmap__r"', 'class="gmap__r is-zero"', 1)
        return f'<g{attrs} data-n="{n}" data-lvl="{lvl}" style="--i:{i}">{body}{label}</g>'
    return re.sub(r'<g(\s+class="gmap__r"[^>]*)>(.*?)</g>', region, svg, flags=re.S)


ZERO_CLS = ' class="is-zero"'


def map_list(data: dict[str, Any], jobs_href: str) -> str:
    """Every mapped region, busiest first; regions with no live role are kept
    at 0 (class is-zero) so Northern Ireland and East Midlands stay offered."""
    rows = [r for r in data["regions"] if r["on_map"]]
    return "".join(f'<a href="{jobs_href}?loc={qs(r["name"])}"{"" if r["n"] else ZERO_CLS}><span>{esc(r["name"])}</span><b class="num">{r["n"]}</b></a>' for r in rows)


def off_map_note(data: dict[str, Any], jobs_href: str) -> str:
    """States the roles the map cannot place (e.g. 'Elsewhere (UK & abroad)'),
    each linked to the jobs list filtered to that bucket. Empty when none."""
    rows = [r for r in data["regions"] if not r["on_map"] and r["n"] > 0]
    if not rows:
        return ""
    total = sum(r["n"] for r in rows)
    links = ", ".join(f'<a href="{jobs_href}?loc={qs(r["name"])}">{esc(r["name"])} ({r["n"]})</a>' for r in rows)
    return f' {total} {"role is" if total == 1 else "roles are"} not on the map: {links}.'


def select(field_id: str, label: str, values: list[str], any_label: str) -> str:
    return select_pairs(field_id, label, [(v, v) for v in values], any_label)


def select_pairs(field_id: str, label: str, pairs: list[tuple[str, str]], any_label: str) -> str:
    opts = "".join(f'<option value="{esc(v)}">{esc(t)}</option>' for v, t in pairs)
    return f'<div class="field"><label for="{field_id}">{label}</label><select class="in" id="{field_id}" name="{field_id[2:]}"><option value="">{any_label}</option>{opts}</select></div>'


def jobs_jsonld(data: dict[str, Any], site_base: str) -> str:
    items = [{"@type": "ListItem", "position": i + 1, "url": f"{site_base}{data['ed']}/jobs/{j['href']}", "name": j["title"]}
             for i, j in enumerate(data["jobs"][:50])]
    return f'<script type="application/ld+json">{json_ld({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": items})}</script>'


def job_jsonld_payload(j: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """schema.org JobPosting (G1). baseSalary only with numeric values AND the
    job's own currency code; validThrough from the closing date; TELECOMMUTE
    for remote roles; applicantLocationRequirements for cross-border roles."""
    lc = j.get("loc_class") or ""
    country = {"ie": "IE", "uk": "GB", "ni": "GB"}.get(lc, "IE" if data["ed"] == "ie" else "GB")
    payload: dict[str, Any] = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": j["title"], "description": j["text"][:1000] or j["summary"],
        "hiringOrganization": {"@type": "Organization", "name": j["employer"]},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": j["location"], "addressCountry": country}},
        "url": j["url"], "directApply": False,
    }
    if j["posted"]:
        payload["datePosted"] = j["posted"]
    if j["closing"]:
        payload["validThrough"] = j["closing"] + "T23:59:59"
    if j["type"]:
        payload["employmentType"] = j["type"].upper().replace(" ", "_")
    if lc == "remote" or j.get("workplace") == "remote":
        payload["jobLocationType"] = "TELECOMMUTE"
    if lc == "cross":
        payload["applicantLocationRequirements"] = [{"@type": "Country", "name": "Ireland"}, {"@type": "Country", "name": "United Kingdom"}]
    elif lc == "remote" or (j.get("workplace") == "remote" and lc in ("ie", "uk", "ni")):
        payload["applicantLocationRequirements"] = {"@type": "Country", "name": {"IE": "Ireland", "GB": "United Kingdom"}[country]}
    if j.get("cur") in ("EUR", "GBP", "USD") and (isinstance(j["sal_min"], (int, float)) or isinstance(j["sal_max"], (int, float))):
        value: dict[str, Any] = {"@type": "QuantitativeValue", "unitText": (j["period"] or "year").upper()}
        if j["sal_min"] is not None:
            value["minValue"] = j["sal_min"]
        if j["sal_max"] is not None:
            value["maxValue"] = j["sal_max"]
        payload["baseSalary"] = {"@type": "MonetaryAmount", "currency": j["cur"], "value": value}
    return payload


def job_jsonld(j: dict[str, Any], data: dict[str, Any]) -> str:
    return f'<script type="application/ld+json">{json_ld(job_jsonld_payload(j, data))}</script>'


def similar_jobs(j: dict[str, Any], jobs: list[dict[str, Any]], ed_cur: str = "", limit: int = 4) -> list[dict[str, Any]]:
    """Up to `limit` other live roles: same primary sector first, then a shared
    region, then closeness of annualised salary (D2). Deterministic."""
    mine = annual_mid(j, ed_cur)
    my_regions = set(j.get("regions") or [])
    my_sectors = set(j.get("sectors") or [])
    my_key = (str(j.get("title") or "").strip().lower(), str(j.get("employer") or "").strip().lower())
    seen_keys: set[tuple[str, str]] = {my_key}
    scored: list[tuple[float, int, str, str, dict[str, Any]]] = []
    for o in sorted(jobs, key=lambda o: (not o.get("posted"), "".join(chr(255 - ord(c)) for c in (o.get("posted") or "")), o.get("title") or "")):
        if o["id"] == j["id"]:
            continue
        key = (str(o.get("title") or "").strip().lower(), str(o.get("employer") or "").strip().lower())
        if key in seen_keys or not (my_sectors & set(o.get("sectors") or [])):
            continue  # one card per (title, employer); a similar role shares at least one sector
        seen_keys.add(key)
        score = 0.0
        if o["sectors"][0] == j["sectors"][0]:
            score += 4
        else:
            score += 1.5
        if my_regions & set(o.get("regions") or []):
            score += 2
        if o.get("loc_class") == j.get("loc_class"):
            score += 0.5
        theirs = annual_mid(o, ed_cur)
        if mine and theirs:
            score += max(0.0, 1 - abs(mine[2] - theirs[2]) / max(mine[2], theirs[2], 1))
        posted = o.get("posted") or ""
        scored.append((-score, 0 if posted else 1, "".join(chr(255 - ord(c)) for c in posted), o["title"], o))
    scored.sort(key=lambda t: t[:4])  # best score, then newest first, roles without a posted date last
    return [o for *_, o in scored[:limit]]


def slim(j: dict[str, Any], with_text: bool) -> dict[str, Any]:
    keys = ["id", "title", "employer", "location", "regions", "type", "sal_min", "sal_max", "cur", "period", "sal_text", "sectors", "color", "posted", "closing", "summary", "logo", "lw", "lh", "href",
            "loc_class", "workplace", "level", "contract", "agency"]
    out = {k: j[k] for k in keys}
    if j.get("currency_source") == UNVERIFIED_SOURCE:
        out["unverified_cur"] = True  # jobs.js prints the "as listed on greenjobs.ie" note (R011)
    if with_text:
        out["text"] = j["text"]
    return out


def contract_facet(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The one Contract facet (visual 31): [{k, name, n}] in CONTRACT_LABEL
    order, only the values at least one live role carries."""
    counts = Counter(c for j in jobs for c in j.get("contract") or [])
    return [{"k": k, "name": lb, "n": counts[k]} for k, lb in CONTRACT_LABEL.items() if counts.get(k)]


def dataset_script(data: dict[str, Any], jobs_href: str, with_text: bool) -> str:
    payload = {
        "today": data["today"],  # the build date: lib.js uses it for "ago" and closing-date windows, never the browser clock
        "jobs": [slim(j, with_text) for j in data["jobs"]],
        "sectors": [s for s in data["sectors"] if s["n"] > 0],
        "regions": [r for r in data["regions"] if r["on_map"]],
        "types": data["types"], "contracts": contract_facet(data["jobs"]), "currency": EDITIONS[data["ed"]]["currency"], "regionUnit": EDITIONS[data["ed"]]["unit"].title(), "jobsHref": jobs_href,
        "home": EDITION_HOME[data["ed"]], "edition": data["ed"],
    }
    return f'<script type="application/json" id="gj-data">{json_embed(payload)}</script>'


# ------------------------------------------------------------------ film hero data (build-time geometry)

_PATH_CMD = re.compile(r"([MLZ])\s*([^MLZ]*)", re.I)
_NUM = re.compile(r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?")


def svg_polygons(d: str) -> list[list[tuple[float, float]]]:
    """Absolute M/L/Z path data (what make_maps.py writes) -> list of rings."""
    rings: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for cmd, args in _PATH_CMD.findall(d):
        nums = [float(x) for x in _NUM.findall(args)]
        if cmd.upper() == "M":
            if len(cur) > 2:
                rings.append(cur)
            cur = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
        elif cmd.upper() == "L":
            cur += [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
        else:
            if len(cur) > 2:
                rings.append(cur)
            cur = []
    if len(cur) > 2:
        rings.append(cur)
    return rings


def ring_area(ring: list[tuple[float, float]]) -> float:
    a = 0.0
    for i, (x1, y1) in enumerate(ring):
        x2, y2 = ring[(i + 1) % len(ring)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def point_in_rings(x: float, y: float, rings: list[list[tuple[float, float]]]) -> bool:
    """Even-odd rule across every ring (holes and islands both handled)."""
    inside = False
    for ring in rings:
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < xi:
                    inside = not inside
    return inside


def sample_map_points(svg_text: str, n: int = 2500, seed: int = 7) -> dict[str, Any]:
    """Deterministic rejection sampling inside every region path, points
    allotted by area (at least 6 per region so small counties still show).
    Returns viewBox size, an ordered region list and a flat [x, y, region
    index, ...] array of integer coordinates the film canvas can use as-is."""
    import random
    vb = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"', svg_text)
    w, h = (float(vb.group(1)), float(vb.group(2))) if vb else (600.0, 800.0)
    regions: list[dict[str, Any]] = []
    for m in re.finditer(r'<g\s+class="gmap__r"([^>]*)>(.*?)</g>', svg_text, re.S):
        attrs, body = m.group(1), m.group(2)
        name = re.search(r'data-region="([^"]*)"', attrs)
        cx = re.search(r'data-cx="([^"]*)"', attrs)
        cy = re.search(r'data-cy="([^"]*)"', attrs)
        rings: list[list[tuple[float, float]]] = []
        for pm in re.finditer(r'<path[^>]*\sd="([^"]*)"', body):
            rings += svg_polygons(pm.group(1))
        if not rings or not name:
            continue
        xs = [x for r in rings for x, _ in r]
        ys = [y for r in rings for _, y in r]
        regions.append({"name": html.unescape(name.group(1)), "cx": float(cx.group(1)) if cx else 0.0, "cy": float(cy.group(1)) if cy else 0.0,
                        "rings": rings, "area": sum(ring_area(r) for r in rings), "bbox": (min(xs), min(ys), max(xs), max(ys))})
    total_area = sum(r["area"] for r in regions) or 1.0
    rng = random.Random(seed)
    pts: list[int] = []
    for ri, r in enumerate(regions):
        want = max(6, round(n * r["area"] / total_area))
        x0, y0, x1, y1 = r["bbox"]
        got = tries = 0
        while got < want and tries < want * 60:
            tries += 1
            x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
            if point_in_rings(x, y, r["rings"]):
                pts += [round(x), round(y), ri]
                got += 1
    return {"vb": [round(w), round(h)], "regions": [{"n": r["name"], "x": round(r["cx"]), "y": round(r["cy"])} for r in regions], "pts": pts}


def annual_mid(j: dict[str, Any], ed_cur: str = "") -> tuple[float, float, float] | None:
    """(lo, hi, mid) per year, or None; mirrors lib.js annual(). With ed_cur,
    the figures are converted into the edition currency at the fixed rate so
    that filters and medians compare like with like (the label never is)."""
    m = ANNUAL_MULT.get(j.get("period") or "year")
    if not m or (j.get("sal_min") is None and j.get("sal_max") is None):
        return None
    if is_unverified(j):
        return None  # round 4 (Dario): a UK-located role whose euro figure is unconfirmed never enters a median, band or guide
    if j.get("cur") not in COMPARABLE_CURRENCIES:
        return None  # USD or an unknown currency has no fixed rate: it never enters a median, band or salary filter
    lo = (j["sal_min"] if j["sal_min"] is not None else j["sal_max"]) * m
    hi = j["sal_max"] * m if j["sal_max"] is not None else lo
    if ed_cur and j.get("cur") and j["cur"] != ed_cur:
        lo, hi = fx_convert(lo, j["cur"], ed_cur), fx_convert(hi, j["cur"], ed_cur)
    if lo < 8000 or hi > 400000:
        return None
    return (lo, hi, (lo + hi) / 2)


def is_unverified(j: dict[str, Any]) -> bool:
    """True for the UK-located IE roles whose scraped euro figure has no
    sterling twin (normalised jobs carry currency_source, jobs.json the
    unverified_cur flag)."""
    return bool(j.get("unverified_cur")) or j.get("currency_source") == UNVERIFIED_SOURCE


def money_k(n: float, sym: str) -> str:
    """Mirror of lib.js money(): '€62.5k', '£30k', '€900'. Half-up rounding."""
    if n >= 1000:
        return f"{sym}{int(n // 1000)}k" if n % 1000 == 0 else f"{sym}{rnd(n / 100) / 10:g}k"
    return f"{sym}{n:g}"


SALARY_EDGES = [20000, 30000, 40000, 50000, 60000, 75000, 100000]


def salary_bands(jobs: list[dict[str, Any]], sym: str, ed_cur: str = "") -> list[dict[str, Any]]:
    """Histogram of annualised midpoints (edition currency) on the insights page's edges."""
    bands = [{"l": (money_k(e, "") + "–" + money_k(SALARY_EDGES[i + 1], "")) if i + 1 < len(SALARY_EDGES) else money_k(e, "") + "+", "lo": e, "n": 0} for i, e in enumerate(SALARY_EDGES)]
    for j in jobs:
        a = annual_mid(j, ed_cur)
        if not a:
            continue
        for b in reversed(bands):
            if a[2] >= b["lo"]:
                b["n"] += 1
                break
    return [{"l": b["l"], "n": b["n"]} for b in bands]


def film_payload(data: dict[str, Any], src: Path) -> dict[str, Any]:
    ed = EDITIONS[data["ed"]]
    geo = sample_map_points((src / "assets" / "maps" / f"{data['ed']}.svg").read_text(encoding="utf-8"))
    counts = {r["name"]: r["n"] for r in data["regions"]}
    for r in geo["regions"]:
        r["c"] = counts.get(r["n"], 0)
    jobs = data["jobs"]
    n_sal = sum(1 for j in jobs if annual_mid(j, ed["currency"]))
    return {
        "vb": geo["vb"], "regions": geo["regions"], "pts": geo["pts"],
        "bands": salary_bands(jobs, ed["sym"], ed["currency"]), "n_sal": n_sal, "n_jobs": len(jobs), "sym": ed["sym"],
        "sectors": [{"n": s["name"], "c": s["n"], "col": s["color"]} for s in data["sectors"] if s["n"] > 0][:8],
    }


# ------------------------------------------------------------------ "Where this role sits" (job page salary strip)

def salary_strip(j: dict[str, Any], jobs: list[dict[str, Any]], sym: str, unit: str, on_map: set[str] | None = None, ed_cur: str = "") -> str:
    """This role's range against the board's disclosed distribution, overall
    and within its first sector: an SVG with keyboard-focusable marks and a
    table alternative. Without a disclosed salary: one plain line. Positions
    are annualised in the edition currency; labels stay in the advertised one."""
    sector = j["sectors"][0]
    overall = [(o, annual_mid(o, ed_cur)) for o in jobs if annual_mid(o, ed_cur)]
    in_sector = [(o, a) for o, a in overall if sector in o["sectors"]]
    mine = annual_mid(j, ed_cur)
    same_county = [o for o in jobs if o["id"] != j["id"] and set(o["regions"]) & set(j["regions"]) and set(o["sectors"]) & set(j["sectors"])]
    county = j["regions"][0] if j["regions"] else ""
    where = f"within {esc(county)}" if (on_map is None or county in on_map) else ("outside Ireland" if unit == "county" else "outside the UK")  # visitor wording for the off-map bucket
    sim = (f'<p class="sits__sim"><b class="num">{len(same_county)}</b> similar {"role" if len(same_county) == 1 else "roles"} {where}'
           + (f' — <a href="../index.html?loc={qs(county)}&amp;sector={qs(sector)}">see them</a>' if same_county else "") + "</p>")
    if not mine:
        if in_sector:
            lo = min(a[0] for _, a in in_sector)
            hi = max(a[1] for _, a in in_sector)
            line = f"This employer hasn't published a salary. {esc(sector)} roles that do: {money_k(lo, sym)}–{money_k(hi, sym)} ({len(in_sector)})."
        else:
            line = f"This employer hasn't published a salary, and no other live {esc(sector)} role does either."
        return f'<section class="sits sits--none" aria-labelledby="h-sits"><div class="wrap"><h2 id="h-sits">Where this role sits</h2><p class="sits__line">{line}</p>{sim}</div></section>'
    vals = [a[2] for _, a in overall] + [mine[0], mine[1]]
    lo_ax, hi_ax = min(vals), max(vals)
    lo_ax = (lo_ax // 10000) * 10000
    hi_ax = ((hi_ax // 10000) + 1) * 10000
    W, LH = 720, 44
    PL, PR = 8, 8

    def X(v: float) -> float:
        return PL + (W - PL - PR) * (v - lo_ax) / max(1, hi_ax - lo_ax)
    lanes = [("Overall", overall), (sector, in_sector)]
    rows_svg = []
    table_rows = []
    y = 26
    for label, group in lanes:
        med = sorted(a[2] for _, a in group)
        median = med[len(med) // 2] if len(med) % 2 else (med[len(med) // 2 - 1] + med[len(med) // 2]) / 2 if med else None
        marks = "".join(
            f'<g class="sits__mark" tabindex="0" role="listitem" aria-label="{esc(o["title"])}, {esc(o["employer"])}: {esc(salary_label(o, ed_cur))}"><circle cx="{X(a[2]):.1f}" cy="{y + 14}" r="5"/></g>'
            for o, a in sorted(group, key=lambda t: t[1][2]))
        medl = f'<line class="sits__med" x1="{X(median):.1f}" x2="{X(median):.1f}" y1="{y + 2}" y2="{y + 26}"/>' if median is not None else ""
        rows_svg.append(f'<text class="sits__lbl" x="{PL}" y="{y - 6}">{esc(label)} · {len(group)} disclosed' + (f" · median {money_k(median, sym)}" if median is not None else "") + f'</text><g role="list">{marks}</g>{medl}')
        table_rows.append(f'<tr><th scope="row">{esc(label)}</th><td class="num">{len(group)}</td><td class="num">{money_k(median, sym) if median is not None else "—"}</td></tr>')
        y += LH + 16
    mine_y = y
    bar = (f'<rect class="sits__me" x="{X(mine[0]):.1f}" y="{mine_y + 6}" width="{max(6, X(mine[1]) - X(mine[0])):.1f}" height="16" rx="8"/>'
           f'<text class="sits__lbl sits__lbl--me" x="{PL}" y="{mine_y - 6}">This role · {esc(salary_label(j, ed_cur))}</text>')
    ticks = "".join(f'<text class="sits__tick" x="{X(v):.1f}" y="{mine_y + 44}" text-anchor="{"start" if v == lo_ax else "end" if v == hi_ax else "middle"}">{money_k(v, sym)}</text>'
                    for v in sorted({lo_ax, hi_ax, (lo_ax + hi_ax) / 2}))
    H = mine_y + 52
    svg = (f'<svg class="sits__svg" viewBox="0 0 {W} {H}" role="img" aria-label="Salary of this role against {len(overall)} disclosed salaries on the board">'
           f'{"".join(rows_svg)}{bar}<line class="sits__axis" x1="{PL}" x2="{W - PR}" y1="{mine_y + 30}" y2="{mine_y + 30}"/>{ticks}</svg>')
    table = (f'<details class="sits__table"><summary>As a table</summary><table><thead><tr><th>Group</th><th class="num">Disclosed</th><th class="num">Median</th></tr></thead><tbody>{"".join(table_rows)}'
             f'<tr><th scope="row">This role</th><td class="num">1</td><td class="num">{money_k(mine[2], sym)} (midpoint)</td></tr></tbody></table></details>')
    return (f'<section class="sits" aria-labelledby="h-sits"><div class="wrap"><div class="sec-head"><div><h2 id="h-sits">Where this role sits</h2>'
            f'<p>Its published range against every disclosed salary on the board, overall and in {esc(sector)}. Midpoints per role, annualised; tab through the dots.</p></div></div>'
            f'{svg}{table}{sim}</div></section>')


def reach_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Per-sector live count and median disclosed salary for the ad builder."""
    ed = EDITIONS[data["ed"]]
    out: dict[str, Any] = {}
    for s in data["sectors"]:
        if not s["n"]:
            continue
        mids = sorted(a[2] for j in data["jobs"] if s["name"] in j["sectors"] for a in [annual_mid(j, ed["currency"])] if a)
        med = (mids[len(mids) // 2] if len(mids) % 2 else (mids[len(mids) // 2 - 1] + mids[len(mids) // 2]) / 2) if mids else None
        out[s["name"]] = {"n": s["n"], "disc": len(mids), "med": money_k(med, ed["sym"]) if med is not None else "", "col": s["color"]}
    return out


# ------------------------------------------------------------------ pages
def job_is_agency(j: dict[str, Any]) -> bool:
    """j["agency"] as normalise() stored it (one rule for the whole site);
    derived from the employer name when the record has no such field."""
    return bool(j["agency"]) if "agency" in j else is_agency(j.get("employer") or "")


def job_is_remote_or_hybrid(j: dict[str, Any]) -> bool:
    """j["workplace"] in (remote, hybrid) as normalise() stored it; derived
    from the record's text otherwise."""
    wp = j.get("workplace") or workplace_of({**j, "description_html": j.get("description_html") or j.get("text") or "", "summary": j.get("summary") or j.get("location") or ""})
    return wp in ("remote", "hybrid")


def _median_int(vals: list[float]) -> float | None:
    if not vals:
        return None
    vals = sorted(vals)
    h = len(vals) // 2
    return vals[h] if len(vals) % 2 else (vals[h - 1] + vals[h]) / 2


def dashboard_kpis(data: dict[str, Any]) -> dict[str, Any]:
    """Live-now KPIs for the client dashboard, computed from the normalised dataset
    relative to the snapshot date (so the build is deterministic). Agency and
    remote/hybrid shares come from the stored j["agency"] / j["workplace"]
    fields (one rule, shared with the board's facets); the median uses
    annual_mid() in the edition currency so euro and sterling roles compare."""
    jobs = data["jobs"]
    ed_cur = EDITIONS.get(data.get("ed") or "", {}).get("currency", "")
    n = len(jobs)
    asof = date.fromisoformat(data.get("today") or data["fetched"])

    def d(iso: str) -> date | None:
        try:
            return date.fromisoformat(iso) if iso else None
        except ValueError:
            return None

    new7 = sum(1 for j in jobs if new_this_week(j, asof))  # 0..6 days, shared rule
    closing7 = sum(1 for j in jobs if closing_within(j, asof, 7))  # 0..7 days, shared rule
    sal_n = sum(1 for j in jobs if j["sal_min"] is not None or j["sal_max"] is not None)
    med = _median_int([a[2] for j in jobs if (a := annual_mid(j, ed_cur))])
    emp: dict[str, int] = {}
    for j in jobs:
        emp[j["employer"]] = emp.get(j["employer"], 0) + 1
    top = max(emp.items(), key=lambda kv: (kv[1], kv[0])) if emp else ("", 0)
    agency = sum(1 for j in jobs if (j["agency"] if "agency" in j else is_agency(j.get("employer") or "")))
    days_close = _median_int([(c - p).days for j in jobs if (p := d(j["posted"])) and (c := d(j["closing"])) and c >= p])
    remote = sum(1 for j in jobs if (j["workplace"] if "workplace" in j else workplace_of(j)) in ("remote", "hybrid"))
    quality = [0, 0, 0, 0, 0]
    for j in jobs:
        score = int(j["sal_min"] is not None or j["sal_max"] is not None) + int(bool(j["closing"])) + int(bool(j["logo"])) + int(len(j["text"]) >= 400)
        quality[score] += 1
    return {
        "asof": data["fetched"], "live": n, "new7": new7, "weeks": sparkline_weeks(jobs, asof, 4), "closing7": closing7,
        "sal_n": sal_n, "sal_pct": round(100 * sal_n / max(1, n)), "sal_median": round(med) if med is not None else None,
        "sectors": [{"l": s["name"], "v": s["n"]} for s in data["sectors"] if s["n"]],
        "regions": [{"l": r["name"], "v": r["n"]} for r in data["regions"] if r["on_map"]][:12],
        "top_employer": top[0], "top_share": round(100 * top[1] / max(1, n)), "employers": len(emp),
        "agency_pct": round(100 * agency / max(1, n)), "days_to_close": round(days_close) if days_close is not None else None,
        "remote_pct": round(100 * remote / max(1, n)), "quality": quality,
    }


# Visitor-voice dashboard copy (round 4). The template owner takes these as
# {{dash_lede}} and {{dash_events}}; DASHBOARD_REWRITES maps the retired
# developer phrasing onto them so the built page is right in the meantime.
DASHBOARD_COPY = {
    "dash_lede": "What the board is worth this week, and how each number is measured. Live figures from this week's listings. Reported once analytics is connected.",
    "dash_events": "Nothing below is a live number. Each tile names the event the site records and the target it is measured against. Events are sent once an analytics provider is connected and the visitor allows analytics; values fill in from launch day and a dash means \"collected from launch\".",
}
DASHBOARD_REWRITES = [
    ("The top half is computed from the live listings at build time; the bottom half lists the measures the analytics provider will report once it is switched on through the cookie consent's Analytics toggle.",
     "Live figures from this week's listings. Reported once analytics is connected."),
    ("computed from the live listings at build time", "Live figures from this week's listings."),
    ("the analytics provider will report once it is switched on", "Reported once analytics is connected."),
    ("Events are only sent once the visitor switches Analytics on in the cookie settings and a provider is connected;",
     "Events are sent once an analytics provider is connected and the visitor allows analytics;"),
    ("sent once the visitor switches Analytics on", "sent once an analytics provider is connected and the visitor allows analytics"),
    (" (target we propose; no ", " (proposed target; no "),
    (" (target we propose)", " (proposed target)"),
    (", target we propose)", ", proposed target)"),
]


def render_dashboard(data: dict[str, Any], src: Path, out: Path, tpl: dict[str, str], brief: dict[str, Any], site_base: str) -> None:
    """Client KPI dashboard at /{ed}/dashboard/: live-now tiles from the dataset plus
    the event spec for launch. Not in the primary nav; linked from for-keith."""
    ed = EDITIONS[data["ed"]]
    k = dashboard_kpis(data)
    sym = ed["sym"]
    flag = k["top_share"] > 50
    med = f'{sym}{k["sal_median"]:,}' if k["sal_median"] is not None else "n/a"
    real_case = {j["employer"].lower(): j["employer"] for j in data["jobs"]}
    agency_names = ", ".join(real_case.get(n) or AGENCY_DISPLAY.get(n) or n.title() for n in sorted(AGENCY_NAMES))
    agency_words = ", ".join(w for w in AGENCY_WORDS if " " not in w)
    tiles = [
        ("Live roles", str(k["live"]), "Listings with a page in this edition on the snapshot date.", ""),
        ("New this week", str(k["new7"]), "Roles posted within the 7 days up to the snapshot. Line: roles posted per week over the last 4 weeks.", sparkline_svg(k["weeks"], 120, 34)),
        ("Closing within 7 days", str(k["closing7"]), "Roles whose closing date falls within the 7 days after the snapshot.", ""),
        ("Salary disclosure", f'{k["sal_pct"]}%', f'Roles publishing a figure ({k["sal_n"]} of {k["live"]}). Median of disclosed annualised midpoints, converted into {sym} at the fixed rate where a role is advertised in the other currency: {med}.', ""),
        ("Top employer share", f'{k["top_share"]}%', f'{esc(k["top_employer"])} holds this share of live roles across {k["employers"]} employers.' + (" Most roles come from one employer." if flag else ""), ""),
        ("Agency share", f'{k["agency_pct"]}%', f"Roles posted by recruitment agencies rather than the employer directly. Flagged when the employer is a known agency ({esc(agency_names)}) or its name contains a recruitment word ({esc(agency_words)}); the same flag drives the board's \"Advertised by\" filter.", ""),
        ("Advertised window (median days)", str(k["days_to_close"]) if k["days_to_close"] is not None else "n/a", "Median of closing date minus posted date across roles that publish both: how long a listing is advertised, not how long it takes to fill.", ""),
        ("Remote or hybrid option", f'{k["remote_pct"]}%', "Roles whose workplace field is remote or hybrid; the field is set from the full listing text by the same rule as the board's Workplace filter.", ""),
    ]
    tile_html = "".join(
        f'<div class="kpi{" kpi--flag" if flag and lbl == "Top employer share" else ""}"><span class="kpi__l">{lbl}</span><b class="kpi__v num">{val}</b>{spark}<p class="kpi__d">{how}</p></div>'
        for lbl, val, how, spark in tiles)
    root = "../../"
    ctx = shell_ctx(data, 2, "dashboard", f"KPI dashboard — what GreenJobs {ed['short']} measures | GreenJobs {ed['short']}",
                    "Live figures from this week's listings, and the measures reported once analytics is connected.", brief=brief, site_base=site_base, same_path="dashboard/index.html")
    ctx["scripts"] = "".join(f'<script src="{root}js/{s}.js" defer></script>' for s in ("charts", "dashboard"))
    content = render(tpl["dashboard"], {**ctx, "tiles": tile_html, "unit": ed["unit"], "units": plural(ed["unit"]), "sym": sym,
                                        "kpis": f'<script type="application/json" id="gj-dash">{json_embed(k)}</script>',
                                        "keith": f"{root}{data['ed']}/for-keith/index.html", **DASHBOARD_COPY})
    # Round 4 (trace 3, P2): the page is a public URL, so the developer voice
    # goes. The template may still carry the old sentences until it takes the
    # {{dash_lede}} / {{dash_events}} placeholders; the bridge below rewrites them either way.
    for old, new in DASHBOARD_REWRITES:
        content = content.replace(old, new)
    ctx["content"] = content
    (out / data["ed"] / "dashboard").mkdir(parents=True, exist_ok=True)
    (out / data["ed"] / "dashboard" / "index.html").write_text(render(tpl["_shell"], ctx), encoding="utf-8")


def _host(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]


HERO_DIR = "assets/hero"


def hero_files(src: Path, ed: str) -> dict[str, str]:
    """Drop-in hero footage for an edition: <ed>.mp4 (landscape), optional
    <ed>-m.mp4 (portrait, under 800px) and <ed>-poster.webp|jpg. Files are
    optional; the canvas landscape is the hero when they are absent."""
    d = src / HERO_DIR
    out: dict[str, str] = {}
    if (d / f"{ed}.mp4").exists():
        out["video"] = f"{ed}.mp4"
    if (d / f"{ed}-m.mp4").exists():
        out["mobile"] = f"{ed}-m.mp4"
    for ext in ("webp", "jpg"):
        if (d / f"{ed}-poster.{ext}").exists():
            out["poster"] = f"{ed}-poster.{ext}"
            break
    return out


def hero_video(src: Path, ed: str, root: str) -> str:
    """The <video> for the hero scene when footage has been dropped in
    (muted, looped, inline, poster, no preload beyond metadata). landscape.js
    keeps the canvas playing until the first frame is ready, pauses it
    off-screen and shows the poster only on Save-Data / reduced motion."""
    f = hero_files(src, ed)
    if not f.get("video"):
        return ""
    poster = f' poster="{root}{HERO_DIR}/{f["poster"]}"' if f.get("poster") else ""
    sources = ""
    if f.get("mobile"):
        sources += f'<source src="{root}{HERO_DIR}/{f["mobile"]}" type="video/mp4" media="(max-width: 799px)">'
    sources += f'<source src="{root}{HERO_DIR}/{f["video"]}" type="video/mp4">'
    return f'<video class="hero__video" data-hero-video muted loop playsinline autoplay preload="metadata"{poster} aria-hidden="true" tabindex="-1">{sources}</video>'


def hero_bcorp(brief: dict[str, Any], root: str) -> str:
    """The B Corp mark for the home hero (owner confirmed the wording
    "Certified B Corporation" on 2026-09-24; no further claim is made)."""
    if not (brief and brief.get("b_corp") and brief.get("bcorp_size")):
        return ""
    w, h = brief["bcorp_size"]
    return f'<img class="hero__bcorp" src="{root}assets/logos/b-corp-logo.svg" alt="{BCORP_ALT}" title="{BCORP_NOTE}" width="{w}" height="{h}">'


def shell_ctx(data: dict[str, Any], depth: int, page: str, title: str, desc: str, *, dark_header: bool = False,
              body_attrs: str = "", brief: dict[str, Any] | None = None, same_path: str = "", site_base: str = "", switch_path: str = "") -> dict[str, str]:
    ed = EDITIONS[data["ed"]]
    root = "../" * depth
    home = f"{root}{data['ed']}/"
    other = ed["other"]
    other_path = switch_path or same_path or "index.html"  # where the edition switch lands in the other edition
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{home}{href}"{cur if page == href.split("/")[0] else ""}>{label}</a>' for href, label in NAV)
    menu_links = nav
    edsw = (f'<a href="{root}ie/{other_path if other == "ie" else same_path or "index.html"}" data-edswitch="ie" aria-current="{"true" if data["ed"] == "ie" else "false"}" hreflang="en-IE">IE</a>'
            f'<a href="{root}uk/{other_path if other == "uk" else same_path or "index.html"}" data-edswitch="uk" aria-current="{"true" if data["ed"] == "uk" else "false"}" hreflang="en-GB">UK</a>')
    net = "".join(f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}</a></li>' for s in data["network_sites"] if str(s.get("url", "")).startswith("http"))
    contact = data["contact"] or {}
    # Keith F3: the UK footer lists the UK number first, IE the Irish one; the
    # numbers themselves come from brief.md / <ed>.json contact (never typed here).
    raw_phones = [(str(lbl), str(num)) for lbl, num in (contact.get("phones") or []) if num]
    uk_nums = [n for lbl, n in raw_phones if "outside" in lbl.lower() or n.strip().startswith("+44")]
    ie_nums = [n for lbl, n in raw_phones if n not in uk_nums]
    ordered = [("Calling from the UK", n) for n in uk_nums[:1]] + [("Calling from Ireland", n) for n in ie_nums[:1]]
    if data["ed"] == "ie":
        ordered.reverse()
    phones = "".join(f'<li>{esc(lbl)}: <a href="tel:{esc(re.sub(r"[^+0-9]", "", num))}">{esc(num)}</a></li>' for lbl, num in ordered)
    emails = "".join(f'<li><a href="mailto:{esc(e)}">{esc(e)}</a></li>' for e in dict.fromkeys(contact.get("emails") or []))
    bcorp = onepct = hdr_bcorp = ""
    if brief and brief.get("b_corp") and brief.get("bcorp_size"):
        w, h = brief["bcorp_size"]
        bcorp = f'<img class="bcorp" src="{root}assets/logos/b-corp-logo.svg" alt="{BCORP_ALT}" title="{BCORP_NOTE}" width="{w}" height="{h}" loading="lazy">'
        hdr_bcorp = f'<span class="hdr__bcorp" title="{BCORP_NOTE}"><img src="{root}assets/logos/b-corp-logo.svg" alt="{BCORP_ALT}" width="{w}" height="{h}"></span>'
    if brief and brief.get("onepct_size"):
        w, h = brief["onepct_size"]
        onepct = f'<img src="{root}assets/logos/1fortheplanet.svg" alt="1% for the Planet member" width="{w}" height="{h}" loading="lazy" style="height:44px;width:auto;margin-top:12px;filter:brightness(1.4)">'
    social = "".join(
        f'<a href="{esc(u)}" rel="noopener" aria-label="{esc(_host(u))}"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></a>'
        for u in (data.get("social") or [])[:4])
    head_extra = ""
    if site_base:
        mine = f"{site_base}{data['ed']}/{same_path or 'index.html'}"
        head_extra = f'<link rel="canonical" href="{esc(mine)}">'
        # An hreflang pair only when the same path is built in the other
        # edition (data["paired_paths"], computed by build()); absolute URLs,
        # en-IE + en-GB + one x-default (the IE page).
        pairs = data.get("paired_paths")
        if pairs is None or isinstance(pairs, (set, frozenset)):
            pairs = {p: p for p in (PAIRED_PATHS if pairs is None else pairs)}
        twin = pairs.get(same_path or "index.html")
        if twin:
            mine_path, other_path_ = same_path or "index.html", twin
            ie_url = f"{site_base}ie/{mine_path if data['ed'] == 'ie' else other_path_}"
            uk_url = f"{site_base}uk/{mine_path if data['ed'] == 'uk' else other_path_}"
            head_extra += (f'<link rel="alternate" hreflang="en-IE" href="{esc(ie_url)}"><link rel="alternate" hreflang="en-GB" href="{esc(uk_url)}">'
                           f'<link rel="alternate" hreflang="x-default" href="{esc(ie_url)}">')
    return {
        "head_extra": head_extra,
        "lang": ed["lang"], "title": esc(title), "desc": esc(desc), "root": root, "home": home, "ed": data["ed"], "ED": ed["short"],
        "domain": esc(data["site"]), "nav": nav, "menu_links": menu_links, "edsw": edsw, "hdr_cls": " hdr--dark" if dark_header else "",
        "body_attrs": body_attrs, "net_sites": net, "phones": phones, "emails": emails, "bcorp": bcorp, "hdr_bcorp": hdr_bcorp, "social": social,
        "year": str(data.get("today", data["fetched"])[:4]), "n_jobs": str(len(data["jobs"])), "fetched": esc(data["fetched"]), "fetched_long": esc(date_long(data["fetched"])),
        "social_wrap": f'<div class="ftr__social">{social}</div>' if social else "",
        "canonical": esc(f"{site_base}{data['ed']}/{same_path or 'index.html'}") if site_base else "",
        "nav_list": "".join(f'<li><a href="{home}{href}">{label}</a></li>' for href, label in NAV),
        "onepct": onepct, "scripts": "", "page": page, "country": esc(ed["name"]),
        "bcorp_footer": bcorp_line(brief, root, "footer"),
    }


def with_head_extra(html_text: str, shell_tpl: str, head_extra: str) -> str:
    """Canonical + hreflang links (G1). _shell.html should carry {{head_extra}}
    inside <head> (see .tmp/head_extra.patch); until it does, the links are
    inserted before </head> here so every page still ships them."""
    if not head_extra or "{{head_extra}}" in shell_tpl:
        return html_text
    return html_text.replace("</head>", head_extra + "\n</head>", 1)


def emp_count_phrase(ed_key: str, n_emp: int) -> str:
    """' from N employers' for the UK edition when the count is worth saying
    (five or more); '' otherwise (Keith asked for no employer count on IE)."""
    if ed_key != "uk" or n_emp < 5:
        return ""
    return f" from {n_emp} employers"


def landing_search_href(spec: dict[str, Any], jobs_href: str = "../jobs/index.html") -> str:
    """The 'open these N roles' link: every sector of a multi-sector landing
    joined with '|' (lib.js filterJobs accepts any-of), or the region. `only=1`
    ticks the board's "Hide UK/abroad-only roles" toggle so the board opens the
    same set the landing page lists (LANDING_LOC)."""
    if spec["kind"] == "sector":
        return f"{jobs_href}?sector={qs('|'.join(sorted(spec['sectors'])))}&only=1"
    return f"{jobs_href}?loc={qs(spec['region'])}&only=1"


def landing_intro(spec: dict[str, Any], jobs: list[dict[str, Any]], ed: dict[str, Any], data: dict[str, Any]) -> str:
    """At most 80 words (visual sweep, 2026-09-28), every figure from the live data."""
    n = len(jobs)
    n_emp = len({j["employer"] for j in jobs})
    disclosed = [j for j in jobs if annual_mid(j, ed["currency"])]
    med = median_salary(jobs, ed["sym"], ed["currency"])
    top = [name for name, _ in Counter(j["employer"] for j in jobs).most_common(2)]
    regions = Counter(r for j in jobs for r in j["regions"] if r in data["region_table"]["regions"])
    place = spec.get("region") or ed["name"]
    unit = ed["unit"]
    sectors = Counter(s for j in jobs for s in j["sectors"])
    roles = "role" if n == 1 else "roles"
    emp_phrase = emp_count_phrase(data["ed"], n_emp)
    p1 = (f"GreenJobs {ed['short']} lists {n} live {spec['topic']} {roles} in {place} this week{emp_phrase}"
          f"{(' including ' if emp_phrase else ' from ') + ' and '.join(top) if top else ''}. ")
    if disclosed:
        p1 += f"{len(disclosed)} of the {n} publish a salary; the median disclosed salary is {med} a year in {ed['currency']}. "
    else:
        p1 += "None of them publishes a salary yet. "
    if spec["kind"] == "sector" and regions:
        p1 += f"Roles span {len(regions)} {plural(unit) if len(regions) != 1 else unit}, led by {', '.join(r for r, _ in regions.most_common(2))}. "
    elif spec["kind"] != "sector" and sectors:
        p1 += "Sectors: " + ", ".join(s for s, _ in sectors.most_common(3)) + ". "
    p1 += f"Each listing links to the advert on {data['site']}; salaries stay in the currency advertised and the list is rebuilt from the live board on every update."
    return esc(p1)


def landing_jsonld(jobs: list[dict[str, Any]], data: dict[str, Any], site_base: str) -> str:
    """ItemList of JobPosting entries (G2)."""
    items = []
    for i, j in enumerate(jobs[:50]):
        jp = job_jsonld_payload(j, data)
        jp.pop("@context", None)
        items.append({"@type": "ListItem", "position": i + 1, "url": f"{site_base}{data['ed']}/jobs/{j['href']}" if site_base else j["url"], "item": jp})
    return f'<script type="application/ld+json">{json_ld({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": items})}</script>'


def landing_pages(data: dict[str, Any]) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """(spec, matching jobs) for every landing page of this edition that has at least one role."""
    out = []
    pool = [j for j in data["jobs"] if j.get("loc_class", "ie" if data["ed"] == "ie" else "uk") in LANDING_LOC[data["ed"]]]
    for spec in LANDINGS[data["ed"]]:
        if spec["kind"] == "sector":
            jobs = [j for j in pool if set(j["sectors"]) & spec["sectors"]]
        else:
            jobs = [j for j in pool if spec["region"] in j["regions"]]
        if jobs:
            out.append((spec, jobs))
    return out


def guide_salary_body(data: dict[str, Any], ed: dict[str, Any]) -> dict[str, str]:
    """Bands, medians by sector, disclosure rate: the salary guide (G3)."""
    jobs = data["jobs"]
    cur = ed["currency"]
    disclosed = [j for j in jobs if annual_mid(j, cur)]
    bands = salary_bands(jobs, ed["sym"], cur)
    band_rows = "".join(f'<tr><th scope="row">{esc(ed["sym"])}{esc(b["l"])}</th><td class="num">{b["n"]}</td></tr>' for b in bands)
    sec_rows = []
    for s in data["sectors"]:
        if not s["n"]:
            continue
        in_s = [j for j in jobs if s["name"] in j["sectors"]]
        mids = sorted(a[2] for j in in_s for a in [annual_mid(j, cur)] if a)
        med = (mids[len(mids) // 2] if len(mids) % 2 else (mids[len(mids) // 2 - 1] + mids[len(mids) // 2]) / 2) if mids else None
        rate = round(100 * len(mids) / len(in_s))
        sec_rows.append((s["name"], s["n"], len(mids), rate, money_k(med, ed["sym"]) if med is not None and len(mids) >= 3 else "—"))
    sec_html = "".join(f'<tr><th scope="row">{esc(n)}</th><td class="num">{c}</td><td class="num">{d}</td><td class="num">{r}%</td><td class="num">{m}</td></tr>' for n, c, d, r, m in sec_rows)
    foreign = sum(1 for j in disclosed if j.get("cur") and j["cur"] != cur)
    unverified = sum(1 for j in jobs if is_unverified(j) and (j.get("sal_min") is not None or j.get("sal_max") is not None))
    unv_note = f" {unverified} UK-located role{'' if unverified == 1 else 's'} with unconfirmed currency {'is' if unverified == 1 else 'are'} excluded from medians." if unverified else ""
    return {
        "n_jobs": str(len(jobs)), "n_disc": str(len(disclosed)), "disc_pct": str(round(100 * len(disclosed) / max(1, len(jobs)))),
        "median": esc(median_salary(jobs, ed["sym"], cur)), "cur": cur, "sym": ed["sym"], "band_rows": band_rows, "sector_rows": sec_html,
        "updated": esc(snapshot_label(data["fetched"]).replace("Snapshot of ", "")), "country": esc(ed["name"]),
        "fx_note": (f"{foreign} of the disclosed salaries {'is' if foreign == 1 else 'are'} advertised in another currency; for the figures on this page they are converted at a fixed rate of 1 GBP = {FX_GBP_EUR} EUR. On role cards and job pages every salary stays in the currency the employer advertised."
                    if foreign else f"Every disclosed salary on this board is advertised in {cur}, so no conversion was needed.") + unv_note,
        "top_sector": esc(max(sec_rows, key=lambda r: (r[2], r[1]))[0]) if sec_rows else "",
    }


def build_edition(data: dict[str, Any], src: Path, out: Path, tpl: dict[str, str], brief: dict[str, Any], site_base: str, today: date,
                  evidence: dict[str, Any]) -> None:
    ed_key = data["ed"]
    ed = EDITIONS[ed_key]
    edir = out / ed_key
    edir.mkdir(parents=True, exist_ok=True)
    jobs = data["jobs"]
    n_emp = len({j["employer"] for j in jobs})
    n_sal = sum(1 for j in jobs if j["sal_min"] is not None or j["sal_max"] is not None)
    top_regions = [r for r in data["regions"] if r["on_map"]]
    colors = json_embed([s["color"] for s in data["sectors"][:5]])

    def write(rel: str, html_text: str) -> None:
        path = edir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html_text, encoding="utf-8")

    SCRIPTS = {"home": ["landscape"], "jobs": ["jobs", "fit"], "sectors": ["charts", "explore"], "insights": ["charts", "explore"], "compass": ["compass"], "employers": ["adbuilder"]}

    def page(name: str, depth: int, page_key: str, title: str, desc: str, body: dict[str, str], **kw: Any) -> str:
        ctx = shell_ctx(data, depth, page_key, title, desc, brief=brief, site_base=site_base, **kw)
        ctx["scripts"] = "".join(f'<script src="{ctx["root"]}js/{s}.js" defer></script>' for s in SCRIPTS.get(name, []))
        ctx["content"] = render(tpl[name], {**ctx, **body})
        return with_head_extra(render(tpl["_shell"], ctx), tpl["_shell"], ctx["head_extra"])

    # ---- home
    map_counts = {r["name"]: r["n"] for r in top_regions}
    strip = employers_strip(data, "../")
    n_sectors_live = sum(1 for s in data["sectors"] if s["n"])
    n_regions_live = sum(1 for r in top_regions if r["n"])
    hero_sub = ("Find environmental, sustainability, renewable-energy and nature careers across Ireland." if ed_key == "ie"
                else "Search environmental, ecology, sustainability, renewable-energy and low-carbon careers across the UK.")
    # Keith C1/C4: the region map band is a home section on the UK edition only;
    # the IE home reaches the county map through the Salary-insight tile.
    region_band = "" if ed_key == "ie" else (
        '<section class="band band--alt" aria-labelledby="h-map">'
        f'<div class="wrap mapband" data-home-map data-counts="{esc(json_embed(map_counts))}" data-jobs="jobs/index.html"><div>'
        '<h2 id="h-map">See where green employers are hiring</h2>'
        '<p class="muted" style="margin:14px 0 24px;max-width:44ch">Explore current vacancies by UK region, including nationwide and remote opportunities. '
        f'Hover or tab through the map for counts; choose one to open the filtered list.{off_map_note(data, "jobs/index.html")}</p>'
        f'<div class="maplist">{map_list(data, "jobs/index.html")}</div></div><div class="reveal">{map_svg(src, ed_key, map_counts)}</div></div></section>')

    FIT_EXAMPLES = {"ie": ["ecologist Dublin", "solar project manager", "water engineer flood risk"],
                    "uk": ["ecologist Bristol", "sustainability consultant London", "flood risk engineer Manchester", "renewable energy Scotland"]}
    FIT_PLACEHOLDER = {"ie": "e.g. Ecologist, five years of Phase 1 habitat surveys and EIA chapters, Dublin",
                       "uk": "e.g. Ecologist, five years of Phase 1 habitat surveys and EIA chapters, Bristol"}

    def fit_panel(jobs_href: str, fit_id: str) -> str:
        return render(tpl["_fit"], {"jobs_href": jobs_href, "sym": ed["sym"], "fit_id": fit_id, "n_jobs": str(len(jobs)), "fit_map": map_svg(src, ed_key),
                                    "fit_examples": "".join(f'<button type="button" data-fit-eg="{esc(x)}">{esc(x)}</button>' for x in FIT_EXAMPLES[ed_key]),
                                    "fit_placeholder": esc(FIT_PLACEHOLDER[ed_key])})
    home = page("home", 1, "index", f"GreenJobs {ed['short']} — {len(jobs)} live green roles across {ed['name']}",
                f"Environmental, renewable energy and sustainability jobs across {ed['name']}: {len(jobs)} live roles{emp_count_phrase(ed_key, n_emp)}, searchable in a second.",
                {
                    "n_jobs": str(len(jobs)), "n_emp": str(n_emp), "n_sal": str(n_sal), "country": esc(ed["name"]), "unit": ed["unit"], "units": plural(ed["unit"]),
                    "colors": esc(colors), "sector_tiles": sector_tiles(data, "jobs/index.html", today, ed["sym"]),
                    "latest_rows": "".join(home_row(j, "../", "jobs/", today, ed["currency"]) for j in jobs[:8]),
                    "hero_bcorp": hero_bcorp(brief, "../"), "hero_video": hero_video(src, ed_key, "../"), "bcorp_note": BCORP_NOTE,
                    "hero_sub": hero_sub, "hero_facts": hero_facts(data, n_emp), "region_band": region_band,
                    "latest_title": "Latest roles" if ed_key == "ie" else "Latest UK roles",
                    "snapshot_short": esc(snapshot_label(data["fetched"]).replace("Snapshot of", "snapshot of")),
                    "emp_heading": "Employer proposition" if ed_key == "ie" else "Employers and advertising",
                    "alert_title": "Email alerts: the week's green roles, in your inbox" if ed_key == "ie" else "Job alerts: the week's green roles, in your inbox",
                    "n_disc": str(n_sal), "disc_pct": str(round(100 * n_sal / max(1, len(jobs)))), "median": esc(median_salary(jobs, ed["sym"], ed["currency"])),
                    "inside_net": "".join(f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}<span class="arw" aria-hidden="true">↗</span></a></li>' for s in data["network_sites"] if str(s.get("url", "")).startswith("http")),
                    "n_regions": str(n_regions_live), "employers": strip["html"], "emp_title": strip["title"], "emp_sub": strip["sub"], "snapshot": esc(snapshot_label(data["fetched"])), "facts": facts_block(brief, data),
                    "sector_options": "".join(f'<option value="{esc(s["name"])}">{esc(s["name"])}</option>' for s in data["sectors"] if s["n"]),
                    "n_sectors": str(n_sectors_live),
                }, body_attrs=' data-data="data/jobs.json"', same_path="index.html")
    write("index.html", home)
    (edir / "data").mkdir(exist_ok=True)
    (edir / "data" / "jobs.json").write_text(json.dumps({"today": data["today"], "jobs": [slim(j, True) for j in jobs]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- jobs board
    pages_for_palette = json_embed([{"t": lbl, "h": "../" + href} for href, lbl in NAV] + [{"t": "Home", "h": "../index.html"}])
    board = page("jobs", 2, "jobs", f"Green jobs across {ed['name']} — search {len(jobs)} live roles | GreenJobs {ed['short']}",
                 f"Filter {len(jobs)} live environmental and renewable energy roles by {ed['unit']}, sector, type and salary.",
                 {
                     "dataset": dataset_script(data, "index.html", True), "jsonld": jobs_jsonld(data, site_base) if site_base else "",
                     "loc_options": "".join(f'<option value="{esc(r["name"])}">' for r in top_regions),
                     "sector_select": select("f-sector", "Sector", [s["name"] for s in data["sectors"] if s["n"]], "All sectors"),
                     # Job type is folded into Contract + Workplace (visual 31); the hidden field keeps ?type= working as an alias.
                     "type_select": '<input type="hidden" id="f-type" name="type" value="">',
                     "wp_select": select_pairs("f-wp", "Workplace", [(k, WORKPLACE_LABEL[k]) for k in ("office", "hybrid", "remote", "site", "unspecified") if any(j["workplace"] == k for j in jobs)], "Any workplace"),
                     "level_select": select_pairs("f-level", "Career level", [(lv, lv) for lv in LEVEL_ORDER if any(j["level"] == lv for j in jobs)], "Any level"),
                     "ct_select": select_pairs("f-ct", "Contract", [(k, CONTRACT_LABEL[k]) for k in CONTRACT_LABEL if any(k in j["contract"] for j in jobs)], "Any contract"),
                     "close_select": select_pairs("f-close", "Closing date", [("7", "Closing within 7 days"), ("14", "Closing within 14 days"), ("30", "Closing within 30 days"), ("open", "Hide closed roles")], "Any closing date"),
                     "emp_select": select_pairs("f-emp", "Advertised by", [("direct", "Direct employer"), ("agency", "Recruitment agency")], "Employers and agencies"),
                     "only_label": esc("Hide UK/abroad-only roles" if ed_key == "ie" else "Hide Ireland/abroad-only roles"),
                     "only_hint": esc("Keeps Ireland, Northern Ireland, remote and Ireland-and-UK roles; hides roles advertised only in the UK or abroad." if ed_key == "ie" else "Keeps UK, Northern Ireland, remote and Ireland-and-UK roles; hides roles advertised only in Ireland or abroad."),
                     "cur": ed["currency"], "sym": ed["sym"], "units": plural(ed["unit"]),
                     "multi_note": esc(MULTI_COUNT_NOTE.format(units=plural(ed["unit"]))),
                     "unit": ed["unit"].title(), "map": map_svg(src, ed_key), "map_counts": map_list(data, "index.html"), "pages": esc(pages_for_palette), "n_jobs": str(len(jobs)),
                     "fit_panel": fit_panel("index.html", "fit-q"),
                 }, same_path="jobs/index.html")
    write("jobs/index.html", board)

    # ---- one page per job
    for j in jobs:
        similar = similar_jobs(j, jobs, ed["currency"], 4)
        sal = salary_label(j, ed["currency"])
        note = currency_note(j, ed["currency"])
        meta_tags = ("".join(f'<span class="tag">{esc(x)}</span>' for x in [j["location"], j["type"]] if x) + loc_badge(j)
                     + (f'<span class="tag tag--sal">{esc(sal)}</span>' if sal else "")
                     + (f'<span class="tag tag--wp">{esc(WORKPLACE_LABEL[j["workplace"]])}</span>' if j["workplace"] != "unspecified" else ""))
        dl = ""
        for k, v in (("Location", j["location"]), ("Where", LOC_LABEL.get(j["loc_class"], "")), ("Workplace", WORKPLACE_LABEL[j["workplace"]] if j["workplace"] != "unspecified" else ""),
                     ("Contract", contract_row(j)), ("Level", j["level"]),
                     ("Salary", (j["sal_text"] or (sal or "Not disclosed")) + (f" ({note.lower()}, about {sal.split('about ', 1)[1].rstrip(')')})" if note and "about " in sal else "")),
                     ("Salary source", salary_source_line(j)),
                     ("Advertised by", "Recruitment agency" if j["agency"] else "Direct employer"),
                     ("Posted", date_long(j["posted"]) if j["posted"] else ""), ("Closes", date_long(j["closing"]) if j["closing"] else ""), ("Sector", ", ".join(j["sectors"]))):
            if v:
                dl += f"<dt>{k}</dt><dd>{esc(v)}</dd>"
        body_html = j["description_html"] or f"<p>{esc(j['summary'])}</p>"
        jp = page("job", 3, "jobs", f"{j['title']} — {j['employer']} | GreenJobs {ed['short']}", (j["summary"] or j["title"])[:155],
                  {
                      "jsonld": job_jsonld(j, data), "title": esc(no_break_dash(j["title"])), "employer": esc(j["employer"]), "logo": logo_img(j, "../../../", "job__logo") if j["logo"] else "",
                      "meta": meta_tags, "dl": dl, "desc_html": body_html, "apply_url": esc(j["url"]), "domain": esc(data["site"]), "id": esc(j["id"]), "region": esc((j.get("regions") or [""])[0]), "closing": esc(j.get("closing") or ""),
                      "similar": "".join(role_card(s, "../../../", "../", today, ed["currency"]) for s in similar) or '<p class="muted">No similar live roles this week.</p>',
                      "sector_link": f'../index.html?sector={qs(j["sectors"][0])}', "sector": esc(j["sectors"][0]),
                      "posted_line": esc(f"Posted {date_long(j['posted'])}" + (f" · closes {date_long(j['closing'])}" if j["closing"] else "")) if j["posted"] else "",
                      "sits": salary_strip(j, jobs, ed["sym"], ed["unit"], set(data["region_table"]["regions"]), ed["currency"]),
                  }, same_path=f"jobs/{j['href']}", switch_path="jobs/index.html")
        write(f"jobs/{j['id']}/index.html", jp)

    # ---- SEO landing pages (G2) and the content hub (G3)
    built_landings = landing_pages(data)
    data["landings"] = [spec["slug"] for spec, _ in built_landings]
    for spec, in_page in built_landings:
        related = "".join(f'<li><a href="../{o["slug"]}/index.html">{esc(o["h1"])}</a></li>' for o, _ in built_landings if o["slug"] != spec["slug"])
        related += '<li><a href="../guides/salary-guide/index.html">Green salary guide</a></li>'
        write(f"{spec['slug']}/index.html", page("landing", 2, "jobs", f"{spec['h1']} — {len(in_page)} live {'role' if len(in_page) == 1 else 'roles'} | GreenJobs {ed['short']}",
                                                  f"{len(in_page)} live {spec['topic']} roles in {spec.get('region') or ed['name']} on GreenJobs {ed['short']}, with disclosed salaries and employers.",
                                                  {"h1": esc(spec["h1"]), "intro": landing_intro(spec, in_page, ed, data), "n": str(len(in_page)),
                                                   "roles": "".join(role_card(j, "../../", "../jobs/", today, ed["currency"]) for j in in_page),
                                                   "related": related, "jsonld": landing_jsonld(in_page, data, site_base), "search_href": landing_search_href(spec),
                                                   "updated": esc(snapshot_label(data["fetched"]))}, same_path=f"{spec['slug']}/index.html", switch_path="jobs/index.html"))
    guide = guide_salary_body(data, ed)
    write("guides/salary-guide/index.html", page("guide_salary", 3, "guides", f"Green salary guide {ed['short']} — what {ed['name']}'s green roles pay | GreenJobs {ed['short']}",
                                                  f"Salary bands, medians by sector and disclosure rates from {len(jobs)} live green roles on GreenJobs {ed['short']}.",
                                                  guide, same_path="guides/salary-guide/index.html"))
    write("guides/index.html", page("guides", 2, "guides", f"Guides — green careers in {ed['name']} | GreenJobs {ed['short']}",
                                    f"Salary guides and market pages built from the live GreenJobs {ed['short']} board.",
                                    {"updated": esc(snapshot_label(data["fetched"])), "n_jobs": str(len(jobs)), "n_disc": guide["n_disc"], "median": guide["median"], "country": esc(ed["name"]),
                                     "landing_links": "".join(f'<li><a href="../{spec["slug"]}/index.html">{esc(spec["h1"])}</a> <span class="muted">· {len(in_page)} live</span></li>' for spec, in_page in built_landings)},
                                    same_path="guides/index.html"))

    # ---- sectors, insights, compass, employers
    sec_rows = "".join(
        f'<a class="secrow" data-secrow="{esc(s["name"])}" href="../jobs/index.html?sector={qs(s["name"])}"><span><i style="background:{s["color"]}"></i>{esc(s["name"])}</span><b class="num">{s["n"]}</b></a>'
        for s in data["sectors"] if s["n"] > 0)
    write("sectors/index.html", page("sectors", 2, "sectors", f"Sectors — where the green work is | GreenJobs {ed['short']}",
                                     f"Every sector with live roles on GreenJobs {ed['short']}, sized by count.",
                                     {"dataset": dataset_script(data, "../jobs/index.html", False), "rows": sec_rows,
                                      "multi_note": esc(MULTI_COUNT_NOTE.format(units=plural(ed["unit"]))),
                                      "n_sectors": str(sum(1 for s in data["sectors"] if s["n"])), "n_jobs": str(len(jobs))}, same_path="sectors/index.html"))
    write("insights/index.html", page("insights", 2, "insights", f"Green salary explorer — what {ed['name']}'s green roles pay | GreenJobs {ed['short']}",
                                      f"Disclosed salaries on GreenJobs {ed['short']}: bands, medians by sector, disclosure rates and roles by {ed['unit']}.",
                                      {"dataset": dataset_script(data, "../jobs/index.html", False), "cur": ed["sym"], "unit": ed["unit"], "n_jobs": str(len(jobs)), "n_sal": str(n_sal),
                                       "disc_pct": str(round(100 * n_sal / max(1, len(jobs)))), "median": esc(median_salary(jobs, ed["sym"], ed["currency"])),
                                       "fetched": esc(data["fetched"])}, same_path="insights/index.html"))
    write("compass/index.html", page("compass", 2, "compass", f"Green Career Compass — find your sector in seven questions | GreenJobs {ed['short']}",
                                     "Seven quick questions, three sectors that fit, live roles to match.",
                                     {"dataset": dataset_script(data, "../jobs/index.html", False)}, same_path="compass/index.html"))
    render_dashboard(data, src, out, tpl, brief, site_base)
    emp_strip = employers_strip(data, "../../", cap=None)  # the employers page lists every live employer
    # Keith E7: UK-only credibility block. Testimonials are collected for launch
    # (brief.md testimonials are anonymous; none is reproduced).
    trust_block = "" if ed_key != "uk" else (
        '<section class="wrap band--tight" aria-labelledby="h-trust"><div class="sec-head"><div><h2 id="h-trust">Trusted across the UK</h2>'
        '<p>Client testimonials available on request.</p></div>'
        '<a class="btn btn--lime" href="#rates" data-ev="request_rates">Request advertising rates<span class="arw" aria-hidden="true">→</span></a></div>'
        f'<p class="netline" style="margin-top:24px"><b>Network coverage:</b> {network_inline(data)}</p></section>')
    write("employers/index.html", page("employers", 2, "employers", f"Advertise a green role | GreenJobs {ed['short']}",
                                       f"Reach candidates who only want green work. What GreenJobs {ed['short']} offers employers.",
                                       {"n_jobs": str(len(jobs)), "n_emp": str(n_emp), "emp_count_phrase": esc(emp_count_phrase(ed_key, n_emp)), "n_sites": str(len(data["network_sites"])), "about": esc(data["about"].split("\n")[0]),
                                        "email": esc(next(iter(dict.fromkeys((data["contact"] or {}).get("emails") or [])), f"info@{data['site']}")),
                                        "net_inline": network_inline(data), "employers": emp_strip["html"], "emp_sub": emp_strip["sub"],
                                        "trust_block": trust_block,
                                        "country": esc(ed["name"]), "reach": esc(json_embed(reach_payload(data))), "sym": ed["sym"],
                                        "unit": ed["unit"], "fetched": esc(data["fetched"]),
                                        "sector_options": "".join(f'<option value="{esc(s["name"])}">{esc(s["name"])}</option>' for s in data["sectors"] if s["n"])}, same_path="employers/index.html"))

    # ---- evidence page (rendered after measuring; filled in by build())
    evidence[ed_key] = {"n_jobs": len(jobs), "n_emp": n_emp, "n_sal": n_sal, "n_sectors": sum(1 for s in data["sectors"] if s["n"]), "n_regions": len(top_regions),
                        "excluded": data.get("excluded") or [], "closed": len(data.get("closed") or []), "landings": len(built_landings)}

    # No per-edition 404: GitHub Pages and Cloudflare Pages only ever serve the
    # root 404.html (src/templates/404root.html), which is self-contained.


def render_evidence(out: Path, src: Path, data_by_ed: dict[str, dict[str, Any]], tests: tuple[int, int] | None, today: date) -> dict[str, str]:
    """Before/after rows from perf_<ed>.json (scraped by the research worker)
    and the built site's own measured bytes. Nothing here is typed by hand."""
    rows: dict[str, str] = {}
    css = sorted((out / "css").glob("*.css"))
    js = sorted((out / "js").glob("*.js"))
    css_raw = sum(_measure(p)[0] for p in css)
    js_raw = sum(_measure(p)[0] for p in js)
    js_gz = sum(_measure(p)[1] for p in js)
    css_gz = sum(_measure(p)[1] for p in css)
    for ed_key, data in data_by_ed.items():
        perf_path = src / "data" / f"perf_{ed_key}.json"
        perf = json.loads(perf_path.read_text(encoding="utf-8")) if perf_path.exists() else {}
        home = out / ed_key / "index.html"
        home_raw, home_gz = _measure(home)
        home_html = home.read_text(encoding="utf-8")
        local_refs = len(set(re.findall(r'(?:href|src)="([^"#?]+\.(?:css|js|woff2|png|jpg|jpeg|gif|svg|webp|json))', home_html)))
        third = len(re.findall(r'<(?:link|script|img|iframe|source)\b[^>]*(?:href|src)="(?:https?:)?//', home_html))
        before_html = perf.get("html_bytes")
        before_req = perf.get("total_requests_estimate")
        before_scripts = perf.get("script_tags_external")
        stack_before = ", ".join(x for x in [f"jQuery {perf['jquery']}" if perf.get("jquery") else "", "Bootstrap 3" if perf.get("bootstrap") else "", "html5shiv" if perf.get("html5shiv") else "", "vendor CDN" if perf.get("platform_cdn") else ""] if x) or "not measured"

        def cell(v: Any, unit: str = "") -> str:
            return f"{v:,}{unit}" if isinstance(v, (int, float)) else "not measured"
        rows[ed_key] = (
            f"<tr><td>Home page HTML</td><td class=\"n\">{cell(before_html, ' B')}</td><td class=\"n good\">{home_raw:,} B ({home_gz:,} B gzipped)</td></tr>"
            f"<tr><td>Requests on the home page <small class=\"muted\">estimated (live) / measured (demo)</small></td><td class=\"n\">{cell(before_req)} (estimated)</td><td class=\"n good\">{local_refs + 1} measured, all first-party</td></tr>"
            f"<tr><td>External script tags</td><td class=\"n\">{cell(before_scripts)}</td><td class=\"n good\">{len(js)} own files, {js_raw / 1024:.1f} KB ({js_gz / 1024:.1f} KB gzipped)</td></tr>"
            f"<tr><td>Third-party requests</td><td class=\"n\">{'yes (analytics, CDN fonts/scripts)' if perf.get('ga4') or perf.get('platform_cdn') else 'not measured'}</td><td class=\"n good\">{third}</td></tr>"
            f"<tr><td>Stylesheet</td><td class=\"n\">{len(perf.get('stylesheets') or []) or 'not measured'} files</td><td class=\"n good\">1 file, {css_raw / 1024:.1f} KB ({css_gz / 1024:.1f} KB gzipped)</td></tr>"
            f"<tr><td>Front-end stack</td><td>{esc(stack_before)}</td><td class=\"good\">Vanilla ES2020, no framework, no build-time packages</td></tr>"
            f"<tr><td>Pages rendered</td><td>server-side, per request</td><td class=\"good\">{len(list((out / ed_key).rglob('*.html')))} static pages, {len(data['jobs'])} of them job pages</td></tr>"
            + excluded_row(data)
        )
        rows[ed_key + "_score"] = scoreboard(before_html, home_raw, before_req, local_refs + 1, before_scripts, len(js), len(data["jobs"]))
        rows[ed_key + "_waterfall"] = waterfall(perf, home_html)
    rows["tests"] = f"{tests[0]} passing, {tests[1]} failing" if tests else "not run (node unavailable)"
    rows["built"] = today.isoformat()
    rows["css_kb"] = f"{css_raw / 1024:.1f}"
    rows["js_kb"] = f"{js_raw / 1024:.1f}"
    return rows


def excluded_row(data: dict[str, Any]) -> str:
    """Evidence-table row for the edition inclusion rule (B5): what each board
    leaves off. UK: how many scraped roles were kept off greenjobs.co.uk and
    why. IE: nothing is excluded (Keith: "allow users to exclude UK
    opportunities"); UK-only roles are shown with a UK label, sterling figures
    restored from the greenjobs.co.uk twin, and the hide toggle."""
    ex = data.get("excluded") or []
    ed_key = data["ed"]
    ed = EDITIONS[ed_key]
    if ed_key == "ie":
        uk_only = sum(1 for j in data["jobs"] if j["loc_class"] == "uk")
        fixed = len(data.get("corrected") or [])
        return (f"<tr><td>Roles outside {esc(ed['name'])} <small class=\"muted\">Keith: retain the advertised currency, label UK / Ireland / remote / cross-border, let users exclude UK opportunities</small></td>"
                f"<td class=\"n\">shown, unlabelled, sterling relabelled as euros</td>"
                f"<td class=\"n good\">0 roles excluded; {uk_only} UK-only role{'' if uk_only == 1 else 's'} shown with a UK label and the \"Hide UK/abroad-only roles\" toggle; "
                f"{fixed} of them carry the sterling figures from the greenjobs.co.uk listing (the rest keep the scraped figures)</td></tr>")
    by = Counter(x["loc_class"] for x in ex)
    detail = ", ".join(f"{n} {LOC_LABEL.get(k, k)}" for k, n in by.most_common()) or "none"
    titles = "; ".join(f"{esc(x['title'])} ({esc(x['location'])})" for x in ex[:6])
    single = by.get("ie", 0)
    headline = f"{single} Ireland-only role{'' if single == 1 else 's'} kept off {EDITION_HOST[ed_key]}" + (f", {by['intl']} international" if by.get("intl") else "")
    return (f"<tr><td>Roles excluded by the UK inclusion rule <small class=\"muted\">shown only if located in the UK or NI, fully remote, or advertised for Ireland and the UK</small></td>"
            f"<td class=\"n\">{len(data['jobs']) + len(ex)} listed, all counted</td><td class=\"n good\">{esc(headline)}: {len(ex)} excluded ({detail}){'; ' + titles if titles else ''}{'…' if len(ex) > 6 else ''}</td></tr>")


def scoreboard(before_html: Any, after_html: int, before_req: Any, after_req: int, before_scripts: Any, after_scripts: int, n_jobs: int) -> str:
    """Count-up tiles; a live-site figure that was not measured is shown as such, never invented."""
    def tile(label: str, before: Any, after: int, unit: str = "") -> str:
        b = f'<b class="num" data-count="{before}">{before:,}</b>{unit}' if isinstance(before, (int, float)) else '<span class="muted">not measured</span>'
        return (f'<div class="score__t"><span class="score__l">{label}</span><span class="score__v">{b}</span>'
                f'<span class="score__v score__v--after"><b class="num" data-count="{after}">{after:,}</b>{unit}</span></div>')
    return (tile("Home page HTML, bytes", before_html, after_html) + tile("Requests on the home page", before_req, after_req)
            + tile("Script files", before_scripts, after_scripts) + tile("Job pages with structured data", 0, n_jobs))


def waterfall(perf: dict[str, Any], home_html: str) -> str:
    """Two stacked bars from measured counts: the live home page's requests
    by type (from its HTML, an estimate) and this demo's first-party requests
    by type (counted in the built page). Same scale, no screenshots."""
    live = [("scripts", len(perf.get("scripts") or [])), ("stylesheets", len(perf.get("stylesheets") or [])), ("images", int(perf.get("img_tags") or 0))]
    total = int(perf.get("total_requests_estimate") or 0)
    counted = sum(n for _, n in live)
    other = max(0, total - counted)
    live.append(("other", other))
    total = max(total, counted)
    refs = set(re.findall(r'(?:href|src)="([^"#?]+\.(?:css|js|woff2|png|jpg|jpeg|gif|svg|webp|json|webmanifest))', home_html))
    demo = [("scripts", sum(1 for r in refs if r.endswith(".js"))), ("stylesheets", sum(1 for r in refs if r.endswith(".css"))),
            ("images", sum(1 for r in refs if re.search(r"\.(png|jpe?g|gif|svg|webp)$", r) and "favicon" not in r)),
            ("other", 1 + sum(1 for r in refs if re.search(r"\.(woff2|json|webmanifest)$", r) or "favicon" in r))]
    mx = max(total, sum(n for _, n in demo), 1)

    def bar(label: str, parts: list[tuple[str, int]], note: str) -> str:
        tot = sum(n for _, n in parts)
        segs = "".join(f'<i class="wf__s wf__s--{k}" style="--w:{100 * n / mx:.2f}%" title="{k}: {n}"></i>' for k, n in parts if n)
        legend = ", ".join(f"{n} {k}" for k, n in parts if n)
        return (f'<div class="wf__row"><span class="wf__l">{label}</span><span class="wf__bar" role="img" aria-label="{label}: {tot} requests ({legend})">{segs}</span>'
                f'<b class="wf__n num" data-count="{tot}">{tot}</b></div><p class="wf__note">{legend}. {note}</p>')
    if not total:
        return '<p class="muted">Live-site request counts were not measured for this edition.</p>'
    return ('<div class="wf">' + bar("Live site", live, "Tags counted in the page's HTML on 2026-09-22, not a network trace: the table's request estimate is lower because repeated images are fetched once. \"Other\" is fonts, XHR and tracking where the estimate exceeds the tag count.")
            + bar("This demo", demo, "Counted in the built home page: every request is first-party; logos load lazily and are not in this count.") + "</div>")


# ------------------------------------------------------------------ build plumbing

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def publish_text(text: str) -> str:
    """Strip block comments, whole-line // comments and indentation from CSS/JS."""
    out = _BLOCK_COMMENT.sub("", text)
    kept = []
    for line in out.split("\n"):
        bare = line.strip()
        if not bare or bare.startswith("//"):
            continue
        kept.append(bare)
    return "\n".join(kept) + "\n"


def run_node_tests(src: Path) -> tuple[int, int] | None:
    test = src / "js" / "lib.test.js"
    if not test.exists():
        return None
    try:
        proc = subprocess.run(["node", "--test", "lib.test.js"], cwd=str(src / "js"), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"      node tests not run: {type(exc).__name__}: {exc}")
        return None
    passed = failed = 0
    for line in proc.stdout.splitlines():
        if line.startswith("# pass "):
            passed = int(line.split()[-1])
        elif line.startswith("# fail "):
            failed = int(line.split()[-1])
    if proc.returncode != 0 and failed == 0:
        failed = 1
    if passed == 0 and failed == 0:
        failed = 1
    return passed, failed


def check_built_js(site: Path) -> list[str]:
    problems: list[str] = []
    for script in sorted((site / "js").glob("*.js")):
        try:
            proc = subprocess.run(["node", "--check", script.name], cwd=str(script.parent), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            problems.append(f"{script.name}: node --check could not run: {type(exc).__name__}: {exc}")
            continue
        if proc.returncode != 0:
            problems.append(f"{script.name} does not parse after the publish pass: {proc.stderr.strip()[:200]}")
        if "'use strict'" not in script.read_text(encoding="utf-8")[:200]:
            problems.append(f"{script.name} does not start with 'use strict'")
    return problems


def site_tree_sha(site: Path) -> str:
    """sha256 over every file in the site tree (path + bytes), markers and
    screenshot scratch excluded, so deploy_cloudflare.sh can prove the
    validated tree is the one it ships."""
    import hashlib
    h = hashlib.sha256()
    for p in sorted(site.rglob("*")):
        if not p.is_file() or p.name in (MARKER, OK_MARKER) or p.name.startswith("_shot-"):
            continue
        h.update(p.relative_to(site).as_posix().encode("utf-8") + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def guard_output(src: Path, out: Path) -> str:
    repo = Path(__file__).resolve().parents[3]
    allowed = [repo / "deliverables", repo / ".tmp"]
    scratch = os.environ.get("CLAUDE_SCRATCHPAD")
    if scratch:
        allowed.append(Path(scratch).resolve())
    if not any(_within(out, base) for base in allowed):
        return f"--out {out} is outside the build areas ({', '.join(str(b) for b in allowed)}); refusing to delete it"
    if out == src or _within(src, out) or _within(out, src):
        return f"--out {out} overlaps --src {src}; refusing to delete it"
    if out.parent == out:
        return f"--out {out} is a filesystem root; refusing to delete it"
    if out.exists():
        if not out.is_dir():
            return f"--out {out} exists and is not a directory"
        if not (out / MARKER).exists() and any(out.iterdir()):
            return (f"--out {out} is not empty and was not created by this build (no {MARKER} marker); refusing to delete it. "
                    f"Remove it manually or create an empty {MARKER} file in it, then re-run.")
    return ""


def _within(child: Path, parent: Path) -> bool:
    try:
        return child.resolve().is_relative_to(parent.resolve())
    except (OSError, ValueError):
        return False


def load_templates(src: Path) -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in (src / "templates").glob("*.html")}


def build(src: Path, out: Path, *, editions: list[str], fixture: Path | None = None, site_base: str = "", today: date | None = None) -> int:
    if not src.is_dir():
        print(f"FAIL  source directory not found: {src}", file=sys.stderr)
        return 2
    refusal = guard_output(src, out)
    if refusal:
        print(f"FAIL  {refusal}", file=sys.stderr)
        return 2
    (out / OK_MARKER).unlink(missing_ok=True)  # a failed build must never leave a deployable marker behind
    config = json.loads((src / "config.json").read_text(encoding="utf-8")) if (src / "config.json").exists() else {}
    site_base = (site_base or str(config.get("site_base") or "")).rstrip("/") + "/" if (site_base or config.get("site_base")) else ""
    tpl = load_templates(src)
    brief = read_brief(src)
    logos_dir = src / "assets" / "logos"
    for key, name in (("bcorp_size", "b-corp-logo.svg"), ("onepct_size", "1fortheplanet.svg")):
        if (logos_dir / name).is_file():
            brief[key] = image_size(logos_dir / name)

    data_by_ed: dict[str, dict[str, Any]] = {}
    for ed_key in editions:
        path = fixture if fixture else src / "data" / f"{ed_key}.json"
        if not path.exists():
            print(f"FAIL  dataset missing: {path}", file=sys.stderr)
            return 2
        raw = json.loads(path.read_text(encoding="utf-8"))
        today = build_today(raw, today)  # first dataset's fetched date unless --today was given
        data = normalise(raw, ed_key, src, logos_dir, today)
        problems = check_dataset(data)
        if problems:
            print(f"FAIL  {ed_key}.json has {len(problems)} problem(s):", file=sys.stderr)
            for line in problems:
                print(f"  - {line}", file=sys.stderr)
            return 2
        data_by_ed[ed_key] = data
        unresolved = sum(1 for j in data["jobs"] if not any(r in data["region_table"]["regions"] for r in j["regions"]))
        off_map = ", ".join(f"{r['name']} {r['n']}" for r in data["regions"] if not r["on_map"])
        print(f"…  {ed_key}: {len(data['jobs'])} jobs, {sum(1 for s in data['sectors'] if s['n'])} sectors live, {unresolved} jobs off-map ({off_map}), {len(data['excluded'])} excluded by the edition rule, {len(data.get('corrected') or [])} sterling salaries restored from greenjobs.co.uk, {len(data['closed'])} closed before {today}")
    assert today is not None
    # hreflang pairs: only paths built in both editions (landing slugs differ per edition)
    paths_by_ed = {k: PAIRED_PATHS | {f"{spec['slug']}/index.html" for spec, _ in landing_pages(d)} for k, d in data_by_ed.items()}
    paired = paired_paths(paths_by_ed)
    for k, d in data_by_ed.items():
        d["paired_paths"] = paired.get(k, {})

    # ---- copy the static tree
    if out.exists():
        shutil.rmtree(out)  # also drops any stale OK_MARKER: nothing is deployable until validate passes again
    out.mkdir(parents=True)
    (out / MARKER).write_text("generated by build_site.py\n", encoding="utf-8")
    for name in ("css", "js"):
        shutil.copytree(src / name, out / name, ignore=shutil.ignore_patterns("*.test.js", "__pycache__"))
        for path in (out / name).glob("*"):
            if path.suffix in (".css", ".js"):
                path.write_text(publish_text(path.read_text(encoding="utf-8")), encoding="utf-8")
    (out / "assets").mkdir()
    for sub in ("fonts",):
        shutil.copytree(src / "assets" / sub, out / "assets" / sub)
    for f in (src / "assets").glob("*.*"):
        shutil.copy2(f, out / "assets" / f.name)
    hero_src = src / HERO_DIR
    if hero_src.is_dir():
        used = {name for ed_key in ("ie", "uk") for name in hero_files(src, ed_key).values()}
        if used:
            (out / HERO_DIR).mkdir(parents=True, exist_ok=True)
            for name in sorted(used):
                shutil.copy2(hero_src / name, out / HERO_DIR / name)
    used_logos = {j["logo"] for d in data_by_ed.values() for j in d["jobs"] if j["logo"]} | {e["logo"] for d in data_by_ed.values() for e in d["employers"] if e["logo"]}
    used_logos |= {n for k, n in (("bcorp_size", "b-corp-logo.svg"), ("onepct_size", "1fortheplanet.svg")) if brief.get(k)}
    (out / "assets" / "logos").mkdir()
    for name in sorted(used_logos):
        shutil.copy2(logos_dir / name, out / "assets" / "logos" / name)
    for static in ("robots.txt",):
        if (src / static).exists():
            shutil.copy2(src / static, out / static)

    evidence: dict[str, Any] = {}
    for ed_key, data in data_by_ed.items():
        build_edition(data, src, out, tpl, brief, site_base, today, evidence)

    # ---- root chooser + 404 + manifest + sitemap
    tiles = []
    for ed_key in ("ie", "uk"):
        d = data_by_ed.get(ed_key)
        ed = EDITIONS[ed_key]
        n = len(d["jobs"]) if d else 0
        tiles.append(f'<a class="tile" href="{ed_key}/index.html" data-edswitch="{ed_key}" hreflang="{ed["lang"]}"><span class="flag" aria-hidden="true">'
                     + ('<i style="background:#169b62"></i><i style="background:#fff"></i><i style="background:#ff883e"></i>' if ed_key == "ie" else '<i style="background:#012169"></i><i style="background:#c8102e"></i><i style="background:#012169"></i>')
                     + f'</span><h2>GreenJobs {ed["short"]}</h2><p>{esc(ed["domain"])} — green roles across {esc(ed["name"])}, in {ed["sym"]}.</p><span class="n num">{n} live roles →</span></a>')
    chooser = render(tpl["chooser"], {"tiles": "".join(tiles), "year": str(today.year)})
    (out / "index.html").write_text(chooser, encoding="utf-8")
    (out / "404.html").write_text(render(tpl["404root"], {}), encoding="utf-8")
    manifest = {"name": "GreenJobs", "short_name": "GreenJobs", "start_url": "./index.html", "display": "standalone",
                "background_color": "#f6f0e6", "theme_color": "#f6f0e6", "icons": [{"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]}
    (out / "manifest.webmanifest").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    if site_base:
        urls = "".join(f"<url><loc>{esc(site_base)}{ed_key}/{p}</loc></url>" for ed_key in data_by_ed for p in PAGES_FOR_SITEMAP)
        urls += "".join(f"<url><loc>{esc(site_base)}{ed_key}/{slug}/index.html</loc></url>" for ed_key, d in data_by_ed.items() for slug in d.get("landings") or [])
        urls += "".join(f"<url><loc>{esc(site_base)}{ed_key}/jobs/{j['href']}</loc></url>" for ed_key, d in data_by_ed.items() for j in d["jobs"])
    else:
        urls = ""
    (out / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")

    # ---- evidence page last (it measures the files written above)
    tests = run_node_tests(src)
    if tests is None:
        print("FAIL  node tests could not run (node missing or lib.test.js absent); the build is not verified", file=sys.stderr)
        return 1
    if tests[1]:
        print(f"FAIL  {tests[1]} node test(s) failing", file=sys.stderr)
        return 1
    ev = render_evidence(out, src, data_by_ed, tests, today)
    for ed_key, data in data_by_ed.items():
        ctx = shell_ctx(data, 2, "for-keith", "For Keith — the evidence behind the GreenJobs redesign demo",
                        "What was measured, what was built, what comes next.", brief=brief, site_base=site_base, same_path="for-keith/index.html")
        e = evidence[ed_key]
        ctx["content"] = render(tpl["for-keith"], {**ctx, "rows": ev[ed_key], "tests": esc(ev["tests"]), "built": esc(ev["built"]), "css_kb": ev["css_kb"], "js_kb": ev["js_kb"],
                                                    "n_jobs": str(e["n_jobs"]), "n_emp": str(e["n_emp"]), "n_sal": str(e["n_sal"]), "n_sectors": str(e["n_sectors"]),
                                                    "n_regions": str(e["n_regions"]), "other_ed": EDITIONS[ed_key]["other"], "domain": esc(data["site"]),
                                                    "score": ev[ed_key + "_score"], "waterfall": ev[ed_key + "_waterfall"],
                                                    "css_budget": str(validate_site.CSS_BUDGET // 1024), "js_budget": str(validate_site.JS_BUDGET // 1024),
                                                    "n_regions_unit": EDITIONS[ed_key]["unit"], "changes": keith_changes(src)})
        (out / ed_key / "for-keith").mkdir(exist_ok=True)
        (out / ed_key / "for-keith" / "index.html").write_text(with_head_extra(render(tpl["_shell"], ctx), tpl["_shell"], ctx["head_extra"]), encoding="utf-8")

    # ---- validate
    print("…  validating")
    failures = check_built_js(out)
    failures += validate_site.validate(out, {k: d["jobs"] for k, d in data_by_ed.items()}, data_by_ed, dashboard_kpis)
    if failures:
        print(f"FAIL  {len(failures)} validation problem(s):", file=sys.stderr)
        for line in failures[:80]:
            print(f"  - {line}", file=sys.stderr)
        return 1
    css = sum(p.stat().st_size for p in (out / "css").glob("*.css"))
    js = sum(p.stat().st_size for p in (out / "js").glob("*.js"))
    pages = len(list(out.rglob("*.html")))
    (out / OK_MARKER).write_text(site_tree_sha(out) + "\n", encoding="utf-8")
    print("PASS  all checks green")
    print(f"      {sum(len(d['jobs']) for d in data_by_ed.values())} roles · {pages} pages · css {css / 1024:.1f} KB (budget {validate_site.CSS_BUDGET // 1024}) · js {js / 1024:.1f} KB (budget {validate_site.JS_BUDGET // 1024})")
    if tests:
        print(f"      node tests: {tests[0]} passed, {tests[1]} failed")
    print(f"      site: {out}")
    return 0


def main() -> int:
    here = Path(__file__).resolve().parents[3] / "deliverables" / PROJECT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=here / "src")
    parser.add_argument("--out", type=Path, default=here / "site")
    parser.add_argument("--edition", choices=["ie", "uk", "both"], default="both",
                        help="a single edition renders a partial site (cross-edition links dangle); ship 'both'")
    parser.add_argument("--data-fixture", type=Path, default=None, help="tests only: render this JSON as every edition")
    parser.add_argument("--site-base", default="", help="absolute base URL for sitemap/canonical (overrides config.json)")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="build date YYYY-MM-DD (default: the dataset's fetched date); closed roles are dropped relative to it")
    args = parser.parse_args()
    editions = ["ie", "uk"] if args.edition == "both" else [args.edition]
    return build(args.src.resolve(), args.out.resolve(), editions=editions, fixture=args.data_fixture.resolve() if args.data_fixture else None, site_base=args.site_base, today=args.today)


if __name__ == "__main__":
    raise SystemExit(main())
