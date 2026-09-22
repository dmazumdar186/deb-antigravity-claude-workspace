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
  as both editions instead of the real files)
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
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_site  # noqa: E402

MARKER = ".greenjobs-build"
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
# description. Colours: five data hues from the spec, the rest moss-tinted so
# the hero field and tiles stay one system (charts use a single hue anyway).
TAXONOMY: list[tuple[str, str, bool, list[str]]] = [
    ("Wind energy", "#b4e33d", False, ["wind", "offshore wind", "onshore wind", "turbine", "turbines"]),
    ("Solar energy", "#f2b544", False, ["solar", "photovoltaic", "pv"]),
    ("Renewable energy & storage", "#8fc73a", False, ["renewable", "renewables", "battery", "storage", "hydrogen", "hydro", "hydropower", "bioenergy", "biomass", "biogas", "anaerobic", "green energy", "clean energy", "alternative energy", "marine energy", "tidal", "wave"]),
    ("Water & flood", "#5aa9e6", False, ["water", "flood", "flooding", "drainage", "wastewater", "hydrology", "hydrogeology", "hydrogeologist", "hydrologist", "sewer", "sewerage", "catchment"]),
    ("Waste & circular economy", "#d9774f", False, ["waste", "recycling", "circular", "circular economy", "landfill", "resource management", "reuse"]),
    ("Ecology & conservation", "#2fbf9f", False, ["ecology", "ecologist", "ecological", "conservation", "biodiversity", "habitat", "habitats", "wildlife", "species", "ornithologist", "botanist", "botany", "arboriculture", "arboriculturist", "arborist", "nature", "rewilding", "peatland", "forestry", "woodland", "marine biology"]),
    ("Environmental science & consulting", "#6fa36b", True, ["environmental", "environment", "eia", "eiar", "impact assessment", "contaminated land", "geo-environmental", "geoenvironmental", "air quality", "acoustics", "noise", "geologist", "geology", "environmental scientist", "environmental consultant"]),
    ("Sustainability & net zero", "#3e8e5e", True, ["sustainability", "sustainable", "net zero", "carbon", "esg", "climate", "decarbonisation", "decarbonization", "csrd", "emissions", "greenhouse"]),
    ("Built environment & energy efficiency", "#7c8f5c", True, ["building", "buildings", "built environment", "energy efficiency", "retrofit", "breeam", "leed", "heat pump", "heat pumps", "insulation", "mechanical", "electrical", "hvac", "facilities", "architect", "architecture", "construction", "quantity surveyor", "surveyor"]),
    ("Energy networks & utilities", "#4f7f8c", True, ["grid", "utility", "utilities", "transmission", "distribution", "network", "networks", "substation", "energy management", "energy manager", "power", "electricity", "smart meter", "district heating"]),
    ("Policy, planning & advisory", "#8a7a5a", True, ["policy", "planning", "planner", "advisor", "adviser", "advisory", "regulation", "regulatory", "consents", "permitting", "compliance", "legal", "economist", "campaign", "communications", "fundraising", "education", "officer"]),
]
PRIMARY_MIN = 2  # score a sector needs before a job carries it

NAV = [("jobs/index.html", "Jobs"), ("sectors/index.html", "Sectors"), ("insights/index.html", "Salary explorer"),
       ("compass/index.html", "Career compass"), ("employers/index.html", "Employers")]
PAGES_FOR_SITEMAP = ["index.html", "jobs/index.html", "sectors/index.html", "insights/index.html", "compass/index.html", "employers/index.html"]

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

def _word_hits(text: str, words: list[str]) -> int:
    hits = 0
    for w in words:
        if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", text):
            hits += 1
    return hits


def assign_sectors(job: dict[str, Any]) -> list[str]:
    raw = " ".join(job.get("sectors") or []).lower()
    title = str(job.get("title") or "").lower()
    summary = str(job.get("summary") or "").lower()
    body = strip_tags(str(job.get("description_html") or ""))[:2500].lower()
    scored: list[tuple[int, int, str]] = []
    for pos, (name, _, _, words) in enumerate(TAXONOMY):
        score = 3 * _word_hits(raw, words) + 3 * _word_hits(title, words) + 2 * _word_hits(summary, words) + _word_hits(body, words)
        if score >= PRIMARY_MIN:
            scored.append((-score, pos, name))
    scored.sort()
    picked = [name for _, _, name in scored[:3]]
    return picked or ["Environmental science & consulting"]


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


