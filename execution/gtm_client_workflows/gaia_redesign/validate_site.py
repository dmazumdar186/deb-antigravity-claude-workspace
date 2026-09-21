"""Validate a rendered Gaia Talent static site before it is called shippable.

description: Structural, accessibility and honesty checks over the built site —
  relative paths only, every local reference resolves, every image is dimensioned
  and described, JSON-LD parses, the rendered role count matches the dataset, no
  placeholder or forbidden vocabulary on the public pages, and the CSS/JS weight
  budgets hold.
inputs: a built site directory, the job records it was rendered from
outputs: a list of failure strings (empty means the build passes)
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# The public pages must not read as a machine wrote them. The note to the
# client is the one page allowed to discuss how it was built.
FORBIDDEN = [
    (r"\bAI\b", "AI"),
    (r"\bA\.I\.", "A.I."),
    (r"\bClaude\b", "Claude"),
    (r"\bartificial intelligence\b", "artificial intelligence"),
    (r"\bautomat(?:ion|ed|ically)\b", "automation"),
    (r"\bnuclear\b", "nuclear"),
    (r"\bLLM\b", "LLM"),
    (r"\bHidden Depth\b", "Hidden Depth"),
    (r"615983", "615983"),
    (r"\bCRO\b", "CRO"),
    (r"\bWordPress\b", "WordPress"),
    (r"\bTODO\b", "TODO"),
    (r"\blorem ipsum\b", "lorem ipsum"),
    (r"\bLorem\b", "Lorem"),
    (r"\bplaceholder text\b", "placeholder text"),
    (r"\bXXX\b", "XXX"),
]
EXEMPT_PAGES = {"for-keith/index.html"}
CSS_BUDGET = 45 * 1024
# Round 4 (2026-09-17) added real accessibility-correctness code required by
# the handoff — clearing stale inert/aria-hidden on the process-stack cards
# and flow panels when leaving desktop-motion mode, the stackFrozen resize
# guard, and the menu focus-move fix — which pushed the published JS ~1KB
# over the old 30KB budget. Raised to 32KB rather than cutting that code.
JS_BUDGET = 32 * 1024


class _Doc(HTMLParser):
    """Collects the handful of facts the checks need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[dict[str, str]] = []
        self.refs: list[tuple[str, str]] = []  # (attr, value)
        self.h1 = 0
        self.h1_fallback = 0
        self._in_fallback = False
        self.titles = 0
        self.robots = False
        self.lang = ""
        self.jsonld: list[str] = []
        self.labels: set[str] = set()
        self.field_ids: list[tuple[str, str]] = []  # (tag, id)
        self._in_ld = False
        self._in_title = False
        self.title_text = ""
        self.job_rows = 0
        self.job_hrefs: list[str] = []
        self.options: list[str] = []
        self._current_select_id = ""
        self.sector_options: list[str] = []
        self.featured_rows = 0
        self.ticker_links = 0
        self.team_rows = 0
        self.jobs_com_hrefs: list[str] = []

    # The hero fallback is delimited by two marker comments rather than by
    # element nesting: HTMLParser does not close <p>/<li> implicitly, so a depth
    # counter drifts on real markup and the one-h1 check would misfire.
    FALLBACK_OPEN = "flow-fallback:start"
    FALLBACK_CLOSE = "flow-fallback:end"

    def handle_comment(self, data: str) -> None:
        token = data.strip()
        if token == self.FALLBACK_OPEN:
            self._in_fallback = True
        elif token == self.FALLBACK_CLOSE:
            self._in_fallback = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "title":
            self.titles += 1
            self._in_title = True
        if tag == "h1":
            # The hero ships two renderings of the same content: the pinned
            # canvas stage and the stacked fallback used below 800px, under
            # reduced motion and with JS off. Exactly one is ever displayed, so
            # each path is required to carry exactly one h1.
            if self._in_fallback:
                self.h1_fallback += 1
            else:
                self.h1 += 1
        if tag == "meta" and a.get("name", "").lower() == "robots":
            self.robots = "noindex" in a.get("content", "").lower()
        if tag == "img":
            self.images.append(a)
        for attr in ("href", "src"):
            if attr in a:
                self.refs.append((attr, a[attr]))
                if attr == "href" and "gaiatalent.com/jobs/" in a[attr]:
                    self.jobs_com_hrefs.append(a[attr])
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self.jsonld.append("")
        if tag == "label" and a.get("for"):
            self.labels.add(a["for"])
        if tag in ("input", "select", "textarea"):
            if a.get("type") not in ("hidden", "submit", "button"):
                self.field_ids.append((tag, a.get("id", "")))
            if tag == "select":
                self._current_select_id = a.get("id", "")
        if tag == "option":
            self.options.append(a.get("value", ""))
            if self._current_select_id == "f-sector":
                self.sector_options.append(a.get("value", ""))
        cls = a.get("class", "").split()
        if "rolerow" in cls:
            if "data-job" in a:
                self.job_hrefs.append(a.get("href", ""))
            if "data-job" in a:
                self.job_rows += 1
            else:
                self.featured_rows += 1
        if "person" in cls:
            self.team_rows += 1
        if tag == "a" and "ticker" in a.get("data-scope", ""):
            self.ticker_links += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_ld = False
        if tag == "title":
            self._in_title = False
        if tag == "select":
            self._current_select_id = ""

    def handle_data(self, data: str) -> None:
        if self._in_ld and self.jsonld:
            self.jsonld[-1] += data
        if self._in_title:
            self.title_text += data


