"""Gaia Talent jobs (gaiatalent.com WordPress) -> canonical GreenJobs feed, destination-agnostic.

description: Reads every Gaia job from the public `/wp-json/wp/v2/jobs` endpoint (paginated, count
    checked against X-WP-Total) plus the four job taxonomies, normalises each to a canonical record
    (stable `gaia:<wp id>`, sanitised description html, dates, apply method), maps Gaia taxonomy to
    the GreenJobs sector / region / job-type vocabulary (dictionary first, Jev on unmatched or
    conflicting values, review queue below the confidence cut, never guessed), flags jobs already
    on the GreenJobs boards (deterministic title + employer + location first, Jev noul on ambiguous
    pairs), and writes feed.json, feed.xml, sync_report.json and review_queue.json. Nothing is
    posted anywhere: the outputs are files a destination (Cavuno XML import or our D1) pulls.
inputs: --offline FIXTURE (snapshot JSON; no network) or live fetch; --board-jobs PATH (repeatable;
    scrape_greenjobs.py {site,jobs} JSON, a list of jobs, or a GreenJobs RSS .xml with --board-site);
    --out DIR (default .tmp/gaia_feed); --no-jev; --jev-cut 0.6; --dup-hi 0.8 --dup-lo 0.2;
    --save-fixture PATH (write the live fetch as a snapshot); --max-removed-share 0.5.
outputs: {out}/feed.json, feed.xml, sync_report.json, review_queue.json, jev_cache.json. Files are
    rewritten only when their bytes change; no wall-clock time is written, so a re-run with no
    source change is byte-identical. Exit 0 ok, 2 usage, 3 gate (count mismatch, empty fetch,
    removal above the ceiling).
CLI:
  python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_sync.py \\
      --board-jobs .tmp/gj/ie.json --board-jobs .tmp/gj/uk.json --out .tmp/gaia_feed
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # .env is optional: the only secret (OpenRouter key) may already be in the environment
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # stdlib-only fallback; Jev then reads the process env
    pass

import build_site  # noqa: E402  (TAXONOMY = the GreenJobs sector vocabulary)

API = "https://gaiatalent.com/wp-json/wp/v2"
TAXONOMIES = ("job_location", "job_category", "job_type", "job_sector")
UA = "GreenJobsFeedSync/1.0 (read-only job feed sync; contact via gaiatalent.com owner)"
TIMEOUT_S = 20
RETRIES = 3
PAGE_SLEEP_S = 0.5
MAPPING_PATH = HERE / "gaia_feed_mapping.json"
REGIONS_DIR = ROOT / "deliverables" / build_site.PROJECT / "src" / "data"
SECTORS = [t[0] for t in build_site.TAXONOMY]
NONE = "@none"  # mapping sentinel: the edition's "Nationwide / remote" label

# ---------------------------------------------------------------- fetch

Getter = Callable[[str], tuple[Any, dict[str, str]]]


def http_get_json(url: str) -> tuple[Any, dict[str, str]]:
    """GET JSON with an honest UA, timeout and retries (429/5xx/network: 1 s, 2 s, 4 s backoff)."""
    last: Exception | None = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                return json.loads(resp.read().decode("utf-8")), hdrs
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise
            last = exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        time.sleep(2**attempt)
    raise RuntimeError(f"GET failed after {RETRIES} tries: {url}: {last}")


def fetch_paged(
    get: Getter, path: str, params: dict[str, str], sleep_s: float = PAGE_SLEEP_S
) -> list[dict]:
    """Every page of a WP collection. Fails loud if the rows do not add up to X-WP-Total."""
    rows: list[dict] = []
    page, pages, total = 1, 1, None
    while page <= pages:
        q = urllib.parse.urlencode({**params, "per_page": 100, "page": page})
        data, hdrs = get(f"{API}/{path}?{q}")
        if not isinstance(data, list):
            raise RuntimeError(f"{path} page {page}: expected a list")
        rows.extend(data)
        pages = int(hdrs.get("x-wp-totalpages", pages) or pages)
        total = int(hdrs["x-wp-total"]) if hdrs.get("x-wp-total") else total
        page += 1
        if page <= pages and sleep_s:
            time.sleep(sleep_s)
    if total is not None and len(rows) != total:
        raise GateError(f"{path}: fetched {len(rows)} rows but X-WP-Total says {total}")
    return rows


class GateError(RuntimeError):
    pass


def fetch_live(
    get: Getter = http_get_json, sleep_s: float = PAGE_SLEEP_S
) -> dict[str, Any]:
    jobs = fetch_paged(get, "jobs", {}, sleep_s)
    tax = {
        t: fetch_paged(get, t, {"_fields": "id,name,slug,parent"}, sleep_s)
        for t in TAXONOMIES
    }
    return snapshot(jobs, tax)


def snapshot(jobs: list[dict], tax: dict[str, list[dict]]) -> dict[str, Any]:
    """Trim raw WP rows to what the sync reads (drops the Yoast payload); this is the fixture format."""
    keep = ("id", "date_gmt", "modified_gmt", "slug", "status", "link", *TAXONOMIES)
    out = []
    for j in sorted(jobs, key=lambda r: r["id"]):
        r = {k: j.get(k) for k in keep}
        r["title"] = (j.get("title") or {}).get("rendered", "")
        r["content"] = (j.get("content") or {}).get("rendered", "")
        ov = (j.get("acf") or {}).get("hdt_jobs_overview") or {}
        r["acf"] = {
            k: ov.get(k)
            for k in (
                "overview_salary",
                "overview_closing_date",
                "overview_start_date",
                "overview_ref",
            )
        }
        out.append(r)
    return {
        "source": API + "/jobs",
        "total": len(out),
        "jobs": out,
        "taxonomies": {
            t: sorted(
                (
                    {k: x.get(k) for k in ("id", "name", "slug", "parent")}
                    for x in tax[t]
                ),
                key=lambda x: x["id"],
            )
            for t in TAXONOMIES
        },
    }


# ---------------------------------------------------------------- sanitise

ALLOWED = {
    "p",
    "br",
    "ul",
    "ol",
    "li",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "h2",
    "h3",
    "h4",
    "a",
}
DROP_WITH_CONTENT = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "noscript",
    "template",
    "svg",
    "math",
    "form",
}
VOID = {"br"}


class _Sanitiser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.open: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in DROP_WITH_CONTENT:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ("div",):
            tag = "p"
        if tag not in ALLOWED:
            return
        if tag == "a":
            href = (dict(attrs).get("href") or "").strip()
            if not re.match(r"(?i)^(https://|mailto:)", href):
                return
            self.out.append(
                f'<a href="{html.escape(href, quote=True)}" rel="nofollow noopener">'
            )
            self.open.append("a")
            return
        self.out.append(f"<{tag}>")
        if tag not in VOID:
            self.open.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" and not self.skip:
            self.out.append("<br>")

    def handle_endtag(self, tag: str) -> None:
        if tag in DROP_WITH_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "div":
            tag = "p"
        if tag in self.open:
            while self.open:
                t = self.open.pop()
                self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(html.escape(data, quote=False))


def sanitise_html(raw: str) -> str:
    """Allow-list html: no scripts, styles, attributes (except https/mailto href), or event handlers."""
    s = _Sanitiser()
    s.feed(raw or "")
    s.close()
    out = "".join(s.out) + "".join(f"</{t}>" for t in reversed(s.open))
    out = re.sub(r"<p>\s*</p>", "", out)
    out = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", out)
    return re.sub(r"\n\s*\n+", "\n", out).strip()


def plain_text(raw: str) -> str:
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


# ---------------------------------------------------------------- vocab + mapping


def load_mapping(path: Path = MAPPING_PATH) -> dict[str, Any]:
    m = json.loads(path.read_text(encoding="utf-8"))
    for key in ("sector_by_gaia_sector", "sector_by_gaia_category"):
        bad = [v for v in m[key].values() if v is not None and v not in SECTORS]
        if bad:
            raise ValueError(f"{key}: not GreenJobs sectors: {bad}")
    bad = [
        v
        for v in m["type_by_gaia_type"].values()
        if v is not None and v not in m["greenjobs_types"]
    ]
    if bad:
        raise ValueError(f"type_by_gaia_type: not GreenJobs types: {bad}")
    return m


def load_regions(regions_dir: Path = REGIONS_DIR) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ed in ("ie", "uk"):
        t = json.loads((regions_dir / f"regions_{ed}.json").read_text(encoding="utf-8"))
        out[ed] = {"none": t["none_label"], "regions": t["regions"]}
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip().lower()


def region_lookup(regions: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """lower-case name or alias -> (edition, region name)."""
    idx: dict[str, tuple[str, str]] = {}
    for ed, t in regions.items():
        for name, aliases in t["regions"].items():
            idx.setdefault(name.lower(), (ed, name))
            for a in aliases:
                idx.setdefault(a.lower(), (ed, name))
    return idx


_LOC_LINE = re.compile(
    r"(?i)\blocations?\s*:\s*(.{1,120}?)(?=\s+(?:job type|sector|salary|level|working|employment|type|about|the|overview|contract|discipline|position|we|our)\b|$)"
)


def places_in(text: str, idx: dict[str, tuple[str, str]]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    low = text.lower()
    for key, val in idx.items():
        if (
            len(key) > 2
            and re.search(rf"\b{re.escape(key)}\b", low)
            and val not in found
        ):
            found.append(val)
    return found


CONTRACT_HINT = re.compile(
    r"(?i)\b(fixed[- ]term|specified purpose|contract\s*:|temporary|maternity cover|\d+\s*(?:-\s*\d+\s*)?months?\b)"
)


class Jev:
    """Jev tier with a disk cache so re-runs never re-ask (cost 0, byte-identical outputs)."""

    def __init__(self, cache_path: Path | None, enabled: bool) -> None:
        self.cache_path = cache_path
        self.cache: dict[str, Any] = {}
        if cache_path and cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
        from execution.modules import jev_client

        self.client = jev_client
        self.enabled = enabled and jev_client.available()
        self.reason = (
            ""
            if self.enabled
            else ("disabled by --no-jev" if not enabled else "no OpenRouter key")
        )
        self.calls = 0
        self.cost = 0.0
        self.errors = 0

    @staticmethod
    def key(state: Any, questions: Any) -> str:
        return hashlib.sha256(
            json.dumps([state, questions], sort_keys=True).encode()
        ).hexdigest()[:24]

    def ask_many(self, items: list[tuple[Any, dict]]) -> list[dict | None]:
        """items: (state, questions). Returns cached/served answers dict or None (not run / failed)."""
        out: list[dict | None] = [None] * len(items)
        todo = []
        for i, (state, qs) in enumerate(items):
            k = self.key(state, qs)
            if k in self.cache:
                out[i] = self.cache[k]
            elif self.enabled:
                todo.append((i, k, state, qs))
        if todo:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=8) as pool:
                res = list(pool.map(lambda t: self.client.decide(t[2], t[3]), todo))
            for (i, k, _s, _q), r in zip(todo, res):
                self.calls += 1
                if not r.ok:
                    self.errors += 1
                    continue
                self.cost += r.cost_usd
                self.cache[k] = r.answers
                out[i] = r.answers
            self.client.append_ledger(
                {
                    "caller": "gaia_feed_sync",
                    "calls": len(todo),
                    "cost_usd": round(self.cost, 6),
                },
                ROOT / ".tmp" / "jev_ledger.jsonl",
            )
        return out

    def save(self) -> None:
        if self.cache_path:
            write_if_changed(
                self.cache_path,
                json.dumps(
                    dict(sorted(self.cache.items())), indent=1, ensure_ascii=False
                )
                + "\n",
            )


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def sector_question() -> dict[str, Any]:
    opts = {
        _slug(n): f"{n}: roles about " + ", ".join(kw[:6])
        for n, _c, _d, kw in build_site.TAXONOMY
    }
    opts["none"] = "none of these sectors fits the role"
    return {
        "sector": {
            "type": "choice",
            "instructions": "Which GreenJobs sector would a job seeker browse to find this role? Judge by the job title first, then the work described. Prefer the specific sector over an umbrella one.",
            "criteria": opts,
        }
    }


def region_question(regions: dict[str, Any], editions: list[str]) -> dict[str, Any]:
    """Options are the regions of the source's editions only (Gaia: Irish counties), so Jev cannot
    put an Irish "Midlands" role in the English West Midlands."""
    opts = {}
    for ed, t in regions.items():
        if ed not in editions:
            continue
        for name, aliases in t["regions"].items():
            opts[f"{ed}_{_slug(name)}"] = (
                f"{name} ({'Ireland county' if ed == 'ie' else 'UK region'})"
                + (f", includes {', '.join(aliases[:5])}" if aliases else "")
            )
    opts["nationwide"] = (
        "the role is nationwide, remote, or spread over several counties/regions with no main base"
    )
    opts["none"] = "cannot tell where the role is based"
    return {
        "region": {
            "type": "choice",
            "instructions": "Where is this job based? Use the stated Location line and the place the role is based in; if several places are offered, pick the one the advert lists for this posting (location_term) when it is among them, else the first listed.",
            "criteria": opts,
        }
    }


def type_question(types: list[str]) -> dict[str, Any]:
    opts = {_slug(t): t for t in types}
    opts["none"] = "the advert does not say"
    return {
        "job_type": {
            "type": "choice",
            "instructions": "Which employment type is this job? A fixed-term, specified-purpose or time-limited role is Contract; a permanent full-time role is Permanent.",
            "criteria": opts,
        }
    }


def title_sectors(title: str) -> list[str]:
    """GreenJobs sectors whose keywords (build_site.TAXONOMY, whole words) appear in the title."""
    low = html.unescape(title or "").lower()
    return [
        n
        for n, _c, _d, words in build_site.TAXONOMY
        if build_site._word_hits(low, words) > 0
    ]


def map_jobs(
    records: list[dict],
    mapping: dict[str, Any],
    regions: dict[str, Any],
    jev: Jev,
    cut: float,
    force_jev: bool = False,
) -> None:
    """Fill rec['mapping'][dim] = {value, method: dict|jev|queue, confidence, reason}.

    force_jev=True skips the dictionary (eval only: measures the Jev tier on every job).
    """
    idx = region_lookup(regions)
    sec_dict, cat_dict = (
        ({}, {})
        if force_jev
        else (mapping["sector_by_gaia_sector"], mapping["sector_by_gaia_category"])
    )
    loc_dict, type_dict = (
        ({}, {})
        if force_jev
        else (mapping["region_by_gaia_location"], mapping["type_by_gaia_type"])
    )
    if force_jev:
        idx = {}
    pending: list[tuple[dict, str, Any, dict, Callable[[str], Any]]] = []
    sq, rq, tq = (
        sector_question(),
        region_question(regions, mapping["default_boards"]),
        type_question(mapping["greenjobs_types"]),
    )
    sec_back = {_slug(n): n for n in SECTORS}
    reg_back = {
        f"{ed}_{_slug(n)}": (ed, n) for ed, t in regions.items() for n in t["regions"]
    }
    type_back = {_slug(t): t for t in mapping["greenjobs_types"]}

    for r in records:
        r["mapping"] = {}
        text = r["description_text"]
        head = text[:700]
        # sector: gaia sector term, then category term
        val, why = None, "no dictionary entry"
        for term in r["gaia"]["sector"]:
            if sec_dict.get(_norm(term)):
                val, why = sec_dict[_norm(term)], f"sector term '{term}'"
                break
        if not val:
            for term in r["gaia"]["category"]:
                if cat_dict.get(_norm(term)):
                    val, why = cat_dict[_norm(term)], f"category term '{term}'"
                    break
        # title keywords from the board's own taxonomy (build_site.TAXONOMY) are the strongest
        # signal; a title naming two sectors, or disagreeing with the term dictionary, is a
        # conflict and goes to Jev rather than being guessed
        title_hits = [] if force_jev else title_sectors(r["title"])
        conflict_note = None
        if len(title_hits) == 1 and val in (None, title_hits[0]):
            val, why = (
                title_hits[0],
                f"title keyword ({why if val else 'no term entry'})",
            )
        elif title_hits:
            conflict_note = (
                f"title names {title_hits}; Gaia terms say {val or 'nothing decisive'}"
            )
            val = None
        if val:
            r["mapping"]["sector"] = {
                "value": val,
                "method": "dict",
                "confidence": 1.0,
                "reason": why,
            }
        else:
            state = {
                "title": r["title"],
                "gaia_sector": r["gaia"]["sector"],
                "gaia_category": r["gaia"]["category"],
                "advert_opening": text[:900],
            }
            if conflict_note:
                state["note"] = conflict_note
            pending.append((r, "sector", state, sq, lambda k: sec_back.get(k)))
        # region: location term (aliases + gaia dictionary), unless the advert's Location line excludes it
        term = (r["gaia"]["location"] or [""])[0]
        hit: Any = None
        if _norm(term) in loc_dict:
            v = loc_dict[_norm(term)]
            hit = (
                ("ie", NONE)
                if v == NONE
                else (None if v is None else idx.get(v.lower()))
            )
        elif _norm(term) in idx:
            hit = idx[_norm(term)]
        m = _LOC_LINE.search(head)
        stated = places_in(m.group(1), idx) if m else []
        conflict = bool(hit and hit[1] != NONE and stated and hit not in stated)
        if hit and not conflict:
            ed, name = hit
            r["mapping"]["region"] = {
                "value": regions[ed]["none"] if name == NONE else name,
                "edition": ed,
                "method": "dict",
                "confidence": 1.0,
                "reason": f"location term '{term}'",
            }
        else:
            state = {"title": r["title"], "location_term": term, "advert_opening": head}
            if conflict:
                state["note"] = (
                    "the advert's Location line does not include location_term"
                )
            pending.append(
                (
                    r,
                    "region",
                    state,
                    rq,
                    lambda k: reg_back.get(k) or ({"nationwide": (mapping["default_boards"][0], NONE)}.get(k)),
                )
            )
        # job type
        tterm = (r["gaia"]["type"] or [""])[0]
        tv = type_dict.get(_norm(tterm))
        if tv == "Permanent" and CONTRACT_HINT.search(text):
            tv = None  # the advert text contradicts the term: let Jev read it
        if tv:
            r["mapping"]["job_type"] = {
                "value": tv,
                "method": "dict",
                "confidence": 1.0,
                "reason": f"type term '{tterm}'",
            }
        else:
            state = {
                "title": r["title"],
                "type_term": tterm,
                "advert_opening": head,
                "contract_mentions": [
                    mm.group(0) for mm in CONTRACT_HINT.finditer(text)
                ][:5],
            }
            pending.append((r, "job_type", state, tq, lambda k: type_back.get(k)))

    answers = jev.ask_many([(p[2], p[3]) for p in pending])
    for (r, dim, _state, qs, back), ans in zip(pending, answers):
        qname = next(iter(qs))
        if ans is None:
            r["mapping"][dim] = {
                "value": None,
                "method": "queue",
                "confidence": 0.0,
                "reason": "no dictionary match; Jev " + (jev.reason or "call failed"),
            }
            continue
        a = ans.get(qname) or {}
        choice, conf = str(a.get("choice", "")), float(a.get("confidence", 0.0) or 0.0)
        mapped = back(choice)
        if dim == "region" and mapped is not None:
            ed, name = mapped
            shown: Any = regions[ed]["none"] if name == NONE else name
        else:
            shown = mapped
        if mapped is None or conf < cut:
            r["mapping"][dim] = {
                "jev_value": shown,  # what Jev would have picked (eval sweep); never published
                "value": None,
                "value": None,
                "method": "queue",
                "confidence": round(conf, 3),
                "reason": (
                    f"Jev '{choice}' below cut {cut}"
                    if mapped
                    else f"Jev abstained ('{choice}')"
                ),
                "jev_choice": choice,
            }
            continue
        entry: dict[str, Any] = {
            "method": "jev",
            "confidence": round(conf, 3),
            "reason": "Jev choice",
        }
        if dim == "region":
            ed, name = mapped
            entry.update(
                value=regions[ed]["none"] if name == NONE else name, edition=ed
            )
        else:
            entry["value"] = mapped
        r["mapping"][dim] = entry


# ---------------------------------------------------------------- normalise


def normalise(snap: dict[str, Any], mapping: dict[str, Any]) -> list[dict]:
    terms = {
        t: {x["id"]: html.unescape(x["name"]) for x in snap["taxonomies"].get(t, [])}
        for t in TAXONOMIES
    }
    recs = []
    for j in snap["jobs"]:
        if j.get("status", "publish") != "publish":
            continue
        content = j.get("content") or ""
        emails = sorted(
            set(re.findall(r"mailto:([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", content, re.I))
        )
        acf = j.get("acf") or {}
        link = j.get("link") or ""
        apply = (
            {"method": "email", "email": emails[0], "url": link}
            if emails
            else {"method": "url", "url": link}
        )
        recs.append(
            {
                "source_id": f"gaia:{j['id']}",
                "wp_id": j["id"],
                "title": html.unescape(j.get("title") or "").strip(),
                "url": link,
                "description_html": sanitise_html(content),
                "description_text": plain_text(content),
                "gaia": {
                    "location": [
                        terms["job_location"].get(i, f"#{i}")
                        for i in j.get("job_location") or []
                    ],
                    "sector": [
                        terms["job_sector"].get(i, f"#{i}")
                        for i in j.get("job_sector") or []
                    ],
                    "category": [
                        terms["job_category"].get(i, f"#{i}")
                        for i in j.get("job_category") or []
                    ],
                    "type": [
                        terms["job_type"].get(i, f"#{i}")
                        for i in j.get("job_type") or []
                    ],
                },
                "salary_text": (acf.get("overview_salary") or "").strip() or None,
                "posted_at": (
                    (j.get("date_gmt") or "") + "Z" if j.get("date_gmt") else None
                ),
                "modified_at": (
                    (j.get("modified_gmt") or "") + "Z"
                    if j.get("modified_gmt")
                    else None
                ),
                "expires_at": acf.get("overview_closing_date") or None,
                "apply": apply,
            }
        )
    return sorted(recs, key=lambda r: r["wp_id"])


# ---------------------------------------------------------------- dedupe


def norm_title(t: str) -> str:
    t = html.unescape(t or "").lower().replace("&", " and ")
    t = re.sub(r"[‐-―/|()\-,.:;]+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def title_sim(a: str, b: str) -> float:
    sa, sb = set(norm_title(a).split()), set(norm_title(b).split())
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def is_gaia(employer: str | None) -> bool | None:
    if not employer:
        return None
    return "gaia" in employer.lower()


def load_board(path: Path, site: str | None = None) -> list[dict]:
    """Board jobs from scrape_greenjobs JSON ({site, jobs}), a plain list, or a GreenJobs RSS file."""
    if path.suffix.lower() == ".xml":
        root = ET.parse(path).getroot()
        out = []
        for it in root.iter("item"):
            link = it.findtext("link") or ""
            m = re.search(r"[?&]v=(\d+)", link)
            out.append(
                {
                    "id": m.group(1) if m else link,
                    "site": site or "ie",
                    "title": it.findtext("title") or "",
                    "employer": None,
                    "location": None,
                    "url": link,
                    "text": plain_text(it.findtext("description") or "")[:2000],
                }
            )
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    s = site or (data.get("site") if isinstance(data, dict) else None)
    out = []
    for j in jobs:
        out.append(
            {
                "id": str(j["id"]),
                "site": j.get("site") or s or "ie",
                "title": j.get("title") or "",
                "employer": j.get("employer"),
                "location": j.get("location"),
                "url": j.get("url"),
                # advert text (first 2000 chars): enough to tell a copied advert from a
                # sister advert that shares only the client's boilerplate opening
                "text": (
                    plain_text(j["description_html"])
                    if j.get("description_html")
                    else (j.get("text") or j.get("summary") or "")
                )[:2000],
            }
        )
    return out


def board_region(b: dict, idx: dict[str, tuple[str, str]]) -> list[tuple[str, str]]:
    return places_in(b.get("location") or "", idx)


def shingles(text: str, k: int = 5) -> set[str]:
    w = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {" ".join(w[i : i + k]) for i in range(max(0, len(w) - k + 1))}


def text_containment(a: str, b: str) -> float:
    """Share of the shorter text's 5-word shingles found in the other (1.0 = one copies the other)."""
    sa, sb = shingles(a), shingles(b)
    return len(sa & sb) / min(len(sa), len(sb)) if sa and sb else 0.0


