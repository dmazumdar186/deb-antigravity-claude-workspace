"""Validate a rendered GreenJobs static site before it is called shippable.

description: Structural, accessibility and honesty checks over the built site:
  relative paths only, every local reference resolves and stays inside the
  site, every <img> has alt + width + height, JSON-LD parses, one <h1> and one
  <title> per page, noindex on every page, every form control labelled, the
  job-page count equals the dataset length per edition, no forbidden
  vocabulary on public pages (for-keith/ exempt; employer-authored description
  blocks exempt), no third-party requests, fonts self-hosted and preloaded,
  CSS/JS weight budgets (80 KB / 125 KB), hero footage per edition
  (<ed>.mp4, <ed>-m.mp4, poster; HERO_BUDGET_FILE / HERO_BUDGET_TOTAL),
  canonical + hreflang links absolute with an x-default and every alternate
  target present in the other edition, every landing page carrying at least
  one role card, dashboard "wired at launch" tiles free of digits outside
  their labelled targets, and the dashboard's live tiles equal to a fresh
  dashboard_kpis() recomputation. Absolute hrefs are allowed only on
  <link rel=canonical|alternate> (no request is made for those).
inputs: a built site directory, {edition: [normalised job records]},
  optionally {edition: normalised dataset} and the dashboard_kpis callable
outputs: a list of failure strings (empty means the build passes)
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

FORBIDDEN = [
    (r"\bAI\b", "AI"),
    (r"\bA\.I\.", "A.I."),
    (r"\bClaude\b", "Claude"),
    (r"\bLLM\b", "LLM"),
    (r"\bartificial intelligence\b", "artificial intelligence"),
    (r"\blorem\b", "lorem"),
    (r"\bTODO\b", "TODO"),
    (r"\bHidden Depth\b", "Hidden Depth"),
    (r"\bWordPress\b", "WordPress"),
    (r"\bplaceholder text\b", "placeholder text"),
    (r"\bXXX\b", "XXX"),
]
EXEMPT_RE = re.compile(r"^(?:ie|uk)/for-keith/index\.html$")
CSS_BUDGET = 80 * 1024
JS_BUDGET = 125 * 1024
HERO_BUDGET_FILE = 2 * 1024 * 1024  # per hero file (mp4, portrait mp4, poster)
HERO_BUDGET_TOTAL = 6 * 1024 * 1024  # every hero file together
HERO_REQUIRED = ("{ed}.mp4", "{ed}-m.mp4")  # plus a poster: {ed}-poster.webp|jpg
EDITIONS = ("ie", "uk")
# Location classes an edition may show (mirrors build_site.EDITION_INCLUDES): the IE board shows every class
# with a label (Keith B4: users exclude UK roles with the toggle); the UK board excludes Ireland-only and intl.
EDITION_LOC = {"ie": {"ie", "uk", "ni", "remote", "cross", "intl", "unspecified"}, "uk": {"uk", "ni", "remote", "cross", "unspecified"}}
DANGEROUS_SCHEMES = ("javascript:", "data:", "vbscript:", "file:")
THIRD_PARTY_TAGS = ("link", "script", "img", "iframe", "source", "video", "audio", "object", "embed")


class _Doc(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[dict[str, str]] = []
        self.refs: list[tuple[str, str, str]] = []  # (tag, attr, value)
        self.h1 = 0
        self.titles = 0
        self.title_text = ""
        self._in_title = False
        self.robots = False
        self.lang = ""
        self.jsonld: list[str] = []
        self._in_ld = False
        self.labels: set[str] = set()
        self.field_ids: list[tuple[str, str]] = []
        self.aria_labelled_fields: set[str] = set()
        self.dataset_blocks: list[str] = []
        self._in_dataset = False
        self.external_hrefs: list[str] = []
        self.seo_links: list[tuple[str, str, str]] = []  # (rel, hreflang, href)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self.titles += 1
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and a.get("name", "").lower() == "robots":
            self.robots = "noindex" in a.get("content", "").lower()
        elif tag == "img":
            self.images.append(a)
        if tag == "script":
            if a.get("type") == "application/ld+json":
                self._in_ld = True
                self.jsonld.append("")
            elif a.get("id") == "gj-data":
                self._in_dataset = True
                self.dataset_blocks.append("")
        for attr in ("href", "src"):
            if attr in a:
                if tag == "link" and a.get("rel", "").lower() in ("canonical", "alternate"):
                    self.seo_links.append((a.get("rel", "").lower(), a.get("hreflang", ""), a[attr]))
                    continue  # SEO links: no request is made, an absolute URL is required (checked below)
                self.refs.append((tag, attr, a[attr]))
                if tag == "a" and a[attr].startswith("http"):
                    self.external_hrefs.append(a[attr])
        if tag == "label" and a.get("for"):
            self.labels.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit", "button", "checkbox"):
            self.field_ids.append((tag, a.get("id", "")))
            if a.get("aria-label"):
                self.aria_labelled_fields.add(a.get("id", ""))
        if tag == "input" and a.get("type") == "checkbox":
            self.field_ids.append((tag, a.get("id", "")))

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_ld = False
            self._in_dataset = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_ld and self.jsonld:
            self.jsonld[-1] += data
        if self._in_dataset and self.dataset_blocks:
            self.dataset_blocks[-1] += data
        if self._in_title:
            self.title_text += data


def _is_local(value: str) -> bool:
    low = value.strip().lower()
    if not low or low.startswith(("#", "mailto:", "tel:")):
        return False
    return not re.match(r"^(?:https?:)?//", low)


def _visible_text(markup: str) -> str:
    body = re.sub(r"<!--\s*src:start\s*-->.*?<!--\s*src:end\s*-->", " ", markup, flags=re.S)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    # attribute values (alt, aria-label, placeholder) are visible to someone
    attrs = " ".join(re.findall(r'(?:alt|aria-label|placeholder|title)="([^"]*)"', body))
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body + " " + attrs)


def _inside(child: Path, parent: Path) -> bool:
    try:
        return child.resolve().is_relative_to(parent.resolve())
    except (OSError, ValueError):
        return False


def _check_labels(doc: _Doc, rel: str, fails: list[str]) -> None:
    # A <label> wrapping the control (the .check pattern) counts: detect by id
    # presence inside a label-for set OR the wrapping pattern in raw text later.
    for tag, field_id in doc.field_ids:
        if not field_id:
            fails.append(f"{rel}: a <{tag}> form control has no id, so it cannot be labelled")
        elif field_id not in doc.labels and field_id not in doc.aria_labelled_fields and field_id not in doc.wrapped:
            fails.append(f"{rel}: <{tag} id=\"{field_id}\"> has no <label for> and no aria-label")


def _check_seo_links(doc: _Doc, rel: str, site: Path, fails: list[str]) -> None:
    """Canonical/alternate links: absolute https URLs, one x-default whenever
    an alternate is present, and every alternate that points into this site
    must resolve to a built page (the same path in the other edition)."""
    alternates = [(hl, href) for r, hl, href in doc.seo_links if r == "alternate"]
    for r, hl, href in doc.seo_links:
        if not href.startswith("https://"):
            fails.append(f"{rel}: <link rel={r}{' hreflang=' + hl if hl else ''}> href must be absolute (got {href!r})")
    if alternates:
        langs = [hl for hl, _ in alternates]
        if "x-default" not in langs:
            fails.append(f"{rel}: hreflang alternates without an x-default")
        if len(langs) != len(set(langs)):
            fails.append(f"{rel}: duplicate hreflang values {langs}")
        for hl, href in alternates:
            m = re.search(r"https://[^/]+/(?:(ie|uk)/)(.*)$", href)
            if not m:
                continue
            target = site / m.group(1) / (m.group(2) or "index.html")
            if not target.is_file():
                fails.append(f"{rel}: hreflang={hl} points at {href}, which is not a built page")


def _check_hero(site: Path, fails: list[str]) -> None:
    hero = site / "assets" / "hero"
    total = 0
    for ed in EDITIONS:
        if not (site / ed).is_dir():
            continue
        for pat in HERO_REQUIRED:
            f = hero / pat.format(ed=ed)
            if not f.is_file():
                fails.append(f"assets/hero/{f.name} is missing (required per edition)")
        if not any((hero / f"{ed}-poster.{ext}").is_file() for ext in ("webp", "jpg")):
            fails.append(f"assets/hero/{ed}-poster.webp|jpg is missing (required per edition)")
    for f in sorted(hero.glob("*")) if hero.is_dir() else []:
        size = f.stat().st_size
        total += size
        if size > HERO_BUDGET_FILE:
            fails.append(f"assets/hero/{f.name}: {size} bytes exceeds the per-file hero budget {HERO_BUDGET_FILE}")
    if total > HERO_BUDGET_TOTAL:
        fails.append(f"hero footage: {total} bytes exceeds the total hero budget {HERO_BUDGET_TOTAL}")


def _check_dashboard(raw: str, rel: str, data: dict[str, Any] | None, kpis: Any, fails: list[str]) -> None:
    """Wired-at-launch tiles show no live number (digits only inside the
    labelled target or a <code> event name); the live tiles and the embedded
    gj-dash block equal a fresh dashboard_kpis() recomputation."""
    for tile in re.findall(r'<div class="kpi kpi--wired">(.*?)</div>', raw, re.S):
        body = re.sub(r'<span class="kpi__t">.*?</span>', "", tile, flags=re.S)
        body = re.sub(r"<code>[^<]*</code>", "", body)
        body = re.sub(r'<span class="kpi__l">[^<]*</span>', "", body)  # the tile's name may carry a window ("(30d)"); its value and description may not
        body = re.sub(r"\b\d+[- ]?(?:d|days?|weeks?|months?|h|hours?)\b", " ", body)  # a window definition ("rolling 30 days") is not a live figure
        if re.search(r"\d", body):
            fails.append(f"{rel}: a wired-at-launch tile carries a digit outside its labelled target: {re.sub(r'<[^>]+>', ' ', body).strip()[:80]!r}")
            break
    if data is None or kpis is None:
        return
    m = re.search(r'<script type="application/json" id="gj-dash">(.*?)</script>', raw, re.S)
    if not m:
        fails.append(f"{rel}: no embedded gj-dash KPI block")
        return
    try:
        embedded = json.loads(m.group(1))
    except ValueError as exc:
        fails.append(f"{rel}: gj-dash block does not parse ({exc})")
        return
    fresh = json.loads(json.dumps(kpis(data)))
    if embedded != fresh:
        diff = [k for k in set(embedded) | set(fresh) if embedded.get(k) != fresh.get(k)]
        fails.append(f"{rel}: embedded KPIs differ from a fresh dashboard_kpis() recomputation on {sorted(diff)}")
    allowed = set()
    for k, v in fresh.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            allowed |= {str(v), f"{v}%", f"{v:,}"}
    allowed |= {"n/a", "—"}
    for val in re.findall(r'<div class="kpi(?: kpi--flag)?"><span class="kpi__l">[^<]*</span><b class="kpi__v num">([^<]*)</b>', raw):
        bare = re.sub(r"^[€£$]", "", val.strip())
        if bare not in allowed:
            fails.append(f"{rel}: live tile value {val!r} is not a value of dashboard_kpis(data)")


def validate(site: Path, jobs_by_edition: dict[str, list[dict[str, Any]]], data_by_edition: dict[str, dict[str, Any]] | None = None, dashboard_kpis: Any = None) -> list[str]:
    """Return a list of human-readable failures. Empty list means the build passes."""
    fails: list[str] = []
    pages = sorted(p for p in site.rglob("*.html"))
    if not pages:
        return [f"no HTML pages found under {site}"]
    job_pages: dict[str, int] = {}
    for page in pages:
        rel = page.relative_to(site).as_posix()
        raw = page.read_text(encoding="utf-8")
        doc = _Doc()
        doc.wrapped = set(re.findall(r"<label[^>]*>\s*<input[^>]*\bid=\"([^\"]+)\"", raw))  # type: ignore[attr-defined]
        doc.feed(raw)
        if re.search(r"\{\{[a-zA-Z0-9_:]+\}\}", raw):
            fails.append(f"{rel}: unrendered template key {re.search(r'{{[a-zA-Z0-9_:]+}}', raw).group(0)}")
        if not doc.lang:
            fails.append(f"{rel}: <html> has no lang attribute")
        if doc.titles != 1 or not doc.title_text.strip():
            fails.append(f"{rel}: expected exactly one non-empty <title>, found {doc.titles}")
        if doc.h1 != 1:
            fails.append(f"{rel}: expected exactly one <h1>, found {doc.h1}")
        if not doc.robots:
            fails.append(f"{rel}: missing <meta name=robots content=noindex,...>")
        for tag, attr, value in doc.refs:
            stripped = value.strip()
            if not stripped:
                fails.append(f"{rel}: empty {attr} attribute on <{tag}>")
                continue
            if stripped.lower().startswith(DANGEROUS_SCHEMES):
                fails.append(f"{rel}: {attr}=\"{stripped[:60]}\" uses a forbidden scheme")
                continue
            if stripped.startswith("/"):
                fails.append(f"{rel}: absolute path {attr}=\"{stripped}\" (relative paths only)")
                continue
            if not _is_local(stripped):
                if tag in THIRD_PARTY_TAGS:
                    fails.append(f"{rel}: third-party request <{tag} {attr}=\"{stripped[:80]}\">")
                continue
            path_part = stripped.split("#")[0].split("?")[0]
            target = page.resolve() if not path_part else (page.parent / path_part).resolve()
            if not _inside(target, site):
                fails.append(f"{rel}: {attr}=\"{stripped}\" escapes the site root")
            elif not target.exists():
                fails.append(f"{rel}: {attr}=\"{stripped}\" does not resolve to a file")
        for img in doc.images:
            src = img.get("src", "?")
            if "alt" not in img:
                fails.append(f"{rel}: <img src=\"{src}\"> has no alt attribute")
            if not img.get("width") or not img.get("height"):
                fails.append(f"{rel}: <img src=\"{src}\"> is missing width/height")
        for i, block in enumerate(doc.jsonld):
            try:
                parsed = json.loads(block)
            except (json.JSONDecodeError, ValueError) as exc:
                fails.append(f"{rel}: JSON-LD block {i} does not parse ({exc})")
                continue
            if not parsed:
                fails.append(f"{rel}: JSON-LD block {i} is empty")
        for i, block in enumerate(doc.dataset_blocks):
            try:
                json.loads(block)
            except (json.JSONDecodeError, ValueError) as exc:
                fails.append(f"{rel}: embedded dataset block {i} does not parse ({exc})")
        _check_labels(doc, rel, fails)
        if not EXEMPT_RE.match(rel):
            text = html.unescape(_visible_text(raw))
            for pattern, word in FORBIDDEN:
                if re.search(pattern, text):
                    fails.append(f"{rel}: forbidden word on a public page: {word!r}")
        if "fonts.googleapis.com" in raw or "fonts.gstatic.com" in raw:
            fails.append(f"{rel}: requests fonts from Google; they are self-hosted")
        m = re.match(r"^(ie|uk)/jobs/([^/]+)/index\.html$", rel)
        if m:
            job_pages[m.group(1)] = job_pages.get(m.group(1), 0) + 1
            if 'rel="noopener"' not in raw or "Apply on" not in raw:
                fails.append(f"{rel}: job page has no apply link")
            for block in doc.jsonld:
                try:
                    ld = json.loads(block)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(ld, dict) and ld.get("@type") == "JobPosting":
                    sal = ld.get("baseSalary")
                    if sal is not None:
                        val = sal.get("value") or {}
                        if sal.get("currency") not in ("EUR", "GBP", "USD") or not any(isinstance(val.get(k), (int, float)) for k in ("minValue", "maxValue", "value")):
                            fails.append(f"{rel}: JobPosting baseSalary must carry a currency code and a numeric value")
                    if "validThrough" in ld and not re.match(r"^\d{4}-\d{2}-\d{2}", str(ld["validThrough"])):
                        fails.append(f"{rel}: JobPosting validThrough is not a date")
        if re.match(r"^(ie|uk)/(?!for-keith/)[^/]+/index\.html$", rel) or re.match(r"^(ie|uk)/index\.html$", rel) or re.match(r"^(ie|uk)/guides/", rel):
            if 'rel="canonical"' not in raw:
                fails.append(f"{rel}: no canonical link")
        if re.match(r"^(ie|uk)/index\.html$", rel) and "data-landscape" not in raw:
            fails.append(f"{rel}: home page has no hero landscape host")
        _check_seo_links(doc, rel, site, fails)
        if 'id="h-landing-roles"' in raw and not re.search(r'<article class="role\b', raw):
            fails.append(f"{rel}: landing page carries no role card (a landing page with zero roles must not be built)")
        dm = re.match(r"^(ie|uk)/dashboard/index\.html$", rel)
        if dm:
            _check_dashboard(raw, rel, (data_by_edition or {}).get(dm.group(1)), dashboard_kpis, fails)
        for vid in re.finditer(r"<video\b[^>]*>(.*?)</video>", raw, re.S):
            # A referenced hero video (drop-in footage) must ship with the site, poster included.
            poster = re.search(r'\bposter="([^"]+)"', vid.group(0))
            srcs = re.findall(r'<source\b[^>]*\bsrc="([^"]+)"', vid.group(1)) + re.findall(r'<video\b[^>]*\bsrc="([^"]+)"', vid.group(0))
            if not srcs:
                fails.append(f"{rel}: <video> has no source")
            for ref in srcs + ([poster.group(1)] if poster else []):
                if not _is_local(ref) or ref.startswith("/"):
                    fails.append(f"{rel}: hero video reference {ref!r} is not a relative local path")
                elif not (page.parent / ref.split("?")[0]).resolve().exists():
                    fails.append(f"{rel}: hero video reference {ref!r} does not exist in the built site")
            if 'muted' not in vid.group(0) or 'playsinline' not in vid.group(0):
                fails.append(f"{rel}: hero <video> must be muted and playsinline")
        hm = re.match(r"^(ie|uk)/index\.html$", rel)
        if hm and 'data-strip="hiring"' in raw:
            # Every logo under "Employers hiring now" must belong to an employer with a live role in this edition.
            live = {html.unescape(j["employer"]) for j in jobs_by_edition.get(hm.group(1), [])}
            strip = re.search(r'<div class="marq" data-marq data-strip="hiring">(.*?)</div></div>', raw, re.S)
            names = re.findall(r'<(?:img[^>]*\balt="([^"]*)"|span>([^<]*)</span>)', strip.group(1)) if strip else []
            for alt, span in names:
                name = html.unescape(alt or span)
                if name and name not in live:
                    fails.append(f"{rel}: '{name}' is shown under \"Employers hiring now\" but has no live role in this edition")
        if hm and "countyies" in raw:
            fails.append(f"{rel}: 'countyies' pluralisation bug")
        em = re.match(r"^(ie|uk)/", rel)
        if em and not EXEMPT_RE.match(rel):
            # Edition rule: no role card (location badge) whose class is outside this edition's set.
            outside = sorted({lc for lc in re.findall(r'<span class="tag tag--loc" data-loc="([^"]*)"', raw) if lc not in EDITION_LOC[em.group(1)]})
            if outside:
                fails.append(f"{rel}: role card with location class {', '.join(outside)} on the {em.group(1)} edition (outside its inclusion rule)")

    for ed, jobs in jobs_by_edition.items():
        if job_pages.get(ed, 0) != len(jobs):
            fails.append(f"{ed}: rendered {job_pages.get(ed, 0)} job pages, dataset has {len(jobs)}")
        board = site / ed / "jobs" / "index.html"
        if board.exists():
            m = re.search(r'<script type="application/json" id="gj-data">(.*?)</script>', board.read_text(encoding="utf-8"), re.S)
            embedded = json.loads(m.group(1)) if m else {"jobs": []}
            if len(embedded["jobs"]) != len(jobs):
                fails.append(f"{ed}/jobs/index.html: embedded dataset has {len(embedded['jobs'])} jobs, expected {len(jobs)}")
            hrefs = {j["href"] for j in embedded["jobs"]}
            for href in sorted(hrefs):
                if not (board.parent / href).exists():
                    fails.append(f"{ed}/jobs/index.html: dataset href {href} has no page")
                    break
    css = sum(p.stat().st_size for p in site.rglob("*.css"))
    js = sum(p.stat().st_size for p in site.rglob("*.js"))
    if css > CSS_BUDGET:
        fails.append(f"CSS budget: {css} bytes exceeds {CSS_BUDGET}")
    if js > JS_BUDGET:
        fails.append(f"JS budget: {js} bytes exceeds {JS_BUDGET}")
    if list(site.rglob("*.test.js")):
        fails.append("a *.test.js file was shipped into the site (tests stay in src)")
    _check_hero(site, fails)
    for required in ("robots.txt", "manifest.webmanifest", "sitemap.xml", "index.html", "404.html"):
        if not (site / required).exists():
            fails.append(f"{required} is missing")
    robots = (site / "robots.txt").read_text(encoding="utf-8") if (site / "robots.txt").exists() else ""
    if "Disallow: /" not in robots:
        fails.append("robots.txt does not disallow crawling (the demo is noindex)")
    font_dir = site / "assets" / "fonts"
    fonts = sorted(font_dir.glob("*.woff2")) if font_dir.is_dir() else []
    if len(fonts) < 2:
        fails.append(f"expected two self-hosted woff2 files in {font_dir}, found {len(fonts)}")
    for page in pages:
        raw = page.read_text(encoding="utf-8")
        rel = page.relative_to(site).as_posix()
        if rel == "404.html":
            continue  # the root 404 is served at any missing URL, so it is self-contained (no relative font/CSS refs)
        for font in fonts:
            if font.name not in raw:
                fails.append(f"{rel}: does not preload {font.name}")
    return fails