DANGEROUS_SCHEMES = ("javascript:", "data:", "vbscript:", "file:")


def _is_local(value: str) -> bool:
    low = value.strip().lower()
    if not low or low.startswith(("#", "mailto:", "tel:")):
        return False
    return not re.match(r"^(?:https?:)?//", low)


def _strip_comments(text: str) -> str:
    """Remove HTML comments so template markers and notes are not word-checked."""
    return re.sub(r"<!--.*?-->", " ", text, flags=re.S)


def _visible_text(html: str) -> str:
    body = _strip_comments(html)
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body)


def _inside(child: Path, parent: Path) -> bool:
    try:
        return child.resolve().is_relative_to(parent.resolve())
    except (OSError, ValueError):
        return False


_SECMAP_BLOCK = re.compile(r'<div class="secmap">(.*?)</div>', re.S)
_SECMAP_LINK = re.compile(
    r'<a href="jobs/index\.html\?q=([^"]*)"[^>]*>.*?(?:<sup>(\d+)</sup>)?</a>', re.S
)


def _job_haystack(job: dict[str, Any]) -> str:
    """Mirrors build_site.job_haystack; duplicated here rather than imported,
    since build_site imports this module (an import back would be circular)."""
    parts = [
        str(job.get("title", "")),
        str(job.get("location", "")),
        " ".join(job.get("sectors") or []),
        str(job.get("type", "")),
        str(job.get("summary") or ""),
    ]
    return " ".join(parts).lower()


def _check_sector_map(raw: str, jobs: list[dict[str, Any]]) -> list[str]:
    """Every `?q=<term>` link under the home Sectors map must land on exactly
    as many rows as its superscript claims (jobs.js filters by the same
    substring test performed here)."""
    fails: list[str] = []
    block = _SECMAP_BLOCK.search(raw)
    if not block:
        return fails
    haystacks = [_job_haystack(j) for j in jobs]
    from urllib.parse import unquote_plus

    for match in _SECMAP_LINK.finditer(block.group(1)):
        term = unquote_plus(match.group(1)).lower()
        shown = int(match.group(2)) if match.group(2) else 0
        actual = sum(1 for h in haystacks if term in h)
        if actual != shown:
            fails.append(
                f"sector map link q={term!r} shows <sup>{shown}</sup> but matches {actual} job row(s)"
            )
    return fails