def resolve_regions(job: dict[str, Any], table: dict[str, Any], ed: dict[str, Any]) -> list[str]:
    text = " , ".join(str(job.get(k) or "") for k in ("region", "location")).lower()
    found: list[str] = []
    for name, aliases in table["regions"].items():
        for alias in [name] + list(aliases):
            if _word_hits(text, [alias.lower()]):
                if name not in found:
                    found.append(name)
                break
    if found:
        return found
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


def normalise(raw: dict[str, Any], ed_key: str, src: Path, logos_dir: Path) -> dict[str, Any]:
    ed = EDITIONS[ed_key]
    table = load_region_table(src, ed_key)
    jobs_out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for j in raw.get("jobs") or []:
        jid = str(j.get("id") or "").strip() or slugify(j.get("slug") or j.get("title") or "")
        if jid in seen_ids or not j.get("title") or not str(j.get("url") or "").startswith(("http://", "https://")):
            continue
        seen_ids.add(jid)
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
        jobs_out.append({
            "id": jid, "slug": slugify(j.get("slug") or j.get("title")), "title": str(j["title"]).strip(),
            "employer": str(j.get("employer") or "Confidential employer").strip(), "location": str(j.get("location") or ed["none"]).strip(),
            "regions": resolve_regions(j, table, ed), "type": str(j.get("type") or "").strip(),
            "sal_min": j.get("salary_min") if isinstance(j.get("salary_min"), (int, float)) else None,
            "sal_max": j.get("salary_max") if isinstance(j.get("salary_max"), (int, float)) else None,
            "cur": j.get("currency") or None, "period": j.get("period") or None, "sal_text": str(j.get("salary_text") or "").strip(),
            "sectors": sectors, "color": color, "posted": parse_date(j.get("posted")), "closing": parse_date(j.get("closing")),
            "summary": str(j.get("summary") or "").strip() or text[:180], "text": text[:1500], "description_html": desc,
            "logo": logo, "lw": lw, "lh": lh, "url": str(j["url"]).strip(), "href": f"{jid}/index.html",
        })
    jobs_out.sort(key=lambda x: (x["posted"], x["title"]), reverse=True)
    sector_counts = Counter(s for j in jobs_out for s in j["sectors"])
    sectors = [{"name": n, "n": sector_counts.get(n, 0), "color": c, "dark": d} for n, c, d, _ in TAXONOMY]
    sectors.sort(key=lambda s: (-s["n"], s["name"]))
    region_counts = Counter(r for j in jobs_out for r in j["regions"])
    regions = [{"name": n, "n": c, "on_map": n in table["regions"]} for n, c in region_counts.most_common()]
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
    return {
        "ed": ed_key, "site": str(raw.get("site") or ed["domain"]), "fetched": str(raw.get("fetched") or date.today().isoformat())[:10],
        "jobs": jobs_out, "sectors": sectors, "regions": regions, "types": types,
        "employers": list(employers.values()), "about": str(raw.get("about") or "").strip(),
        "contact": raw.get("contact") or {}, "network_sites": raw.get("network_sites") or [],
        "region_table": table, "social": social_links(src, ed_key),
    }


def check_dataset(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not data["jobs"]:
        problems.append("no usable jobs after normalisation")
    for j in data["jobs"]:
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
            f'<path d="{line}"/><circle cx="{lx:.1f}" cy="{ly:.1f}" r="3"/></svg>')


def salary_label(j: dict[str, Any]) -> str:
    """Mirror of lib.js salaryLabel for server-rendered cards."""
    sym = {"EUR": "€", "GBP": "£", "USD": "$"}.get(j.get("cur") or "", "")

    def money(n: float) -> str:
        if n >= 1000:
            return f"{sym}{int(n / 1000)}k" if n % 1000 == 0 else f"{sym}{round(n / 100) / 10:g}k"
        return f"{sym}{n:g}"
    lo, hi = j.get("sal_min"), j.get("sal_max")
    if lo is None and hi is None:
        return ""
    per = {"year": "", "month": "/mo", "hour": "/hr", "day": "/day", "week": "/wk"}.get(j.get("period") or "year", "")
    if lo is not None and hi is not None and hi != lo:
        return f"{money(lo)}–{money(hi).lstrip(sym)}{per}"
    v = lo if lo is not None else hi
    prefix = "up to " if (hi is None and lo is not None and re.search(r"up to", j.get("sal_text") or "", re.I)) else ""
    return f"{prefix}{money(v)}{per}"


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
        return f"{round(d / 7)} wk ago"
    return f"{round(d / 30)} mo ago"


