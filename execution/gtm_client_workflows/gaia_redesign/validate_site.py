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

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

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
    (r"\bTODO\b", "TODO"),
    (r"\blorem ipsum\b", "lorem ipsum"),
    (r"\bLorem\b", "Lorem"),
    (r"\bplaceholder text\b", "placeholder text"),
    (r"\bXXX\b", "XXX"),
]
EXEMPT_PAGES = {"for-keith/index.html"}
CSS_BUDGET = 45 * 1024
JS_BUDGET = 30 * 1024


class _Doc(HTMLParser):
    """Collects the handful of facts the checks need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[dict[str, str]] = []
        self.refs: list[tuple[str, str]] = []  # (attr, value)
        self.h1 = 0
        self.h1_fallback = 0
        self._fb_depth = 0
        self._depth = 0
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
        self.featured_rows = 0
        self.ticker_links = 0
        self.team_rows = 0

    VOID = {"img", "br", "hr", "meta", "link", "input", "source", "area", "col", "wbr"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag not in self.VOID:
            self._depth += 1
            if "flow__fallback" in a.get("class", "").split() and not self._fb_depth:
                self._fb_depth = self._depth
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
            if self._fb_depth:
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
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self.jsonld.append("")
        if tag == "label" and a.get("for"):
            self.labels.add(a["for"])
        if tag in ("input", "select", "textarea"):
            if a.get("type") not in ("hidden", "submit", "button"):
                self.field_ids.append((tag, a.get("id", "")))
        cls = a.get("class", "").split()
        if "rolerow" in cls:
            if "data-job" in a:
                self.job_rows += 1
            else:
                self.featured_rows += 1
        if "person" in cls:
            self.team_rows += 1
        if tag == "a" and "ticker" in a.get("data-scope", ""):
            self.ticker_links += 1

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.VOID:
            if self._fb_depth and self._depth == self._fb_depth:
                self._fb_depth = 0
            self._depth = max(0, self._depth - 1)
        if tag == "script":
            self._in_ld = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_ld and self.jsonld:
            self.jsonld[-1] += data
        if self._in_title:
            self.title_text += data


def _is_local(value: str) -> bool:
    low = value.strip().lower()
    if not low or low.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
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


def validate(site: Path, jobs: list[dict[str, Any]]) -> list[str]:
    """Return a list of human-readable failures. Empty list means the build passes."""
    fails: list[str] = []
    pages = sorted(p for p in site.rglob("*.html"))
    if not pages:
        return [f"no HTML pages found under {site}"]

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
            if value.startswith("/"):
                fails.append(f"{rel}: absolute path {attr}=\"{value}\" (relative paths only)")
                continue
            if not _is_local(value):
                continue
            target = (page.parent / value.split("#")[0].split("?")[0]).resolve()
            if not target.exists():
                fails.append(f"{rel}: {attr}=\"{value}\" does not resolve to a file")

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
            text = _visible_text(raw)
            for pattern, word in FORBIDDEN:
                if re.search(pattern, text):
                    fails.append(f"{rel}: forbidden word on a public page: {word!r}")

        if rel == "jobs/index.html" and doc.job_rows != len(jobs):
            fails.append(f"{rel}: rendered {doc.job_rows} role rows, dataset has {len(jobs)}")
        if rel == "index.html":
            if doc.featured_rows != 8:
                fails.append(f"{rel}: expected 8 featured roles, rendered {doc.featured_rows}")
            if doc.ticker_links < 10:
                fails.append(f"{rel}: ticker rendered only {doc.ticker_links} roles")
            if doc.team_rows != 5:
                fails.append(f"{rel}: expected 5 team rows, rendered {doc.team_rows}")
        if rel == "team/index.html" and doc.team_rows != 5:
            fails.append(f"{rel}: expected 5 team rows, rendered {doc.team_rows}")

    css = sum(p.stat().st_size for p in (site / "css").glob("*.css")) if (site / "css").is_dir() else 0
    js = sum(p.stat().st_size for p in (site / "js").glob("*.js")) if (site / "js").is_dir() else 0
    if css > CSS_BUDGET:
        fails.append(f"CSS budget: {css} bytes exceeds {CSS_BUDGET}")
    if js > JS_BUDGET:
        fails.append(f"JS budget: {js} bytes exceeds {JS_BUDGET}")
    if (site / "js" / "motion.test.js").exists():
        fails.append("js/motion.test.js was shipped into the site (tests stay in src)")
    if not (site / "robots.txt").exists():
        fails.append("robots.txt is missing")

    return fails