def validate(site: Path, jobs: list[dict[str, Any]]) -> list[str]:
    """Return a list of human-readable failures. Empty list means the build passes."""
    fails: list[str] = []
    pages = sorted(p for p in site.rglob("*.html"))
    if not pages:
        return [f"no HTML pages found under {site}"]
    board_options: list[str] = []
    filter_links: list[tuple[str, str]] = []  # (page, href)

    for page in pages:
        rel = page.relative_to(site).as_posix()
        raw = page.read_text(encoding="utf-8")
        doc = _Doc()
        doc.feed(raw)

        leftovers = re.findall(r"<!--\s*@[a-z:0-9]+\s*-->", raw)
        if leftovers:
            fails.append(f"{rel}: unrendered template markers {sorted(set(leftovers))}")

        if not doc.lang:
            fails.append(f"{rel}: <html> has no lang attribute")
        if doc.titles != 1 or not doc.title_text.strip():
            fails.append(f"{rel}: expected exactly one non-empty <title>, found {doc.titles}")
        if doc.h1 != 1:
            fails.append(f"{rel}: expected exactly one <h1>, found {doc.h1}")
        if doc.h1_fallback and doc.h1_fallback != 1:
            fails.append(f"{rel}: the no-motion hero fallback carries {doc.h1_fallback} <h1> elements, expected 1")
        if not doc.robots:
            fails.append(f"{rel}: missing <meta name=robots content=noindex,...>")

        for attr, value in doc.refs:
            if "jobs/index.html?" in value or (rel.startswith("jobs/") and value.startswith("?")):
                filter_links.append((rel, value))
            stripped = value.strip()
            if not stripped:
                fails.append(f"{rel}: empty {attr} attribute")
                continue
            if stripped.lower().startswith(DANGEROUS_SCHEMES):
                fails.append(f"{rel}: {attr}=\"{stripped[:60]}\" uses a forbidden scheme")
                continue
            if stripped.startswith("/"):
                fails.append(f"{rel}: absolute path {attr}=\"{stripped}\" (relative paths only)")
                continue
            if not _is_local(stripped):
                continue
            path_part = stripped.split("#")[0].split("?")[0]
            # A query-only or fragment-only ref points at the page itself.
            target = page.resolve() if not path_part else (page.parent / path_part).resolve()
            if not _inside(target, site):
                fails.append(f"{rel}: {attr}=\"{stripped}\" escapes the site root")
            elif not target.exists():
                fails.append(f"{rel}: {attr}=\"{stripped}\" does not resolve to a file")

        for img in doc.images:
            src = img.get("src", "?")
            if "alt" not in img:
                fails.append(f"{rel}: <img src=\"{src}\"> has no alt attribute")
            elif not img["alt"].strip() and "aria-hidden" not in img:
                fails.append(f"{rel}: <img src=\"{src}\"> has empty alt and is not aria-hidden")
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

        for tag, field_id in doc.field_ids:
            if not field_id:
                fails.append(f"{rel}: a <{tag}> form control has no id, so it cannot be labelled")
            elif field_id not in doc.labels:
                fails.append(f"{rel}: <{tag} id=\"{field_id}\"> has no <label for>")

        if rel not in EXEMPT_PAGES:
            text = html.unescape(_visible_text(raw))
            for pattern, word in FORBIDDEN:
                if re.search(pattern, text):
                    fails.append(f"{rel}: forbidden word on a public page: {word!r}")

        if rel == "jobs/index.html":
            if doc.job_rows != len(jobs):
                fails.append(f"{rel}: rendered {doc.job_rows} role rows, dataset has {len(jobs)}")
            rendered = {h.strip() for h in doc.job_hrefs if h.strip()}
            expected = {str(j["url"]).strip() for j in jobs}
            missing = sorted(expected - rendered)
            extra = sorted(rendered - expected)
            if missing:
                fails.append(f"{rel}: {len(missing)} dataset role URL(s) not on the board, e.g. {missing[0]}")
            if extra:
                fails.append(f"{rel}: {len(extra)} role link(s) not in the dataset, e.g. {extra[0]}")
            board_options[:] = doc.sector_options
        if rel == "index.html":
            if doc.featured_rows != 8:
                fails.append(f"{rel}: expected 8 featured roles, rendered {doc.featured_rows}")
            if doc.ticker_links < 10:
                fails.append(f"{rel}: ticker rendered only {doc.ticker_links} roles")
            if doc.team_rows != 5:
                fails.append(f"{rel}: expected 5 team rows, rendered {doc.team_rows}")
            known_urls = {str(j["url"]).strip() for j in jobs}
            stray = sorted({h.strip() for h in doc.jobs_com_hrefs if h.strip()} - known_urls)
            if stray:
                fails.append(
                    f"{rel}: {len(stray)} gaiatalent.com/jobs/ link(s) (hero cards / featured) "
                    f"not in jobs.json, e.g. {stray[0]}"
                )
            sector_map_fails = _check_sector_map(raw, jobs)
            fails.extend(f"{rel}: {msg}" for msg in sector_map_fails)
        if rel == "team/index.html" and doc.team_rows != 5:
            fails.append(f"{rel}: expected 5 team rows, rendered {doc.team_rows}")

    css = sum(p.stat().st_size for p in site.rglob("*.css"))
    js = sum(p.stat().st_size for p in site.rglob("*.js"))
    if css > CSS_BUDGET:
        fails.append(f"CSS budget: {css} bytes exceeds {CSS_BUDGET}")
    if js > JS_BUDGET:
        fails.append(f"JS budget: {js} bytes exceeds {JS_BUDGET}")
    if (site / "js" / "motion.test.js").exists():
        fails.append("js/motion.test.js was shipped into the site (tests stay in src)")
    # Every ?sector= / ?location= / ?type= link must select something the board
    # can actually offer: an unencoded '&' in a sector name silently splits the
    # query and the link lands on an unfiltered list.
    option_keys = {o.strip().lower() for o in board_options if o.strip()}
    for page_rel, href in filter_links:
        query = parse_qs(urlparse(html.unescape(href)).query, keep_blank_values=True)
        for key in ("sector", "location", "type"):
            for value in query.get(key, []):
                if not value.strip():
                    fails.append(f"{page_rel}: empty ?{key}= in {href}")
                elif key == "sector" and value.strip().lower() not in option_keys:
                    fails.append(
                        f"{page_rel}: ?sector={value!r} in {href} matches no option on the board"
                    )
        for value in query.get("q", []):
            if not value.strip():
                fails.append(f"{page_rel}: empty ?q= in {href}")

    if not (site / "robots.txt").exists():
        fails.append("robots.txt is missing")

    # Fonts are self-hosted: the files must be there and every page must preload
    # them, or the site silently falls back to a system sans.
    font_dir = site / "assets" / "fonts"
    fonts = sorted(font_dir.glob("*.woff2")) if font_dir.is_dir() else []
    if len(fonts) < 2:
        fails.append(f"expected two self-hosted woff2 files in {font_dir}, found {len(fonts)}")
    for page in pages:
        raw = page.read_text(encoding="utf-8")
        rel = page.relative_to(site).as_posix()
        if "fonts.googleapis.com" in raw or "fonts.gstatic.com" in raw:
            fails.append(f"{rel}: still requests fonts from Google; they are self-hosted now")
        for font in fonts:
            if font.name not in raw:
                fails.append(f"{rel}: does not preload {font.name}")

    return fails