VERBATIM = 0.5  # containment at or above this is a copied advert


def pair_rule(g: dict, b: dict, idx: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """Deterministic tier. Returns (verdict, reason); verdict dup | not | ambiguous.

    dup only on a copied advert (text containment >= VERBATIM) by Gaia Talent. A same-title
    rewrite is ambiguous, never auto-merged: Gaia runs near-identical senior roles for several
    clients at once (e.g. two 'Senior Town Planner' vacancies), so the title alone is not proof.
    """
    sim = title_sim(g["title"], b["title"])
    gaia = is_gaia(b.get("employer"))
    if gaia is False:
        return "not", "board employer is not Gaia Talent"
    cont = text_containment(g["description_text"], b.get("text") or "")
    if sim < 0.5 and cont < VERBATIM:
        return "not", f"title similarity {sim:.2f} < 0.5, text containment {cont:.2f}"
    if gaia and cont >= VERBATIM:
        return (
            "dup",
            f"copied advert (text containment {cont:.2f}), employer Gaia Talent",
        )
    same_title = norm_title(g["title"]) == norm_title(b["title"])
    g_places = places_in(g["gaia_location_text"], idx)
    b_places = board_region(b, idx)
    loc_ok = (not b_places) or (not g_places) or bool(set(g_places) & set(b_places))
    if not loc_ok and not same_title:
        return "not", f"title similarity {sim:.2f}, different title and location"
    return (
        "ambiguous",
        f"title similarity {sim:.2f}{' (same title)' if same_title else ''}, text containment {cont:.2f}, "
        f"employer {'Gaia' if gaia else 'unknown'}, location {'compatible' if loc_ok else 'differs'}",
    )


DUP_Q = {
    "same": {
        "type": "noul",
        "instructions": "Are feed_job and board_job the same vacancy (one job advertised twice), not just two similar roles?",
        "criteria": {
            "true": "same role title and seniority at the same place for the same hiring client; wording may differ",
            "false": "a different role, seniority, specialism, location or client",
        },
    }
}


def dedupe(
    records: list[dict],
    board: list[dict],
    regions: dict[str, Any],
    jev: Jev,
    hi: float,
    lo: float,
) -> dict[str, Any]:
    judged = judge_pairs([(r, b) for r in records for b in board], regions, jev, hi, lo)
    pairs = [p for p in judged if not (p["verdict"] == "not" and p["method"] == "rule")]
    for r in records:
        r["on_board"] = sorted(
            [
                {
                    "site": p["board_site"],
                    "board_id": p["board_id"],
                    "method": p["method"],
                }
                for p in pairs
                if p["source_id"] == r["source_id"] and p["verdict"] == "dup"
            ],
            key=lambda x: (x["site"], x["board_id"]),
        )
    dup_board = {
        (p["board_site"], p["board_id"]) for p in pairs if p["verdict"] == "dup"
    }
    board_only = sorted(
        [
            {"site": b["site"], "board_id": b["id"], "title": b["title"]}
            for b in board
            if is_gaia(b.get("employer")) and (b["site"], b["id"]) not in dup_board
        ],
        key=lambda x: (x["site"], x["board_id"]),
    )
    return {
        "pairs": sorted(
            pairs, key=lambda p: (p["source_id"], p["board_site"], p["board_id"])
        ),
        "board_only": board_only,
    }


def judge_pairs(
    items: list[tuple[dict, dict]],
    regions: dict[str, Any],
    jev: Jev,
    hi: float,
    lo: float,
) -> list[dict]:
    """Verdict per (feed record, board job): rule tier, then Jev noul on ambiguous pairs.
    verdict dup | not | queue (Jev between lo and hi, or Jev not run)."""
    idx = region_lookup(regions)
    pairs, amb = [], []
    for r, b in items:
        r.setdefault(
            "gaia_location_text",
            " ".join(r["gaia"]["location"]) + " " + r["description_text"][:400],
        )
        verdict, why = pair_rule(r, b, idx)
        p = {
            "source_id": r["source_id"],
            "board_site": b["site"],
            "board_id": b["id"],
            "verdict": verdict,
            "method": "rule",
            "reason": why,
        }
        pairs.append(p)
        if verdict == "ambiguous":
            amb.append((p, r, b))
    # one advert is one vacancy: a board advert already proven to be a copy of one feed job is
    # not also a duplicate of another (Gaia runs same-title roles for different clients)
    copied = {
        (p["board_site"], p["board_id"]): p["source_id"]
        for p in pairs
        if p["verdict"] == "dup"
    }
    still = []
    for p, r, b in amb:
        other = copied.get((b["site"], b["id"]))
        if other and other != r["source_id"]:
            p.update(verdict="not", reason=f"board advert is already a copy of {other}")
        else:
            still.append((p, r, b))
    amb = still
    states = [
        (
            {
                "feed_job": {
                    "title": r["title"],
                    "employer": "Gaia Talent",
                    "location": r["gaia"]["location"],
                    "opening": r["description_text"][:500],
                },
                "board_job": {
                    "title": b["title"],
                    "employer": b.get("employer") or "unknown",
                    "location": b.get("location") or "unknown",
                    "opening": (b.get("text") or "")[:500],
                },
            },
            DUP_Q,
        )
        for _p, r, b in amb
    ]
    for (p, _r, _b), ans in zip(amb, jev.ask_many(states)):
        if ans is None:
            p.update(
                verdict="queue",
                reason=p["reason"] + "; Jev " + (jev.reason or "call failed"),
            )
            continue
        pv = float((ans.get("same") or {}).get("noul", 0.5))
        p["jev_noul"] = round(pv, 3)
        p["method"] = "jev"
        p["verdict"] = "dup" if pv >= hi else "not" if pv <= lo else "queue"
    for r, _b in items:
        r.pop("gaia_location_text", None)
    return pairs


# ---------------------------------------------------------------- outputs


def write_if_changed(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return True


def content_hash(r: dict) -> str:
    keys = (
        "title",
        "url",
        "description_html",
        "location",
        "sector",
        "region",
        "job_type",
        "salary_text",
        "posted_at",
        "modified_at",
        "expires_at",
        "apply",
        "boards",
    )
    return hashlib.sha256(
        json.dumps({k: r.get(k) for k in keys}, sort_keys=True).encode()
    ).hexdigest()[:16]


def finalise(records: list[dict], mapping: dict[str, Any]) -> list[dict]:
    out = []
    for r in records:
        m = r["mapping"]
        ed = (m.get("region") or {}).get("edition")
        boards = [ed] if ed in ("ie", "uk") else list(mapping["default_boards"])
        rec = {
            "source_id": r["source_id"],
            "source": "gaia",
            "title": r["title"],
            "url": r["url"],
            "description_html": r["description_html"],
            "location": ", ".join(r["gaia"]["location"]) or None,
            "sector": (m.get("sector") or {}).get("value"),
            "region": (m.get("region") or {}).get("value"),
            "job_type": (m.get("job_type") or {}).get("value"),
            "salary_text": r["salary_text"],
            "posted_at": r["posted_at"],
            "modified_at": r["modified_at"],
            "expires_at": r["expires_at"],
            "apply": r["apply"],
            "boards": boards,
            "gaia_terms": r["gaia"],
            "mapping": m,
            "on_board": r.get("on_board", []),
            "status": (
                "needs_review"
                if any(
                    (m.get(d) or {}).get("method") == "queue"
                    for d in ("sector", "region", "job_type")
                )
                else "ready"
            ),
        }
        rec["content_hash"] = content_hash(rec)
        out.append(rec)
    return out


def to_xml(feed: list[dict], generated: str) -> str:
    root = ET.Element(
        "jobs",
        {"source": "gaiatalent.com", "generated": generated, "count": str(len(feed))},
    )
    for r in feed:
        j = ET.SubElement(root, "job")
        cat = r["sector"] or ""
        fields = [
            ("id", r["source_id"]),
            ("title", r["title"]),
            ("description", r["description_html"]),
            ("location", r["location"] or ""),
            ("region", r["region"] or ""),
            ("category", cat),
            ("type", r["job_type"] or ""),
            ("salary", r["salary_text"] or ""),
            ("url", r["url"]),
            ("date", r["posted_at"] or ""),
            ("updated", r["modified_at"] or ""),
            ("expiry", r["expires_at"] or ""),
            ("boards", ",".join(r["boards"])),
            ("status", r["status"]),
        ]
        for k, v in fields:
            ET.SubElement(j, k).text = v
        ap = ET.SubElement(j, "apply", {"method": r["apply"]["method"]})
        ap.text = (
            r["apply"].get("email")
            if r["apply"]["method"] == "email"
            else r["apply"]["url"]
        )
    ET.indent(root)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode")
        + "\n"
    )


def run(
    snap: dict[str, Any],
    board: list[dict],
    out: Path,
    *,
    use_jev: bool = True,
    cut: float = 0.6,
    hi: float = 0.8,
    lo: float = 0.2,
    max_removed_share: float = 0.5,
    regions_dir: Path = REGIONS_DIR,
    mapping_path: Path = MAPPING_PATH,
) -> dict[str, Any]:
    mapping = load_mapping(mapping_path)
    regions = load_regions(regions_dir)
    if not snap.get("jobs"):
        raise GateError("fetched 0 Gaia jobs: refusing to write an empty feed")
    if snap.get("total") is not None and len(snap["jobs"]) != snap["total"]:
        raise GateError(
            f"snapshot holds {len(snap['jobs'])} jobs but says total {snap['total']}"
        )
    jev = Jev(out / "jev_cache.json", use_jev)
    records = normalise(snap, mapping)
    map_jobs(records, mapping, regions, jev, cut)
    dd = (
        dedupe(records, board, regions, jev, hi, lo)
        if board
        else {"pairs": [], "board_only": []}
    )
    feed = finalise(records, mapping)

    prev_path = out / "feed.json"
    prev = {}
    if prev_path.exists():
        prev = {
            r["source_id"]: r.get("content_hash")
            for r in json.loads(prev_path.read_text(encoding="utf-8")).get("jobs", [])
        }
    cur = {r["source_id"]: r["content_hash"] for r in feed}
    removed = sorted(set(prev) - set(cur))
    if prev and len(removed) > max_removed_share * len(prev):
        raise GateError(
            f"{len(removed)} of {len(prev)} jobs would be removed (ceiling {max_removed_share:.0%}); refusing"
        )
    generated = max((r["modified_at"] or "") for r in feed)
    dims = ("sector", "region", "job_type")
    cnt = lambda meth: sum(
        1 for r in feed for d in dims if r["mapping"][d]["method"] == meth
    )  # noqa: E731
    report = {
        "generated": generated,
        "fetched": len(snap["jobs"]),
        "jobs_in_feed": len(feed),
        "decisions": len(feed) * len(dims),
        "mapped_deterministically": cnt("dict"),
        "mapped_by_jev": cnt("jev"),
        "queued": cnt("queue"),
        "jobs_needing_review": sum(1 for r in feed if r["status"] == "needs_review"),
        "jobs_fully_deterministic": sum(
            1 for r in feed if all(r["mapping"][d]["method"] == "dict" for d in dims)
        ),
        "board_jobs_compared": len(board),
        "duplicates_found": sum(1 for r in feed if r["on_board"]),
        "duplicate_pairs": sum(1 for p in dd["pairs"] if p["verdict"] == "dup"),
        "duplicate_pairs_queued": sum(
            1 for p in dd["pairs"] if p["verdict"] == "queue"
        ),
        "board_gaia_jobs_not_in_feed": len(dd["board_only"]),
        "new_vs_board": sum(1 for r in feed if not r["on_board"]) if board else None,
        "new": len(set(cur) - set(prev)),
        "updated": sum(1 for k in cur if k in prev and prev[k] != cur[k]),
        "removed": len(removed),
        "removed_ids": removed,
        "jev": {
            "run": jev.enabled or bool(jev.cache),
            "reason_not_run": jev.reason or None,
            "new_calls": jev.calls,
            "errors": jev.errors,
        },
        "dry_run": True,
    }
    queue = [
        {
            "source_id": r["source_id"],
            "title": r["title"],
            "url": r["url"],
            "dimension": d,
            **r["mapping"][d],
        }
        for r in feed
        for d in dims
        if r["mapping"][d]["method"] == "queue"
    ]
    titles = {r["source_id"]: r["title"] for r in feed}
    queue += [
        {
            "source_id": p["source_id"],
            "title": titles.get(p["source_id"]),
            "dimension": "duplicate",
            "board_site": p["board_site"],
            "board_id": p["board_id"],
            "reason": p["reason"],
            "jev_noul": p.get("jev_noul"),
        }
        for p in dd["pairs"]
        if p["verdict"] == "queue"
    ]
    dump = (
        lambda o: json.dumps(o, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    )  # noqa: E731
    write_if_changed(
        out / "feed.json",
        dump(
            {
                "source": "gaiatalent.com",
                "generated": generated,
                "count": len(feed),
                "jobs": feed,
            }
        ),
    )
    write_if_changed(out / "feed.xml", to_xml(feed, generated))
    write_if_changed(
        out / "review_queue.json", dump({"count": len(queue), "items": queue})
    )
    write_if_changed(out / "dedupe.json", dump(dd))
    # the report describes the change since the last run; on a no-change re-run it converges (and stays identical)
    write_if_changed(out / "sync_report.json", dump(report))
    jev.save()
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", type=Path, help="snapshot JSON (no network)")
    ap.add_argument("--board-jobs", type=Path, action="append", default=[])
    ap.add_argument("--board-site", choices=("ie", "uk"))
    ap.add_argument("--out", type=Path, default=ROOT / ".tmp" / "gaia_feed")
    ap.add_argument("--no-jev", action="store_true")
    ap.add_argument("--jev-cut", type=float, default=0.6)
    ap.add_argument("--dup-hi", type=float, default=0.8)
    ap.add_argument("--dup-lo", type=float, default=0.2)
    ap.add_argument("--max-removed-share", type=float, default=0.5)
    ap.add_argument("--save-fixture", type=Path)
    a = ap.parse_args(argv)
    if not (0 < a.jev_cut <= 1 and 0 <= a.dup_lo < a.dup_hi <= 1):
        print("bad thresholds", file=sys.stderr)
        return 2
    try:
        snap = (
            json.loads(a.offline.read_text(encoding="utf-8"))
            if a.offline
            else fetch_live()
        )
        if a.save_fixture:
            write_if_changed(
                a.save_fixture, json.dumps(snap, indent=1, ensure_ascii=False) + "\n"
            )
        board = [b for p in a.board_jobs for b in load_board(p, a.board_site)]
        rep = run(
            snap,
            board,
            a.out,
            use_jev=not a.no_jev,
            cut=a.jev_cut,
            hi=a.dup_hi,
            lo=a.dup_lo,
            max_removed_share=a.max_removed_share,
        )
    except GateError as exc:
        print(f"GATE: {exc}", file=sys.stderr)
        return 3
    print(json.dumps({k: v for k, v in rep.items() if k != "removed_ids"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