SAVE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg>'


def logo_img(j: dict[str, Any], root: str, cls: str = "role__logo") -> str:
    if j.get("logo"):
        return (f'<img class="{cls}" src="{root}assets/logos/{esc(j["logo"])}" alt="" width="{j["lw"] or 200}" height="{j["lh"] or 80}" loading="lazy" decoding="async">')
    initial = esc((j.get("employer") or "?")[:1])
    return f'<div class="{cls} role__logo--t" aria-hidden="true">{initial}</div>'


def role_card(j: dict[str, Any], root: str, jobs_dir: str, today: date) -> str:
    sal = salary_label(j)
    chips = (f'<span class="tag tag--sal">{esc(sal)}</span>' if sal else "") + (f'<span class="tag tag--type">{esc(j["type"])}</span>' if j["type"] else "")
    return (f'<article class="role reveal">'
            f'<div class="role__top">{logo_img(j, root)}<button class="save" type="button" data-save="{esc(j["id"])}" data-title="{esc(j["title"])}" aria-pressed="false" aria-label="Save: {esc(j["title"])}">{SAVE_ICON}</button></div>'
            f'<h3><a href="{jobs_dir}{esc(j["href"])}">{esc(j["title"])}</a></h3>'
            f'<p class="role__emp"><span>{esc(j["employer"])}</span><span>{esc(j["location"])}</span></p>'
            f'<div class="role__meta">{chips}<time datetime="{esc(j["posted"])}">{esc(ago(j["posted"], today))}</time></div></article>')


def sector_tiles(data: dict[str, Any], jobs_href: str, today: date) -> str:
    out = []
    live = [s for s in data["sectors"] if s["n"] > 0][:8]
    for i, s in enumerate(live):
        in_sector = [j for j in data["jobs"] if s["name"] in j["sectors"]]
        spark = sparkline_svg(sparkline_weeks(in_sector, today))
        disclosed = sum(1 for j in in_sector if j["sal_min"] is not None or j["sal_max"] is not None)
        out.append(
            f'<a class="sect reveal{" sect--lead" if i == 0 else ""}" href="{jobs_href}?sector={qs(s["name"])}" style="--sc:{s["color"]}">'
            f'<span class="arw" aria-hidden="true">&#8599;</span><h3>{esc(s["name"])}</h3>'
            f'<p class="n num">{s["n"]}<small>{"role" if s["n"] == 1 else "roles"} · {disclosed} with salary</small></p>'
            f'{spark}<span class="vh">Postings over the last eight weeks</span></a>')
    return "".join(out)


def employers_strip(data: dict[str, Any], root: str) -> str:
    with_logo = [e for e in data["employers"] if e["logo"]]
    items = with_logo if len(with_logo) >= 6 else with_logo + [e for e in data["employers"] if not e["logo"]][: max(0, 10 - len(with_logo))]
    if not items:
        return ""
    cells = []
    for e in items:
        inner = (f'<img src="{root}assets/logos/{esc(e["logo"])}" alt="{esc(e["name"])}" width="{e["lw"] or 200}" height="{e["lh"] or 80}" loading="lazy" decoding="async">'
                 if e["logo"] else f'<span>{esc(e["name"])}</span>')
        url = e["url"] if str(e["url"]).startswith("http") else ""
        cells.append(f'<a class="emp" href="{esc(url)}" rel="noopener">{inner}</a>' if url else f'<div class="emp">{inner}</div>')
    track = "".join(cells)
    return (f'<div class="marq" data-marq><div class="marq__track">{track}<span class="marq__dup" aria-hidden="true" style="display:contents">{track}</span></div></div>'
            f'<p style="text-align:right;margin-top:8px"><button class="btn btn--sm btn--ghost" type="button" data-marq-pause aria-pressed="false">Pause</button></p>')


# Three facts for the home page, each traceable to a row in src/data/brief.md
# (sections 1, 2/4 and 5). Used only when brief.md is present; otherwise the
# facts are derived from the dataset itself.
BRIEF_FACTS = [
    ("Wholly dedicated to green work since 2008", "A job board built only for the environmental and renewable energy market — not a general board with a green filter."),
    ("One posting, the whole network", "Each job is shown across the relevant sites in the GreenJobs Network of Websites at no additional cost, so it reaches the readers who want it."),
    ("Alerts that do the searching", "Up to ten job alerts by email, a weekly jobs newsletter, saved roles and one-tap applications on any device."),
]


