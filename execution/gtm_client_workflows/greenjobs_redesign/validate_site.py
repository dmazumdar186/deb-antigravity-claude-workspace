"""Validate a rendered GreenJobs static site before it is called shippable.

description: Structural, accessibility and honesty checks over the built site:
  relative paths only, every local reference resolves and stays inside the
  site, every <img> has alt + width + height, JSON-LD parses, one <h1> and one
  <title> per page, noindex on every page, every form control labelled, the
  job-page count equals the dataset length per edition, no forbidden
  vocabulary on public pages (for-keith/ exempt; employer-authored description
  blocks exempt), no third-party requests, fonts self-hosted and preloaded,
  CSS/JS weight budgets.
inputs: a built site directory, {edition: [normalised job records]}
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
CSS_BUDGET = 60 * 1024
JS_BUDGET = 60 * 1024
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


def validate(site: Path, jobs_by_edition: dict[str, list[dict[str, Any]]]) -> list[str]:
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
        if re.match(r"^(ie|uk)/index\.html$", rel) and 'data-wind' not in raw:
            fails.append(f"{rel}: home page has no hero canvas host")
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