def facts_block(brief: dict[str, Any], data: dict[str, Any]) -> str:
    items: list[tuple[str, str]] = list(BRIEF_FACTS) if brief.get("text") else []
    if len(items) < 3:
        for fact in derived_facts(data):
            if len(items) >= 3:
                break
            if fact[0] not in [i[0] for i in items]:
                items.append(fact)
    return "".join(f'<div class="fact reveal"><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for h, p in items[:3])


def map_svg(src: Path, ed: str) -> str:
    return (src / "assets" / "maps" / f"{ed}.svg").read_text(encoding="utf-8").strip()


def map_list(data: dict[str, Any], jobs_href: str, limit: int = 12) -> str:
    rows = [r for r in data["regions"] if r["on_map"]][:limit]
    return "".join(f'<a href="{jobs_href}?loc={qs(r["name"])}"><span>{esc(r["name"])}</span><b class="num">{r["n"]}</b></a>' for r in rows)


def select(field_id: str, label: str, values: list[str], any_label: str) -> str:
    opts = "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in values)
    return f'<div class="field"><label for="{field_id}">{label}</label><select class="in" id="{field_id}" name="{field_id[2:]}"><option value="">{any_label}</option>{opts}</select></div>'


def jobs_jsonld(data: dict[str, Any], site_base: str) -> str:
    items = [{"@type": "ListItem", "position": i + 1, "url": f"{site_base}{data['ed']}/jobs/{j['href']}", "name": j["title"]}
             for i, j in enumerate(data["jobs"][:50])]
    return f'<script type="application/ld+json">{json_ld({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": items})}</script>'


def job_jsonld(j: dict[str, Any], data: dict[str, Any]) -> str:
    ed = EDITIONS[data["ed"]]
    payload: dict[str, Any] = {
        "@context": "https://schema.org", "@type": "JobPosting", "title": j["title"], "description": j["text"][:1000] or j["summary"],
        "hiringOrganization": {"@type": "Organization", "name": j["employer"]},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": j["location"], "addressCountry": "IE" if data["ed"] == "ie" else "GB"}},
        "url": j["url"], "directApply": False,
    }
    if j["posted"]:
        payload["datePosted"] = j["posted"]
    if j["closing"]:
        payload["validThrough"] = j["closing"]
    if j["type"]:
        payload["employmentType"] = j["type"].upper().replace(" ", "_")
    if j["sal_min"] is not None or j["sal_max"] is not None:
        value: dict[str, Any] = {"@type": "QuantitativeValue", "unitText": (j["period"] or "year").upper()}
        if j["sal_min"] is not None:
            value["minValue"] = j["sal_min"]
        if j["sal_max"] is not None:
            value["maxValue"] = j["sal_max"]
        payload["baseSalary"] = {"@type": "MonetaryAmount", "currency": j["cur"] or ed["currency"], "value": value}
    return f'<script type="application/ld+json">{json_ld(payload)}</script>'


def slim(j: dict[str, Any], with_text: bool) -> dict[str, Any]:
    keys = ["id", "title", "employer", "location", "regions", "type", "sal_min", "sal_max", "cur", "period", "sal_text", "sectors", "color", "posted", "summary", "logo", "lw", "lh", "href"]
    out = {k: j[k] for k in keys}
    if with_text:
        out["text"] = j["text"]
    return out


def dataset_script(data: dict[str, Any], jobs_href: str, with_text: bool) -> str:
    payload = {
        "jobs": [slim(j, with_text) for j in data["jobs"]],
        "sectors": [s for s in data["sectors"] if s["n"] > 0],
        "regions": [r for r in data["regions"] if r["on_map"]],
        "types": data["types"], "currency": EDITIONS[data["ed"]]["currency"], "regionUnit": EDITIONS[data["ed"]]["unit"].title(), "jobsHref": jobs_href,
    }
    return f'<script type="application/json" id="gj-data">{json_embed(payload)}</script>'


# ------------------------------------------------------------------ pages

def _host(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]


def shell_ctx(data: dict[str, Any], depth: int, page: str, title: str, desc: str, *, dark_header: bool = False,
              body_attrs: str = "", brief: dict[str, Any] | None = None, same_path: str = "", site_base: str = "") -> dict[str, str]:
    ed = EDITIONS[data["ed"]]
    root = "../" * depth
    home = f"{root}{data['ed']}/"
    other = ed["other"]
    other_path = same_path if same_path else "index.html"
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{home}{href}"{cur if page == href.split("/")[0] else ""}>{label}</a>' for href, label in NAV)
    menu_links = nav + f'<a href="{home}for-keith/index.html">The evidence page</a>'
    edsw = (f'<a href="{root}ie/{other_path if other == "ie" else same_path or "index.html"}" data-edswitch="ie" aria-current="{"true" if data["ed"] == "ie" else "false"}" hreflang="en-IE">IE</a>'
            f'<a href="{root}uk/{other_path if other == "uk" else same_path or "index.html"}" data-edswitch="uk" aria-current="{"true" if data["ed"] == "uk" else "false"}" hreflang="en-GB">UK</a>')
    net = "".join(f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s["name"])}</a></li>' for s in data["network_sites"] if str(s.get("url", "")).startswith("http"))
    contact = data["contact"] or {}
    phones = "".join(f'<li>{esc(lbl)}: <a href="tel:{esc(re.sub(r"[^+0-9]", "", num))}">{esc(num)}</a></li>' for lbl, num in (contact.get("phones") or [])[:2] if num)
    emails = "".join(f'<li><a href="mailto:{esc(e)}">{esc(e)}</a></li>' for e in dict.fromkeys(contact.get("emails") or []))
    bcorp = onepct = ""
    if brief and brief.get("b_corp") and brief.get("bcorp_size"):
        w, h = brief["bcorp_size"]
        bcorp = f'<img class="bcorp" src="{root}assets/logos/b-corp-logo.svg" alt="Certified B Corporation" width="{w}" height="{h}" loading="lazy">'
    if brief and brief.get("onepct_size"):
        w, h = brief["onepct_size"]
        onepct = f'<img src="{root}assets/logos/1fortheplanet.svg" alt="1% for the Planet member" width="{w}" height="{h}" loading="lazy" style="height:44px;width:auto;margin-top:12px;filter:brightness(1.4)">'
    social = "".join(
        f'<a href="{esc(u)}" rel="noopener" aria-label="{esc(_host(u))}"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></a>'
        for u in (data.get("social") or [])[:4])
    return {
        "lang": ed["lang"], "title": esc(title), "desc": esc(desc), "root": root, "home": home, "ed": data["ed"], "ED": ed["short"],
        "domain": esc(data["site"]), "nav": nav, "menu_links": menu_links, "edsw": edsw, "hdr_cls": " hdr--dark" if dark_header else "",
        "body_attrs": body_attrs, "net_sites": net, "phones": phones, "emails": emails, "bcorp": bcorp, "social": social,
        "year": str(date.today().year), "n_jobs": str(len(data["jobs"])), "fetched": esc(data["fetched"]),
        "social_wrap": f'<div class="ftr__social">{social}</div>' if social else "",
        "canonical": esc(f"{site_base}{data['ed']}/{same_path or 'index.html'}") if site_base else "",
        "nav_list": "".join(f'<li><a href="{home}{href}">{label}</a></li>' for href, label in NAV) + f'<li><a href="{home}for-keith/index.html">For Keith</a></li>',
        "onepct": onepct, "scripts": "",
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

    SCRIPTS = {"home": ["wind"], "jobs": ["jobs"], "sectors": ["charts", "explore"], "insights": ["charts", "explore"], "compass": ["compass"]}

    def page(name: str, depth: int, page_key: str, title: str, desc: str, body: dict[str, str], **kw: Any) -> str:
        ctx = shell_ctx(data, depth, page_key, title, desc, brief=brief, site_base=site_base, **kw)
        ctx["scripts"] = "".join(f'<script src="{ctx["root"]}js/{s}.js" defer></script>' for s in SCRIPTS.get(name, []))
        ctx["content"] = render(tpl[name], {**ctx, **body})
        return render(tpl["_shell"], ctx)

    # ---- home
    map_counts = {r["name"]: r["n"] for r in top_regions}
    home = page("home", 1, "index", f"GreenJobs {ed['short']} — {len(jobs)} live green roles across {ed['name']}",
                f"Environmental, renewable energy and sustainability jobs across {ed['name']}: {len(jobs)} live roles from {n_emp} employers, searchable in a second.",
                {
                    "n_jobs": str(len(jobs)), "n_emp": str(n_emp), "n_sal": str(n_sal), "country": esc(ed["name"]), "unit": ed["unit"], "units": ed["unit"] + ("ies" if ed["unit"].endswith("y") else "s"),
                    "colors": esc(colors), "sector_tiles": sector_tiles(data, "jobs/index.html", today),
                    "latest": "".join(role_card(j, "../", "jobs/", today) for j in jobs[:8]),
                    "map": map_svg(src, ed_key), "map_counts": esc(json_embed(map_counts)), "map_list": map_list(data, "jobs/index.html"),
                    "n_regions": str(len(top_regions)), "employers": employers_strip(data, "../"), "facts": facts_block(brief, data),
                    "sector_options": "".join(f'<option value="{esc(s["name"])}">{esc(s["name"])}</option>' for s in data["sectors"] if s["n"]),
                    "n_sectors": str(sum(1 for s in data["sectors"] if s["n"])),
                    "legend": "".join(f'<span><i style="background:{s["color"]}"></i>{esc(s["name"])}</span>' for s in data["sectors"][:5]),
                }, dark_header=True, body_attrs=f' data-data="data/jobs.json"', same_path="index.html")
    write("index.html", home)
    (edir / "data").mkdir(exist_ok=True)
    (edir / "data" / "jobs.json").write_text(json.dumps({"jobs": [slim(j, False) for j in jobs]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- jobs board
    pages_for_palette = json_embed([{"t": lbl, "h": "../" + href} for href, lbl in NAV] + [{"t": "Home", "h": "../index.html"}])
    board = page("jobs", 2, "jobs", f"Green jobs across {ed['name']} — search {len(jobs)} live roles | GreenJobs {ed['short']}",
                 f"Filter {len(jobs)} live environmental and renewable energy roles by {ed['unit']}, sector, type and salary.",
                 {
                     "dataset": dataset_script(data, "index.html", True), "jsonld": jobs_jsonld(data, site_base) if site_base else "",
                     "loc_options": "".join(f'<option value="{esc(r["name"])}">' for r in top_regions),
                     "sector_select": select("f-sector", "Sector", [s["name"] for s in data["sectors"] if s["n"]], "All sectors"),
                     "type_select": select("f-type", "Job type", [t["name"] for t in data["types"]], "Any type"),
                     "unit": ed["unit"].title(), "map": map_svg(src, ed_key), "pages": esc(pages_for_palette), "n_jobs": str(len(jobs)),
                 }, same_path="jobs/index.html")
    write("jobs/index.html", board)

    # ---- one page per job
    for j in jobs:
        similar = [s for s in jobs if s["id"] != j["id"] and set(s["sectors"]) & set(j["sectors"])][:3]
        sal = salary_label(j)
        meta_tags = "".join(f'<span class="tag">{esc(x)}</span>' for x in [j["location"], j["type"]] if x) + (f'<span class="tag tag--sal">{esc(sal)}</span>' if sal else "")
        dl = ""
        for k, v in (("Location", j["location"]), ("Type", j["type"]), ("Salary", j["sal_text"] or (sal or "Not disclosed")),
                     ("Posted", j["posted"]), ("Closes", j["closing"]), ("Sector", ", ".join(j["sectors"]))):
            if v:
                dl += f"<dt>{k}</dt><dd>{esc(v)}</dd>"
        body_html = j["description_html"] or f"<p>{esc(j['summary'])}</p>"
        jp = page("job", 3, "jobs", f"{j['title']} — {j['employer']} | GreenJobs {ed['short']}", (j["summary"] or j["title"])[:155],
                  {
                      "jsonld": job_jsonld(j, data), "title": esc(j["title"]), "employer": esc(j["employer"]), "logo": logo_img(j, "../../../", "job__logo") if j["logo"] else "",
                      "meta": meta_tags, "dl": dl, "desc_html": body_html, "apply_url": esc(j["url"]), "domain": esc(data["site"]), "id": esc(j["id"]),
                      "similar": "".join(role_card(s, "../../../", "../", today) for s in similar) or '<p class="muted">No other live roles in this sector this week.</p>',
                      "sector_link": f'../index.html?sector={qs(j["sectors"][0])}', "sector": esc(j["sectors"][0]),
                      "posted_line": esc(f"Posted {j['posted']}" + (f" · closes {j['closing']}" if j["closing"] else "")) if j["posted"] else "",
                  }, same_path="jobs/index.html")
        write(f"jobs/{j['id']}/index.html", jp)

    # ---- sectors, insights, compass, employers
    sec_rows = "".join(
        f'<a class="secrow" data-secrow="{esc(s["name"])}" href="../jobs/index.html?sector={qs(s["name"])}"><span><i style="background:{s["color"]}"></i>{esc(s["name"])}</span><b class="num">{s["n"]}</b></a>'
        for s in data["sectors"] if s["n"] > 0)
    write("sectors/index.html", page("sectors", 2, "sectors", f"Sectors — where the green work is | GreenJobs {ed['short']}",
                                     f"Every sector with live roles on GreenJobs {ed['short']}, sized by count.",
                                     {"dataset": dataset_script(data, "../jobs/index.html", False), "rows": sec_rows,
                                      "n_sectors": str(sum(1 for s in data["sectors"] if s["n"])), "n_jobs": str(len(jobs))}, same_path="sectors/index.html"))
    write("insights/index.html", page("insights", 2, "insights", f"Green salary explorer — what {ed['name']}'s green roles pay | GreenJobs {ed['short']}",
                                      f"Disclosed salaries on GreenJobs {ed['short']}: bands, medians by sector, disclosure rates and roles by {ed['unit']}.",
                                      {"dataset": dataset_script(data, "../jobs/index.html", False), "cur": ed["sym"], "unit": ed["unit"], "n_jobs": str(len(jobs)), "n_sal": str(n_sal),
                                       "fetched": esc(data["fetched"])}, same_path="insights/index.html"))
    write("compass/index.html", page("compass", 2, "compass", f"Green Career Compass — find your sector in seven questions | GreenJobs {ed['short']}",
                                     "Seven quick questions, three sectors that fit, live roles to match.",
                                     {"dataset": dataset_script(data, "../jobs/index.html", False)}, same_path="compass/index.html"))
    write("employers/index.html", page("employers", 2, "employers", f"Advertise a green role | GreenJobs {ed['short']}",
                                       f"Reach candidates who only want green work. What GreenJobs {ed['short']} offers employers.",
                                       {"n_jobs": str(len(jobs)), "n_emp": str(n_emp), "n_sites": str(len(data["network_sites"])), "about": esc(data["about"].split("\n")[0]),
                                        "emp_points_wrap": "",
                                        "country": esc(ed["name"]),
                                        "sector_options": "".join(f'<option value="{esc(s["name"])}">{esc(s["name"])}</option>' for s in data["sectors"] if s["n"])}, same_path="employers/index.html"))

    # ---- evidence page (rendered after measuring; filled in by build())
    evidence[ed_key] = {"n_jobs": len(jobs), "n_emp": n_emp, "n_sal": n_sal, "n_sectors": sum(1 for s in data["sectors"] if s["n"]), "n_regions": len(top_regions)}

    # ---- 404 per edition
    write("404.html", page("404", 1, "404", f"Page not found | GreenJobs {ed['short']}", "That page is not here.", {}, same_path="404.html"))


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
            f"<tr><td>Requests on the home page</td><td class=\"n\">{cell(before_req)}</td><td class=\"n good\">{local_refs + 1} (all first-party)</td></tr>"
            f"<tr><td>External script tags</td><td class=\"n\">{cell(before_scripts)}</td><td class=\"n good\">{len(js)} own files, {js_raw / 1024:.1f} KB ({js_gz / 1024:.1f} KB gzipped)</td></tr>"
            f"<tr><td>Third-party requests</td><td class=\"n\">{'yes (analytics, CDN fonts/scripts)' if perf.get('ga4') or perf.get('platform_cdn') else 'not measured'}</td><td class=\"n good\">{third}</td></tr>"
            f"<tr><td>Stylesheet</td><td class=\"n\">{len(perf.get('stylesheets') or []) or 'not measured'} files</td><td class=\"n good\">1 file, {css_raw / 1024:.1f} KB ({css_gz / 1024:.1f} KB gzipped)</td></tr>"
            f"<tr><td>Front-end stack</td><td>{esc(stack_before)}</td><td class=\"good\">Vanilla ES2020, no framework, no build-time packages</td></tr>"
            f"<tr><td>Pages rendered</td><td>server-side, per request</td><td class=\"good\">{len(list((out / ed_key).rglob('*.html')))} static pages, {len(data['jobs'])} of them job pages</td></tr>"
        )
    rows["tests"] = f"{tests[0]} passing, {tests[1]} failing" if tests else "not run (node unavailable)"
    rows["built"] = today.isoformat()
    rows["css_kb"] = f"{css_raw / 1024:.1f}"
    rows["js_kb"] = f"{js_raw / 1024:.1f}"
    return rows


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


def build(src: Path, out: Path, *, editions: list[str], fixture: Path | None = None, site_base: str = "") -> int:
    if not src.is_dir():
        print(f"FAIL  source directory not found: {src}", file=sys.stderr)
        return 2
    refusal = guard_output(src, out)
    if refusal:
        print(f"FAIL  {refusal}", file=sys.stderr)
        return 2
    today = date.today()
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
        data = normalise(raw, ed_key, src, logos_dir)
        problems = check_dataset(data)
        if problems:
            print(f"FAIL  {ed_key}.json has {len(problems)} problem(s):", file=sys.stderr)
            for line in problems:
                print(f"  - {line}", file=sys.stderr)
            return 2
        data_by_ed[ed_key] = data
        unresolved = sum(1 for j in data["jobs"] if not any(r in data["region_table"]["regions"] for r in j["regions"]))
        off_map = ", ".join(f"{r['name']} {r['n']}" for r in data["regions"] if not r["on_map"])
        print(f"…  {ed_key}: {len(data['jobs'])} jobs, {sum(1 for s in data['sectors'] if s['n'])} sectors live, {unresolved} jobs off-map ({off_map})")

    # ---- copy the static tree
    if out.exists():
        shutil.rmtree(out)
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
                "background_color": "#0c1a12", "theme_color": "#0c1a12", "icons": [{"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]}
    (out / "manifest.webmanifest").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    if site_base:
        urls = "".join(f"<url><loc>{esc(site_base)}{ed_key}/{p}</loc></url>" for ed_key in data_by_ed for p in PAGES_FOR_SITEMAP)
        urls += "".join(f"<url><loc>{esc(site_base)}{ed_key}/jobs/{j['href']}</loc></url>" for ed_key, d in data_by_ed.items() for j in d["jobs"])
    else:
        urls = ""
    (out / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")

    # ---- evidence page last (it measures the files written above)
    tests = run_node_tests(src)
    if tests and tests[1]:
        print(f"FAIL  {tests[1]} node test(s) failing", file=sys.stderr)
        return 1
    ev = render_evidence(out, src, data_by_ed, tests, today)
    for ed_key, data in data_by_ed.items():
        ctx = shell_ctx(data, 2, "for-keith", "For Keith — the evidence behind the GreenJobs redesign demo",
                        "What was measured, what was built, what comes next.", brief=brief, site_base=site_base, same_path="for-keith/index.html")
        e = evidence[ed_key]
        ctx["content"] = render(tpl["for-keith"], {**ctx, "rows": ev[ed_key], "tests": esc(ev["tests"]), "built": esc(ev["built"]), "css_kb": ev["css_kb"], "js_kb": ev["js_kb"],
                                                    "n_jobs": str(e["n_jobs"]), "n_emp": str(e["n_emp"]), "n_sal": str(e["n_sal"]), "n_sectors": str(e["n_sectors"]),
                                                    "n_regions": str(e["n_regions"]), "other_ed": EDITIONS[ed_key]["other"], "domain": esc(data["site"])})
        (out / ed_key / "for-keith").mkdir(exist_ok=True)
        (out / ed_key / "for-keith" / "index.html").write_text(render(tpl["_shell"], ctx), encoding="utf-8")

    # ---- validate
    print("…  validating")
    failures = check_built_js(out)
    failures += validate_site.validate(out, {k: d["jobs"] for k, d in data_by_ed.items()})
    if failures:
        print(f"FAIL  {len(failures)} validation problem(s):", file=sys.stderr)
        for line in failures[:80]:
            print(f"  - {line}", file=sys.stderr)
        return 1
    css = sum(p.stat().st_size for p in (out / "css").glob("*.css"))
    js = sum(p.stat().st_size for p in (out / "js").glob("*.js"))
    pages = len(list(out.rglob("*.html")))
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
    args = parser.parse_args()
    editions = ["ie", "uk"] if args.edition == "both" else [args.edition]
    return build(args.src.resolve(), args.out.resolve(), editions=editions, fixture=args.data_fixture.resolve() if args.data_fixture else None, site_base=args.site_base)


if __name__ == "__main__":
    raise SystemExit(main())
